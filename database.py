"""
05-gichul_db: SQLite 데이터베이스 모듈
- SQLite를 활용한 로컬 단일 파일(gichul.db) 데이터베이스
- 시험지(exams), 지문(passages), 문장(sentences), 태그(tags) 테이블 관리
- FTS5(Full-Text Search) 전문 검색 지원
"""

import sqlite3
import os
import json
from datetime import datetime
from typing import List, Dict, Optional, Any

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "gichul.db")


def get_connection() -> sqlite3.Connection:
    """SQLite 데이터베이스 연결 반환 (ROW 딕셔너리 팩토리 적용)"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db():
    """데이터베이스 테이블 및 FTS5 가상 테이블 초기화"""
    with get_connection() as conn:
        cursor = conn.cursor()

        # 1. 시험지 마스터 테이블
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS exams (
                id TEXT PRIMARY KEY,               -- e.g. '고3-2024년-06월'
                grade TEXT NOT NULL,              -- e.g. '고3'
                year INTEGER NOT NULL,            -- e.g. 2024
                month INTEGER NOT NULL,           -- e.g. 6
                exam_type TEXT DEFAULT '평가원',   -- e.g. '평가원', '교육청', '수능'
                reading_start_q INTEGER DEFAULT 18,
                reading_end_q INTEGER DEFAULT 45,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # 2. 지문 / 문항 테이블
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS passages (
                id TEXT PRIMARY KEY,               -- e.g. '고3-2024년-06월-21번'
                exam_id TEXT NOT NULL,
                q_num INTEGER NOT NULL,
                question_title TEXT,              -- 발문 (e.g. '21. 밑줄 친 부분이 의미하는 바로...')
                question_type TEXT,               -- 문제 유형 (e.g. '빈칸', '어휘함축' 등)
                passage_text TEXT NOT NULL,       -- txt 변환 순수 영문 지문 본문
                answer_text TEXT,                 -- 정답 번호 (e.g. '③')
                explanation_text TEXT,            -- HWP 추출 정답 및 해설/해석
                pdf_crop_image TEXT,              -- PDF 문항 크롭 이미지 경로
                validation_ratio REAL DEFAULT 1.0,-- HWP-PDF 일치율 (0.0 ~ 1.0)
                remarks TEXT,                     -- 비고
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (exam_id) REFERENCES exams (id) ON DELETE CASCADE
            );
        """)

        # 기존 테이블에 question_type 컬럼이 없는 경우 안전 마이그레이션
        try:
            cursor.execute("ALTER TABLE passages ADD COLUMN question_type TEXT;")
        except sqlite3.OperationalError:
            pass  # 이미 컬럼이 존재함

        # 3. 문장 테이블
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sentences (
                id TEXT PRIMARY KEY,               -- e.g. '고3-2024년-06월-21번-1번째 문장'
                passage_id TEXT NOT NULL,
                order_index INTEGER NOT NULL,     -- 1, 2, 3...
                sentence_text TEXT NOT NULL,      -- 개별 영문 문장
                word_count INTEGER DEFAULT 0,
                remarks TEXT,
                FOREIGN KEY (passage_id) REFERENCES passages (id) ON DELETE CASCADE
            );
        """)

        # sentences 테이블에 is_starred 컬럼 안전 마이그레이션
        try:
            cursor.execute("ALTER TABLE sentences ADD COLUMN is_starred INTEGER DEFAULT 0;")
        except sqlite3.OperationalError:
            pass  # 이미 컬럼이 존재함

        # 4. 지문 태그 테이블
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS passage_tags (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                passage_id TEXT NOT NULL,
                tag_name TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE (passage_id, tag_name),
                FOREIGN KEY (passage_id) REFERENCES passages (id) ON DELETE CASCADE
            );
        """)

        # 5. 문장 태그 테이블
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sentence_tags (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sentence_id TEXT NOT NULL,
                tag_name TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE (sentence_id, tag_name),
                FOREIGN KEY (sentence_id) REFERENCES sentences (id) ON DELETE CASCADE
            );
        """)

        # 6. 문장 어법 범주 분석 테이블 (다대다 어법 태깅 & AI 해설)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sentence_grammar_annotations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sentence_id TEXT NOT NULL,
                category_id INTEGER NOT NULL,          -- grammar_categories.json의 id (1~243)
                pos TEXT NOT NULL,                     -- 대분류 (명사, 동사, 특수구문 등)
                full_path TEXT NOT NULL,               -- 전체 계층 경로
                leaf_name TEXT NOT NULL,               -- 최하위 범주명
                target_expression TEXT,                -- 문장 내 해당 표현 (하이라이트용)
                explanation TEXT,                      -- AI 어법 해설
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE (sentence_id, category_id),
                FOREIGN KEY (sentence_id) REFERENCES sentences (id) ON DELETE CASCADE
            );
        """)

        # 7. 시스템 설정 테이블 (AI API 키, 선택된 모델 등 로컬 저장)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS app_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # 인덱스 생성
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_passages_exam ON passages(exam_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_sentences_passage ON sentences(passage_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_passage_tags_tag ON passage_tags(tag_name);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_sentence_tags_tag ON sentence_tags(tag_name);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_s_grammar_cat ON sentence_grammar_annotations(category_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_s_grammar_pos ON sentence_grammar_annotations(pos);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_sentences_starred ON sentences(is_starred);")

        conn.commit()


# --- CRUD 및 검색 헬퍼 함수 ---

def save_exam(exam_data: dict) -> str:
    """시험지 정보 저장 (기존 존재 시 갱신)"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO exams (id, grade, year, month, exam_type, reading_start_q, reading_end_q)
            VALUES (:id, :grade, :year, :month, :exam_type, :reading_start_q, :reading_end_q)
            ON CONFLICT(id) DO UPDATE SET
                grade = excluded.grade,
                year = excluded.year,
                month = excluded.month,
                exam_type = excluded.exam_type,
                reading_start_q = excluded.reading_start_q,
                reading_end_q = excluded.reading_end_q
        """, exam_data)
        conn.commit()
        return exam_data["id"]


def save_passage(passage_data: dict) -> str:
    """지문 정보 저장"""
    if "question_type" not in passage_data:
        passage_data["question_type"] = ""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO passages (
                id, exam_id, q_num, question_title, question_type, passage_text,
                answer_text, explanation_text, pdf_crop_image, validation_ratio, remarks
            )
            VALUES (
                :id, :exam_id, :q_num, :question_title, :question_type, :passage_text,
                :answer_text, :explanation_text, :pdf_crop_image, :validation_ratio, :remarks
            )
            ON CONFLICT(id) DO UPDATE SET
                question_title = excluded.question_title,
                question_type = excluded.question_type,
                passage_text = excluded.passage_text,
                answer_text = excluded.answer_text,
                explanation_text = excluded.explanation_text,
                pdf_crop_image = excluded.pdf_crop_image,
                validation_ratio = excluded.validation_ratio,
                remarks = excluded.remarks
        """, passage_data)
        conn.commit()
        return passage_data["id"]


def update_passage_question_type(passage_id: str, question_type: str) -> bool:
    """지문의 문제 유형 업데이트"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE passages SET question_type = ? WHERE id = ?",
            (question_type.strip(), passage_id.strip())
        )
        conn.commit()
        return cursor.rowcount > 0


def save_sentences(sentences: List[dict]):
    """문장 목록 일괄 저장"""
    with get_connection() as conn:
        cursor = conn.cursor()
        for s in sentences:
            cursor.execute("""
                INSERT INTO sentences (id, passage_id, order_index, sentence_text, word_count, remarks)
                VALUES (:id, :passage_id, :order_index, :sentence_text, :word_count, :remarks)
                ON CONFLICT(id) DO UPDATE SET
                    sentence_text = excluded.sentence_text,
                    word_count = excluded.word_count,
                    remarks = excluded.remarks
            """, s)
        conn.commit()


def add_passage_tag(passage_id: str, tag_name: str) -> bool:
    """지문 태그 추가"""
    tag_name = tag_name.strip()
    if not tag_name:
        return False
    with get_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO passage_tags (passage_id, tag_name) VALUES (?, ?)",
                (passage_id, tag_name)
            )
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False


def remove_passage_tag(passage_id: str, tag_name: str) -> bool:
    """지문 태그 삭제"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "DELETE FROM passage_tags WHERE passage_id = ? AND tag_name = ?",
            (passage_id, tag_name)
        )
        conn.commit()
        return cursor.rowcount > 0


def add_sentence_tag(sentence_id: str, tag_name: str) -> bool:
    """문장 태그 추가"""
    tag_name = tag_name.strip()
    if not tag_name:
        return False
    with get_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO sentence_tags (sentence_id, tag_name) VALUES (?, ?)",
                (sentence_id, tag_name)
            )
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False


def remove_sentence_tag(sentence_id: str, tag_name: str) -> bool:
    """문장 태그 삭제"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "DELETE FROM sentence_tags WHERE sentence_id = ? AND tag_name = ?",
            (sentence_id, tag_name)
        )
        conn.commit()
        return cursor.rowcount > 0


def get_passage_tags(passage_id: str) -> List[str]:
    """특정 지문의 태그 목록 조회"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT tag_name FROM passage_tags WHERE passage_id = ? ORDER BY id ASC",
            (passage_id,)
        )
        return [row["tag_name"] for row in cursor.fetchall()]


def get_sentence_tags(sentence_id: str) -> List[str]:
    """특정 문장의 태그 목록 조회"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT tag_name FROM sentence_tags WHERE sentence_id = ? ORDER BY id ASC",
            (sentence_id,)
        )
        return [row["tag_name"] for row in cursor.fetchall()]


def search_passages(
    keyword: str = "",
    grade: str = "",
    year: Optional[int] = None,
    month: Optional[int] = None,
    exam_type: str = "",
    question_type: str = "",
    tag: str = "",
    limit: int = 50
) -> List[Dict[str, Any]]:
    """지문 검색 (지문 본문, 발문, 해설, 출처, 태그, 문제유형, 시험구분)"""
    query = """
        SELECT p.*, e.grade, e.year, e.month, e.exam_type
        FROM passages p
        JOIN exams e ON p.exam_id = e.id
        WHERE 1=1
    """
    params = []

    if keyword:
        kw = f"%{keyword.strip()}%"
        query += """
            AND (
                p.id LIKE ? OR
                p.passage_text LIKE ? OR
                p.question_title LIKE ? OR
                p.explanation_text LIKE ?
            )
        """
        params.extend([kw, kw, kw, kw])

    if grade:
        query += " AND e.grade = ?"
        params.append(grade)
    if year:
        query += " AND e.year = ?"
        params.append(year)
    if month:
        query += " AND e.month = ?"
        params.append(month)
    if exam_type:
        query += " AND e.exam_type = ?"
        params.append(exam_type)
    if question_type:
        query += " AND p.question_type = ?"
        params.append(question_type)

    if tag:
        query += """
            AND p.id IN (SELECT passage_id FROM passage_tags WHERE tag_name LIKE ?)
        """
        params.append(f"%{tag.strip()}%")

    query += " ORDER BY e.year DESC, e.month DESC, p.q_num ASC LIMIT ?"
    params.append(limit)

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        rows = cursor.fetchall()
        results = []
        for r in rows:
            p_dict = dict(r)
            p_dict["tags"] = get_passage_tags(r["id"])
            results.append(p_dict)
        return results


def toggle_sentence_star(sentence_id: str) -> int:
    """문장 별표(중요 문장) 플래그 토글 (0 -> 1, 1 -> 0) 후 새 상태 반환"""
    clean_id = sentence_id.strip()
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT is_starred FROM sentences WHERE id = ?", (clean_id,))
        row = cursor.fetchone()
        if not row:
            return 0
        current_state = row["is_starred"] if row["is_starred"] is not None else 0
        new_state = 0 if current_state == 1 else 1
        cursor.execute("UPDATE sentences SET is_starred = ? WHERE id = ?", (new_state, clean_id))
        conn.commit()
        return new_state


def save_grammar_annotations(sentence_id: str, annotations: List[Dict[str, Any]]):
    """문장의 어법 범주 분석 결과 저장 (기존 AI 분석 결과 교체, 수동 등록 어법 보존)"""
    clean_id = sentence_id.strip()
    if not clean_id.startswith("["):
        clean_id = f"[{clean_id}]"
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM sentence_grammar_annotations WHERE sentence_id = ? AND (explanation IS NULL OR explanation NOT LIKE '수동 등록%')", (clean_id,))
        for anno in annotations:
            try:
                cursor.execute("""
                    INSERT OR REPLACE INTO sentence_grammar_annotations 
                    (sentence_id, category_id, pos, full_path, leaf_name, target_expression, explanation)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    clean_id,
                    anno.get("category_id", 0),
                    anno.get("pos", ""),
                    anno.get("full_path", ""),
                    anno.get("leaf_name", "") or anno.get("leaf", ""),
                    anno.get("target_expression", ""),
                    anno.get("explanation", "")
                ))
            except Exception:
                pass
        conn.commit()


def add_sentence_grammar_annotation(sentence_id: str, annotation: Dict[str, Any]) -> bool:
    """문장에 어법 범주 단일 수동 추가"""
    clean_id = sentence_id.strip()
    if not clean_id.startswith("["):
        clean_id = f"[{clean_id}]"
    cat_id = annotation.get("category_id", 0)
    pos = annotation.get("pos", "")
    full_path = annotation.get("full_path", "")
    leaf_name = annotation.get("leaf_name", "") or annotation.get("leaf", "")
    target_expression = annotation.get("target_expression", "")
    explanation = annotation.get("explanation", "수동 등록")

    # category_id가 0일 경우 leaf_name 기반 고유 가상 ID 생성
    if not cat_id or cat_id == 0:
        cat_id = 10000 + (abs(hash(leaf_name)) % 90000)

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO sentence_grammar_annotations 
            (sentence_id, category_id, pos, full_path, leaf_name, target_expression, explanation)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (clean_id, cat_id, pos, full_path, leaf_name, target_expression, explanation))
        conn.commit()
        return True


def delete_sentence_grammar_annotation(sentence_id: str, identifier: int) -> bool:
    """문장에서 특정 어법 범주 삭제 (category_id 또는 annotation row id 기준)"""
    clean_id = sentence_id.strip()
    if not clean_id.startswith("["):
        clean_id = f"[{clean_id}]"
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            DELETE FROM sentence_grammar_annotations 
            WHERE sentence_id = ? AND (category_id = ? OR id = ?)
        """, (clean_id, identifier, identifier))
        conn.commit()
        return True


def get_sentence_grammar_annotations(sentence_id: str) -> List[Dict[str, Any]]:
    """특정 문장의 어법 범주 분석 목록 조회"""
    clean_id = sentence_id.strip()
    if not clean_id.startswith("["):
        clean_id = f"[{clean_id}]"
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, category_id, pos, full_path, leaf_name, target_expression, explanation
            FROM sentence_grammar_annotations
            WHERE sentence_id = ?
            ORDER BY id ASC
        """, (clean_id,))
        return [dict(r) for r in cursor.fetchall()]


def set_sentence_grammar_annotations(sentence_id: str, annotations: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """문장의 어법 범주 목록을 일괄 설정 (기존 항목 교체)"""
    clean_id = sentence_id.strip()
    if not clean_id.startswith("["):
        clean_id = f"[{clean_id}]"

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM sentence_grammar_annotations WHERE sentence_id = ?", (clean_id,))
        for anno in annotations:
            cat_id = anno.get("category_id", 0)
            leaf_name = anno.get("leaf_name", "") or anno.get("leaf", "")
            if not cat_id or cat_id == 0:
                cat_id = 10000 + (abs(hash(leaf_name)) % 90000)
            try:
                cursor.execute("""
                    INSERT OR REPLACE INTO sentence_grammar_annotations 
                    (sentence_id, category_id, pos, full_path, leaf_name, target_expression, explanation)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    clean_id,
                    cat_id,
                    anno.get("pos", ""),
                    anno.get("full_path", ""),
                    leaf_name,
                    anno.get("target_expression", ""),
                    anno.get("explanation", "수동 등록")
                ))
            except Exception:
                pass
        conn.commit()

    return get_sentence_grammar_annotations(clean_id)



def get_setting(key: str, default: str = "") -> str:
    """앱 설정값 조회"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM app_settings WHERE key = ?", (key,))
        row = cursor.fetchone()
        return row["value"] if row else default


def set_setting(key: str, value: str):
    """앱 설정값 저장/갱신"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO app_settings (key, value, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = CURRENT_TIMESTAMP
        """, (key, value))
        conn.commit()


def search_sentences(
    keyword: str = "",
    passage_id: str = "",
    grade: str = "",
    year: Optional[int] = None,
    month: Optional[int] = None,
    exam_type: str = "",
    tag: str = "",
    is_starred: Optional[bool] = None,
    grammar_cat_id: Optional[int] = None,
    grammar_pos: Optional[str] = None,
    limit: int = 100
) -> List[Dict[str, Any]]:
    """문장 검색 (1행 테이블 뷰용)"""
    query = """
        SELECT s.*, p.q_num, e.grade, e.year, e.month, e.exam_type
        FROM sentences s
        JOIN passages p ON s.passage_id = p.id
        JOIN exams e ON p.exam_id = e.id
        WHERE 1=1
    """
    params = []

    if passage_id:
        clean_pid = passage_id.strip()
        if not clean_pid.startswith("["):
            clean_pid = f"[{clean_pid}]"
        query += " AND s.passage_id = ?"
        params.append(clean_pid)

    if keyword:
        kw = f"%{keyword.strip()}%"
        query += " AND (s.sentence_text LIKE ? OR s.id LIKE ?)"
        params.extend([kw, kw])

    if grade:
        query += " AND e.grade = ?"
        params.append(grade)
    if year:
        query += " AND e.year = ?"
        params.append(year)
    if month:
        query += " AND e.month = ?"
        params.append(month)
    if exam_type:
        query += " AND e.exam_type = ?"
        params.append(exam_type)

    if is_starred is True:
        query += " AND s.is_starred = 1"

    if grammar_cat_id:
        query += """
            AND s.id IN (SELECT sentence_id FROM sentence_grammar_annotations WHERE category_id = ?)
        """
        params.append(grammar_cat_id)
    elif grammar_pos:
        query += """
            AND s.id IN (SELECT sentence_id FROM sentence_grammar_annotations WHERE pos = ?)
        """
        params.append(grammar_pos.strip())

    if tag:
        query += """
            AND s.id IN (SELECT sentence_id FROM sentence_tags WHERE tag_name LIKE ?)
        """
        params.append(f"%{tag.strip()}%")

    query += " ORDER BY e.year DESC, e.month DESC, p.q_num ASC, s.order_index ASC LIMIT ?"
    params.append(limit)

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        rows = cursor.fetchall()
        results = []
        for idx, r in enumerate(rows, 1):
            s_dict = dict(r)
            s_dict["row_num"] = idx
            s_dict["is_starred"] = 1 if r["is_starred"] == 1 else 0
            s_dict["tags"] = get_sentence_tags(r["id"])
            s_dict["grammar_annotations"] = get_sentence_grammar_annotations(r["id"])
            results.append(s_dict)
        return results


def get_db_stats() -> Dict[str, Any]:
    """데이터베이스 현황 통계 반환"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM exams")
        total_exams = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM passages")
        total_passages = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM sentences")
        total_sentences = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(DISTINCT tag_name) FROM (SELECT tag_name FROM passage_tags UNION SELECT tag_name FROM sentence_tags)")
        total_tags = cursor.fetchone()[0]

        return {
            "exams": total_exams,
            "passages": total_passages,
            "sentences": total_sentences,
            "tags": total_tags
        }


# 모듈 로드 시 DB 자동 초기화
init_db()
