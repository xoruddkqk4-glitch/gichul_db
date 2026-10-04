"""
tools/regenerate_group_crops.py
독해 1지문 2문항(41~42번) 및 1지문 3문항(43~45번)에 대해
지문 누락 방지 및 정답 형광펜 하이라이트가 포함된 통합 크롭 이미지를 일괄 재생성하고 DB를 갱신합니다.
"""

import os
import glob
import time
import sqlite3
import sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from gichul import pdf_parser
from gichul.paths import DB_PATH
from PIL import Image

def find_pdf_for_exam(grade: str, year: int, month: int, subtype: str = None) -> str:
    patterns = [
        f"uploads/*{year}*{month:02d}*{grade}*.pdf",
        f"uploads/*{grade}*{year}*{month:02d}*.pdf",
        f"uploads/*{grade}*{year}*{month}*.pdf"
    ]
    for pat in patterns:
        for f in glob.glob(pat):
            if "script" in f or "old_scan" in f:
                continue
            if subtype and subtype in f:
                return f
            return f
    return None

def main():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # 대상: 2012년 이후 45문항 체제 시험 중 41~45번 크롭 갱신이 필요한 시험지
    exams = cur.execute("""
        SELECT id, grade, year, month, subtype, reading_start_q, reading_end_q
        FROM exams
        WHERE year >= 2012
        ORDER BY year DESC, month DESC
    """).fetchall()

    print(f"=== 41~45번 복합 지문 크롭 검사 시작 (총 {len(exams)}개 세트) ===")

    updated_exams = 0
    total_crops_updated = 0

    for ex in exams:
        eid, grade, year, month, subtype, start_q, end_q = ex
        p_rows = cur.execute(
            "SELECT q_num, pdf_crop_image FROM passages WHERE exam_id=? AND q_num IN (41, 42, 43, 44, 45)",
            (eid,)
        ).fetchall()
        if not p_rows:
            continue

        pmap = {r[0]: r[1] for r in p_rows}
        p41 = pmap.get(41, "")
        p42 = pmap.get(42, "")
        p43 = pmap.get(43, "")
        p44 = pmap.get(44, "")
        p45 = pmap.get(45, "")

        needs = False
        # 43, 44, 45가 통합 이미지로 연결되지 않은 경우
        if p43 and (p43 != p44 or p43 != p45):
            needs = True
        # 41번 이미지가 지문 없이 문항만 있는 경우 (높이 < 600)
        if p41:
            f41 = "." + p41
            if os.path.exists(f41) and Image.open(f41).height < 600:
                needs = True
        # 42번 이미지가 41번과 통합되지 않았거나 지문이 없는 경우
        if p42 and p41 != p42:
            needs = True

        if not needs:
            continue

        pdf = find_pdf_for_exam(grade, year, month, subtype)
        if not pdf:
            print(f"[SKIP] {eid}: PDF 파일 없음")
            continue

        ans_rows = cur.execute("SELECT q_num, answer_text FROM passages WHERE exam_id=?", (eid,)).fetchall()
        answers_dict = {r[0]: r[1] for r in ans_rows}

        t0 = time.time()
        try:
            crops = pdf_parser.extract_pdf_columns_and_questions(
                pdf_path=pdf, grade=grade, year=year, month=month,
                start_q=start_q or 18, end_q=end_q or 45,
                answers_dict=answers_dict, subtype=subtype
            )
            count = 0
            for q in (41, 42, 43, 44, 45):
                if q in crops and crops[q].get("pdf_crop_image"):
                    cur.execute(
                        "UPDATE passages SET pdf_crop_image=? WHERE exam_id=? AND q_num=?",
                        (crops[q]["pdf_crop_image"], eid, q)
                    )
                    count += 1
            conn.commit()
            updated_exams += 1
            total_crops_updated += count
            print(f"[OK] {eid} 갱신 완료 ({count}문항, {time.time()-t0:.2f}s)")
        except Exception as e:
            print(f"[ERR] {eid} 실패: {e}")

    conn.close()
    print(f"\n=== 작업 완료: 총 {updated_exams}개 시험지 / {total_crops_updated}개 문항 크롭 갱신 ===")

if __name__ == "__main__":
    main()
