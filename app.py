"""
05-gichul_db: FastAPI 로컬 웹 서버 애플리케이션 (app.py)
- 구글 스타일 클린 검색 API (지문 검색 / 문장 검색)
- 2x2 지문 뷰어용 상세 데이터 및 실시간 태그 API
- 1행 테이블 문장 뷰어용 데이터 및 클립보드 복사 친화 API
- PDF + HWP 상호 검증 업로드 파이프라인 (초고속 배치 쿼리 최적화)
"""

import os
import re
import json
import shutil
import glob
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Query, BackgroundTasks, Response
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.gzip import GZipMiddleware
from pydantic import BaseModel

import database as db
import grammar_analyzer
from pdf_parser import extract_pdf_columns_and_questions
from hwp_parser import parse_hwp_questions, parse_hwp_explanations, read_answer_image, CIRCLED_MAP
import answer_keys
import answer_resolver
from validator import cross_validate_and_merge
from rate_parser import parse_correct_rate_csv, get_difficulty_badge_info

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
UPLOADS_DIR = os.path.join(BASE_DIR, "uploads")

os.makedirs(UPLOADS_DIR, exist_ok=True)
os.makedirs(STATIC_DIR, exist_ok=True)

app = FastAPI(title="05-gichul_db (기출문제 DB 웹앱)")

# 정적 파일 마운트 (/static -> static/)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


# --- Pydantic 모델 ---
class TagRequest(BaseModel):
    tag_name: str


class QuestionTypeRequest(BaseModel):
    question_type: str


class AnswerRequest(BaseModel):
    answer: str
    note: Optional[str] = ""


class SeedDataRequest(BaseModel):
    pass


class SingleProviderTestRequest(BaseModel):
    provider: str
    api_key: Optional[str] = ""
    model: Optional[str] = ""


class AISettingsRequest(BaseModel):
    provider: Optional[str] = None
    api_key: Optional[str] = ""
    model: Optional[str] = ""
    test_now: Optional[bool] = False
    active_providers: Optional[List[str]] = None
    consensus_mode: Optional[str] = None
    providers: Optional[Dict[str, Dict[str, str]]] = None
    openrouter_ensemble: Optional[bool] = None
    openrouter_ensemble_models: Optional[List[str]] = None


class BatchAnalyzeRequest(BaseModel):
    sentence_ids: Optional[List[str]] = None
    starred_only: Optional[bool] = False
    skip_already_analyzed: Optional[bool] = True
    limit: Optional[int] = 50


class AddGrammarAnnotationRequest(BaseModel):
    category_id: Optional[int] = 0
    pos: Optional[str] = ""
    full_path: Optional[str] = ""
    leaf_name: str
    target_expression: Optional[str] = ""
    explanation: Optional[str] = "수동 등록"


class BatchSetGrammarAnnotationsRequest(BaseModel):
    annotations: List[Dict[str, Any]] = []



def _regenerate_exam_crops(exam_id, grade, year, month, reading_start, reading_end, answers_dict) -> bool:
    """원본 PDF가 있으면 정답 선지 형광펜 하이라이트 크롭 이미지를 재생성하고 경로를 DB에 동기화"""
    search_patterns = [
        os.path.join(UPLOADS_DIR, f"{grade}_{year}_{month:02d}_*.pdf"),
        os.path.join(UPLOADS_DIR, f"{grade}_{year}_{month}_*.pdf"),
        os.path.join(UPLOADS_DIR, f"*{year}*{month:02d}*.pdf"),
        os.path.join(UPLOADS_DIR, f"*{year}*{month}*.pdf"),
        os.path.join(UPLOADS_DIR, f"*{grade}*{year}*.pdf"),
    ]
    pdf_candidates = []
    for pat in search_patterns:
        matched = [p for p in glob.glob(pat) if "_ans_" not in os.path.basename(p)]
        if matched:
            pdf_candidates = matched
            break
    if not pdf_candidates:
        return False
    try:
        crop_results = extract_pdf_columns_and_questions(
            pdf_path=pdf_candidates[0], grade=grade, year=year, month=month,
            start_q=reading_start, end_q=reading_end, answers_dict=answers_dict
        )
        with db.get_connection() as conn:
            cursor = conn.cursor()
            for q_n, q_data in crop_results.items():
                crop_url = q_data.get("pdf_crop_image", "")
                if crop_url:
                    cursor.execute(
                        "UPDATE passages SET pdf_crop_image = ? WHERE exam_id = ? AND q_num = ?",
                        (crop_url, exam_id, q_n)
                    )
            conn.commit()
        print(f"[Crops] {exam_id} 정답 형광펜 크롭 {len(crop_results)}개 재생성 완료")
        return True
    except Exception as crop_err:
        import traceback
        traceback.print_exc()
        print(f"[Crops] {exam_id} PDF 하이라이트 갱신 중 경고: {crop_err}")
        return False


# --- 웹 페이지 루트 ---
@app.get("/", response_class=HTMLResponse)
async def serve_index():
    """메인 웹 UI 페이지 서빙"""
    index_file = os.path.join(TEMPLATES_DIR, "index.html")
    if os.path.exists(index_file):
        with open(index_file, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse("<h1>05-gichul_db 준비 중입니다.</h1>")


# --- 통계 API ---
@app.get("/api/stats")
async def api_stats():
    """DB 통계 반환"""
    return db.get_db_stats()


# --- 검색 API ---
@app.get("/api/search/passages")
async def api_search_passages(
    keyword: str = "",
    grade: str = "",
    year: Optional[int] = None,
    month: Optional[int] = None,
    exam_type: str = "",
    question_type: str = "",
    correct_rate_range: str = "",
    tag: str = "",
    whole_word: bool = False,
    limit: int = 0
):
    """지문 검색 API (2x2 화면용 - 온전한 단어 검색 지원)"""
    # 검색어 내 #태그 자동 파싱 (예: "#빈칸" 또는 "climate #빈칸")
    if keyword and "#" in keyword:
        found_tags = re.findall(r"#([^\s#]+)", keyword)
        if found_tags and not tag:
            tag = found_tags[0]
            keyword = re.sub(r"#[^\s#]+", "", keyword).strip()

    results = db.search_passages(
        keyword=keyword,
        grade=grade,
        year=year,
        month=month,
        exam_type=exam_type,
        question_type=question_type,
        correct_rate_range=correct_rate_range,
        tag=tag,
        whole_word=whole_word,
        limit=limit
    )
    payload = json.dumps({"count": len(results), "items": results}, ensure_ascii=False)
    return Response(content=payload, media_type="application/json")


@app.get("/api/search/sentences")
async def api_search_sentences(
    keyword: str = "",
    passage_id: str = "",
    grade: str = "",
    year: Optional[int] = None,
    month: Optional[int] = None,
    exam_type: str = "",
    question_type: str = "",
    correct_rate_range: str = "",
    tag: str = "",
    is_starred: Optional[bool] = None,
    grammar_cat_id: Optional[int] = None,
    grammar_pos: Optional[str] = None,
    whole_word: bool = False,
    limit: int = 0
):
    """문장 검색 API (1행 테이블 뷰용 - 온전한 단어 검색 지원)"""
    # 검색어 내 #태그 자동 파싱
    if keyword and "#" in keyword:
        found_tags = re.findall(r"#([^\s#]+)", keyword)
        if found_tags and not tag:
            tag = found_tags[0]
            keyword = re.sub(r"#[^\s#]+", "", keyword).strip()

    results = db.search_sentences(
        keyword=keyword,
        passage_id=passage_id,
        grade=grade,
        year=year,
        month=month,
        exam_type=exam_type,
        question_type=question_type,
        correct_rate_range=correct_rate_range,
        tag=tag,
        is_starred=is_starred,
        grammar_cat_id=grammar_cat_id,
        grammar_pos=grammar_pos,
        whole_word=whole_word,
        limit=limit
    )
    payload = json.dumps({"count": len(results), "items": results}, ensure_ascii=False)
    return Response(content=payload, media_type="application/json")


# --- 단일 지문 상세 API (2x2 그리드 뷰용) ---
@app.get("/api/passages/{passage_id}")
async def api_get_passage(passage_id: str):
    """특정 지문의 상세 데이터 (HWP 해설, PDF 캡처, txt 본문, 태그, 문제유형, 정답률 및 선지 선택률)"""
    clean_id = passage_id.strip()
    if not clean_id.startswith("["):
        clean_id = f"[{clean_id}]"

    data = db.get_passage(clean_id)
    if not data:
        raise HTTPException(status_code=404, detail="해당 지문을 찾을 수 없습니다.")
    return data


# --- 문제 유형 수정 API ---
@app.patch("/api/passages/{passage_id}/question-type")
async def api_update_question_type(passage_id: str, req: QuestionTypeRequest):
    """지문의 문제 유형 변경/저장"""
    clean_id = passage_id.strip()
    if not clean_id.startswith("["):
        clean_id = f"[{clean_id}]"

    success = db.update_passage_question_type(clean_id, req.question_type)
    return {"success": success, "question_type": req.question_type}


# --- 정답 수동 정정 API ---
@app.patch("/api/passages/{passage_id}/answer")
async def api_update_answer(passage_id: str, req: AnswerRequest):
    """교사가 확인한 정답으로 정정: DB 정답/해설 헤더/검증 상태 갱신 + 키 파일 기록 + 형광펜 크롭 재생성"""
    clean_id = passage_id.strip()
    if not clean_id.startswith("["):
        clean_id = f"[{clean_id}]"
    new_ans = answer_resolver.normalize_answer(req.answer)
    if not new_ans:
        raise HTTPException(status_code=400, detail="정답은 ①~⑤ 또는 1~5 로 입력해야 합니다.")

    passage = db.get_passage(clean_id)
    if not passage:
        raise HTTPException(status_code=404, detail=f"지문 '{clean_id}'를 찾을 수 없습니다.")
    exam_id = passage["exam_id"]
    q_num = int(passage["q_num"])
    old_ans = passage.get("answer_text") or ""

    with db.get_connection() as conn:
        exam = conn.execute(
            "SELECT grade, year, month, reading_start_q, reading_end_q FROM exams WHERE id = ?", (exam_id,)
        ).fetchone()
        exam_answers = {int(r["q_num"]): (r["answer_text"] or "") for r in conn.execute(
            "SELECT q_num, answer_text FROM passages WHERE exam_id = ?", (exam_id,))}
    if not exam:
        raise HTTPException(status_code=404, detail=f"시험지 '{exam_id}'를 찾을 수 없습니다.")

    db.update_passage_answers(exam_id, {q_num: new_ans}, source="manual", verified=1)
    answer_keys.record_manual_answer(exam["grade"], exam["year"], exam["month"], q_num, new_ans, old_ans, req.note or "")

    exam_answers[q_num] = new_ans
    pdf_highlighted = False
    if old_ans != new_ans:
        pdf_highlighted = _regenerate_exam_crops(
            exam_id, exam["grade"], exam["year"], exam["month"],
            exam["reading_start_q"] or 18, exam["reading_end_q"] or 45, exam_answers
        )

    return {
        "success": True,
        "passage": db.get_passage(clean_id),
        "old_answer": old_ans,
        "new_answer": new_ans,
        "pdf_highlighted": pdf_highlighted,
        "message": f"{clean_id} 정답을 '{old_ans or '-'}' → '{new_ans}' 로 정정했습니다." + (" (형광펜 크롭 갱신)" if pdf_highlighted else "")
    }


# --- 태그 관리 API ---
@app.post("/api/passages/{passage_id}/tags")
async def api_add_passage_tag(passage_id: str, req: TagRequest):
    """지문 태그 추가"""
    clean_id = passage_id.strip()
    if not clean_id.startswith("["):
        clean_id = f"[{clean_id}]"

    success = db.add_passage_tag(clean_id, req.tag_name)
    tags = db.get_passage_tags(clean_id)
    return {"success": success, "tags": tags}


@app.delete("/api/passages/{passage_id}/tags/{tag_name}")
async def api_delete_passage_tag(passage_id: str, tag_name: str):
    """지문 태그 삭제"""
    clean_id = passage_id.strip()
    if not clean_id.startswith("["):
        clean_id = f"[{clean_id}]"

    success = db.remove_passage_tag(clean_id, tag_name)
    tags = db.get_passage_tags(clean_id)
    return {"success": success, "tags": tags}


@app.post("/api/sentences/{sentence_id}/tags")
async def api_add_sentence_tag(sentence_id: str, req: TagRequest):
    """문장 태그 추가"""
    clean_id = sentence_id.strip()
    if not clean_id.startswith("["):
        clean_id = f"[{clean_id}]"

    success = db.add_sentence_tag(clean_id, req.tag_name)
    tags = db.get_sentence_tags(clean_id)
    return {"success": success, "tags": tags}


@app.delete("/api/sentences/{sentence_id}/tags/{tag_name}")
async def api_delete_sentence_tag(sentence_id: str, tag_name: str):
    """문장 태그 삭제"""
    clean_id = sentence_id.strip()
    if not clean_id.startswith("["):
        clean_id = f"[{clean_id}]"

    success = db.remove_sentence_tag(clean_id, tag_name)
    tags = db.get_sentence_tags(clean_id)
    return {"success": success, "tags": tags}


# --- AI 어법 분석 및 설정 API ---
@app.get("/api/settings/ai")
async def api_get_ai_settings():
    """현재 저장된 모든 AI Provider의 설정 및 활성화 현황 종합 반환"""
    cfg = grammar_analyzer.get_all_ai_configs()
    # 레거시 하위 호환 필드 결합
    legacy_p, legacy_k, legacy_m = grammar_analyzer.get_ai_config()
    cfg["provider"] = legacy_p
    cfg["model"] = legacy_m
    cfg["has_key"] = bool(legacy_k)
    cfg["masked_key"] = cfg["providers"].get(legacy_p, {}).get("masked_key", "")
    return cfg


@app.get("/api/openrouter/top-models")
async def api_get_openrouter_top_models(force_refresh: bool = False):
    """OpenRouter Top 5 추천 모델 정보 실시간 조회 및 반환"""
    models = grammar_analyzer.get_openrouter_top_models(force_refresh=force_refresh)
    return {"success": True, "models": models}


@app.get("/api/openrouter/models")
async def api_get_openrouter_all_models(force_refresh: bool = False):
    """OpenRouter 전체 실시간 모델 목록 및 현재 설정된 앙상블 3개 모델 반환"""
    models = grammar_analyzer.get_all_openrouter_models(force_refresh=force_refresh)
    top_models = grammar_analyzer.get_openrouter_top_models(force_refresh=force_refresh)
    ensemble = grammar_analyzer.get_openrouter_ensemble_models()
    return {
        "success": True,
        "total": len(models),
        "models": models,
        "top_models": top_models,
        "current_ensemble": ensemble
    }



@app.post("/api/settings/ai/test")
async def api_test_single_ai_provider(req: SingleProviderTestRequest):
    """특정 AI Provider 개별 연결 핑 테스트"""
    p = req.provider.strip().lower()
    k = req.api_key.strip() if req.api_key else ""
    m = req.model.strip() if req.model else ""

    if not k:
        existing_k, existing_m = grammar_analyzer.get_provider_config(p)
        k = existing_k
        if not m:
            m = existing_m

    if not k:
        prov_label = grammar_analyzer.PROVIDER_NAMES.get(p, p)
        return JSONResponse(status_code=400, content={"success": False, "message": f"{prov_label} API Key를 입력해 주세요."})

    if p == "gemini":
        m = grammar_analyzer.resolve_gemini_model(k, m)

    ok, msg, used_model = grammar_analyzer.test_connection(p, k, m)
    if not ok:
        return JSONResponse(status_code=400, content={"success": False, "message": msg})
    return {"success": True, "provider": p, "model": used_model, "message": msg}


@app.post("/api/settings/ai")
async def api_save_ai_settings(req: AISettingsRequest):
    """AI 설정 일괄/단일 저장 및 연결 테스트"""
    import json

    # 1. 활성 Provider 목록 및 합의 판정 방식 저장 (복수 선택 지원)
    if req.active_providers is not None:
        valid_actives = [p for p in req.active_providers if p in grammar_analyzer.SUPPORTED_PROVIDERS]
        if not valid_actives:
            valid_actives = ["gemini"]
        db.set_setting("ai_active_providers", json.dumps(valid_actives))
        db.set_setting("ai_provider", valid_actives[0])

    if req.consensus_mode is not None:
        grammar_analyzer.set_consensus_mode(req.consensus_mode)

    # 2. 프로바이더별 개별 키 및 모델 설정 저장
    if req.providers:
        for p, p_data in req.providers.items():
            p_clean = p.lower()
            if p_clean in grammar_analyzer.SUPPORTED_PROVIDERS:
                k = (p_data.get("api_key") or "").strip()
                m = (p_data.get("model") or "").strip()
                if k:
                    db.set_setting(f"ai_key_{p_clean}", k)
                if m:
                    db.set_setting(f"ai_model_{p_clean}", m)

    # 3. 레거시 단일 필드 호환 처리
    if req.provider:
        p = req.provider.strip().lower()
        k = (req.api_key or "").strip()
        m = (req.model or "").strip()
        db.set_setting("ai_provider", p)
        if k:
            db.set_setting(f"ai_key_{p}", k)
            db.set_setting("ai_api_key", k)
        if m:
            db.set_setting(f"ai_model_{p}", m)
            db.set_setting("ai_model", m)

    # 4. OpenRouter 3개 모델 앙상블(교차 검토) 모드 설정 저장
    if req.openrouter_ensemble is not None:
        grammar_analyzer.set_openrouter_ensemble(req.openrouter_ensemble)
    if req.openrouter_ensemble_models is not None:
        grammar_analyzer.set_openrouter_ensemble_models(req.openrouter_ensemble_models)

    # 5. test_now인 경우 첫 번째 활성 프로바이더 연결 테스트
    test_msg = ""
    if req.test_now:
        active = grammar_analyzer.get_active_providers()
        target_p = active[0] if active else "gemini"
        tk, tm = grammar_analyzer.get_provider_config(target_p)
        if tk:
            ok, test_msg, _ = grammar_analyzer.test_connection(target_p, tk, tm)
            if not ok:
                return JSONResponse(status_code=400, content={"success": False, "message": test_msg})

    return {
        "success": True,
        "message": test_msg or "AI 설정이 성공적으로 저장되었습니다."
    }


@app.post("/api/sentences/{sentence_id}/star")
async def api_toggle_sentence_star(sentence_id: str):
    """문장 별표(⭐ 중요 문장 플래그) 토글 API"""
    clean_id = sentence_id.strip()
    if not clean_id.startswith("["):
        clean_id = f"[{clean_id}]"

    new_state = db.toggle_sentence_star(clean_id)
    return {"sentence_id": clean_id, "is_starred": new_state}


@app.post("/api/sentences/{sentence_id}/analyze-grammar")
async def api_analyze_sentence_grammar(sentence_id: str):
    """단일 문장 실시간 AI 어법 분석 및 DB 저장"""
    clean_id = sentence_id.strip()
    if not clean_id.startswith("["):
        clean_id = f"[{clean_id}]"

    target = db.get_sentence(clean_id)
    if not target:
        sentences = db.search_sentences(keyword="", passage_id="", limit=2000)
        for s in sentences:
            if s["id"] == clean_id:
                target = s
                break

    if not target:
        raise HTTPException(status_code=404, detail="문장을 찾을 수 없습니다.")

    passage = db.get_passage(target["passage_id"]) if target.get("passage_id") else None

    # 밑줄 빈칸 문제의 경우 정답 선지를 반영하고 선지 기호를 정제하여 온전한 문장 생성
    prep_text = grammar_analyzer.prepare_sentence_for_analysis(
        target["sentence_text"],
        passage_id=target.get("passage_id"),
        passage_text=passage.get("passage_text", "") if passage else "",
        answer_text=passage.get("answer_text", "") if passage else "",
        explanation_text=passage.get("explanation_text", "") if passage else ""
    )
    if prep_text and prep_text != target["sentence_text"]:
        db.update_sentence_text(clean_id, prep_text)
        target["sentence_text"] = prep_text

    try:
        annos = grammar_analyzer.analyze_sentence(
            target["sentence_text"],
            passage_id=target.get("passage_id"),
            passage_text=passage.get("passage_text", "") if passage else "",
            answer_text=passage.get("answer_text", "") if passage else "",
            explanation_text=passage.get("explanation_text", "") if passage else ""
        )
        db.save_grammar_annotations(clean_id, annos)
        return {
            "success": True,
            "sentence_id": clean_id,
            "sentence_text": target["sentence_text"],
            "annotations": annos,
            "count": len(annos),
            "grammar_analyzed": 1
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI 어법 분석 실패: {str(e)}")


@app.post("/api/sentences/{sentence_id}/grammar-annotations")
async def api_add_grammar_annotation(sentence_id: str, req: AddGrammarAnnotationRequest):
    """문장에 수동으로 어법 범주 추가"""
    clean_id = sentence_id.strip()
    if not clean_id.startswith("["):
        clean_id = f"[{clean_id}]"

    try:
        data = req.dict()
        db.add_sentence_grammar_annotation(clean_id, data)
        updated = db.get_sentence_grammar_annotations(clean_id)
        return {
            "success": True,
            "sentence_id": clean_id,
            "annotations": updated,
            "count": len(updated)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"어법 범주 추가 실패: {str(e)}")


@app.delete("/api/sentences/{sentence_id}/grammar-annotations/{identifier}")
async def api_delete_grammar_annotation(sentence_id: str, identifier: int):
    """문장의 특정 어법 범주 삭제"""
    clean_id = sentence_id.strip()
    if not clean_id.startswith("["):
        clean_id = f"[{clean_id}]"

    try:
        db.delete_sentence_grammar_annotation(clean_id, identifier)
        updated = db.get_sentence_grammar_annotations(clean_id)
        return {
            "success": True,
            "sentence_id": clean_id,
            "annotations": updated,
            "count": len(updated)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"어법 범주 삭제 실패: {str(e)}")


@app.delete("/api/sentences/{sentence_id}/grammar")
async def api_reset_sentence_grammar(sentence_id: str):
    """문장의 어법 분석 결과 및 상태를 초기화(미분석 상태로 복원)하여 재분석 허용"""
    clean_id = sentence_id.strip()
    if not clean_id.startswith("["):
        clean_id = f"[{clean_id}]"

    try:
        db.reset_sentence_grammar(clean_id)
        return {
            "success": True,
            "sentence_id": clean_id,
            "grammar_analyzed": 0,
            "annotations": []
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"어법 분석 초기화 실패: {str(e)}")


@app.post("/api/sentences/{sentence_id}/grammar-annotations/batch")
async def api_batch_set_grammar_annotations(sentence_id: str, req: BatchSetGrammarAnnotationsRequest):
    """문장의 어법 범주 목록을 모달 선택값으로 일괄 저장"""
    clean_id = sentence_id.strip()
    if not clean_id.startswith("["):
        clean_id = f"[{clean_id}]"

    try:
        updated = db.set_sentence_grammar_annotations(clean_id, req.annotations)
        return {
            "success": True,
            "sentence_id": clean_id,
            "annotations": updated,
            "count": len(updated)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"어법 범주 일괄 설정 실패: {str(e)}")


@app.post("/api/sentences/batch-analyze-grammar")
async def api_batch_analyze_grammar(req: BatchAnalyzeRequest):
    """다중 문장 배치 AI 어법 분석 (선택된 활성 모델 엄격 교집합 적용)"""
    active_configs = grammar_analyzer.get_active_ai_configs()
    valid_configs = [c for c in active_configs if c["api_key"]]
    if not valid_configs:
        raise HTTPException(status_code=400, detail="활성화된 AI 모델 중 유효한 API Key가 등록된 모델이 없습니다. 상단 [🔑 AI 설정]에서 먼저 등록해 주세요.")

    if req.sentence_ids:
        target_ids = set(req.sentence_ids)
        all_sentences = db.search_sentences(limit=0)
        sentences = [s for s in all_sentences if s["id"] in target_ids]
    else:
        limit_val = req.limit or 0
        sentences = db.search_sentences(is_starred=True if req.starred_only else None, limit=limit_val)

    # 이미 어법 분석이 완료된 문장 필터링 (토큰 절약 및 중복 분석 방지: 어법 배지가 있거나 특이 어법 없음으로 분석된 문장 제외)
    if req.skip_already_analyzed:
        sentences = [s for s in sentences if not s.get("grammar_analyzed") and not s.get("grammar_annotations")]

    if not sentences:
        return {
            "total_processed": 0,
            "results": [],
            "message": "선택된 문장들이 이미 모두 어법 분석 완료 상태입니다."
        }

    passages_cache = {}
    results = []
    for s in sentences:
        pid = s.get("passage_id")
        p_data = None
        if pid:
            if pid not in passages_cache:
                passages_cache[pid] = db.get_passage(pid)
            p_data = passages_cache[pid]

        try:
            prep_text = grammar_analyzer.prepare_sentence_for_analysis(
                s["sentence_text"],
                passage_id=pid,
                passage_text=p_data.get("passage_text", "") if p_data else "",
                answer_text=p_data.get("answer_text", "") if p_data else "",
                explanation_text=p_data.get("explanation_text", "") if p_data else ""
            )
            if prep_text and prep_text != s["sentence_text"]:
                db.update_sentence_text(s["id"], prep_text)
                s["sentence_text"] = prep_text

            annos = grammar_analyzer.analyze_sentence(
                s["sentence_text"],
                passage_id=pid,
                passage_text=p_data.get("passage_text", "") if p_data else "",
                answer_text=p_data.get("answer_text", "") if p_data else "",
                explanation_text=p_data.get("explanation_text", "") if p_data else ""
            )
            db.save_grammar_annotations(s["id"], annos)
            results.append({
                "sentence_id": s["id"],
                "sentence_text": s.get("sentence_text", ""),
                "count": len(annos),
                "success": True,
                "annotations": annos,
                "grammar_analyzed": 1
            })
        except Exception as e:
            results.append({
                "sentence_id": s["id"],
                "sentence_text": s.get("sentence_text", ""),
                "error": str(e),
                "success": False,
                "annotations": [],
                "grammar_analyzed": 0
            })

    return {
        "total_processed": len(results),
        "results": results
    }


def background_auto_analyze_exam_grammar(exam_id: str):
    """업로드 완료 후 백그라운드에서 해당 시험지의 문장 자동 어법 분석"""
    try:
        active_configs = grammar_analyzer.get_active_ai_configs()
        if not any(c["api_key"] for c in active_configs):
            return

        sentences = db.search_sentences(passage_id="", limit=1000)
        prefix = exam_id.rstrip("]")
        target_sentences = [s for s in sentences if s["id"].startswith(prefix)]
        passages_cache = {}
        for s in target_sentences:
            try:
                if s.get("grammar_analyzed") or s.get("grammar_annotations"):
                    continue
                pid = s.get("passage_id")
                p_data = None
                if pid:
                    if pid not in passages_cache:
                        passages_cache[pid] = db.get_passage(pid)
                    p_data = passages_cache[pid]

                prep_text = grammar_analyzer.prepare_sentence_for_analysis(
                    s["sentence_text"],
                    passage_id=pid,
                    passage_text=p_data.get("passage_text", "") if p_data else "",
                    answer_text=p_data.get("answer_text", "") if p_data else "",
                    explanation_text=p_data.get("explanation_text", "") if p_data else ""
                )
                if prep_text and prep_text != s["sentence_text"]:
                    db.update_sentence_text(s["id"], prep_text)
                    s["sentence_text"] = prep_text

                annos = grammar_analyzer.analyze_sentence(
                    s["sentence_text"],
                    passage_id=pid,
                    passage_text=p_data.get("passage_text", "") if p_data else "",
                    answer_text=p_data.get("answer_text", "") if p_data else "",
                    explanation_text=p_data.get("explanation_text", "") if p_data else ""
                )
                db.save_grammar_annotations(s["id"], annos)
            except Exception as ex:
                print(f"[Background Grammar Analysis Error] {s['id']}: {ex}")
    except Exception as e:
        print(f"[Background Grammar Task Error] {e}")


# --- 파일 업로드 및 상호 검증 파이프라인 API ---
@app.post("/api/upload")
async def api_upload_exam(
    background_tasks: BackgroundTasks,
    grade: str = Form("고3"),
    year: int = Form(2024),
    month: int = Form(6),
    exam_type: str = Form("평가원"),
    reading_start: Optional[int] = Form(None),
    reading_end: Optional[int] = Form(None),
    pdf_file: UploadFile = File(...),
    hwp_file: UploadFile = File(...),
    exp_file: Optional[UploadFile] = File(None),
    ans_file: Optional[UploadFile] = File(None),
    csv_file: Optional[UploadFile] = File(None)
):
    """
    동일 시험지의 PDF, HWP(문제지), 선택적 해설지(HWP), 선택적 정답표 이미지(PNG/JPG), 선택적 정답률 CSV 파일 업로드 및 상호 검증 파이프라인
    """
    # 1. 업로드 파일 임시 저장
    pdf_save_path = os.path.join(UPLOADS_DIR, f"{grade}_{year}_{month:02d}_{pdf_file.filename}")
    hwp_save_path = os.path.join(UPLOADS_DIR, f"{grade}_{year}_{month:02d}_{hwp_file.filename}")

    with open(pdf_save_path, "wb") as buffer:
        shutil.copyfileobj(pdf_file.file, buffer)
    with open(hwp_save_path, "wb") as buffer:
        shutil.copyfileobj(hwp_file.file, buffer)

    exp_save_path = None
    if exp_file and exp_file.filename:
        exp_save_path = os.path.join(UPLOADS_DIR, f"{grade}_{year}_{month:02d}_exp_{exp_file.filename}")
        with open(exp_save_path, "wb") as buffer:
            shutil.copyfileobj(exp_file.file, buffer)

    ans_save_path = None
    if ans_file and ans_file.filename:
        ans_save_path = os.path.join(UPLOADS_DIR, f"{grade}_{year}_{month:02d}_ans_{ans_file.filename}")
        with open(ans_save_path, "wb") as buffer:
            shutil.copyfileobj(ans_file.file, buffer)

    csv_save_path = None
    if csv_file and csv_file.filename:
        csv_save_path = os.path.join(UPLOADS_DIR, f"{grade}_{year}_{month:02d}_{csv_file.filename}")
        with open(csv_save_path, "wb") as buffer:
            shutil.copyfileobj(csv_file.file, buffer)

    try:
        # 2. 시험지 정보 DB 등록
        exam_id = f"[{grade}-{year}년-{month:02d}월]"
        # 출제기관 자동 판별 규칙 적용 (3학년 6, 9, 11월: 평가원, 그 외 3학년 월 및 1, 2학년 전체: 교육청)
        if grade in ("고3", "3학년") and month in (6, 9, 11):
            exam_type = "평가원"
        else:
            exam_type = "교육청"

        db.save_exam({
            "id": exam_id,
            "grade": grade,
            "year": year,
            "month": month,
            "exam_type": exam_type,
            "reading_start_q": reading_start or 18,
            "reading_end_q": reading_end or 45
        })

        # 3. 정답 소스 수집
        # (1) 정답표 이미지(-A.png): 활성화된 모든 Vision 모델이 독립 판독, 2개 이상 일치한 문항만 검증 정답으로 인정
        image_report = None
        if ans_save_path and os.path.exists(ans_save_path):
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
                print(f"[Upload] 정답률 CSV 파싱 실패: {e}")

        # (4) 문항별 정답 확정: 검증 키 파일 > CSV 정답 > 이미지 모델 합의 > 이미지 단일 모델 > HWP 해설
        #     검증되지 않은 소스로 결정된 문항은 answer_verified=0 으로 기록되고 응답에 경고로 명시된다 (무언 폴백 금지)
        resolution = answer_resolver.resolve_answers(
            q_range=range(reading_start or 18, (reading_end or 45) + 1),
            verified_key=answer_keys.load_answer_key(grade, year, month),
            image_report=image_report,
            csv_rates=rates_dict,
            hwp_answers={q: info.get("answer", "") for q, info in explanations.items()},
        )
        answers_dict = resolution["answers"]
        for w in resolution["report"]["warnings"]:
            print(f"[Upload][정답 검증 경고] {exam_id} {w}")

        # (5) 최종 확정된 정답을 explanations 해설 텍스트 헤더 및 answer 필드에 동기화
        for q_num, final_ans in answers_dict.items():
            if q_num in explanations:
                explanations[q_num]["answer"] = final_ans
                exp_body = explanations[q_num].get("explanation", "").strip()
                if re.search(r"^\s*\[\s*정답\s*\]", exp_body):
                    explanations[q_num]["explanation"] = re.sub(
                        r"^\s*\[\s*정답\s*\]\s*[①②③④⑤1-5]?",
                        f"[정답] {final_ans}",
                        exp_body
                    )
                else:
                    explanations[q_num]["explanation"] = f"[정답] {final_ans}\n\n{exp_body}".strip()
            else:
                explanations[q_num] = {"answer": final_ans, "explanation": f"[정답] {final_ans}"}

        # 4. PDF 문제지 파싱 및 캡처 (정답 선지 형광펜 하이라이트 연동)
        pdf_questions = extract_pdf_columns_and_questions(
            pdf_path=pdf_save_path,
            grade=grade,
            year=year,
            month=month,
            start_q=reading_start or 18,
            end_q=reading_end or 45,
            answers_dict=answers_dict
        )

        # 5. HWP 문제지 파싱 (독해 지문 문항)
        hwp_questions = parse_hwp_questions(
            hwp_path=hwp_save_path,
            grade=grade,
            year=year,
            month=month,
            start_q=reading_start or 18,
            end_q=reading_end or 45,
            answers_dict=answers_dict
        )

        # 6. 상호 검증 및 문장 분할
        merged_packages = cross_validate_and_merge(
            hwp_data=hwp_questions,
            pdf_data=pdf_questions,
            explanations=explanations,
            grade=grade,
            year=year,
            month=month
        )

        # 7. SQLite DB 일괄 저장
        saved_passages_count = 0
        saved_sentences_count = 0

        for pkg in merged_packages:
            db.save_passage(pkg["passage_data"])
            saved_passages_count += 1
            if pkg["sentences"]:
                db.save_sentences(pkg["sentences"])
                saved_sentences_count += len(pkg["sentences"])

        # 문항별 정답 출처/검증 상태 기록
        db.set_answer_status(exam_id, resolution["sources"], resolution["verified"])

        # 정답률 데이터가 파싱된 경우 passages 테이블에 일괄 반영
        if rates_dict:
            try:
                db.save_exam_correct_rates(exam_id, rates_dict)
            except Exception as e:
                print(f"[Upload] 정답률 DB 갱신 실패: {e}")

        # AI API 키가 설정되어 있는 경우 백그라운드 어법 자동 분석 스케줄링
        _, ai_key, _ = grammar_analyzer.get_ai_config()
        if ai_key:
            background_tasks.add_task(background_auto_analyze_exam_grammar, exam_id)

        report = resolution["report"]
        msg = f"성공적으로 {saved_passages_count}개 문항과 {saved_sentences_count}개 문장을 상호 검증하여 저장했습니다."
        if report["unverified_questions"]:
            msg += f" ⚠ 정답 미검증 {len(report['unverified_questions'])}문항 - 정답표 이미지/정답률 CSV를 확인하세요."
        return {
            "status": "success",
            "exam_id": exam_id,
            "passages_count": saved_passages_count,
            "sentences_count": saved_sentences_count,
            "answer_report": report,
            "message": msg
        }

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"파싱 및 저장 중 오류 발생: {str(e)}")


# --- 시험지 관리 및 삭제 API ---
@app.get("/api/exams")
async def api_get_exams():
    """등록된 모든 시험지 목록 및 통계 반환"""
    try:
        exams = db.get_all_exams_with_stats()
        return {"status": "success", "total": len(exams), "items": exams}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"시험지 목록 조회 실패: {str(e)}")


@app.delete("/api/exams/{exam_id}")
async def api_delete_exam(exam_id: str):
    """지정된 시험지 및 관련 모든 데이터(지문, 문장, 어법, 태그, 캡처 이미지) 연쇄 삭제"""
    try:
        res = db.delete_exam(exam_id)
        if not res.get("success"):
            raise HTTPException(status_code=404, detail=res.get("message", "시험지를 찾을 수 없습니다."))
        return res
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"시험지 삭제 중 오류 발생: {str(e)}")


@app.post("/api/exams/{exam_id}/upload-file")
async def api_upload_exam_single_file(
    exam_id: str,
    file_type: str = Form(...),  # "ans" | "pdf" | "hwp" | "csv"
    file: UploadFile = File(...)
):
    """
    기존 등록된 특정 시험지에 대해 단독 파일(정답표 이미지, PDF, HWP, 정답률 CSV)을 업로드 및 갱신하는 API
    특히 정답표 이미지(ans) 또는 정답률 CSV(csv) 업로드 시 데이터 추출 + DB 갱신 자동 수행
    """
    clean_id = exam_id.strip()
    if not clean_id.startswith("["):
        clean_id = f"[{clean_id}]"

    # 1. 시험지 정보 조회
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, grade, year, month, reading_start_q, reading_end_q FROM exams WHERE id = ?", (clean_id,))
        exam = cursor.fetchone()

    if not exam:
        raise HTTPException(status_code=404, detail=f"시험지 '{clean_id}'를 찾을 수 없습니다.")

    grade = exam["grade"]
    year = exam["year"]
    month = exam["month"]
    reading_start = exam["reading_start_q"] or 18
    reading_end = exam["reading_end_q"] or 45

    # 2. 파일 저장
    if file_type == "ans":
        save_path = os.path.join(UPLOADS_DIR, f"{grade}_{year}_{month:02d}_ans_{file.filename}")
    else:
        save_path = os.path.join(UPLOADS_DIR, f"{grade}_{year}_{month:02d}_{file.filename}")

    with open(save_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # 3. 정답표 이미지(ans) 처리
    if file_type == "ans":
        try:
            # (1) 활성화된 모든 Vision 모델로 독립 판독 → 2개 이상 일치한 문항만 검증 정답으로 인정
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

            # (2) DB 지문 정답 및 해설 텍스트 갱신 (검증 키 파일이 있으면 키 파일 우선)
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
                        if not re.search(r"^\s*\[\s*정답\s*\]", exp_body):
                            new_exp = f"[정답] {target_ans}\n\n{exp_body}".strip()
                        else:
                            new_exp = re.sub(r"^\s*\[\s*정답\s*\]\s*[①②③④⑤1-5]?", f"[정답] {target_ans}", exp_body)

                        cursor.execute(
                            "UPDATE passages SET answer_text = ?, explanation_text = ?, answer_source = ?, answer_verified = ? WHERE id = ?",
                            (target_ans, new_exp, src, ver, p["id"])
                        )
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

            # (1) 기존 DB 정답과 교차검증: 다른 시험의 CSV면 반영 거부, 정답률이 유일하게 가리키는 정답은 정정/확인
            with db.get_connection() as conn:
                rows = conn.execute("SELECT q_num, answer_text FROM passages WHERE exam_id = ?", (clean_id,)).fetchall()
            current = {int(r["q_num"]): r["answer_text"] or "" for r in rows}
            check = answer_resolver.check_csv_against_answers(rates_dict, current)
            if check["suspect"]:
                raise HTTPException(status_code=422, detail=(
                    f"정답률 CSV가 다른 시험의 데이터로 의심되어 반영하지 않았습니다 "
                    f"(비교 {check['checked']}문항 중 {len(check['mismatch'])}문항 정답 불일치: {check['mismatch']}). 파일을 확인하세요."
                ))

            # (2) 정답률/선택률 저장
            res_data = db.save_exam_correct_rates(clean_id, rates_dict)

            # (3) CSV가 결정적으로 확정한 정답: 기존 정답 정정 + 검증 상태 기록
            decided = {q: new for q, (_old, new) in check["corrections"].items()}
            decided.update({q: current[q] for q in check["confirmed"]})
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

    # 5. PDF 또는 HWP 파일 단독 교체 시
    return {
        "status": "success",
        "exam_id": clean_id,
        "file_type": file_type,
        "message": f"{file_type.upper()} 파일이 성공적으로 업로드되었습니다."
    }


class BatchDeleteRequest(BaseModel):
    exam_ids: List[str]


class SelectiveDeleteRequest(BaseModel):
    exam_ids: List[str]
    delete_raw_files: bool = True
    delete_core_corpus: bool = True
    delete_metadata: bool = True
    delete_rate_data: bool = False


@app.post("/api/exams/selective-delete")
async def api_selective_delete_exams(req: SelectiveDeleteRequest):
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


@app.post("/api/exams/batch-delete")
async def api_batch_delete_exams(req: BatchDeleteRequest):
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


# --- 데모/샘플 데이터 즉시 시드 API (사용자가 바로 화면을 테스트할 수 있도록 제공) ---
@app.post("/api/seed-sample-data")
async def api_seed_sample_data():
    """실제 수능/모의고사 대표 기출 지문 3개와 문장 20여 개를 즉시 DB에 주입"""
    from sentence_tokenizer import create_sentence_records

    # 샘플 시험지 1: 2024년 6월 모평 고3
    exam1 = {
        "id": "[고3-2024년-06월]",
        "grade": "고3",
        "year": 2024,
        "month": 6,
        "exam_type": "평가원",
        "reading_start_q": 18,
        "reading_end_q": 45
    }
    db.save_exam(exam1)

    # 지문 1: 21번 함축의미
    p21_id = "[고3-2024년-06월-21번]"
    p21_text = (
        "In modern science, the concept of objectivity has undergone a profound transformation. "
        "Scientists have long realized that observation is not a passive reception of external facts, "
        "but an active engagement with the world. Dr. James Smith notes that our theoretical frameworks "
        "invariably shape what we perceive. For example, e.g., the way quantum physicists measure "
        "subatomic particles influences their observed states. Consequently, true objectivity does not "
        "mean viewing reality from nowhere, but acknowledging our situated perspectives."
    )
    p21_data = {
        "id": p21_id,
        "exam_id": exam1["id"],
        "q_num": 21,
        "question_title": "21. 밑줄 친 viewing reality from nowhere가 다음 글에서 의미하는 바로 가장 적절한 것은? [3점]",
        "question_type": "어휘함축",
        "passage_text": p21_text,
        "answer_text": "③",
        "explanation_text": (
            "[정답] ③\n"
            "[해설] 현대 과학에서 관찰자가 가진 이론적 틀이 관찰 결과에 영향을 미치므로, "
            "완전한 무위치(viewing reality from nowhere)에서 객관성을 찾는 것은 불가능하며 "
            "자신의 위치된 관점을 인정해야 한다는 요지의 글이다.\n"
            "[어휘] objectivity: 객관성 / profound: 심오한 / situated: 위치한, 특정한 상황에 놓인"
        ),
        "pdf_crop_image": "",
        "validation_ratio": 1.0,
        "remarks": "HWP-PDF 일치율 100%"
    }
    db.save_passage(p21_data)
    s21 = create_sentence_records(p21_id, p21_text)
    db.save_sentences(s21)
    db.add_passage_tag(p21_id, "함축의미")
    db.add_passage_tag(p21_id, "과학철학")
    if s21:
        db.add_sentence_tag(s21[0]["id"], "핵심주제문")
        db.add_sentence_tag(s21[1]["id"], "not A but B 구문")

    # 지문 2: 31번 빈칸추론
    p31_id = "[고3-2024년-06월-31번]"
    p31_text = (
        "Human memory is fundamentally constructive rather than reproductive. "
        "When we recall past events, our brains do not replay a recorded video tape. "
        "Instead, we piece together fragments of information stored across various neural networks. "
        "In this process, our current emotions, beliefs, and expectations heavily influence the outcome. "
        "This inherent plasticity allows us to adapt to future scenarios, yet it also makes our recollections "
        "remarkably vulnerable to distortion. Therefore, memory serves adaptability rather than absolute accuracy."
    )
    p31_data = {
        "id": p31_id,
        "exam_id": exam1["id"],
        "q_num": 31,
        "question_title": "31. 다음 빈칸에 들어갈 말로 가장 적절한 것을 고르시오. [3점]",
        "question_type": "빈칸",
        "passage_text": p31_text,
        "answer_text": "②",
        "explanation_text": (
            "[정답] ②\n"
            "[해설] 인간의 기억은 과거를 그대로 재생하는 것이 아니라 현재의 정서와 신념에 따라 재구성되는 구성적 특성을 지닌다는 내용이다.\n"
            "[어휘] constructive: 구성적인 / plasticity: 가소성 / distortion: 왜곡 / adaptability: 적응성"
        ),
        "pdf_crop_image": "",
        "validation_ratio": 0.998,
        "remarks": "HWP-PDF 일치율 99.8%"
    }
    db.save_passage(p31_data)
    s31 = create_sentence_records(p31_id, p31_text)
    db.save_sentences(s31)
    db.add_passage_tag(p31_id, "빈칸추론")
    db.add_passage_tag(p31_id, "인지심리학")
    if s31:
        db.add_sentence_tag(s31[0]["id"], "핵심정의문")

    # 지문 3: 고2 2023년 3월 34번
    exam2 = {
        "id": "[고2-2023년-03월]",
        "grade": "고2",
        "year": 2023,
        "month": 3,
        "exam_type": "교육청",
        "reading_start_q": 18,
        "reading_end_q": 45
    }
    db.save_exam(exam2)

    p34_id = "[고2-2023년-03월-34번]"
    p34_text = (
        "Language does not merely reflect our thoughts; it actively structures how we experience time. "
        "For instance, speakers of English usually describe time using spatial metaphors of horizontal lines, "
        "moving forward from left to right. In contrast, Mandarin speakers frequently employ vertical metaphors. "
        "Psycholinguistic experiments demonstrate that these linguistic differences directly alter cognitive processing speeds. "
        "Thus, the vocabulary and grammar we acquire shape the mental architecture of our reality."
    )
    p34_data = {
        "id": p34_id,
        "exam_id": exam2["id"],
        "q_num": 34,
        "question_title": "34. 다음 빈칸에 들어갈 말로 가장 적절한 것을 고르시오.",
        "question_type": "빈칸",
        "passage_text": p34_text,
        "answer_text": "①",
        "explanation_text": (
            "[정답] ①\n"
            "[해설] 언어가 단순히 생각을 표현하는 수단이 아니라 인간의 시간 인지 구조 자체를 형성한다는 사피어-워프 가설 관련 지문이다.\n"
            "[어휘] metaphor: 은유 / psycholinguistic: 심리언어학의 / alter: 바꾸다"
        ),
        "pdf_crop_image": "",
        "validation_ratio": 1.0,
        "remarks": "HWP-PDF 일치율 100%"
    }
    db.save_passage(p34_data)
    s34 = create_sentence_records(p34_id, p34_text)
    db.save_sentences(s34)
    db.add_passage_tag(p34_id, "언어학")
    db.add_passage_tag(p34_id, "빈칸추론")

    stats = db.get_db_stats()
    return {
        "status": "success",
        "message": "고3/고2 평가원·교육청 대표 기출 샘플 데이터(3개 지문, 18개 문장)가 성공적으로 주입되었습니다.",
        "stats": stats
    }
