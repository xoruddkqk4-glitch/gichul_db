"""answer_resolver.py 회귀 테스트 — 정답 정규화, CSV 후보 산출, 소스 우선순위, 검증 강등, 다른 시험 CSV 판정"""
import pytest

import answer_resolver as ar


def _csv_item(ans="", rate=None, rates=None):
    """rate_parser 출력 형태의 문항 dict 생성 헬퍼"""
    item = {"correct_ans": ans, "correct_ans_circle": ar.CIRCLED_MAP.get(ans, ""), "correct_rate": rate}
    item["choice_rates"] = dict(rates) if rates else {}
    return item


def _image(status, consensus=None, readings=None, disputed=None, errors=None):
    readings = readings if readings is not None else {"A": {}, "B": {}}
    return {
        "status": status,
        "consensus": consensus or {},
        "readings": readings,
        "disputed": disputed or {},
        "errors": errors or [],
        "reader_count": len(readings),
    }


# ---------- normalize_answer ----------

@pytest.mark.parametrize("raw,expected", [
    ("3", "③"), ("③", "③"), (" 2 ", "②"), (5, "⑤"),
    ("6", ""), ("0", ""), ("", ""), (None, ""), ("정답", ""), ("③④", ""),
])
def test_normalize_answer(raw, expected):
    assert ar.normalize_answer(raw) == expected


# ---------- csv_rate_candidates / csv_answer_tables ----------

def test_rate_candidates_within_tolerance_inclusive():
    item = _csv_item(rate=50.0, rates={"1": 10.0, "2": 52.0, "3": 48.0, "4": 47.9, "5": 30.0})
    assert ar.csv_rate_candidates(item) == ["②", "③"]   # ±2.0 포함, 47.9는 제외


def test_rate_candidates_empty_when_rate_or_rates_missing():
    assert ar.csv_rate_candidates(_csv_item(rate=None, rates={"1": 50.0})) == []
    assert ar.csv_rate_candidates(_csv_item(rate=50.0, rates=None)) == []


def test_answer_tables_explicit_answer_wins_over_candidates():
    csv = {18: _csv_item(ans="4", rate=50.0, rates={"1": 50.0, "2": 0, "3": 0, "4": 20.0, "5": 30.0})}
    decided, cands = ar.csv_answer_tables(csv)
    assert decided == {18: "④"}
    assert cands == {18: ["①"]}


def test_answer_tables_unique_candidate_decides_and_multiple_do_not():
    csv = {
        18: _csv_item(rate=70.0, rates={"1": 70.2, "2": 10, "3": 10, "4": 5, "5": 4.8}),
        19: _csv_item(rate=40.0, rates={"1": 40.0, "2": 41.0, "3": 10, "4": 5, "5": 4}),
    }
    decided, cands = ar.csv_answer_tables(csv)
    assert decided == {18: "①"}
    assert cands == {18: ["①"], 19: ["①", "②"]}


def test_answer_tables_string_keys_converted_to_int():
    decided, _ = ar.csv_answer_tables({"20": _csv_item(ans="2")})
    assert decided == {20: "②"}


# ---------- detect_csv_mismatch ----------

def test_mismatch_below_min_overlap_never_suspect():
    csv = {q: "①" for q in range(18, 25)}          # 7문항
    ref = {q: "②" for q in range(18, 25)}          # 전부 불일치
    check = ar.detect_csv_mismatch(csv, ref)
    assert check["checked"] == 7 and check["mismatch"] == list(range(18, 25))
    assert check["suspect"] is False


def test_mismatch_ratio_boundary():
    ref = {q: "①" for q in range(1, 11)}                            # 10문항 비교
    csv_30 = {q: ("②" if q <= 3 else "①") for q in range(1, 11)}   # 30% 불일치 → 미의심
    csv_40 = {q: ("②" if q <= 4 else "①") for q in range(1, 11)}   # 40% 불일치 → 의심
    assert ar.detect_csv_mismatch(csv_30, ref)["suspect"] is False
    assert ar.detect_csv_mismatch(csv_40, ref)["suspect"] is True


# ---------- resolve_answers: 우선순위 및 검증 플래그 ----------

def test_source_priority_csv_key_consensus_single_hwp():
    csv = {18: _csv_item(ans="1")}
    key = {18: "②", 19: "②"}
    image = _image("ok", consensus={18: "③", 19: "③", 20: "③"})
    hwp = {18: "⑤", 19: "⑤", 20: "⑤", 21: "⑤"}
    res = ar.resolve_answers(range(18, 24), verified_key=key, image_report=image, csv_rates=csv, hwp_answers=hwp)
    assert res["answers"] == {18: "①", 19: "②", 20: "③", 21: "⑤"}
    assert res["sources"] == {18: "csv", 19: "verified_key", 20: "image_consensus", 21: "hwp", 22: "none", 23: "none"}
    assert res["verified"] == {18: True, 19: True, 20: True, 21: False, 22: False, 23: False}
    assert res["report"]["unverified_questions"] == [21, 22, 23]
    assert res["report"]["source_counts"] == {"csv": 1, "verified_key": 1, "image_consensus": 1, "hwp": 1, "none": 2}


def test_single_reader_image_is_used_but_unverified():
    image = _image("single_reader", readings={"Gemini": {18: "④", 19: "②"}})
    res = ar.resolve_answers(range(18, 20), image_report=image)
    assert res["answers"] == {18: "④", 19: "②"}
    assert res["sources"] == {18: "image_single", 19: "image_single"}
    assert res["verified"] == {18: False, 19: False}
    assert res["report"]["image_reader_count"] == 1
    assert any("Vision 모델 1개만" in w for w in res["report"]["warnings"])


def test_failed_image_report_yields_warning_and_no_answers():
    image = _image("failed", readings={}, errors=["402 크레딧 부족"])
    res = ar.resolve_answers(range(18, 20), image_report=image)
    assert res["answers"] == {}
    assert res["sources"] == {18: "none", 19: "none"}
    assert any("정답표 이미지 판독 실패" in w and "402 크레딧 부족" in w for w in res["report"]["warnings"])
    assert res["report"]["image_errors"] == ["402 크레딧 부족"]


def test_disputed_questions_reported_and_not_adopted():
    image = _image("partial", consensus={18: "①"}, disputed={19: {"A": "②", "B": "③"}})
    res = ar.resolve_answers(range(18, 20), image_report=image, hwp_answers={19: "②"})
    assert res["sources"] == {18: "image_consensus", 19: "hwp"}
    assert res["report"]["image_disputed"] == {"19": {"A": "②", "B": "③"}}
    assert any("판독 불일치 문항" in w and "[19]" in w for w in res["report"]["warnings"])


def test_no_sources_at_all():
    res = ar.resolve_answers(range(18, 21))
    assert res["answers"] == {}
    assert res["report"]["unverified_questions"] == [18, 19, 20]
    assert res["report"]["image_status"] is None
    assert res["report"]["image_reader_count"] == 0


# ---------- resolve_answers: CSV 교차 검사 ----------

def test_suspect_csv_is_ignored_entirely():
    key = {q: "①" for q in range(18, 28)}                                          # 10문항 참조
    csv = {q: _csv_item(ans=("2" if q < 23 else "1")) for q in range(18, 28)}    # 5/10 불일치 → 의심
    res = ar.resolve_answers(range(18, 28), verified_key=key, csv_rates=csv)
    assert all(s == "verified_key" for s in res["sources"].values())
    assert res["report"]["csv_suspect"] is True
    assert res["report"]["csv_checked"] == 10
    assert any("다른 시험의 데이터로 의심" in w for w in res["report"]["warnings"])


def test_csv_conflict_with_image_consensus_csv_wins():
    image = _image("ok", consensus={18: "③"})
    res = ar.resolve_answers(range(18, 19), image_report=image, csv_rates={18: _csv_item(ans="4")})
    assert res["answers"] == {18: "④"}
    assert res["sources"][18] == "csv"
    assert res["report"]["csv_conflicts"] == [{"q": 18, "image": "③", "csv": "④"}]
    assert any("CSV 우선 적용" in w for w in res["report"]["warnings"])


def test_rate_violation_demotes_verified_answer():
    # CSV에 정답 컬럼은 없고 정답률 후보가 ②/④ 둘인데, 검증 키는 ⑤ → 정답률과 모순 → 미검증 강등
    csv = {18: _csv_item(rate=40.0, rates={"1": 5, "2": 40.0, "3": 10, "4": 41.0, "5": 4})}
    res = ar.resolve_answers(range(18, 19), verified_key={18: "⑤"}, csv_rates=csv)
    assert res["answers"] == {18: "⑤"}
    assert res["sources"][18] == "verified_key"
    assert res["verified"][18] is False
    assert res["report"]["csv_rate_violations"] == [
        {"q": 18, "answer": "⑤", "source": "verified_key", "csv_candidates": ["②", "④"]}
    ]
    assert any("정답률과 모순" in w for w in res["report"]["warnings"])


def test_rate_consistent_key_answer_stays_verified():
    csv = {18: _csv_item(rate=40.0, rates={"1": 5, "2": 40.0, "3": 10, "4": 41.0, "5": 4})}
    res = ar.resolve_answers(range(18, 19), verified_key={18: "②"}, csv_rates=csv)
    assert res["verified"][18] is True
    assert res["report"]["csv_rate_violations"] == []


# ---------- check_csv_against_answers (CSV 단독 재업로드) ----------

def test_check_csv_corrections_confirmed_violations():
    current = {18: "①", 19: "②", 20: "③", 21: "④"}
    csv = {
        18: _csv_item(ans="1"),                                                          # 일치 → confirmed
        19: _csv_item(ans="3"),                                                          # 불일치 → correction
        20: _csv_item(rate=50.0, rates={"1": 50.0, "2": 49.0, "3": 1, "4": 0, "5": 0}),  # 후보 ①/② 인데 현재 ③ → violation
        22: _csv_item(ans="5"),                                                          # DB에 없는 문항 → 무시
    }
    check = ar.check_csv_against_answers(csv, current)
    assert check["suspect"] is False
    assert check["confirmed"] == [18]
    assert check["corrections"] == {19: ("②", "③")}
    assert check["violations"] == [20]


def test_check_csv_suspect_suppresses_corrections():
    current = {q: "①" for q in range(18, 28)}
    csv = {q: _csv_item(ans="2") for q in range(18, 28)}   # 10/10 불일치
    check = ar.check_csv_against_answers(csv, current)
    assert check["suspect"] is True
    assert check["corrections"] == {} and check["confirmed"] == []
    assert check["mismatch"] == list(range(18, 28))


# ---------- uploaded_json 최우선 순위 및 정답 키 JSON 파싱 ----------

def test_uploaded_json_wins_over_all_sources():
    uploaded = {18: "①"}
    csv = {18: _csv_item(ans="2")}
    key = {18: "③"}
    image = _image("ok", consensus={18: "④"})
    hwp = {18: "⑤"}
    res = ar.resolve_answers(
        range(18, 19),
        verified_key=key,
        image_report=image,
        csv_rates=csv,
        hwp_answers=hwp,
        uploaded_json=uploaded,
    )
    assert res["answers"] == {18: "①"}
    assert res["sources"][18] == "uploaded_json"
    assert res["verified"][18] is True
    assert res["report"]["source_counts"]["uploaded_json"] == 1
    # CSV와 불일치 시 경고 및 json_csv_conflicts 기록 확인
    assert res["report"]["json_csv_conflicts"] == [{"q": 18, "json": "①", "csv": "②"}]
    assert any("정답 JSON과 CSV 정답 불일치 (JSON 우선 적용)" in w for w in res["report"]["warnings"])


def test_uploaded_json_stays_verified_even_with_csv_rate_discrepancy():
    uploaded = {18: "③"}
    # CSV는 후보 ①/② 만 가리킴
    csv = {18: _csv_item(rate=50.0, rates={"1": 50.0, "2": 49.0, "3": 1.0, "4": 0, "5": 0})}
    res = ar.resolve_answers(range(18, 19), uploaded_json=uploaded, csv_rates=csv)
    assert res["answers"] == {18: "③"}
    assert res["sources"][18] == "uploaded_json"
    # Ground Truth이므로 verified 상태 유지
    assert res["verified"][18] is True
    assert len(res["report"]["csv_rate_violations"]) == 1
    assert any("정답률과 모순되는 정답" in w for w in res["report"]["warnings"])


def test_parse_answer_json_various_formats():
    import answer_keys as ak

    # 1) dict with numbers
    assert ak.parse_answer_json({"18": 2, "19": 1}) == {18: "②", 19: "①"}
    # 2) dict with circles
    assert ak.parse_answer_json({"18": "③", "19": "④"}) == {18: "③", 19: "④"}
    # 3) nested {"answers": {...}}
    assert ak.parse_answer_json({"answers": {"20": 5, "21": 3}}) == {20: "⑤", 21: "③"}
    # 4) flat list of length 28 (starts at 18)
    lst28 = [1] * 28
    res28 = ak.parse_answer_json(lst28)
    assert len(res28) == 28
    assert res28[18] == "①" and res28[45] == "①"
    # 5) list of dicts
    assert ak.parse_answer_json([{"q": 18, "a": 4}, {"q": 19, "a": "②"}]) == {18: "④", 19: "②"}
    # 6) json string
    assert ak.parse_answer_json('{"18": 3, "19": 5}') == {18: "③", 19: "⑤"}

