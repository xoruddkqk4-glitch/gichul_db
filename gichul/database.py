"""
05-gichul_db: SQLite 데이터베이스 모듈
- SQLite를 활용한 로컬 단일 파일(gichul.db) 데이터베이스
- 시험지(exams), 지문(passages), 문장(sentences), 태그(tags) 테이블 관리
- FTS5(Full-Text Search) 전문 검색 지원
"""

import sqlite3
import os
import json
import re
from contextlib import contextmanager
from datetime import datetime
from typing import List, Dict, Optional, Any
from collections import defaultdict

from . import paths
from . import access
from .logging_config import get_logger
from .text_utils import (
    normalize_bracket_id, apply_answer_header,
    extract_answer_num, extract_choices, fill_blanks,
    split_choice_parts, _CHOICE_PART_SPLIT_PATTERN, _BLANK_PATTERN,
)

logger = get_logger("gichul.database")
DB_PATH = os.environ.get("GICHUL_DB_PATH") or paths.DB_PATH


def get_db_path() -> str:
    """런타임 DB 경로 반환 (테스트 시 GICHUL_DB_PATH 환경변수로 동적 교체 지원)"""
    return os.environ.get("GICHUL_DB_PATH") or DB_PATH


def _regexp_func(expr: Optional[str], item: Optional[str]) -> bool:
    """SQLite REGEXP 커스텀 함수 (대소문자 무시 단어 경계/정규식 매칭)"""
    if expr is None or item is None:
        return False
    try:
        return bool(re.search(expr, item, re.IGNORECASE))
    except Exception:
        return False


class _ClosingConnection(sqlite3.Connection):
    """`with get_connection() as conn:` 블록이 끝나면 commit/rollback 후 연결까지 닫는 연결 클래스.

    기본 sqlite3.Connection의 with 블록은 트랜잭션만 끝내고 연결은 열어 둔다.
    기존 사용처(50여 곳)를 고치지 않고도 연결이 쌓이지 않도록 여기서 닫는다.
    """
    def __exit__(self, exc_type, exc, tb):
        try:
            return super().__exit__(exc_type, exc, tb)  # 성공 시 commit, 예외 시 rollback
        finally:
            self.close()


def get_connection() -> sqlite3.Connection:
    """SQLite 데이터베이스 연결 반환 (ROW 딕셔너리 팩토리 및 REGEXP 함수 등록)

    - with 블록이 끝나면 연결이 자동으로 닫힌다 (_ClosingConnection)
    - timeout=15: 라우트가 스레드풀에서 동시에 실행되므로, 다른 쓰기가 끝날 때까지 최대 15초 기다린다
    - journal_mode=WAL은 DB 파일에 영구 저장되는 설정이라 init_db()에서 한 번만 설정한다
    """
    conn = sqlite3.connect(get_db_path(), timeout=15, factory=_ClosingConnection)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA synchronous = NORMAL;")
    conn.execute("PRAGMA cache_size = -64000;")
    conn.execute("PRAGMA mmap_size = 268435456;")
    conn.execute("PRAGMA temp_store = MEMORY;")
    conn.create_function("REGEXP", 2, _regexp_func)
    return conn


@contextmanager
def transaction():
    """여러 저장 함수를 하나의 트랜잭션으로 묶는다. 블록이 예외 없이 끝나면 commit, 예외면 전부 rollback.

    사용 예:
        with db.transaction() as conn:
            db.save_exam(exam, conn=conn)
            db.save_passage(p, conn=conn)
    """
    with get_connection() as conn:
        yield conn


@contextmanager
def _use_conn(conn: Optional[sqlite3.Connection] = None):
    """conn이 주어지면 그대로 쓴다(commit은 호출한 쪽 트랜잭션 담당).
    없으면 새 연결을 열고, 블록이 끝나면 commit 후 닫는다."""
    if conn is not None:
        yield conn
    else:
        with get_connection() as own_conn:
            yield own_conn


def init_db():
    """데이터베이스 테이블 및 FTS5 가상 테이블 초기화"""
    with get_connection() as conn:
        # WAL은 DB 파일에 영구 저장되는 설정이므로 연결마다가 아니라 여기서 한 번만 지정한다
        conn.execute("PRAGMA journal_mode = WAL;")
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

        # passages 테이블에 correct_rate 및 choice_rates 컬럼 안전 마이그레이션
        try:
            cursor.execute("ALTER TABLE passages ADD COLUMN correct_rate REAL DEFAULT NULL;")
        except sqlite3.OperationalError:
            pass

        try:
            cursor.execute("ALTER TABLE passages ADD COLUMN choice_rates TEXT DEFAULT NULL;")
        except sqlite3.OperationalError:
            pass

        # 정답 출처 및 검증 상태 (verified_key / csv / image_consensus 만 검증 인정)
        for col_sql in (
            "ALTER TABLE passages ADD COLUMN answer_source TEXT;",
            "ALTER TABLE passages ADD COLUMN answer_verified INTEGER DEFAULT 0;",
            "ALTER TABLE passages ADD COLUMN area TEXT DEFAULT 'reading';",
            "ALTER TABLE passages ADD COLUMN script_crop_image TEXT DEFAULT NULL;",
            "ALTER TABLE passages ADD COLUMN script_text TEXT DEFAULT NULL;",
            "ALTER TABLE passages ADD COLUMN fels_text TEXT DEFAULT NULL;",
            "ALTER TABLE passages ADD COLUMN audio_file_path TEXT DEFAULT NULL;",
            "ALTER TABLE passages ADD COLUMN user_memo TEXT DEFAULT '';",
            "ALTER TABLE passages ADD COLUMN user_memo_updated_at TIMESTAMP DEFAULT NULL;",
            "ALTER TABLE exams ADD COLUMN listening_start_q INTEGER DEFAULT 1;",
            "ALTER TABLE exams ADD COLUMN listening_end_q INTEGER DEFAULT 17;",
            "ALTER TABLE exams ADD COLUMN subtype TEXT DEFAULT NULL;",
        ):
            try:
                cursor.execute(col_sql)
            except sqlite3.OperationalError:
                pass

        # 기존 지문들의 기본 area를 'reading'으로 보정
        try:
            cursor.execute("UPDATE passages SET area = 'reading' WHERE area IS NULL OR area = '';")
        except Exception:
            logger.debug("Failed to set default area to reading", exc_info=True)

        # 빈 문제 유형을 '기타'로 자동 보정
        try:
            cursor.execute("UPDATE passages SET question_type = '기타' WHERE question_type IS NULL OR question_type = '' OR trim(question_type) = '';")
        except Exception:
            logger.debug("Failed to set default question_type to 기타", exc_info=True)

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

        # sentences 테이블에 grammar_analyzed 컬럼 안전 마이그레이션 (0: 미분석, 1: 분석 완료)
        try:
            cursor.execute("ALTER TABLE sentences ADD COLUMN grammar_analyzed INTEGER DEFAULT 0;")
        except sqlite3.OperationalError:
            pass  # 이미 컬럼이 존재함

        # 7. 시스템 설정 테이블 (AI API 키, 선택된 모델 등 로컬 저장)
        #    아래 마이그레이션 버전(db_migration_version)을 여기서 읽으므로, 새 DB에서도 먼저 만들어 둔다
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS app_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # 일회성 데이터 마이그레이션 버전 관리 (기동 시 7만 문장/1.3만 지문 반복 전수 순회 차단 -> 0.05초 즉각 기동)
        cursor.execute("SELECT value FROM app_settings WHERE key = 'db_migration_version'")
        mig_row = cursor.fetchone()
        mig_ver = int(mig_row["value"]) if (mig_row and str(mig_row["value"]).isdigit()) else 0

        if mig_ver < 1:
            try:
                cursor.execute("""
                    UPDATE sentences 
                    SET grammar_analyzed = 1 
                    WHERE id IN (SELECT DISTINCT sentence_id FROM sentence_grammar_annotations)
                """)
            except Exception:
                logger.debug("Failed to set grammar_analyzed flag in migration", exc_info=True)

            try:
                cursor.execute("SELECT id, passage_id, sentence_text FROM sentences WHERE sentence_text LIKE '%\\_\\_%' ESCAPE '\\'")
                unfilled_rows = cursor.fetchall()
                if unfilled_rows:
                    # 지문 정보는 같은 트랜잭션에서 읽어 text_utils.fill_blanks 로 직접 채운다
                    # (grammar_analyzer 역방향 import 및 별도 연결로 DB를 다시 여는 일을 없앰)
                    for ur in unfilled_rows:
                        cur_p = None
                        pid = ur["passage_id"]
                        if pid:
                            cursor.execute("SELECT passage_text, answer_text, explanation_text FROM passages WHERE id = ?", (pid,))
                            p_row = cursor.fetchone()
                            if p_row:
                                cur_p = dict(p_row)
                        prep_text = fill_blanks(
                            ur["sentence_text"],
                            (cur_p.get("passage_text") or "") if cur_p else "",
                            (cur_p.get("answer_text") or "") if cur_p else "",
                            (cur_p.get("explanation_text") or "") if cur_p else ""
                        )
                        if prep_text and prep_text != ur["sentence_text"]:
                            words = re.findall(r"\b[\w'-]+\b", prep_text)
                            cursor.execute(
                                "UPDATE sentences SET sentence_text = ?, word_count = ? WHERE id = ?",
                                (prep_text.strip(), len(words), ur["id"])
                            )
            except Exception as mig_err:
                logger.error("[Init DB Blank Sentence Migration Error] %s", mig_err, exc_info=True)

            try:
                cursor.execute("SELECT id, answer_text, explanation_text FROM passages WHERE answer_text IS NOT NULL AND TRIM(answer_text) != '' AND explanation_text IS NOT NULL")
                p_rows = cursor.fetchall()
                for pr in p_rows:
                    ans = pr["answer_text"].strip()
                    exp = pr["explanation_text"] or ""
                    if not exp:
                        continue
                    m = re.search(r"^\s*\[\s*정답\s*\]\s*([①②③④⑤1-5]?)", exp)
                    if m:
                        cur_ans = m.group(1)
                        if cur_ans != ans:
                            new_exp = apply_answer_header(exp, ans)
                            cursor.execute("UPDATE passages SET explanation_text = ? WHERE id = ?", (new_exp, pr["id"]))
                    else:
                        new_exp = apply_answer_header(exp.strip(), ans)
                        cursor.execute("UPDATE passages SET explanation_text = ? WHERE id = ?", (new_exp, pr["id"]))
            except Exception as sync_err:
                logger.error("[Init DB Answer Sync Error] %s", sync_err, exc_info=True)

            cursor.execute("INSERT OR REPLACE INTO app_settings (key, value) VALUES ('db_migration_version', '1')")

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

        # sentence_grammar_annotations 테이블에 source_type, user_id, ai_model 컬럼 안전 마이그레이션
        for col_sql in (
            "ALTER TABLE sentence_grammar_annotations ADD COLUMN source_type TEXT DEFAULT 'AI';",
            "ALTER TABLE sentence_grammar_annotations ADD COLUMN user_id TEXT DEFAULT NULL;",
            "ALTER TABLE sentence_grammar_annotations ADD COLUMN ai_model TEXT DEFAULT NULL;",
        ):
            try:
                cursor.execute(col_sql)
            except sqlite3.OperationalError:
                pass

        # 기존 수동 등록 어법 데이터의 source_type을 'USER'로 안전 보정
        try:
            cursor.execute("UPDATE sentence_grammar_annotations SET source_type = 'USER' WHERE explanation LIKE '수동 등록%' AND (source_type IS NULL OR source_type = 'AI');")
        except Exception:
            logger.debug("Failed to set source_type to USER for manual annotations", exc_info=True)

        # 6-1. 사용자 커스텀 어법 체계 및 매핑 설정 테이블
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_grammar_settings (
                user_id TEXT PRIMARY KEY DEFAULT 'default_user',
                use_custom_tree INTEGER DEFAULT 0,
                custom_tree_json TEXT,
                custom_mapping_json TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # 8. 고속 복합 B-Tree 인덱스 생성
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_exams_filter ON exams(grade, year, month);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_passages_exam ON passages(exam_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_passages_exam_area ON passages(exam_id, area);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_passages_exam_qnum ON passages(exam_id, q_num);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_passages_type_area ON passages(question_type, area);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_passages_correct_rate ON passages(correct_rate);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_passages_area ON passages(area);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_sentences_passage ON sentences(passage_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_sentences_pid_order ON sentences(passage_id, order_index);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_sentences_starred ON sentences(is_starred);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_sentences_analyzed ON sentences(grammar_analyzed);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_s_grammar_sid ON sentence_grammar_annotations(sentence_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_s_grammar_cat ON sentence_grammar_annotations(category_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_s_grammar_pos ON sentence_grammar_annotations(pos);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_s_grammar_source ON sentence_grammar_annotations(sentence_id, source_type);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_s_grammar_user ON sentence_grammar_annotations(user_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_passage_tags_pid ON passage_tags(passage_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_passage_tags_tag ON passage_tags(tag_name);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_sentence_tags_sid ON sentence_tags(sentence_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_sentence_tags_tag ON sentence_tags(tag_name);")

        # 9. FTS5 전문 검색(Full-Text Search) 가상 테이블 및 자동 동기화 트리거
        try:
            cursor.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS passages_fts USING fts5(
                    passage_id UNINDEXED,
                    passage_text,
                    question_title,
                    explanation_text,
                    script_text,
                    tokenize='unicode61'
                );
            """)
            cursor.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS sentences_fts USING fts5(
                    sentence_id UNINDEXED,
                    sentence_text,
                    tokenize='unicode61'
                );
            """)

            # 트리거 등록 (신규 등록/수정/삭제 시 FTS5 자동 동기화)
            cursor.execute("""
                CREATE TRIGGER IF NOT EXISTS trg_sentences_ai AFTER INSERT ON sentences BEGIN
                    INSERT INTO sentences_fts(sentence_id, sentence_text) VALUES (new.id, new.sentence_text);
                END;
            """)
            cursor.execute("""
                CREATE TRIGGER IF NOT EXISTS trg_sentences_ad AFTER DELETE ON sentences BEGIN
                    DELETE FROM sentences_fts WHERE sentence_id = old.id;
                END;
            """)
            cursor.execute("""
                CREATE TRIGGER IF NOT EXISTS trg_passages_ai AFTER INSERT ON passages BEGIN
                    INSERT INTO passages_fts(passage_id, passage_text, question_title, explanation_text, script_text)
                    VALUES (new.id, new.passage_text, new.question_title, new.explanation_text, new.script_text);
                END;
            """)
            cursor.execute("""
                CREATE TRIGGER IF NOT EXISTS trg_passages_ad AFTER DELETE ON passages BEGIN
                    DELETE FROM passages_fts WHERE passage_id = old.id;
                END;
            """)
            # 갱신 트리거는 텍스트 컬럼이 바뀔 때만 동작하도록 교체한다 (구버전은 별표·메모·정답률 등 어떤 컬럼을 바꿔도 FTS 재색인)
            # CREATE TRIGGER IF NOT EXISTS는 기존 트리거를 바꾸지 않으므로, 정의가 다르면 지우고 다시 만든다
            _fts_update_triggers = {
                "trg_sentences_au": """
                    CREATE TRIGGER trg_sentences_au AFTER UPDATE OF sentence_text ON sentences BEGIN
                        DELETE FROM sentences_fts WHERE sentence_id = old.id;
                        INSERT INTO sentences_fts(sentence_id, sentence_text) VALUES (new.id, new.sentence_text);
                    END;
                """,
                "trg_passages_au": """
                    CREATE TRIGGER trg_passages_au AFTER UPDATE OF passage_text, question_title, explanation_text, script_text ON passages BEGIN
                        DELETE FROM passages_fts WHERE passage_id = old.id;
                        INSERT INTO passages_fts(passage_id, passage_text, question_title, explanation_text, script_text) 
                        VALUES (new.id, new.passage_text, new.question_title, new.explanation_text, new.script_text);
                    END;
                """,
            }
            for trg_name, trg_sql in _fts_update_triggers.items():
                row = cursor.execute(
                    "SELECT sql FROM sqlite_master WHERE type = 'trigger' AND name = ?", (trg_name,)
                ).fetchone()
                if row is None or "UPDATE OF" not in (row["sql"] or ""):
                    cursor.execute(f"DROP TRIGGER IF EXISTS {trg_name}")
                    cursor.execute(trg_sql)
                    logger.info("[Init DB] FTS 갱신 트리거 교체: %s (텍스트 컬럼 변경 시에만 재색인)", trg_name)
        except Exception as fts_err:
            logger.warning("[Init DB FTS5 Warning] %s", fts_err, exc_info=True)

        conn.commit()


# --- CRUD 및 검색 헬퍼 함수 ---

def save_exam(exam_data: dict, conn: Optional[sqlite3.Connection] = None) -> str:
    """시험지 정보 저장 (기존 존재 시 갱신). conn을 주면 호출한 쪽 트랜잭션에 참여한다."""
    if "listening_start_q" not in exam_data:
        exam_data["listening_start_q"] = 1
    if "listening_end_q" not in exam_data:
        exam_data["listening_end_q"] = 17
    if "subtype" not in exam_data:
        exam_data["subtype"] = None
    with _use_conn(conn) as c:
        cursor = c.cursor()
        cursor.execute("""
            INSERT INTO exams (id, grade, year, month, exam_type, subtype, reading_start_q, reading_end_q, listening_start_q, listening_end_q)
            VALUES (:id, :grade, :year, :month, :exam_type, :subtype, :reading_start_q, :reading_end_q, :listening_start_q, :listening_end_q)
            ON CONFLICT(id) DO UPDATE SET
                grade = excluded.grade,
                year = excluded.year,
                month = excluded.month,
                exam_type = excluded.exam_type,
                subtype = excluded.subtype,
                reading_start_q = excluded.reading_start_q,
                reading_end_q = excluded.reading_end_q,
                listening_start_q = excluded.listening_start_q,
                listening_end_q = excluded.listening_end_q
        """, exam_data)
    invalidate_exams_cache()
    return exam_data["id"]


_EXAMS_STATS_CACHE: Optional[List[Dict[str, Any]]] = None

def invalidate_exams_cache():
    """시험지 통계 캐시 무효화 (업로드, 삭제, 변경 시 호출)"""
    global _EXAMS_STATS_CACHE
    _EXAMS_STATS_CACHE = None

def get_all_exams_with_stats(force_refresh: bool = False) -> List[Dict[str, Any]]:
    """등록된 모든 시험지 목록 및 3대 데이터 영역(원본 파일, 코어 본문, 메타데이터) 통계 조회 (초고속 인메모리 캐시 지원)"""
    global _EXAMS_STATS_CACHE
    if not force_refresh and _EXAMS_STATS_CACHE is not None:
        return _EXAMS_STATS_CACHE

    import os, re
    uploads_dir = paths.UPLOADS_DIR
    captures_dir = paths.CAPTURES_DIR

    # 1. uploads/ 및 static/captures/ 디스크 파일을 1회 단일 스캔하여 (grade, year, month) 키로 사전 인덱싱 (0.04s)
    uploads_by_key = {}
    if os.path.exists(uploads_dir):
        for entry in os.scandir(uploads_dir):
            if entry.is_file():
                m = re.match(r"(고[1-3])[-_](\d{4})[-_](\d{1,2})", entry.name)
                if m:
                    k = (m.group(1), int(m.group(2)), int(m.group(3)))
                    if k not in uploads_by_key:
                        uploads_by_key[k] = []
                    try:
                        uploads_by_key[k].append((entry.name, entry.stat().st_size))
                    except Exception:
                        logger.debug("Failed to stat upload file %s", entry.name, exc_info=True)

    captures_by_key = {}
    if os.path.exists(captures_dir):
        for entry in os.scandir(captures_dir):
            if entry.is_file() and entry.name.endswith(".png"):
                m = re.match(r"(고[1-3])[-_](\d{4})[-_](\d{1,2})", entry.name)
                if m:
                    k = (m.group(1), int(m.group(2)), int(m.group(3)))
                    captures_by_key[k] = captures_by_key.get(k, 0) + 1

    with get_connection() as conn:
        cursor = conn.cursor()
        # 2. 시험지 메타정보 + 지문/문장 카운트 일괄 조회
        cursor.execute("""
            SELECT 
                e.id,
                e.grade,
                e.year,
                e.month,
                e.exam_type,
                e.subtype,
                e.reading_start_q,
                e.reading_end_q,
                e.created_at,
                COUNT(DISTINCT p.id) AS passage_count,
                COUNT(DISTINCT s.id) AS sentence_count
            FROM exams e
            LEFT JOIN passages p ON e.id = p.exam_id
            LEFT JOIN sentences s ON p.id = s.passage_id
            GROUP BY e.id
            ORDER BY e.year DESC, e.month DESC, e.grade ASC
        """)
        rows = cursor.fetchall()
        exams = [dict(r) for r in rows]

        # 3. 어법 분석 통계 일괄 집계 (1회 쿼리)
        cursor.execute("""
            SELECT p.exam_id, COUNT(DISTINCT a.id)
            FROM sentence_grammar_annotations a
            JOIN sentences s ON a.sentence_id = s.id
            JOIN passages p ON s.passage_id = p.id
            GROUP BY p.exam_id
        """)
        grammar_stats_map = dict(cursor.fetchall())

        # 4. 태그 통계 일괄 집계 (1회 쿼리)
        cursor.execute("SELECT p.exam_id, COUNT(*) FROM passage_tags pt JOIN passages p ON pt.passage_id = p.id GROUP BY p.exam_id")
        ptag_map = dict(cursor.fetchall())
        cursor.execute("SELECT p.exam_id, COUNT(*) FROM sentence_tags st JOIN sentences s ON st.sentence_id = s.id JOIN passages p ON s.passage_id = p.id GROUP BY p.exam_id")
        stag_map = dict(cursor.fetchall())

        # 5. 지문 정답 및 정답률 통계 일괄 집계 (1회 쿼리)
        cursor.execute("""
            SELECT 
                exam_id,
                COUNT(*) AS total_passages,
                SUM(CASE WHEN answer_text IS NOT NULL AND TRIM(answer_text) != '' THEN 1 ELSE 0 END) AS answered_passages,
                SUM(CASE WHEN correct_rate IS NOT NULL THEN 1 ELSE 0 END) AS rated_passages,
                AVG(correct_rate) AS avg_correct_rate
            FROM passages
            GROUP BY exam_id
        """)
        ans_stats_map = {r["exam_id"]: dict(r) for r in cursor.fetchall()}

        def _is_problem_pdf(fn: str) -> bool:
            fl = fn.lower()
            if not fl.endswith(".pdf"):
                return False
            if "_script" in fl or "대본" in fl or "_ans_" in fl or "_exp_" in fl:
                return False
            if re.search(r"[-_]A\.pdf$", fn, re.I):
                return False
            return True

        for ex in exams:
            eid = ex["id"]
            grade = ex["grade"]
            year = ex["year"]
            month = ex["month"]

            # 어법 및 태그
            ex["grammar_count"] = grammar_stats_map.get(eid, 0)
            ex["tag_count"] = ptag_map.get(eid, 0) + stag_map.get(eid, 0)

            # 원본 파일 매핑
            k = (grade, year, month)
            matching_files = uploads_by_key.get(k, [])
            if ex.get("subtype"):
                sub_key = ex["subtype"].replace("형", "")
                matching_files = [f for f in matching_files if re.search(rf"[-_\[\s]{sub_key}(?:형)?(?:[-_\]\s]|\.|$)", f[0], re.I)]

            raw_size = sum(f[1] for f in matching_files)
            raw_basenames = [f[0] for f in matching_files]
            ex["raw_file_count"] = len(matching_files)
            ex["raw_file_size_bytes"] = raw_size
            ex["raw_file_size_mb"] = round(raw_size / (1024 * 1024), 2)
            ex["raw_files"] = raw_basenames

            # 5대 파일 판별
            script_file = next((f for f in raw_basenames if f.lower().endswith(".pdf") and ("_script" in f.lower() or "대본" in f.lower())), None)
            exp_pdf_file = next((f for f in raw_basenames if f.lower().endswith(".pdf") and (re.search(r"[-_]A\.pdf$", f, re.I) or "_exp_" in f.lower() or "_exp.pdf" in f.lower())), None)
            script_target = script_file or exp_pdf_file
            script_type = "script" if script_file else ("exp_pdf" if exp_pdf_file else None)

            pdf_file = next((f for f in raw_basenames if _is_problem_pdf(f)), None)
            hwp_file = next((f for f in raw_basenames if f.lower().endswith((".hwp", ".hwpx")) and "_exp_" not in f), None)
            ans_file = next((f for f in raw_basenames if "_ans_" in f or f.lower().endswith((".png", ".jpg", ".jpeg"))), None)
            csv_file = next((f for f in raw_basenames if f.lower().endswith(".csv")), None)

            # 지문 정답/정답률
            ans_row = ans_stats_map.get(eid)
            total_passages = ans_row["total_passages"] if ans_row else 0
            answered_passages = ans_row["answered_passages"] if ans_row and ans_row["answered_passages"] else 0
            rated_passages = ans_row["rated_passages"] if ans_row and ans_row["rated_passages"] else 0
            avg_rate = round(ans_row["avg_correct_rate"], 1) if (ans_row and ans_row["avg_correct_rate"] is not None) else None

            ex["file_status"] = {
                "pdf": {
                    "exists": bool(pdf_file),
                    "filename": pdf_file or ""
                },
                "hwp": {
                    "exists": bool(hwp_file),
                    "filename": hwp_file or ""
                },
                "script": {
                    "exists": bool(script_target),
                    "filename": script_target or "",
                    "type": script_type,
                    "is_exp": bool(exp_pdf_file and not script_file)
                },
                "ans": {
                    "exists": bool(ans_file),
                    "filename": ans_file or "",
                    "answered_count": answered_passages,
                    "total_count": total_passages
                },
                "csv": {
                    "exists": bool(csv_file) or (rated_passages > 0),
                    "filename": csv_file or "",
                    "rated_count": rated_passages,
                    "total_count": total_passages,
                    "avg_rate": avg_rate
                }
            }

            # 캡처 개수
            ex["captures_count"] = captures_by_key.get(k, 0)

        _EXAMS_STATS_CACHE = exams
        return exams


def _format_size(size_bytes: int) -> str:
    if not size_bytes or size_bytes <= 0:
        return "0 B"
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.1f} MB"


def get_exam_raw_files(exam_id: str) -> Optional[Dict[str, Any]]:
    """
    특정 시험지에 해당하는 5종 원본 파일(문제 PDF, 해설 HWP, 대본 PDF, 정답 JSON/PNG, 정답률 CSV)의
    디스크 존재 여부, 파일명, 크기, 절대 경로 등을 조회하여 반환
    """
    clean_id = normalize_bracket_id(exam_id)

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, grade, year, month, exam_type, subtype FROM exams WHERE id = ?",
            (clean_id,)
        )
        exam = cursor.fetchone()
        if not exam:
            clean_search = clean_id.strip("[]")
            cursor.execute(
                "SELECT id, grade, year, month, exam_type, subtype FROM exams WHERE id LIKE ?",
                (f"%{clean_search}%",)
            )
            exam = cursor.fetchone()

    if not exam:
        return None

    exam = dict(exam)
    grade = exam["grade"]
    year = int(exam["year"])
    month = int(exam["month"])
    subtype = exam.get("subtype")

    uploads_dir = paths.UPLOADS_DIR
    keys_dir = paths.KEYS_DIR

    matched_entries = []
    prefix1 = f"{grade}_{year}_{month:02d}"
    prefix2 = f"{grade}_{year}_{month}"
    prefix3 = f"{grade}-{year}-{month:02d}"
    prefix4 = f"{grade}-{year}-{month}"

    if os.path.exists(uploads_dir):
        for entry in os.scandir(uploads_dir):
            if entry.is_file():
                fn = entry.name
                if fn.startswith(prefix1) or fn.startswith(prefix2) or fn.startswith(prefix3) or fn.startswith(prefix4):
                    if subtype:
                        sub_key = subtype.replace("형", "")
                        if not re.search(rf"[-_\[\s]{sub_key}(?:형)?(?:[-_\]\s]|\.|$)", fn, re.I):
                            continue
                    matched_entries.append(entry)

    # 1. 대본/해설 PDF
    script_entry = next((e for e in matched_entries if e.name.lower().endswith(".pdf") and ("_script" in e.name.lower() or "대본" in e.name.lower())), None)
    exp_pdf_entry = next((e for e in matched_entries if e.name.lower().endswith(".pdf") and (re.search(r"[-_]A\.pdf$", e.name, re.I) or "_exp_" in e.name.lower() or "_exp.pdf" in e.name.lower())), None)
    script_target = script_entry or exp_pdf_entry
    is_exp_script = bool(exp_pdf_entry and not script_entry)

    def _is_prob(fn: str) -> bool:
        fl = fn.lower()
        if not fl.endswith(".pdf"):
            return False
        if "_script" in fl or "대본" in fl or "_ans_" in fl or "_exp_" in fl:
            return False
        if re.search(r"[-_]A\.pdf$", fn, re.I):
            return False
        return True

    # 2. 문제 PDF
    pdf_entry = next((e for e in matched_entries if _is_prob(e.name)), None)

    # 3. 해설 HWP
    hwp_entry = next((e for e in matched_entries if e.name.lower().endswith((".hwp", ".hwpx")) and "_exp_" not in e.name.lower()), None)

    # 4. 정답표 (JSON or 이미지)
    ans_entry = next((e for e in matched_entries if "_ans_" in e.name.lower() or e.name.lower().endswith((".png", ".jpg", ".jpeg")) or (e.name.lower().endswith(".json") and ("_ans" in e.name.lower() or "ans_" in e.name.lower()))), None)
    ans_path = ans_entry.path if ans_entry else None
    if not ans_path:
        if subtype:
            sub_k = subtype.replace("형", "")
            cand1 = os.path.join(keys_dir, f"{grade}_{year}_{month:02d}_{sub_k}.json")
            cand2 = os.path.join(keys_dir, f"{grade}_{year}_{month:02d}_{subtype}.json")
            if os.path.exists(cand1):
                ans_path = cand1
            elif os.path.exists(cand2):
                ans_path = cand2
        if not ans_path:
            cand = os.path.join(keys_dir, f"{grade}_{year}_{month:02d}.json")
            if os.path.exists(cand):
                ans_path = cand

    # 5. 정답률 CSV
    csv_entry = next((e for e in matched_entries if e.name.lower().endswith(".csv")), None)

    def _file_info(p: Optional[str], type_label: str, is_exp: bool = False) -> Dict[str, Any]:
        exists = bool(p and os.path.exists(p))
        size = os.path.getsize(p) if exists else 0
        fn = os.path.basename(p) if exists else ""
        return {
            "exists": exists,
            "filename": fn,
            "abs_path": p if exists else "",
            "size_bytes": size,
            "size_formatted": _format_size(size) if exists else "",
            "type_label": type_label,
            "is_exp": is_exp
        }

    return {
        "exam_id": exam["id"],
        "grade": grade,
        "year": year,
        "month": month,
        "subtype": subtype,
        "exam_type": exam.get("exam_type", ""),
        "files": {
            "pdf": _file_info(pdf_entry.path if pdf_entry else None, "문제 PDF"),
            "hwp": _file_info(hwp_entry.path if hwp_entry else None, "해설 HWP"),
            "script": _file_info(script_target.path if script_target else None, "대본 PDF" if not is_exp_script else "해설(대본) PDF", is_exp=is_exp_script),
            "ans": _file_info(ans_path, "정답표 (JSON/이미지)"),
            "csv": _file_info(csv_entry.path if csv_entry else None, "정답률 CSV")
        }
    }


def selective_delete_exam(
    exam_id: str,
    delete_raw: bool = True,
    delete_core: bool = True,
    delete_metadata: bool = True,
    delete_rate: bool = False
) -> Dict[str, Any]:
    """
    모의고사 데이터를 4개 영역(원본 파일, 코어 본문, 메타데이터, 정답률 데이터)으로 구분하여 선택적으로 삭제
    - delete_raw: uploads/ 폴더의 원본 PDF/HWP 파일 삭제
    - delete_core: gichul.db의 exams/passages/sentences 및 static/captures/ 크롭 이미지 삭제 (FK Cascade)
    - delete_metadata: 코어 본문은 유지하고 어법 분석(annotations) 및 태그(tags)만 초기화
    - delete_rate: 코어 본문은 유지하고 문항별 정답률/선지선택률(correct_rate, choice_rates) 및 uploads/ 정답률 CSV 삭제
    """
    import glob
    uploads_dir = paths.UPLOADS_DIR
    captures_dir = paths.CAPTURES_DIR

    with get_connection() as conn:
        cursor = conn.cursor()

        # 1. 시험지 마스터 정보 조회
        cursor.execute("SELECT id, grade, year, month FROM exams WHERE id = ?", (exam_id,))
        exam = cursor.fetchone()
        if not exam:
            return {"success": False, "message": f"시험지 '{exam_id}'를 찾을 수 없습니다."}

        grade = exam["grade"]
        year = exam["year"]
        month = exam["month"]

        del_res = {
            "success": True,
            "exam_id": exam_id,
            "deleted_raw_count": 0,
            "freed_raw_bytes": 0,
            "deleted_passages_count": 0,
            "deleted_sentences_count": 0,
            "deleted_captures_count": 0,
            "deleted_grammar_count": 0,
            "deleted_tags_count": 0,
            "deleted_rate_count": 0,
            "core_deleted": False,
            "metadata_reset": False,
            "rate_data_deleted": False,
            "raw_files_deleted": False,
            "message": ""
        }

        # 2. 메타데이터만 단독 초기화하는 경우 (코어 본문은 삭제하지 않는 경우)
        if delete_metadata and not delete_core:
            # 어법 분석 삭제 전 카운트
            cursor.execute("""
                SELECT COUNT(DISTINCT a.id)
                FROM sentence_grammar_annotations a
                JOIN sentences s ON a.sentence_id = s.id
                JOIN passages p ON s.passage_id = p.id
                WHERE p.exam_id = ?
            """, (exam_id,))
            del_res["deleted_grammar_count"] = cursor.fetchone()[0]

            # 태그 삭제 전 카운트
            cursor.execute("""
                SELECT 
                    (SELECT COUNT(*) FROM passage_tags pt JOIN passages p ON pt.passage_id = p.id WHERE p.exam_id = ?) +
                    (SELECT COUNT(*) FROM sentence_tags st JOIN sentences s ON st.sentence_id = s.id JOIN passages p ON s.passage_id = p.id WHERE p.exam_id = ?)
            """, (exam_id, exam_id))
            del_res["deleted_tags_count"] = cursor.fetchone()[0]

            # 어법 분석 레코드 삭제
            cursor.execute("""
                DELETE FROM sentence_grammar_annotations
                WHERE sentence_id IN (
                    SELECT s.id FROM sentences s
                    JOIN passages p ON s.passage_id = p.id
                    WHERE p.exam_id = ?
                )
            """, (exam_id,))

            # 문장의 어법 분석 완료 플래그 초기화
            cursor.execute("""
                UPDATE sentences
                SET grammar_analyzed = 0
                WHERE passage_id IN (
                    SELECT id FROM passages WHERE exam_id = ?
                )
            """, (exam_id,))

            # 태그 삭제
            cursor.execute("""
                DELETE FROM passage_tags
                WHERE passage_id IN (SELECT id FROM passages WHERE exam_id = ?)
            """, (exam_id,))
            cursor.execute("""
                DELETE FROM sentence_tags
                WHERE sentence_id IN (
                    SELECT s.id FROM sentences s
                    JOIN passages p ON s.passage_id = p.id
                    WHERE p.exam_id = ?
                )
            """, (exam_id,))
            conn.commit()
            del_res["metadata_reset"] = True

        # 3. 정답률 데이터 단독 초기화 (코어 본문은 유지하고 passages의 correct_rate/choice_rates 및 uploads/의 CSV 삭제)
        if delete_rate and not delete_core:
            cursor.execute("""
                SELECT COUNT(*) FROM passages
                WHERE exam_id = ? AND (correct_rate IS NOT NULL OR choice_rates IS NOT NULL)
            """, (exam_id,))
            del_res["deleted_rate_count"] = cursor.fetchone()[0]

            cursor.execute("""
                UPDATE passages
                SET correct_rate = NULL, choice_rates = NULL
                WHERE exam_id = ?
            """, (exam_id,))

            # uploads/ 내 해당 시험지의 원본 정답률 CSV 파일 삭제
            csv_pattern = os.path.join(uploads_dir, f"{grade}_{year}_{month:02d}_*.csv")
            for f in glob.glob(csv_pattern):
                try:
                    os.remove(f)
                except Exception:
                    logger.debug("Failed to remove csv %s", f, exc_info=True)

            conn.commit()
            del_res["rate_data_deleted"] = True

        # 4. 코어 본문 데이터 삭제 (exams, passages, sentences, captures)
        if delete_core:
            cursor.execute("SELECT COUNT(*) FROM passages WHERE exam_id = ?", (exam_id,))
            del_res["deleted_passages_count"] = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM sentences s JOIN passages p ON s.passage_id = p.id WHERE p.exam_id = ?", (exam_id,))
            del_res["deleted_sentences_count"] = cursor.fetchone()[0]

            # DB Cascade 삭제 (exams 삭제 시 하위 지문, 문장, 어법, 태그 자동 삭제)
            cursor.execute("DELETE FROM exams WHERE id = ?", (exam_id,))
            conn.commit()
            del_res["core_deleted"] = True

            # 디스크 크롭 이미지 정리
            cap_pattern = os.path.join(captures_dir, f"{grade}_{year}_{month:02d}_*.png")
            for f in glob.glob(cap_pattern):
                try:
                    os.remove(f)
                    del_res["deleted_captures_count"] += 1
                except Exception:
                    logger.debug("Failed to remove capture %s", f, exc_info=True)

        # 5. 원본 파일(uploads/) 삭제
        if delete_raw:
            raw_pattern = os.path.join(uploads_dir, f"{grade}_{year}_{month:02d}_*")
            for f in glob.glob(raw_pattern):
                try:
                    size = os.path.getsize(f)
                    os.remove(f)
                    del_res["deleted_raw_count"] += 1
                    del_res["freed_raw_bytes"] += size
                except Exception:
                    logger.debug("Failed to remove raw file %s", f, exc_info=True)
            del_res["raw_files_deleted"] = True

        # 메시지 조합
        actions = []
        if del_res["raw_files_deleted"]:
            mb = round(del_res["freed_raw_bytes"] / (1024 * 1024), 2)
            actions.append(f"원본 파일 {del_res['deleted_raw_count']}개({mb}MB) 삭제")
        if del_res["core_deleted"]:
            actions.append(f"코어 지문 {del_res['deleted_passages_count']}개·문장 {del_res['deleted_sentences_count']}개 및 캡처 {del_res['deleted_captures_count']}개 삭제")
        else:
            if del_res["metadata_reset"]:
                actions.append(f"어법 메타데이터 {del_res['deleted_grammar_count']}개 및 태그 {del_res['deleted_tags_count']}개 초기화")
            if del_res["rate_data_deleted"]:
                actions.append(f"정답률 데이터 {del_res['deleted_rate_count']}문항 초기화")

        del_res["message"] = f"'{exam_id}': " + (", ".join(actions) if actions else "선택된 삭제 작업 없음")
        invalidate_exams_cache()
        return del_res


def delete_exam(exam_id: str) -> Dict[str, Any]:
    """하위 호환성을 위한 완전 삭제 함수 (4대 영역 모두 삭제)"""
    return selective_delete_exam(exam_id, delete_raw=True, delete_core=True, delete_metadata=True, delete_rate=True)


def save_passage(passage_data: dict, conn: Optional[sqlite3.Connection] = None) -> str:
    """지문 정보 저장. conn을 주면 호출한 쪽 트랜잭션에 참여한다."""
    if "question_type" not in passage_data or not passage_data.get("question_type") or not str(passage_data["question_type"]).strip():
        passage_data["question_type"] = "기타"
    if "correct_rate" not in passage_data:
        passage_data["correct_rate"] = None
    if "choice_rates" not in passage_data:
        passage_data["choice_rates"] = None
    if "area" not in passage_data or not passage_data.get("area"):
        q_num = passage_data.get("q_num", 0)
        passage_data["area"] = "listening" if 1 <= q_num <= 17 else "reading"
    if "script_crop_image" not in passage_data:
        passage_data["script_crop_image"] = None
    if "script_text" not in passage_data:
        passage_data["script_text"] = None
    if "fels_text" not in passage_data:
        passage_data["fels_text"] = None
    if "audio_file_path" not in passage_data:
        passage_data["audio_file_path"] = None

    with _use_conn(conn) as c:
        cursor = c.cursor()
        cursor.execute("""
            INSERT INTO passages (
                id, exam_id, q_num, question_title, question_type, passage_text,
                answer_text, explanation_text, pdf_crop_image, validation_ratio, remarks,
                correct_rate, choice_rates, area, script_crop_image, script_text, fels_text, audio_file_path
            )
            VALUES (
                :id, :exam_id, :q_num, :question_title, :question_type, :passage_text,
                :answer_text, :explanation_text, :pdf_crop_image, :validation_ratio, :remarks,
                :correct_rate, :choice_rates, :area, :script_crop_image, :script_text, :fels_text, :audio_file_path
            )
            ON CONFLICT(id) DO UPDATE SET
                question_title = excluded.question_title,
                question_type = excluded.question_type,
                passage_text = excluded.passage_text,
                answer_text = excluded.answer_text,
                explanation_text = excluded.explanation_text,
                pdf_crop_image = excluded.pdf_crop_image,
                validation_ratio = excluded.validation_ratio,
                remarks = excluded.remarks,
                correct_rate = COALESCE(excluded.correct_rate, passages.correct_rate),
                choice_rates = COALESCE(excluded.choice_rates, passages.choice_rates),
                area = excluded.area,
                script_crop_image = COALESCE(excluded.script_crop_image, passages.script_crop_image),
                script_text = COALESCE(excluded.script_text, passages.script_text),
                fels_text = COALESCE(excluded.fels_text, passages.fels_text),
                audio_file_path = COALESCE(excluded.audio_file_path, passages.audio_file_path)
        """, passage_data)
    invalidate_exams_cache()
    return passage_data["id"]


def set_answer_status(exam_id: str, sources: Dict[int, str], verified: Dict[int, bool],
                      conn: Optional[sqlite3.Connection] = None):
    """문항별 정답 출처(answer_source)와 검증 여부(answer_verified) 기록"""
    with _use_conn(conn) as c:
        cursor = c.cursor()
        for q_num, source in sources.items():
            cursor.execute(
                "UPDATE passages SET answer_source = ?, answer_verified = ? WHERE exam_id = ? AND q_num = ?",
                (source, 1 if verified.get(q_num) else 0, exam_id, q_num)
            )


def update_passage_answers(exam_id: str, answers: Dict[int, str], source: str, verified: int):
    """문항별 정답, 해설 [정답] 헤더, 정답 출처, 검증 상태를 함께 갱신"""
    with get_connection() as conn:
        cursor = conn.cursor()
        for q_num, ans in answers.items():
            row = cursor.execute(
                "SELECT id, explanation_text FROM passages WHERE exam_id = ? AND q_num = ?", (exam_id, q_num)
            ).fetchone()
            if not row:
                continue
            exp = (row["explanation_text"] or "").strip()
            exp = apply_answer_header(exp, ans)
            cursor.execute(
                "UPDATE passages SET answer_text = ?, explanation_text = ?, answer_source = ?, answer_verified = ? WHERE id = ?",
                (ans, exp, source, verified, row["id"])
            )
        # 정답이 바뀌었으면, 예전 정답 선지로 채워 저장된 빈칸 문장을 새 정답으로 다시 채움
        refill_blank_sentences(exam_id=exam_id, conn=conn)
        conn.commit()


def save_exam_correct_rates(exam_id: str, rates_dict: Dict[int, Dict[str, Any]],
                            conn: Optional[sqlite3.Connection] = None) -> Dict[str, Any]:
    """
    특정 시험지의 문항별 정답률 및 선지 선택률 일괄 DB 갱신 (정답은 건드리지 않음 - 정답 교차검증은 answer_resolver 담당)
    rates_dict: { q_num: { 'correct_rate': float, 'choice_rates': dict, 'correct_ans_circle': str } }
    """
    clean_id = normalize_bracket_id(exam_id)

    updated_count = 0
    rates_collected = []

    with _use_conn(conn) as c:
        cursor = c.cursor()
        cursor.execute("SELECT id, q_num, answer_text, explanation_text FROM passages WHERE exam_id = ?", (clean_id,))
        passages = cursor.fetchall()

        for p in passages:
            q_num = p["q_num"]
            q_int = int(q_num) if str(q_num).isdigit() else q_num
            target_data = rates_dict.get(q_int) or rates_dict.get(str(q_int))
            if target_data:
                c_rate = target_data.get("correct_rate")
                ch_rates = target_data.get("choice_rates")
                ch_rates_json = json.dumps(ch_rates, ensure_ascii=False) if ch_rates else None
                cursor.execute(
                    "UPDATE passages SET correct_rate = ?, choice_rates = ? WHERE id = ?",
                    (c_rate, ch_rates_json, p["id"])
                )
                updated_count += 1
                if c_rate is not None:
                    rates_collected.append(c_rate)

    invalidate_exams_cache()

    avg_rate = round(sum(rates_collected) / len(rates_collected), 1) if rates_collected else None
    return {
        "exam_id": clean_id,
        "updated_count": updated_count,
        "avg_rate": avg_rate
    }


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
        invalidate_exams_cache()


# 재업로드 시 "같은 문장" 판정용 정규화.
# 저장된 문장은 어법 분석 전처리(grammar_analyzer.prepare_sentence_for_analysis)를 거쳐
# 선지 기호 제거·빈칸 정답 채움·구두점 공백 정리가 되어 있을 수 있으므로, 단어 토큰만 비교한다.
_SENTENCE_BLANK_RE = _BLANK_PATTERN  # text_utils.fill_blanks 와 같은 빈칸 기준
_SENTENCE_TOKEN_RE = re.compile(r"[A-Za-z0-9가-힣']+")


def _sentence_tokens(text: Optional[str]) -> List[str]:
    """HWP 엔티티·특수 기호·선지 표식을 걷어낸 뒤 소문자 단어 토큰 목록을 만든다."""
    t = re.sub(r'&#\d+;', ' ', text or "")
    t = re.sub(r'[\uF000-\uFFFF]', ' ', t)
    t = re.sub(r'\(\s*[①②③④⑤1-5a-eA-E]\s*\)', ' ', t)   # (1)~(5), (a)~(e) 선지 표식
    t = re.sub(r'^\s*\([A-E]\)\s*', ' ', t)               # 문두 (A)~(E) 문단 표식
    t = re.sub(r'^\s*\[?[1-5]\]?[\.\)]\s*', ' ', t)       # 문두 1. / 2) / [3] 번호
    return [tok.lower() for tok in _SENTENCE_TOKEN_RE.findall(t)]


def _sentence_equivalent(stored_text: Optional[str], incoming_text: Optional[str]) -> bool:
    """저장된 문장과 새로 파싱한 문장이 같은 문장인지 판정한다.

    새 문장에 빈칸(____ 등)이 있으면, 저장본에서는 그 자리가 정답으로 채워졌을 수 있으므로
    빈칸 자리는 임의 개수(0개 이상)의 단어와 일치하는 것으로 본다.
    """
    stored = _sentence_tokens(stored_text)
    parts = _SENTENCE_BLANK_RE.split(incoming_text or "")
    if len(parts) == 1:
        return stored == _sentence_tokens(incoming_text)

    segments = [_sentence_tokens(p) for p in parts]
    first, last = segments[0], segments[-1]
    n = len(stored)
    if len(first) + len(last) > n:
        return False
    if stored[:len(first)] != first:
        return False
    if last and stored[n - len(last):] != last:
        return False
    pos, end = len(first), n - len(last)
    for seg in segments[1:-1]:
        if not seg:
            continue
        found = -1
        for i in range(pos, end - len(seg) + 1):
            if stored[i:i + len(seg)] == seg:
                found = i
                break
        if found < 0:
            return False
        pos = found + len(seg)
    return True


def replace_passage_sentences(passage_id: str, sentences: List[dict],
                              conn: Optional[sqlite3.Connection] = None) -> Dict[str, int]:
    """지문의 문장 목록을 새 파싱 결과로 교체한다 (재업로드 시 옛 문장이 남지 않도록).

    - 새 목록에 없는 기존 문장은 삭제 (태그·어법 주석은 FK CASCADE로 함께 삭제)
    - 같은 ID이고 같은 문장(_sentence_equivalent)이면 저장된 텍스트·별표·어법 분석을 그대로 두고 순서/비고만 갱신
    - 같은 ID인데 내용이 바뀌었으면 텍스트를 덮어쓰고 AI 어법 주석만 삭제 (사용자 주석은 유지)
    - 빈 목록이면 아무것도 지우지 않는다 (파싱 실패로 문장이 통째로 사라지는 것을 방지; 호출 쪽에서 경고)
    """
    stats = {"inserted": 0, "updated": 0, "text_changed": 0, "removed": 0}
    if not sentences:
        return stats

    with _use_conn(conn) as c:
        cursor = c.cursor()
        existing = {
            row["id"]: row["sentence_text"]
            for row in cursor.execute(
                "SELECT id, sentence_text FROM sentences WHERE passage_id = ?", (passage_id,)
            ).fetchall()
        }
        new_ids = set()
        for s in sentences:
            sid = s["id"]
            new_ids.add(sid)
            order_index = s.get("order_index", 0)
            new_text = s.get("sentence_text", "")
            remarks = s.get("remarks")
            word_count = s.get("word_count", 0)

            if sid not in existing:
                cursor.execute("""
                    INSERT INTO sentences (id, passage_id, order_index, sentence_text, word_count, remarks)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        passage_id = excluded.passage_id,
                        order_index = excluded.order_index,
                        sentence_text = excluded.sentence_text,
                        word_count = excluded.word_count,
                        remarks = excluded.remarks
                """, (sid, passage_id, order_index, new_text, word_count, remarks))
                stats["inserted"] += 1
            elif _sentence_equivalent(existing[sid], new_text):
                cursor.execute(
                    "UPDATE sentences SET order_index = ?, remarks = ? WHERE id = ?",
                    (order_index, remarks, sid)
                )
                stats["updated"] += 1
            else:
                cursor.execute(
                    "UPDATE sentences SET order_index = ?, sentence_text = ?, word_count = ?, remarks = ? WHERE id = ?",
                    (order_index, new_text, word_count, remarks, sid)
                )
                cursor.execute(
                    "DELETE FROM sentence_grammar_annotations WHERE sentence_id = ? AND COALESCE(source_type, 'AI') = 'AI'",
                    (sid,)
                )
                cursor.execute("""
                    UPDATE sentences SET grammar_analyzed = CASE
                        WHEN EXISTS (SELECT 1 FROM sentence_grammar_annotations WHERE sentence_id = ?) THEN 1 ELSE 0 END
                    WHERE id = ?
                """, (sid, sid))
                stats["text_changed"] += 1

        stale_ids = [sid for sid in existing if sid not in new_ids]
        for sid in stale_ids:
            cursor.execute("DELETE FROM sentences WHERE id = ?", (sid,))
        stats["removed"] = len(stale_ids)

    invalidate_exams_cache()
    return stats


# 지문 본문에서 빈칸이 들어 있는 문장 조각을 찾기 위한 분할 기준 (문장 끝 부호 뒤 공백, 줄바꿈)
_BLANK_TEMPLATE_SPLIT_RE = re.compile(r'(?<=[.!?])\s+|(?<=[.!?][”"’)])\s+|[\r\n]+')
_TOKEN_CHARS = "A-Za-z0-9가-힣'"
# 요약문 선지 "(A) …… (B)" 구분자 (text_utils.fill_blanks 의 분할 기준과 동일)
_CHOICE_PART_SPLIT_RE = _CHOICE_PART_SPLIT_PATTERN


def _contains_tokens(haystack: List[str], needle: List[str]) -> bool:
    """needle 토큰열이 haystack 안에 연속으로 들어 있는지"""
    n = len(needle)
    return any(haystack[i:i + n] == needle for i in range(len(haystack) - n + 1))


def _token_span_regex(tokens: List[str]) -> "re.Pattern":
    """토큰열을 원문에서 찾는 정규식 (토큰 사이에는 공백·구두점 등 토큰이 아닌 문자 허용, 대소문자 무시)"""
    sep = f"[^{_TOKEN_CHARS}]+"
    body = sep.join(re.escape(t) for t in tokens)
    return re.compile(f"(?<![{_TOKEN_CHARS}]){body}(?![{_TOKEN_CHARS}])", re.IGNORECASE)


def _token_core(text: str) -> str:
    """첫 토큰 시작 ~ 마지막 토큰 끝 구간 (앞뒤 구두점 제외)"""
    toks = list(_SENTENCE_TOKEN_RE.finditer(text or ""))
    return text[toks[0].start():toks[-1].end()] if toks else ""


def refill_blank_sentences(exam_id: Optional[str] = None,
                           passage_ids: Optional[List[str]] = None,
                           conn: Optional[sqlite3.Connection] = None,
                           dry_run: bool = False) -> List[Dict[str, Any]]:
    """빈칸 문장이 **현재 정답이 아닌 선지**로 채워져 저장돼 있으면 현재 정답 선지로 다시 채운다.

    어법 분석 전처리는 빈칸을 정답 선지로 채운 문장을 DB에 덮어써서 원래 빈칸이 사라진다.
    그 뒤에 정답이 고쳐지면(정답 JSON·정답표·수동 수정 등) 문장에는 예전 선지가 그대로 남는다.
    지문 본문(passage_text)에는 빈칸이 남아 있으므로, 그 문장을 틀로 삼아 판정한다.

    - 틀: 지문 본문에서 빈칸이 들어 있는 문장 조각 (빈칸 밖 단어 2개 이상, 채운 결과 4단어 이상인 것만)
    - 판정: 저장된 문장 안에 "틀 + 오답 선지" 단어열이 그대로 들어 있고, "틀 + 정답 선지" 단어열은 없을 때만 교체
    - 교체: 그 구간만 "틀 + 정답 선지"로 바꾼다 (문장 분할이 달라 앞 문장이 붙어 있어도 나머지는 유지)
    - 바뀐 문장은 AI 어법 주석을 지우고 grammar_analyzed 를 다시 계산한다 (사용자 주석은 유지, 재분석 필요)

    exam_id 또는 passage_ids 로 대상을 정한다 (둘 다 없으면 전체 지문).
    반환: 바뀐(또는 dry_run 이면 바뀔) 문장 목록 [{sentence_id, passage_id, old_text, new_text, wrong_choice, answer}]
    """
    changes: List[Dict[str, Any]] = []
    with _use_conn(conn) as c:
        cursor = c.cursor()
        query = "SELECT id, passage_text, answer_text, explanation_text FROM passages"
        params: list = []
        if passage_ids is not None:
            if not passage_ids:
                return changes
            query += " WHERE id IN (SELECT value FROM json_each(?))"
            params.append(json.dumps([normalize_bracket_id(p) for p in passage_ids], ensure_ascii=False))
        elif exam_id:
            query += " WHERE exam_id = ?"
            params.append(normalize_bracket_id(exam_id))

        for p in cursor.execute(query, params).fetchall():
            passage_text = p["passage_text"] or ""
            if not _SENTENCE_BLANK_RE.search(passage_text):
                continue
            ans_num = extract_answer_num(p["answer_text"] or "")
            if not ans_num:
                continue
            explanation_text = p["explanation_text"] or ""
            choices = extract_choices(passage_text, explanation_text)
            if ans_num not in choices:
                continue

            # 틀마다 (정답 채움 토큰, 정답 채움 원문, [(오답 번호, 오답 채움 토큰)])
            plans = []
            for piece in _BLANK_TEMPLATE_SPLIT_RE.split(passage_text):
                if not piece or not _SENTENCE_BLANK_RE.search(piece):
                    continue
                if len(_sentence_tokens(_SENTENCE_BLANK_RE.sub(" ", piece))) < 2:
                    continue  # 문맥이 너무 짧으면 다른 문장의 같은 단어와 헷갈릴 수 있어 건너뜀
                n_blanks = len(_SENTENCE_BLANK_RE.findall(piece))
                if n_blanks >= 2 and len(split_choice_parts(choices[ans_num])) != n_blanks:
                    continue  # 요약문 등 복수 빈칸인데 정답 선지를 빈칸 수만큼 나눌 수 없으면 건너뜀
                right_text = fill_blanks(piece, passage_text, str(ans_num), explanation_text)
                if _SENTENCE_BLANK_RE.search(right_text):
                    continue
                right_tokens = _sentence_tokens(right_text)
                wrongs = []
                for k in sorted(choices):
                    if k == ans_num:
                        continue
                    w_tokens = _sentence_tokens(fill_blanks(piece, passage_text, str(k), explanation_text))
                    # 오답 채움 결과가 4단어 미만이면 우연히 겹칠 수 있어 비교하지 않음
                    if len(w_tokens) >= 4 and w_tokens != right_tokens:
                        wrongs.append((k, w_tokens))
                if wrongs:
                    plans.append((right_tokens, right_text, wrongs))
            if not plans:
                continue

            sentences = cursor.execute(
                "SELECT id, sentence_text FROM sentences WHERE passage_id = ?", (p["id"],)
            ).fetchall()
            for s in sentences:
                old_text = s["sentence_text"] or ""
                if _SENTENCE_BLANK_RE.search(old_text):
                    continue  # 아직 빈칸이 남은 문장은 분석할 때 현재 정답으로 채워짐
                stored_tokens = _sentence_tokens(old_text)
                for right_tokens, right_text, wrongs in plans:
                    if _contains_tokens(stored_tokens, right_tokens):
                        break  # 이미 정답으로 채워져 있음
                    hit = next(((k, wt) for k, wt in wrongs if _contains_tokens(stored_tokens, wt)), None)
                    if not hit:
                        continue
                    m = _token_span_regex(hit[1]).search(old_text)
                    core = _token_core(right_text)
                    if not m or not core:
                        break
                    new_text = (old_text[:m.start()] + core + old_text[m.end():]).strip()
                    if _sentence_tokens(new_text) == stored_tokens:
                        break
                    changes.append({
                        "sentence_id": s["id"],
                        "passage_id": p["id"],
                        "old_text": old_text,
                        "new_text": new_text,
                        "wrong_choice": hit[0],
                        "answer": ans_num,
                    })
                    if not dry_run:
                        words = re.findall(r"\b[\w'-]+\b", new_text)
                        cursor.execute(
                            "UPDATE sentences SET sentence_text = ?, word_count = ? WHERE id = ?",
                            (new_text, len(words), s["id"])
                        )
                        cursor.execute(
                            "DELETE FROM sentence_grammar_annotations WHERE sentence_id = ? AND COALESCE(source_type, 'AI') = 'AI'",
                            (s["id"],)
                        )
                        cursor.execute("""
                            UPDATE sentences SET grammar_analyzed = CASE
                                WHEN EXISTS (SELECT 1 FROM sentence_grammar_annotations WHERE sentence_id = ?) THEN 1 ELSE 0 END
                            WHERE id = ?
                        """, (s["id"], s["id"]))
                    break

    if changes and not dry_run:
        invalidate_exams_cache()
    return changes


def update_sentence_text(sentence_id: str, new_text: str, word_count: Optional[int] = None) -> bool:
    """단일 문장의 본문 텍스트 및 단어 수 수정 업데이트"""
    clean_id = normalize_bracket_id(sentence_id)
    if word_count is None:
        words = re.findall(r"\b[\w'-]+\b", new_text)
        word_count = len(words)
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE sentences SET sentence_text = ?, word_count = ? WHERE id = ?",
            (new_text.strip(), word_count, clean_id)
        )
        conn.commit()
        return cursor.rowcount > 0


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


def _apply_correct_rate_filter(range_key: str, table_alias: str = "p") -> str:
    """정답률 구간 필터링 SQL 조건문 생성 (10% 단위 세분화 체계)"""
    if not range_key:
        return ""
    col = f"{table_alias}.correct_rate"
    rk = range_key.strip().lower()

    # 10% 단위 세분화 체계
    if rk == "under20":
        return f" AND {col} IS NOT NULL AND {col} < 20.0"
    elif rk == "20to30":
        return f" AND {col} IS NOT NULL AND {col} >= 20.0 AND {col} < 30.0"
    elif rk == "30to40":
        return f" AND {col} IS NOT NULL AND {col} >= 30.0 AND {col} < 40.0"
    elif rk == "40to50":
        return f" AND {col} IS NOT NULL AND {col} >= 40.0 AND {col} < 50.0"
    elif rk == "50to60":
        return f" AND {col} IS NOT NULL AND {col} >= 50.0 AND {col} < 60.0"
    elif rk == "60to70":
        return f" AND {col} IS NOT NULL AND {col} >= 60.0 AND {col} < 70.0"
    elif rk == "70to80":
        return f" AND {col} IS NOT NULL AND {col} >= 70.0 AND {col} < 80.0"
    elif rk == "over80":
        return f" AND {col} IS NOT NULL AND {col} >= 80.0"

    # 기존 옵션 하위 호환성 유지
    elif rk == "under40":
        return f" AND {col} IS NOT NULL AND {col} < 40.0"
    elif rk == "40to60":
        return f" AND {col} IS NOT NULL AND {col} >= 40.0 AND {col} < 60.0"
    elif rk == "60to80":
        return f" AND {col} IS NOT NULL AND {col} >= 60.0 AND {col} < 80.0"
    elif rk == "under50":
        return f" AND {col} IS NOT NULL AND {col} <= 50.0"
    elif rk == "under60":
        return f" AND {col} IS NOT NULL AND {col} < 60.0"
    return ""


def _build_fts_query(term: str, whole_word: bool = False) -> str:
    """FTS5 전문 검색용 안전한 쿼리 문자열 생성 (특수문자 이스케이프 및 접두사 가속화)"""
    clean = re.sub(r'["\*\(\)\{\}\^~:+\-]', ' ', term).strip()
    words = [w for w in clean.split() if w]
    if not words:
        return '""'
    if whole_word:
        return " ".join(f'"{w}"' for w in words)
    else:
        # 단어별 접두사 검색(prefix matching)으로 부분 일치 및 풀스캔 대체 초고속 지원
        return " ".join(f'"{w}"*' for w in words)


def search_passages(
    keyword: str = "",
    exam_id: str = "",
    grade: str = "",
    year: Optional[int] = None,
    years: Optional[List[int]] = None,
    month: Optional[int] = None,
    exam_type: str = "",
    question_type: str = "",
    correct_rate_range: str = "",
    tag: str = "",
    area: str = "",
    whole_word: bool = False,
    limit: int = 0,
    meta_only: bool = False,
    user_role: str = access.DEFAULT_ROLE,
    _use_fts: bool = True
) -> List[Dict[str, Any]]:
    """지문 검색 (지문 본문, 발문, 해설, 스크립트, 출처, 태그, 문제유형, 시험구분, 영역 - 온전한 단어 검색 및 복수 연도 지원, meta_only 초고속 경량 모드 지원)

    user_role: 등급별 데이터 필터 (access.py). 기본값 관리자 = 예전과 같은 결과.
               비회원이면 정답률/태그 검색 조건을 무시하고, 응답에서 메타·관리자 전용 필드를 뺀다.
    _use_fts: 내부 전용. FTS 쿼리가 실패하면 False로 자기 자신을 다시 호출해 LIKE 검색으로 대체한다.
    """
    # FTS 실패 시 같은 인자로 재호출하기 위해 최초 인자를 보관 (반드시 함수 첫 줄에 둔다)
    _call_args = {k: v for k, v in locals().items() if k != "_use_fts"}
    # 등급별 검색 조건 제한: 메타 정보로 걸러 보는 것 자체가 메타 정보를 드러내므로 막는다
    if not access.allowed_search_filters(user_role)["meta"]:
        correct_rate_range = ""
        tag = ""
    if meta_only:
        select_clause = """
            p.id, p.exam_id, p.q_num, p.question_type, p.area, p.correct_rate,
            p.pdf_crop_image, p.script_crop_image, p.user_memo, p.user_memo_updated_at,
            (p.passage_text IS NOT NULL AND LENGTH(p.passage_text) > 0) AS has_passage_text,
            e.grade, e.year, e.month, e.exam_type, e.subtype, e.reading_start_q, e.reading_end_q,
            e.listening_start_q, e.listening_end_q
        """
    else:
        select_clause = """
            p.*, e.grade, e.year, e.month, e.exam_type, e.subtype, e.reading_start_q, e.reading_end_q,
            e.listening_start_q, e.listening_end_q
        """

    query = f"""
        SELECT {select_clause}
        FROM passages p
        JOIN exams e ON p.exam_id = e.id
        WHERE 1=1
    """
    params = []

    if exam_id:
        clean_eid = normalize_bracket_id(exam_id)
        query += " AND p.exam_id = ?"
        params.append(clean_eid)

    if keyword:
        k_strip = keyword.strip()
        if _use_fts:
            # 1차 시도: FTS5 전문 검색 가속화 (수백 ms -> 2~5ms 단축)
            fts_q = _build_fts_query(k_strip, whole_word)
            query += """
                AND (
                    p.id IN (SELECT passage_id FROM passages_fts WHERE passages_fts MATCH ?) OR
                    p.id LIKE ?
                )
            """
            params.extend([fts_q, f"%{k_strip}%"])
        else:
            # FTS 쿼리 실패 시 표준 LIKE 백업
            kw = f"%{k_strip}%"
            query += """
                AND (
                    p.id LIKE ? OR
                    p.passage_text LIKE ? OR
                    p.question_title LIKE ? OR
                    p.explanation_text LIKE ? OR
                    p.script_text LIKE ?
                )
            """
            params.extend([kw, kw, kw, kw, kw])

    if area:
        if area == "listening":
            query += " AND p.area = 'listening'"
        elif area == "reading":
            query += " AND (p.area = 'reading' OR p.area IS NULL)"

    if grade:
        query += " AND e.grade = ?"
        params.append(grade)
    if years and len(years) > 0:
        placeholders = ",".join(["?"] * len(years))
        query += f" AND e.year IN ({placeholders})"
        params.extend(years)
    elif year:
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

    if correct_rate_range:
        query += _apply_correct_rate_filter(correct_rate_range, "p")

    if tag:
        query += """
            AND p.id IN (SELECT passage_id FROM passage_tags WHERE tag_name LIKE ?)
        """
        params.append(f"%{tag.strip()}%")

    if limit and limit > 0:
        query += " ORDER BY e.year DESC, e.month DESC, p.q_num ASC LIMIT ?"
        params.append(limit)
    else:
        query += " ORDER BY e.year DESC, e.month DESC, p.q_num ASC"

    with get_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(query, params)
            rows = cursor.fetchall()
        except sqlite3.OperationalError as e:
            if keyword and _use_fts:
                logger.warning("[search_passages] FTS 검색 실패 → LIKE 검색으로 대체: %s", e)
                return search_passages(**_call_args, _use_fts=False)
            raise
        if not rows:
            return []

        # meta_only 모드일 때는 태그 N+1 조회 및 대용량 choice_rates JSON 파싱을 생략하여 초고속 반환
        if meta_only:
            return access.filter_passages([dict(r) for r in rows], user_role)

        passage_ids = [r["id"] for r in rows]
        tags_by_passage = defaultdict(list)
        chunk_size = 900
        for i in range(0, len(passage_ids), chunk_size):
            chunk = passage_ids[i:i + chunk_size]
            placeholders = ",".join(["?"] * len(chunk))
            cursor.execute(
                f"SELECT passage_id, GROUP_CONCAT(tag_name, '||') as tag_list FROM passage_tags WHERE passage_id IN ({placeholders}) GROUP BY passage_id",
                chunk
            )
            for tr in cursor.fetchall():
                if tr["tag_list"]:
                    tags_by_passage[tr["passage_id"]] = tr["tag_list"].split("||")

        results = []
        for r in rows:
            p_dict = dict(r)
            p_dict["tags"] = tags_by_passage.get(r["id"], [])
            if p_dict.get("choice_rates") and isinstance(p_dict["choice_rates"], str):
                try:
                    p_dict["choice_rates_obj"] = json.loads(p_dict["choice_rates"])
                except Exception:
                    logger.debug("Failed to parse choice_rates json: %s", p_dict.get("choice_rates"), exc_info=True)
                    p_dict["choice_rates_obj"] = None
            results.append(p_dict)
        return access.filter_passages(results, user_role)


def get_exam_passages(exam_id: str, user_role: str = access.DEFAULT_ROLE) -> List[Dict[str, Any]]:
    """특정 시험 ID에 속한 모든 지문의 전체 상세 데이터(본문, 해설, 보기 등) 일괄 조회

    user_role: 등급별 데이터 필터 (access.py). 기본값 관리자 = 예전과 같은 결과.
    """
    if not exam_id:
        return []
    clean_eid = normalize_bracket_id(exam_id)
    return search_passages(exam_id=clean_eid, meta_only=False, user_role=user_role)


def get_passage(passage_id: str, user_role: str = access.DEFAULT_ROLE) -> Optional[Dict[str, Any]]:
    """지문 ID로 단일 지문 정보 조회

    user_role: 등급별 데이터 필터 (access.py). 기본값 관리자 = 예전과 같은 결과.
               내부 처리(빈칸 채우기, 어법 분석 등)는 기본값으로 호출해 전체 데이터를 쓴다.
    """
    if not passage_id:
        return None
    clean_id = normalize_bracket_id(passage_id)
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT p.*, e.listening_start_q, e.listening_end_q, e.reading_start_q, e.reading_end_q, e.year, e.month, e.grade
            FROM passages p
            LEFT JOIN exams e ON p.exam_id = e.id
            WHERE p.id = ?
        """, (clean_id,))
        row = cursor.fetchone()
        if not row:
            cursor.execute("""
                SELECT p.*, e.listening_start_q, e.listening_end_q, e.reading_start_q, e.reading_end_q, e.year, e.month, e.grade
                FROM passages p
                LEFT JOIN exams e ON p.exam_id = e.id
                WHERE p.id = ?
            """, (clean_id.strip("[]"),))
            row = cursor.fetchone()
        if row:
            p_dict = dict(row)
            p_dict["tags"] = get_passage_tags(p_dict["id"])
            if p_dict.get("choice_rates") and isinstance(p_dict["choice_rates"], str):
                try:
                    p_dict["choice_rates_obj"] = json.loads(p_dict["choice_rates"])
                except Exception:
                    logger.debug("Failed to parse choice_rates json: %s", p_dict.get("choice_rates"), exc_info=True)
                    p_dict["choice_rates_obj"] = None
            return access.filter_passage(p_dict, user_role)
        return None


def get_sentence(sentence_id: str) -> Optional[Dict[str, Any]]:
    """문장 ID로 단일 문장 정보 조회"""
    if not sentence_id:
        return None
    clean_id = normalize_bracket_id(sentence_id)
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM sentences WHERE id = ?", (clean_id,))
        row = cursor.fetchone()
        if not row:
            cursor.execute("SELECT * FROM sentences WHERE id = ?", (clean_id.strip("[]"),))
            row = cursor.fetchone()
        if row:
            return dict(row)
        return None


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


def save_grammar_annotations(
    sentence_id: str, 
    annotations: List[Dict[str, Any]], 
    source_type: str = "AI", 
    ai_model: Optional[str] = None, 
    user_id: Optional[str] = None
):
    """문장의 어법 범주 분석 결과 저장
    - source_type='AI'인 경우: 기존 AI 분석 결과만 교체하고 사용자가 직접 등록한 어법('USER')은 안전하게 영구 보존
    - source_type='USER'인 경우: 사용자 분석 결과로 저장 (동일 사용자의 어법만 갱신)
    """
    clean_id = normalize_bracket_id(sentence_id)
    with get_connection() as conn:
        cursor = conn.cursor()
        if source_type == "AI":
            cursor.execute("DELETE FROM sentence_grammar_annotations WHERE sentence_id = ? AND (source_type = 'AI' OR source_type IS NULL)", (clean_id,))
        else:
            if user_id:
                cursor.execute("DELETE FROM sentence_grammar_annotations WHERE sentence_id = ? AND source_type = 'USER' AND user_id = ?", (clean_id, user_id))
            else:
                cursor.execute("DELETE FROM sentence_grammar_annotations WHERE sentence_id = ? AND source_type = 'USER'", (clean_id,))

        for anno in annotations:
            try:
                cat_id = anno.get("category_id", 0)
                leaf_name = anno.get("leaf_name", "") or anno.get("leaf", "")
                if not cat_id or cat_id == 0:
                    cat_id = 10000 + (abs(hash(leaf_name)) % 90000)
                cursor.execute("""
                    INSERT OR REPLACE INTO sentence_grammar_annotations 
                    (sentence_id, category_id, pos, full_path, leaf_name, target_expression, explanation, source_type, user_id, ai_model)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    clean_id,
                    cat_id,
                    anno.get("pos", ""),
                    anno.get("full_path", ""),
                    leaf_name,
                    anno.get("target_expression", ""),
                    anno.get("explanation", "AI 분석" if source_type == "AI" else "사용자 분석"),
                    source_type,
                    user_id,
                    ai_model or anno.get("ai_model")
                ))
            except Exception:
                logger.debug("Failed to insert sentence_grammar_annotation: %s", anno, exc_info=True)
        cursor.execute("UPDATE sentences SET grammar_analyzed = 1 WHERE id = ?", (clean_id,))
        conn.commit()


def add_sentence_grammar_annotation(
    sentence_id: str, 
    annotation: Dict[str, Any], 
    source_type: str = "USER", 
    user_id: str = "default_user", 
    ai_model: Optional[str] = None
) -> bool:
    """문장에 어법 범주 단일 추가 (기본: 사용자 직접 등록)"""
    clean_id = normalize_bracket_id(sentence_id)
    cat_id = annotation.get("category_id", 0)
    pos = annotation.get("pos", "")
    full_path = annotation.get("full_path", "")
    leaf_name = annotation.get("leaf_name", "") or annotation.get("leaf", "")
    target_expression = annotation.get("target_expression", "")
    explanation = annotation.get("explanation", "사용자 분석" if source_type == "USER" else "AI 분석")

    # category_id가 0일 경우 leaf_name 기반 고유 가상 ID 생성
    if not cat_id or cat_id == 0:
        cat_id = 10000 + (abs(hash(leaf_name)) % 90000)

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO sentence_grammar_annotations 
            (sentence_id, category_id, pos, full_path, leaf_name, target_expression, explanation, source_type, user_id, ai_model)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (clean_id, cat_id, pos, full_path, leaf_name, target_expression, explanation, source_type, user_id, ai_model))
        cursor.execute("UPDATE sentences SET grammar_analyzed = 1 WHERE id = ?", (clean_id,))
        conn.commit()
        return True


def delete_sentence_grammar_annotation(sentence_id: str, identifier: int, source_type: Optional[str] = None) -> bool:
    """문장에서 특정 어법 범주 삭제 (category_id 또는 annotation row id 기준, source_type 선택 가능)"""
    clean_id = normalize_bracket_id(sentence_id)
    with get_connection() as conn:
        cursor = conn.cursor()
        if source_type:
            cursor.execute("""
                DELETE FROM sentence_grammar_annotations 
                WHERE sentence_id = ? AND (category_id = ? OR id = ?) AND source_type = ?
            """, (clean_id, identifier, identifier, source_type))
        else:
            cursor.execute("""
                DELETE FROM sentence_grammar_annotations 
                WHERE sentence_id = ? AND (category_id = ? OR id = ?)
            """, (clean_id, identifier, identifier))

        cursor.execute("SELECT COUNT(*) as cnt FROM sentence_grammar_annotations WHERE sentence_id = ?", (clean_id,))
        row = cursor.fetchone()
        if row and row["cnt"] == 0:
            cursor.execute("UPDATE sentences SET grammar_analyzed = 0 WHERE id = ?", (clean_id,))
        conn.commit()
        return True


def reset_sentence_grammar(sentence_id: str, source_type: Optional[str] = None) -> bool:
    """문장의 어법 분석 결과 초기화 (특정 source_type만 초기화하거나 전체 초기화)"""
    clean_id = normalize_bracket_id(sentence_id)
    with get_connection() as conn:
        cursor = conn.cursor()
        if source_type:
            cursor.execute("DELETE FROM sentence_grammar_annotations WHERE sentence_id = ? AND source_type = ?", (clean_id, source_type))
        else:
            cursor.execute("DELETE FROM sentence_grammar_annotations WHERE sentence_id = ?", (clean_id,))

        cursor.execute("SELECT COUNT(*) as cnt FROM sentence_grammar_annotations WHERE sentence_id = ?", (clean_id,))
        row = cursor.fetchone()
        if row and row["cnt"] == 0:
            cursor.execute("UPDATE sentences SET grammar_analyzed = 0 WHERE id = ?", (clean_id,))
        conn.commit()
        return True


def get_sentence_grammar_annotations(sentence_id: str, source_type: Optional[str] = None) -> List[Dict[str, Any]]:
    """특정 문장의 어법 범주 분석 목록 조회 (AI 및 USER 출처 포함, 사용자 분석 우선 정렬)"""
    clean_id = normalize_bracket_id(sentence_id)
    with get_connection() as conn:
        cursor = conn.cursor()
        if source_type:
            cursor.execute("""
                SELECT id, category_id, pos, full_path, leaf_name, target_expression, explanation,
                       COALESCE(source_type, 'AI') AS source_type, user_id, ai_model
                FROM sentence_grammar_annotations
                WHERE sentence_id = ? AND source_type = ?
                ORDER BY id ASC
            """, (clean_id, source_type))
        else:
            cursor.execute("""
                SELECT id, category_id, pos, full_path, leaf_name, target_expression, explanation,
                       COALESCE(source_type, 'AI') AS source_type, user_id, ai_model
                FROM sentence_grammar_annotations
                WHERE sentence_id = ?
                ORDER BY CASE WHEN source_type = 'USER' THEN 0 ELSE 1 END, id ASC
            """, (clean_id,))
        return [dict(r) for r in cursor.fetchall()]


def set_sentence_grammar_annotations(
    sentence_id: str, 
    annotations: List[Dict[str, Any]], 
    source_type: str = "USER", 
    user_id: str = "default_user"
) -> List[Dict[str, Any]]:
    """문장의 어법 범주 목록을 일괄 설정 (기존 해당 source_type 항목만 교체하여 AI와 USER 상호 보존)"""
    clean_id = normalize_bracket_id(sentence_id)

    with get_connection() as conn:
        cursor = conn.cursor()
        if source_type == "USER":
            cursor.execute("DELETE FROM sentence_grammar_annotations WHERE sentence_id = ? AND source_type = 'USER' AND (user_id = ? OR user_id IS NULL)", (clean_id, user_id))
        else:
            cursor.execute("DELETE FROM sentence_grammar_annotations WHERE sentence_id = ? AND (source_type = 'AI' OR source_type IS NULL)", (clean_id,))

        for anno in annotations:
            cat_id = anno.get("category_id", 0)
            leaf_name = anno.get("leaf_name", "") or anno.get("leaf", "")
            if not cat_id or cat_id == 0:
                cat_id = 10000 + (abs(hash(leaf_name)) % 90000)
            try:
                cursor.execute("""
                    INSERT OR REPLACE INTO sentence_grammar_annotations 
                    (sentence_id, category_id, pos, full_path, leaf_name, target_expression, explanation, source_type, user_id, ai_model)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    clean_id,
                    cat_id,
                    anno.get("pos", ""),
                    anno.get("full_path", ""),
                    leaf_name,
                    anno.get("target_expression", ""),
                    anno.get("explanation", "사용자 분석" if source_type == "USER" else "AI 분석"),
                    source_type,
                    user_id if source_type == "USER" else None,
                    anno.get("ai_model")
                ))
            except Exception:
                logger.debug("Failed to insert sentence_grammar_annotation: %s", anno, exc_info=True)
        cursor.execute("UPDATE sentences SET grammar_analyzed = 1 WHERE id = ?", (clean_id,))
        conn.commit()

    return get_sentence_grammar_annotations(clean_id)


# =========================================================================
# 사용자 커스텀 어법 체계 및 매핑 설정 관리 함수
# =========================================================================

def get_user_grammar_settings(user_id: str = "default_user") -> Dict[str, Any]:
    """사용자의 어법 체계 설정 조회 (커스텀 트리 활성화 여부, 커스텀 트리 JSON, 매핑 JSON)"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT user_id, use_custom_tree, custom_tree_json, custom_mapping_json, updated_at 
            FROM user_grammar_settings 
            WHERE user_id = ?
        """, (user_id,))
        row = cursor.fetchone()
        if row:
            res = dict(row)
            res["use_custom_tree"] = bool(res.get("use_custom_tree", 0))
            return res
        return {
            "user_id": user_id,
            "use_custom_tree": False,
            "custom_tree_json": None,
            "custom_mapping_json": None,
            "updated_at": None
        }


def save_user_grammar_settings(
    user_id: str = "default_user",
    use_custom_tree: int = 0,
    custom_tree_json: Optional[str] = None,
    custom_mapping_json: Optional[str] = None
) -> bool:
    """사용자의 어법 커스텀 트리 및 매핑 설정 저장"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO user_grammar_settings 
            (user_id, use_custom_tree, custom_tree_json, custom_mapping_json, updated_at)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, (user_id, 1 if use_custom_tree else 0, custom_tree_json, custom_mapping_json))
        conn.commit()
        return True


def reset_user_grammar_settings(user_id: str = "default_user") -> bool:
    """사용자의 커스텀 어법 설정을 기본 243개 표준 체계로 초기화"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE user_grammar_settings SET use_custom_tree = 0 WHERE user_id = ?", (user_id,))
        conn.commit()
        return True


def get_effective_grammar_categories(user_id: str = "default_user") -> Dict[str, Any]:
    """현재 사용자에게 유효한 어법 범주표 반환 (커스텀 트리가 활성화된 경우 커스텀 트리, 아니면 기본 243개 표준 반환)"""
    settings = get_user_grammar_settings(user_id)
    if settings.get("use_custom_tree") and settings.get("custom_tree_json"):
        try:
            custom_data = json.loads(settings["custom_tree_json"])
            custom_mapping = {}
            if settings.get("custom_mapping_json"):
                try:
                    custom_mapping = json.loads(settings["custom_mapping_json"])
                except Exception:
                    logger.debug("Failed to parse custom_mapping_json", exc_info=True)
            return {
                "is_custom": True,
                "use_custom_tree": True,
                "data": custom_data,
                "mapping": custom_mapping,
                "user_id": user_id
            }
        except Exception as e:
            logger.error("[Custom Grammar Tree Parse Error] %s", e, exc_info=True)

    # 기본 243개 표준 JSON 로드
    std_path = paths.GRAMMAR_CATEGORIES_JSON
    if os.path.exists(std_path):
        try:
            with open(std_path, "r", encoding="utf-8") as f:
                std_data = json.load(f)
            return {
                "is_custom": False,
                "use_custom_tree": False,
                "data": std_data,
                "mapping": {},
                "user_id": user_id
            }
        except Exception as e:
            logger.error("[Standard Grammar Categories Load Error] %s", e, exc_info=True)

    return {"is_custom": False, "use_custom_tree": False, "data": {"list": [], "tree": []}, "mapping": {}, "user_id": user_id}


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
    years: Optional[List[int]] = None,
    month: Optional[int] = None,
    exam_type: str = "",
    question_type: str = "",
    correct_rate_range: str = "",
    tag: str = "",
    is_starred: Optional[bool] = None,
    grammar_cat_id: Optional[int] = None,
    grammar_pos: Optional[str] = None,
    area: str = "",
    whole_word: bool = False,
    limit: int = 0,
    exam_id: str = "",
    sentence_ids: Optional[List[str]] = None,
    user_role: str = access.DEFAULT_ROLE,
    _use_fts: bool = True
) -> List[Dict[str, Any]]:
    """문장 검색 (1행 테이블 뷰용 - 온전한 단어 검색 및 복수 연도, 영역 지원)

    exam_id: 해당 시험지의 문장만 조회 (대괄호 없이 넣어도 됨)
    sentence_ids: 지정한 문장 ID만 조회. 빈 리스트면 즉시 [] 반환 (None이면 조건 없음)
    user_role: 등급별 데이터 필터 (access.py). 기본값 관리자 = 예전과 같은 결과.
               회원 미만이면 정답률/태그/어법 범주 조건을, 관리자가 아니면 즐겨찾기 조건을 무시하고
               응답에서 해당 등급이 볼 수 없는 필드를 뺀다.
    _use_fts: 내부 전용. FTS 쿼리가 실패하면 False로 자기 자신을 다시 호출해 LIKE 검색으로 대체한다.
    """
    # FTS 실패 시 같은 인자로 재호출하기 위해 최초 인자를 보관 (반드시 함수 첫 줄에 둔다)
    _call_args = {k: v for k, v in locals().items() if k != "_use_fts"}
    if sentence_ids is not None and len(sentence_ids) == 0:
        return []
    # 등급별 검색 조건 제한 (조건으로 걸러 보는 것만으로도 메타/개인 데이터가 드러나므로)
    _allowed = access.allowed_search_filters(user_role)
    if not _allowed["meta"]:
        correct_rate_range = ""
        tag = ""
        grammar_cat_id = None
        grammar_pos = None
    if not _allowed["admin"]:
        is_starred = None

    query = """
        SELECT s.*, p.q_num, p.correct_rate, p.question_type, p.area, e.grade, e.year, e.month, e.exam_type, e.subtype
        FROM sentences s
        JOIN passages p ON s.passage_id = p.id
        JOIN exams e ON p.exam_id = e.id
        WHERE 1=1
    """
    params = []

    if area:
        if area == "listening":
            query += " AND p.area = 'listening'"
        elif area == "reading":
            query += " AND (p.area = 'reading' OR p.area IS NULL)"

    if passage_id:
        clean_pid = normalize_bracket_id(passage_id)
        query += " AND s.passage_id = ?"
        params.append(clean_pid)

    if exam_id:
        clean_eid = normalize_bracket_id(exam_id)
        query += " AND p.exam_id = ?"
        params.append(clean_eid)

    if sentence_ids:
        # json_each로 넘기면 SQLite 변수 개수 제한 없이 문장 ID 목록을 한 번에 조건으로 쓸 수 있다
        query += " AND s.id IN (SELECT value FROM json_each(?))"
        params.append(json.dumps(list(sentence_ids), ensure_ascii=False))

    if keyword:
        k_strip = keyword.strip()
        if _use_fts:
            # FTS5 전문 검색 엔진 상시 활용 (7만 문장 풀스캔 350ms -> 3~8ms 초고속화)
            fts_q = _build_fts_query(k_strip, whole_word)
            query += " AND (s.id IN (SELECT sentence_id FROM sentences_fts WHERE sentences_fts MATCH ?) OR s.id LIKE ?)"
            params.extend([fts_q, f"%{k_strip}%"])
        else:
            # FTS 쿼리 실패 시 표준 LIKE 백업
            kw = f"%{k_strip}%"
            query += " AND (s.sentence_text LIKE ? OR s.id LIKE ?)"
            params.extend([kw, kw])

    if grade:
        query += " AND e.grade = ?"
        params.append(grade)
    if years and len(years) > 0:
        placeholders = ",".join(["?"] * len(years))
        query += f" AND e.year IN ({placeholders})"
        params.extend(years)
    elif year:
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
    if correct_rate_range:
        query += _apply_correct_rate_filter(correct_rate_range, "p")

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

    if limit and limit > 0:
        query += " ORDER BY e.year DESC, e.month DESC, p.q_num ASC, s.order_index ASC LIMIT ?"
        params.append(limit)
    else:
        query += " ORDER BY e.year DESC, e.month DESC, p.q_num ASC, s.order_index ASC"

    with get_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(query, params)
            rows = cursor.fetchall()
        except sqlite3.OperationalError as e:
            if keyword and _use_fts:
                logger.warning("[search_sentences] FTS 검색 실패 → LIKE 검색으로 대체: %s", e)
                return search_sentences(**_call_args, _use_fts=False)
            raise
        if not rows:
            return []

        sentence_ids = [r["id"] for r in rows]

        # 1. 일괄 태그 조회 (N+1 쿼리 최적화)
        from collections import defaultdict
        tags_by_sent = defaultdict(list)
        chunk_size = 900
        for i in range(0, len(sentence_ids), chunk_size):
            chunk = sentence_ids[i:i + chunk_size]
            placeholders = ",".join(["?"] * len(chunk))
            cursor.execute(f"SELECT sentence_id, tag_name FROM sentence_tags WHERE sentence_id IN ({placeholders})", chunk)
            for tr in cursor.fetchall():
                tags_by_sent[tr["sentence_id"]].append(tr["tag_name"])

        # 2. 일괄 어법 범주 조회 (N+1 쿼리 최적화)
        annos_by_sent = defaultdict(list)
        for i in range(0, len(sentence_ids), chunk_size):
            chunk = sentence_ids[i:i + chunk_size]
            placeholders = ",".join(["?"] * len(chunk))
            cursor.execute(f"""
                SELECT id, sentence_id, category_id, pos, full_path, leaf_name, target_expression, explanation,
                       COALESCE(source_type, 'AI') AS source_type, user_id, ai_model
                FROM sentence_grammar_annotations
                WHERE sentence_id IN ({placeholders})
                ORDER BY CASE WHEN source_type = 'USER' THEN 0 ELSE 1 END, id ASC
            """, chunk)
            for ar in cursor.fetchall():
                annos_by_sent[ar["sentence_id"]].append(dict(ar))

        # 3. 아직 밑줄/빈칸이 남은 문장의 지문 정보(본문·정답·해설)를 한 번에 조회 (예전: 문장마다 지문을 따로 조회하는 N+1)
        blank_pids = list({r["passage_id"] for r in rows if r["passage_id"] and "__" in (r["sentence_text"] or "")})
        passage_info: Dict[str, Dict[str, Any]] = {}
        for i in range(0, len(blank_pids), chunk_size):
            chunk = blank_pids[i:i + chunk_size]
            placeholders = ",".join(["?"] * len(chunk))
            cursor.execute(
                f"SELECT id, passage_text, answer_text, explanation_text FROM passages WHERE id IN ({placeholders})",
                chunk
            )
            for pr in cursor.fetchall():
                passage_info[pr["id"]] = dict(pr)

        results = []
        for idx, r in enumerate(rows, 1):
            s_dict = dict(r)
            s_dict["row_num"] = idx
            s_dict["is_starred"] = 1 if r["is_starred"] == 1 else 0
            s_dict["grammar_analyzed"] = 1 if r["grammar_analyzed"] == 1 else 0
            s_dict["tags"] = tags_by_sent.get(r["id"], [])
            s_dict["grammar_annotations"] = annos_by_sent.get(r["id"], [])

            # 만약 문장에 아직 밑줄/빈칸이 남아있는 경우 온전한 정답 선지 문장으로 실시간 변환
            if "__" in s_dict.get("sentence_text", ""):
                try:
                    p_info = passage_info.get(s_dict.get("passage_id")) or {}
                    prep = fill_blanks(
                        s_dict["sentence_text"],
                        p_info.get("passage_text") or "",
                        p_info.get("answer_text") or "",
                        p_info.get("explanation_text") or ""
                    )
                    if prep and prep != s_dict["sentence_text"]:
                        s_dict["sentence_text"] = prep
                except Exception:
                    logger.debug("Failed to fill_blanks for sentence %s", s_dict.get("id"), exc_info=True)

            results.append(s_dict)
        return access.filter_sentences(results, user_role)


def get_listening_passages_by_exam(exam_id: str) -> List[Dict[str, Any]]:
    """특정 시험지의 듣기 문항(area='listening' 또는 q_num <= 17) 목록 조회 (q_num 순 정렬)"""
    clean_id = normalize_bracket_id(exam_id)
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT p.*, e.grade, e.year, e.month, e.exam_type
            FROM passages p
            JOIN exams e ON p.exam_id = e.id
            WHERE p.exam_id = ? AND (p.area = 'listening' OR p.q_num <= COALESCE(e.listening_end_q, 17))
            ORDER BY p.q_num ASC
        """, (clean_id,))
        rows = cursor.fetchall()
        result = []
        for r in rows:
            d = dict(r)
            d["tags"] = get_passage_tags(d["id"])
            if d.get("choice_rates") and isinstance(d["choice_rates"], str):
                try:
                    d["choice_rates_obj"] = json.loads(d["choice_rates"])
                except Exception:
                    logger.debug("Failed to parse choice_rates json: %s", d.get("choice_rates"), exc_info=True)
                    d["choice_rates_obj"] = None
            result.append(d)
        return result


def update_passage_audio(passage_id: str, audio_file_path: str) -> bool:
    """문항 오디오 파일 경로 갱신"""
    clean_id = normalize_bracket_id(passage_id)
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE passages SET audio_file_path = ? WHERE id = ?", (audio_file_path, clean_id))
        conn.commit()
        return cursor.rowcount > 0


def update_passage_script(
    passage_id: str,
    script_text: Optional[str] = None,
    fels_text: Optional[str] = None,
    script_crop_image: Optional[str] = None
) -> bool:
    """문항 대본 텍스트, FELS 텍스트 및 대본 크롭 이미지 경로 갱신"""
    clean_id = normalize_bracket_id(passage_id)
    updates = []
    params = []
    if script_text is not None:
        updates.append("script_text = ?")
        params.append(script_text)
    if fels_text is not None:
        updates.append("fels_text = ?")
        params.append(fels_text)
    if script_crop_image is not None:
        updates.append("script_crop_image = ?")
        params.append(script_crop_image)
    if not updates:
        return False
    params.append(clean_id)
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(f"UPDATE passages SET {', '.join(updates)} WHERE id = ?", params)
        conn.commit()
        return cursor.rowcount > 0


def update_passage_memo(passage_id: str, memo_text: str) -> Dict[str, Any]:
    """특정 지문의 사용자 메모 업데이트 및 갱신 시간 기록"""
    if not passage_id:
        return {"success": False, "error": "passage_id is required"}
    clean_id = normalize_bracket_id(passage_id)

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE passages SET user_memo = ?, user_memo_updated_at = ? WHERE id = ?",
            (memo_text, now_str, clean_id)
        )
        if cursor.rowcount == 0:
            cursor.execute(
                "UPDATE passages SET user_memo = ?, user_memo_updated_at = ? WHERE id = ?",
                (memo_text, now_str, clean_id.strip("[]"))
            )
        conn.commit()
        updated = cursor.rowcount > 0
        return {
            "success": updated,
            "passage_id": clean_id,
            "memo": memo_text,
            "updated_at": now_str if updated else None
        }


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


# init_db()는 import 시점에 자동 실행하지 않는다 (import 부작용 제거).
# - 웹 서버: app.py의 FastAPI lifespan에서 기동 시 1회 호출
# - tools/*.py 등 단독 스크립트: main()에서 db.init_db()를 직접 호출
