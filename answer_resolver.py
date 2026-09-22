"""
05-gichul_db: 정답 소스 결합 및 검증 판정 (answer_resolver.py)

문항별 정답 결정 우선순위:
  1. csv              - 정답률 CSV: 정답 컬럼이 있으면 그 값, 없으면 |정답률 - 선지 선택률| <= 2.0%p 인 선지가 유일할 때 그 선지
                        (채점 통계에서 결정적으로 도출되므로 최우선. 단, 다른 시험의 CSV로 판단되면 전체 무시)
  2. verified_key     - data/answer_keys 검증 키 파일
  3. image_consensus  - 정답표 이미지를 2개 이상 Vision 모델이 독립 판독하여 과반 일치한 값
  4. image_single     - Vision 모델 1개만 응답한 이미지 판독값 (미검증)
  5. hwp              - HWP 해설 정규식 추출값 (미검증)
'검증됨'으로 인정하는 소스는 1~3 이며, 최종 정답이 CSV 정답률 후보와 어긋나면 미검증으로 강등하고 경고를 남긴다.
"""

from collections import Counter
from typing import Dict, Any, Iterable, List, Optional

CIRCLED_MAP = {"1": "①", "2": "②", "3": "③", "4": "④", "5": "⑤"}
CIRCLED_SET = set(CIRCLED_MAP.values())
VERIFIED_SOURCES = {"verified_key", "csv", "image_consensus", "manual"}
SOURCE_LABELS = {
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


def detect_csv_mismatch(csv_decided: Dict[int, str], reference: Dict[int, str]) -> Dict[str, Any]:
    """CSV 확정 정답을 신뢰 가능한 참조 정답과 비교하여 '다른 시험의 CSV' 여부 판정"""
    common = [q for q in csv_decided if q in reference]
    mismatch = [q for q in common if csv_decided[q] != reference[q]]
    suspect = len(common) >= CSV_SUSPECT_MIN_OVERLAP and len(mismatch) / len(common) > CSV_SUSPECT_RATIO
    return {"checked": len(common), "mismatch": sorted(mismatch), "suspect": suspect}


def resolve_answers(
    q_range: Iterable[int],
    verified_key: Optional[Dict[int, str]] = None,
    image_report: Optional[Dict[str, Any]] = None,
    csv_rates: Optional[Dict[int, Dict[str, Any]]] = None,
    hwp_answers: Optional[Dict[int, str]] = None,
) -> Dict[str, Any]:
    q_list = list(q_range)
    verified_key = {int(q): normalize_answer(a) for q, a in (verified_key or {}).items() if normalize_answer(a)}
    consensus: Dict[int, str] = {}
    single: Dict[int, str] = {}
    if image_report:
        consensus = {int(q): a for q, a in (image_report.get("consensus") or {}).items()}
        if image_report.get("status") == "single_reader":
            readings = image_report.get("readings", {}) or {}
            single = next(iter(readings.values()), {}) if readings else {}

    csv_decided, csv_candidates = csv_answer_tables(csv_rates)
    reference = {**consensus, **verified_key}
    csv_check = detect_csv_mismatch(csv_decided, reference)
    if csv_check["suspect"]:
        csv_decided, csv_candidates = {}, {}

    ordered_sources = (
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
    rate_violations = []
    for q in q_list:
        cands = csv_candidates.get(q)
        if cands and q in answers and answers[q] not in cands:
            rate_violations.append({"q": q, "answer": answers[q], "source": sources[q], "csv_candidates": cands})
            verified[q] = False

    unverified = [q for q in q_list if not verified[q]]
    csv_conflicts = [
        {"q": q, "image": consensus[q], "csv": csv_decided[q]}
        for q in q_list if q in consensus and q in csv_decided and consensus[q] != csv_decided[q]
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
    if csv_conflicts:
        warnings.append(
            "이미지 합의 정답과 CSV 정답 불일치 (CSV 우선 적용): "
            + ", ".join(f"Q{c['q']} 이미지 {c['image']} / CSV {c['csv']}" for c in csv_conflicts)
        )
    if rate_violations:
        warnings.append(
            "정답률과 모순되는 정답 (미검증 처리): "
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
            "warnings": warnings,
        },
    }


def check_csv_against_answers(
    csv_rates: Dict[int, Dict[str, Any]],
    current_answers: Dict[int, str],
) -> Dict[str, Any]:
    """
    기존 DB 정답에 대해 새 CSV를 교차검증한다 (CSV 단독 재업로드용).
    반환: suspect(다른 시험 CSV 여부), corrections {q: (old, new)}, confirmed [q], violations [q]
    """
    decided, candidates = csv_answer_tables(csv_rates)
    current = {int(q): normalize_answer(a) for q, a in current_answers.items() if normalize_answer(a)}
    check = detect_csv_mismatch(decided, current)
    corrections, confirmed = {}, []
    if not check["suspect"]:
        for q, ans in decided.items():
            if q not in current:
                continue
            if current[q] == ans:
                confirmed.append(q)
            else:
                corrections[q] = (current[q], ans)
    violations = [q for q, cands in candidates.items() if q in current and q not in decided and current[q] not in cands]
    return {
        "suspect": check["suspect"],
        "checked": check["checked"],
        "mismatch": check["mismatch"],
        "corrections": corrections,
        "confirmed": sorted(confirmed),
        "violations": sorted(violations),
    }
