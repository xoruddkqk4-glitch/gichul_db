"""
데이터베이스 검색 기능 단위 테스트 (tests/test_db_search.py)
- exam_id 및 sentence_ids 필터링
- FTS5 특수문자 입력 시 문법 오류 없이 LIKE 검색으로 안전하게 대체되는지 검증
- 온전한 단어(whole_word) 검색 동작 검증
"""

import pytest


@pytest.fixture
def sample_data(tmp_db):
    """검색 테스트용 고유 시험지, 지문, 문장 생성"""
    exam = {
        "id": "[고3-2024년-06월]",
        "grade": "고3",
        "year": 2024,
        "month": 6,
        "exam_type": "평가원",
        "reading_start_q": 18,
        "reading_end_q": 45,
    }
    tmp_db.save_exam(exam)

    p18_id = "[고3-2024년-06월-18번]"
    passage = {
        "id": p18_id,
        "exam_id": exam["id"],
        "q_num": 18,
        "question_title": "18. 다음 글의 목적으로 가장 적절한 것은?",
        "question_type": "목적",
        "passage_text": "Dear Principal, our climate science club requests funding for subatomic research.",
        "answer_text": "①",
        "explanation_text": "[정답] ①\n[해설] 연구 지원금 요청",
        "pdf_crop_image": "",
        "validation_ratio": 1.0,
        "remarks": "",
    }
    tmp_db.save_passage(passage)

    sentences = [
        {
            "id": f"{p18_id}-01",
            "passage_id": p18_id,
            "order_index": 1,
            "sentence_text": "Dear Principal, our climate science club requests funding for research.",
            "word_count": 10,
            "remarks": "",
        },
        {
            "id": f"{p18_id}-02",
            "passage_id": p18_id,
            "order_index": 2,
            "sentence_text": "Scientists observed: 'subatomic particles' with [special*] detectors.",
            "word_count": 8,
            "remarks": "",
        },
        {
            "id": f"{p18_id}-03",
            "passage_id": p18_id,
            "order_index": 3,
            "sentence_text": "We hope this proposal is realistic and meets all regulations.",
            "word_count": 10,
            "remarks": "",
        },
    ]
    tmp_db.save_sentences(sentences)
    return {"exam": exam, "passage": passage, "sentences": sentences}


def test_search_sentences_by_exam_id(tmp_db, sample_data):
    """exam_id 대괄호 포함/미포함 검색 필터 검증"""
    res_bracket = tmp_db.search_sentences(exam_id="[고3-2024년-06월]")
    assert len(res_bracket) == 3

    res_raw = tmp_db.search_sentences(exam_id="고3-2024년-06월")
    assert len(res_raw) == 3

    res_other = tmp_db.search_sentences(exam_id="[고1-2020년-03월]")
    assert len(res_other) == 0


def test_search_sentences_by_sentence_ids(tmp_db, sample_data):
    """sentence_ids 목록 필터 및 빈 리스트 즉시 반환 검증"""
    target_id = sample_data["sentences"][0]["id"]
    res_single = tmp_db.search_sentences(sentence_ids=[target_id])
    assert len(res_single) == 1
    assert res_single[0]["id"] == target_id

    # 빈 리스트 전달 시 즉시 빈 리스트 반환
    res_empty = tmp_db.search_sentences(sentence_ids=[])
    assert res_empty == []

    # None 전달 시 전체 반환
    res_none = tmp_db.search_sentences(sentence_ids=None)
    assert len(res_none) == 3


def test_search_sentences_fts_special_characters_fallback(tmp_db, sample_data):
    """FTS5 문법 에러 유발 특수문자(따옴표 불일치, 별표, 콜론 등) 입력 시 LIKE 검색으로 크래시 없이 자동 대체"""
    # 닫히지 않은 큰따옴표
    res_unclosed_quote = tmp_db.search_sentences(keyword='"subatomic')
    assert isinstance(res_unclosed_quote, list)
    assert len(res_unclosed_quote) == 1
    assert "subatomic" in res_unclosed_quote[0]["sentence_text"]

    # FTS 특수 연산자 기호 (*, :, OR, NOT 등 조합)
    res_fts_syntax = tmp_db.search_sentences(keyword="observed:*")
    assert isinstance(res_fts_syntax, list)
    assert len(res_fts_syntax) == 1

    # 괄호 및 대괄호 기호
    res_bracket_kw = tmp_db.search_sentences(keyword="[special*]")
    assert isinstance(res_bracket_kw, list)
    assert len(res_bracket_kw) == 1


def test_search_passages_fts_special_characters_fallback(tmp_db, sample_data):
    """지문 검색에서도 FTS5 특수문자 입력 시 크래시 없이 LIKE 대체 정상 동작"""
    res = tmp_db.search_passages(keyword='"subatomic')
    assert isinstance(res, list)
    assert len(res) == 1
    assert res[0]["id"] == sample_data["passage"]["id"]


def test_search_sentences_whole_word_matching(tmp_db, sample_data):
    """온전한 단어 검색(whole_word=True) 시 부분 일치 배제 검증"""
    # "real" 검색 시 "realistic"은 부분 일치이므로 whole_word=False일 때만 매칭
    res_substring = tmp_db.search_sentences(keyword="real", whole_word=False)
    assert len(res_substring) == 1  # "realistic" 매칭

    res_whole_word = tmp_db.search_sentences(keyword="real", whole_word=True)
    assert len(res_whole_word) == 0  # 독립 단어 "real"은 없으므로 0건

    res_whole_exact = tmp_db.search_sentences(keyword="realistic", whole_word=True)
    assert len(res_whole_exact) == 1
