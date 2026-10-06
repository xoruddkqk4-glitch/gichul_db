"""
05-gichul_db: FastAPI 로컬 웹 서버 애플리케이션 (app.py)
- 애플리케이션 초기화, 미들웨어 구성 및 라이프사이클 관리
- 6대 도메인별 라우터(search, listening, passages, settings, grammar, exams) 통합
"""

import os
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

os.environ["COQUI_TOS_AGREED"] = "1"

from . import database as db
from . import paths
from .core.state import (
    INGEST_LOCK,
    FastSearchCache,
    _ingest_serialized,
    fast_json_dumps,
    get_current_role,
    search_cache,
)
from .logging_config import get_logger, setup_logging
from .routers import exams, grammar, handouts, listening, passages, reports, search, settings
from .services.ingest import _regenerate_exam_crops, background_auto_analyze_exam_grammar

logger = get_logger("gichul.app")

BASE_DIR = paths.ROOT_DIR
STATIC_DIR = paths.STATIC_DIR
TEMPLATES_DIR = paths.TEMPLATES_DIR
UPLOADS_DIR = paths.UPLOADS_DIR

os.makedirs(UPLOADS_DIR, exist_ok=True)
os.makedirs(STATIC_DIR, exist_ok=True)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """서버 기동 시 1회: 로깅 초기화 및 DB 테이블/마이그레이션 초기화"""
    setup_logging()
    db.init_db()
    yield


app = FastAPI(title="05-gichul_db (기출문제 DB 웹앱)", lifespan=lifespan)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """공통 예외 핸들러: 스택 트레이스를 기록하고 클라이언트에게 일관된 JSON 형식 반환"""
    if isinstance(exc, (HTTPException, StarletteHTTPException)):
        return JSONResponse(
            status_code=exc.status_code,
            content={"success": False, "detail": exc.detail}
        )
    if isinstance(exc, RequestValidationError):
        return JSONResponse(
            status_code=422,
            content={"success": False, "detail": exc.errors()}
        )
    logger.error(f"서버 내부 오류 발생: {request.method} {request.url.path} - {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"success": False, "detail": f"서버 내부 오류: {str(exc)}"}
    )


# GZip 압축 미들웨어 등록 (1KB 이상의 모든 JSON/텍스트 응답을 80~90% 초고속 압축하여 전송 지연 해결)
app.add_middleware(GZipMiddleware, minimum_size=1000)

# 정적 파일 마운트 (/static -> static/)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.middleware("http")
async def no_cache_static_js(request: Request, call_next):
    """ES 모듈 파일(/static/js/*.js)은 import 경로에 ?v= 캐시버스터가 없으므로 항상 재검증(ETag)하도록 강제"""
    response = await call_next(request)
    if request.url.path.startswith("/static/js/"):
        response.headers["Cache-Control"] = "no-cache"
    return response


_WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
# 검색 결과에 영향을 주지 않는 쓰기 경로 (AI 키 저장/테스트, TTS 미리듣기 등)
_CACHE_SAFE_WRITE_PREFIXES = ("/api/settings/", "/api/handouts/")


@app.middleware("http")
async def invalidate_cache_on_write(request: Request, call_next):
    """데이터를 바꾸는 API 요청이 끝나면 검색 캐시와 시험지 통계 캐시를 비운다."""
    response = await call_next(request)
    path = request.url.path
    if (request.method in _WRITE_METHODS
            and path.startswith("/api/")
            and not path.startswith(_CACHE_SAFE_WRITE_PREFIXES)):
        search_cache.clear()
        db.invalidate_exams_cache()
    return response


# --- 웹 페이지 루트 ---
@app.get("/", response_class=HTMLResponse)
def serve_index():
    """메인 웹 UI 페이지 서빙"""
    index_file = os.path.join(TEMPLATES_DIR, "index.html")
    if os.path.exists(index_file):
        with open(index_file, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse("<h1>05-gichul_db 준비 중입니다.</h1>")


# --- 도메인별 라우터 등록 ---
app.include_router(search.router)
app.include_router(listening.router)
app.include_router(passages.router)
app.include_router(settings.router)
app.include_router(grammar.router)
app.include_router(exams.router)
app.include_router(reports.router)
app.include_router(handouts.router)


# --- 하위 호환 re-export ---
__all__ = [
    "app",
    "lifespan",
    "global_exception_handler",
    "search_cache",
    "FastSearchCache",
    "INGEST_LOCK",
    "_ingest_serialized",
    "fast_json_dumps",
    "get_current_role",
    "_regenerate_exam_crops",
    "background_auto_analyze_exam_grammar",
]
