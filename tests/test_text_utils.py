"""text_utils.py / services/grammar_service.py 회귀 테스트 (로드맵 3-A)
- 순수 함수: ID 정규화, [정답] 헤더 갱신, 선지/정답 추출, 빈칸 채우기
- 서비스: DB·LLM 호출을 가짜로 바꿔 '전처리 → 문장 갱신 → 분석 → 저장' 흐름만 검증 (실제 DB/AI 호출 없음)
"""
import re

import pytest

from gichul import text_utils as tu
from gichul import grammar_analyzer as ga
from gichul.services import grammar_service as gs


# ---------- normalize_bracket_id ----------

@pytest.mark.parametrize("raw, expected", [
    ("고3-2024년-06월-18번", "[고3-2024년-06월-18번]"),
    ("  고3-2024년-06월-18번  ", "[고3-2024년-06월-18번]"),
    ("[고3-2024년-06월-18번]", "[고3-2024년-06월-18번]"),
    ("  [ID]  ", "[ID]"),
    ("", "[]"),
])
def test_normalize_bracket_id(raw, expected):
    assert tu.normalize_bracket_id(raw) == expected


def _old_header_logic(exp_body, ans):
    """교체 전 코드(app.py/hwp_parser/listening_parser 등)에 반복되던 원래 구현"""
    if not re.search(r"^\s*\[\s*정답\s*\]", exp_body):
        return f"[정답] {ans}\n\n{exp_body}".strip()
    return re.sub(r"^\s*\[\s*정답\s*\]\s*[①②③④⑤1-5]?", f"[정답] {ans}", exp_body)


# ---------- apply_answer_header ----------

@pytest.mark.parametrize("exp", [
    "",
    "해설 본문입니다.",
    "  앞뒤 공백 해설  \n",
    "[정답] ③\n\n해설",
    "[정답]③ 붙어 있는 헤더",
    "  [ 정답 ]  2\n해설",
    "[정답]\n번호 없는 헤더",
    "본문 중간의 [정답] ④ 는 헤더가 아님",
])
@pytest.mark.parametrize("ans", ["①", "⑤", "3"])
def test_apply_answer_header_matches_old_logic(exp, ans):
    assert tu.apply_answer_header(exp, ans) == _old_header_logic(exp, ans)


def test_apply_answer_header_examples():
    assert tu.apply_answer_header("", "②") == "[정답] ②"
    assert tu.apply_answer_header("해설", "②") == "[정답] ②\n\n해설"
    assert tu.apply_answer_header("[정답] ① 해설", "④") == "[정답] ④ 해설"
    assert tu.apply_answer_header(None, "④") == "[정답] ④"


# ---------- extract_answer_num / extract_choices / clean_choice_markers ----------

@pytest.mark.parametrize("text, expected", [
    ("③", 3), ("3", 3), ("[정답] ④", 4), ("", None), (None, None), ("정답 없음", None),
])
def test_extract_answer_num(text, expected):
    assert tu.extract_answer_num(text) == expected


def test_extract_choices_circled():
    passage = "Some passage ____.\n① apple ② banana ③ cherry [3점] ④ date ⑤ elder"
    assert tu.extract_choices(passage) == {1: "apple", 2: "banana", 3: "cherry", 4: "date", 5: "elder"}


def test_clean_choice_markers():
    assert tu.clean_choice_markers("(A) The (1) cat ① sat.") == "The cat sat."
    assert tu.clean_choice_markers("2) second item") == "second item"
    assert tu.clean_choice_markers("") == ""


# ---------- fill_blanks ----------

def test_fill_blanks_single_blank():
    passage = "① red ② blue ③ green ④ black ⑤ white"
    out = tu.fill_blanks("The sky is ____ .", passage, "②")
    assert out == "The sky is blue."


def test_fill_blanks_two_blanks_split_choice():
    passage = "① fast …… slow\n② hot …… cold\n③ up …… down\n④ big …… small\n⑤ new …… old"
    out = tu.fill_blanks("It is (A) ____ and (B) ____ .", passage, "③")
    assert out == "It is up and down."


def test_fill_blanks_summary_q40_underscores_and_markers():
    passage = (
        "In the past, color was considered an ___(A)___ to the truth.\n"
        "(A) \t (B)\n"
        "① controllability ---\tchallenge\n"
        "② predictability ---\tsupport\n"
        "③ manageability ---\tintensify\n"
        "④ affordability ---\treverse\n"
        "⑤ accessibility ---\tquestion\n"
    )
    raw_sentence = (
        "The ___(A)___ of the process may ___(B)___ people's commonly held assumption."
    )
    filled = tu.fill_blanks(raw_sentence, passage, "①")
    assert filled == "The controllability of the process may challenge people's commonly held assumption."


def test_fill_blanks_summary_multiline_choices():
    passage = (
        "Summary text here.\n"
        "(A)\n(B)\n"
        "①associate\n…… genetic\n"
        "②associate\n…… environmental\n"
        "③identify\n…… psychological\n"
        "④replace\n…… psychological\n"
        "⑤replace\n…… environmental\n"
        "*footnote line that must not leak into choice 5\n"
    )
    raw_sentence = "We must ___(A)___ the factor and ____(B)____ the outcome."
    assert tu.fill_blanks(raw_sentence, passage, "②") == "We must associate the factor and environmental the outcome."
    # ⑤는 ④와 같은 줄 수(2줄)만 가져온다
    assert tu.extract_choices(passage)[5] == "replace\t…… environmental"


def test_fill_blanks_korean_prompt_not_filled():
    prompt = "40. 다음 글의 내용을 한 문장으로 요약하고자 한다. 빈칸 (A), (B)에 들어갈 말로 가장 적절한 것은?"
    passage = "① good …… bad ② high …… low ③ fast …… slow ④ big …… small ⑤ hot …… cold"
    out = tu.fill_blanks(prompt, passage, "①")
    assert "good" not in out and "bad" not in out


# ---------- 회귀 방지: 밑줄 없는 맨 (A)/(B)는 빈칸이 아니다 ----------

def test_fill_blanks_ordering_paragraph_marker_untouched():
    passage = "① (A)-(C)-(B) ② (B)-(A)-(C) ③ (B)-(C)-(A) ④ (C)-(A)-(B) ⑤ (C)-(B)-(A)"
    assert tu.fill_blanks("(A) Once upon a time there was a king.", passage, "②") == "Once upon a time there was a king."


def test_fill_blanks_grammar_box_label_untouched():
    passage = "① good …… was ② goods …… were ③ good …… were ④ goods …… was ⑤ good …… is"
    out = tu.fill_blanks("Americans could not buy all of the (A) good / goods .", passage, "②")
    assert out == "Americans could not buy all of the good / goods ."


def test_fill_blanks_labeled_blank_in_separate_sentence():
    # (A), (B) 빈칸이 서로 다른 문장에 있으면 문장마다 빈칸이 1개 -> 표지로 선지 파트를 고른다
    passage = (
        "① What is worse\t……\tLikewise\n② What is worse\t……\tInstead\n"
        "③ As a result\t……\tLikewise\n④ On the contrary\t……\tLikewise\n⑤ On the contrary\t……\tInstead"
    )
    assert tu.fill_blanks("___(A)___, you are busy.", passage, "②") == "What is worse, you are busy."
    assert tu.fill_blanks("___(B)___, find special occasions.", passage, "②") == "Instead, find special occasions."


def test_extract_choices_drops_broken_glyph_segments():
    passage = "① In fact\t\u0d00\u0100\t----     Instead\n② In fact\t\u0d00\u0100\t----     In\u3000addition\n" \
              "③ Otherwise\t\u07c0\u0100\t----     In short\n④ Nevertheless\t\u031c\u0100\t----     As a result\n" \
              "⑤ Nevertheless\t\u031c\u0100\t----     Otherwise"
    assert tu.split_choice_parts(tu.extract_choices(passage)[2]) == ["In fact", "In addition"]


def test_fill_blanks_no_answer_keeps_blank():
    assert tu.fill_blanks("Keep ____ here", "", "") == "Keep ____ here"


def test_fill_blanks_empty():
    assert tu.fill_blanks("", "x", "①") == ""


def test_grammar_analyzer_reexports_same_functions():
    # 기존 import 경로(grammar_analyzer.xxx)가 그대로 동작해야 함
    assert ga.extract_answer_num is tu.extract_answer_num
    assert ga.extract_choices is tu.extract_choices
    assert ga.clean_choice_markers is tu.clean_choice_markers
    assert ga.fill_blanks is tu.fill_blanks


def test_prepare_with_full_info_equals_fill_blanks():
    # 지문/정답이 모두 주어지면 DB 보강 없이 fill_blanks 와 같은 결과
    passage = "① red ② blue ③ green ④ black ⑤ white"
    assert ga.prepare_sentence_for_analysis("Sky ____ .", passage_text=passage, answer_text="②") == \
        tu.fill_blanks("Sky ____ .", passage, "②")


# ---------- services.grammar_service ----------

@pytest.fixture
def fake_backend(monkeypatch):
    calls = {"get_passage": [], "update": [], "save": [], "analyze": []}
    passages = {"P1": {"passage_text": "① red ② blue ③ green ④ black ⑤ white", "answer_text": "②", "explanation_text": ""}}

    def get_passage(pid):
        calls["get_passage"].append(pid)
        return passages.get(pid)

    monkeypatch.setattr(gs.db, "get_passage", get_passage)
    monkeypatch.setattr(gs.db, "update_sentence_text", lambda sid, text: calls["update"].append((sid, text)))
    monkeypatch.setattr(gs.db, "save_grammar_annotations",
                        lambda sid, annos, source_type, ai_model: calls["save"].append((sid, annos, source_type, ai_model)))

    def analyze_sentence(text, **kw):
        calls["analyze"].append((text, kw))
        return [{"category_id": 1, "text": text}]

    monkeypatch.setattr(gs.grammar_analyzer, "analyze_sentence", analyze_sentence)

    # 분석 직전 안전망: 기본은 바뀐 문장 없음. 테스트에서 calls["refill_result"] 로 결과를 지정
    calls["refill"] = []
    calls["refill_result"] = []

    def refill_blank_sentences(passage_ids=None, **kw):
        calls["refill"].append(passage_ids)
        return calls["refill_result"]

    monkeypatch.setattr(gs.db, "refill_blank_sentences", refill_blank_sentences)
    return calls


def test_service_refill_safety_net_replaces_stale_text(fake_backend):
    # 예전 정답(black)으로 채워진 문장 → 안전망이 현재 정답(blue)으로 바로잡은 뒤 분석
    fake_backend["refill_result"] = [{"sentence_id": "[S9]", "new_text": "The sky is blue."}]
    row = {"id": "[S9]", "sentence_text": "The sky is black.", "passage_id": "P1"}
    res = gs.analyze_and_save_sentence(row)
    assert fake_backend["refill"] == [["P1"]]
    assert res["sentence_text"] == "The sky is blue."
    assert fake_backend["analyze"][0][0] == "The sky is blue."


def test_service_fills_blank_updates_and_saves(fake_backend):
    row = {"id": "[S1]", "sentence_text": "The sky is ____ .", "passage_id": "P1"}
    res = gs.analyze_and_save_sentence(row, {})
    assert res["sentence_text"] == "The sky is blue."
    assert row["sentence_text"] == "The sky is blue."           # 원본 dict 도 갱신 (기존 동작)
    assert fake_backend["update"] == [("[S1]", "The sky is blue.")]
    assert fake_backend["analyze"][0][0] == "The sky is blue."  # 갱신된 문장으로 분석
    sid, annos, src, model = fake_backend["save"][0]
    assert (sid, src, model) == ("[S1]", "AI", "Multi-LLM")
    assert res["annotations"] == annos


def test_service_no_change_skips_update(fake_backend):
    row = {"id": "[S2]", "sentence_text": "Plain sentence.", "passage_id": "P1"}
    gs.analyze_and_save_sentence(row, {})
    assert fake_backend["update"] == []
    assert len(fake_backend["save"]) == 1


def test_service_uses_passage_cache_once(fake_backend):
    cache = {}
    for i in range(3):
        gs.analyze_and_save_sentence({"id": f"[S{i}]", "sentence_text": "Plain.", "passage_id": "P1"}, cache)
    assert fake_backend["get_passage"] == ["P1"]


def test_service_sentence_id_override(fake_backend):
    row = {"id": "S3", "sentence_text": "The sky is ____ .", "passage_id": "P1"}
    gs.analyze_and_save_sentence(row, {}, sentence_id="[S3]")
    assert fake_backend["update"][0][0] == "[S3]"
    assert fake_backend["save"][0][0] == "[S3]"


def test_service_propagates_analysis_error(fake_backend, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("LLM down")
    monkeypatch.setattr(gs.grammar_analyzer, "analyze_sentence", boom)
    with pytest.raises(RuntimeError):
        gs.analyze_and_save_sentence({"id": "[S4]", "sentence_text": "Plain.", "passage_id": "P1"}, {})
    assert fake_backend["save"] == []


# ---------- sanitize_upload_filename (로드맵 4-B) ----------

@pytest.mark.parametrize("raw, expected", [
    ("고3_2024_06_문제지.pdf", "고3_2024_06_문제지.pdf"),
    ("[고3-2024년-06월] (A형).png", "[고3-2024년-06월] (A형).png"),
    ("../../etc/passwd.pdf", "passwd.pdf"),
    ("some/nested/path/sample.pdf", "sample.pdf"),
    ("..\\..\\windows\\system32\\calc.exe", "calc.bin"),
    ("malicious.bat", "malicious.bin"),
    ("test<script>alert(1).hwp", "test_script_alert(1).hwp"),
    ("file:with*invalid?chars.csv", "file_with_invalid_chars.csv"),
    ("   spaces   and...dots...hwp", "spaces and_dots.hwp"),
    ("", "upload"),
    ("...", "upload"),
    ("   ", "upload"),
    ("///", "upload"),
    ("a   b___c.pdf", "a b_c.pdf"),
])
def test_sanitize_upload_filename(raw, expected):
    assert tu.sanitize_upload_filename(raw) == expected


