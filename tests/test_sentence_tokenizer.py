"""sentence_tokenizer.py 회귀 테스트 — 문장 분할, 지문 정제, 문장 레코드 생성"""
from sentence_tokenizer import clean_passage_for_sentences, split_sentences, create_sentence_records


# ---------- split_sentences: 기본 분할 ----------

def test_basic_three_sentences():
    text = "The cat sat on the mat. It was warm. Then it slept!"
    assert split_sentences(text) == ["The cat sat on the mat.", "It was warm.", "Then it slept!"]


def test_question_mark_and_newline_normalized():
    text = "Why did he leave?\nNobody knew the\nreason."
    assert split_sentences(text) == ["Why did he leave?", "Nobody knew the reason."]


def test_empty_and_whitespace_input():
    assert split_sentences("") == []
    assert split_sentences("   \n  ") == []


# ---------- split_sentences: 마침표 보호 ----------

def test_title_abbreviations_not_split():
    text = "Dr. Smith met Mr. Jones at noon. They talked for an hour."
    result = split_sentences(text)
    assert result == ["Dr. Smith met Mr. Jones at noon.", "They talked for an hour."]


def test_latin_abbreviations_not_split():
    text = "Some fruits, e.g. apples, are sweet. Others, i.e. lemons, are sour."
    result = split_sentences(text)
    assert result == ["Some fruits, e.g. apples, are sweet.", "Others, i.e. lemons, are sour."]


def test_geo_abbreviation_not_split():
    text = "He moved to the U.S. last year. He likes it there."
    assert split_sentences(text) == ["He moved to the U.S. last year.", "He likes it there."]


def test_decimal_number_not_split():
    text = "The value of pi is about 3.14 in math. Everyone knows that."
    result = split_sentences(text)
    assert result == ["The value of pi is about 3.14 in math.", "Everyone knows that."]


def test_ellipsis_preserved_and_not_split():
    text = "He waited... and waited. Nothing happened."
    result = split_sentences(text)
    assert result == ["He waited... and waited.", "Nothing happened."]


def test_single_letter_initial_not_split():
    text = "J. K. Rowling wrote the book. It sold well."
    assert split_sentences(text) == ["J. K. Rowling wrote the book.", "It sold well."]


# ---------- split_sentences: 인용부호 / 원문자 ----------

def test_closing_quote_stays_with_sentence():
    text = 'He said, "Go home." Then he left the room.'
    assert split_sentences(text) == ['He said, "Go home."', "Then he left the room."]


def test_circled_number_starts_new_sentence():
    text = "The chart shows sales. ① Sales rose in 2020. ② They fell in 2021."
    result = split_sentences(text)
    assert result == ["The chart shows sales.", "① Sales rose in 2020.", "② They fell in 2021."]


def test_fragment_without_english_word_dropped():
    # 숫자만 있는 조각은 유효 문장으로 인정하지 않음
    text = "It cost a lot. 2020. It was worth it."
    assert split_sentences(text) == ["It cost a lot.", "It was worth it."]


# ---------- clean_passage_for_sentences ----------

def test_clean_removes_question_stem():
    text = "18. 다음 글의 목적으로 가장 적절한 것은?\nDear Mr. Kim, we are pleased to invite you."
    assert clean_passage_for_sentences(text) == "Dear Mr. Kim, we are pleased to invite you."


def test_clean_removes_choices_block():
    text = "This is the body.\n① first choice\n② second choice\n③ third\n④ fourth\n⑤ fifth"
    assert clean_passage_for_sentences(text) == "This is the body."


def test_clean_removes_inline_choices():
    text = "This is the body.\n① first ② second ③ third ④ fourth ⑤ fifth"
    assert clean_passage_for_sentences(text) == "This is the body."


def test_clean_removes_footnotes():
    text = "Fish perish in the lagoon.\n* perish: 죽다 ** lagoon: 석호"
    assert clean_passage_for_sentences(text) == "Fish perish in the lagoon."


def test_clean_removes_score_marks():
    text = "Choose the best answer. [3점]"
    assert clean_passage_for_sentences(text) == "Choose the best answer."
    assert clean_passage_for_sentences("Another one. (2점)") == "Another one."


def test_clean_empty():
    assert clean_passage_for_sentences("") == ""
    assert clean_passage_for_sentences(None) == ""


def test_full_passage_pipeline():
    passage = (
        "21. 밑줄 친 부분이 의미하는 바로 가장 적절한 것은? [3점]\n"
        "Dr. Lee studied 2.5 million records. The results were clear.\n"
        "* record: 기록\n"
        "① data ② idea ③ time ④ money ⑤ trust"
    )
    assert split_sentences(passage) == ["Dr. Lee studied 2.5 million records.", "The results were clear."]


# ---------- create_sentence_records ----------

def test_records_ids_and_indexes():
    recs = create_sentence_records("[고3-2024년-06월-21번]", "First one. Second one here.")
    assert [r["id"] for r in recs] == ["[고3-2024년-06월-21번-1번째 문장]", "[고3-2024년-06월-21번-2번째 문장]"]
    assert [r["order_index"] for r in recs] == [1, 2]
    assert [r["sentence_text"] for r in recs] == ["First one.", "Second one here."]
    assert all(r["passage_id"] == "[고3-2024년-06월-21번]" for r in recs)
    assert all(r["remarks"] == "" for r in recs)


def test_records_passage_id_without_brackets_is_normalized():
    recs = create_sentence_records("고2-2023년-09월-30번", "Only one sentence.")
    assert recs[0]["id"] == "[고2-2023년-09월-30번-1번째 문장]"
    assert recs[0]["passage_id"] == "[고2-2023년-09월-30번]"


def test_records_word_count():
    recs = create_sentence_records("[고1-2022년-03월-18번]", "Don't stop believing in well-being.")
    assert recs[0]["word_count"] == 5


def test_records_empty_passage():
    assert create_sentence_records("[고3-2024년-06월-21번]", "") == []
