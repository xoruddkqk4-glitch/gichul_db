"""
05-gichul_db: FastAPI 로컬 웹 서버 애플리케이션 (app.py)
- 구글 스타일 클린 검색 API (지문 검색 / 문장 검색)
- 2x2 지문 뷰어용 상세 데이터 및 실시간 태그 API
- 1행 테이블 문장 뷰어용 데이터 및 클립보드 복사 친화 API
- PDF + HWP 상호 검증 업로드 파이프라인
"""

import os
import re
import shutil
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Query, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import database as db
import grammar_analyzer
from pdf_parser import extract_pdf_columns_and_questions
from hwp_parser import parse_hwp_questions, parse_hwp_explanations, KNOWN_EXAM_ANSWERS, CIRCLED_MAP
from validator import cross_validate_and_merge

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


class SeedDataRequest(BaseModel):
    pass


class AISettingsRequest(BaseModel):
    provider: str = "gemini"
    api_key: str = ""
    model: Optional[str] = ""
    test_now: Optional[bool] = False


class BatchAnalyzeRequest(BaseModel):
    sentence_ids: Optional[List[str]] = None
    starred_only: Optional[bool] = False
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
    tag: str = "",
    whole_word: bool = False,
    limit: int = 1000
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
        tag=tag,
        whole_word=whole_word,
        limit=limit
    )
    return {"count": len(results), "items": results}


@app.get("/api/search/sentences")
async def api_search_sentences(
    keyword: str = "",
    passage_id: str = "",
    grade: str = "",
    year: Optional[int] = None,
    month: Optional[int] = None,
    exam_type: str = "",
    tag: str = "",
    is_starred: Optional[bool] = None,
    grammar_cat_id: Optional[int] = None,
    grammar_pos: Optional[str] = None,
    whole_word: bool = False,
    limit: int = 5000
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
        tag=tag,
        is_starred=is_starred,
        grammar_cat_id=grammar_cat_id,
        grammar_pos=grammar_pos,
        whole_word=whole_word,
        limit=limit
    )
    return {"count": len(results), "items": results}


# --- 단일 지문 상세 API (2x2 그리드 뷰용) ---
@app.get("/api/passages/{passage_id}")
async def api_get_passage(passage_id: str):
    """특정 지문의 상세 데이터 (HWP 해설, PDF 캡처, txt 본문, 태그, 문제유형)"""
    clean_id = passage_id.strip()
    if not clean_id.startswith("["):
        clean_id = f"[{clean_id}]"

    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM passages WHERE id = ?", (clean_id,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="해당 지문을 찾을 수 없습니다.")

        data = dict(row)
        data["tags"] = db.get_passage_tags(clean_id)
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
    """현재 저장된 AI Provider 및 마스킹된 API 키 상태 반환"""
    provider, api_key, model = grammar_analyzer.get_ai_config()
    masked_key = ""
    if api_key:
        if len(api_key) > 8:
            masked_key = api_key[:4] + "•" * (len(api_key) - 8) + api_key[-4:]
        else:
            masked_key = "••••••••"

    return {
        "provider": provider,
        "model": model,
        "has_key": bool(api_key),
        "masked_key": masked_key
    }


@app.get("/api/openrouter/top-models")
async def api_get_openrouter_top_models(force_refresh: bool = False):
    """OpenRouter Top 5 추천 모델 정보 실시간 조회 및 반환"""
    models = grammar_analyzer.get_openrouter_top_models(force_refresh=force_refresh)
    return {"success": True, "models": models}


@app.post("/api/settings/ai")
async def api_save_ai_settings(req: AISettingsRequest):
    """AI 설정 저장 및 연결 테스트"""
    p = req.provider.strip().lower()
    k = req.api_key.strip()
    m = req.model.strip() if req.model else ""

    # 빈 키가 넘어왔는데 기존 키가 있다면 유지
    if not k:
        _, existing_k, _ = grammar_analyzer.get_ai_config()
        k = existing_k

    db.set_setting("ai_provider", p)
    if k:
        db.set_setting("ai_api_key", k)
    if m:
        db.set_setting("ai_model", m)

    test_msg = ""
    test_ok = True
    if req.test_now and k:
        test_ok, test_msg = grammar_analyzer.test_connection(p, k, m)
        if not test_ok:
            return JSONResponse(status_code=400, content={"success": False, "message": test_msg})

    return {
        "success": True,
        "provider": p,
        "model": m,
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

    sentences = db.search_sentences(keyword="", passage_id="", limit=1000)
    target = None
    for s in sentences:
        if s["id"] == clean_id:
            target = s
            break

    if not target:
        raise HTTPException(status_code=404, detail="문장을 찾을 수 없습니다.")

    try:
        annos = grammar_analyzer.analyze_sentence(target["sentence_text"])
        db.save_grammar_annotations(clean_id, annos)
        return {
            "success": True,
            "sentence_id": clean_id,
            "annotations": annos,
            "count": len(annos)
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
    """다중 문장 배치 AI 어법 분석"""
    provider, api_key, model = grammar_analyzer.get_ai_config()
    if not api_key:
        raise HTTPException(status_code=400, detail="AI API Key가 설정되지 않았습니다. 상단 [🔑 AI 설정]에서 먼저 등록해 주세요.")

    sentences = db.search_sentences(is_starred=True if req.starred_only else None, limit=req.limit or 50)
    
    if req.sentence_ids:
        sentences = [s for s in sentences if s["id"] in req.sentence_ids]

    results = []
    for s in sentences:
        try:
            annos = grammar_analyzer.analyze_sentence(s["sentence_text"], provider, api_key, model)
            if annos:
                db.save_grammar_annotations(s["id"], annos)
            results.append({"sentence_id": s["id"], "count": len(annos), "success": True})
        except Exception as e:
            results.append({"sentence_id": s["id"], "error": str(e), "success": False})

    return {
        "total_processed": len(results),
        "results": results
    }


def background_auto_analyze_exam_grammar(exam_id: str):
    """업로드 완료 후 백그라운드에서 해당 시험지의 문장 자동 어법 분석"""
    try:
        provider, api_key, model = grammar_analyzer.get_ai_config()
        if not api_key:
            return

        sentences = db.search_sentences(passage_id="", limit=1000)
        prefix = exam_id.rstrip("]")
        target_sentences = [s for s in sentences if s["id"].startswith(prefix)]
        for s in target_sentences:
            try:
                if s.get("grammar_annotations"):
                    continue
                annos = grammar_analyzer.analyze_sentence(s["sentence_text"], provider, api_key, model)
                if annos:
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
    exp_file: Optional[UploadFile] = File(None)
):
    """
    동일 시험지의 PDF, HWP(문제지), 선택적 해설지(HWP) 파일 업로드 및 상호 검증 파이프라인
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

    try:
        # 2. 시험지 정보 DB 등록
        exam_id = f"[{grade}-{year}년-{month:02d}월]"
        db.save_exam({
            "id": exam_id,
            "grade": grade,
            "year": year,
            "month": month,
            "exam_type": exam_type,
            "reading_start_q": reading_start or 18,
            "reading_end_q": reading_end or 45
        })

        # 3. PDF 문제지 파싱 및 캡처
        pdf_questions = extract_pdf_columns_and_questions(
            pdf_path=pdf_save_path,
            grade=grade,
            year=year,
            month=month,
            start_q=reading_start or 18,
            end_q=reading_end or 45
        )

        # 4. 해설 파일이 있는 경우 해설 파싱
        explanations = {}
        if exp_save_path:
            explanations = parse_hwp_explanations(exp_save_path)

        # 정답표 결합 (HWP 해설지 우선, 미등록 시 기출 정답 백업 사전 참조)
        answers_dict = {}
        for q_num, exp_data in explanations.items():
            ans = exp_data.get("answer", "").strip()
            if ans in CIRCLED_MAP:
                ans = CIRCLED_MAP[ans]
            if ans:
                answers_dict[q_num] = ans

        exam_key = (grade, year, month)
        if exam_key in KNOWN_EXAM_ANSWERS:
            backup_answers = KNOWN_EXAM_ANSWERS[exam_key]
            for q_num, ans in backup_answers.items():
                if q_num not in answers_dict or not answers_dict[q_num]:
                    answers_dict[q_num] = ans

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

        # AI API 키가 설정되어 있는 경우 백그라운드 어법 자동 분석 스케줄링
        _, ai_key, _ = grammar_analyzer.get_ai_config()
        if ai_key:
            background_tasks.add_task(background_auto_analyze_exam_grammar, exam_id)

        return {
            "status": "success",
            "exam_id": exam_id,
            "passages_count": saved_passages_count,
            "sentences_count": saved_sentences_count,
            "message": f"성공적으로 {saved_passages_count}개 문항과 {saved_sentences_count}개 문장을 상호 검증하여 저장했습니다."
        }

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"파싱 및 저장 중 오류 발생: {str(e)}")


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
