"""
tests/test_pdf_parser.py: PDF 파서 모듈(gichul/pdf_parser.py) 단위 테스트
- 기호 맵 매핑 무결성 검증
- 듣기/독해 영역 문항 범위 감지(detect_listening_range)
- 1지문 다문항 헤더 감지(find_group_header)
- PyMuPDF 인메모리 문서를 활용한 형광펜 주석(highlight_answer_choice) 검증
"""

import pytest
import pymupdf as fitz
from gichul.pdf_parser import (
    CIRCLED_MAP,
    REVERSE_CIRCLED_MAP,
    detect_listening_range,
    find_group_header,
    highlight_answer_choice,
    extract_choice_words_geometrically,
)


class TestPdfParserSymbolMaps:
    def test_circled_maps_consistency(self):
        """원문자 기호 매핑 양방향 일관성 검증"""
        for num_str, sym in CIRCLED_MAP.items():
            num = int(num_str)
            assert REVERSE_CIRCLED_MAP[sym] == num
            assert REVERSE_CIRCLED_MAP[num_str] == num
            assert REVERSE_CIRCLED_MAP[num] == num


class TestDetectListeningRange:
    def test_standard_exam_listening_range(self):
        """현행 45문항 체제 (듣기 1~17번, 독해 18~45번) 감지"""
        sample_text = (
            "1번부터 17번까지는 듣고 답하는 문제입니다.\n"
            "이제 듣기·말하기 문제가 끝났습니다. 18번부터는 문제지의 지시에 따라 답을 하시기 바랍니다."
        )
        start, end = detect_listening_range(sample_text, year=2024, grade="고3", month=6)
        assert start == 18
        assert end == 45

    def test_ab_period_listening_range(self):
        """2013년 수준별(A/B형) 45문항 체제 (듣기 1~22번, 독해 23~45번) 감지"""
        sample_text = (
            "1번부터 22번까지는 듣고 답하는 문제입니다.\n"
            "이제 듣기 문제가 끝났습니다. 23번부터는 문제지의 지시에 따라..."
        )
        start, end = detect_listening_range(sample_text, year=2013, grade="고3", month=6, subtype="B형")
        assert start == 23
        assert end == 45

    def test_50_questions_exam_detection(self):
        """구 50문항 체제 (2006~2011년) 50번 감지"""
        sample_text = (
            "1번부터 17번까지는 듣고 답하는 문제입니다.\n"
            "이제 듣기·말하기 문제가 끝났습니다. 18번부터는...\n"
            "[49~50] 다음 글을 읽고 물음에 답하시오.\n"
            "50. 위 글의 빈칸에 들어갈 말로 가장 적절한 것은?"
        )
        start, end = detect_listening_range(sample_text, year=2010, grade="고3", month=11)
        assert start == 18
        assert end == 50

    def test_font_cid_corruption_fallback(self):
        """CID 폰트 손상 시 숫자 시퀀스(1 ... 17 ... 1 ... 15) 기반 폴백"""
        sample_text = "1 abcdef 17 ghijkl 1 mnop 15"
        start, end = detect_listening_range(sample_text, year=2022, grade="고2", month=3)
        assert start == 18
        assert end == 45


class TestFindGroupHeader:
    def test_standard_bracket_headers(self):
        """표준 대괄호 다문항 헤더 감지"""
        assert find_group_header("[41~42] 다음 글을 읽고 물음에 답하시오.", 18, 45) == (41, 42)
        assert find_group_header("[43～45] 다음 글을 읽고 물음에 답하시오.", 18, 45) == (43, 45)
        assert find_group_header("[41-42] 다음 글을 읽고...", 18, 45) == (41, 42)

    def test_asian_brackets_and_spaces(self):
        """전각 괄호 및 특수 괄호 헤더 감지"""
        assert find_group_header("［41~42］ 다음 글을 읽고", 18, 45) == (41, 42)
        assert find_group_header("【43 - 45】 다음 글을 읽고", 18, 45) == (43, 45)
        assert find_group_header("[46 ~ 다음 글을 읽고 48]", 18, 48) == (46, 48)

    def test_out_of_range_or_single_question_returns_none(self):
        """단일 문항이거나 허용 범위를 벗어난 경우 None 반환"""
        assert find_group_header("21. 다음 밑줄 친 부분이 의미하는 바로...", 18, 45) is None
        assert find_group_header("[55~60] 범위 외 문항", 18, 45) is None
        assert find_group_header("일반 본문 텍스트", 18, 45) is None


class TestPdfHighlightAnnotations:
    def test_highlight_answer_choice_in_memory(self):
        """인메모리 PDF 페이지에 정답 기호 형광펜 주석 생성 검증"""
        doc = fitz.open()
        page = doc.new_page(width=500, height=700)
        
        # 선지 번호(대체 표기 포맷)가 포함된 텍스트 삽입
        text = "21. Choose the best answer.\n(1) First choice\n(2) Second choice\n(3) Third choice\n(4) Fourth choice\n(5) Fifth choice"
        page.insert_text(fitz.Point(50, 100), text, fontsize=11)
        
        clip_rect = fitz.Rect(40, 80, 450, 300)
        annots = highlight_answer_choice(page, clip_rect, ans_val="3")
        
        assert len(annots) >= 1
        annot = annots[0]
        assert annot.type[0] == fitz.PDF_ANNOT_HIGHLIGHT
        # 파스텔 노란색 스트로크 컬러 검증 (1.0, 0.91, 0.33)
        colors = annot.colors
        assert "stroke" in colors
        assert len(colors["stroke"]) == 3
        assert colors["stroke"][0] == pytest.approx(1.0, abs=0.05)
        assert colors["stroke"][1] == pytest.approx(0.91, abs=0.05)

    def test_highlight_answer_choice_invalid_or_empty(self):
        """유효하지 않은 정답 값 전달 시 주석 미생성 검증"""
        doc = fitz.open()
        page = doc.new_page(width=500, height=700)
        clip_rect = fitz.Rect(0, 0, 500, 700)
        
        assert highlight_answer_choice(page, clip_rect, ans_val="") == []
        assert highlight_answer_choice(page, clip_rect, ans_val="0") == []
        assert highlight_answer_choice(page, clip_rect, ans_val="unknown") == []
