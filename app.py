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
import io
import zipfile
from urllib.parse import quote
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Query, BackgroundTasks, Response, Body
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
import logging
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.gzip import GZipMiddleware
from pydantic import BaseModel

logger = logging.getLogger("gichul_db")
os.environ["COQUI_TOS_AGREED"] = "1"

try:
    import orjson
    def fast_json_dumps(obj: Any) -> bytes:
        return orjson.dumps(obj)
except ImportError:
    def fast_json_dumps(obj: Any) -> bytes:
        return json.dumps(obj, ensure_ascii=False).encode("utf-8")

import database as db
import grammar_analyzer
import pymupdf as fitz
from pdf_parser import extract_pdf_columns_and_questions, detect_listening_range
from hwp_parser import parse_hwp_questions, parse_hwp_explanations, read_answer_image, CIRCLED_MAP, get_hwp_text, convert_hwp_to_pdf
import answer_keys
import answer_resolver
from validator import cross_validate_and_merge
from rate_parser import parse_correct_rate_csv, get_difficulty_badge_info
import tts_service
import listening_parser
import fels_engine


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
UPLOADS_DIR = os.path.join(BASE_DIR, "uploads")

os.makedirs(UPLOADS_DIR, exist_ok=True)
os.makedirs(STATIC_DIR, exist_ok=True)

app = FastAPI(title="05-gichul_db (기출문제 DB 웹앱)")

# GZip 압축 미들웨어 등록 (1KB 이상의 모든 JSON/텍스트 응답을 80~90% 초고속 압축하여 전송 지연 해결)
app.add_middleware(GZipMiddleware, minimum_size=1000)

from collections import OrderedDict
import threading

class FastSearchCache:
    """스레드 안전 인메모리 검색 결과 캐시 (동일 조건 쿼리 1ms 즉시 반환)"""
    def __init__(self, maxsize: int = 256):
        self._cache: OrderedDict = OrderedDict()
        self._maxsize = maxsize
        self._lock = threading.Lock()

    def get(self, key: str) -> Optional[bytes]:
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
                return self._cache[key]
            return None

    def set(self, key: str, value: bytes) -> None:
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
            self._cache[key] = value
            if len(self._cache) > self._maxsize:
                self._cache.popitem(last=False)

    def clear(self) -> None:
        with self._lock:
            self._cache.clear()

search_cache = FastSearchCache(maxsize=256)

# 정적 파일 마운트 (/static -> static/)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.middleware("http")
async def no_cache_static_js(request, call_next):
    """ES 모듈 파일(/static/js/*.js)은 import 경로에 ?v= 캐시버스터가 없으므로 항상 재검증(ETag)하도록 강제"""
    response = await call_next(request)
    if request.url.path.startswith("/static/js/"):
        response.headers["Cache-Control"] = "no-cache"
    return response


_WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
# 검색 결과에 영향을 주지 않는 쓰기 경로 (AI 키 저장/테스트, TTS 미리듣기 등)
_CACHE_SAFE_WRITE_PREFIXES = ("/api/settings/",)


@app.middleware("http")
async def invalidate_cache_on_write(request, call_next):
    """데이터를 바꾸는 API 요청이 끝나면 검색 캐시와 시험지 통계 캐시를 비운다.

    실패 응답(4xx/5xx)이어도 일부 데이터가 이미 저장됐을 수 있으므로 상태 코드와 관계없이 비운다.
    (캐시를 비우는 비용은 다음 검색 1회가 DB를 다시 읽는 것뿐이다.)
    """
    response = await call_next(request)
    path = request.url.path
    if (request.method in _WRITE_METHODS
            and path.startswith("/api/")
            and not path.startswith(_CACHE_SAFE_WRITE_PREFIXES)):
        search_cache.clear()
        db.invalidate_exams_cache()
    return response


# --- Pydantic 모델 ---
class TagRequest(BaseModel):
    tag_name: str


class QuestionTypeRequest(BaseModel):
    question_type: str


class PassageMemoRequest(BaseModel):
    memo: str


class AnswerRequest(BaseModel):
    answer: str
    note: Optional[str] = ""


class SeedDataRequest(BaseModel):
    pass


class SingleProviderTestRequest(BaseModel):
    provider: str
    api_key: Optional[str] = ""
    model: Optional[str] = ""
    base_url: Optional[str] = ""


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
    # TTS 엔진 설정 (Edge-TTS 및 ElevenLabs)
    tts_engine: Optional[str] = None
    edge_tts_voice_male: Optional[str] = None
    edge_tts_voice_female: Optional[str] = None
    edge_tts_rate: Optional[str] = None
    elevenlabs_api_key: Optional[str] = None
    elevenlabs_voice_male: Optional[str] = None
    elevenlabs_voice_female: Optional[str] = None
    elevenlabs_model_id: Optional[str] = None


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
    explanation: Optional[str] = "사용자 분석"
    source_type: Optional[str] = "USER"
    user_id: Optional[str] = "default_user"
    ai_model: Optional[str] = None


class BatchSetGrammarAnnotationsRequest(BaseModel):
    annotations: List[Dict[str, Any]] = []
    source_type: Optional[str] = "USER"
    user_id: Optional[str] = "default_user"


class UserGrammarSettingsRequest(BaseModel):
    user_id: Optional[str] = "default_user"
    use_custom_tree: Optional[bool] = False
    custom_tree_json: Optional[str] = None
    custom_mapping_json: Optional[str] = None



def _regenerate_exam_crops(exam_id, grade, year, month, reading_start, reading_end, answers_dict, subtype=None) -> bool:
    """원본 PDF가 있으면 정답 선지 형광펜 하이라이트 크롭 이미지를 재생성하고 경로를 DB에 동기화"""
    if not subtype:
        m_sub = re.search(r"-([AB]형)", exam_id)
        if m_sub:
            subtype = m_sub.group(1)
    search_patterns = [
        os.path.join(UPLOADS_DIR, f"{grade}_{year}_{month:02d}_*.pdf"),
        os.path.join(UPLOADS_DIR, f"{grade}_{year}_{month}_*.pdf"),
        os.path.join(UPLOADS_DIR, f"*{year}*{month:02d}*.pdf"),
        os.path.join(UPLOADS_DIR, f"*{year}*{month}*.pdf"),
        os.path.join(UPLOADS_DIR, f"*{grade}*{year}*.pdf"),
    ]
    pdf_candidates = []
    for pat in search_patterns:
        matched = [p for p in glob.glob(pat) if "_ans_" not in os.path.basename(p) and "_script" not in os.path.basename(p)]
        if subtype:
            sub_key = subtype.replace("형", "")
            sub_matched = [p for p in matched if re.search(rf"[-_\[\s]{sub_key}(?:형)?(?:[-_\]\s]|\.|$)", os.path.basename(p), re.I)]
            if sub_matched:
                pdf_candidates = sub_matched
                break
        if matched and not pdf_candidates:
            pdf_candidates = matched
            break
    if not pdf_candidates:
        return False
    try:
        if (reading_end is None or reading_end == 45) and (2006 <= year <= 2011):
            reading_end = 50
        if (reading_start is None or reading_start == 18) and year == 2013:
            reading_start = 23

        # 스캔본 PDF(텍스트 0자) 감지 시 동명 HWP 원본으로부터 고화질 디지털 PDF 자동 생성
        target_pdf = pdf_candidates[0]
        try:
            test_doc = fitz.open(target_pdf)
            is_empty_pdf = sum(len(p.get_text()) for p in test_doc) < 50
            test_doc.close()
            if is_empty_pdf:
                hwp_pat = os.path.splitext(target_pdf)[0] + ".hwp"
                if not os.path.exists(hwp_pat):
                    hwp_pat = os.path.splitext(target_pdf)[0] + ".hwpx"
                if os.path.exists(hwp_pat):
                    if convert_hwp_to_pdf(hwp_pat, target_pdf):
                        print(f"[Crops] 스캔본 PDF를 HWP 원본({hwp_pat})으로부터 디지털 PDF로 자동 재변환 완료")
        except Exception as scan_err:
            print(f"[Crops] 스캔본 PDF 자동 치환 검사 중 경고: {scan_err}")

        # 정답 사전 보완 (verified_key 및 DB 저장값 결합)
        full_answers = dict(answer_keys.load_answer_key(grade, year, month) or {})
        if answers_dict:
            full_answers.update(answers_dict)
        try:
            with db.get_connection() as conn:
                cur = conn.cursor()
                rows = cur.execute("SELECT q_num, answer_text FROM passages WHERE exam_id = ?", (exam_id,)).fetchall()
                for r in rows:
                    if r["answer_text"] and r["q_num"] not in full_answers:
                        full_answers[r["q_num"]] = r["answer_text"]
        except Exception:
            pass

        # 1. 독해 문항 크롭 생성 (정답 형광펜 포함)
        crop_results = extract_pdf_columns_and_questions(
            pdf_path=target_pdf, grade=grade, year=year, month=month,
            start_q=reading_start, end_q=reading_end, answers_dict=full_answers,
            subtype=subtype
        )

        # 2. 듣기 문항(1~17번) 크롭도 정답 형광펜 주석을 포함하여 함께 재생성
        listening_end = (reading_start - 1) if (reading_start and reading_start > 1) else 17
        try:
            listening_crops = extract_pdf_columns_and_questions(
                pdf_path=target_pdf, grade=grade, year=year, month=month,
                start_q=1, end_q=listening_end, answers_dict=full_answers
            )
            crop_results.update(listening_crops)
        except Exception as l_crop_err:
            print(f"[Crops] {exam_id} 듣기 문항 형광펜 크롭 생성 중 경고: {l_crop_err}")

        # [특수 예외 폴백] 고3 2013년 9월 등 벡터 폰트 외곽선 변환 문서 전용 크롭 연동
        if not crop_results and grade == "고3" and year == 2013 and month == 9:
            from tools.crop_2013_09 import generate_crops_for_exam
            sub = subtype or ("A형" if "-A" in exam_id else "B형")
            if generate_crops_for_exam(exam_id, sub):
                print(f"[Crops] {exam_id} 전용 고정밀 기하 크롭 생성 완료")
                return True

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
        print(f"[Crops] {exam_id} 정답 형광펜 크롭 {len(crop_results)}개(듣기+독해) 재생성 완료")
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
    exam_id: str = "",
    grade: str = "",
    year: Optional[int] = None,
    years: Optional[str] = Query(None),
    month: Optional[int] = None,
    exam_type: str = "",
    question_type: str = "",
    correct_rate_range: str = "",
    tag: str = "",
    area: str = "reading",
    whole_word: bool = False,
    limit: int = 0,
    meta_only: bool = False
):
    """지문 검색 API (2x2 화면용 - 온전한 단어 검색 및 복수 연도, 영역(독해/듣기) 지원, meta_only 초고속 경량 모드 지원)"""
    # 검색어 내 #태그 자동 파싱 (예: "#빈칸" 또는 "climate #빈칸")
    if keyword and "#" in keyword:
        found_tags = re.findall(r"#([^\s#]+)", keyword)
        if found_tags and not tag:
            tag = found_tags[0]
            keyword = re.sub(r"#[^\s#]+", "", keyword).strip()

    years_list: Optional[List[int]] = None
    if years:
        try:
            years_list = [int(y.strip()) for y in years.split(",") if y.strip().isdigit()]
        except Exception:
            years_list = None

    cache_key = f"passages:{keyword}:{exam_id}:{grade}:{year}:{years}:{month}:{exam_type}:{question_type}:{correct_rate_range}:{tag}:{area}:{whole_word}:{limit}:{meta_only}"
    cached_payload = search_cache.get(cache_key)
    if cached_payload is not None:
        return Response(content=cached_payload, media_type="application/json")

    results = db.search_passages(
        keyword=keyword,
        exam_id=exam_id,
        grade=grade,
        year=year,
        years=years_list,
        month=month,
        exam_type=exam_type,
        question_type=question_type,
        correct_rate_range=correct_rate_range,
        tag=tag,
        area=area,
        whole_word=whole_word,
        limit=limit,
        meta_only=meta_only
    )
    payload = fast_json_dumps({"count": len(results), "items": results, "meta_only": meta_only})
    search_cache.set(cache_key, payload)
    return Response(content=payload, media_type="application/json")


@app.get("/api/exams/{exam_id:path}/passages")
async def api_get_exam_passages(exam_id: str):
    """특정 시험의 전체 문항 본문/해설 일괄 조회 (단 28문항 안팎 초고속 온디맨드 로드)"""
    cache_key = f"exam_passages:{exam_id}"
    cached_payload = search_cache.get(cache_key)
    if cached_payload is not None:
        return Response(content=cached_payload, media_type="application/json")

    passages = db.get_exam_passages(exam_id)
    payload = fast_json_dumps({"exam_id": exam_id, "count": len(passages), "items": passages})
    search_cache.set(cache_key, payload)
    return Response(content=payload, media_type="application/json")



@app.get("/api/search/sentences")
async def api_search_sentences(
    keyword: str = "",
    passage_id: str = "",
    grade: str = "",
    year: Optional[int] = None,
    years: Optional[str] = Query(None),
    month: Optional[int] = None,
    exam_type: str = "",
    question_type: str = "",
    correct_rate_range: str = "",
    tag: str = "",
    is_starred: Optional[bool] = None,
    grammar_cat_id: Optional[int] = None,
    grammar_pos: Optional[str] = None,
    area: str = "reading",
    whole_word: bool = False,
    limit: int = 0
):
    """문장 검색 API (1행 테이블 뷰용 - 온전한 단어 검색 및 복수 연도, 영역(독해/듣기) 지원)"""
    # 검색어 내 #태그 자동 파싱
    if keyword and "#" in keyword:
        found_tags = re.findall(r"#([^\s#]+)", keyword)
        if found_tags and not tag:
            tag = found_tags[0]
            keyword = re.sub(r"#[^\s#]+", "", keyword).strip()

    years_list: Optional[List[int]] = None
    if years:
        try:
            years_list = [int(y.strip()) for y in years.split(",") if y.strip().isdigit()]
        except Exception:
            years_list = None

    cache_key = f"sentences:{keyword}:{passage_id}:{grade}:{year}:{years}:{month}:{exam_type}:{question_type}:{correct_rate_range}:{tag}:{is_starred}:{grammar_cat_id}:{grammar_pos}:{area}:{whole_word}:{limit}"
    cached_payload = search_cache.get(cache_key)
    if cached_payload is not None:
        return Response(content=cached_payload, media_type="application/json")

    results = db.search_sentences(
        keyword=keyword,
        passage_id=passage_id,
        grade=grade,
        year=year,
        years=years_list,
        month=month,
        exam_type=exam_type,
        question_type=question_type,
        correct_rate_range=correct_rate_range,
        tag=tag,
        is_starred=is_starred,
        grammar_cat_id=grammar_cat_id,
        grammar_pos=grammar_pos,
        area=area,
        whole_word=whole_word,
        limit=limit
    )
    payload = fast_json_dumps({"count": len(results), "items": results})
    search_cache.set(cache_key, payload)
    return Response(content=payload, media_type="application/json")


# --- 단일 지문 상세 API (2x2 그리드 뷰용) ---
@app.get("/api/passages/{passage_id}")
async def api_get_passage(passage_id: str):
    """특정 지문의 상세 데이터 (HWP 해설, PDF 캡처, txt 본문, 태그, 문제유형, 정답률 및 선지 선택률, 듣기 대본/FELS/오디오)"""
    clean_id = passage_id.strip()
    if not clean_id.startswith("["):
        clean_id = f"[{clean_id}]"

    data = db.get_passage(clean_id)
    if not data:
        raise HTTPException(status_code=404, detail="해당 지문을 찾을 수 없습니다.")
    return data


# --- 듣기 영역 오디오 및 동기화 API ---
@app.post("/api/passages/{passage_id:path}/generate-audio")
async def api_generate_passage_audio(passage_id: str):
    """특정 듣기 문항의 대본을 Edge-TTS 또는 ElevenLabs M/W 듀얼 보이스로 합성하여 MP3 생성"""
    try:
        clean_id = passage_id.strip()
        if not clean_id.startswith("["):
            clean_id = f"[{clean_id}]"
        result = await tts_service.generate_passage_audio(clean_id)
        if not result.get("success"):
            return JSONResponse(status_code=400, content=result)
        return result
    except Exception as e:
        logger.error(f"문항 음성 합성 실패 ({passage_id}): {e}")
        return JSONResponse(
            status_code=400,
            content={"success": False, "message": str(e), "detail": str(e)}
        )


@app.post("/api/exams/{exam_id:path}/generate-listening-audio")
async def api_generate_exam_listening_audio(exam_id: str):
    """시험지의 1~17번 전체 듣기 문항 오디오를 일괄 생성"""
    try:
        clean_id = exam_id.strip()
        if not clean_id.startswith("["):
            clean_id = f"[{clean_id}]"
        result = await tts_service.generate_exam_listening_audio(clean_id)
        return result
    except Exception as e:
        logger.error(f"시험지 전체 음성 합성 실패 ({exam_id}): {e}")
        return JSONResponse(
            status_code=400,
            content={"success": False, "message": str(e), "detail": str(e)}
        )


@app.get("/api/exams/{exam_id}/download-listening-zip")
async def api_download_listening_zip(exam_id: str):
    """시험지의 전체 듣기 MP3 파일들을 ZIP 파일로 묶어서 다운로드"""
    clean_id = exam_id.strip()
    if not clean_id.startswith("["):
        clean_id = f"[{clean_id}]"
    try:
        result = tts_service.create_listening_zip(clean_id)
    except ValueError as e:
        # 듣기 문항이 없거나 생성된 MP3가 하나도 없는 경우
        raise HTTPException(status_code=404, detail=str(e))
    zip_path = os.path.join(tts_service.AUDIO_DIR, result["zip_filename"])
    if not os.path.exists(zip_path):
        raise HTTPException(status_code=404, detail="생성된 듣기 오디오 파일이 없거나 압축 생성에 실패했습니다.")
    safe_name = clean_id.replace("[", "").replace("]", "").replace(" ", "_")
    filename = f"{safe_name}_listening_audio.zip"
    return FileResponse(zip_path, media_type="application/zip", filename=filename)


@app.post("/api/exams/{exam_id}/sync-listening")
async def api_sync_exam_listening(exam_id: str):
    """기존 시험지의 듣기 문항(1~17번) 크롭 이미지 및 대본/FELS 재동기화"""
    clean_id = exam_id.strip()
    if not clean_id.startswith("["):
        clean_id = f"[{clean_id}]"
    count = listening_parser.sync_exam_listening(clean_id)
    return {"success": True, "exam_id": clean_id, "synced_count": count}


# --- 문제 유형 수정 API ---
@app.patch("/api/passages/{passage_id}/question-type")
async def api_update_question_type(passage_id: str, req: QuestionTypeRequest):
    """지문의 문제 유형 변경/저장"""
    clean_id = passage_id.strip()
    if not clean_id.startswith("["):
        clean_id = f"[{clean_id}]"

    success = db.update_passage_question_type(clean_id, req.question_type)
    return {"success": success, "question_type": req.question_type}


# --- 지문 메모(수업/변형 노트) 저장 API ---
@app.put("/api/passages/{passage_id}/memo")
@app.patch("/api/passages/{passage_id}/memo")
async def api_update_passage_memo(passage_id: str, req: PassageMemoRequest):
    """지문의 사용자 메모(수업/변형 노트) 저장"""
    clean_id = passage_id.strip()
    if not clean_id.startswith("["):
        clean_id = f"[{clean_id}]"

    res = db.update_passage_memo(clean_id, req.memo)
    if not res.get("success"):
        raise HTTPException(status_code=404, detail=f"지문 '{clean_id}'를 찾을 수 없거나 갱신하지 못했습니다.")
    return res


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


# --- PDF 문항 크롭 다시 캡처 API ---
@app.post("/api/passages/{passage_id:path}/recapture")
async def api_recapture_passage_pdf(passage_id: str):
    """지문 PDF 크롭 이미지 다시 캡처 (원본 PDF로부터 형광펜 하이라이트 문항 크롭 재생성)"""
    clean_id = passage_id.strip()
    if not clean_id.startswith("["):
        clean_id = f"[{clean_id}]"

    passage = db.get_passage(clean_id)
    if not passage:
        raise HTTPException(status_code=404, detail=f"지문 '{clean_id}'를 찾을 수 없습니다.")
    exam_id = passage["exam_id"]

    with db.get_connection() as conn:
        exam = conn.execute(
            "SELECT grade, year, month, reading_start_q, reading_end_q, subtype FROM exams WHERE id = ?", (exam_id,)
        ).fetchone()
        exam_answers = {int(r["q_num"]): (r["answer_text"] or "") for r in conn.execute(
            "SELECT q_num, answer_text FROM passages WHERE exam_id = ?", (exam_id,))}
    if not exam:
        raise HTTPException(status_code=404, detail=f"시험지 '{exam_id}'를 찾을 수 없습니다.")

    success = _regenerate_exam_crops(
        exam_id, exam["grade"], exam["year"], exam["month"],
        exam["reading_start_q"] or 18, exam["reading_end_q"] or 45, exam_answers,
        subtype=exam["subtype"]
    )

    with db.get_connection() as conn:
        exam_passages = [dict(r) for r in conn.execute(
            "SELECT * FROM passages WHERE exam_id = ? ORDER BY q_num ASC", (exam_id,)
        ).fetchall()]

    updated_passage = db.get_passage(clean_id)
    if not success or not (updated_passage and updated_passage.get("pdf_crop_image")):
        return {
            "success": False,
            "message": "PDF 원본 파일이 없거나 캡처 생성에 실패했습니다. uploads 폴더의 PDF 파일을 확인하세요.",
            "passage": updated_passage,
            "passages": exam_passages
        }

    return {
        "success": True,
        "message": f"{clean_id} PDF 문항 캡처를 성공적으로 다시 생성했습니다.",
        "passage": updated_passage,
        "passages": exam_passages
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
    cfg["tts"] = tts_service.get_tts_config()
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


@app.get("/api/lmstudio/models")
async def api_get_lmstudio_models(base_url: Optional[str] = None):
    """LM Studio 로컬 서버에서 다운로드/로드된 모델 목록 실시간 조회"""
    b_url = base_url or grammar_analyzer.get_lmstudio_base_url()
    models = grammar_analyzer.get_available_lmstudio_models(b_url)
    return {"success": True, "models": models, "total": len(models)}


def describe_non_ascii(value: str) -> str:
    """문자열에 ASCII 외 문자가 있으면 '위치: 문자' 목록을 반환 (없으면 빈 문자열)"""
    found = [f"{i + 1}번째 '{ch}'" for i, ch in enumerate(value) if ord(ch) > 127]
    return ", ".join(found[:5]) + (" 외" if len(found) > 5 else "")


@app.post("/api/settings/ai/test")
async def api_test_single_ai_provider(req: SingleProviderTestRequest):
    """특정 AI Provider 개별 연결 핑 테스트"""
    p = req.provider.strip().lower()
    k = req.api_key.strip() if req.api_key else ""
    m = req.model.strip() if req.model else ""
    b_url = req.base_url.strip() if req.base_url else ""

    if p == "lmstudio":
        if b_url:
            grammar_analyzer.set_lmstudio_base_url(b_url)
        if not k:
            existing_k, _ = grammar_analyzer.get_provider_config(p)
            k = existing_k or "lm-studio"
    else:
        if not k:
            existing_k, existing_m = grammar_analyzer.get_provider_config(p)
            k = existing_k
            if not m:
                m = existing_m

        if not k:
            prov_label = grammar_analyzer.PROVIDER_NAMES.get(p, p)
            return JSONResponse(status_code=400, content={"success": False, "message": f"{prov_label} API Key를 입력해 주세요."})

        # HTTP 헤더(x-api-key 등)는 latin-1 만 허용되므로 ASCII 외 문자가 섞인 키는 전송 전에 차단
        bad = describe_non_ascii(k)
        if bad:
            return JSONResponse(status_code=400, content={"success": False, "message": f"API Key에 허용되지 않는 문자가 있습니다 ({bad}). 콘솔에서 전체 키를 다시 복사해 붙여 주세요 (말줄임표 '…'나 공백이 섞인 잘린 키인지 확인)."})

    if p == "gemini":
        m = grammar_analyzer.resolve_gemini_model(k, m)

    ok, msg, used_model = grammar_analyzer.test_connection(p, k, m, base_url=b_url)
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
                if p_clean == "lmstudio":
                    b_url = (p_data.get("base_url") or "").strip()
                    if b_url:
                        grammar_analyzer.set_lmstudio_base_url(b_url)
                if k:
                    bad = describe_non_ascii(k)
                    if bad:
                        prov_label = grammar_analyzer.PROVIDER_NAMES.get(p_clean, p_clean)
                        return JSONResponse(status_code=400, content={"success": False, "message": f"{prov_label} API Key에 허용되지 않는 문자가 있습니다 ({bad}). 저장하지 않았습니다. 콘솔에서 전체 키를 다시 복사해 주세요."})
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

    # 5. TTS 엔진 및 세부 설정 저장 (Edge-TTS 및 ElevenLabs)
    if req.tts_engine is not None:
        db.set_setting("tts_engine", req.tts_engine.strip())
    if req.edge_tts_voice_male is not None:
        db.set_setting("edge_tts_voice_male", req.edge_tts_voice_male.strip())
    if req.edge_tts_voice_female is not None:
        db.set_setting("edge_tts_voice_female", req.edge_tts_voice_female.strip())
    if req.edge_tts_rate is not None:
        db.set_setting("edge_tts_rate", req.edge_tts_rate.strip())

    # 6. test_now인 경우 첫 번째 활성 프로바이더 연결 테스트
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
        "message": test_msg or "AI 및 TTS 설정이 성공적으로 저장되었습니다."
    }


@app.get("/api/settings/tts/hardware")
async def api_get_tts_hardware():
    """현재 머신의 GPU(CUDA) 및 XTTS 설치 하드웨어 상태 반환"""
    return tts_service.get_hardware_status()


@app.post("/api/settings/tts/preview")
async def api_preview_tts(req: Dict[str, Any] = Body(...)):
    """XTTS-v2 수능 성우 복제 및 Edge-TTS 목소리 샘플 미리듣기 생성"""
    try:
        engine = (req.get("engine") or "xtts").strip()
        gender = (req.get("gender") or "male").strip()
        rate = (req.get("rate") or "+0%").strip()
        preview_url = await tts_service.generate_tts_preview(engine=engine, gender=gender, rate=rate)
        return {"success": True, "audio_url": preview_url}
    except Exception as e:
        logger.error(f"TTS 미리듣기 실패: {e}")
        return JSONResponse(status_code=400, content={"success": False, "message": str(e)})


@app.post("/api/settings/edge-tts/preview")
async def api_preview_edge_tts(req: Dict[str, Any] = Body(...)):
    """Edge-TTS 목소리 샘플 미리듣기 생성 (호환용)"""
    try:
        voice = (req.get("voice") or "en-US-GuyNeural").strip()
        rate = (req.get("rate") or "+0%").strip()
        gender = "female" if "Jenny" in voice or "female" in voice.lower() else "male"
        preview_url = await tts_service.generate_tts_preview(engine="edge-tts", gender=gender, rate=rate)
        return {"success": True, "audio_url": preview_url}
    except Exception as e:
        logger.error(f"Edge-TTS 미리듣기 실패: {e}")
        return JSONResponse(status_code=400, content={"success": False, "message": str(e)})


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
        found = db.search_sentences(sentence_ids=[clean_id])
        target = found[0] if found else None

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
        db.save_grammar_annotations(clean_id, annos, source_type="AI", ai_model="Multi-LLM")
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


@app.get("/api/grammar/categories")
async def api_get_grammar_categories(user_id: str = "default_user"):
    """현재 사용자에게 유효한 어법 범주표 및 커스텀 체계 메타데이터 반환"""
    return db.get_effective_grammar_categories(user_id)


@app.get("/api/grammar/settings")
async def api_get_grammar_settings(user_id: str = "default_user"):
    """사용자 커스텀 어법 체계 설정 조회"""
    return db.get_user_grammar_settings(user_id)


@app.post("/api/grammar/settings")
async def api_save_grammar_settings(req: UserGrammarSettingsRequest):
    """사용자 커스텀 어법 트리 및 매핑 설정 저장"""
    try:
        db.save_user_grammar_settings(
            user_id=req.user_id or "default_user",
            use_custom_tree=1 if req.use_custom_tree else 0,
            custom_tree_json=req.custom_tree_json,
            custom_mapping_json=req.custom_mapping_json
        )
        return {"success": True, "message": "어법 체계 설정이 성공적으로 저장되었습니다."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"어법 체계 저장 실패: {str(e)}")


@app.post("/api/grammar/settings/reset")
async def api_reset_grammar_settings(user_id: str = "default_user"):
    """사용자 커스텀 어법 설정을 기본 243개 표준 체계로 초기화"""
    try:
        db.reset_user_grammar_settings(user_id)
        return {"success": True, "message": "기본 243개 표준 어법 체계로 복원되었습니다."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"어법 체계 초기화 실패: {str(e)}")


@app.post("/api/sentences/{sentence_id}/grammar-annotations")
async def api_add_grammar_annotation(sentence_id: str, req: AddGrammarAnnotationRequest):
    """문장에 수동/사용자 어법 범주 추가"""
    clean_id = sentence_id.strip()
    if not clean_id.startswith("["):
        clean_id = f"[{clean_id}]"

    try:
        data = req.dict()
        db.add_sentence_grammar_annotation(
            clean_id, 
            data, 
            source_type=req.source_type or "USER", 
            user_id=req.user_id or "default_user",
            ai_model=req.ai_model
        )
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
async def api_delete_grammar_annotation(sentence_id: str, identifier: int, source_type: Optional[str] = None):
    """문장의 특정 어법 범주 삭제 (source_type 선택적 필터)"""
    clean_id = sentence_id.strip()
    if not clean_id.startswith("["):
        clean_id = f"[{clean_id}]"

    try:
        db.delete_sentence_grammar_annotation(clean_id, identifier, source_type=source_type)
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
async def api_reset_sentence_grammar(sentence_id: str, source_type: Optional[str] = None):
    """문장의 어법 분석 결과 초기화 (AI 또는 USER 개별 초기화 또는 전체 초기화)"""
    clean_id = sentence_id.strip()
    if not clean_id.startswith("["):
        clean_id = f"[{clean_id}]"

    try:
        db.reset_sentence_grammar(clean_id, source_type=source_type)
        updated = db.get_sentence_grammar_annotations(clean_id)
        return {
            "success": True,
            "sentence_id": clean_id,
            "grammar_analyzed": 1 if updated else 0,
            "annotations": updated
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"어법 분석 초기화 실패: {str(e)}")


@app.post("/api/sentences/{sentence_id}/grammar-annotations/batch")
async def api_batch_set_grammar_annotations(sentence_id: str, req: BatchSetGrammarAnnotationsRequest):
    """문장의 어법 범주 목록을 모달 선택값으로 일괄 저장 (지정된 source_type 항목만 교체)"""
    clean_id = sentence_id.strip()
    if not clean_id.startswith("["):
        clean_id = f"[{clean_id}]"

    try:
        updated = db.set_sentence_grammar_annotations(
            clean_id, 
            req.annotations, 
            source_type=req.source_type or "USER", 
            user_id=req.user_id or "default_user"
        )
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
        # 선택한 문장만 SQL에서 바로 조회 (전체 7만 문장을 읽고 거르던 방식 제거)
        sentences = db.search_sentences(sentence_ids=req.sentence_ids)
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
            db.save_grammar_annotations(s["id"], annos, source_type="AI", ai_model="Multi-LLM")
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

        # 해당 시험지의 문장 전체를 SQL 조건으로 조회 (기존: 최신 1,000문장 중 접두사 필터 → 문장 누락 가능)
        target_sentences = db.search_sentences(exam_id=exam_id)
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
                db.save_grammar_annotations(s["id"], annos, source_type="AI", ai_model="Multi-LLM")
            except Exception as ex:
                print(f"[Background Grammar Analysis Error] {s['id']}: {ex}")
    except Exception as e:
        print(f"[Background Grammar Task Error] {e}")
    finally:
        # 응답이 나간 뒤에 실행되므로 캐시 무효화 미들웨어가 잡지 못한다 → 직접 비운다
        search_cache.clear()
        db.invalidate_exams_cache()


# --- 파일 업로드 및 상호 검증 파이프라인 API ---
@app.post("/api/upload")
async def api_upload_exam(
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
    # 1. 업로드 파일 임시 저장
    pdf_save_path = os.path.join(UPLOADS_DIR, f"{grade}_{year}_{month:02d}_{pdf_file.filename}")
    hwp_save_path = os.path.join(UPLOADS_DIR, f"{grade}_{year}_{month:02d}_{hwp_file.filename}")

    with open(pdf_save_path, "wb") as buffer:
        shutil.copyfileobj(pdf_file.file, buffer)
    with open(hwp_save_path, "wb") as buffer:
        shutil.copyfileobj(hwp_file.file, buffer)

    script_save_path = None
    if script_file and script_file.filename:
        script_save_path = os.path.join(UPLOADS_DIR, f"{grade}_{year}_{month:02d}_script_{script_file.filename}")
        with open(script_save_path, "wb") as buffer:
            shutil.copyfileobj(script_file.file, buffer)

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
        is_ab_period = (year == 2013 or (year == 2012 and month >= 6) or (subtype and "형" in subtype))
        if is_ab_period and reading_start is None:
            effective_reading_start = 23
            effective_reading_end = reading_end if reading_end is not None else 45
            listening_start = 1
            listening_end = 22
        else:
            sample_text = ""
            if pdf_save_path and os.path.exists(pdf_save_path):
                try:
                    tdoc = fitz.open(pdf_save_path)
                    sample_text = "".join(p.get_text() for p in tdoc)
                    tdoc.close()
                except Exception:
                    pass
            if not sample_text and hwp_save_path and os.path.exists(hwp_save_path):
                try:
                    sample_text = get_hwp_text(hwp_save_path)
                except Exception:
                    pass

            detected_start, detected_end = detect_listening_range(sample_text, year=year)
            effective_reading_start = reading_start if reading_start is not None else detected_start
            effective_reading_end = reading_end if reading_end is not None else detected_end
            listening_start = 1
            listening_end = (effective_reading_start - 1) if effective_reading_start > 1 else 17

        db.save_exam({
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
        })

        # 3. 정답 소스 수집
        # (1) 정답표 파일 처리:
        #     - .json 확장자인 경우: Vision AI 호출을 건너뛰고(Bypass), JSON 데이터를 1순위 Ground Truth(uploaded_json)로 채택
        #     - 이미지(.png/.jpg)인 경우: 활성화된 모든 Vision 모델이 독립 판독, 2개 이상 일치한 문항만 검증 정답으로 인정
        uploaded_json_answers = {}
        image_report = None
        if ans_save_path and os.path.exists(ans_save_path):
            if ans_save_path.lower().endswith(".json"):
                try:
                    uploaded_json_answers = answer_keys.parse_answer_json_file(ans_save_path)
                    if uploaded_json_answers:
                        answer_keys.save_uploaded_answer_key(grade, year, month, uploaded_json_answers, ans_file.filename if ans_file else "")
                        print(f"[Upload] 정답 JSON 파일 파싱 및 키 저장 완료 ({len(uploaded_json_answers)}문항)")
                    else:
                        print(f"[Upload] 정답 JSON 파싱 결과 비어있음: {ans_save_path}")
                except Exception as e:
                    print(f"[Upload] 정답 JSON 파싱 실패: {e}")
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
                print(f"[Upload] 정답률 CSV 파싱 실패: {e}")

        # (4) 문항별 정답 확정: 업로드 JSON > 정답률 CSV > 검증 키 파일 > 이미지 모델 합의 > 이미지 단일 모델 > HWP 해설
        #     검증되지 않은 소스로 결정된 문항은 answer_verified=0 으로 기록되고 응답에 경고로 명시된다 (무언 폴백 금지)
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

        # 8. 듣기 영역(1~17번) 자동 크롭 및 스크립트/FELS 추출 동기화
        listening_count = 0
        try:
            listening_count = listening_parser.sync_exam_listening(
                exam_id=exam_id,
                question_pdf_path=pdf_save_path,
                script_pdf_path=script_save_path,
                explanation_hwp_path=exp_save_path or hwp_save_path,
                answers_dict=answers_dict
            )
            print(f"[Upload] {exam_id} 듣기 문항 {listening_count}개 동기화 완료")
        except Exception as l_err:
            print(f"[Upload] 듣기 문항 동기화 중 경고: {l_err}")

        # AI API 키가 설정되어 있는 경우 백그라운드 어법 자동 분석 스케줄링
        _, ai_key, _ = grammar_analyzer.get_ai_config()
        if ai_key:
            background_tasks.add_task(background_auto_analyze_exam_grammar, exam_id)

        report = resolution["report"]
        msg = f"성공적으로 독해 {saved_passages_count}개 문항과 듣기 {listening_count}개 문항을 상호 검증하여 저장했습니다."
        if report["unverified_questions"]:
            msg += f" ⚠ 정답 미검증 {len(report['unverified_questions'])}문항 - 정답표 이미지/정답률 CSV를 확인하세요."
        return {
            "status": "success",
            "exam_id": exam_id,
            "passages_count": saved_passages_count,
            "listening_count": listening_count,
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


@app.get("/api/exams/{exam_id}/raw-files")
async def api_get_exam_raw_files(exam_id: str):
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


@app.get("/api/exams/{exam_id}/download-file")
async def api_download_exam_file(exam_id: str, file_type: str = Query(...)):
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


@app.get("/api/exams/{exam_id}/download-zip")
async def api_download_exam_all_zip(exam_id: str):
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
        cursor.execute("SELECT id, grade, year, month, subtype, reading_start_q, reading_end_q FROM exams WHERE id = ?", (clean_id,))
        exam = cursor.fetchone()

    if not exam:
        raise HTTPException(status_code=404, detail=f"시험지 '{clean_id}'를 찾을 수 없습니다.")

    grade = exam["grade"]
    year = exam["year"]
    month = exam["month"]
    subtype = exam["subtype"]
    reading_start = exam["reading_start_q"] or (23 if year == 2013 else 18)
    reading_end = exam["reading_end_q"] or (50 if 2006 <= year <= 2011 else 45)

    # 2. 파일 저장
    if file_type == "ans":
        save_path = os.path.join(UPLOADS_DIR, f"{grade}_{year}_{month:02d}_ans_{file.filename}")
    else:
        save_path = os.path.join(UPLOADS_DIR, f"{grade}_{year}_{month:02d}_{file.filename}")

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
                answer_keys.save_uploaded_answer_key(grade, year, month, json_answers, file.filename)

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
                            if not re.search(r"^\s*\[\s*정답\s*\]", exp_body):
                                new_exp = f"[정답] {target_ans}\n\n{exp_body}".strip()
                            else:
                                new_exp = re.sub(r"^\s*\[\s*정답\s*\]\s*[①②③④⑤1-5]?", f"[정답] {target_ans}", exp_body)
                            cursor.execute(
                                "UPDATE passages SET answer_text = ?, explanation_text = ?, answer_source = 'uploaded_json', answer_verified = 1 WHERE id = ?",
                                (target_ans, new_exp, p["id"])
                            )
                        elif p["answer_text"]:
                            answers_dict[q_int] = p["answer_text"]
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

            # (3) CSV가 결정적으로 확정한 정답: 정답 JSON(uploaded_json) 출처의 정답은 절대 덮어쓰지 않고 최우선 유지!
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
            # 파일명이 -A.pdf 등 해설 PDF인지 판별
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

                            # 기존에 정답이 비어있으면 HWP 해설에서 추출된 정답 보충
                            if not cur_ans and hwp_ans:
                                update_ans = hwp_ans
                                update_src = "hwp"

                            if new_exp:
                                cursor.execute(
                                    "UPDATE passages SET explanation_text = ?, answer_text = ?, answer_source = ? WHERE id = ?",
                                    (new_exp, update_ans, update_src, p["id"])
                                )
                                updated_count += 1
                    conn.commit()

            # 원본 PDF가 있으면 형광펜 재생성 시도
            pdf_highlighted = False
            try:
                with db.get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT q_num, answer_text FROM passages WHERE exam_id = ?", (clean_id,))
                    rows = cursor.fetchall()
                    answers_dict = {int(r["q_num"]): r["answer_text"] for r in rows if r["answer_text"]}
                pdf_highlighted = _regenerate_exam_crops(clean_id, grade, year, month, reading_start, reading_end, answers_dict, subtype=subtype)
            except Exception as cr_err:
                print(f"[Upload HWP] 크롭 갱신 경고: {cr_err}")

            if not hwp_exps:
                # 파일은 저장됐지만 해설을 하나도 추출하지 못한 경우 → 성공으로 알리면 사용자가 문제를 놓친다
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
            print(f"[Upload HWP] 해설 파싱 실패 ({clean_id}): {e}")
            # 파일 저장 자체는 성공했으므로 HTTP 200을 유지하되, status로 부분 실패를 알린다
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
            print(f"[Upload PDF] 크롭 갱신 경고: {cr_err}")

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
