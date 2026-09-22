"""
CSV 검증이 없는(이미지 단독 근거) 정답 키 파일을 다중 Vision 모델 합의 판독으로 재감사한다.
- 대상: data/answer_keys/*.json 중 verification.csv_decided 가 비어 있는 세트
- 각 정답표 이미지를 read_answer_image()로 판독하고 키 파일 정답과 대조
- 결과는 scratch/vision_audit.json 에 저장하며 키 파일이나 DB는 수정하지 않는다
사용: python tools/audit_keys_with_vision.py [--workers 4] [--only 고3_2024_11]
"""
import os
import sys
import json
import glob
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from answer_keys import KEYS_DIR  # noqa: E402
from hwp_parser import read_answer_image  # noqa: E402

OUT_PATH = os.path.join(ROOT, "scratch", "vision_audit.json")


def audit_one(key):
    img = os.path.join(ROOT, "uploads", key["source_file"])
    report = read_answer_image(img)
    answers = {int(q): a for q, a in key["answers"].items()}
    consensus = report.get("consensus", {})
    mismatches = [
        {"q": q, "key": answers[q], "vision": consensus[q]}
        for q in sorted(consensus) if q in answers and consensus[q] != answers[q]
    ]
    return {
        "exam_key": key["exam_key"],
        "status": report["status"],
        "reader_count": report["reader_count"],
        "consensus_count": len(consensus),
        "disputed": {str(q): v for q, v in report.get("disputed", {}).items()},
        "errors": report.get("errors", []),
        "mismatches": mismatches,
        "reading_mismatches": [m for m in mismatches if m["q"] >= 18],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--only", default="")
    args = ap.parse_args()

    targets = []
    for path in sorted(glob.glob(os.path.join(KEYS_DIR, "*.json"))):
        if os.path.basename(path).startswith("_"):
            continue
        with open(path, encoding="utf-8") as f:
            key = json.load(f)
        if key["verification"].get("csv_decided"):
            continue
        if args.only and key["exam_key"] != args.only:
            continue
        targets.append(key)
    print(f"감사 대상(이미지 단독 근거) {len(targets)}세트, workers={args.workers}")

    results = []
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futures = {ex.submit(audit_one, k): k["exam_key"] for k in targets}
        for fut in as_completed(futures):
            name = futures[fut]
            try:
                r = fut.result()
            except Exception as e:
                r = {"exam_key": name, "status": "error", "errors": [str(e)], "mismatches": [], "reading_mismatches": [], "disputed": {}}
            results.append(r)
            flag = "" if not r["reading_mismatches"] else f"  !! 독해 불일치 {[(m['q'], m['key'], m['vision']) for m in r['reading_mismatches']]}"
            print(f"[{r['status']:<13}] {r['exam_key']}: readers={r.get('reader_count', 0)} consensus={r.get('consensus_count', 0)} disputed={sorted(int(q) for q in r['disputed'])}{flag}")

    results.sort(key=lambda r: r["exam_key"])
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    ok = [r for r in results if r["status"] in ("ok", "partial")]
    bad = [r for r in results if r["reading_mismatches"]]
    print("\n=== 요약 ===")
    print(f"판독 성공 {len(ok)}/{len(results)} | 독해(18~45) 불일치 세트 {len(bad)} | 결과: {OUT_PATH}")
    for r in bad:
        print(f"  {r['exam_key']}: {[(m['q'], m['key'], m['vision']) for m in r['reading_mismatches']]}")
    for r in results:
        if r["status"] not in ("ok", "partial"):
            print(f"  [{r['status']}] {r['exam_key']}: {r['errors']}")


if __name__ == "__main__":
    main()
