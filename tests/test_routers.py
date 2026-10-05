"""
라우터 모듈 분리 및 등록 검증 테스트 (tests/test_routers.py)
"""

import pytest
from fastapi.testclient import TestClient

from gichul.app import (
    INGEST_LOCK,
    FastSearchCache,
    _ingest_serialized,
    _regenerate_exam_crops,
    app,
    background_auto_analyze_exam_grammar,
    fast_json_dumps,
    get_current_role,
    search_cache,
)
from gichul.routers import (
    exams,
    grammar,
    listening,
    passages,
    search,
    settings,
)


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


def test_app_reexports():
    """gichul.app의 하위 호환 re-export 심볼 확인"""
    assert search_cache is not None
    assert isinstance(search_cache, FastSearchCache)
    assert INGEST_LOCK is not None
    assert callable(_ingest_serialized)
    assert callable(fast_json_dumps)
    assert callable(get_current_role)
    assert callable(_regenerate_exam_crops)
    assert callable(background_auto_analyze_exam_grammar)


def test_router_modules_exist():
    """6개 도메인 라우터 모듈 및 라우터 인스턴스 존재 확인"""
    for module in [search, listening, passages, settings, grammar, exams]:
        assert hasattr(module, "router")


def test_all_routes_registered():
    """FastAPI 앱에 56개 엔드포인트(정적 마운트 및 문서 포함)가 빠짐없이 등록되었는지 확인"""
    registered_paths = set()
    for r in app.routes:
        if hasattr(r, "path") and r.path is not None:
            registered_paths.add(r.path)
        elif hasattr(r, "original_router"):
            for sub in r.original_router.routes:
                registered_paths.add(sub.path)

    expected_endpoints = {
        "/",
        "/static",
        "/api/stats",
        "/api/search/passages",
        "/api/exams/{exam_id:path}/passages",
        "/api/search/sentences",
        "/api/passages/{passage_id}",
        "/api/tts/progress/{job_id}",
        "/api/passages/{passage_id:path}/generate-audio",
        "/api/exams/{exam_id:path}/generate-listening-audio",
        "/api/exams/{exam_id}/download-listening-zip",
        "/api/exams/{exam_id}/sync-listening",
        "/api/passages/{passage_id}/question-type",
        "/api/passages/{passage_id}/memo",
        "/api/passages/{passage_id}/answer",
        "/api/passages/{passage_id:path}/recapture",
        "/api/passages/{passage_id}/tags",
        "/api/passages/{passage_id}/tags/{tag_name}",
        "/api/sentences/{sentence_id}/tags",
        "/api/sentences/{sentence_id}/tags/{tag_name}",
        "/api/settings/ai",
        "/api/openrouter/top-models",
        "/api/openrouter/models",
        "/api/lmstudio/models",
        "/api/settings/ai/test",
        "/api/settings/tts-engine",
        "/api/settings/tts/hardware",
        "/api/settings/tts/preview",
        "/api/settings/edge-tts/preview",
        "/api/sentences/{sentence_id}/star",
        "/api/sentences/{sentence_id}/analyze-grammar",
        "/api/grammar/categories",
        "/api/grammar/settings",
        "/api/grammar/settings/reset",
        "/api/sentences/{sentence_id}/grammar-annotations",
        "/api/sentences/{sentence_id}/grammar-annotations/{identifier}",
        "/api/sentences/{sentence_id}/grammar",
        "/api/sentences/{sentence_id}/grammar-annotations/batch",
        "/api/sentences/batch-analyze-grammar",
        "/api/upload",
        "/api/exams",
        "/api/exams/{exam_id}",
        "/api/exams/{exam_id}/raw-files",
        "/api/exams/{exam_id}/download-file",
        "/api/exams/{exam_id}/download-zip",
        "/api/exams/{exam_id}/upload-file",
        "/api/exams/selective-delete",
        "/api/exams/batch-delete",
    }
    for ep in expected_endpoints:
        assert ep in registered_paths, f"Missing endpoint: {ep}"


def test_core_get_endpoints(client):
    """핵심 GET 엔드포인트 정상 응답 검증"""
    res_root = client.get("/")
    assert res_root.status_code == 200

    res_stats = client.get("/api/stats")
    assert res_stats.status_code == 200
    assert "exams" in res_stats.json()

    res_search = client.get("/api/search/passages?keyword=test&limit=1")
    assert res_search.status_code == 200
    assert "items" in res_search.json()

    res_grammar_cat = client.get("/api/grammar/categories")
    assert res_grammar_cat.status_code == 200

    res_settings_ai = client.get("/api/settings/ai")
    assert res_settings_ai.status_code == 200

    res_exams = client.get("/api/exams")
    assert res_exams.status_code == 200
    assert res_exams.json().get("status") == "success"
