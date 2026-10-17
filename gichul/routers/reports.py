"""
05-gichul_db: 문항 및 문장 오류 신고 관리 라우터 (gichul/routers/reports.py)
"""

from typing import List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .. import database as db
from ..logging_config import get_logger

router = APIRouter()
logger = get_logger("gichul.routers.reports")


class ErrorReportCreateRequest(BaseModel):
    target_type: str                   # 'passage' | 'sentence'
    passage_id: Optional[str] = None
    sentence_id: Optional[str] = None
    exam_id: Optional[str] = None
    error_types: Optional[List[str]] = []
    comment: Optional[str] = ""


@router.post("/api/reports")
def api_create_report(req: ErrorReportCreateRequest):
    """문항 또는 문장 오류 신고 접수"""
    if req.target_type not in ("passage", "sentence"):
        raise HTTPException(status_code=400, detail="target_type은 'passage' 또는 'sentence'여야 합니다.")
    if req.target_type == "passage" and not req.passage_id:
        raise HTTPException(status_code=400, detail="지문 오류 신고 시 passage_id가 필요합니다.")
    if req.target_type == "sentence" and not req.sentence_id:
        raise HTTPException(status_code=400, detail="문장 오류 신고 시 sentence_id가 필요합니다.")

    try:
        res = db.create_error_report(
            target_type=req.target_type,
            passage_id=req.passage_id,
            sentence_id=req.sentence_id,
            exam_id=req.exam_id,
            error_types=req.error_types,
            comment=req.comment,
        )
        return res
    except Exception as e:
        logger.error(f"오류 신고 등록 실패: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"오류 신고 등록에 실패했습니다: {e}")


@router.get("/api/reports")
def api_get_reports(target_type: Optional[str] = None, status: str = "pending"):
    """신고된 오류 목록 조회"""
    try:
        reports = db.get_error_reports(target_type=target_type, status=status)
        return {"success": True, "count": len(reports), "reports": reports}
    except Exception as e:
        logger.error(f"오류 신고 목록 조회 실패: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"오류 신고 목록 조회에 실패했습니다: {e}")


@router.get("/api/reports/count")
def api_get_reports_count():
    """미해결 오류 건수 조회 (헤더 배지용)"""
    try:
        count = db.get_pending_reports_count()
        return {"success": True, "count": count}
    except Exception as e:
        logger.error(f"오류 신고 건수 조회 실패: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"오류 신고 건수 조회에 실패했습니다: {e}")


@router.delete("/api/reports/{report_id}")
def api_delete_report(report_id: int):
    """신고된 오류 항목 삭제 (수정 완료 처리)"""
    try:
        success = db.delete_error_report(report_id)
        if not success:
            raise HTTPException(status_code=404, detail="해당 오류 신고 항목을 찾을 수 없습니다.")
        return {"success": True, "deleted_id": report_id, "message": "오류 신고 항목이 삭제되었습니다."}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"오류 신고 항목 삭제 실패: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"오류 신고 항목 삭제에 실패했습니다: {e}")


# ====================================================================
# AI 오류 진단 및 일괄 교정/승인 적용
# ====================================================================

class BatchDiagnoseRequest(BaseModel):
    report_ids: Optional[List[int]] = None


class BatchApplyFixItem(BaseModel):
    report_id: Optional[int] = None
    target_type: str = "passage"
    passage_id: Optional[str] = None
    sentence_id: Optional[str] = None
    explanation_text: Optional[str] = None
    passage_text: Optional[str] = None
    sentence_text: Optional[str] = None
    answer_text: Optional[str] = None
    chained_passage_id: Optional[str] = None
    chained_explanation_text: Optional[str] = None
    chained_report_id: Optional[int] = None


class BatchApplyRequest(BaseModel):
    items: List[BatchApplyFixItem]


def _diagnose_single_report(report: dict) -> dict:
    """단일 신고 항목에 대해 AI 또는 규칙 기반으로 해결안 생성"""
    import json
    import re
    from .. import grammar_analyzer

    report_id = report["id"]
    target_type = report["target_type"]
    comment = (report.get("comment") or "").strip()
    error_types = report.get("error_types") or []

    result = {
        "report_id": report_id,
        "target_type": target_type,
        "target_id": report.get("passage_id") if target_type == "passage" else report.get("sentence_id"),
        "grade": report.get("grade"),
        "year": report.get("year"),
        "month": report.get("month"),
        "q_num": report.get("q_num"),
        "error_types": error_types,
        "comment": comment,
        "diagnosis": "",
        "action_type": "manual",
        "field_name": "explanation_text",
        "before_text": "",
        "after_text": "",
        "chained": None
    }

    if target_type == "passage":
        p_id = report["passage_id"]
        clean_p_id = db.normalize_bracket_id(p_id)
        current_p = db.get_passage(clean_p_id)
        if not current_p:
            result["diagnosis"] = f"지문 '{clean_p_id}'를 DB에서 찾을 수 없습니다."
            return result

        cur_exp = (current_p.get("explanation_text") or "").strip()
        cur_text = (current_p.get("passage_text") or "").strip()
        cur_ans = current_p.get("answer_text") or ""
        q_num = current_p.get("q_num")
        exam_id = current_p.get("exam_id")

        # 다음 문항(q_num + 1) 정보 탐색
        next_p = None
        next_report = None
        if q_num and exam_id:
            try:
                next_q = int(q_num) + 1
                with db.get_connection() as conn:
                    np_row = conn.execute(
                        "SELECT id, q_num, explanation_text, passage_text FROM passages WHERE exam_id = ? AND q_num = ?",
                        (exam_id, next_q)
                    ).fetchone()
                    if np_row:
                        next_p = dict(np_row)
                    # 다음 문항에 대한 pending 오류 신고도 있는지 확인
                    nr_row = conn.execute(
                        "SELECT id FROM error_reports WHERE passage_id = ? AND status = 'pending' LIMIT 1",
                        (next_p["id"] if next_p else "",)
                    ).fetchone()
                    if nr_row:
                        next_report = dict(nr_row)
            except Exception:
                pass

        # 1. 오류 유형 및 타겟 필드 판별
        is_passage_text_case = (
            "passage_text" in error_types or
            "본문" in comment or "지문" in comment or "문항 텍스트" in comment
        )
        is_split_case = (
            "해설" in comment or "explanation" in error_types or
            bool(re.search(r'\b(3[0-9]|4[0-5]|[1-9]|[12][0-9])\s*번', comment)) or
            "둘 다" in comment or "추가" in comment or "누락" in comment
        )

        target_field = "passage_text" if (is_passage_text_case and not is_split_case) else "explanation_text"

        # AI 호출 시도
        api_key, model = grammar_analyzer.get_provider_config("gemini")
        ai_success = False

        if api_key and (cur_exp or cur_text):
            try:
                import urllib.request
                if target_field == "passage_text":
                    prompt = f"""당신은 수능·모의고사 기출문제 데이터베이스 교정 전문가입니다.
사용자가 다음 문항의 [지문 본문 텍스트]에 대해 오류를 신고했습니다:
- 문항: {clean_p_id} (문항번호: {q_num}번)
- 신고된 오류 유형: {error_types}
- 신고 상세 내용: {comment}
- 현재 문항의 지문 본문 텍스트:
\"\"\"
{cur_text}
\"\"\"

분석 후 아래 JSON 포맷으로만 답변하세요 (코드블록 없이 JSON만):
{{
  "diagnosis": "지문 본문 오류 내용 요약 (1문장)",
  "action_type": "correct_passage",
  "corrected_text": "오탈자나 줄바꿈, 특수기호가 교정된 올바른 지문 본문 텍스트"
}}"""
                else:
                    prompt = f"""당신은 수능·모의고사 기출문제 데이터베이스 교정 전문가입니다.
사용자가 다음 문항에 대해 오류를 신고했습니다:
- 문항: {clean_p_id} (문항번호: {q_num}번)
- 신고된 오류 유형: {error_types}
- 신고 상세 내용: {comment}
- 현재 문항의 해설 텍스트:
\"\"\"
{cur_exp}
\"\"\"
{"- 다음 문항 정보: " + str(next_p.get('q_num')) + "번 (현재 해설 길이: " + str(len(next_p.get('explanation_text') or '')) + "자)" if next_p else ""}

분석 후 아래 JSON 포맷으로만 답변하세요 (코드블록 없이 JSON만):
{{
  "diagnosis": "오류 내용 요약 (1문장)",
  "action_type": "split_explanation" 또는 "correct_explanation" 또는 "correct_passage",
  "current_explanation": "현재 {q_num}번에 남길 올바른 해설 텍스트",
  "next_explanation": "다음 문항으로 이관할 해설 텍스트 (해설 분리인 경우에만, 아니면 빈 문자열)",
  "next_q_num": {next_p.get('q_num') if next_p else "null"}
}}"""

                url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.6-flash:generateContent?key={api_key}"
                payload = {
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {"response_mime_type": "application/json", "temperature": 0.1}
                }
                req = urllib.request.Request(
                    url,
                    data=json.dumps(payload).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="POST"
                )
                with urllib.request.urlopen(req, timeout=15) as resp:
                    resp_data = json.loads(resp.read().decode("utf-8"))
                    raw_ai_text = resp_data["candidates"][0]["content"]["parts"][0]["text"]
                    ai_json = json.loads(raw_ai_text)

                    if target_field == "passage_text":
                        result["diagnosis"] = ai_json.get("diagnosis", "지문 본문 AI 분석 완료")
                        result["action_type"] = "correct_passage"
                        result["field_name"] = "passage_text"
                        result["before_text"] = cur_text
                        result["after_text"] = ai_json.get("corrected_text", cur_text)
                    else:
                        result["diagnosis"] = ai_json.get("diagnosis", "AI 분석 완료")
                        result["action_type"] = ai_json.get("action_type", "correct_explanation")
                        result["field_name"] = "explanation_text"
                        result["before_text"] = cur_exp
                        result["after_text"] = ai_json.get("current_explanation", cur_exp)

                        if ai_json.get("next_explanation") and next_p:
                            result["chained"] = {
                                "passage_id": next_p["id"],
                                "q_num": next_p["q_num"],
                                "report_id": next_report["id"] if next_report else None,
                                "field_name": "explanation_text",
                                "before_text": next_p.get("explanation_text") or "",
                                "after_text": ai_json.get("next_explanation")
                            }
                    ai_success = True
            except Exception as e:
                logger.warning(f"AI 진단 호출 실패: {e}")

        # AI 호출이 없거나 실패했을 때 휴리스틱 규칙 기반 자동 진단
        if not ai_success:
            if target_field == "passage_text":
                result["diagnosis"] = f"지문 본문 검토 필요 ({comment})"
                result["action_type"] = "correct_passage"
                result["field_name"] = "passage_text"
                result["before_text"] = cur_text
                result["after_text"] = cur_text
            elif is_split_case and next_p:
                # 텍스트 내에서 다음 문항 번호 패턴 탐색 (예: [34], 34., 34번 등)
                next_q = next_p["q_num"]
                split_pattern = rf'(?:\n\s*|\s+)(?:\[?{next_q}\]?[\.\s번]|\[?문항\s*{next_q}\]?|\[{next_q}\])'
                match = re.search(split_pattern, cur_exp)
                if match:
                    split_idx = match.start()
                    part1 = cur_exp[:split_idx].strip()
                    part2 = cur_exp[split_idx:].strip()

                    result["diagnosis"] = f"{q_num}번 해설에 {next_q}번 해설이 결합되어 있어 분리 제안합니다."
                    result["action_type"] = "split_explanation"
                    result["field_name"] = "explanation_text"
                    result["before_text"] = cur_exp
                    result["after_text"] = part1
                    result["chained"] = {
                        "passage_id": next_p["id"],
                        "q_num": next_q,
                        "report_id": next_report["id"] if next_report else None,
                        "field_name": "explanation_text",
                        "before_text": next_p.get("explanation_text") or "",
                        "after_text": part2
                    }
                else:
                    result["diagnosis"] = f"{q_num}번 해설 검토 필요 ({comment})"
                    result["field_name"] = "explanation_text"
                    result["before_text"] = cur_exp
                    result["after_text"] = cur_exp
            else:
                result["diagnosis"] = f"신고 내용: {comment}"
                result["field_name"] = "explanation_text" if ("해설" in comment or "explanation" in error_types) else "passage_text"
                result["before_text"] = cur_exp if result["field_name"] == "explanation_text" else cur_text
                result["after_text"] = result["before_text"]

    elif target_type == "sentence":
        s_id = report["sentence_id"]
        clean_s_id = db.normalize_bracket_id(s_id)
        with db.get_connection() as conn:
            s_row = conn.execute("SELECT id, sentence_text FROM sentences WHERE id = ?", (clean_s_id,)).fetchone()
        if s_row:
            s_text = s_row["sentence_text"]
            result["field_name"] = "sentence_text"
            result["before_text"] = s_text
            result["after_text"] = s_text
            result["diagnosis"] = f"문장 오류 신고 ({comment})"
            result["action_type"] = "correct_sentence"
        else:
            result["diagnosis"] = f"문장 '{clean_s_id}'를 찾을 수 없습니다."

    return result


@router.post("/api/reports/batch-diagnose")
def api_batch_diagnose_reports(req: BatchDiagnoseRequest):
    """신고 항목 일괄(또는 선택) AI 진단 및 사전 해결안 반환 (사용자 검토용)"""
    try:
        all_pending = db.get_error_reports(status="pending")
        if req.report_ids:
            target_reports = [r for r in all_pending if r["id"] in req.report_ids]
        else:
            target_reports = all_pending

        diagnoses = []
        for r in target_reports:
            diag = _diagnose_single_report(r)
            diagnoses.append(diag)

        return {
            "success": True,
            "total_count": len(target_reports),
            "diagnoses": diagnoses
        }
    except Exception as e:
        logger.error(f"일괄 진단 처리 실패: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"일괄 진단 처리에 실패했습니다: {e}")


@router.post("/api/reports/batch-apply")
def api_batch_apply_fixes(req: BatchApplyRequest):
    """사용자가 검토 후 승인한 교정안들을 일괄 DB 반영 및 해당 신고 삭제 처리"""
    if not req.items:
        return {"success": True, "applied_count": 0, "message": "적용할 항목이 없습니다."}

    applied_count = 0
    resolved_report_ids = set()

    try:
        with db.get_connection() as conn:
            cursor = conn.cursor()
            for item in req.items:
                # 1. 메인 대상 문항/문장 업데이트
                if item.target_type == "passage" and item.passage_id:
                    clean_pid = db.normalize_bracket_id(item.passage_id)
                    if item.explanation_text is not None:
                        db.update_passage_explanation(clean_pid, item.explanation_text)
                    if item.passage_text is not None:
                        db.update_passage_text(clean_pid, item.passage_text)
                    if item.answer_text is not None:
                        cursor.execute("UPDATE passages SET answer_text = ? WHERE id = ?", (item.answer_text, clean_pid))
                    applied_count += 1

                elif item.target_type == "sentence" and item.sentence_id:
                    clean_sid = db.normalize_bracket_id(item.sentence_id)
                    if item.sentence_text is not None:
                        db.update_sentence_text(clean_sid, item.sentence_text)
                    applied_count += 1

                if item.report_id:
                    resolved_report_ids.add(item.report_id)

                # 2. 연계 대상(예: 34번 문항 주입 및 34번 신고) 업데이트
                if item.chained_passage_id and item.chained_explanation_text is not None:
                    clean_cpid = db.normalize_bracket_id(item.chained_passage_id)
                    db.update_passage_explanation(clean_cpid, item.chained_explanation_text)
                    applied_count += 1
                    if item.chained_report_id:
                        resolved_report_ids.add(item.chained_report_id)

            # 3. 승인된 오류 신고 항목들 일괄 삭제
            for rid in resolved_report_ids:
                cursor.execute("DELETE FROM error_reports WHERE id = ?", (rid,))
            conn.commit()

        return {
            "success": True,
            "applied_count": applied_count,
            "resolved_report_count": len(resolved_report_ids),
            "resolved_report_ids": list(resolved_report_ids),
            "message": f"총 {applied_count}건의 문항/문장 데이터가 성공적으로 교정되었으며, {len(resolved_report_ids)}건의 오류 신고가 해결 처리되었습니다."
        }
    except Exception as e:
        logger.error(f"일괄 교정 적용 실패: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"일괄 교정 적용에 실패했습니다: {e}")

