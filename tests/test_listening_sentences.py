"""
tests/test_listening_sentences.py
듣기 대본 문장 토큰화, 검색 분기, DB 문장 적재에 관한 단위 테스트
"""

import pytest
from gichul.sentence_tokenizer import (
    split_sentences,
    split_script_sentences,
    create_script_sentence_records,
)
from gichul import database as db


def test_split_script_sentences_dialogue():
    """대화문 스크립트가 화자 턴 및 개별 문장으로 정확히 분할되는지 검증"""
    script = (
        "W: Mike, you look exhausted. Is everything okay?\n"
        "M: Yes, Mom. I just feel tired because I have lots of social events these days.\n"
        "W: Yeah, you've seemed busy meeting people."
    )
    results = split_script_sentences(script)
    assert len(results) == 5

    # 1번째: W: 첫 문장
    assert results[0]["speaker"] == "W"
    assert results[0]["sentence_text"] == "W: Mike, you look exhausted."

    # 2번째: W: 두 번째 문장
    assert results[1]["speaker"] == "W"
    assert results[1]["sentence_text"] == "Is everything okay?"

    # 3번째: M: 첫 문장
    assert results[2]["speaker"] == "M"
    assert results[2]["sentence_text"] == "M: Yes, Mom."

    # 4번째: M: 두 번째 문장
    assert results[3]["speaker"] == "M"
    assert "I just feel tired" in results[3]["sentence_text"]

    # 5번째: W: 첫 문장
    assert results[4]["speaker"] == "W"
    assert results[4]["sentence_text"] == "W: Yeah, you've seemed busy meeting people."


def test_split_script_sentences_monologue():
    """화자 태그가 1개인 담화문(1인 발화) 분할 검증"""
    script = (
        "M: Hello, visitors to Cryston Beach. This is an announcement from the management office. "
        "As you know, this beach is famous for its beautiful black stones."
    )
    results = split_script_sentences(script)
    assert len(results) == 3
    assert results[0]["speaker"] == "M"
    assert results[0]["sentence_text"].startswith("M: Hello, visitors")
    assert results[1]["speaker"] == "M"
    assert results[1]["sentence_text"].startswith("This is an announcement")
    assert results[2]["speaker"] == "M"
    assert results[2]["sentence_text"].startswith("As you know")


def test_create_script_sentence_records():
    """문장 식별자 및 메타데이터(remarks, word_count 등) 생성 규격 검증"""
    passage_id = "[고3-2026년-09월-02번]"
    script = "W: Hello! How can I help you?\nM: I'm looking for a book."
    records = create_script_sentence_records(passage_id, script)

    assert len(records) == 3
    assert records[0]["id"] == "[고3-2026년-09월-02번-1번째 문장]"
    assert records[0]["passage_id"] == passage_id
    assert records[0]["order_index"] == 1
    assert records[0]["remarks"] == "듣기 대본 문장 (W)"
    assert records[0]["word_count"] > 0

    assert records[1]["id"] == "[고3-2026년-09월-02번-2번째 문장]"
    assert records[1]["order_index"] == 2
    assert records[1]["remarks"] == "듣기 대본 문장 (W)"

    assert records[2]["id"] == "[고3-2026년-09월-02번-3번째 문장]"
    assert records[2]["order_index"] == 3
    assert records[2]["remarks"] == "듣기 대본 문장 (M)"


def test_listening_search_passages_english_keyword():
    """듣기 영역 영문 검색 시 script_text 기준으로 정확히 필터링되는지 검증"""
    results = db.search_passages(keyword="exhausted", area="listening", limit=10)
    assert len(results) > 0
    # 모든 결과 지문의 script_text 또는 passage_text에 exhausted가 포함되어 있어야 함
    for r in results:
        found = "exhausted" in (r.get("script_text") or "").lower() or "exhausted" in (r.get("passage_text") or "").lower()
        assert found, f"지문 {r['id']}에 exhausted가 없습니다."


def test_listening_search_sentences():
    """문장 검색에서 area='listening'으로 듣기 대본 문장이 정상 조회되는지 검증"""
    results = db.search_sentences(keyword="exhausted", area="listening", limit=10)
    assert len(results) > 0
    for s in results:
        assert s["area"] == "listening"
        assert "exhausted" in s["sentence_text"].lower()
