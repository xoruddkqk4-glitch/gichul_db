"""
05-gichul_db: 수능/모의고사 문항 정답률 및 선지별 선택률(%) CSV 파서 모듈 (rate_parser.py)
- 다양한 인코딩(CP949, EUC-KR, UTF-8-SIG, UTF-8) 자동 감지
- 문항별 정답률(%), 선지별(1~5번) 응시자 수 및 선택률(%) 자동 산출
- 매력적 오답(함정 선지) 자동 판별
"""

import os
import re
import csv
import json
from typing import Dict, Any, Union, Optional, List


def parse_correct_rate_csv(file_input: Union[str, bytes]) -> Dict[int, Dict[str, Any]]:
    """
    정답률 및 선지 선택률 CSV 파일 파싱
    
    반환 형태:
    {
        18: {
            "q_num": 18,
            "correct_ans": "2",
            "correct_ans_circle": "②",
            "correct_rate": 95.81,
            "choice_rates": {
                "1": 0.0,
                "2": 95.8,
                "3": 0.5,
                "4": 2.1,
                "5": 1.6,
                "counts": {"1": 0, "2": 183, "3": 1, "4": 4, "5": 3, "no_resp": 0, "dup_resp": 0, "total": 191},
                "attractive_wrong": {"choice": "4", "rate": 2.1}
            }
        }, ...
    }
    """
    raw_bytes: bytes
    if isinstance(file_input, str):
        if not os.path.exists(file_input):
            raise FileNotFoundError(f"CSV 파일을 찾을 수 없습니다: {file_input}")
        with open(file_input, "rb") as f:
            raw_bytes = f.read()
    elif isinstance(file_input, bytes):
        raw_bytes = file_input
    else:
        raise ValueError("file_input은 파일 경로(str) 또는 bytes여야 합니다.")

    text: str = ""
    for enc in ["cp949", "euc-kr", "utf-8-sig", "utf-8"]:
        try:
            text = raw_bytes.decode(enc)
            break
        except UnicodeDecodeError:
            continue

    if not text:
        raise ValueError("지원되는 인코딩(CP949, EUC-KR, UTF-8)으로 CSV 파일을 읽을 수 없습니다.")

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return {}

    # CSV DictReader 생성
    reader = csv.reader(lines)
    header_row = next(reader, None)
    if not header_row:
        return {}

    # 컬럼 인덱스 맵핑
    col_map = {}
    for idx, col in enumerate(header_row):
        c_clean = col.strip().replace(" ", "").replace("(", "").replace(")", "")
        col_map[c_clean] = idx

    def find_col(*candidates: str) -> Optional[int]:
        for c in candidates:
            if c in col_map:
                return col_map[c]
        # 부분 일치 탐색
        for k, idx in col_map.items():
            for c in candidates:
                if c in k:
                    return idx
        return None

    col_q = find_col("번호", "문항", "문항번호", "q_num", "Q")
    col_ans = find_col("정답", "정답번호", "답", "ans", "answer")
    col_rate = find_col("정답률", "정답율", "정답률%", "rate")
    
    col_c1 = find_col("1번", "①", "1선지", "선지1")
    col_c2 = find_col("2번", "②", "2선지", "선지2")
    col_c3 = find_col("3번", "③", "3선지", "선지3")
    col_c4 = find_col("4번", "④", "4선지", "선지4")
    col_c5 = find_col("5번", "⑤", "5선지", "선지5")

    col_no_resp = find_col("무응답", "미응답", "no_resp")
    col_dup = find_col("중복답", "중복", "dup_resp")

    if col_q is None:
        raise ValueError("CSV 파일에서 '번호' 또는 '문항' 컬럼을 찾을 수 없습니다.")

    results: Dict[int, Dict[str, Any]] = {}
    circle_symbols = {"1": "①", "2": "②", "3": "③", "4": "④", "5": "⑤"}

    for row in reader:
        if not row or len(row) <= col_q:
            continue
        q_raw = row[col_q].strip()
        # 정수 번호 추출
        q_match = re.search(r"\d+", q_raw)
        if not q_match:
            continue
        q_num = int(q_match.group())

        # 정답 추출
        ans_raw = row[col_ans].strip() if (col_ans is not None and len(row) > col_ans) else ""
        # 1~5 정수형으로 정규화
        ans_num = ""
        for k, v in circle_symbols.items():
            if k in ans_raw or v in ans_raw:
                ans_num = k
                break
        if not ans_num and ans_raw.isdigit() and 1 <= int(ans_raw) <= 5:
            ans_num = str(int(ans_raw))

        circle_ans = circle_symbols.get(ans_num, ans_raw)

        # 정답률 추출
        rate_val = None
        if col_rate is not None and len(row) > col_rate:
            rate_str = row[col_rate].replace("%", "").strip()
            try:
                rate_val = round(float(rate_str), 2)
            except ValueError:
                rate_val = None

        # 1~5번 선지 카운트 파싱
        def get_count(c_idx: Optional[int]) -> float:
            if c_idx is not None and len(row) > c_idx:
                val = row[c_idx].replace(",", "").replace("%", "").strip()
                try:
                    return float(val)
                except ValueError:
                    return 0.0
            return 0.0

        c1 = get_count(col_c1)
        c2 = get_count(col_c2)
        c3 = get_count(col_c3)
        c4 = get_count(col_c4)
        c5 = get_count(col_c5)
        no_resp = get_count(col_no_resp)
        dup_resp = get_count(col_dup)

        total_resp = c1 + c2 + c3 + c4 + c5 + no_resp + dup_resp
        
        choice_rates_dict = {}
        if total_resp > 0:
            r1 = round((c1 / total_resp) * 100.0, 1)
            r2 = round((c2 / total_resp) * 100.0, 1)
            r3 = round((c3 / total_resp) * 100.0, 1)
            r4 = round((c4 / total_resp) * 100.0, 1)
            r5 = round((c5 / total_resp) * 100.0, 1)

            # 정답률이 명시되지 않은 경우, 정답 선지 비율로 계산
            if rate_val is None and ans_num:
                target_map = {"1": r1, "2": r2, "3": r3, "4": r4, "5": r5}
                rate_val = target_map.get(ans_num, 0.0)

            # 매력적 오답 (오답 중 최다 선택 선지)
            wrong_choices = []
            for ch, rate in [("1", r1), ("2", r2), ("3", r3), ("4", r4), ("5", r5)]:
                if ch != ans_num:
                    wrong_choices.append((ch, rate))
            
            attractive_wrong = None
            if wrong_choices:
                wrong_choices.sort(key=lambda x: x[1], reverse=True)
                top_wrong_ch, top_wrong_rate = wrong_choices[0]
                if top_wrong_rate >= 15.0:  # 15% 이상 선택된 경우 매력적 오답으로 표기
                    attractive_wrong = {
                        "choice": top_wrong_ch,
                        "choice_circle": circle_symbols.get(top_wrong_ch, top_wrong_ch),
                        "rate": top_wrong_rate
                    }

            choice_rates_dict = {
                "1": r1,
                "2": r2,
                "3": r3,
                "4": r4,
                "5": r5,
                "counts": {
                    "1": int(c1),
                    "2": int(c2),
                    "3": int(c3),
                    "4": int(c4),
                    "5": int(c5),
                    "no_resp": int(no_resp),
                    "dup_resp": int(dup_resp),
                    "total": int(total_resp)
                },
                "attractive_wrong": attractive_wrong
            }

        results[q_num] = {
            "q_num": q_num,
            "correct_ans": ans_num or ans_raw,
            "correct_ans_circle": circle_ans,
            "correct_rate": rate_val,
            "choice_rates": choice_rates_dict
        }

    return results


def get_difficulty_badge_info(rate: Optional[float]) -> Dict[str, str]:
    """
    정답률에 따른 난이도 등급 및 시각화 스타일 메타데이터 반환
    - 40% 미만: 킬러 / 고난도 (레드)
    - 40% ~ 60%: 중고난도 (오렌지)
    - 60% ~ 80%: 보통 (앰버/옐로우)
    - 80% 이상: 평이 (에메랄드 그린)
    """
    if rate is None:
        return {
            "level": "none",
            "label": "미등록",
            "badge_class": "badge-rate-none",
            "color": "#64748b",
            "bg": "#f1f5f9"
        }
    if rate < 40.0:
        return {
            "level": "killer",
            "label": "킬러 · 고난도",
            "badge_class": "badge-rate-killer",
            "color": "#dc2626",
            "bg": "#fef2f2"
        }
    elif rate < 60.0:
        return {
            "level": "hard",
            "label": "중고난도",
            "badge_class": "badge-rate-hard",
            "color": "#ea580c",
            "bg": "#fff7ed"
        }
    elif rate < 80.0:
        return {
            "level": "medium",
            "label": "보통 난이도",
            "badge_class": "badge-rate-medium",
            "color": "#d97706",
            "bg": "#fffbeb"
        }
    else:
        return {
            "level": "easy",
            "label": "평이 문항",
            "badge_class": "badge-rate-easy",
            "color": "#059669",
            "bg": "#ecfdf5"
        }
