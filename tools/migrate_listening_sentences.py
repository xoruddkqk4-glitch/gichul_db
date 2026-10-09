"""
tools/migrate_listening_sentences.py
기존 DB의 듣기 문항(area='listening') 대본을 문장 단위로 분할하여 sentences 테이블 및 sentences_fts에 일괄 적재하는 마이그레이션 스크립트
"""

import os
import sys
import time
import sqlite3
import re

# 루트 디렉토리를 sys.path에 추가
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from gichul import paths
from gichul.sentence_tokenizer import create_script_sentence_records


def migrate():
    db_path = paths.DB_PATH
    if not os.path.exists(db_path):
        print(f"[Error] DB 파일을 찾을 수 없습니다: {db_path}")
        return

    print(f"=== 듣기 대본 문장(sentences) 일괄 마이그레이션 시작 ===")
    print(f"DB 경로: {db_path}")

    start_time = time.time()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # 1. 듣기 문항 조회
    cursor.execute("""
        SELECT id, script_text, passage_text 
        FROM passages 
        WHERE area = 'listening'
        ORDER BY id
    """)
    rows = cursor.fetchall()
    total_passages = len(rows)
    print(f"총 듣기 문항 수: {total_passages}건")

    total_sentences_created = 0
    skipped_passages = 0
    batch_records = []
    processed_count = 0

    insert_sql = """
        INSERT INTO sentences (id, passage_id, order_index, sentence_text, word_count, remarks)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            passage_id = excluded.passage_id,
            order_index = excluded.order_index,
            sentence_text = excluded.sentence_text,
            word_count = excluded.word_count,
            remarks = excluded.remarks
    """

    for r in rows:
        p_id = r["id"]
        script = (r["script_text"] or "").strip()
        # script_text가 없고 passage_text에 영문 대본이 있는 경우 보완
        if not script and r["passage_text"]:
            p_text = r["passage_text"].strip()
            # 영단어가 15개 이상이고 한글 발문 형태만 있는 것이 아닌 경우
            eng_words = re.findall(r"[a-zA-Z]{2,}", p_text)
            if len(eng_words) >= 10:
                script = p_text

        if not script:
            skipped_passages += 1
            continue

        records = create_script_sentence_records(p_id, script)
        if not records:
            skipped_passages += 1
            continue

        for rec in records:
            batch_records.append((
                rec["id"],
                rec["passage_id"],
                rec["order_index"],
                rec["sentence_text"],
                rec["word_count"],
                rec["remarks"]
            ))

        processed_count += 1
        total_sentences_created += len(records)

        # 500개 지문마다 커밋
        if len(batch_records) >= 5000:
            cursor.executemany(insert_sql, batch_records)
            conn.commit()
            batch_records = []
            print(f"  진행 중... 처리 지문: {processed_count}/{total_passages} (누적 문장: {total_sentences_created})")

    # 남은 레코드 커밋
    if batch_records:
        cursor.executemany(insert_sql, batch_records)
        conn.commit()

    elapsed = time.time() - start_time
    print(f"\n=== 마이그레이션 완료 ===")
    print(f"처리된 지문: {processed_count}건 (대본 없음 스킵: {skipped_passages}건)")
    print(f"생성 및 적재된 총 듣기 문장: {total_sentences_created}건")
    print(f"소요 시간: {elapsed:.2f}초")

    # 검증: DB 통계 확인
    cursor.execute("""
        SELECT COUNT(*) FROM sentences s
        JOIN passages p ON s.passage_id = p.id
        WHERE p.area = 'listening'
    """)
    db_listening_sentences = cursor.fetchone()[0]

    cursor.execute("""
        SELECT COUNT(*) FROM sentences_fts
        WHERE sentence_id IN (
            SELECT id FROM sentences WHERE remarks LIKE '듣기 대본%'
        )
    """)
    fts_listening_count = cursor.fetchone()[0]

    print(f"\n[검증 결과]")
    print(f"- sentences 테이블 내 듣기 문장 수: {db_listening_sentences}건")
    print(f"- sentences_fts 테이블 내 색인 수: {fts_listening_count}건")

    conn.close()


if __name__ == "__main__":
    migrate()
