"""
tests/test_hwpx_generator.py: HWPX 유인물 생성 엔진 단위 테스트
- B4 단면 문제지 생성 검증 (사용자 지정 번호, 발문, 본문, 선지, 형광펜)
- B4 단면 해설지 생성 검증 (사용자 지정 번호, 원출처, 좌측하단패널 해설 텍스트)
- ZIP 압축 패키징 검증
- 템플릿 목록 조회 및 파일 무결성 검증
"""

import os
import zipfile
import pytest

from gichul.services.hwpx_generator import (
    generate_question_handout,
    generate_explanation_handout,
    generate_handout_zip,
    list_templates,
)

SAMPLE_ITEMS = [
    {
        "id": "[고2-2026년-09월-18번]",
        "exam_id": "[고2-2026년-09월]",
        "q_num": 18,
        "custom_q_num": "1",
        "question_title": "18. 다음 글의 목적으로 가장 적절한 것은?",
        "passage_text": (
            "18. 다음 글의 목적으로 가장 적절한 것은?\n\n"
            "To whom it may concern,\nI am a teacher at Pendington High School.\n"
            "Sincerely,\nSarah Clayton\n"
            "① 인쇄 부수 확인\n② 견적 비용 문의\n③ 디자인 수정 요청\n④ 출판사 설립 안내\n⑤ 강사 채용 공고"
        ),
        "answer_text": "②",
        "explanation_text": (
            "[정답] ②\n\n"
            "[해석]\n관계자분께, 저는 Pendington 고등학교 교사입니다...\n\n"
            "[해설]\n견적 비용을 문의하는 편지 글이다.\n\n"
            "[어휘]\npromotional 홍보의, brochure 소책자"
        ),
        "correct_rate": 85.5,
    },
    {
        "id": "[고2-2026년-09월-19번]",
        "exam_id": "[고2-2026년-09월]",
        "q_num": 19,
        "custom_q_num": "2",
        "question_title": "19. 다음 글에 드러난 Jonas의 심경 변화로 가장 적절한 것은?",
        "passage_text": (
            "19. 다음 글에 드러난 Jonas의 심경 변화로 가장 적절한 것은?\n\n"
            "Looking out the bus window, Jonas could not stay calm...\n"
            "① hopeful -> disappointed\n② nervous -> delighted\n③ proud -> ashamed\n④ bored -> excited\n⑤ indifferent -> sympathetic"
        ),
        "answer_text": "②",
        "explanation_text": (
            "[정답] ②\n\n"
            "[해석]\n버스 창밖을 내다보며 조나스는 진정할 수 없었다...\n\n"
            "[해설]\n처음에는 긴장했다가 기뻐하는 심경 변화이다.\n\n"
            "[어휘]\ncalm 침착한, delighted 기쁜"
        ),
        "correct_rate": 72.0,
    }
]

def test_list_templates():
    templates = list_templates()
    assert len(templates) >= 1
    assert any("default_b4" in t["filename"] for t in templates)

def test_generate_question_handout():
    options = {
        "header_title": "2026학년도 영어 기출 유인물",
        "header_sub": "2학년 / 영어과",
        "footer_text": "OO고등학교 영어과",
        "highlight_answer": True,
    }
    hwpx_bytes = generate_question_handout(SAMPLE_ITEMS, options)
    assert len(hwpx_bytes) > 2000

    # HWPX 내부 XML 무결성 확인
    import io
    with zipfile.ZipFile(io.BytesIO(hwpx_bytes), "r") as zf:
        namelist = zf.namelist()
        assert "Contents/section0.xml" in namelist
        assert "Contents/header.xml" in namelist
        sec0 = zf.read("Contents/section0.xml").decode("utf-8")
        # 사용자 지정 번호 '1. ' 및 '2. ' 확인
        assert "1. 다음 글의 목적으로" in sec0
        assert "2. 다음 글에 드러난" in sec0
        # 형광펜 마크 확인
        assert "markPenBegin" in sec0 or "shadeColor" in sec0

def test_generate_explanation_handout():
    options = {
        "header_title": "2026학년도 영어 기출 정답 및 해설",
        "footer_text": "OO고등학교 영어과",
    }
    hwpx_bytes = generate_explanation_handout(SAMPLE_ITEMS, options)
    assert len(hwpx_bytes) > 2000

    import io
    with zipfile.ZipFile(io.BytesIO(hwpx_bytes), "r") as zf:
        sec0 = zf.read("Contents/section0.xml").decode("utf-8")
        # 1행 4열 출처 표 각 셀 주입 확인 (년도, 학년, 월, 번호)
        assert "2026년" in sec0
        assert "고2" in sec0
        assert "18번" in sec0
        assert "19번" in sec0
        # 좌측하단패널 해설 텍스트 및 정답 포함 확인
        assert "[정답] ②" in sec0
        assert "소책자" in sec0

def test_generate_handout_zip():
    zip_bytes = generate_handout_zip(SAMPLE_ITEMS)
    assert len(zip_bytes) > 4000

    import io
    with zipfile.ZipFile(io.BytesIO(zip_bytes), "r") as zf:
        names = zf.namelist()
        assert "문제지_B4_유인물.hwpx" in names
        assert "해설지_B4_유인물.hwpx" in names


def test_api_handouts_endpoints():
    from fastapi.testclient import TestClient
    from gichul.app import app
    client = TestClient(app)

    # 1. 템플릿 목록 조회 API
    res = client.get("/api/handouts/templates")
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert len(data["templates"]) >= 1

    # 2. 유인물 생성 API (DB에 실제 존재하는 18번 문항)
    res_gen = client.post("/api/handouts/generate", json={
        "handout_type": "question",
        "passage_ids": ["[고2-2026년-09월-18번]"],
        "custom_q_nums": {"[고2-2026년-09월-18번]": "5"},
        "header_title": "테스트 모의고사",
        "highlight_answer": True,
    })
    assert res_gen.status_code == 200
    assert "application/haansofthwpx" in res_gen.headers.get("content-type", "")
    assert len(res_gen.content) > 1000

    # 3. 해설지 생성 API
    res_exp = client.post("/api/handouts/generate", json={
        "handout_type": "explanation",
        "passage_ids": ["[고2-2026년-09월-18번]"],
        "custom_q_nums": {"[고2-2026년-09월-18번]": "5"},
        "header_title": "테스트 해설지",
    })
    assert res_exp.status_code == 200
    assert len(res_exp.content) > 1000

    # 4. ZIP 패키지 생성 API
    res_zip = client.post("/api/handouts/generate", json={
        "handout_type": "both_zip",
        "passage_ids": ["[고2-2026년-09월-18번]"],
        "custom_q_nums": {"[고2-2026년-09월-18번]": "5"},
    })
    assert res_zip.status_code == 200
    assert "application/zip" in res_zip.headers.get("content-type", "")
