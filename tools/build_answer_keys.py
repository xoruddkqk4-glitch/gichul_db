"""
검증된 정답 키 JSON(data/answer_keys/{학년}_{연도}_{월}.json)을 생성한다.

정답 결정 우선순위 (문항 단위):
  1. CSV 정답률: DB choice_rates 중 |선택률 - 정답률| <= 2.0%p 인 선지가 유일하면 그 선지 (결정적, 최우선)
  2. 정답표 이미지: _manual.json(확대 크롭 직접 재판독 확정값)이 최우선, 그 외는 두 독립 판독(_passA/_passB)이 일치한 값
     - CSV 후보가 2개 이상(근접 선택률)이면 이미지 값이 후보에 포함될 때만 채택
이미지가 CSV와 충돌한 문항은 image_conflicts 에 기록한다 (이미지 파일 오타 추적용).

사용: python tools/build_answer_keys.py                       (검증 보고만)
      python tools/build_answer_keys.py --write               (최종 JSON 기록)
      python tools/build_answer_keys.py --ignore-csv 고1_2021_03,고3_2022_06   (다른 시험의 CSV가 잘못 연결된 세트)
"""
import os
import sys
import json
import glob
import sqlite3
import argparse
from datetime import date

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KEYS_DIR = os.path.join(ROOT, "data", "answer_keys")
DB_PATH = os.path.join(ROOT, "gichul.db")
N2C = {"1": "①", "2": "②", "3": "③", "4": "④", "5": "⑤"}
RATE_TOLERANCE = 2.0


def load_pass(dirname):
    out = {}
    for path in glob.glob(os.path.join(KEYS_DIR, dirname, "*.json")):
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        out[data["exam_key"]] = data
    return out


def load_manual():
    path = os.path.join(KEYS_DIR, "_manual.json")
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return {k: v for k, v in data.items() if not k.startswith("_")}


def csv_candidates(conn, grade, year, month):
    """{문항: [CSV 정답 후보 선지들]} (정답률 데이터가 있는 문항만)"""
    exam_id = f"[{grade}-{year}년-{month:02d}월]"
    out = {}
    for q, cr, rates in conn.execute(
        "SELECT q_num, correct_rate, choice_rates FROM passages WHERE exam_id=?", (exam_id,)
    ):
        if cr is None or not rates:
            continue
        r = json.loads(rates)
        cands = [N2C[k] for k in "12345" if r.get(k) is not None and abs(r[k] - cr) <= RATE_TOLERANCE]
        if cands:
            out[int(q)] = cands
    return out


def db_answers(conn, grade, year, month):
    exam_id = f"[{grade}-{year}년-{month:02d}월]"
    return {int(q): a or "" for q, a in conn.execute(
        "SELECT q_num, answer_text FROM passages WHERE exam_id=?", (exam_id,))}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--ignore-csv", default="")
    args = ap.parse_args()
    ignore_csv = {k for k in args.ignore_csv.split(",") if k}

    pass_a, pass_b, manual = load_pass("_passA"), load_pass("_passB"), load_manual()
    conn = sqlite3.connect(DB_PATH)
    keys = sorted(set(pass_a) | set(pass_b))

    written, unresolved_sets, total_db_fix, total_conflicts = [], [], 0, []

    for key in keys:
        a, b = pass_a.get(key), pass_b.get(key)
        if not a or not b:
            unresolved_sets.append((key, "판독 파일 누락"))
            print(f"[MISSING] {key}")
            continue
        grade, year, month = key.split("_")
        year, month = int(year), int(month)
        man = {int(q): v for q, v in manual.get(key, {}).items()}
        cands = {} if key in ignore_csv else csv_candidates(conn, grade, year, month)
        db_ans = db_answers(conn, grade, year, month)

        answers, sources, conflicts, unresolved = {}, {"csv": [], "image": []}, [], []
        for q in range(1, 46):
            va, vb = a["answers"].get(str(q), "?"), b["answers"].get(str(q), "?")
            if q in man:
                img = man[q]
            elif va == vb and va in N2C.values():
                img = va
            else:
                img = None

            c = cands.get(q, [])
            if len(c) == 1:
                answers[q] = c[0]
                sources["csv"].append(q)
                if img and img != c[0]:
                    conflicts.append({"q": q, "image": img, "csv": c[0]})
            elif img and (not c or img in c):
                answers[q] = img
                sources["image"].append(q)
            else:
                unresolved.append((q, va, vb, c))

        if unresolved:
            unresolved_sets.append((key, unresolved))
            print(f"[UNRESOLVED] {key}: " + ", ".join(f"Q{q} A={va} B={vb} csv={c}" for q, va, vb, c in unresolved))
            continue

        db_fix = [(q, db_ans[q], answers[q]) for q in sorted(db_ans) if db_ans[q] and db_ans[q] != answers[q]]
        total_db_fix += len(db_fix)
        if conflicts:
            total_conflicts.append((key, conflicts))

        warnings = []
        if key in ignore_csv:
            warnings.append("CSV 파일이 다른 시험의 데이터로 판단되어 무시함 (정답률 데이터 교체 필요)")
        if not sources["csv"]:
            warnings.append("CSV 정답률 검증 없음 - 이미지 판독(이중 전사 + 다중 Vision 모델 감사) 근거")

        csv_n = len(sources["csv"])
        print(f"[OK] {key}: csv={csv_n:>2}문항 image={len(sources['image']):>2}문항 "
              f"db_fix={len(db_fix):>2} conflicts={len(conflicts)}"
              + (f"  -> {db_fix}" if db_fix else "")
              + (f"  !! 이미지≠CSV {[(c['q'], c['image'], c['csv']) for c in conflicts]}" if conflicts else ""))

        if args.write:
            final = {
                "exam_key": key, "grade": grade, "year": year, "month": month,
                "source_file": a.get("source_file", ""),
                "verification": {
                    "method": "csv_rate_match > manual_reread(3x crop) > dual_independent_image_transcription; audited by multi-model vision consensus (tools/audit_keys_with_vision.py)",
                    "csv_decided": sources["csv"],
                    "image_decided": sources["image"],
                    "image_conflicts": conflicts,
                    "warnings": warnings,
                    "verified_at": date.today().isoformat(),
                },
                "answers": {str(q): answers[q] for q in range(1, 46)},
            }
            with open(os.path.join(KEYS_DIR, key + ".json"), "w", encoding="utf-8") as f:
                json.dump(final, f, ensure_ascii=False, indent=2)
            written.append(key)

    print("\n=== 요약 ===")
    print(f"총 {len(keys)}세트 | 확정 {len(keys) - len(unresolved_sets)} | 미확정 {len(unresolved_sets)}")
    print(f"이미지≠CSV 충돌 세트 {len(total_conflicts)} (문항 {sum(len(c) for _, c in total_conflicts)}) | DB 정정 필요 문항 {total_db_fix}")
    if args.write:
        print(f"최종 키 파일 기록 {len(written)}개 -> {KEYS_DIR}")
    return 1 if unresolved_sets else 0


if __name__ == "__main__":
    sys.exit(main())
