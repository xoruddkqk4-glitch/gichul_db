"""
문장 교체 및 AI 어법 주석 관리 단위 테스트 (tests/test_db_sentences.py)
- replace_passage_sentences: 빈 목록 전달 시 보존 (오류 방지)
- 신규 삽입 및 누락 문장 연쇄 삭제(FK CASCADE) 검증
- 문장 텍스트 변경 시 AI 어법 주석 삭제 및 사용자(USER) 수동 주석 보존 검증
- 동일 텍스트 재업로드 시 AI 어법 주석 유지 검증
"""

import pytest


@pytest.fixture
def base_passage(tmp_db):
    """지문 및 기본 시험지 픽스처"""
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

    pid = "[고3-2024년-06월-20번]"
    passage = {
        "id": pid,
        "exam_id": exam["id"],
        "q_num": 20,
        "question_title": "20. 다음 글에서 필자가 주장하는 바로 가장 적절한 것은?",
        "question_type": "주장",
        "passage_text": "Sample passage text for testing replace_passage_sentences.",
        "answer_text": "①",
        "explanation_text": "[정답] ①",
        "pdf_crop_image": "",
        "validation_ratio": 1.0,
        "remarks": "",
    }
    tmp_db.save_passage(passage)
    return pid


def test_replace_sentences_empty_list_preserves_existing(tmp_db, base_passage):
    """빈 문장 목록 전달 시 파싱 실패로 인한 오삭제를 방지하고 기존 문장을 보존"""
    pid = base_passage
    initial = [
        {"id": f"{pid}-01", "passage_id": pid, "order_index": 1, "sentence_text": "First sentence.", "word_count": 2, "remarks": ""},
        {"id": f"{pid}-02", "passage_id": pid, "order_index": 2, "sentence_text": "Second sentence.", "word_count": 2, "remarks": ""},
    ]
    tmp_db.save_sentences(initial)

    stats = tmp_db.replace_passage_sentences(pid, [])
    assert stats == {"inserted": 0, "updated": 0, "text_changed": 0, "removed": 0}

    remaining = tmp_db.search_sentences(passage_id=pid)
    assert len(remaining) == 2


def test_replace_sentences_insert_and_delete(tmp_db, base_passage):
    """새 목록에 없는 기존 문장은 삭제되고, 새 문장은 정상 삽입되는지 검증"""
    pid = base_passage
    initial = [
        {"id": f"{pid}-01", "passage_id": pid, "order_index": 1, "sentence_text": "First sentence.", "word_count": 2, "remarks": ""},
        {"id": f"{pid}-02", "passage_id": pid, "order_index": 2, "sentence_text": "Second sentence.", "word_count": 2, "remarks": ""},
    ]
    tmp_db.save_sentences(initial)

    # 1번 문장은 빠지고, 2번 문장 유지, 3번 문장 신규 추가
    new_sentences = [
        {"id": f"{pid}-02", "passage_id": pid, "order_index": 1, "sentence_text": "Second sentence.", "word_count": 2, "remarks": ""},
        {"id": f"{pid}-03", "passage_id": pid, "order_index": 2, "sentence_text": "Third sentence.", "word_count": 2, "remarks": ""},
    ]
    stats = tmp_db.replace_passage_sentences(pid, new_sentences)
    assert stats["inserted"] == 1
    assert stats["removed"] == 1
    assert stats["updated"] == 1

    current = {s["id"]: s["sentence_text"] for s in tmp_db.search_sentences(passage_id=pid)}
    assert f"{pid}-01" not in current
    assert f"{pid}-02" in current
    assert f"{pid}-03" in current


def test_replace_sentences_text_changed_resets_ai_grammar_preserves_user_grammar(tmp_db, base_passage):
    """문장 텍스트가 변경되었을 때 AI 어법 주석은 초기화되고, 사용자(USER) 수동 등록 어법은 보존"""
    pid = base_passage
    sid = f"{pid}-01"
    initial = [
        {"id": sid, "passage_id": pid, "order_index": 1, "sentence_text": "The earth revolves around the sun.", "word_count": 6, "remarks": ""}
    ]
    tmp_db.save_sentences(initial)

    # AI 주석 및 USER 수동 주석 각각 등록
    with tmp_db.get_connection() as conn:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO sentence_grammar_annotations 
            (sentence_id, category_id, pos, full_path, leaf_name, target_expression, explanation, source_type)
            VALUES (?, 1, '동사', '동사>시제', '현재시제', 'revolves', 'AI 자동 분석', 'AI')
        """, (sid,))
        cur.execute("""
            INSERT INTO sentence_grammar_annotations 
            (sentence_id, category_id, pos, full_path, leaf_name, target_expression, explanation, source_type)
            VALUES (?, 2, '명사', '명사>고유명사', '고유명사', 'sun', '교사 수동 등록', 'USER')
        """, (sid,))
        conn.commit()

    # 텍스트 변경 재업로드
    modified = [
        {"id": sid, "passage_id": pid, "order_index": 1, "sentence_text": "The planet Earth orbits around the sun.", "word_count": 7, "remarks": ""}
    ]
    stats = tmp_db.replace_passage_sentences(pid, modified)
    assert stats["text_changed"] == 1

    # 주석 검증
    with tmp_db.get_connection() as conn:
        rows = conn.execute("SELECT source_type, leaf_name FROM sentence_grammar_annotations WHERE sentence_id = ?", (sid,)).fetchall()
        assert len(rows) == 1
        assert rows[0]["source_type"] == "USER"
        assert rows[0]["leaf_name"] == "고유명사"


def test_replace_sentences_equivalent_text_preserves_ai_grammar(tmp_db, base_passage):
    """문장 텍스트가 동일하면 재업로드되어도 AI 어법 주석이 삭제되지 않고 보존"""
    pid = base_passage
    sid = f"{pid}-01"
    initial = [
        {"id": sid, "passage_id": pid, "order_index": 1, "sentence_text": "Practice makes perfect.", "word_count": 3, "remarks": ""}
    ]
    tmp_db.save_sentences(initial)

    with tmp_db.get_connection() as conn:
        conn.execute("""
            INSERT INTO sentence_grammar_annotations 
            (sentence_id, category_id, pos, full_path, leaf_name, target_expression, explanation, source_type)
            VALUES (?, 10, '동사', '동사>자동사', '완전자동사', 'makes', 'AI 분석', 'AI')
        """, (sid,))
        conn.commit()

    # 공백이나 사소한 서식만 다른 동일 문장
    same = [
        {"id": sid, "passage_id": pid, "order_index": 1, "sentence_text": "Practice makes perfect. ", "word_count": 3, "remarks": "updated"}
    ]
    stats = tmp_db.replace_passage_sentences(pid, same)
    assert stats["updated"] == 1
    assert stats["text_changed"] == 0

    with tmp_db.get_connection() as conn:
        count = conn.execute("SELECT COUNT(*) FROM sentence_grammar_annotations WHERE sentence_id = ? AND source_type = 'AI'", (sid,)).fetchone()[0]
        assert count == 1
