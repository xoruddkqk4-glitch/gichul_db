"""tests/test_tts_engine.py: TTS 엔진 인라인 전환 API 단위 테스트"""
import pytest
from starlette.testclient import TestClient

from gichul.app import app
from gichul import database as db


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


def test_chime_bell_pcm_generation():
    """듣기 평가 시작/종료용 청아한 차임벨 PCM 생성 단위 테스트"""
    from gichul.tts_service import generate_chime_bell_pcm, get_or_create_chime_bell_pcm
    pcm = generate_chime_bell_pcm(24000)
    assert len(pcm) == 96000  # 2.0초 * 24000 * 2바이트
    cached_pcm = get_or_create_chime_bell_pcm(24000)
    assert len(cached_pcm) == 96000


def test_is_two_questions_passage():
    """1지문 2문항 판별 로직 단위 테스트"""
    from gichul.tts_service import is_two_questions_passage
    assert is_two_questions_passage({"q_num": 16, "question_type": "1담화 2문항"}) is True
    assert is_two_questions_passage({"q_num": 17}) is True
    assert is_two_questions_passage({"id": "[고3-2025년-09월-16번]"}) is True
    assert is_two_questions_passage({"q_num": 22}) is True
    assert is_two_questions_passage({"q_num": 1, "question_type": "목적"}) is False
    assert is_two_questions_passage({"id": "[고1-2024년-03월-05번]"}) is False


def test_build_listening_mp3_timings():
    """종소리 앞뒤 삽입, 8초 무음, 1지문 2문항 반복 빌더 단위 테스트"""
    from gichul.tts_service import build_listening_mp3
    # 0.5초 더미 발화 턴 2개
    turn1 = b"\x10\x00" * 12000
    turn2 = b"\x20\x00" * 12000

    # 1지문 1문항: 앞뒤 종소리 + 마지막 8초 무음
    mp3_single = build_listening_mp3([turn1, turn2], is_two_questions=False, include_chimes=True)
    assert len(mp3_single) > 0

    # 1지문 2문항: 맨앞 종소리 + 1회차 + 반복 간 8초 silent + 2회차 + 마지막 8초 silent + 맨뒤 종소리
    mp3_two = build_listening_mp3([turn1, turn2], is_two_questions=True, include_chimes=True)
    assert len(mp3_two) > len(mp3_single)
