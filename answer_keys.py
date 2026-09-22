"""
05-gichul_db: 검증된 시험지 정답 키 로더 (answer_keys.py)
- data/answer_keys/{학년}_{연도}_{월}.json 에 저장된 정답표 이미지 기반 검증 정답을 조회
- 정답은 코드가 아닌 데이터 파일로 관리한다 (검증 근거 포함)
"""

import os
import re
import json
from datetime import datetime
from typing import Dict, Any, Union

KEYS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "answer_keys")
CIRCLED = {"1": "①", "2": "②", "3": "③", "4": "④", "5": "⑤"}


def exam_key(grade: str, year: int, month: int) -> str:
    return f"{grade}_{int(year)}_{int(month):02d}"


def key_path(grade: str, year: int, month: int) -> str:
    return os.path.join(KEYS_DIR, exam_key(grade, year, month) + ".json")


def normalize_answer_val(val: Any) -> str:
    """숫자(1~5) 또는 원문자('①'~'⑤')를 '①'~'⑤'로 정규화"""
    s = str(val or "").strip()
    return CIRCLED.get(s, s) if (s in CIRCLED or s in CIRCLED.values()) else ""


def parse_answer_json(data: Any) -> Dict[int, str]:
    """
    유연한 JSON 정답 파서.
    지원 형태:
    1) {"18": 2, "19": "①", ...}
    2) {"answers": [{"number": 1, "answer": 5}, ...]} (EBSi 표준 포맷 등)
    3) {"answers": {"18": 2, ...}}
    4) {"data": {"18": 2, ...}} 또는 {"questions": [{"q": 18, "a": 2}, ...]}
    5) [2, 1, 4, 3, ...] (길이 45면 1~45, 길이 28이면 18~45)
    반환: {문항번호(int): '①'..'⑤'}
    """
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except Exception:
            return {}

    result: Dict[int, str] = {}

    # 리스트 형식
    if isinstance(data, list):
        if data and isinstance(data[0], dict):
            for item in data:
                q_raw = (
                    item.get("number")
                    or item.get("no")
                    or item.get("num")
                    or item.get("q")
                    or item.get("question")
                    or item.get("q_num")
                    or item.get("qNum")
                    or item.get("questionNumber")
                    or item.get("question_number")
                    or item.get("id")
                    or item.get("문항")
                    or item.get("문제")
                    or item.get("번호")
                )
                a_raw = (
                    item.get("answer")
                    or item.get("ans")
                    or item.get("a")
                    or item.get("correctAnswer")
                    or item.get("correct_answer")
                    or item.get("정답")
                    or item.get("답")
                    or item.get("val")
                    or item.get("value")
                )
                if q_raw is not None and a_raw is not None:
                    try:
                        q_int = int(str(q_raw).strip())
                        ans_str = normalize_answer_val(a_raw)
                        if ans_str:
                            result[q_int] = ans_str
                    except (ValueError, TypeError):
                        pass
        else:
            start_q = 1 if len(data) >= 40 else 18
            for idx, a_raw in enumerate(data):
                ans_str = normalize_answer_val(a_raw)
                if ans_str:
                    result[start_q + idx] = ans_str
        return result

    # 딕셔너리 형식
    if isinstance(data, dict):
        target_dict = data
        for k in ("answers", "data", "result", "items", "questions"):
            if isinstance(target_dict.get(k), (dict, list)):
                target_dict = target_dict[k]
                break

        if isinstance(target_dict, list):
            return parse_answer_json(target_dict)

        if isinstance(target_dict, dict):
            for k, v in target_dict.items():
                try:
                    q_int = int(str(k).strip())
                    ans_str = normalize_answer_val(v)
                    if ans_str:
                        result[q_int] = ans_str
                except (ValueError, TypeError):
                    m = re.search(r'\d+', str(k))
                    if m:
                        try:
                            q_int = int(m.group())
                            ans_str = normalize_answer_val(v)
                            if ans_str:
                                result[q_int] = ans_str
                        except Exception:
                            pass

    return result


def parse_answer_json_file(file_path: str) -> Dict[int, str]:
    """JSON 파일 경로에서 정답 dict 추출. utf-8, utf-8-sig, cp949 인코딩 순차 시도."""
    if not os.path.exists(file_path):
        return {}
    content = None
    for enc in ("utf-8", "utf-8-sig", "cp949"):
        try:
            with open(file_path, "r", encoding=enc) as f:
                content = f.read()
            break
        except UnicodeDecodeError:
            continue
    if not content:
        return {}
    return parse_answer_json(content)


def save_uploaded_answer_key(grade: str, year: int, month: int, answers: Dict[int, str], filename: str = "") -> str:
    """사용자가 업로드한 정답 JSON 데이터를 data/answer_keys/{key}.json 에 영구 저장"""
    path = key_path(grade, year, month)
    existing_data = {}
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                existing_data = json.load(f)
        except Exception:
            existing_data = {}

    data = {
        "exam_key": exam_key(grade, year, month),
        "grade": grade,
        "year": int(year),
        "month": int(month),
        "source_file": filename or existing_data.get("source_file", ""),
        "verification": {
            "method": "uploaded_json",
            "verified_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "warnings": [],
            "manual_overrides": existing_data.get("verification", {}).get("manual_overrides", [])
        },
        "answers": {str(int(q)): normalize_answer_val(a) for q, a in sorted(answers.items()) if normalize_answer_val(a)}
    }
    os.makedirs(KEYS_DIR, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return path


def load_answer_key(grade: str, year: int, month: int) -> Dict[int, str]:
    """검증된 정답 키 반환 {문항번호: '①'..'⑤'}. 파일이 없으면 빈 dict."""
    path = key_path(grade, year, month)
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    result: Dict[int, str] = {}
    for q, a in (data.get("answers") or {}).items():
        a = CIRCLED.get(str(a).strip(), str(a).strip())
        if a in CIRCLED.values():
            result[int(q)] = a
    return result


def record_manual_answer(grade: str, year: int, month: int, q_num: int, answer: str, old_answer: str = "", note: str = "") -> str:
    """교사가 UI에서 확정한 정답을 키 파일에 기록 (재업로드 시에도 유지). 키 파일이 없으면 생성."""
    path = key_path(grade, year, month)
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    else:
        data = {
            "exam_key": exam_key(grade, year, month), "grade": grade, "year": int(year), "month": int(month),
            "source_file": "",
            "verification": {"method": "manual", "csv_decided": [], "image_decided": [], "warnings": [],
                             "verified_at": datetime.now().strftime("%Y-%m-%d")},
            "answers": {},
        }
    data.setdefault("answers", {})[str(int(q_num))] = answer
    ver = data.setdefault("verification", {})
    ver.setdefault("manual_overrides", []).append({
        "q": int(q_num), "old": old_answer or "", "new": answer,
        "at": datetime.now().strftime("%Y-%m-%d %H:%M"), "note": note,
    })
    os.makedirs(KEYS_DIR, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return path
