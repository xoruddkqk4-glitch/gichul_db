"""
05-gichul_db: 통계 및 지문/문장 검색 라우터 (gichul/routers/search.py)
"""

import re
from typing import Optional, List, Dict, Any, Union
from fastapi import APIRouter, Query, Depends, Response, HTTPException
from pydantic import BaseModel, Field

from .. import database as db
from ..text_utils import normalize_bracket_id
from ..core.state import search_cache, fast_json_dumps, get_current_role
from ..services import similarity_search

router = APIRouter()


class SimilarExtractRequest(BaseModel):
    text: str = Field(..., description="붙여 넣은 단락 텍스트")
    area: str = Field(default="reading", description="reading | listening")
    filter_common_ngrams: bool = True
    max_df_3gram: int = 30
    max_df_4gram: int = 10


class SimilarSearchRequest(BaseModel):
    text: str = Field(default="", description="붙여 넣은 단락 텍스트")
    preset: str = Field(default="balanced", description="balanced | near_duplicate | proper_noun | phrase_combo | topic_broad | ngram_3 | ngram_4 | ngram_3_4")
    weights: Optional[Dict[str, float]] = None
    selected_proper_nouns: Optional[List[str]] = None
    selected_phrases: Optional[List[str]] = None
    selected_keywords: Optional[List[str]] = None
    selected_ngrams: Optional[List[str]] = None
    required_terms: Optional[List[str]] = None
    required_ngrams: Optional[List[str]] = None
    excluded_terms: Optional[List[str]] = None
    custom_terms: Optional[List[str]] = None
    use_ai_expansion: bool = False
    ngram_mode: Optional[str] = None
    min_ngram_hits: int = 1
    filter_common_ngrams: bool = True
    max_df_3gram: int = 30
    max_df_4gram: int = 10
    allow_gap: int = 0
    min_score: float = 0.05
    top_k: int = 30
    area: str = "reading"
    grade: str = ""
    year: Optional[int] = None
    years: Optional[Union[List[int], str]] = None
    month: Optional[int] = None
    exam_type: str = ""
    question_type: str = ""
    correct_rate_range: str = ""
    tag: str = ""


@router.post("/api/search/similar/extract")
def api_extract_similar_features(req: SimilarExtractRequest):
    """붙여 넣은 단락에서 고유명사, 표현 조합, 핵심어, 연속 3·4단어를 미리 추출한다."""
    if not (req.text or "").strip() or len(req.text.strip()) < 5:
        raise HTTPException(status_code=400, detail="유사 검색을 위해 최소 5자 이상의 영어 텍스트를 입력하세요.")
    return similarity_search.extract_paragraph_features(
        text=req.text,
        area=req.area,
        filter_common_ngrams=req.filter_common_ngrams,
        max_df_3gram=req.max_df_3gram,
        max_df_4gram=req.max_df_4gram,
    )


@router.post("/api/search/similar")
def api_search_similar_passages(
    req: SimilarSearchRequest,
    user_role: str = Depends(get_current_role),
):
    """단락 텍스트 기반 다중 기준 + 연속 3·4단어 유사 지문 검색 API"""
    has_text = bool((req.text or "").strip())
    has_custom = bool(req.custom_terms and any(t.strip() for t in req.custom_terms))
    if not has_text and not has_custom:
        raise HTTPException(status_code=400, detail="검색할 단락 텍스트 또는 검색어를 입력하세요.")

    years_list: Optional[List[int]] = None
    if isinstance(req.years, list):
        years_list = [int(y) for y in req.years if str(y).isdigit()]
    elif isinstance(req.years, str) and req.years.strip():
        years_list = [int(y.strip()) for y in req.years.split(",") if y.strip().isdigit()]

    result = similarity_search.search_similar_passages(
        text=req.text,
        preset=req.preset,
        weights=req.weights,
        selected_proper_nouns=req.selected_proper_nouns,
        selected_phrases=req.selected_phrases,
        selected_keywords=req.selected_keywords,
        selected_ngrams=req.selected_ngrams,
        required_terms=req.required_terms,
        required_ngrams=req.required_ngrams,
        excluded_terms=req.excluded_terms,
        custom_terms=req.custom_terms,
        use_ai_expansion=req.use_ai_expansion,
        ngram_mode=req.ngram_mode,
        min_ngram_hits=req.min_ngram_hits,
        filter_common_ngrams=req.filter_common_ngrams,
        max_df_3gram=req.max_df_3gram,
        max_df_4gram=req.max_df_4gram,
        allow_gap=req.allow_gap,
        min_score=req.min_score,
        top_k=req.top_k,
        area=req.area,
        grade=req.grade,
        year=req.year,
        years=years_list,
        month=req.month,
        exam_type=req.exam_type,
        question_type=req.question_type,
        correct_rate_range=req.correct_rate_range,
        tag=req.tag,
        user_role=user_role,
    )
    return Response(content=fast_json_dumps(result), media_type="application/json")


@router.get("/api/stats")
def api_stats():
    """DB 통계 반환"""
    return db.get_db_stats()


@router.get("/api/search/passages")
def api_search_passages(
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
    meta_only: bool = False,
    user_role: str = Depends(get_current_role)
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

    # 등급별로 응답이 다르므로 캐시 키에 등급을 넣는다
    cache_key = f"passages:{user_role}:{keyword}:{exam_id}:{grade}:{year}:{years}:{month}:{exam_type}:{question_type}:{correct_rate_range}:{tag}:{area}:{whole_word}:{limit}:{meta_only}"
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
        meta_only=meta_only,
        user_role=user_role
    )
    payload = fast_json_dumps({"count": len(results), "items": results, "meta_only": meta_only})
    search_cache.set(cache_key, payload)
    return Response(content=payload, media_type="application/json")


@router.get("/api/exams/{exam_id:path}/passages")
def api_get_exam_passages(exam_id: str, user_role: str = Depends(get_current_role)):
    """특정 시험의 전체 문항 본문/해설 일괄 조회 (단 28문항 안팎 초고속 온디맨드 로드)"""
    cache_key = f"exam_passages:{user_role}:{exam_id}"
    cached_payload = search_cache.get(cache_key)
    if cached_payload is not None:
        return Response(content=cached_payload, media_type="application/json")

    passages = db.get_exam_passages(exam_id, user_role=user_role)
    payload = fast_json_dumps({"exam_id": exam_id, "count": len(passages), "items": passages})
    search_cache.set(cache_key, payload)
    return Response(content=payload, media_type="application/json")


@router.get("/api/search/sentences")
def api_search_sentences(
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
    limit: int = 0,
    user_role: str = Depends(get_current_role)
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

    cache_key = f"sentences:{user_role}:{keyword}:{passage_id}:{grade}:{year}:{years}:{month}:{exam_type}:{question_type}:{correct_rate_range}:{tag}:{is_starred}:{grammar_cat_id}:{grammar_pos}:{area}:{whole_word}:{limit}"
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
        limit=limit,
        user_role=user_role
    )
    payload = fast_json_dumps({"count": len(results), "items": results})
    search_cache.set(cache_key, payload)
    return Response(content=payload, media_type="application/json")


@router.get("/api/passages/{passage_id}")
def api_get_passage(passage_id: str, user_role: str = Depends(get_current_role)):
    """특정 지문의 상세 데이터 (HWP 해설, PDF 캡처, txt 본문, 태그, 문제유형, 정답률 및 선지 선택률, 듣기 대본/FELS/오디오)"""
    clean_id = normalize_bracket_id(passage_id)

    data = db.get_passage(clean_id, user_role=user_role)
    if not data:
        raise HTTPException(status_code=404, detail="해당 지문을 찾을 수 없습니다.")
    return data
