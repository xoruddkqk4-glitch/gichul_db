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
# ___(A)___, (A), [A] 등 요약문 복수 빈칸 표기와 일반 밑줄/빈칸 모두 감지
_BLANK_PATTERN = re.compile(
    r'(?:[_=]{2,}\s*)?\(\s*[A-E]\s*\)(?:\s*[_=]{2,})?'   # ___(A)___, (A)___, ___(A), (A)
    r'|(?:[_=]{2,}\s*)?\[\s*[A-E]\s*\](?:\s*[_=]{2,})?'  # ___[A]___, [A]
    r'|_{2,}|={2,}'                                       # ______, ======
    r'|\[빈칸\]|\(빈칸\)|\[밑줄\]|\(밑줄\)|<u>\s*</u>|<u>\s*_{1,}\s*</u>'
)

# 선지 내부 구분자: 탭, 2개 이상의 대시, 말줄임표, 가운뎃점/불릿, 물결표, 2칸 이상의 연속 공백
_CHOICE_PART_SPLIT_PATTERN = re.compile(
    r'\s*(?:[\u2025\u2026\u22EF]+|[\.\u00b7\u2022\u318d]{2,}|[-―－]{2,}[\s\\]*|~|\t+|\s{2,})\s*'
)


def split_choice_parts(choice_text: str) -> list:
    """선지 문자열을 (A), (B) 등 하위 파트로 분할하고 잔여 기호를 정리한다."""
    if not choice_text:
        return []
    parts = _CHOICE_PART_SPLIT_PATTERN.split(choice_text.strip())
    clean_parts = []
    for p in parts:
        cp = re.sub(r'^[\s\-―－\.\u00b7\u2026\\~]+|[\s\-―－\.\u00b7\u2026\\~]+$', '', p).strip()
        if cp:
            clean_parts.append(cp)
    return clean_parts


def clean_hwp_glitches(text: str) -> str:
    """깨진 HWP 특수문자 및 저작권 문구 제거"""
    if not text:
        return ""
    # 저작권 문구 및 확인사항 제거
    t = re.sub(r'이 문제지에 관한 저작권은.*?있습니다\.?', '', text)
    t = re.sub(r'[\*·•]?\s*확인\s*사항.*', '', t)
    # 깨진 HWP 유니코드 글립 기호 정리
    t = re.sub(r'[\u0590-\u0fff]+[A-Za-z가-힣]*', ' ', t)
    return t


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
    """지문 본문 또는 해설 텍스트에서 1~5번 선지 텍스트를 추출 (40번 요약문 멀티라인 및 탭 선지 지원)"""
    choices: Dict[int, str] = {}
    if not passage_text and not explanation_text:
        return choices

    num_map = {'①': 1, '②': 2, '③': 3, '④': 4, '⑤': 5}
    text_to_search = clean_hwp_glitches(passage_text or "")

    # 1. 40번 요약문 등 지문 하단 선지 블록 역방향 탐색:
    # 지문 본문 중간의 원문자(문장삽입 번호 등)와 혼동하지 않기 위해 마지막 ⑤부터 역추적
    p5 = text_to_search.rfind('⑤')
    if p5 != -1:
        p4 = text_to_search.rfind('④', 0, p5)
        p3 = text_to_search.rfind('③', 0, p4) if p4 != -1 else -1
        p2 = text_to_search.rfind('②', 0, p3) if p3 != -1 else -1
        p1 = text_to_search.rfind('①', 0, p2) if p2 != -1 else -1

        if p1 != -1 and p2 != -1 and p3 != -1 and p4 != -1:
            positions = [p1, p2, p3, p4, p5]
            for i in range(5):
                start = positions[i] + 1
                if i < 4:
                    raw_chunk = text_to_search[start:positions[i + 1]]
                else:
                    tail = text_to_search[start:]
                    stop_match = re.search(r'\n\s*(?:(?:4[1-9]|50)\.|\d+\s*번|[【\[]\s*\d+|\*(?!\*))', tail)
                    if stop_match:
                        raw_chunk = tail[:stop_match.start()]
                    else:
                        lines = [l for l in tail.splitlines() if l.strip()]
                        raw_chunk = "\n".join(lines[:3]) if lines else tail

                chunk_clean = re.sub(r'\[\d+점\]', '', raw_chunk)
                # 줄바꿈을 탭으로 변환하여 멀티라인 (A)/(B) 선지의 경계 유지
                chunk_clean = re.sub(r'[\r\n]+', '\t', chunk_clean).strip()
                if chunk_clean:
                    choices[i + 1] = chunk_clean

    # 2. 기존 정규식 기반 탐색 (원문자 사이 \t 포함 허용: [^①②③④⑤\n\r]+)
    if len(choices) < 5 and text_to_search:
        pattern_circle = re.compile(r'([①②③④⑤])\s*([^①②③④⑤\n\r]+)')
        matches = list(pattern_circle.finditer(text_to_search))
        if len(matches) >= 3:
            for m in matches:
                idx = num_map.get(m.group(1))
                val = m.group(2).strip()
                val = re.sub(r'\[\d+점\]', '', val).strip()
                if idx and val and idx not in choices:
                    choices[idx] = val

    # 3. 줄 단위 패턴: (1) 텍스트, 1. 텍스트 등
    if len(choices) < 5 and text_to_search:
        line_pattern = re.compile(r'(?:^|\n)\s*(?:[①②③④⑤]|\([1-5]\)|[1-5]\.)\s*([^\n\r]+)')
        alt_matches = list(line_pattern.finditer(text_to_search))
        if len(alt_matches) >= 4:
            for i, m in enumerate(alt_matches[:5], 1):
                if i not in choices:
                    choices[i] = m.group(1).strip()

    # 4. explanation_text에서 선지 추출
    if len(choices) < 5 and explanation_text:
        pattern_circle = re.compile(r'([①②③④⑤])\s*([^①②③④⑤\n\r]+)')
        matches_exp = list(pattern_circle.finditer(clean_hwp_glitches(explanation_text)))
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
    1. 한국어 발문 또는 단순 헤더는 치환하지 않고 원문 반환
    2. 깨진 HWP 특수문자 엔티티(&#56192;&#56379;, &#61440; 등) 및 불릿 기호 제거
    3. 단일 밑줄/빈칸(____)은 정답 선지 텍스트로 치환
    4. 40번 요약문 등 2개 이상의 빈칸(A/B)은 선지 구분자(……, ..., ~, \\t 등)로 분할하여 각각의 빈칸에 1:1 순서대로 치환
    5. 선지 식별 기호 제거 및 구두점/공백 정리하여 완전한 자연어 문장 완성
    """
    if not sentence_text:
        return ""

    # 한국어 발문 또는 단순 (A)/(B) 헤더는 빈칸 치환 대상이 아니므로 그대로 유지
    if re.search(r'다음\s*글의\s*내용|가장\s*적절한\s*것은', sentence_text):
        return sentence_text
    if re.match(r'^\s*\(?\s*A\s*\)?\s*[\t\s]+\(?\s*B\s*\)?\s*$', sentence_text):
        return sentence_text

    # 1. HWP HTML 엔티티 및 특수 기호 정리
    cleaned = clean_hwp_glitches(sentence_text)
    cleaned = re.sub(r'&#\d+;', ' ', cleaned)
    cleaned = re.sub(r'[\uF000-\uFFFF]', ' ', cleaned)

    # 2. 밑줄 / 빈칸 패턴 탐색 및 정답 선지 삽입
    blank_matches = list(_BLANK_PATTERN.finditer(cleaned))

    if blank_matches:
        choices = extract_choices(passage_text, explanation_text)
        ans_num = extract_answer_num(answer_text)
        if ans_num and ans_num in choices:
            raw_choice = choices[ans_num]
            # 배점 제거 ([3점] 등)
            raw_choice = re.sub(r'\[\d+점\]', '', raw_choice).strip()
            split_parts = split_choice_parts(raw_choice)

            # 빈칸이 2개 이상이고, 선지도 복수 파트로 분할되는 경우 (40번 요약문 등)
            if len(blank_matches) >= 2 and len(split_parts) >= 2:
                res = []
                last_idx = 0
                for i, m in enumerate(blank_matches):
                    res.append(cleaned[last_idx:m.start()])
                    replacement = split_parts[i] if i < len(split_parts) else split_parts[-1]
                    res.append(f" {replacement.strip()} ")
                    last_idx = m.end()
                res.append(cleaned[last_idx:])
                cleaned = "".join(res)
            elif len(blank_matches) == 1 and len(split_parts) >= 1:
                m = blank_matches[0]
                cleaned = cleaned[:m.start()] + f" {split_parts[0].strip()} " + cleaned[m.end():]
            elif len(split_parts) == 1:
                cleaned = _BLANK_PATTERN.sub(f" {split_parts[0].strip()} ", cleaned)

    # 3. 잔여 선지 기호 정리
    cleaned = clean_choice_markers(cleaned)
    # 구두점 앞 불필요한 공백 제거 (예: "create state authority : " -> "create state authority:")
    cleaned = re.sub(r'\s+([,.:;?!])', r'\1', cleaned)
    # 중복 공백 정리
    cleaned = re.sub(r'[ \t]{2,}', ' ', cleaned).strip()

    return cleaned
