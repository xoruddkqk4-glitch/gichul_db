"""
tests/test_sentence_hwpx.py: A4 단면 문장 유인물 생성 엔진 단위 테스트
- format_sentence_source: 기출 출처 '[OOOO년 고O O월 OO번]' 정규화 검증
- generate_sentence_handout (개념 설명 포함): 상단 1x1 Row 1 유지, 6문장 주입, 12pt/줄간격 서식 검증
- generate_sentence_handout (개념 설명 미포함): 상단 1x1 Row 1 삭제, 10문장 주입 검증
- list_templates: 기본 A4 문장 유인물 양식 등록 확인
"""

import io
import zipfile
import xml.etree.ElementTree as ET
import pytest

from gichul.services.hwpx_generator import (
    generate_sentence_handout,
    format_sentence_source,
    get_sentence_template_path,
    list_templates,
    DEFAULT_SENTENCE_TEMPLATE,
)

SAMPLE_SENTENCES = [
    {
        "id": f"[고3-2024년-06월-{20+i}번-{i+1}번째 문장]",
        "sentence_text": f"This is an exemplary test sentence {i+1} illustrating syntactic structures in English.",
    }
    for i in range(12)
]


def test_format_sentence_source():
    """기출 식별자 포맷팅 검증"""
    assert format_sentence_source("[고3-2024년-06월-21번-3번째 문장]") == "[2024년 고3 6월 21번]"
    assert format_sentence_source("[고2-2023년-11월-34번-1번째 문장]") == "[2023년 고2 11월 34번]"
    assert format_sentence_source("[고1-2025년-3월-18번]") == "[2025년 고1 3월 18번]"
    assert format_sentence_source("[2022년-09월-고3-33번]") == "[2022년 고3 9월 33번]"


def test_get_sentence_template_path():
    """A4 문장 템플릿 파일 경로 조회 검증"""
    path = get_sentence_template_path()
    assert path.endswith("default_a4_sentence.hwpx")


def test_list_templates_includes_sentence_template():
    """템플릿 목록에 A4 문장 템플릿 포함 여부 검증"""
    templates = list_templates()
    found = [t for t in templates if t["filename"] == DEFAULT_SENTENCE_TEMPLATE]
    assert len(found) == 1
    assert found[0]["name"] == "기본 A4 문장 유인물 양식"
    assert found[0]["is_default"] is True


def test_generate_sentence_handout_with_concept_table():
    """개념 설명 포함 시 6문장 및 상단 Row 1 유지 검증"""
    options = {
        "header_left": "테스트고등학교 영어과",
        "header_center": "2026 1학기 기말고사 대비",
        "header_right": "2학년 3반 이름: 홍길동",
        "main_title": "관계대명사 that vs what 핵심 기출",
        "include_concept_table": True,
    }
    hwpx_bytes = generate_sentence_handout(SAMPLE_SENTENCES, options)
    assert len(hwpx_bytes) > 5000

    with zipfile.ZipFile(io.BytesIO(hwpx_bytes), "r") as zf:
        namelist = zf.namelist()
        assert "Contents/section0.xml" in namelist
        assert "Contents/header.xml" in namelist

        sec_xml = zf.read("Contents/section0.xml").decode("utf-8")
        root = ET.fromstring(sec_xml)

        # 상단 표 검증
        tbl_top = root.find(".//{http://www.hancom.co.kr/hwpml/2011/paragraph}tbl[@id='1195242981']")
        assert tbl_top is not None
        assert tbl_top.get("rowCnt") == "2"
        trs = tbl_top.findall("{http://www.hancom.co.kr/hwpml/2011/paragraph}tr")
        assert len(trs) == 2

        # 머리말 및 제목 텍스트 포함 확인
        assert "테스트고등학교 영어과" in sec_xml
        assert "2026 1학기 기말고사 대비" in sec_xml
        assert "홍길동" in sec_xml
        assert "관계대명사 that vs what 핵심 기출" in sec_xml

        # 예문 표(tbl id=1214106299) 검증 (6문장 주입)
        tbl_example = root.find(".//{http://www.hancom.co.kr/hwpml/2011/paragraph}tbl[@id='1214106299']")
        assert tbl_example is not None
        sublist = tbl_example.find(".//{http://www.hancom.co.kr/hwpml/2011/paragraph}subList")
        assert sublist is not None

        # 6문장의 텍스트가 순차 번호와 함께 모두 포함되었는지 확인
        for i in range(6):
            expected_prefix = format_sentence_source(SAMPLE_SENTENCES[i]["id"])
            assert f"{i+1}. {expected_prefix}" in sec_xml
        # 7번째 문장은 6문장 제한에 따라 1페이지에서 제외되었는지 확인
        seventh_prefix = format_sentence_source(SAMPLE_SENTENCES[6]["id"])
        assert seventh_prefix not in sec_xml


def test_generate_sentence_handout_without_concept_table():
    """개념 설명 미포함 시 10문장 및 상단 Row 1 삭제 검증"""
    options = {
        "header_left": "OO고 영어과",
        "header_center": "수능 완성",
        "header_right": "이름: 김철수",
        "main_title": "분사구문 완전 정복",
        "include_concept_table": False,
    }
    hwpx_bytes = generate_sentence_handout(SAMPLE_SENTENCES, options)
    assert len(hwpx_bytes) > 5000

    with zipfile.ZipFile(io.BytesIO(hwpx_bytes), "r") as zf:
        sec_xml = zf.read("Contents/section0.xml").decode("utf-8")
        root = ET.fromstring(sec_xml)

        # 상단 표 검증: Row 1이 삭제되어 rowCnt="1"이어야 함
        tbl_top = root.find(".//{http://www.hancom.co.kr/hwpml/2011/paragraph}tbl[@id='1195242981']")
        assert tbl_top is not None
        assert tbl_top.get("rowCnt") == "1"
        trs = tbl_top.findall("{http://www.hancom.co.kr/hwpml/2011/paragraph}tr")
        assert len(trs) == 1

        # 10문장의 텍스트가 순차 번호와 함께 모두 포함되었는지 확인
        for i in range(10):
            expected_prefix = format_sentence_source(SAMPLE_SENTENCES[i]["id"])
            assert f"{i+1}. {expected_prefix}" in sec_xml
        # 11번째 문장은 10문장 제한에 따라 제외되었는지 확인
        eleventh_prefix = format_sentence_source(SAMPLE_SENTENCES[10]["id"])
        assert eleventh_prefix not in sec_xml


def test_api_sentence_handout_endpoints():
    """문장 유인물 미리보기 및 생성 API 엔드포인트 검증"""
    from fastapi.testclient import TestClient
    from gichul.app import app
    from gichul import database as db

    client = TestClient(app)

    # DB에 테스트 문장 임시 등록
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO passages (id, exam_id, q_num, passage_text) VALUES ('[고3-2024년-06월-21번]', '[고3-2024년-06월]', 21, 'Sample passage')")
        cursor.execute(
            "INSERT OR REPLACE INTO sentences (id, passage_id, sentence_text, order_index) VALUES (?, ?, ?, ?)",
            ("[고3-2024년-06월-21번-1번째 문장]", "[고3-2024년-06월-21번]", "This is a real test sentence in database.", 1)
        )
        conn.commit()

    # 1. 미리보기 API 테스트
    resp_prev = client.post("/api/handouts/sentence-preview-info", json={
        "sentence_ids": ["[고3-2024년-06월-21번-1번째 문장]"]
    })
    assert resp_prev.status_code == 200
    prev_data = resp_prev.json()
    assert len(prev_data["items"]) == 1
    assert prev_data["items"][0]["source_label"] == "[2024년 고3 6월 21번]"
    assert "This is a real test sentence" in prev_data["items"][0]["sentence_text"]

    # 2. 문장 유인물 생성 API 테스트 (custom_sentence_nums 적용 확인)
    resp_gen = client.post("/api/handouts/generate-sentence", json={
        "sentence_ids": ["[고3-2024년-06월-21번-1번째 문장]"],
        "custom_sentence_nums": {"[고3-2024년-06월-21번-1번째 문장]": "7"},
        "include_concept_table": True,
        "main_title": "테스트 문장 유인물",
        "header_left": "테스트고",
    })
    assert resp_gen.status_code == 200
    assert resp_gen.headers["content-type"] == "application/haansofthwpx"
    assert len(resp_gen.content) > 5000

    with zipfile.ZipFile(io.BytesIO(resp_gen.content), "r") as zf:
        sec_xml = zf.read("Contents/section0.xml").decode("utf-8")
        assert "7. [2024년 고3 6월 21번] This is a real test sentence" in sec_xml


def test_sentence_handout_custom_numbering():
    """사용자 지정 문장 번호(custom_num) 및 순차 번호 주입 검증"""
    sentences = [
        {
            "id": "[고3-2024년-06월-21번-1번째 문장]",
            "sentence_text": "First sentence.",
            "custom_num": "101",
        },
        {
            "id": "[고3-2024년-06월-21번-2번째 문장]",
            "sentence_text": "Second sentence.",
            # custom_num 미지정 시 순차 번호(2) 부여
        },
    ]

    hwpx_bytes = generate_sentence_handout(sentences, {"include_concept_table": True})
    with zipfile.ZipFile(io.BytesIO(hwpx_bytes), "r") as zf:
        sec_xml = zf.read("Contents/section0.xml").decode("utf-8")
        assert "101. [2024년 고3 6월 21번] First sentence." in sec_xml
        assert "2. [2024년 고3 6월 21번] Second sentence." in sec_xml


