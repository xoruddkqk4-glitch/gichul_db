"""
05-gichul_db: 시험지 업로드, 원본 파일 관리 및 시험지 CRUD 라우터 (gichul/routers/exams.py)
"""

import io
import os
import re
import shutil
import zipfile
from typing import List, Optional
from urllib.parse import quote

import pymupdf as fitz
from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel

from .. import answer_keys
from .. import answer_resolver
from .. import database as db
from .. import grammar_analyzer
from .. import listening_parser
from .. import paths
from ..core.state import _ingest_serialized
from ..exam_profiles import get_exam_profile
from ..hwp_parser import get_hwp_text, parse_hwp_explanations, parse_hwp_questions, read_answer_image
from ..logging_config import get_logger
from ..pdf_parser import detect_listening_range, extract_pdf_columns_and_questions
from ..rate_parser import parse_correct_rate_csv
from ..services.ingest import _regenerate_exam_crops, background_auto_analyze_exam_grammar
from ..text_utils import apply_answer_header, normalize_bracket_id, sanitize_upload_filename
from ..validator import cross_validate_and_merge

logger = get_logger("gichul.routers.exams")
UPLOADS_DIR = paths.UPLOADS_DIR

router = APIRouter()


class BatchDeleteRequest(BaseModel):
    exam_ids: List[str]


class SelectiveDeleteRequest(BaseModel):
    exam_ids: List[str]
    delete_raw_files: bool = True
    delete_core_corpus: bool = True
    delete_metadata: bool = True
    delete_rate_data: bool = False


# --- 파일 업로드 및 상호 검증 파이프라인 API ---
@router.post("/api/upload")
@_ingest_serialized
def api_upload_exam(
    background_tasks: BackgroundTasks,
    grade: str = Form("고3"),
    year: int = Form(2024),
    month: int = Form(6),
    exam_type: str = Form("평가원"),
    subtype: Optional[str] = Form(None),
    reading_start: Optional[int] = Form(None),
    reading_end: Optional[int] = Form(None),
    pdf_file: UploadFile = File(...),
    hwp_file: UploadFile = File(...),
    exp_file: Optional[UploadFile] = File(None),
    ans_file: Optional[UploadFile] = File(None),
    csv_file: Optional[UploadFile] = File(None),
    script_file: Optional[UploadFile] = File(None)
):
    """
    동일 시험지의 PDF, HWP(문제지), 선택적 해설지(HWP), 선택적 정답표 이미지(PNG/JPG), 선택적 정답률 CSV 파일, 선택적 듣기 대본 파일 업로드 및 상호 검증 파이프라인
    """
    # 1. 업로드 파일 임시 저장 (파일명 화이트리스트 및 경로 순회 방지 적용)
    safe_pdf_name = sanitize_upload_filename(pdf_file.filename)
    safe_hwp_name = sanitize_upload_filename(hwp_file.filename)
    pdf_save_path = os.path.join(UPLOADS_DIR, f"{grade}_{year}_{month:02d}_{safe_pdf_name}")
    hwp_save_path = os.path.join(UPLOADS_DIR, f"{grade}_{year}_{month:02d}_{safe_hwp_name}")

    with open(pdf_save_path, "wb") as buffer:
        shutil.copyfileobj(pdf_file.file, buffer)
    with open(hwp_save_path, "wb") as buffer:
        shutil.copyfileobj(hwp_file.file, buffer)

    script_save_path = None
    if script_file and script_file.filename:
        safe_script_name = sanitize_upload_filename(script_file.filename)
        script_save_path = os.path.join(UPLOADS_DIR, f"{grade}_{year}_{month:02d}_script_{safe_script_name}")
        with open(script_save_path, "wb") as buffer:
            shutil.copyfileobj(script_file.file, buffer)

    exp_save_path = None
    if exp_file and exp_file.filename:
        safe_exp_name = sanitize_upload_filename(exp_file.filename)
        exp_save_path = os.path.join(UPLOADS_DIR, f"{grade}_{year}_{month:02d}_exp_{safe_exp_name}")
        with open(exp_save_path, "wb") as buffer:
            shutil.copyfileobj(exp_file.file, buffer)

    ans_save_path = None
    if ans_file and ans_file.filename:
        safe_ans_name = sanitize_upload_filename(ans_file.filename)
        ans_save_path = os.path.join(UPLOADS_DIR, f"{grade}_{year}_{month:02d}_ans_{safe_ans_name}")
        with open(ans_save_path, "wb") as buffer:
            shutil.copyfileobj(ans_file.file, buffer)

    csv_save_path = None
    if csv_file and csv_file.filename:
        safe_csv_name = sanitize_upload_filename(csv_file.filename)
        csv_save_path = os.path.join(UPLOADS_DIR, f"{grade}_{year}_{month:02d}_{safe_csv_name}")
        with open(csv_save_path, "wb") as buffer:
            shutil.copyfileobj(csv_file.file, buffer)

    try:
        # subtype 자동 판별 보완
        if not subtype:
            for fn in (pdf_file.filename if pdf_file else "", hwp_file.filename if hwp_file else ""):
                m_sub = re.search(r"[-_\[\s]([AB])(?:형)?(?:[-_\]\s]|$)", fn, re.I)
                if m_sub:
                    subtype = f"{m_sub.group(1).upper()}형"
                    break

        # 2. 시험지 정보 DB 등록
        if subtype:
            exam_id = f"[{grade}-{year}년-{month:02d}월-{subtype}]"
        else:
            exam_id = f"[{grade}-{year}년-{month:02d}월]"

        # 출제기관 자동 판별 규칙 적용 (3학년 6, 9, 11월: 평가원, 그 외 3학년 월 및 1, 2학년 전체: 교육청)
        if grade in ("고3", "3학년") and month in (6, 9, 11):
            exam_type = "평가원"
        else:
            exam_type = "교육청"

        # 독해 시작 및 종료 문항 번호 자동 감지 (발문 기반 분기: 18~45, 23~45, 18~50)
        profile = get_exam_profile(grade, year, month, subtype)
        if profile.is_ab_period and reading_start is None:
            effective_reading_start = profile.reading_start
            effective_reading_end = reading_end if reading_end is not None else profile.reading_end
            listening_start = 1
            listening_end = profile.listening_end
        else:
            sample_text = ""
            if pdf_save_path and os.path.exists(pdf_save_path):
                try:
                    tdoc = fitz.open(pdf_save_path)
                    sample_text = "".join(p.get_text() for p in tdoc)
                    tdoc.close()
                except Exception:
                    logger.debug("[Upload] PDF 텍스트 추출 실패 (무시)", exc_info=True)
            if not sample_text and hwp_save_path and os.path.exists(hwp_save_path):
                try:
                    sample_text = get_hwp_text(hwp_save_path)
                except Exception:
                    logger.debug("[Upload] HWP 텍스트 추출 실패 (무시)", exc_info=True)

            detected_start, detected_end = detect_listening_range(
                sample_text, year=year, grade=grade, month=month, subtype=subtype
            )
            effective_reading_start = reading_start if reading_start is not None else detected_start
            effective_reading_end = reading_end if reading_end is not None else detected_end
            listening_start = 1
            listening_end = (effective_reading_start - 1) if effective_reading_start > 1 else profile.listening_end

        # 시험지 정보는 파싱이 끝난 뒤 지문·문장과 함께 한 트랜잭션으로 저장한다 (중간 실패 시 반쯤 저장 방지)
        exam_record = {
            "id": exam_id,
            "grade": grade,
            "year": year,
            "month": month,
            "exam_type": exam_type,
            "subtype": subtype,
            "reading_start_q": effective_reading_start,
            "reading_end_q": effective_reading_end,
            "listening_start_q": listening_start,
            "listening_end_q": listening_end
        }

        # 3. 정답 소스 수집
        uploaded_json_answers = {}
        image_report = None
        if ans_save_path and os.path.exists(ans_save_path):
            if ans_save_path.lower().endswith(".json"):
                try:
                    uploaded_json_answers = answer_keys.parse_answer_json_file(ans_save_path)
                    if uploaded_json_answers:
                        answer_keys.save_uploaded_answer_key(grade, year, month, uploaded_json_answers, safe_ans_name if ans_file else "")
                        logger.info(f"[Upload] 정답 JSON 파일 파싱 및 키 저장 완료 ({len(uploaded_json_answers)}문항)")
                    else:
                        logger.warning(f"[Upload] 정답 JSON 파싱 결과 비어있음: {ans_save_path}")
                except Exception as e:
                    logger.error(f"[Upload] 정답 JSON 파싱 실패: {e}", exc_info=True)
            else:
                image_report = read_answer_image(ans_save_path)

        # (2) HWP 해설 파싱 (별도 해설 파일 우선, 없거나 미흡할 경우 문제지 HWP 파일에서 추출)
        explanations = {}
        if exp_save_path and os.path.exists(exp_save_path):
            explanations = parse_hwp_explanations(exp_save_path)

        if hwp_save_path and os.path.exists(hwp_save_path):
            hwp_exps = parse_hwp_explanations(hwp_save_path)
            if not explanations:
                explanations = hwp_exps
            else:
                for q_num, exp_info in hwp_exps.items():
                    if q_num not in explanations or not explanations[q_num].get("explanation"):
                        explanations[q_num] = exp_info

        # (3) 정답률 CSV
        rates_dict = {}
        if csv_save_path and os.path.exists(csv_save_path):
            try:
                rates_dict = parse_correct_rate_csv(csv_save_path)
            except Exception as e:
                logger.error(f"[Upload] 정답률 CSV 파싱 실패: {e}", exc_info=True)

        # (4) 문항별 정답 확정
        resolution = answer_resolver.resolve_answers(
            q_range=range(effective_reading_start, effective_reading_end + 1),
            verified_key=answer_keys.load_answer_key(grade, year, month),
            image_report=image_report,
            csv_rates=rates_dict,
            hwp_answers={q: info.get("answer", "") for q, info in explanations.items()},
            uploaded_json=uploaded_json_answers,
        )
        answers_dict = resolution["answers"]
        for w in resolution["report"]["warnings"]:
            logger.warning(f"[Upload][정답 검증 경고] {exam_id} {w}")

        # (5) 최종 확정된 정답을 explanations 해설 텍스트 헤더 및 answer 필드에 동기화
        for q_num, final_ans in answers_dict.items():
            if q_num in explanations:
                explanations[q_num]["answer"] = final_ans
                exp_body = explanations[q_num].get("explanation", "").strip()
                explanations[q_num]["explanation"] = apply_answer_header(exp_body, final_ans)
            else:
                explanations[q_num] = {"answer": final_ans, "explanation": f"[정답] {final_ans}"}

        # 4. PDF 문제지 파싱 및 캡처 (정답 선지 형광펜 하이라이트 연동)
        pdf_questions = extract_pdf_columns_and_questions(
            pdf_path=pdf_save_path,
            grade=grade,
            year=year,
            month=month,
            start_q=effective_reading_start,
            end_q=effective_reading_end,
            answers_dict=answers_dict,
            subtype=subtype
        )

        # 5. HWP 문제지 파싱 (독해 지문 문항)
        hwp_questions = parse_hwp_questions(
            hwp_path=hwp_save_path,
            grade=grade,
            year=year,
            month=month,
            start_q=effective_reading_start,
            end_q=effective_reading_end,
            answers_dict=answers_dict
        )

        # 6. 상호 검증 및 문장 분할
        merged_packages = cross_validate_and_merge(
            hwp_data=hwp_questions,
            pdf_data=pdf_questions,
            explanations=explanations,
            grade=grade,
            year=year,
            month=month,
            subtype=subtype
        )

        # 7. SQLite DB 일괄 저장
        saved_passages_count = 0
        saved_sentences_count = 0
        sentence_stats = {"inserted": 0, "updated": 0, "text_changed": 0, "removed": 0}
        warnings: List[str] = []

        with db.transaction() as conn:
            db.save_exam(exam_record, conn=conn)

            for pkg in merged_packages:
                db.save_passage(pkg["passage_data"], conn=conn)
                saved_passages_count += 1
                if pkg["sentences"]:
                    res = db.replace_passage_sentences(pkg["passage_data"]["id"], pkg["sentences"], conn=conn)
                    for k in sentence_stats:
                        sentence_stats[k] += res[k]
                    saved_sentences_count += len(pkg["sentences"])
                else:
                    warnings.append(f"{pkg['passage_data'].get('q_num')}번: 문장 분할 결과가 비어 있어 기존 문장을 그대로 두었습니다.")

            db.set_answer_status(exam_id, resolution["sources"], resolution["verified"], conn=conn)
            db.refill_blank_sentences(exam_id=exam_id, conn=conn)

            if rates_dict:
                try:
                    db.save_exam_correct_rates(exam_id, rates_dict, conn=conn)
                except Exception as e:
                    logger.error(f"[Upload] 정답률 DB 갱신 실패: {e}", exc_info=True)
                    warnings.append(f"정답률 반영 실패: {e}")

        # 8. 듣기 영역(1~17번) 자동 크롭 및 스크립트/FELS 추출 동기화
        listening_count = 0
        try:
            listening_result = listening_parser.sync_exam_listening(
                exam_id=exam_id,
                question_pdf_path=pdf_save_path,
                script_pdf_path=script_save_path,
                explanation_hwp_path=exp_save_path or hwp_save_path,
                answers_dict=answers_dict
            )
            if isinstance(listening_result, dict):
                listening_count = listening_result.get("saved_count", 0) or 0
            else:
                listening_count = int(listening_result or 0)
            logger.info(f"[Upload] {exam_id} 듣기 문항 {listening_count}개 동기화 완료")
        except Exception as l_err:
            logger.warning(f"[Upload] 듣기 문항 동기화 중 경고: {l_err}", exc_info=True)
            warnings.append(f"듣기 문항 동기화 실패: {l_err}")

        # AI API 키가 설정되어 있는 경우 백그라운드 어법 자동 분석 스케줄링
        _, ai_key, _ = grammar_analyzer.get_ai_config()
        if ai_key:
            background_tasks.add_task(background_auto_analyze_exam_grammar, exam_id)

        report = resolution["report"]
        msg = f"성공적으로 독해 {saved_passages_count}개 문항과 듣기 {listening_count}개 문항을 상호 검증하여 저장했습니다."
        if sentence_stats["removed"]:
            msg += f" (이전 업로드의 남은 문장 {sentence_stats['removed']}개 정리)"
        if report["unverified_questions"]:
            msg += f" ⚠ 정답 미검증 {len(report['unverified_questions'])}문항 - 정답표 이미지/정답률 CSV를 확인하세요."
        if warnings:
            msg += f" ⚠ 경고 {len(warnings)}건"
        return {
            "status": "success",
            "exam_id": exam_id,
            "passages_count": saved_passages_count,
            "listening_count": listening_count,
            "sentences_count": saved_sentences_count,
            "sentences_inserted": sentence_stats["inserted"],
            "sentences_text_changed": sentence_stats["text_changed"],
            "sentences_removed": sentence_stats["removed"],
            "answer_report": report,
            "warnings": warnings,
            "message": msg
        }

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"파싱 및 저장 중 오류 발생: {str(e)}")


# --- 시험지 관리 및 삭제 API ---
@router.get("/api/exams")
def api_get_exams():
    """등록된 모든 시험지 목록 및 통계 반환"""
    try:
        exams = db.get_all_exams_with_stats()
        return {"status": "success", "total": len(exams), "items": exams}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"시험지 목록 조회 실패: {str(e)}")


@router.delete("/api/exams/{exam_id}")
def api_delete_exam(exam_id: str):
    """지정된 시험지 및 관련 모든 데이터(지문, 문장, 어법, 태그, 캡처 이미지) 연쇄 삭제"""
    clean_id = normalize_bracket_id(exam_id)
    try:
        res = db.delete_exam(clean_id)
        if not res.get("success"):
            raise HTTPException(status_code=404, detail=res.get("message", "시험지를 찾을 수 없습니다."))
        return res
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"시험지 삭제 중 오류 발생: {str(e)}")


@router.get("/api/exams/{exam_id}/raw-files")
def api_get_exam_raw_files(exam_id: str):
    """특정 시험지에 등록된 5종 원본 파일(문제 PDF, 해설 HWP, 대본 PDF, 정답 JSON/PNG, 정답률 CSV) 현황 조회"""
    data = db.get_exam_raw_files(exam_id)
    if not data:
        raise HTTPException(status_code=404, detail=f"시험지 '{exam_id}'를 찾을 수 없습니다.")

    safe_files = {}
    for ft, f_info in data["files"].items():
        safe_files[ft] = {
            "exists": f_info["exists"],
            "filename": f_info["filename"],
            "size_bytes": f_info["size_bytes"],
            "size_formatted": f_info["size_formatted"],
            "type_label": f_info["type_label"],
            "is_exp": f_info.get("is_exp", False)
        }
    return {
        "status": "success",
        "exam_id": data["exam_id"],
        "grade": data["grade"],
        "year": data["year"],
        "month": data["month"],
        "subtype": data["subtype"],
        "files": safe_files
    }


@router.get("/api/exams/{exam_id}/download-file")
def api_download_exam_file(exam_id: str, file_type: str = Query(...)):
    """특정 시험지의 단일 원본 파일(pdf, hwp, script, ans, csv)을 다운로드"""
    data = db.get_exam_raw_files(exam_id)
    if not data:
        raise HTTPException(status_code=404, detail=f"시험지 '{exam_id}'를 찾을 수 없습니다.")

    clean_type = file_type.strip().lower()
    if clean_type not in data["files"]:
        raise HTTPException(status_code=400, detail=f"지원하지 않는 파일 유형입니다: {file_type}")

    f_info = data["files"][clean_type]
    if not f_info["exists"] or not f_info["abs_path"] or not os.path.exists(f_info["abs_path"]):
        raise HTTPException(status_code=404, detail=f"해당 시험지의 {f_info['type_label']} 파일이 서버에 존재하지 않습니다.")

    file_path = f_info["abs_path"]
    filename = f_info["filename"]

    media_type = "application/octet-stream"
    fl = filename.lower()
    if fl.endswith(".pdf"):
        media_type = "application/pdf"
    elif fl.endswith((".hwp", ".hwpx")):
        media_type = "application/x-hwp"
    elif fl.endswith(".json"):
        media_type = "application/json"
    elif fl.endswith(".png"):
        media_type = "image/png"
    elif fl.endswith((".jpg", ".jpeg")):
        media_type = "image/jpeg"
    elif fl.endswith(".csv"):
        media_type = "text/csv; charset=utf-8"

    encoded_filename = quote(filename)
    headers = {
        "Content-Disposition": f"attachment; filename=\"{encoded_filename}\"; filename*=UTF-8''{encoded_filename}"
    }
    return FileResponse(file_path, media_type=media_type, headers=headers)


@router.get("/api/exams/{exam_id}/download-zip")
def api_download_exam_all_zip(exam_id: str):
    """특정 시험지의 보관된 모든 원본 파일(문제, 해설, 대본, 정답, 정답률)을 하나의 ZIP으로 일괄 압축 다운로드"""
    data = db.get_exam_raw_files(exam_id)
    if not data:
        raise HTTPException(status_code=404, detail=f"시험지 '{exam_id}'를 찾을 수 없습니다.")

    existing_files = [
        (f_info["abs_path"], f_info["filename"])
        for f_info in data["files"].values()
        if f_info["exists"] and f_info["abs_path"] and os.path.exists(f_info["abs_path"])
    ]

    if not existing_files:
        raise HTTPException(status_code=404, detail="다운로드할 수 있는 원본 파일이 서버에 없습니다.")

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for f_path, f_name in existing_files:
            zip_file.write(f_path, arcname=f_name)

    zip_buffer.seek(0)
    safe_name = data["exam_id"].replace("[", "").replace("]", "").replace(" ", "_")
    zip_filename = f"{safe_name}_전체파일.zip"
    encoded_filename = quote(zip_filename)
    headers = {
        "Content-Disposition": f"attachment; filename=\"{encoded_filename}\"; filename*=UTF-8''{encoded_filename}"
    }
    return Response(content=zip_buffer.getvalue(), media_type="application/zip", headers=headers)


@router.post("/api/exams/{exam_id}/upload-file")
@_ingest_serialized
def api_upload_exam_single_file(
    exam_id: str,
    file_type: str = Form(...),  # "ans" | "pdf" | "hwp" | "csv"
    file: UploadFile = File(...)
):
    """
    기존 등록된 특정 시험지에 대해 단독 파일(정답표 이미지, PDF, HWP, 정답률 CSV)을 업로드 및 갱신하는 API
    특히 정답표 이미지(ans) 또는 정답률 CSV(csv) 업로드 시 데이터 추출 + DB 갱신 자동 수행
    """
    clean_id = normalize_bracket_id(exam_id)

    # 1. 시험지 정보 조회
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, grade, year, month, subtype, reading_start_q, reading_end_q FROM exams WHERE id = ?", (clean_id,))
        exam = cursor.fetchone()

    if not exam:
        raise HTTPException(status_code=404, detail=f"시험지 '{clean_id}'를 찾을 수 없습니다.")

    grade = exam["grade"]
    year = exam["year"]
    month = exam["month"]
    subtype = exam["subtype"]
    profile = get_exam_profile(grade, year, month, subtype)
    reading_start = exam["reading_start_q"] or profile.reading_start
    reading_end = exam["reading_end_q"] or profile.reading_end

    # 2. 파일 저장 (파일명 화이트리스트 및 경로 순회 방지 적용)
    safe_file_name = sanitize_upload_filename(file.filename)
    if file_type == "ans":
        save_path = os.path.join(UPLOADS_DIR, f"{grade}_{year}_{month:02d}_ans_{safe_file_name}")
    else:
        save_path = os.path.join(UPLOADS_DIR, f"{grade}_{year}_{month:02d}_{safe_file_name}")

    with open(save_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # 3. 정답표 파일(ans) 처리 (JSON 파일 또는 이미지 파일)
    if file_type == "ans":
        try:
            # (A) 정답 JSON 파일인 경우: Vision AI 바이패스, 1순위 Ground Truth로 즉시 반영
            if save_path.lower().endswith(".json"):
                json_answers = answer_keys.parse_answer_json_file(save_path)
                if not json_answers:
                    raise ValueError("정답 JSON 파일에서 유효한 문항 정답을 추출하지 못했습니다.")
                answer_keys.save_uploaded_answer_key(grade, year, month, json_answers, safe_file_name)

                answers_dict = {}
                with db.get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute(
                        "SELECT id, q_num, answer_text, explanation_text FROM passages WHERE exam_id = ?",
                        (clean_id,)
                    )
                    passages = cursor.fetchall()
                    for p in passages:
                        q_int = int(p["q_num"])
                        if q_int in json_answers:
                            target_ans = json_answers[q_int]
                            answers_dict[q_int] = target_ans
                            exp_body = p["explanation_text"] or ""
                            new_exp = apply_answer_header(exp_body, target_ans)
                            cursor.execute(
                                "UPDATE passages SET answer_text = ?, explanation_text = ?, answer_source = 'uploaded_json', answer_verified = 1 WHERE id = ?",
                                (target_ans, new_exp, p["id"])
                            )
                        elif p["answer_text"]:
                            answers_dict[q_int] = p["answer_text"]
                    db.refill_blank_sentences(exam_id=clean_id, conn=conn)
                    conn.commit()

                pdf_highlighted = _regenerate_exam_crops(clean_id, grade, year, month, reading_start, reading_end, answers_dict)
                return {
                    "status": "success",
                    "exam_id": clean_id,
                    "file_type": "ans",
                    "extracted_count": len(json_answers),
                    "source": "uploaded_json",
                    "pdf_highlighted": pdf_highlighted,
                    "message": f"정답 JSON 파일에서 {len(json_answers)}개 문항 정답을 1순위로 즉시 반영했습니다."
                               + (" (PDF 형광펜 갱신 완료)" if pdf_highlighted else "")
                }

            # (B) 이미지 파일인 경우: 활성화된 모든 Vision 모델로 독립 판독 → 2개 이상 일치한 문항만 검증 정답으로 인정
            report = read_answer_image(save_path)
            if report["status"] == "failed":
                raise ValueError("정답표 이미지 판독 실패: " + "; ".join(report["errors"]))
            if report["status"] == "single_reader":
                image_answers = next(iter(report["readings"].values()))
                img_source, img_verified = "image_single", 0
            else:
                image_answers = report["consensus"]
                img_source, img_verified = "image_consensus", 1
            verified_key = answer_keys.load_answer_key(grade, year, month)

            # (2) DB 지문 정답 및 해설 텍스트 갱신
            answers_dict = {}
            with db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT id, q_num, answer_text, explanation_text FROM passages WHERE exam_id = ?",
                    (clean_id,)
                )
                passages = cursor.fetchall()

                for p in passages:
                    q_int = int(p["q_num"])
                    if q_int in verified_key:
                        target_ans, src, ver = verified_key[q_int], "verified_key", 1
                    elif q_int in image_answers:
                        target_ans, src, ver = image_answers[q_int], img_source, img_verified
                    else:
                        target_ans, src, ver = None, None, 0
                    new_ans = target_ans or (p["answer_text"] or "")
                    if new_ans:
                        answers_dict[q_int] = new_ans

                    if target_ans:
                        exp_body = p["explanation_text"] or ""
                        new_exp = apply_answer_header(exp_body, target_ans)

                        cursor.execute(
                            "UPDATE passages SET answer_text = ?, explanation_text = ?, answer_source = ?, answer_verified = ? WHERE id = ?",
                            (target_ans, new_exp, src, ver, p["id"])
                        )
                db.refill_blank_sentences(exam_id=clean_id, conn=conn)
                conn.commit()

            # (3) 원본 PDF가 있으면 정답 선지 형광펜 하이라이트 크롭 이미지 재생성
            pdf_highlighted = _regenerate_exam_crops(clean_id, grade, year, month, reading_start, reading_end, answers_dict)

            warnings = []
            if report["status"] == "single_reader":
                warnings.append("Vision 모델 1개만 응답 - 교차검증 불가 (미검증 처리)")
            if report["disputed"]:
                warnings.append(f"모델 간 판독 불일치 문항(미반영): {sorted(report['disputed'])}")
            return {
                "status": "success",
                "exam_id": clean_id,
                "file_type": "ans",
                "image_status": report["status"],
                "reader_count": report["reader_count"],
                "extracted_count": len(image_answers),
                "disputed": {str(q): v for q, v in report["disputed"].items()},
                "warnings": warnings,
                "pdf_highlighted": pdf_highlighted,
                "message": f"정답표 이미지를 {report['reader_count']}개 모델이 판독하여 {len(image_answers)}개 문항 정답을 반영했습니다."
                           + (" (PDF 형광펜 갱신 완료)" if pdf_highlighted else "")
                           + ((" ⚠ " + " / ".join(warnings)) if warnings else "")
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"정답 이미지 파싱 중 오류: {str(e)}")

    # 4. 정답률 및 선지 선택률 CSV 파일 처리
    elif file_type == "csv":
        try:
            rates_dict = parse_correct_rate_csv(save_path)
            if not rates_dict:
                raise ValueError("정답률 CSV 파일에서 유효한 문항 데이터를 추출하지 못했습니다.")

            # (1) 기존 DB 정답과 교차검증
            with db.get_connection() as conn:
                rows = conn.execute("SELECT q_num, answer_text, answer_source FROM passages WHERE exam_id = ?", (clean_id,)).fetchall()
            current = {int(r["q_num"]): r["answer_text"] or "" for r in rows}
            sources = {int(r["q_num"]): r["answer_source"] or "" for r in rows}
            check = answer_resolver.check_csv_against_answers(rates_dict, current, sources)
            if check["suspect"]:
                raise HTTPException(status_code=422, detail=(
                    f"정답률 CSV가 다른 시험의 데이터로 의심되어 반영하지 않았습니다 "
                    f"(비교 {check['checked']}문항 중 {len(check['mismatch'])}문항 정답 불일치: {check['mismatch']}). 파일을 확인하세요."
                ))

            # (2) 정답률/선택률 저장
            res_data = db.save_exam_correct_rates(clean_id, rates_dict)

            # (3) CSV가 결정적으로 확정한 정답
            decided = {}
            for q, (_old, new) in check["corrections"].items():
                if sources.get(q) != "uploaded_json":
                    decided[q] = new
            for q in check["confirmed"]:
                if sources.get(q) not in ("uploaded_json", "verified_key"):
                    decided[q] = current[q]
            if decided:
                db.update_passage_answers(clean_id, decided, source="csv", verified=1)
            pdf_highlighted = False
            if check["corrections"]:
                merged = {**current, **{q: n for q, (_o, n) in check["corrections"].items()}}
                pdf_highlighted = _regenerate_exam_crops(clean_id, grade, year, month, reading_start, reading_end, merged)

            warnings = []
            if check["corrections"]:
                warnings.append("정답 정정: " + ", ".join(f"Q{q} {o}→{n}" for q, (o, n) in sorted(check["corrections"].items())))
            if check["violations"]:
                warnings.append(f"정답률과 모순되는 기존 정답 (후보 복수로 자동 확정 불가, 확인 필요): {check['violations']}")
            return {
                "status": "success",
                "exam_id": clean_id,
                "file_type": "csv",
                "extracted_count": len(rates_dict),
                "updated_count": res_data["updated_count"],
                "avg_rate": res_data["avg_rate"],
                "csv_checked": check["checked"],
                "confirmed_count": len(check["confirmed"]),
                "corrections": {str(q): {"old": o, "new": n} for q, (o, n) in check["corrections"].items()},
                "violations": check["violations"],
                "pdf_highlighted": pdf_highlighted,
                "warnings": warnings,
                "message": f"정답률 데이터 {res_data['updated_count']}문항 반영, 정답 {len(check['confirmed'])}문항 교차검증 확인"
                           + (f", {len(check['corrections'])}문항 정정" if check["corrections"] else "")
                           + (f" (평균 정답률 {res_data['avg_rate']}%)" if res_data["avg_rate"] is not None else "")
                           + ((" ⚠ " + " / ".join(warnings)) if warnings else "")
            }
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"정답률 CSV 파싱 중 오류: {str(e)}")

    # 5. 듣기 대본 파일 단독 등록/교체 시
    elif file_type == "script":
        try:
            is_exp = bool(re.search(r"[-_]A\.pdf$", file.filename, re.I) or "_exp" in file.filename.lower())
            sync_res = listening_parser.sync_exam_listening(clean_id, script_pdf_path=save_path, is_explanation_pdf=is_exp)
            synced_count = sync_res.get("synced_count", 0) if isinstance(sync_res, dict) else (sync_res or 0)
            desc_type = "해설(대본)" if is_exp else "대본"
            return {
                "status": "success",
                "exam_id": clean_id,
                "file_type": "script",
                "synced_count": synced_count,
                "is_exp": is_exp,
                "message": f"{desc_type} PDF 파일 등록 및 {synced_count}개 듣기 문항 대본/FELS 추출이 완료되었습니다."
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"듣기 대본 처리 중 오류: {str(e)}")

    # 6. HWP 해설지 단독 업로드 / 갱신 시
    elif file_type == "hwp":
        try:
            hwp_exps = parse_hwp_explanations(save_path)
            updated_count = 0
            if hwp_exps:
                with db.get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute(
                        "SELECT id, q_num, answer_text, explanation_text, answer_source FROM passages WHERE exam_id = ?",
                        (clean_id,)
                    )
                    passages = cursor.fetchall()
                    for p in passages:
                        q_int = int(p["q_num"])
                        if q_int in hwp_exps:
                            exp_info = hwp_exps[q_int]
                            new_exp = (exp_info.get("explanation") or "").strip()
                            hwp_ans = (exp_info.get("answer") or "").strip()

                            cur_ans = p["answer_text"] or ""
                            cur_src = p["answer_source"] or ""
                            update_ans = cur_ans
                            update_src = cur_src

                            if not cur_ans and hwp_ans:
                                update_ans = hwp_ans
                                update_src = "hwp"

                            if new_exp:
                                cursor.execute(
                                    "UPDATE passages SET explanation_text = ?, answer_text = ?, answer_source = ? WHERE id = ?",
                                    (new_exp, update_ans, update_src, p["id"])
                                )
                                updated_count += 1
                    db.refill_blank_sentences(exam_id=clean_id, conn=conn)
                    conn.commit()

            pdf_highlighted = False
            try:
                with db.get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT q_num, answer_text FROM passages WHERE exam_id = ?", (clean_id,))
                    rows = cursor.fetchall()
                    answers_dict = {int(r["q_num"]): r["answer_text"] for r in rows if r["answer_text"]}
                pdf_highlighted = _regenerate_exam_crops(clean_id, grade, year, month, reading_start, reading_end, answers_dict, subtype=subtype)
            except Exception as cr_err:
                logger.warning(f"[Upload HWP] 크롭 갱신 경고: {cr_err}", exc_info=True)

            if not hwp_exps:
                return {
                    "status": "partial",
                    "exam_id": clean_id,
                    "file_type": "hwp",
                    "updated_count": 0,
                    "pdf_highlighted": pdf_highlighted,
                    "message": "⚠ 파일은 저장했지만 HWP에서 문항별 해설을 찾지 못했습니다. 파일 형식이나 내용을 확인해 주세요."
                }

            return {
                "status": "success",
                "exam_id": clean_id,
                "file_type": "hwp",
                "updated_count": updated_count,
                "pdf_highlighted": pdf_highlighted,
                "message": f"HWP 해설지가 성공적으로 업로드되었습니다." + (f" ({updated_count}개 문항 해설 갱신)" if updated_count else "")
            }
        except Exception as e:
            logger.warning(f"[Upload HWP] 해설 파싱 실패 ({clean_id}): {e}", exc_info=True)
            return {
                "status": "partial",
                "exam_id": clean_id,
                "file_type": "hwp",
                "message": f"⚠ 파일은 저장했지만 해설 파싱에 실패했습니다: {str(e)}"
            }

    # 7. PDF 문제지 단독 업로드 / 교체 시
    elif file_type == "pdf":
        pdf_highlighted = False
        try:
            with db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT q_num, answer_text FROM passages WHERE exam_id = ?", (clean_id,))
                rows = cursor.fetchall()
                answers_dict = {int(r["q_num"]): r["answer_text"] for r in rows if r["answer_text"]}
            pdf_highlighted = _regenerate_exam_crops(clean_id, grade, year, month, reading_start, reading_end, answers_dict, subtype=subtype)
        except Exception as cr_err:
            logger.warning(f"[Upload PDF] 크롭 갱신 경고: {cr_err}", exc_info=True)

        return {
            "status": "success",
            "exam_id": clean_id,
            "file_type": "pdf",
            "pdf_highlighted": pdf_highlighted,
            "message": f"PDF 문제지가 성공적으로 업로드되었습니다." + (" (정답 형광펜 크롭 재생성 완료)" if pdf_highlighted else "")
        }

    # 8. 기타 파일 교체 시
    return {
        "status": "success",
        "exam_id": clean_id,
        "file_type": file_type,
        "message": f"{file_type.upper()} 파일이 성공적으로 업로드되었습니다."
    }


@router.post("/api/exams/selective-delete")
def api_selective_delete_exams(req: SelectiveDeleteRequest):
    """
    모의고사 데이터를 4개 영역(원본 파일, 코어 본문, 메타데이터, 정답률 데이터)으로 구분하여 선택적 삭제
    """
    try:
        results = []
        for eid in req.exam_ids:
            r = db.selective_delete_exam(
                exam_id=eid,
                delete_raw=req.delete_raw_files,
                delete_core=req.delete_core_corpus,
                delete_metadata=req.delete_metadata,
                delete_rate=req.delete_rate_data
            )
            results.append(r)

        success_count = sum(1 for r in results if r.get("success"))
        freed_bytes = sum(r.get("freed_raw_bytes", 0) for r in results)
        deleted_passages = sum(r.get("deleted_passages_count", 0) for r in results)
        deleted_sentences = sum(r.get("deleted_sentences_count", 0) for r in results)
        deleted_grammar = sum(r.get("deleted_grammar_count", 0) for r in results)
        deleted_rates = sum(r.get("deleted_rate_count", 0) for r in results)

        return {
            "status": "success",
            "processed_count": len(req.exam_ids),
            "success_count": success_count,
            "freed_raw_mb": round(freed_bytes / (1024 * 1024), 2),
            "deleted_passages": deleted_passages,
            "deleted_sentences": deleted_sentences,
            "deleted_grammar": deleted_grammar,
            "deleted_rates": deleted_rates,
            "details": results
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"선택적 데이터 삭제 처리 중 오류 발생: {str(e)}")


@router.post("/api/exams/batch-delete")
def api_batch_delete_exams(req: BatchDeleteRequest):
    """복수 시험지 일괄 완전 삭제 (하위 호환)"""
    try:
        results = []
        for eid in req.exam_ids:
            r = db.delete_exam(eid)
            results.append(r)
        return {
            "status": "success",
            "deleted_count": sum(1 for r in results if r.get("success")),
            "details": results
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"시험지 일괄 삭제 중 오류 발생: {str(e)}")
