"""database.refill_blank_sentences 회귀 테스트 (임시 DB 사용, 실제 gichul.db 는 건드리지 않음)

버그: 빈칸 문장을 어법 분석 전처리로 채워 저장한 뒤 정답이 바뀌면, 문장에 예전 선지가 남았다.
예) 고3-2026년-05월-31번: 정답 ② efficiency 인데 문장은 ④ randomness 로 채워져 있었음
"""
import pytest

from gichul import database as db

PASSAGE_ID = "[T-2026-05-31]"
PASSAGE_TEXT = (
    "31. 다음 빈칸에 들어갈 말로 가장 적절한 것을 고르시오.\n\n"
    "Orb-weaving spiders often use distinct vibrational signals to defend their webs. "
    "The beauty of vibrational signaling lies in its __________. "
    "It avoids costly physical clashes.\n"
    "① secrecy \t\t② efficiency\n③ dishonesty \t\t④ randomness\n⑤ subjectivity"
)


@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "test.db"))
    db.init_db()
    with db.get_connection() as conn:
        conn.execute("INSERT INTO exams (id, grade, year, month) VALUES (?, ?, ?, ?)", ("[T-2026-05]", "고3", 2026, 5))
        conn.execute(
            "INSERT INTO passages (id, exam_id, q_num, passage_text, answer_text, explanation_text) VALUES (?, ?, ?, ?, ?, ?)",
            (PASSAGE_ID, "[T-2026-05]", 31, PASSAGE_TEXT, "②", "[정답] ②"),
        )
        rows = [
            ("[S1]", "Orb-weaving spiders often use distinct vibrational signals to defend their webs.", 1),
            ("[S2]", "The beauty of vibrational signaling lies in its randomness.", 1),   # 예전 오답으로 채워짐
            ("[S3]", "It avoids costly physical clashes.", 1),
        ]
        for i, (sid, text, analyzed) in enumerate(rows):
            conn.execute(
                "INSERT INTO sentences (id, passage_id, order_index, sentence_text, word_count, grammar_analyzed) VALUES (?, ?, ?, ?, ?, ?)",
                (sid, PASSAGE_ID, i, text, len(text.split()), analyzed),
            )
    return db


def _sentence(sid):
    with db.get_connection() as conn:
        return conn.execute("SELECT sentence_text, grammar_analyzed FROM sentences WHERE id = ?", (sid,)).fetchone()


def test_dry_run_reports_without_writing(temp_db):
    changes = db.refill_blank_sentences(passage_ids=[PASSAGE_ID], dry_run=True)
    assert [(c["sentence_id"], c["wrong_choice"], c["answer"]) for c in changes] == [("[S2]", 4, 2)]
    assert changes[0]["new_text"] == "The beauty of vibrational signaling lies in its efficiency."
    assert _sentence("[S2]")["sentence_text"].endswith("randomness.")


def test_refill_replaces_wrong_choice_and_resets_ai(temp_db):
    with db.get_connection() as conn:
        conn.execute(
            "INSERT INTO sentence_grammar_annotations (sentence_id, category_id, pos, full_path, leaf_name, source_type) "
            "VALUES ('[S2]', 1, '명사', '명사 > 테스트', '테스트', 'AI')"
        )
    changes = db.refill_blank_sentences(exam_id="[T-2026-05]")
    assert len(changes) == 1
    row = _sentence("[S2]")
    assert row["sentence_text"] == "The beauty of vibrational signaling lies in its efficiency."
    assert row["grammar_analyzed"] == 0  # AI 주석 삭제 → 재분석 필요
    # 다른 문장은 그대로
    assert _sentence("[S1]")["grammar_analyzed"] == 1
    # 두 번째 실행은 바꿀 것이 없음
    assert db.refill_blank_sentences(exam_id="[T-2026-05]") == []


def test_merged_previous_sentence_is_kept(temp_db):
    # 문장 분할이 달라 앞 문장이 붙어 있어도 빈칸 구간만 바뀐다
    with db.get_connection() as conn:
        conn.execute("UPDATE sentences SET sentence_text = ? WHERE id = '[S2]'",
                     ("Signals matter. The beauty of vibrational signaling lies in its randomness.",))
    db.refill_blank_sentences(passage_ids=[PASSAGE_ID])
    assert _sentence("[S2]")["sentence_text"] == "Signals matter. The beauty of vibrational signaling lies in its efficiency."


def test_answer_update_triggers_refill(temp_db):
    # 정답을 ④로 바꾸면 이제 efficiency(②)로 채워진 문장이 randomness(④)로 바뀐다
    db.refill_blank_sentences(passage_ids=[PASSAGE_ID])
    db.update_passage_answers("[T-2026-05]", {31: "④"}, source="manual", verified=1)
    assert _sentence("[S2]")["sentence_text"].endswith("randomness.")


def test_unrelated_or_unfilled_sentences_untouched(temp_db):
    with db.get_connection() as conn:
        conn.execute("UPDATE sentences SET sentence_text = ? WHERE id = '[S2]'",
                     ("The beauty of vibrational signaling lies in its __________.",))
    assert db.refill_blank_sentences(passage_ids=[PASSAGE_ID]) == []
    assert db.refill_blank_sentences(passage_ids=[]) == []
