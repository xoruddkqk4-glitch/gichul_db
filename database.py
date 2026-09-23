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
from datetime import datetime
from typing import List, Dict, Optional, Any
from collections import defaultdict

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "gichul.db")


def _regexp_func(expr: Optional[str], item: Optional[str]) -> bool:
    """SQLite REGEXP 커스텀 함수 (대소문자 무시 단어 경계/정규식 매칭)"""
    if expr is None or item is None:
        return False
    try:
        return bool(re.search(expr, item, re.IGNORECASE))
    except Exception:
        return False


def get_connection() -> sqlite3.Connection:
    """SQLite 데이터베이스 연결 반환 (ROW 딕셔너리 팩토리 및 REGEXP 함수 등록)"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA synchronous = NORMAL;")
    conn.execute("PRAGMA cache_size = -64000;")
    conn.execute("PRAGMA mmap_size = 268435456;")
    conn.execute("PRAGMA temp_store = MEMORY;")
    conn.create_function("REGEXP", 2, _regexp_func)
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
            "ALTER TABLE exams ADD COLUMN listening_start_q INTEGER DEFAULT 1;",
            "ALTER TABLE exams ADD COLUMN listening_end_q INTEGER DEFAULT 17;",
        ):
            try:
                cursor.execute(col_sql)
            except sqlite3.OperationalError:
                pass

        # 기존 지문들의 기본 area를 'reading'으로 보정
        try:
            cursor.execute("UPDATE passages SET area = 'reading' WHERE area IS NULL OR area = '';")
        except Exception:
            pass

        # 빈 문제 유형을 '기타'로 자동 보정
        try:
            cursor.execute("UPDATE passages SET question_type = '기타' WHERE question_type IS NULL OR question_type = '' OR trim(question_type) = '';")
        except Exception:
            pass

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

        # 기존에 이미 어법 분석 결과가 등록된 문장들은 분석 완료(1)로 동기화
        try:
            cursor.execute("""
                UPDATE sentences 
                SET grammar_analyzed = 1 
                WHERE id IN (SELECT DISTINCT sentence_id FROM sentence_grammar_annotations)
            """)
        except Exception:
            pass

        # sentences 테이블에 빈칸(____)이 남아있는 기존 문장들 정답 선지 자동 완성 동기화
        try:
            cursor.execute("SELECT id, passage_id, sentence_text FROM sentences WHERE sentence_text LIKE '%\\_\\_%' ESCAPE '\\'")
            unfilled_rows = cursor.fetchall()
            if unfilled_rows:
                from grammar_analyzer import prepare_sentence_for_analysis
                for ur in unfilled_rows:
                    cur_p = None
                    pid = ur["passage_id"]
                    if pid:
                        cursor.execute("SELECT passage_text, answer_text, explanation_text FROM passages WHERE id = ?", (pid,))
                        p_row = cursor.fetchone()
                        if p_row:
                            cur_p = dict(p_row)
                    
                    prep_text = prepare_sentence_for_analysis(
                        ur["sentence_text"],
                        passage_id=pid,
                        passage_text=cur_p.get("passage_text", "") if cur_p else "",
                        answer_text=cur_p.get("answer_text", "") if cur_p else "",
                        explanation_text=cur_p.get("explanation_text", "") if cur_p else ""
                    )
                    if prep_text and prep_text != ur["sentence_text"]:
                        words = re.findall(r"\b[\w'-]+\b", prep_text)
                        cursor.execute(
                            "UPDATE sentences SET sentence_text = ?, word_count = ? WHERE id = ?",
                            (prep_text.strip(), len(words), ur["id"])
                        )
        except Exception as mig_err:
            print(f"[Init DB Blank Sentence Migration Error] {mig_err}")

        # passages 테이블의 해설(explanation_text) 상단 [정답] 표기를 정답표 이미지/검증 정답(answer_text)과 자동 동기화
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
                        new_exp = re.sub(r"^\s*\[\s*정답\s*\]\s*[①②③④⑤1-5]?", f"[정답] {ans}", exp)
                        cursor.execute("UPDATE passages SET explanation_text = ? WHERE id = ?", (new_exp, pr["id"]))
                else:
                    new_exp = f"[정답] {ans}\n\n{exp.strip()}".strip()
                    cursor.execute("UPDATE passages SET explanation_text = ? WHERE id = ?", (new_exp, pr["id"]))
        except Exception as sync_err:
            print(f"[Init DB Answer Sync Error] {sync_err}")


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
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_passages_exam_qnum ON passages(exam_id, q_num);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_sentences_passage ON sentences(passage_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_passage_tags_pid ON passage_tags(passage_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_passage_tags_tag ON passage_tags(tag_name);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_sentence_tags_sid ON sentence_tags(sentence_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_sentence_tags_tag ON sentence_tags(tag_name);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_s_grammar_cat ON sentence_grammar_annotations(category_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_s_grammar_pos ON sentence_grammar_annotations(pos);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_sentences_starred ON sentences(is_starred);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_sentences_analyzed ON sentences(grammar_analyzed);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_passages_correct_rate ON passages(correct_rate);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_passages_area ON passages(area);")

        conn.commit()


# --- CRUD 및 검색 헬퍼 함수 ---

def save_exam(exam_data: dict) -> str:
    """시험지 정보 저장 (기존 존재 시 갱신)"""
    if "listening_start_q" not in exam_data:
        exam_data["listening_start_q"] = 1
    if "listening_end_q" not in exam_data:
        exam_data["listening_end_q"] = 17
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO exams (id, grade, year, month, exam_type, reading_start_q, reading_end_q, listening_start_q, listening_end_q)
            VALUES (:id, :grade, :year, :month, :exam_type, :reading_start_q, :reading_end_q, :listening_start_q, :listening_end_q)
            ON CONFLICT(id) DO UPDATE SET
                grade = excluded.grade,
                year = excluded.year,
                month = excluded.month,
                exam_type = excluded.exam_type,
                reading_start_q = excluded.reading_start_q,
                reading_end_q = excluded.reading_end_q,
                listening_start_q = excluded.listening_start_q,
                listening_end_q = excluded.listening_end_q
        """, exam_data)
        conn.commit()
        return exam_data["id"]


def get_all_exams_with_stats() -> List[Dict[str, Any]]:
    """등록된 모든 시험지 목록 및 3대 데이터 영역(원본 파일, 코어 본문, 메타데이터) 통계 조회"""
    import glob
    base_dir = os.path.dirname(os.path.abspath(__file__))
    uploads_dir = os.path.join(base_dir, "uploads")
    captures_dir = os.path.join(base_dir, "static", "captures")

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 
                e.id,
                e.grade,
                e.year,
                e.month,
                e.exam_type,
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

        # 각 시험지별 메타데이터(어법 분석, 태그) 및 디스크 파일(원본 파일, 캡처) 통계 보강
        for ex in exams:
            eid = ex["id"]
            grade = ex["grade"]
            year = ex["year"]
            month = ex["month"]

            # 1) 메타데이터 통계: 어법 분석 개수 & 태그 개수
            cursor.execute("""
                SELECT COUNT(DISTINCT a.id)
                FROM sentence_grammar_annotations a
                JOIN sentences s ON a.sentence_id = s.id
                JOIN passages p ON s.passage_id = p.id
                WHERE p.exam_id = ?
            """, (eid,))
            ex["grammar_count"] = cursor.fetchone()[0]

            cursor.execute("""
                SELECT 
                    (SELECT COUNT(*) FROM passage_tags pt JOIN passages p ON pt.passage_id = p.id WHERE p.exam_id = ?) +
                    (SELECT COUNT(*) FROM sentence_tags st JOIN sentences s ON st.sentence_id = s.id JOIN passages p ON s.passage_id = p.id WHERE p.exam_id = ?)
            """, (eid, eid))
            ex["tag_count"] = cursor.fetchone()[0]

            # 2) 원본 파일(uploads/) 통계: 파일 개수 및 총 바이트 크기
            raw_pattern = os.path.join(uploads_dir, f"{grade}_{year}_{month:02d}_*")
            raw_files = glob.glob(raw_pattern)
            raw_size = sum(os.path.getsize(f) for f in raw_files if os.path.isfile(f))
            ex["raw_file_count"] = len(raw_files)
            ex["raw_file_size_bytes"] = raw_size
            ex["raw_file_size_mb"] = round(raw_size / (1024 * 1024), 2)
            raw_basenames = [os.path.basename(f) for f in raw_files]
            ex["raw_files"] = raw_basenames

            # 4대 파일(PDF, HWP, 정답표 이미지, 정답률 CSV) 개별 유무 판별
            pdf_file = next((f for f in raw_basenames if f.lower().endswith(".pdf")), None)
            hwp_file = next((f for f in raw_basenames if f.lower().endswith((".hwp", ".hwpx")) and "_exp_" not in f), None)
            ans_file = next((f for f in raw_basenames if "_ans_" in f or f.lower().endswith((".png", ".jpg", ".jpeg"))), None)
            csv_file = next((f for f in raw_basenames if f.lower().endswith(".csv")), None)

            # 지문 정답 및 정답률 입력 현황 조회
            cursor.execute("""
                SELECT 
                    COUNT(*) AS total_passages,
                    SUM(CASE WHEN answer_text IS NOT NULL AND TRIM(answer_text) != '' THEN 1 ELSE 0 END) AS answered_passages,
                    SUM(CASE WHEN correct_rate IS NOT NULL THEN 1 ELSE 0 END) AS rated_passages,
                    AVG(correct_rate) AS avg_correct_rate
                FROM passages
                WHERE exam_id = ?
            """, (eid,))
            ans_row = cursor.fetchone()
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

            # 3) 크롭 캡처 이미지(static/captures/) 개수
            cap_pattern = os.path.join(captures_dir, f"{grade}_{year}_{month:02d}_*.png")
            ex["captures_count"] = len(glob.glob(cap_pattern))

        return exams


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
    base_dir = os.path.dirname(os.path.abspath(__file__))
    uploads_dir = os.path.join(base_dir, "uploads")
    captures_dir = os.path.join(base_dir, "static", "captures")

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
                    pass

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
                    pass

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
                    pass
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
        return del_res


def delete_exam(exam_id: str) -> Dict[str, Any]:
    """하위 호환성을 위한 완전 삭제 함수 (4대 영역 모두 삭제)"""
    return selective_delete_exam(exam_id, delete_raw=True, delete_core=True, delete_metadata=True, delete_rate=True)


def save_passage(passage_data: dict) -> str:
    """지문 정보 저장"""
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

    with get_connection() as conn:
        cursor = conn.cursor()
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
        conn.commit()
        return passage_data["id"]


def set_answer_status(exam_id: str, sources: Dict[int, str], verified: Dict[int, bool]):
    """문항별 정답 출처(answer_source)와 검증 여부(answer_verified) 기록"""
    with get_connection() as conn:
        cursor = conn.cursor()
        for q_num, source in sources.items():
            cursor.execute(
                "UPDATE passages SET answer_source = ?, answer_verified = ? WHERE exam_id = ? AND q_num = ?",
                (source, 1 if verified.get(q_num) else 0, exam_id, q_num)
            )
        conn.commit()


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
            if re.search(r"^\s*\[\s*정답\s*\]", exp):
                exp = re.sub(r"^\s*\[\s*정답\s*\]\s*[①②③④⑤1-5]?", f"[정답] {ans}", exp, count=1)
            else:
                exp = f"[정답] {ans}\n\n{exp}".strip()
            cursor.execute(
                "UPDATE passages SET answer_text = ?, explanation_text = ?, answer_source = ?, answer_verified = ? WHERE id = ?",
                (ans, exp, source, verified, row["id"])
            )
        conn.commit()


def save_exam_correct_rates(exam_id: str, rates_dict: Dict[int, Dict[str, Any]]) -> Dict[str, Any]:
    """
    특정 시험지의 문항별 정답률 및 선지 선택률 일괄 DB 갱신 (정답은 건드리지 않음 - 정답 교차검증은 answer_resolver 담당)
    rates_dict: { q_num: { 'correct_rate': float, 'choice_rates': dict, 'correct_ans_circle': str } }
    """
    clean_id = exam_id.strip()
    if not clean_id.startswith("["):
        clean_id = f"[{clean_id}]"

    updated_count = 0
    rates_collected = []

    with get_connection() as conn:
        cursor = conn.cursor()
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

        conn.commit()

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


def update_sentence_text(sentence_id: str, new_text: str, word_count: Optional[int] = None) -> bool:
    """단일 문장의 본문 텍스트 및 단어 수 수정 업데이트"""
    clean_id = sentence_id.strip()
    if not clean_id.startswith("["):
        clean_id = f"[{clean_id}]"
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


def search_passages(
    keyword: str = "",
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
    limit: int = 0
) -> List[Dict[str, Any]]:
    """지문 검색 (지문 본문, 발문, 해설, 스크립트, 출처, 태그, 문제유형, 시험구분, 영역 - 온전한 단어 검색 및 복수 연도 지원)"""
    query = """
        SELECT p.*, e.grade, e.year, e.month, e.exam_type, e.reading_start_q, e.reading_end_q
        FROM passages p
        JOIN exams e ON p.exam_id = e.id
        WHERE 1=1
    """
    params = []

    if keyword:
        k_strip = keyword.strip()
        if whole_word:
            # 온전한 단어 검색: 앞뒤로 단어 문자(\w, 영문/숫자/한글)가 없는 독립 단어 일치
            pattern = r"(?<!\w)" + re.escape(k_strip).replace(r"\ ", r"\s+") + r"(?!\w)"
            query += """
                AND (
                    p.id REGEXP ? OR
                    p.passage_text REGEXP ? OR
                    p.question_title REGEXP ? OR
                    p.explanation_text REGEXP ? OR
                    p.script_text REGEXP ?
                )
            """
            params.extend([pattern, pattern, pattern, pattern, pattern])
        else:
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
        cursor.execute(query, params)
        rows = cursor.fetchall()
        if not rows:
            return []

        passage_ids = [r["id"] for r in rows]
        tags_by_passage = defaultdict(list)
        chunk_size = 900
        for i in range(0, len(passage_ids), chunk_size):
            chunk = passage_ids[i:i + chunk_size]
            placeholders = ",".join(["?"] * len(chunk))
            cursor.execute(
                f"SELECT passage_id, tag_name FROM passage_tags WHERE passage_id IN ({placeholders}) ORDER BY id ASC",
                chunk
            )
            for tr in cursor.fetchall():
                tags_by_passage[tr["passage_id"]].append(tr["tag_name"])

        results = []
        for r in rows:
            p_dict = dict(r)
            p_dict["tags"] = tags_by_passage.get(r["id"], [])
            if p_dict.get("choice_rates") and isinstance(p_dict["choice_rates"], str):
                try:
                    p_dict["choice_rates_obj"] = json.loads(p_dict["choice_rates"])
                except Exception:
                    p_dict["choice_rates_obj"] = None
            results.append(p_dict)
        return results


def get_passage(passage_id: str) -> Optional[Dict[str, Any]]:
    """지문 ID로 단일 지문 정보 조회"""
    if not passage_id:
        return None
    clean_id = passage_id.strip()
    if not clean_id.startswith("["):
        clean_id = f"[{clean_id}]"
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM passages WHERE id = ?", (clean_id,))
        row = cursor.fetchone()
        if not row:
            cursor.execute("SELECT * FROM passages WHERE id = ?", (clean_id.strip("[]"),))
            row = cursor.fetchone()
        if row:
            p_dict = dict(row)
            p_dict["tags"] = get_passage_tags(p_dict["id"])
            if p_dict.get("choice_rates") and isinstance(p_dict["choice_rates"], str):
                try:
                    p_dict["choice_rates_obj"] = json.loads(p_dict["choice_rates"])
                except Exception:
                    p_dict["choice_rates_obj"] = None
            return p_dict
        return None


def get_sentence(sentence_id: str) -> Optional[Dict[str, Any]]:
    """문장 ID로 단일 문장 정보 조회"""
    if not sentence_id:
        return None
    clean_id = sentence_id.strip()
    if not clean_id.startswith("["):
        clean_id = f"[{clean_id}]"
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
        cursor.execute("UPDATE sentences SET grammar_analyzed = 1 WHERE id = ?", (clean_id,))
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
        cursor.execute("UPDATE sentences SET grammar_analyzed = 1 WHERE id = ?", (clean_id,))
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
        cursor.execute("SELECT COUNT(*) as cnt FROM sentence_grammar_annotations WHERE sentence_id = ?", (clean_id,))
        row = cursor.fetchone()
        if row and row["cnt"] == 0:
            cursor.execute("UPDATE sentences SET grammar_analyzed = 0 WHERE id = ?", (clean_id,))
        conn.commit()
        return True


def reset_sentence_grammar(sentence_id: str) -> bool:
    """문장의 어법 분석 결과 및 상태를 초기화(미분석 상태)로 복원하여 재분석 허용"""
    clean_id = sentence_id.strip()
    if not clean_id.startswith("["):
        clean_id = f"[{clean_id}]"
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM sentence_grammar_annotations WHERE sentence_id = ?", (clean_id,))
        cursor.execute("UPDATE sentences SET grammar_analyzed = 0 WHERE id = ?", (clean_id,))
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
        cursor.execute("UPDATE sentences SET grammar_analyzed = 1 WHERE id = ?", (clean_id,))
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
    limit: int = 0
) -> List[Dict[str, Any]]:
    """문장 검색 (1행 테이블 뷰용 - 온전한 단어 검색 및 복수 연도, 영역 지원)"""
    query = """
        SELECT s.*, p.q_num, p.correct_rate, p.question_type, p.area, e.grade, e.year, e.month, e.exam_type
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
        clean_pid = passage_id.strip()
        if not clean_pid.startswith("["):
            clean_pid = f"[{clean_pid}]"
        query += " AND s.passage_id = ?"
        params.append(clean_pid)

    if keyword:
        k_strip = keyword.strip()
        if whole_word:
            # 온전한 단어 검색: 앞뒤로 단어 문자(\w, 영문/숫자/한글)가 없는 독립 단어 일치
            pattern = r"(?<!\w)" + re.escape(k_strip).replace(r"\ ", r"\s+") + r"(?!\w)"
            query += " AND (s.sentence_text REGEXP ? OR s.id REGEXP ?)"
            params.extend([pattern, pattern])
        else:
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
        cursor.execute(query, params)
        rows = cursor.fetchall()
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
                SELECT id, sentence_id, category_id, pos, full_path, leaf_name, target_expression, explanation
                FROM sentence_grammar_annotations
                WHERE sentence_id IN ({placeholders})
                ORDER BY id ASC
            """, chunk)
            for ar in cursor.fetchall():
                annos_by_sent[ar["sentence_id"]].append(dict(ar))

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
                    from grammar_analyzer import prepare_sentence_for_analysis
                    prep = prepare_sentence_for_analysis(s_dict["sentence_text"], passage_id=s_dict.get("passage_id"))
                    if prep and prep != s_dict["sentence_text"]:
                        s_dict["sentence_text"] = prep
                except Exception:
                    pass

            results.append(s_dict)
        return results


def get_listening_passages_by_exam(exam_id: str) -> List[Dict[str, Any]]:
    """특정 시험지의 듣기 문항(area='listening' 또는 q_num <= 17) 목록 조회 (q_num 순 정렬)"""
    clean_id = exam_id.strip()
    if not clean_id.startswith("["):
        clean_id = f"[{clean_id}]"
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT p.*, e.grade, e.year, e.month, e.exam_type
            FROM passages p
            JOIN exams e ON p.exam_id = e.id
            WHERE p.exam_id = ? AND (p.area = 'listening' OR p.q_num <= 17)
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
                    d["choice_rates_obj"] = None
            result.append(d)
        return result


def update_passage_audio(passage_id: str, audio_file_path: str) -> bool:
    """문항 오디오 파일 경로 갱신"""
    clean_id = passage_id.strip()
    if not clean_id.startswith("["):
        clean_id = f"[{clean_id}]"
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
    clean_id = passage_id.strip()
    if not clean_id.startswith("["):
        clean_id = f"[{clean_id}]"
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
