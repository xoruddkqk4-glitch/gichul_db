"""등급별 데이터 필터(access.py)와 3-B 변경 회귀 테스트 (임시 DB 사용, 실제 gichul.db 는 건드리지 않음)

- 기본 등급(관리자)은 예전과 똑같은 결과
- 회원: 관리자 전용 필드(메모·정답 출처·즐겨찾기 등)만 빠짐
- 비회원: 메타 정보(정답률·선지 선택률·태그·어법 범주)까지 빠지고, 메타 검색 조건은 무시
- search_sentences 빈칸 채우기: 지문 정보를 한 번에 조회해 text_utils.fill_blanks 로 채움
- init_db 는 import 시점이 아니라 FastAPI lifespan 에서 호출
"""
import pytest

from gichul import access
from gichul import database as db

EXAM_ID = "[T-2026-05]"
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
        conn.execute("INSERT INTO exams (id, grade, year, month) VALUES (?, ?, ?, ?)", (EXAM_ID, "고3", 2026, 5))
        conn.execute(
            "INSERT INTO passages (id, exam_id, q_num, passage_text, answer_text, explanation_text, "
            "correct_rate, choice_rates, user_memo, answer_source, answer_verified) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (PASSAGE_ID, EXAM_ID, 31, PASSAGE_TEXT, "②", "[정답] ②", 42.5, '{"1": 10}', "내 메모", "verified_key", 1),
        )
        rows = [
            ("[S1]", "Orb-weaving spiders often use distinct vibrational signals to defend their webs."),
            ("[S2]", "The beauty of vibrational signaling lies in its __________."),  # 아직 빈칸
            ("[S3]", "It avoids costly physical clashes."),
        ]
        for i, (sid, text) in enumerate(rows):
            conn.execute(
                "INSERT INTO sentences (id, passage_id, order_index, sentence_text, word_count, is_starred) VALUES (?, ?, ?, ?, ?, ?)",
                (sid, PASSAGE_ID, i, text, len(text.split()), 1 if sid == "[S1]" else 0),
            )
        conn.execute("INSERT INTO passage_tags (passage_id, tag_name) VALUES (?, ?)", (PASSAGE_ID, "빈칸"))
        conn.execute("INSERT INTO sentence_tags (sentence_id, tag_name) VALUES (?, ?)", ("[S1]", "핵심"))
        conn.execute(
            "INSERT INTO sentence_grammar_annotations (sentence_id, category_id, pos, full_path, leaf_name, source_type) "
            "VALUES ('[S3]', 1, '명사', '명사 > 테스트', '테스트', 'AI')"
        )
    return db


# ---------- access.py 단위 ----------

def test_normalize_role():
    assert access.normalize_role(None) == access.ROLE_ADMIN       # 인증 전 기본값 = 관리자
    assert access.normalize_role("") == access.ROLE_ADMIN
    assert access.normalize_role(" Member ") == access.ROLE_MEMBER
    assert access.normalize_role("hacker") == access.ROLE_GUEST   # 모르는 값은 가장 낮은 등급


def test_admin_filter_returns_same_object():
    p = {"id": "x", "correct_rate": 50, "user_memo": "m"}
    assert access.filter_passage(p) is p
    lst = [p]
    assert access.filter_passages(lst, "admin") is lst


def test_member_and_guest_fields():
    p = {"id": "x", "passage_text": "t", "answer_text": "②", "explanation_text": "e",
         "correct_rate": 50, "choice_rates": "{}", "choice_rates_obj": {}, "tags": ["a"],
         "user_memo": "m", "answer_source": "csv", "answer_verified": 1}
    member = access.filter_passage(p, "member")
    assert {"correct_rate", "choice_rates", "choice_rates_obj", "tags"} <= member.keys()
    assert "user_memo" not in member and "answer_source" not in member
    guest = access.filter_passage(p, "guest")
    assert set(guest) == {"id", "passage_text", "answer_text", "explanation_text"}
    assert p["user_memo"] == "m"  # 원본은 바뀌지 않음


# ---------- DB 함수 훅 ----------

def test_get_passage_by_role(temp_db):
    admin = db.get_passage(PASSAGE_ID)
    assert admin["correct_rate"] == 42.5 and admin["tags"] == ["빈칸"] and admin["user_memo"] == "내 메모"
    member = db.get_passage(PASSAGE_ID, user_role="member")
    assert member["correct_rate"] == 42.5 and member["tags"] == ["빈칸"] and "user_memo" not in member
    guest = db.get_passage(PASSAGE_ID, user_role="guest")
    assert guest["answer_text"] == "②" and guest["explanation_text"] == "[정답] ②"
    assert not ({"correct_rate", "choice_rates", "choice_rates_obj", "tags", "user_memo"} & guest.keys())


def test_search_passages_guest_ignores_meta_filters(temp_db):
    # 관리자: 정답률/태그 조건이 적용됨
    assert db.search_passages(tag="없는태그") == []
    # 비회원: 메타 조건은 무시되고(간접 노출 방지) 메타 필드도 빠진다
    res = db.search_passages(tag="없는태그", user_role="guest")
    assert [r["id"] for r in res] == [PASSAGE_ID]
    assert "correct_rate" not in res[0] and "tags" not in res[0]
    meta = db.search_passages(meta_only=True, user_role="guest")
    assert "correct_rate" not in meta[0] and "user_memo" not in meta[0]
    assert len(db.get_exam_passages(EXAM_ID, user_role="guest")) == 1


def test_search_sentences_by_role(temp_db):
    admin = {r["id"]: r for r in db.search_sentences()}
    assert admin["[S1]"]["is_starred"] == 1 and admin["[S1]"]["tags"] == ["핵심"]
    assert len(admin["[S3]"]["grammar_annotations"]) == 1

    member = {r["id"]: r for r in db.search_sentences(user_role="member")}
    assert "is_starred" not in member["[S1]"] and member["[S1]"]["tags"] == ["핵심"]

    guest = db.search_sentences(user_role="guest")
    assert all(not ({"tags", "grammar_annotations", "correct_rate", "is_starred"} & r.keys()) for r in guest)
    # 즐겨찾기/어법 범주 조건도 무시된다
    assert len(db.search_sentences(is_starred=True, user_role="guest")) == 3
    assert len(db.search_sentences(grammar_cat_id=999, user_role="member")) == 0
    assert len(db.search_sentences(grammar_cat_id=999, user_role="guest")) == 3


def test_search_sentences_fills_blank_from_batched_passage(temp_db):
    rows = {r["id"]: r for r in db.search_sentences()}
    assert rows["[S2]"]["sentence_text"] == "The beauty of vibrational signaling lies in its efficiency."
    assert rows["[S1]"]["sentence_text"].startswith("Orb-weaving")


# ---------- import 부작용 제거 ----------

def test_init_db_runs_in_lifespan(monkeypatch):
    from starlette.testclient import TestClient
    from gichul import app as app_module

    calls = []
    monkeypatch.setattr(app_module.db, "init_db", lambda: calls.append(1))
    with TestClient(app_module.app):
        pass
    assert calls == [1]
