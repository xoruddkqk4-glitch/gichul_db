"""rate_parser.py 회귀 테스트 — 정답률 CSV 파싱(실제 교육청 포맷), 인코딩, 매력적 오답, 난이도 배지"""
import pytest

from rate_parser import parse_correct_rate_csv, get_difficulty_badge_info

# 실제 업로드 CSV(uploads/고1_2022_03_*.csv)와 동일한 컬럼 구조
REAL_HEADER = "과목명,번호,무응답,1번,2번,3번,4번,5번,중복답,정답,정답률"
REAL_ROWS = [
    "영어,1,1,167,13,15,16,0,0,1,78.77 %",
    "영어,2,1,0,1,209,0,1,0,3,98.58 %",
    "영어,3,1,2,186,15,5,3,0,2,87.74 %",
]


def _csv_bytes(header, rows, enc="cp949"):
    return ("\n".join([header] + rows) + "\n").encode(enc)


# ---------- 실제 포맷 파싱 ----------

def test_real_format_cp949_basic_fields():
    result = parse_correct_rate_csv(_csv_bytes(REAL_HEADER, REAL_ROWS))
    assert sorted(result) == [1, 2, 3]
    q1 = result[1]
    assert q1["q_num"] == 1
    assert q1["correct_ans"] == "1"
    assert q1["correct_ans_circle"] == "①"
    assert q1["correct_rate"] == 78.77
    assert result[2]["correct_ans_circle"] == "③"
    assert result[3]["correct_ans_circle"] == "②"


def test_real_format_choice_counts_and_rates():
    q1 = parse_correct_rate_csv(_csv_bytes(REAL_HEADER, REAL_ROWS))[1]["choice_rates"]
    counts = q1["counts"]
    assert counts == {"1": 167, "2": 13, "3": 15, "4": 16, "5": 0, "no_resp": 1, "dup_resp": 0, "total": 212}
    assert q1["1"] == 78.8   # 167/212
    assert q1["2"] == 6.1
    assert q1["3"] == 7.1
    assert q1["4"] == 7.5
    assert q1["5"] == 0.0
    assert q1["attractive_wrong"] is None  # 오답 최다 선택률 7.5% < 15%


def test_answer_column_not_confused_with_rate_column():
    # '정답'(index 9)과 '정답률'(index 10)이 모두 있을 때 정답은 정답 컬럼에서만 읽어야 한다
    q2 = parse_correct_rate_csv(_csv_bytes(REAL_HEADER, REAL_ROWS))[2]
    assert q2["correct_ans"] == "3"
    assert q2["correct_rate"] == 98.58


def test_utf8_sig_encoding_supported():
    result = parse_correct_rate_csv(_csv_bytes(REAL_HEADER, REAL_ROWS, enc="utf-8-sig"))
    assert result[1]["correct_ans_circle"] == "①"


def test_file_path_input(tmp_path):
    p = tmp_path / "rates.csv"
    p.write_bytes(_csv_bytes(REAL_HEADER, REAL_ROWS))
    assert parse_correct_rate_csv(str(p))[3]["correct_rate"] == 87.74


def test_missing_file_raises():
    with pytest.raises(FileNotFoundError):
        parse_correct_rate_csv("no/such/file.csv")


# ---------- 매력적 오답 / 정답률 유도 ----------

def test_attractive_wrong_detected_at_15_percent_or_more():
    rows = ["영어,30,0,100,20,60,15,5,0,1,50.0 %"]  # 총 200명, 3번 선지 30%
    q = parse_correct_rate_csv(_csv_bytes(REAL_HEADER, rows))[30]
    aw = q["choice_rates"]["attractive_wrong"]
    assert aw == {"choice": "3", "choice_circle": "③", "rate": 30.0}


def test_rate_derived_from_correct_choice_when_rate_column_missing():
    header = "번호,1번,2번,3번,4번,5번,정답"
    rows = ["18,10,70,10,5,5,2"]
    q = parse_correct_rate_csv(_csv_bytes(header, rows))[18]
    assert q["correct_rate"] == 70.0
    assert q["correct_ans_circle"] == "②"


def test_circled_answer_value_and_beon_suffix_normalized():
    header = "번호,정답,정답률"
    rows = ["18,③,80 %", "19,4번,70 %", "20,7,60 %"]  # 7은 1~5 범위 밖 → 원문자 없음
    result = parse_correct_rate_csv(_csv_bytes(header, rows))
    assert result[18]["correct_ans_circle"] == "③"
    assert result[19]["correct_ans_circle"] == "④"
    assert result[20]["correct_ans_circle"] == ""
    assert result[20]["choice_rates"] == {}  # 선지 카운트 컬럼이 없으면 빈 dict


def test_rows_without_numeric_question_skipped():
    rows = ["영어,합계,0,0,0,0,0,0,0,,", "영어,5,0,10,10,10,10,10,0,5,20 %"]
    result = parse_correct_rate_csv(_csv_bytes(REAL_HEADER, rows))
    assert list(result) == [5]


# ---------- 헤더 판별 ----------

def test_missing_question_column_raises():
    with pytest.raises(ValueError):
        parse_correct_rate_csv(_csv_bytes("과목,점수", ["영어,80"]))


def test_headerless_45_row_rate_only_csv():
    rows = [f"{50 + i * 0.5} %,2" for i in range(45)]
    result = parse_correct_rate_csv("\n".join(rows).encode("cp949"))
    assert len(result) == 45
    assert result[1]["correct_rate"] == 50.0
    assert result[45]["correct_rate"] == 72.0
    assert result[1]["correct_ans"] == ""


def test_empty_input_raises_value_error():
    # 현재 동작: 빈 파일은 디코딩 결과가 빈 문자열이라 인코딩 오류 메시지의 ValueError로 처리됨
    with pytest.raises(ValueError):
        parse_correct_rate_csv(b"")


# ---------- 난이도 배지 ----------

@pytest.mark.parametrize("rate,level", [
    (None, "none"),
    (0.0, "killer"),
    (39.99, "killer"),
    (40.0, "hard"),
    (59.99, "hard"),
    (60.0, "medium"),
    (79.99, "medium"),
    (80.0, "easy"),
    (100.0, "easy"),
])
def test_difficulty_badge_thresholds(rate, level):
    assert get_difficulty_badge_info(rate)["level"] == level
