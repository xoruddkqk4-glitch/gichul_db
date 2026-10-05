"""
05-gichul_db: 통계 및 지문/문장 검색 라우터 (gichul/routers/search.py)
"""

import re
from typing import Optional, List
from fastapi import APIRouter, Query, Depends, Response, HTTPException

from .. import database as db
from ..text_utils import normalize_bracket_id
from ..core.state import search_cache, fast_json_dumps, get_current_role

router = APIRouter()


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
