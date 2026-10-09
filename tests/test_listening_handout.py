"""
05-gichul_db: 교사용 B4 세로 듣기 유인물 HWPX 생성 및 API 회귀 검증 테스트 (tests/test_listening_handout.py)
"""

import io
import zipfile
import xml.etree.ElementTree as ET
import pytest
from fastapi.testclient import TestClient

from gichul.app import app
from gichul import database as db
from gichul.services.hwpx_generator import (
    generate_listening_question_handout,
    generate_listening_explanation_handout,
    generate_listening_handout_zip,
    _prepare_listening_item_data,
    NS_HP,
)


@pytest.fixture
def sample_listening_item():
    return {
        "id": "[고3-2026년-09월-01번]",
        "question_title": "1. 대화를 듣고, 남자의 마지막 말에 대한 여자의 응답으로 가장 적절한 것을 고르시오.",
        "question_type": "짧은 대화 응답",
        "passage_text": "M: Hey, Jane. Are you ready for the game?\nW: Almost, I just need to find my racket.\n① I agree.\n② Not yet.\n③ Sounds good.\n④ Here it is.\n⑤ Never mind.",
        "script_text": "M: Hey, Jane. Are you ready for the game?\nW: Almost, I just need to find my racket.",
        "fels_text": "M: Hey, Jane. Are you ready for the game?\nW: Almost, I just need to find my racket.",
        "explanation_text": "[해석]\n남: 안녕, 제인. 경기 준비 다 됐어?\n여: 거의 다 됐어, 내 라켓만 찾으면 돼.\n\n[정답] ②",
        "answer_text": "2",
        "custom_q_num": "1",
    }


def test_prepare_listening_item_data(sample_listening_item):
    data = _prepare_listening_item_data(sample_listening_item, custom_q_num="5")
    assert data["id"] == "[고3-2026년-09월-01번]"
    assert data["question_title"].startswith("대화를 듣고")
    assert "5. 대화를 듣고" in data["question_text"]
    assert "① I agree." in data["question_text"]
    assert "② Not yet." in data["question_text"]
    assert len(data["fels_blank"]) > 0
    assert "남: 안녕, 제인" in data["korean_translation"]
    assert data["answer_display"] == "②"


def test_listening_question_handout_generation(sample_listening_item):
    items = [sample_listening_item, dict(sample_listening_item, id="[고3-2026년-09월-02번]", custom_q_num="2")]
    options = {
        "header_left": "테스트고등학교",
        "header_center": "영어듣기평가 문제지",
        "header_right": "1학년 1반",
    }
    q_bytes = generate_listening_question_handout(items, options)
    assert len(q_bytes) > 5000

    # HWPX ZIP 및 XML 무결성 검증
    with zipfile.ZipFile(io.BytesIO(q_bytes), "r") as zf:
        assert "Contents/section0.xml" in zf.namelist()
        sec0 = ET.fromstring(zf.read("Contents/section0.xml"))
        # 머리말 텍스트 주입 확인
        tbl0 = sec0.find(f".//{{{NS_HP}}}tbl[@id='1315644029']")
        assert tbl0 is not None
        all_text = "".join(tbl0.itertext())
        assert "영어듣기평가 문제지" in all_text


def test_listening_explanation_handout_generation(sample_listening_item):
    items = [sample_listening_item]
    options = {
        "header_left": "테스트고등학교",
        "header_center": "영어듣기평가 해설지",
        "header_right": "교사용",
    }
    e_bytes = generate_listening_explanation_handout(items, options)
    assert len(e_bytes) > 5000

    with zipfile.ZipFile(io.BytesIO(e_bytes), "r") as zf:
        assert "Contents/section0.xml" in zf.namelist()
        sec0 = ET.fromstring(zf.read("Contents/section0.xml"))
        tbl1 = sec0.find(f".//{{{NS_HP}}}tbl[@id='1216160613']")
        assert tbl1 is not None
        all_text = "".join(tbl1.itertext())
        assert "[정답]" in all_text
        assert "남: 안녕, 제인" in all_text


def test_listening_handout_zip_generation(sample_listening_item):
    items = [sample_listening_item]
    z_bytes = generate_listening_handout_zip(items, {})
    assert len(z_bytes) > 10000
    with zipfile.ZipFile(io.BytesIO(z_bytes), "r") as zf:
        names = zf.namelist()
        assert any(n.endswith(".hwpx") and "문제" in n for n in names)
        assert any(n.endswith(".hwpx") and "해설" in n for n in names)


def test_listening_endpoints():
    client = TestClient(app)
    # 1. Preview
    res_prev = client.post("/api/handouts/listening/preview-info", json={"passage_ids": []})
    assert res_prev.status_code == 200
    assert res_prev.json()["items"] == []

    # 2. Download 400 when empty
    res_down = client.post("/api/handouts/listening/download", json={"passage_ids": []})
    assert res_down.status_code == 400


def test_listening_dynamic_scaling_for_long_items(sample_listening_item):
    # 장문 복합 문항 2개 페어 (대본이 30줄 이상)
    long_script = "\n".join([f"M{i}: This is a long dialogue line with lots of details to fill in blanks." for i in range(1, 20)])
    item1 = dict(sample_listening_item, id="[고3-2026년-09월-13번]", fels_text=long_script, custom_q_num="13")
    item2 = dict(sample_listening_item, id="[고3-2026년-09월-14번]", fels_text=long_script, custom_q_num="14")
    
    q_bytes = generate_listening_question_handout([item1, item2], {})
    with zipfile.ZipFile(io.BytesIO(q_bytes), "r") as zf:
        sec0 = ET.fromstring(zf.read("Contents/section0.xml"))
        tbl1 = sec0.find(f".//{{{NS_HP}}}tbl[@id='1216160613']")
        assert tbl1 is not None
        # 1페이지 내에 Row 0과 Row 7 문단이 105 또는 106 컴팩트 스타일로 축소되었는지 검증
        p_list = tbl1.findall(f".//{{{NS_HP}}}p")
        styles = {p.get("paraPrIDRef") for p in p_list if p.get("paraPrIDRef") in ("104", "105", "106")}
        assert len(styles) > 0
        assert any(s in ("105", "106") for s in styles)


def test_listening_classroom_endpoints(sample_listening_item):
    client = TestClient(app)

    # 1. Classroom data endpoint
    req_body = {
        "items": [sample_listening_item],
        "project_title": "테스트 고등학교 듣기 수업"
    }
    res = client.post("/api/handouts/listening/classroom-data", json=req_body)
    assert res.status_code == 200
    data = res.json()
    assert data["project_title"] == "테스트 고등학교 듣기 수업"
    assert data["total_questions"] == 1
    assert len(data["questions"]) == 1
    q0 = data["questions"][0]
    assert len(q0["sentences"]) >= 2
    assert "speaker" in q0["sentences"][0]
    assert "clean_text" in q0["sentences"][0]
    assert "fels_blank_text" in q0["sentences"][0]

    # 2. Sentence audio endpoint
    res_audio = client.get(
        "/api/handouts/listening/sentence-audio",
        params={"text": "Hello, how are you today?", "speaker": "W", "speed": 1.0}
    )
    assert res_audio.status_code == 200
    assert res_audio.headers["content-type"] == "audio/mpeg"
    assert len(res_audio.content) > 100

