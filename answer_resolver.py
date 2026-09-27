"""
05-gichul_db: 정답 소스 결합 및 검증 판정 (answer_resolver.py)

문항별 정답 결정 우선순위:
  1. uploaded_json    - 사용자가 직접 업로드한 정답 JSON 파일 (100% 확정 Ground Truth, 최우선)
  2. csv              - 정답률 CSV: 정답 컬럼이 있으면 그 값, 없으면 |정답률 - 선지 선택률| <= 2.0%p 인 선지가 유일할 때 그 선지
                        (채점 통계에서 결정적으로 도출되므로 최우선. 단, 다른 시험의 CSV로 판단되면 전체 무시)
  3. verified_key     - data/answer_keys 검증 키 파일
  4. image_consensus  - 정답표 이미지를 2개 이상 Vision 모델이 독립 판독하여 과반 일치한 값
  5. image_single     - Vision 모델 1개만 응답한 이미지 판독값 (미검증)
  6. hwp              - HWP 해설 정규식 추출값 (미검증)
'검증됨'으로 인정하는 소스는 1~4 이며, 최종 정답이 CSV 정답률 후보와 어긋나면 미검증으로 강등하고 경고를 남긴다.
(직접 업로드한 JSON 정답은 최우선 Ground Truth로 채택되며, CSV와 불일치 시 검토용 경고를 기록한다)
"""

from collections import Counter
from typing import Dict, Any, Iterable, List, Optional

CIRCLED_MAP = {"1": "①", "2": "②", "3": "③", "4": "④", "5": "⑤"}
CIRCLED_SET = set(CIRCLED_MAP.values())
CIRCLE_TO_NUM = {v: k for k, v in CIRCLED_MAP.items()}
VERIFIED_SOURCES = {"uploaded_json", "verified_key", "csv", "image_consensus", "manual"}
SOURCE_LABELS = {
    "uploaded_json": "정답 JSON 파일",
    "verified_key": "검증 키 파일",
    "csv": "정답률 CSV",
    "image_consensus": "정답표 이미지(모델 합의)",
    "image_single": "정답표 이미지(단일 모델)",
    "hwp": "HWP 해설",
    "manual": "수동 확정",
    "none": "없음",
}
RATE_TOLERANCE = 2.0          # 정답률 vs 정답 선지 선택률 허용 오차 (%p)
CSV_SUSPECT_MIN_OVERLAP = 8   # 이 개수 이상 비교 가능할 때만 '다른 시험 CSV' 판정
CSV_SUSPECT_RATIO = 0.3       # 비교 문항의 30% 초과 불일치 시 다른 시험의 CSV로 간주


def normalize_answer(value: Any) -> str:
    text = str(value or "").strip()
    text = CIRCLED_MAP.get(text, text)
    return text if text in CIRCLED_SET else ""


def csv_rate_candidates(item: Dict[str, Any], tolerance: float = RATE_TOLERANCE) -> List[str]:
    """정답률과 선택률이 허용 오차 내에서 일치하는 선지 후보 목록 (정답률/선택률 없으면 빈 리스트)"""
    rate = item.get("correct_rate")
    rates = item.get("choice_rates") or {}
    if rate is None or not rates:
        return []
    cands = []
    for num, circ in CIRCLED_MAP.items():
        r = rates.get(num)
        if r is not None and abs(float(r) - float(rate)) <= tolerance:
            cands.append(circ)
    return cands


def recalculate_attractive_wrong(item: Dict[str, Any], correct_circle: str):
    """올바른 정답 기준으로 매력적 오답(attractive_wrong) 재계산"""
    correct_num = CIRCLE_TO_NUM.get(correct_circle)
    ch_rates = item.get("choice_rates")
    if not isinstance(ch_rates, dict):
        return
    wrong_choices = []
    for num in ["1", "2", "3", "4", "5"]:
        if num != correct_num:
            r = ch_rates.get(num)
            if r is not None:
                try:
                    wrong_choices.append((num, float(r)))
                except (ValueError, TypeError):
                    pass
    if wrong_choices:
        wrong_choices.sort(key=lambda x: x[1], reverse=True)
        top_num, top_rate = wrong_choices[0]
        if top_rate >= 15.0:
            ch_rates["attractive_wrong"] = {
                "choice": top_num,
                "choice_circle": CIRCLED_MAP.get(top_num, top_num),
                "rate": top_rate
            }
        else:
            ch_rates["attractive_wrong"] = None


def csv_answer_tables(csv_rates: Optional[Dict[int, Dict[str, Any]]]):
    """(확정 정답 {q: ans}, 정답률 후보 {q: [ans...]}) - 확정 = 정답 컬럼 값 또는 유일한 정답률 후보"""
    decided: Dict[int, str] = {}
    candidates: Dict[int, List[str]] = {}
    for q, item in (csv_rates or {}).items():
        q = int(q)
        cands = csv_rate_candidates(item)
        if cands:
            candidates[q] = cands
        explicit = normalize_answer(item.get("correct_ans_circle") or item.get("correct_ans"))
        if explicit:
            decided[q] = explicit
        elif len(cands) == 1:
            decided[q] = cands[0]
    return decided, candidates


def detect_csv_mismatch(
    csv_decided: Dict[int, str],
    reference: Dict[int, str],
    candidates: Optional[Dict[int, List[str]]] = None
) -> Dict[str, Any]:
    """
    CSV 확정 정답을 신뢰 가능한 참조 정답(정답 JSON 최우선)과 비교하여 '다른 시험의 CSV' 여부 판정.
    스마트 보정:
      - CSV의 텍스트 '정답' 컬럼이 reference와 다르더라도,
        reference 정답이 CSV의 실제 정답률 후보(candidates)에 속해 있다면
        이는 CSV 텍스트 컬럼의 오기재일 뿐 해당 시험의 통계 데이터가 맞으므로 불일치(mismatch)로 간주하지 않는다.
    """
    candidates = candidates or {}
    common = [q for q in reference if q in csv_decided or q in candidates]
    mismatch = []
    for q in common:
        ref_ans = reference[q]
        dec_ans = csv_decided.get(q)
        cands = candidates.get(q, [])
        if dec_ans == ref_ans:
            continue
        if ref_ans in cands:
            continue
        mismatch.append(q)

    suspect = len(common) >= CSV_SUSPECT_MIN_OVERLAP and len(mismatch) / len(common) > CSV_SUSPECT_RATIO
    return {"checked": len(common), "mismatch": sorted(mismatch), "suspect": suspect}


def resolve_answers(
    q_range: Iterable[int],
    verified_key: Optional[Dict[int, str]] = None,
    image_report: Optional[Dict[str, Any]] = None,
    csv_rates: Optional[Dict[int, Dict[str, Any]]] = None,
    hwp_answers: Optional[Dict[int, str]] = None,
    uploaded_json: Optional[Dict[int, str]] = None,
) -> Dict[str, Any]:
    q_list = list(q_range)
    uploaded_json_clean = {int(q): normalize_answer(a) for q, a in (uploaded_json or {}).items() if normalize_answer(a)}
    verified_key = {int(q): normalize_answer(a) for q, a in (verified_key or {}).items() if normalize_answer(a)}
    consensus: Dict[int, str] = {}
    single: Dict[int, str] = {}
    if image_report:
        consensus = {int(q): a for q, a in (image_report.get("consensus") or {}).items()}
        if image_report.get("status") == "single_reader":
            readings = image_report.get("readings", {}) or {}
            single = next(iter(readings.values()), {}) if readings else {}

    csv_decided, csv_candidates = csv_answer_tables(csv_rates)
    reference = {**consensus, **verified_key, **uploaded_json_clean}
    csv_check = detect_csv_mismatch(csv_decided, reference, csv_candidates)
    if csv_check["suspect"]:
        csv_decided, csv_candidates = {}, {}
    else:
        # 스마트 보정: reference(정답 JSON 등) 정답이 csv_candidates에 속하면 csv_decided를 reference 정답으로 동기화
        for q, ref_ans in reference.items():
            if q in csv_candidates and ref_ans in csv_candidates[q]:
                csv_decided[q] = ref_ans

    ordered_sources = (
        ("uploaded_json", uploaded_json_clean),
        ("csv", csv_decided),
        ("verified_key", verified_key),
        ("image_consensus", consensus),
        ("image_single", single),
        ("hwp", hwp_answers or {}),
    )

    answers: Dict[int, str] = {}
    sources: Dict[int, str] = {}
    for q in q_list:
        sources[q] = "none"
        for name, table in ordered_sources:
            ans = normalize_answer(table.get(q))
            if ans:
                answers[q] = ans
                sources[q] = name
                break

    verified = {q: sources[q] in VERIFIED_SOURCES for q in q_list}

    # 최종 정답이 CSV 정답률 후보(복수 포함)에 속하지 않으면 검증 강등
    # 직접 업로드한 JSON 및 수동 확정은 정답표 자체를 입력한 것이므로 강등하지 않음
    rate_violations = []
    for q in q_list:
        cands = csv_candidates.get(q)
        if cands and q in answers and answers[q] not in cands:
            rate_violations.append({"q": q, "answer": answers[q], "source": sources[q], "csv_candidates": cands})
            if sources[q] not in ("uploaded_json", "manual"):
                verified[q] = False

    unverified = [q for q in q_list if not verified[q]]
    csv_conflicts = [
        {"q": q, "image": consensus[q], "csv": csv_decided[q]}
        for q in q_list if q in consensus and q in csv_decided and consensus[q] != csv_decided[q]
    ]
    json_csv_conflicts = [
        {"q": q, "json": uploaded_json_clean[q], "csv": csv_decided[q]}
        for q in q_list if q in uploaded_json_clean and q in csv_decided and uploaded_json_clean[q] != csv_decided[q]
    ]

    warnings = []
    image_status = image_report.get("status") if image_report else None
    if image_report:
        if image_status == "failed":
            warnings.append("정답표 이미지 판독 실패: " + "; ".join(image_report.get("errors") or ["원인 미상"]))
        elif image_status == "single_reader":
            warnings.append("Vision 모델 1개만 응답하여 이미지 정답을 교차검증하지 못했습니다 (미검증 처리)")
        disputed = image_report.get("disputed") or {}
        if disputed:
            warnings.append(f"모델 간 판독 불일치 문항(이미지 값 미채택): {sorted(int(q) for q in disputed)}")
    if csv_check["suspect"]:
        warnings.append(
            f"정답률 CSV가 다른 시험의 데이터로 의심됩니다 (비교 {csv_check['checked']}문항 중 "
            f"{len(csv_check['mismatch'])}문항 불일치) - CSV 정답을 무시했습니다. 파일을 확인하세요."
        )
    if json_csv_conflicts:
        warnings.append(
            "정답 JSON과 CSV 정답 불일치 (JSON 우선 적용): "
            + ", ".join(f"Q{c['q']} JSON {c['json']} / CSV {c['csv']}" for c in json_csv_conflicts)
        )
    if csv_conflicts:
        warnings.append(
            "이미지 합의 정답과 CSV 정답 불일치 (CSV 우선 적용): "
            + ", ".join(f"Q{c['q']} 이미지 {c['image']} / CSV {c['csv']}" for c in csv_conflicts)
        )
    if rate_violations:
        warnings.append(
            "정답률과 모순되는 정답" + (" (미검증 처리)" if any(v["source"] not in ("uploaded_json", "manual") for v in rate_violations) else " (확인 필요)") + ": "
            + ", ".join(f"Q{v['q']} {v['answer']}({SOURCE_LABELS[v['source']]}) vs 정답률 후보 {'/'.join(v['csv_candidates'])}" for v in rate_violations)
        )
    if unverified:
        warnings.append(f"미검증 정답 {len(unverified)}문항: {unverified}")

    return {
        "answers": answers,
        "sources": sources,
        "verified": verified,
        "report": {
            "source_counts": dict(Counter(sources.values())),
            "unverified_questions": unverified,
            "image_status": image_status,
            "image_reader_count": image_report.get("reader_count", 0) if image_report else 0,
            "image_disputed": {str(q): v for q, v in (image_report.get("disputed") or {}).items()} if image_report else {},
            "image_errors": image_report.get("errors", []) if image_report else [],
            "csv_suspect": csv_check["suspect"],
            "csv_checked": csv_check["checked"],
            "csv_rate_violations": rate_violations,
            "csv_conflicts": csv_conflicts,
            "json_csv_conflicts": json_csv_conflicts,
            "warnings": warnings,
        },
    }


def check_csv_against_answers(
    csv_rates: Dict[int, Dict[str, Any]],
    current_answers: Dict[int, str],
    current_sources: Optional[Dict[int, str]] = None,
) -> Dict[str, Any]:
    """
    기존 DB 정답(정답 JSON 최우선)에 대해 새 CSV를 교차검증한다 (CSV 단독 재업로드용).
    반환: suspect(다른 시험 CSV 여부), corrections {q: (old, new)}, confirmed [q], violations [q]
    스마트 보정:
      - DB 정답(특히 정답 JSON)이 CSV의 candidates(정답률 후보)와 일치하면 CSV의 correct_ans를
        DB 정답으로 스마트 자동 보정하고 confirmed로 인정한다.
    """
    decided, candidates = csv_answer_tables(csv_rates)
    current = {int(q): normalize_answer(a) for q, a in current_answers.items() if normalize_answer(a)}
    sources = current_sources or {}

    check = detect_csv_mismatch(decided, current, candidates)
    corrections, confirmed, smart_corrected = {}, [], []

    if not check["suspect"]:
        for q, ref_ans in current.items():
            item = csv_rates.get(q) or csv_rates.get(str(q))
            if not item:
                continue
            cands = candidates.get(q, [])
            dec_ans = decided.get(q)

            # Case A: DB 정답(정답 JSON 등)이 CSV의 정답률 후보(cands)에 속하는 경우 -> 스마트 일치!
            if ref_ans in cands:
                confirmed.append(q)
                if dec_ans != ref_ans:
                    item["correct_ans"] = CIRCLE_TO_NUM.get(ref_ans, ref_ans)
                    item["correct_ans_circle"] = ref_ans
                    recalculate_attractive_wrong(item, ref_ans)
                    smart_corrected.append(q)
            # Case B: candidates가 비어있고(단순 정답률) 텍스트 정답만 있는 경우
            elif not cands and dec_ans == ref_ans:
                confirmed.append(q)
            # Case C: 기존 DB 정답이 미검증(HWP 등)이고, CSV 정답률이 명백히 다른 정답을 가리키는 경우
            elif dec_ans and dec_ans != ref_ans and sources.get(q) != "uploaded_json":
                # 정답 JSON 출처는 절대 덮어쓰지 않음
                corrections[q] = (ref_ans, dec_ans)

    violations = [q for q, cands in candidates.items() if q in current and current[q] not in cands]
    return {
        "suspect": check["suspect"],
        "checked": check["checked"],
        "mismatch": check["mismatch"],
        "corrections": corrections,
        "confirmed": sorted(confirmed),
        "smart_corrected": sorted(smart_corrected),
        "violations": sorted(violations),
    }
