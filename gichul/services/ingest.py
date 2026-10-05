"""
05-gichul_db: 시험지 업로드 후처리, 크롭 재생성 및 백그라운드 분석 서비스 (gichul/services/ingest.py)
"""

import os
import re
import glob
from typing import Optional, Dict

import pymupdf as fitz

from .. import database as db
from .. import paths
from .. import answer_keys
from ..pdf_parser import extract_pdf_columns_and_questions
from ..hwp_parser import convert_hwp_to_pdf
from ..exam_profiles import get_exam_profile, run_special_crop
from ..logging_config import get_logger
from ..core.state import search_cache
from ..services import grammar_service
from .. import grammar_analyzer

logger = get_logger("gichul.services.ingest")
UPLOADS_DIR = paths.UPLOADS_DIR


def regenerate_exam_crops(exam_id: str, grade: str, year: int, month: int, reading_start: Optional[int], reading_end: Optional[int], answers_dict: Optional[Dict[int, str]], subtype: Optional[str] = None) -> bool:
    """원본 PDF가 있으면 정답 선지 형광펜 하이라이트 크롭 이미지를 재생성하고 경로를 DB에 동기화"""
    if not subtype:
        m_sub = re.search(r"-([AB]형)", exam_id)
        if m_sub:
            subtype = m_sub.group(1)
    search_patterns = [
        os.path.join(UPLOADS_DIR, f"{grade}_{year}_{month:02d}_*.pdf"),
        os.path.join(UPLOADS_DIR, f"{grade}_{year}_{month}_*.pdf"),
        os.path.join(UPLOADS_DIR, f"*{year}*{month:02d}*.pdf"),
        os.path.join(UPLOADS_DIR, f"*{year}*{month}*.pdf"),
        os.path.join(UPLOADS_DIR, f"*{grade}*{year}*.pdf"),
    ]
    pdf_candidates = []
    for pat in search_patterns:
        matched = [p for p in glob.glob(pat) if "_ans_" not in os.path.basename(p) and "_script" not in os.path.basename(p)]
        if subtype:
            sub_key = subtype.replace("형", "")
            sub_matched = [p for p in matched if re.search(rf"[-_\[\s]{sub_key}(?:형)?(?:[-_\]\s]|\.|$)", os.path.basename(p), re.I)]
            if sub_matched:
                pdf_candidates = sub_matched
                break
        if matched and not pdf_candidates:
            pdf_candidates = matched
            break
    if not pdf_candidates:
        return False
    try:
        profile = get_exam_profile(grade, year, month, subtype)
        if (reading_end is None or reading_end == 45) and profile.is_50_questions:
            reading_end = profile.reading_end
        if (reading_start is None or reading_start == 18) and profile.is_ab_period:
            reading_start = profile.reading_start

        # 스캔본 PDF(텍스트 0자) 감지 시 동명 HWP 원본으로부터 고화질 디지털 PDF 자동 생성
        target_pdf = pdf_candidates[0]
        try:
            test_doc = fitz.open(target_pdf)
            is_empty_pdf = sum(len(p.get_text()) for p in test_doc) < 50
            test_doc.close()
            if is_empty_pdf:
                hwp_pat = os.path.splitext(target_pdf)[0] + ".hwp"
                if not os.path.exists(hwp_pat):
                    hwp_pat = os.path.splitext(target_pdf)[0] + ".hwpx"
                if os.path.exists(hwp_pat):
                    if convert_hwp_to_pdf(hwp_pat, target_pdf):
                        logger.info(f"[Crops] 스캔본 PDF를 HWP 원본({hwp_pat})으로부터 디지털 PDF로 자동 재변환 완료")
        except Exception as scan_err:
            logger.warning(f"[Crops] 스캔본 PDF 자동 치환 검사 중 경고: {scan_err}", exc_info=True)

        # 정답 사전 보완 (verified_key 및 DB 저장값 결합)
        full_answers = dict(answer_keys.load_answer_key(grade, year, month) or {})
        if answers_dict:
            full_answers.update(answers_dict)
        try:
            with db.get_connection() as conn:
                cur = conn.cursor()
                rows = cur.execute("SELECT q_num, answer_text FROM passages WHERE exam_id = ?", (exam_id,)).fetchall()
                for r in rows:
                    if r["answer_text"] and r["q_num"] not in full_answers:
                        full_answers[r["q_num"]] = r["answer_text"]
        except Exception:
            logger.debug(f"[Crops] {exam_id} 기존 정답 조회 예외 (무시)", exc_info=True)

        # 1. 독해 문항 크롭 생성 (정답 형광펜 포함)
        crop_results = extract_pdf_columns_and_questions(
            pdf_path=target_pdf, grade=grade, year=year, month=month,
            start_q=reading_start, end_q=reading_end, answers_dict=full_answers,
            subtype=subtype
        )

        # 2. 듣기 문항 크롭도 정답 형광펜 주석을 포함하여 함께 재생성
        listening_end = (reading_start - 1) if (reading_start and reading_start > 1) else profile.listening_end
        try:
            listening_crops = extract_pdf_columns_and_questions(
                pdf_path=target_pdf, grade=grade, year=year, month=month,
                start_q=1, end_q=listening_end, answers_dict=full_answers
            )
            crop_results.update(listening_crops)
        except Exception as l_crop_err:
            logger.warning(f"[Crops] {exam_id} 듣기 문항 형광펜 크롭 생성 중 경고: {l_crop_err}", exc_info=True)

        # [특수 예외 폴백] 고3 2013년 9월 등 벡터 폰트 외곽선 변환 문서 전용 크롭 연동
        if not crop_results and profile.special_crop:
            sub = subtype or ("A형" if "-A" in exam_id else "B형")
            if run_special_crop(profile.special_crop, exam_id, sub):
                logger.info(f"[Crops] {exam_id} 전용 고정밀 기하 크롭 생성 완료")
                return True

        with db.get_connection() as conn:
            cursor = conn.cursor()
            for q_n, q_data in crop_results.items():
                crop_url = q_data.get("pdf_crop_image", "")
                if crop_url:
                    cursor.execute(
                        "UPDATE passages SET pdf_crop_image = ? WHERE exam_id = ? AND q_num = ?",
                        (crop_url, exam_id, q_n)
                    )
            conn.commit()
        logger.info(f"[Crops] {exam_id} 정답 형광펜 크롭 {len(crop_results)}개(듣기+독해) 재생성 완료")
        return True
    except Exception as crop_err:
        logger.warning(f"[Crops] {exam_id} PDF 하이라이트 갱신 중 경고: {crop_err}", exc_info=True)
        return False


# 하위 호환 별칭
_regenerate_exam_crops = regenerate_exam_crops


def background_auto_analyze_exam_grammar(exam_id: str):
    """업로드 완료 후 백그라운드에서 해당 시험지의 문장 자동 어법 분석"""
    try:
        active_configs = grammar_analyzer.get_active_ai_configs()
        if not any(c["api_key"] for c in active_configs):
            return

        # 해당 시험지의 문장 전체를 SQL 조건으로 조회
        target_sentences = db.search_sentences(exam_id=exam_id)
        passages_cache = {}
        for s in target_sentences:
            try:
                if s.get("grammar_analyzed") or s.get("grammar_annotations"):
                    continue
                grammar_service.analyze_and_save_sentence(s, passages_cache)
            except Exception as ex:
                logger.error(f"[Background Grammar Analysis Error] {s['id']}: {ex}", exc_info=True)
    except Exception as e:
        logger.error(f"[Background Grammar Task Error] {e}", exc_info=True)
    finally:
        # 응답이 나간 뒤에 실행되므로 캐시 무효화 미들웨어가 잡지 못한다 → 직접 비운다
        search_cache.clear()
        db.invalidate_exams_cache()
