"""
05-gichul_db: DB에 의존하지 않는 순수 텍스트 유틸리티 (text_utils.py)
- 이 모듈은 다른 gichul 모듈을 import 하지 않습니다 (순환 import 방지, 단위 테스트 용이).
- ID 정규화, 해설 [정답] 헤더 갱신, 선지/정답 번호 추출, 빈칸 정답 채우기
"""

import os
import re
from typing import Dict, Optional

# 파일명 화이트리스트 정제용 패턴 (한글, 영숫자, 하이픈, 밑줄, 공백, 괄호 외 제거)
_SAFE_FILENAME_CHARS_RE = re.compile(r'[^가-힣ㄱ-ㅎㅏ-ㅣa-zA-Z0-9\s\-_()[\]]')
_DANGEROUS_EXTS = {".exe", ".bat", ".cmd", ".sh", ".py", ".vbs", ".ps1", ".msi", ".dll", ".so", ".dylib"}


def sanitize_upload_filename(filename: str, default_name: str = "upload") -> str:
    """
    업로드된 파일명에서 디렉토리 순회(../ 등) 및 허용되지 않는 특수문자를 제거하여 안전한 파일명으로 정제한다.
    - Windows/POSIX 경로 구분자(\\, /)를 모두 제거하여 basename만 추출
    - 한글, 영숫자, 하이픈, 밑줄, 괄호 외 문자는 '_'로 치환
    - 위험한 실행 확장자 차단 (.bin 치환)
    - 파일명이 비어있거나 화이트리스트 정제 후 빈 문자열이 되면 default_name으로 대체
    """
    if not filename:
        return default_name

    # 1. 경로 구분자(\\, /) 제거 및 basename 추출 (경로 탐색 방지)
    raw_name = filename.replace("\\", "/").rstrip("/").split("/")[-1]
    raw_name = os.path.basename(raw_name).strip()

    # 2. 파일명과 확장자 분리
    base, ext = os.path.splitext(raw_name)

    # 3. 확장자 정제
    clean_ext = ext.lower().strip()
    if clean_ext in _DANGEROUS_EXTS:
        clean_ext = ".bin"
    # 확장자 내 점과 영숫자만 허용
    clean_ext = re.sub(r'[^a-z0-9.]', '', clean_ext)

    # 4. 베이스 파일명 화이트리스트 필터링
    clean_base = _SAFE_FILENAME_CHARS_RE.sub('_', base)
    # 연속된 밑줄 및 공백 정리, 양 끝 점/공백/밑줄 트림
    clean_base = re.sub(r'[_]{2,}', '_', clean_base)
    clean_base = re.sub(r'\s{2,}', ' ', clean_base)
    clean_base = clean_base.strip('. _')

    if not clean_base:
        clean_base = default_name

    return f"{clean_base}{clean_ext}"


# 해설 맨 앞 [정답] 헤더 감지 / 교체 패턴
_ANSWER_HEADER_DETECT = re.compile(r"^\s*\[\s*정답\s*\]")
_ANSWER_HEADER_REPLACE = r"^\s*\[\s*정답\s*\]\s*[①②③④⑤1-5]?"

# 빈칸/밑줄 패턴 (fill_blanks)
# - 요약문 복수 빈칸 표기(___(A)___, (A)___, ___(A))는 하나의 빈칸으로 본다.
# - 밑줄 없는 맨 (A)/[A]는 빈칸이 아니다: 글의 순서(36·37번) 문단 표지, 어법 네모 (A)/(B)/(C) 표지로 쓰인다.
#   (실제 DB 40번 요약문 중 밑줄 없이 맨 (A)(B)만 쓴 문장은 0건)
_BLANK_PATTERN = re.compile(
    r'_{2,}\s*\(\s*[A-E]\s*\)(?:\s*_{2,})?'   # ___(A)___, ___(A)
    r'|\(\s*[A-E]\s*\)\s*_{2,}'               # (A)___
    r'|_{2,}\s*\[\s*[A-E]\s*\](?:\s*_{2,})?'  # ___[A]___, ___[A]
    r'|\[\s*[A-E]\s*\]\s*_{2,}'               # [A]___
    r'|_{2,}'                                 # ______
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
        cp = re.sub(r'\s+', ' ', cp)  # 전각 공백(\u3000) 등을 공백 하나로
        if cp:
            clean_parts.append(cp)
    return clean_parts


# 빈칸에 붙은 (A)~(E) 표지 추출용 (_BLANK_PATTERN 매치 문자열 안에서 찾는다)
_BLANK_LABEL_RE = re.compile(r'[\(\[]\s*([A-E])\s*[\)\]]')


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


_WORD_CHAR_RE = re.compile(r'[A-Za-z0-9가-힣]')


def _drop_glyph_segments(text: str) -> str:
    """탭/줄바꿈으로 나뉜 조각 중 글자·숫자가 하나도 없는 조각(깨진 HWP 글립 등)을 버린다.
    ……, --- 같은 구분자 조각도 빠지지만, 남은 조각을 탭으로 다시 잇기 때문에 split_choice_parts 는 그대로 나뉜다.
    """
    segs = [s.strip() for s in re.split(r'[\t\r\n]+', text)]
    return "\t".join(s for s in segs if s and _WORD_CHAR_RE.search(s))

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
            prev_line_count = 1
            for i in range(5):
                start = positions[i] + 1
                if i < 4:
                    raw_chunk = text_to_search[start:positions[i + 1]]
                    # ⑤ 뒤에는 다음 원문자가 없으므로, 바로 앞 선지(④)가 차지한 줄 수만큼만 가져온다
                    prev_line_count = max(1, len([l for l in raw_chunk.splitlines() if l.strip()]))
                else:
                    tail = text_to_search[start:]
                    stop_match = re.search(r'\n\s*(?:(?:4[1-9]|50)\.|\d+\s*번|[【\[]\s*\d+|\*(?!\*))', tail)
                    if stop_match:
                        tail = tail[:stop_match.start()]
                    lines = [l for l in tail.splitlines() if l.strip()]
                    raw_chunk = "\n".join(lines[:prev_line_count])

                chunk_clean = re.sub(r'\[\d+점\]', '', raw_chunk)
                # 줄바꿈을 탭으로 바꿔 멀티라인 (A)/(B) 선지의 경계를 유지하고, 글립만 있는 조각은 버린다
                chunk_clean = _drop_glyph_segments(chunk_clean)
                if chunk_clean:
                    choices[i + 1] = chunk_clean

    # 2. 기존 정규식 기반 탐색 (원문자 사이 \t 포함 허용: [^①②③④⑤\n\r]+)
    if len(choices) < 5 and text_to_search:
        pattern_circle = re.compile(r'([①②③④⑤])\s*([^①②③④⑤\n\r]+)')
        matches = list(pattern_circle.finditer(text_to_search))
        if len(matches) >= 3:
            for m in matches:
                idx = num_map.get(m.group(1))
                val = _drop_glyph_segments(re.sub(r'\[\d+점\]', '', m.group(2)))
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
                val = _drop_glyph_segments(re.sub(r'\[\d+점\]', '', m.group(2)))
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
    4. 40번 요약문 등 2개 이상의 빈칸(A/B)은 선지를 split_choice_parts 로 나눠 각 빈칸에 1:1 순서대로 치환
    5. 빈칸을 채운 경우에만 구두점 및 불필요한 공백 정리 (빈칸이 없는 문장은 1~2단계만 적용)
    """
    if not sentence_text:
        return ""

    # 1. HWP HTML 엔티티 제거 (&#56192;&#56379;, &#61440; 등)
    cleaned = re.sub(r'&#\d+;', ' ', sentence_text)
    # 빈칸 표지 (A)/(B) 기록: 다음 단계에서 ___(B)___ 의 (B)가 지워지므로 먼저 순서대로 읽어 둔다
    labels = []
    for m in _BLANK_PATTERN.finditer(cleaned):
        lm = _BLANK_LABEL_RE.search(m.group(0))
        labels.append(ord(lm.group(1)) - ord('A') if lm else None)
    # 2. 선지 기호 정리 (___(A)___ 의 (A)도 여기서 빠져 ______ 로 남는다)
    cleaned = clean_choice_markers(cleaned)
    # 3. 특수 유니코드 박스/불릿 기호 정리
    cleaned = re.sub(r'[\uF000-\uFFFF]', ' ', cleaned)

    # 4. 밑줄 / 빈칸 패턴 탐색 및 정답 선지 삽입
    blank_matches = list(_BLANK_PATTERN.finditer(cleaned))
    if len(labels) != len(blank_matches):
        labels = [None] * len(blank_matches)  # 짝이 맞지 않으면 표지는 쓰지 않는다

    if blank_matches:
        choices = extract_choices(passage_text, explanation_text)
        ans_num = extract_answer_num(answer_text)
        if ans_num and ans_num in choices:
            raw_choice = re.sub(r'\[\d+점\]', '', choices[ans_num]).strip()  # 배점 제거
            split_parts = split_choice_parts(raw_choice)
            # 단일 빈칸용: 선지 전체 (선지 기호 제거, 줄바꿈/탭은 공백 하나로)
            whole_choice = re.sub(r'\s+', ' ', clean_choice_markers(raw_choice)).strip()
            multi = len(blank_matches) >= 2 and len(split_parts) >= 2

            def _replacement(i: int) -> str:
                label = labels[i]
                if len(split_parts) >= 2 and label is not None and label < len(split_parts):
                    return split_parts[label]  # ___(B)___ -> 선지의 (B) 부분 (빈칸이 다른 문장에 나뉘어 있어도)
                if multi:
                    return split_parts[i] if i < len(split_parts) else split_parts[-1]  # 순서대로 1:1
                return whole_choice  # 단일 빈칸 또는 선지를 나눌 수 없는 경우: 선지 전체

            res = []
            last_idx = 0
            for i, m in enumerate(blank_matches):
                res.append(cleaned[last_idx:m.start()])
                res.append(_replacement(i))
                last_idx = m.end()
            res.append(cleaned[last_idx:])
            cleaned = "".join(res)

            # 구두점 앞 불필요한 공백 제거 (예: "create state authority : " -> "create state authority:")
            cleaned = re.sub(r'\s+([,.:;?!])', r'\1', cleaned)
            # 중복 공백 정리
            cleaned = re.sub(r'[ \t]{2,}', ' ', cleaned).strip()

    return cleaned
