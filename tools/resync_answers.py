"""
검증된 정답 키(data/answer_keys/*.json)로 DB 정답, 해설 [정답] 헤더, PDF 정답 형광펜 크롭 이미지를 재동기화한다.
사용: python tools/resync_answers.py --dry-run          (변경 예정 내역만 출력)
      python tools/resync_answers.py                    (DB 갱신 + 변경 세트 크롭 재생성)
      python tools/resync_answers.py --no-crops         (DB만 갱신)
      python tools/resync_answers.py --only 고3_2024_11 (특정 세트만)
"""
import os
import re
import sys
import glob
import json
import argparse

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import database as db  # noqa: E402
import pdf_parser  # noqa: E402
from answer_keys import KEYS_DIR  # noqa: E402

HEADER_RE = re.compile(r"^\s*\[\s*정답\s*\]\s*[①②③④⑤1-5]?")


def with_header(exp: str, ans: str) -> str:
    exp = (exp or "").strip()
    if HEADER_RE.search(exp):
        return HEADER_RE.sub(f"[정답] {ans}", exp, count=1)
    return f"[정답] {ans}\n\n{exp}".strip()


def find_pdf(grade, year, month):
    for pat in (f"{grade}_{year}_{month:02d}_*.pdf", f"{grade}_{year}_{month}_*.pdf"):
        hits = [p for p in glob.glob(os.path.join(ROOT, "uploads", pat)) if "_ans_" not in os.path.basename(p)]
        if hits:
            return hits[0]
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--no-crops", action="store_true")
    ap.add_argument("--only", default="")
    args = ap.parse_args()

    files = sorted(f for f in glob.glob(os.path.join(KEYS_DIR, "*.json")) if not os.path.basename(f).startswith("_"))
    if args.only:
        files = [f for f in files if os.path.basename(f) == args.only + ".json"]

    conn = db.get_connection()
    cur = conn.cursor()
    total_changed, total_crops, exams_changed = 0, 0, []

    for path in files:
        with open(path, encoding="utf-8") as f:
            key = json.load(f)
        grade, year, month = key["grade"], int(key["year"]), int(key["month"])
        answers = {int(q): a for q, a in key["answers"].items()}
        exam_id = f"[{grade}-{year}년-{month:02d}월]"

        exam = cur.execute("SELECT reading_start_q, reading_end_q FROM exams WHERE id=?", (exam_id,)).fetchone()
        rows = cur.execute(
            "SELECT id, q_num, answer_text, explanation_text FROM passages WHERE exam_id=? ORDER BY q_num", (exam_id,)
        ).fetchall()
        if not exam or not rows:
            print(f"[SKIP] {exam_id}: DB에 없음")
            continue

        changed = []
        for r in rows:
            q = int(r["q_num"])
            true = answers.get(q)
            if not true:
                continue
            new_exp = with_header(r["explanation_text"], true)
            if r["answer_text"] != true:
                changed.append((q, r["answer_text"] or "?", true))
            if not args.dry_run:
                cur.execute(
                    "UPDATE passages SET answer_text=?, explanation_text=?, answer_source='verified_key', answer_verified=1 WHERE id=?",
                    (true, new_exp, r["id"]))
        if not args.dry_run:
            conn.commit()

        total_changed += len(changed)
        tag = "DRY" if args.dry_run else "OK"
        print(f"[{tag}] {exam_id}: 정답 정정 {len(changed):>2}건" + (f"  {changed}" if changed else ""))

        if changed and not args.no_crops and not args.dry_run:
            exams_changed.append(exam_id)
            pdf = find_pdf(grade, year, month)
            if not pdf:
                print("       PDF 없음 - 크롭 재생성 생략")
                continue
            crops = pdf_parser.extract_pdf_columns_and_questions(
                pdf_path=pdf, grade=grade, year=year, month=month,
                start_q=exam["reading_start_q"] or 18, end_q=exam["reading_end_q"] or 45,
                answers_dict=answers,
            )
            for q, info in crops.items():
                if info.get("pdf_crop_image"):
                    cur.execute("UPDATE passages SET pdf_crop_image=? WHERE exam_id=? AND q_num=?",
                                (info["pdf_crop_image"], exam_id, q))
            conn.commit()
            total_crops += len(crops)
            print(f"       형광펜 크롭 재생성 {len(crops)}개")

    conn.close()
    print(f"\n=== 완료: 정답 정정 {total_changed}문항 / 크롭 재생성 {total_crops}개 / 세트 {len(exams_changed)} ===")


if __name__ == "__main__":
    main()
