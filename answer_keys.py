"""
05-gichul_db: 검증된 시험지 정답 키 로더 (answer_keys.py)
- data/answer_keys/{학년}_{연도}_{월}.json 에 저장된 정답표 이미지 기반 검증 정답을 조회
- 정답은 코드가 아닌 데이터 파일로 관리한다 (검증 근거 포함)
"""

import os
import json
from datetime import datetime
from typing import Dict

KEYS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "answer_keys")
CIRCLED = {"1": "①", "2": "②", "3": "③", "4": "④", "5": "⑤"}


def exam_key(grade: str, year: int, month: int) -> str:
    return f"{grade}_{int(year)}_{int(month):02d}"


def key_path(grade: str, year: int, month: int) -> str:
    return os.path.join(KEYS_DIR, exam_key(grade, year, month) + ".json")


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
