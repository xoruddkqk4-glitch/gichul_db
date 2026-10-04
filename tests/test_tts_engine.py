"""tests/test_tts_engine.py: TTS 엔진 인라인 전환 API 단위 테스트"""
import pytest
from starlette.testclient import TestClient

from app import app
import database as db


@pytest.fixture
def client():
    return TestClient(app)


def test_set_tts_engine_success(client):
    # XTTS 설정 테스트
    res = client.post("/api/settings/tts-engine", json={"engine": "xtts"})
    assert res.status_code == 200
    assert res.json() == {"success": True, "engine": "xtts"}
    assert db.get_setting("tts_engine") == "xtts"

    # Edge-TTS 설정 테스트
    res = client.post("/api/settings/tts-engine", json={"engine": "edge-tts"})
    assert res.status_code == 200
    assert res.json() == {"success": True, "engine": "edge-tts"}
    assert db.get_setting("tts_engine") == "edge-tts"

    # 대소문자 무관 및 공백 제거 확인
    res = client.post("/api/settings/tts-engine", json={"engine": "  XTTS  "})
    assert res.status_code == 200
    assert res.json()["engine"] == "xtts"
    assert db.get_setting("tts_engine") == "xtts"


def test_set_tts_engine_invalid(client):
    # 잘못된 엔진 요청 시 400 에러
    res = client.post("/api/settings/tts-engine", json={"engine": "invalid_engine"})
    assert res.status_code == 400
    assert res.json()["success"] is False
    assert "지원하지 않는 TTS 엔진" in res.json()["message"]


def test_get_ai_settings_reflects_engine(client):
    client.post("/api/settings/tts-engine", json={"engine": "edge-tts"})
    res = client.get("/api/settings/ai")
    assert res.status_code == 200
    data = res.json()
    assert data.get("tts", {}).get("engine") == "edge-tts"

    # 기본값인 xtts로 복원
    client.post("/api/settings/tts-engine", json={"engine": "xtts"})
    res2 = client.get("/api/settings/ai")
    assert res2.status_code == 200
    assert res2.json().get("tts", {}).get("engine") == "xtts"
