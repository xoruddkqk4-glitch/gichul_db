"""
tests/test_validator.py: validator.py 및 교차 검증 수치 단위 테스트 (로드맵 4-C)
- normalize_for_comparison 텍스트 정규화
- calculate_similarity 문자열 유사도 계산
- cross_validate_and_merge:
  1) HWP/PDF 완전 일치 및 정상 (ratio >= 0.9)
  2) HWP/PDF 불일치 (ratio < 0.9) 시 '⚠ 검토 필요' 경고 표기
  3) HWP 누락 시 ratio=None, '비교 불가' 표기
  4) PDF 누락 시 ratio=None, '비교 불가' 표기
  5) 양쪽 모두 본문 누락 시 ratio=None, '비교 불가' 표기
  6) SQLite DB 저장/조회 시 validation_ratio=None 무결성 검증
"""

import pytest
from gichul.validator import calculate_similarity, cross_validate_and_merge, normalize_for_comparison


# ---------- normalize_for_comparison ----------

def test_normalize_for_comparison():
    assert normalize_for_comparison("") == ""
    assert normalize_for_comparison("Hello   \n\t  World") == "Hello World"
    # 유니코드 대시 및 인용부호 통일
    assert normalize_for_comparison("state\u2013of\u2014the\u2010art") == "state-of-the-art"
    assert normalize_for_comparison("\u201cquoted\u201d and \u2018single\u2019") == '"quoted" and \'single\''


# ---------- calculate_similarity ----------

def test_calculate_similarity_identical():
    text = "The quick brown fox jumps over the lazy dog."
    assert calculate_similarity(text, text) == 1.0


def test_calculate_similarity_with_formatting_differences():
    t1 = "“Artificial Intelligence” \u2014 a transformative   technology."
    t2 = '"Artificial Intelligence" - a transformative technology.'
    assert calculate_similarity(t1, t2) == 1.0


def test_calculate_similarity_empty():
    assert calculate_similarity("", "") == 1.0
    assert calculate_similarity("some text", "") == 0.0
    assert calculate_similarity("", "some text") == 0.0


def test_calculate_similarity_different():
    t1 = "Science is the systematic study of the physical world."
    t2 = "Art is the expression or application of human creative skill."
    sim = calculate_similarity(t1, t2)
    assert 0.0 < sim < 0.5


# ---------- cross_validate_and_merge (로드맵 4-C) ----------

def test_cross_validate_and_merge_high_match():
    """HWP와 PDF 본문이 모두 존재하고 일치율 90% 이상인 경우"""
    body = "In modern science, observation is an active engagement with the world."
    hwp_data = {
        21: {
            "question_title": "21. 다음 글의 요지로 가장 적절한 것은?",
            "passage_body": body,
            "passage_text": body,
            "question_type": "함축의미",
        }
    }
    pdf_data = {
        21: {
            "question_title": "21. 다음 글의 요지로 가장 적절한 것은?",
            "passage_body": body,
            "passage_text": body,
            "pdf_crop_image": "/static/captures/test_21.png",
        }
    }
    explanations = {
        21: {"answer": "③", "explanation": "[정답] ③\n해설입니다."}
    }

    results = cross_validate_and_merge(hwp_data, pdf_data, explanations, "고3", 2024, 6)
    assert len(results) == 1
    p = results[0]["passage_data"]

    assert p["validation_ratio"] == 1.0
    assert "일치율: 100.0%" in p["remarks"]
    assert "검토 필요" not in p["remarks"]
    assert p["answer_text"] == "③"


def test_cross_validate_and_merge_low_match_warns():
    """HWP와 PDF 본문이 모두 존재하지만 일치율이 90% 미만인 경우 '⚠ 검토 필요' 경고 부착"""
    hwp_data = {
        22: {
            "question_title": "22. 다음 글의 주제로 가장 적절한 것은?",
            "passage_body": "Original HWP text discussing economic behavior in financial markets under uncertainty.",
            "passage_text": "Original HWP text discussing economic behavior in financial markets under uncertainty.",
            "question_type": "주제",
        }
    }
    pdf_data = {
        22: {
            "question_title": "22. 다음 글의 주제로 가장 적절한 것은?",
            "passage_body": "Significantly different PDF OCR text missing many words and having wrong paragraphs.",
            "passage_text": "Significantly different PDF OCR text missing many words and having wrong paragraphs.",
            "pdf_crop_image": "",
        }
    }
    explanations = {22: {"answer": "①", "explanation": "[정답] ①"}}

    results = cross_validate_and_merge(hwp_data, pdf_data, explanations, "고3", 2024, 6)
    p = results[0]["passage_data"]

    assert p["validation_ratio"] is not None
    assert p["validation_ratio"] < 0.9
    assert "⚠ 검토 필요" in p["remarks"]
    assert "일치율:" in p["remarks"]


def test_cross_validate_and_merge_missing_pdf_body():
    """PDF 본문이 없고 HWP만 있는 경우: ratio=None, '비교 불가' 기록 (100% 왜곡 방지)"""
    hwp_data = {
        23: {
            "question_title": "23. 다음 글의 제목으로 가장 적절한 것은?",
            "passage_body": "Only HWP text is available for this question.",
            "passage_text": "Only HWP text is available for this question.",
            "question_type": "제목",
        }
    }
    pdf_data = {}  # PDF 데이터 없음
    explanations = {23: {"answer": "④", "explanation": "[정답] ④"}}

    results = cross_validate_and_merge(hwp_data, pdf_data, explanations, "고3", 2024, 6)
    p = results[0]["passage_data"]

    assert p["validation_ratio"] is None
    assert p["remarks"] == "비교 불가 (HWP/PDF 중 한쪽 없음)"


def test_cross_validate_and_merge_missing_hwp_body():
    """HWP 본문이 없고 PDF만 있는 경우: ratio=None, '비교 불가' 기록"""
    hwp_data = {}
    pdf_data = {
        24: {
            "question_title": "24. 다음 글의 제목으로 가장 적절한 것은?",
            "passage_body": "Only PDF text is available for this question.",
            "passage_text": "Only PDF text is available for this question.",
            "pdf_crop_image": "/static/captures/test_24.png",
        }
    }
    explanations = {24: {"answer": "②", "explanation": "[정답] ②"}}

    results = cross_validate_and_merge(hwp_data, pdf_data, explanations, "고3", 2024, 6)
    p = results[0]["passage_data"]

    assert p["validation_ratio"] is None
    assert p["remarks"] == "비교 불가 (HWP/PDF 중 한쪽 없음)"


def test_cross_validate_and_merge_both_bodies_empty():
    """양쪽 항목은 있으나 passage_body가 모두 빈 문자열인 경우: ratio=None, '비교 불가' 기록"""
    hwp_data = {25: {"question_title": "25. 표의 내용과 일치하지 않는 것은?", "passage_body": ""}}
    pdf_data = {25: {"question_title": "25. 표의 내용과 일치하지 않는 것은?", "passage_body": ""}}
    explanations = {25: {"answer": "⑤", "explanation": "[정답] ⑤"}}

    results = cross_validate_and_merge(hwp_data, pdf_data, explanations, "고3", 2024, 6)
    p = results[0]["passage_data"]

    assert p["validation_ratio"] is None
    assert p["remarks"] == "비교 불가 (HWP/PDF 중 한쪽 없음)"


def test_db_roundtrip_with_none_validation_ratio(tmp_db):
    """validation_ratio=None인 지문을 SQLite에 저장하고 조회 시 정상 동작 검증"""
    db = tmp_db
    exam = {
        "id": "[고3-2099년-10월]",
        "grade": "고3",
        "year": 2099,
        "month": 10,
        "exam_type": "평가원",
        "reading_start_q": 18,
        "reading_end_q": 45,
    }
    db.save_exam(exam)

    pid = "[고3-2099년-10월-21번]"
    p_data = {
        "id": pid,
        "exam_id": exam["id"],
        "q_num": 21,
        "question_title": "21. 문항",
        "question_type": "함축의미",
        "passage_text": "A passage with unvalidated comparison.",
        "answer_text": "①",
        "explanation_text": "[정답] ①",
        "pdf_crop_image": "",
        "validation_ratio": None,
        "remarks": "비교 불가 (HWP/PDF 중 한쪽 없음)",
    }
    db.save_passage(p_data)

    retrieved = db.get_passage(pid)
    assert retrieved is not None
    assert retrieved["validation_ratio"] is None
    assert retrieved["remarks"] == "비교 불가 (HWP/PDF 중 한쪽 없음)"
