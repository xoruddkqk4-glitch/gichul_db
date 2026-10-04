"""
05-gichul_db: DB에 의존하지 않는 순수 텍스트 유틸리티 (text_utils.py)
- 이 모듈은 다른 gichul 모듈을 import 하지 않습니다 (순환 import 방지, 단위 테스트 용이).
- ID 정규화, 해설 [정답] 헤더 갱신, 선지/정답 번호 추출, 빈칸 정답 채우기
"""

import re
from typing import Dict, Optional

# 해설 맨 앞 [정답] 헤더 감지 / 교체 패턴
_ANSWER_HEADER_DETECT = re.compile(r"^\s*\[\s*정답\s*\]")
_ANSWER_HEADER_REPLACE = r"^\s*\[\s*정답\s*\]\s*[①②③④⑤1-5]?"

# 빈칸/밑줄 패턴 (fill_blanks)
_BLANK_PATTERN = re.compile(r'_{2,}|\[빈칸\]|\(빈칸\)|\[밑줄\]|\(밑줄\)|<u>\s*</u>|<u>\s*_{1,}\s*</u>')


def normalize_bracket_id(raw: str) -> str:
    """앞뒤 공백을 제거하고, 대괄호로 시작하지 않으면 '[...]'로 감싼다.
    예) '고3-2024년-06월-18번' -> '[고3-2024년-06월-18번]', ' [ID] ' -> '[ID]'
    (기존 `clean_id = x.strip(); if not clean_id.startswith("["): clean_id = f"[{clean_id}]"` 패턴과 동일)
    """
    s = raw.strip()
    if not s.startswith("["):
        s = f"[{s}]"
    return s


def apply_answer_header(explanation: str, answer: str) -> str:
    """해설 맨 앞의 '[정답] N' 헤더를 갱신하거나, 없으면 맨 앞에 추가한다.
    - 헤더가 있으면: 기존 '[정답] (번호)' 부분만 '[정답] {answer}'로 교체 (본문은 그대로)
    - 헤더가 없으면: '[정답] {answer}\\n\\n{explanation}' 후 양끝 공백 제거
    입력 explanation 은 그대로 사용한다 (strip 여부는 호출하는 쪽의 기존 동작을 유지).
    """
    exp = explanation or ""
    if _ANSWER_HEADER_DETECT.search(exp):
        return re.sub(_ANSWER_HEADER_REPLACE, f"[정답] {answer}", exp, count=1)
    return f"[정답] {answer}\n\n{exp}".strip()


def extract_answer_num(ans_text: str) -> Optional[int]:
    """정답 문자열에서 1~5 정답 번호 추출 (e.g. '③' -> 3, '3' -> 3, '[정답] ④' -> 4)"""
    if not ans_text:
        return None
    num_map = {
        '①': 1, '②': 2, '③': 3, '④': 4, '⑤': 5,
        '1': 1, '2': 2, '3': 3, '4': 4, '5': 5
    }
    for ch in ['①', '②', '③', '④', '⑤']:
        if ch in ans_text:
            return num_map[ch]
    m = re.search(r'[1-5]', ans_text)
    if m:
        return int(m.group(0))
    return None


def extract_choices(passage_text: str, explanation_text: str = "") -> Dict[int, str]:
    """지문 본문 또는 해설 텍스트에서 1~5번 선지 텍스트를 추출"""
    choices: Dict[int, str] = {}
    if not passage_text and not explanation_text:
        return choices

    # 1. passage_text에서 원문자(①~⑤) 패턴 추출
    pattern_circle = re.compile(r'([①②③④⑤])\s*([^①②③④⑤\n\r\t]+)')
    matches = list(pattern_circle.finditer(passage_text or ""))
    num_map = {'①': 1, '②': 2, '③': 3, '④': 4, '⑤': 5}

    if len(matches) >= 3:
        for m in matches:
            idx = num_map.get(m.group(1))
            val = m.group(2).strip()
            val = re.sub(r'\[\d+점\]', '', val).strip()
            if idx and val:
                choices[idx] = val

    # 2. 줄 단위 패턴: (1) 텍스트, 1. 텍스트 등
    if len(choices) < 5 and passage_text:
        line_pattern = re.compile(r'(?:^|\n)\s*(?:[①②③④⑤]|\([1-5]\)|[1-5]\.)\s*([^\n\r]+)')
        alt_matches = list(line_pattern.finditer(passage_text))
        if len(alt_matches) >= 4:
            for i, m in enumerate(alt_matches[:5], 1):
                choices[i] = m.group(1).strip()

    # 3. 만약 passage_text에 없고 explanation_text에 선지가 있는 경우
    if len(choices) < 5 and explanation_text:
        matches_exp = list(pattern_circle.finditer(explanation_text))
        if len(matches_exp) >= 3:
            for m in matches_exp:
                idx = num_map.get(m.group(1))
                val = m.group(2).strip()
                val = re.sub(r'\[\d+점\]', '', val).strip()
                if idx and val and idx not in choices:
                    choices[idx] = val

    return choices


def clean_choice_markers(text: str) -> str:
    """
    선지를 의미하는 번호 및 식별 기호(1, 2, 3, 4, 5, ①~⑤, (1)~(5), (a)~(e) 등) 제거
    """
    if not text:
        return ""
    # 1. 괄호 속 선지 번호/문자: ( ① ), ( ② ), (1), (2), (3), (4), (5), (a), (b), (c), (d), (e)
    t = re.sub(r'\(\s*[①②③④⑤1-5a-eA-E]\s*\)', '', text)
    # 2. 단독 원문자: ①, ②, ③, ④, ⑤
    t = re.sub(r'[①②③④⑤]', '', t)
    # 3. 문단 식별용 (A), (B), (C), (D) 문두 마커
    t = re.sub(r'^\s*\([A-E]\)\s*', '', t)
    # 4. 문두 번호 마커: ^1. , ^2) , ^[1] 등
    t = re.sub(r'^\s*\[?[1-5]\]?[\.\)]\s*', '', t)
    # 5. 중복 공백 정리
    t = re.sub(r'[ \t]{2,}', ' ', t)
    return t.strip()


def fill_blanks(
    sentence_text: str,
    passage_text: str = "",
    answer_text: str = "",
    explanation_text: str = ""
) -> str:
    """
    문장 분석(어법/문법 분석)을 위한 순수 전처리 (DB 조회 없음):
    1. 깨진 HWP 특수문자 엔티티(&#56192;&#56379;, &#61440; 등) 및 불릿 기호 제거
    2. 선지 식별 기호(1, 2, 3, 4, 5, ①~⑤, (1)~(5), (a)~(e) 등) 제거
    3. 단일 밑줄/빈칸(____)은 정답 선지 텍스트로 치환
    4. 40번 요약문 등 2개 이상의 빈칸(A/B)은 선지 구분자(……, ..., ~ 등)로 분할하여 각각의 빈칸에 1:1 순서대로 치환
    5. 구두점 및 불필요한 공백 정리하여 완전한 자연어 문장 완성
    """
    if not sentence_text:
        return ""

    # 1. HWP HTML 엔티티 제거 (&#56192;&#56379;, &#61440; 등)
    cleaned = re.sub(r'&#\d+;', ' ', sentence_text)
    # 2. 선지 기호 정리
    cleaned = clean_choice_markers(cleaned)
    # 3. 특수 유니코드 박스/불릿 기호 정리
    cleaned = re.sub(r'[\uF000-\uFFFF]', ' ', cleaned)

    # 4. 밑줄 / 빈칸 패턴 탐색 및 정답 선지 삽입
    blank_matches = list(_BLANK_PATTERN.finditer(cleaned))

    if blank_matches:
        choices = extract_choices(passage_text, explanation_text)
        ans_num = extract_answer_num(answer_text)
        if ans_num and ans_num in choices:
            raw_choice = clean_choice_markers(choices[ans_num])
            # 배점 제거 ([3점] 등)
            raw_choice = re.sub(r'\[\d+점\]', '', raw_choice).strip()

            # 빈칸이 2개 이상이고, 선지에 구분자(……, ..., ~, \t, 3칸 이상 공백)가 있는 경우 (40번 요약문 등)
            split_parts = re.split(r'\s*(?:[\u2025\u2026\u22EF]+|\.{2,}|~|\t|\s{3,})\s*', raw_choice)
            if len(blank_matches) >= 2 and len(split_parts) >= 2:
                # 복수 빈칸에 각각 순서대로 선지 부분 치환
                res = []
                last_idx = 0
                for i, m in enumerate(blank_matches):
                    res.append(cleaned[last_idx:m.start()])
                    replacement = split_parts[i] if i < len(split_parts) else split_parts[-1]
                    res.append(replacement.strip())
                    last_idx = m.end()
                res.append(cleaned[last_idx:])
                cleaned = "".join(res)
            else:
                # 단일 빈칸 또는 전체 치환
                cleaned = _BLANK_PATTERN.sub(raw_choice, cleaned)

            # 구두점 앞 불필요한 공백 제거 (예: "create state authority : " -> "create state authority:")
            cleaned = re.sub(r'\s+([,.:;?!])', r'\1', cleaned)
            # 중복 공백 정리
            cleaned = re.sub(r'[ \t]{2,}', ' ', cleaned).strip()

    return cleaned
