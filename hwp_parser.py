"""
05-gichul_db: HWP/HWPX 문서 및 정답/해설 추출 모듈 (hwp_parser.py)
- HWPX(XML 기반 초고속 파싱) 및 HWP(pyhwpx OLE 연동) 지원
- 문항 번호별 지문 텍스트 추출
- 정답 및 해설 파일(또는 섹션)에서 문항별 정답 번호, 해설, 해석, 어휘 블록 추출
"""

import os
import re
import zipfile
import xml.etree.ElementTree as ET
from typing import Any, Dict, Optional, Tuple


def sanitize_text(text: str) -> str:
    """한글 문서의 특수 제어문자 및 유니코드 서로게이트 문자 정제"""
    if not text:
        return ""
    # U+D800 ~ U+DFFF 대행 문자 제거
    text = re.sub(r"[\ud800-\udfff]", "", text)
    # 널 문자 등 불필요한 제어 문자 제거
    text = text.replace("\x00", "")
    return text.strip()


def extract_hwpx_text(file_path: str) -> str:
    """HWPX(ZIP/XML)에서 순수 텍스트 고속 추출"""
    full_text = []
    try:
        with zipfile.ZipFile(file_path, "r") as zf:
            section_files = [f for f in zf.namelist() if f.startswith("Contents/section") and f.endswith(".xml")]
            section_files.sort()
            for sf in section_files:
                xml_data = zf.read(sf)
                root = ET.fromstring(xml_data)
                # <hp:t> 태그 텍스트 추출
                for elem in root.iter():
                    if elem.tag.endswith("t") and elem.text:
                        full_text.append(elem.text)
                    elif elem.tag.endswith("p"):
                        full_text.append("\n")
    except Exception as e:
        print(f"[HWPX 직접 파싱 경고] {e}")
        return ""

    return sanitize_text("".join(full_text))


def ensure_hwp_security_module() -> bool:
    """
    한글(Hancom Office) 자동화 시 보안 경고 팝업
    ('한글을 이용하여 위 파일에 접근하려는 시도... 접근 허용')을 억제하기 위해
    Windows 레지스트리에 FilePathCheckerModule 보안 모듈을 자동 등록합니다.
    """
    import sys
    if sys.platform != "win32":
        return False

    try:
        import winreg
        import pyhwpx
        pyhwpx_dir = os.path.dirname(pyhwpx.__file__)
        dll_path = os.path.join(pyhwpx_dir, "FilePathCheckerModule.dll")
        if not os.path.exists(dll_path):
            user_profile = os.environ.get("USERPROFILE", "")
            alt_path = os.path.join(user_profile, "FilePathCheckerModule.dll")
            if os.path.exists(alt_path):
                dll_path = alt_path
            else:
                return False

        target_keys = [
            (winreg.HKEY_CURRENT_USER, r"Software\HNC\HwpAutomation\Modules"),
            (winreg.HKEY_CURRENT_USER, r"Software\Hnc\HwpUserAction\Modules"),
        ]

        for root_key, sub_key in target_keys:
            for access_flag in [0, winreg.KEY_WOW64_32KEY, winreg.KEY_WOW64_64KEY]:
                try:
                    k = winreg.CreateKeyEx(root_key, sub_key, 0, winreg.KEY_SET_VALUE | access_flag)
                    winreg.SetValueEx(k, "FilePathCheckerModule", 0, winreg.REG_SZ, os.path.abspath(dll_path))
                    winreg.CloseKey(k)
                except Exception:
                    pass
        return True
    except Exception as e:
        print(f"[HWP 보안모듈 레지스트리 등록 경고] {e}")
        return False


# 모듈 임포트 시 자동 보안 모듈 등록 실행
ensure_hwp_security_module()


def extract_hwp_text_pyhwpx(file_path: str) -> str:
    """pyhwpx를 사용하여 HWP 텍스트 추출 (백그라운드 OLE 및 보안 팝업 차단)"""
    ensure_hwp_security_module()
    try:
        from pyhwpx import Hwp
        hwp = Hwp(new=True, visible=False, register_module=True)
        try:
            # 보안 승인 모듈 명시적 등록 및 메시지 박스 억제
            try:
                hwp.RegisterModule("FilePathCheckDLL", "FilePathCheckerModule")
            except Exception:
                pass
            try:
                hwp.SetMessageBoxMode(0x00070000)
            except Exception:
                pass

            opened = hwp.Open(os.path.abspath(file_path))
            if not opened:
                print(f"[pyhwpx] 파일 열기 실패: {file_path}")
            # option="" 전달하여 전체 문서 텍스트 추출 (기본값 saveblock:true 시 None 반환 방지)
            text = hwp.GetTextFile("TEXT", "")
            if not text:
                text = hwp.GetTextFile("UNICODE", "")
            return sanitize_text(text or "")
        finally:
            try:
                hwp.Quit()
            except Exception:
                pass
    except Exception as e:
        print(f"[pyhwpx 추출 경고] {e}")
        return ""


def get_hwp_text(file_path: str) -> str:
    """확장자에 따라 HWPX 또는 HWP 텍스트 자동 추출"""
    ext = os.path.splitext(file_path)[1].lower()
    if ext == ".hwpx":
        txt = extract_hwpx_text(file_path)
        if txt:
            return txt
    return extract_hwp_text_pyhwpx(file_path)


# 20대 표준 문제 유형 정의
QUESTION_TYPES = [
    "글의목적", "심경변화", "주장", "어휘함축", "글의요지", "글의주제", "글의제목",
    "도표", "불일치", "실용문불일치", "실용문일치", "어법", "어휘", "빈칸",
    "문장빼기", "글의순서", "문장넣기", "글의요약", "1지문2문항", "1지문3문항"
]


def classify_question_type(title: str, q_num: int = 0, is_50_questions: bool = False) -> str:
    """발문(문제 제목)과 문항 번호를 기반으로 20대 문제 유형 자동 판별 (50문항 체제 지원)"""
    t = title.strip()

    # 복합 장문 우선 판별
    if is_50_questions:
        if q_num in (46, 47, 48) or "46~48" in t or "46-48" in t or "46～48" in t:
            return "1지문3문항"
        if q_num in (49, 50) or "49~50" in t or "49-50" in t or "49～50" in t:
            return "1지문2문항"
        # 50문항 체제에서는 41~45번이 단일 문항이므로 아래 개별 유형 매칭으로 진행
    else:
        if q_num in (41, 42) or "41~42" in t or "41-42" in t or "41～42" in t:
            return "1지문2문항"
        if q_num in (43, 44, 45) or "43~45" in t or "43-45" in t or "43～45" in t:
            return "1지문3문항"

    if "목적" in t:
        return "글의목적"
    if "심경" in t or "분위기" in t:
        return "심경변화"
    if "주장" in t:
        return "주장"
    if "함축" in t or "밑줄 친 부분" in t or "의미하는 바" in t or "밑줄 친" in t:
        return "어휘함축"
    if "요지" in t:
        return "글의요지"
    if "주제" in t:
        return "글의주제"
    if "제목" in t:
        return "글의제목"
    if "도표" in t or "그래프" in t:
        return "도표"
    if "실용문" in t or "안내문" in t or "광고" in t:
        if "일치하지 않는" in t:
            return "실용문불일치"
        if "일치하는" in t:
            return "실용문일치"
    if "일치하지 않는" in t:
        return "불일치"
    if "일치하는" in t:
        return "불일치"
    if "어법" in t or "문법" in t:
        return "어법"
    if "문맥상 낱말" in t or "어휘" in t or "쓰임이 적절하지" in t or "낱말의 쓰임" in t:
        return "어휘"
    if "빈칸" in t:
        return "빈칸"
    if "관계 없는 문장" in t or "관계없는 문장" in t or "흐름과 관계" in t:
        return "문장빼기"
    if "이어질 글의 순서" in t or "순서로 가장" in t or "글의 순서" in t:
        return "글의순서"
    if "문장이 들어가기에" in t or "위치로 가장" in t:
        return "문장넣기"
    if "요약" in t:
        return "글의요약"

    return "기타"


def split_questions_and_explanations(full_text: str) -> Tuple[str, str]:
    """
    한 개의 HWP 문서 안에서 [문제지 영역]과 [정답 및 해설 영역] 분리
    1. 명시적 정답/해설 헤더 탐색
    2. [출제의도] 태그 시작 위치 탐색
    3. 40~45번 문항 이후 1번으로 번호 리셋되는 지점 탐색
    """
    if not full_text:
        return "", ""

    # 1. 명시적 정답/해설 헤더 탐색 (앞에 연도/과목명 등이 붙은 경우 포함: 예: '2026학년도 영어영역 정답 및 해설')
    pattern1 = re.compile(
        r"(?:^|\n)\s*(?:\[|\b)?(?:[^\n]{0,35})?(?:정답\s*(?:및|과)?\s*해설|정답표|정답\s*및\s*풀이|해설\s*및\s*정답|해설편|정답편)(?:\s*\])?",
        re.IGNORECASE
    )
    m1 = pattern1.search(full_text)
    if m1:
        return full_text[:m1.start()].strip(), full_text[m1.start():].strip()

    # 2. [출제의도] 또는 [해설] 태그 시작 위치 탐색 (예: 1. [출제의도] 또는 [출제의도])
    pattern2 = re.compile(
        r"(?:^|\n)\s*(?:0?1\s*[\.\s\t]\s*)?\[\s*(?:출제의도|출제\s*의도|해설)\s*\]",
        re.IGNORECASE
    )
    m2 = pattern2.search(full_text)
    if m2:
        return full_text[:m2.start()].strip(), full_text[m2.start():].strip()

    # 3. 40~45번 문항이 나타난 이후에 다시 1번(01.)으로 번호가 리셋되는 지점 탐색
    m_40s = list(re.finditer(r"(?:^|\n)\s*(?:4[0-5])\s*\.", full_text))
    if m_40s:
        last_40_end = m_40s[-1].end()
        m_reset = re.search(r"(?:^|\n)\s*0?1\s*\.", full_text[last_40_end:])
        if m_reset:
            split_pos = last_40_end + m_reset.start()
            return full_text[:split_pos], full_text[split_pos:]

    return full_text, full_text


def parse_hwp_questions(
    hwp_path: str,
    grade: str = "고3",
    year: int = 2024,
    month: int = 6,
    start_q: int = 18,
    end_q: int = 45,
    reading_start: Optional[int] = None,
    reading_end: Optional[int] = None,
    answers_dict: Optional[Dict[int, str]] = None,
    **kwargs
) -> Dict[int, Dict]:
    """
    HWP 시험지에서 독해 문항별 발문, 지문, 보기 추출
    단일 HWP 파일(문제+해설 포함)에서도 문제지 영역만 분리하여 파싱
    복합 지문([41~42], [43~45]) 공유 지문 정상 매핑
    """
    if reading_start is not None:
        start_q = reading_start
    if reading_end is not None:
        end_q = reading_end

    full_text = get_hwp_text(hwp_path)
    if not full_text:
        return {}

    # 50문항 체제 여부 판별
    is_50 = (end_q >= 48) or (answers_dict and max(answers_dict.keys()) >= 48) or (2006 <= year <= 2011) or bool(re.search(r"(?:^|\n)\s*50\s*\.", full_text))
    if is_50 and reading_end is None and end_q == 45:
        end_q = 50

    # 문제지와 해설지 영역 분리
    question_text, _ = split_questions_and_explanations(full_text)

    lines = question_text.splitlines()
    q_pattern = re.compile(r"^\s*(\d{1,2})\s*\.(?:\s*(.*))?$")
    group_header_pattern = re.compile(r"^\s*\[\s*(\d{1,2})\s*[~～\-]\s*(\d{1,2})\s*\](?:\s*(.*))?")

    questions = {}
    current_q = None
    current_lines = []
    current_inherited_title = ""

    # 공유 지문 캐시: (start_q, end_q) -> 지문 텍스트
    group_passages = {}
    active_group_range = (0, 0)
    group_passage_lines = []

    for line in lines:
        line_s = line.strip()
        if not line_s:
            if current_q:
                current_lines.append("")
            elif active_group_range[0] > 0 and current_q is None:
                group_passage_lines.append("")
            continue

        # 복합 지문 헤더 감지 (예: [41~42], [43~45], [46~48], [49~50])
        grp_m = group_header_pattern.match(line_s)
        if grp_m:
            if current_q and current_lines:
                questions[current_q] = format_hwp_question(
                    current_q, current_lines, grade, year, month, current_inherited_title, group_passages, is_50_questions=is_50
                )
                current_q = None
                current_lines = []

            g_start = int(grp_m.group(1))
            g_end = int(grp_m.group(2))
            active_group_range = (g_start, g_end)
            group_passage_lines = []
            current_inherited_title = grp_m.group(3).strip() if grp_m.group(3) else ""
            continue

        # 문항 번호 감지
        qm = q_pattern.match(line_s)
        if qm:
            q_val = int(qm.group(1))
            if start_q <= q_val <= end_q:
                # 공유 지문 본문 저장
                if active_group_range[0] > 0 and group_passage_lines:
                    group_passages[active_group_range] = "\n".join(group_passage_lines).strip()
                    group_passage_lines = []

                if current_q and current_lines:
                    questions[current_q] = format_hwp_question(
                        current_q, current_lines, grade, year, month, current_inherited_title, group_passages, is_50_questions=is_50
                    )

                current_q = q_val
                current_lines = [line_s]

                # 해당 문항이 복합 지문 범위를 벗어나면 공통 발문 초기화
                if q_val < active_group_range[0] or q_val > active_group_range[1]:
                    current_inherited_title = ""
                continue

        # 복합 지문 본문 누적 (문항 번호가 시작되기 전 지문 텍스트)
        if current_q is None and active_group_range[0] > 0:
            group_passage_lines.append(line_s)
            continue

        if current_q:
            current_lines.append(line_s)

    if current_q and current_lines:
        questions[current_q] = format_hwp_question(
            current_q, current_lines, grade, year, month, current_inherited_title, group_passages, is_50_questions=is_50
        )

    return questions


def format_hwp_question(
    q_num: int,
    lines: list,
    grade: str,
    year: int,
    month: int,
    inherited_title: str = "",
    group_passages: dict = None,
    is_50_questions: bool = False
) -> dict:
    """문항 본문, 발문, 문제 유형 자동 분류"""
    raw_title = lines[0] if lines else f"{q_num}. 문항"
    if inherited_title and (len(raw_title.strip()) <= 4 or raw_title.strip().endswith(".")):
        title = inherited_title
    else:
        title = raw_title

    body_text = "\n".join(lines[1:]) if len(lines) > 1 else ""
    body = body_text

    # 복합 지문에 속한 문항의 경우 공유 지문 + 해당 문항 발문 및 선지 병합
    if group_passages:
        for (g_s, g_e), g_text in group_passages.items():
            if is_50_questions and (g_s, g_e) == (41, 42):
                continue
            if g_s <= q_num <= g_e and g_text:
                if body_text:
                    body = f"{g_text}\n\n{body_text}"
                else:
                    body = g_text
                break

    # 보기(① ~ ⑤) 앞까지의 순수 영문 지문 추출 (문장 분할 및 상호 교차 검증용)
    choice_split = re.split(r"(?:^|\n)\s*①", body, maxsplit=1)
    passage_body = choice_split[0].strip() if choice_split else body.strip()

    # TXT 지문 본문: 문항 번호, 발문, 지문 본문, 그리고 객관식 선지(①~⑤)까지 모두 포함
    full_body = body.strip()
    if full_body:
        full_passage_text = f"{title}\n\n{full_body}"
    else:
        full_passage_text = title

    passage_id = f"[{grade}-{year}년-{month:02d}월-{q_num:02d}번]"
    q_type = classify_question_type(title, q_num, is_50_questions=is_50_questions)

    return {
        "passage_id": passage_id,
        "q_num": q_num,
        "question_title": title,
        "question_type": q_type,
        "passage_body": passage_body,
        "passage_text": full_passage_text,
        "full_text": "\n".join(lines)
    }


CIRCLED_MAP = {"1": "①", "2": "②", "3": "③", "4": "④", "5": "⑤"}

def parse_hwp_explanations(hwp_path: str) -> Dict[int, Dict[str, str]]:
    """
    HWP 파일에서 문항별 정답 및 해설/해석/어휘 추출
    단일 HWP 파일에 문제와 해설이 함께 있는 경우 해설 영역을 우선 탐색
    평가원/교육청 정답표 자동 감지 및 매핑
    범위 헤더(41~42, 43~45 등) 지원 및 정답 정보 자동 매핑
    """
    full_text = get_hwp_text(hwp_path)
    if not full_text:
        return {}

    # 1. 문서 전체에서 1~45번 정답표 사전 탐색 (평가원/교육청/수능 전체 공통 지원)
    table_answers = {}
    ans_patterns = [
        re.compile(r'(?:^|\n|\s)0?(\d{1,2})\s*[\.\s\t:]\s*([①②③④⑤1-5])(?:\s|$)'),
        re.compile(r'\[0?(\d{1,2})\]\s*[\.\s\t:]\s*([①②③④⑤1-5])')
    ]
    for pat in ans_patterns:
        for tm in pat.finditer(full_text):
            try:
                t_q = int(tm.group(1))
                if 1 <= t_q <= 50 and t_q not in table_answers:
                    t_sym = tm.group(2)
                    table_answers[t_q] = CIRCLED_MAP.get(t_sym, t_sym)
            except Exception:
                pass

    _, exp_text = split_questions_and_explanations(full_text)
    # 해설 마커가 명확히 분리되었으면 exp_text 사용, 아니면 full_text 전체에서 해설 패턴 탐색
    target_text = exp_text if exp_text != full_text else full_text

    # 문항 번호 헤더 감지 패턴 (18. 또는 41~42. 등)
    header_pattern = re.compile(
        r"(?:^|\n)\s*(?:\[|\b)?(\d{1,2}(?:\s*[~～\-]\s*\d{1,2})?)(?:번|\.|\s*\])(?:\s*(?:정답|\[정답\])\s*([①②③④⑤1-5]))?"
    )

    matches = list(header_pattern.finditer(target_text))
    explanations = {}

    for i in range(len(matches)):
        m = matches[i]
        raw_q = m.group(1).replace(" ", "")
        answer = m.group(2) or ""

        start_idx = m.end()
        end_idx = matches[i + 1].start() if i + 1 < len(matches) else len(target_text)

        content = target_text[start_idx:end_idx].strip()

        # 정답 번호가 본문 안에 따로 있는 경우 추가 탐지 (대괄호 [정답], [답], 정답: 등 모두 지원)
        if not answer:
            ans_match = re.search(r"(?:\[?정답\]?|\[?답\]?)\s*[:：]?\s*([①②③④⑤1-5])", content)
            if ans_match:
                answer = ans_match.group(1)

        # 번호 범위 처리 (예: 41~42 -> 41, 42)
        range_match = re.match(r"^(\d{1,2})[~～\-](\d{1,2})$", raw_q)
        if range_match:
            s_q = int(range_match.group(1))
            e_q = int(range_match.group(2))
            for sub_q in range(s_q, e_q + 1):
                if sub_q not in explanations or len(explanations[sub_q].get("explanation", "")) < len(content):
                    explanations[sub_q] = {
                        "answer": answer,
                        "explanation": content
                    }
        else:
            try:
                q_num = int(raw_q)
                # 기존 범위 해설이 있으면 내용 병합
                if q_num in explanations and explanations[q_num].get("explanation"):
                    prev_exp = explanations[q_num]["explanation"]
                    if content not in prev_exp:
                        content = f"{prev_exp}\n\n{content}"
                explanations[q_num] = {
                    "answer": answer or explanations.get(q_num, {}).get("answer", ""),
                    "explanation": content
                }
            except ValueError:
                pass

    # 정답 정보 표준화 및 해설 상단에 [정답] 라벨 명시
    for q_num, exp_info in explanations.items():
        ans = exp_info.get("answer") or table_answers.get(q_num, "")
        if ans in CIRCLED_MAP:
            ans = CIRCLED_MAP[ans]
        exp_info["answer"] = ans

        exp_body = exp_info.get("explanation", "").strip()
        if ans:
            # 해설 본문 맨 앞의 [정답] 표기 표준화 (없으면 추가, 있으면 갱신)
            if not re.search(r"^\s*\[\s*정답\s*\]", exp_body):
                exp_info["explanation"] = f"[정답] {ans}\n\n{exp_body}".strip()
            else:
                exp_info["explanation"] = re.sub(r"^\s*\[\s*정답\s*\]\s*[①②③④⑤1-5]?", f"[정답] {ans}", exp_body)

    return explanations


ANSWER_IMAGE_EXPECTED_QUESTIONS = 45

_ANSWER_IMAGE_PROMPT = (
    "첨부된 대한민국 수능/모의고사 영어 영역 정답표 이미지입니다.\n"
    "표 안의 1번부터 45번까지의 모든 문항 번호와 정답 번호를 정확히 판독하여 JSON으로 추출해 주세요.\n"
    "반환 형식 예시: {\"1\": \"①\", \"2\": \"③\", \"3\": \"⑤\", ... \"45\": \"③\"}\n"
    "규칙:\n"
    "1. 각 셀에 인쇄된 문항 번호를 직접 읽어 짝을 맞추고, 위치로 추정하지 마십시오.\n"
    "2. 1번부터 45번까지 누락된 문항 없이 반드시 모두 포함하십시오.\n"
    "3. 정답 기호는 ①, ②, ③, ④, ⑤ 원문자 또는 1, 2, 3, 4, 5 숫자로 명확히 기재하십시오.\n"
    "4. 마크다운이나 설명 없이 오직 유효한 JSON 객체만 단독으로 반환하십시오."
)


def _vision_request(provider: str, api_key: str, model: str, b64_data: str, mime_type: str) -> str:
    """단일 Vision 모델 호출 후 원시 응답 텍스트 반환"""
    import json
    import urllib.request

    if provider == "gemini":
        use_model = model or "gemini-2.5-flash"
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{use_model}:generateContent?key={api_key}"
        payload = {
            "contents": [{"parts": [
                {"text": _ANSWER_IMAGE_PROMPT},
                {"inlineData": {"mimeType": mime_type, "data": b64_data}}
            ]}],
            "generationConfig": {"response_mime_type": "application/json", "temperature": 0.0}
        }
        headers = {"Content-Type": "application/json"}
        extract = lambda d: d["candidates"][0]["content"]["parts"][0]["text"]
    elif provider in ("openai", "openrouter"):
        if provider == "openai":
            url, use_model = "https://api.openai.com/v1/chat/completions", (model or "gpt-4o-mini")
        else:
            url, use_model = "https://openrouter.ai/api/v1/chat/completions", (model or "anthropic/claude-sonnet-4.5")
        payload = {
            "model": use_model,
            "messages": [{"role": "user", "content": [
                {"type": "text", "text": _ANSWER_IMAGE_PROMPT},
                {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{b64_data}"}}
            ]}],
            "temperature": 0.0
        }
        if provider == "openai":
            payload["response_format"] = {"type": "json_object"}
        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}
        extract = lambda d: d["choices"][0]["message"]["content"]
    elif provider == "claude":
        url = "https://api.anthropic.com/v1/messages"
        payload = {
            "model": model or "claude-sonnet-5",
            "max_tokens": 4096,  # thinking 토큰이 포함되므로 여유 확보
            # 현행 Claude 모델(Opus 5/Sonnet 5 등)은 temperature 파라미터를 거부(400)하므로 보내지 않음
            "messages": [{"role": "user", "content": [
                {"type": "image", "source": {"type": "base64", "media_type": mime_type, "data": b64_data}},
                {"type": "text", "text": _ANSWER_IMAGE_PROMPT}
            ]}]
        }
        headers = {"Content-Type": "application/json", "x-api-key": api_key, "anthropic-version": "2023-06-01"}
        extract = lambda d: "".join(block.get("text", "") for block in d.get("content", []))
    else:
        raise ValueError(f"Vision 판독 미지원 provider: {provider}")

    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=45) as resp:
        return extract(json.loads(resp.read().decode("utf-8")))


def _parse_answer_json(raw_json_str: str) -> Dict[int, str]:
    """모델 응답 텍스트를 {문항번호: 원문자} 로 정규화"""
    import json

    clean_str = re.sub(r"^```(?:json)?\s*", "", raw_json_str.strip())
    clean_str = re.sub(r"\s*```$", "", clean_str).strip()
    data = json.loads(clean_str)
    if isinstance(data, dict) and not any(str(k).isdigit() for k in data.keys()):
        for v in data.values():
            if isinstance(v, dict) and any(str(sub_k).isdigit() for sub_k in v.keys()):
                data = v
                break
    result: Dict[int, str] = {}
    for k, v in data.items():
        digits = re.sub(r"[^\d]", "", str(k))
        if not digits:
            continue
        q = int(digits)
        norm = CIRCLED_MAP.get(str(v).strip(), str(v).strip())
        if 1 <= q <= ANSWER_IMAGE_EXPECTED_QUESTIONS and norm in CIRCLED_MAP.values():
            result[q] = norm
    return result


def read_answer_image(image_path: str) -> Dict[str, Any]:
    """
    정답표 이미지를 활성화된 모든 Vision 모델로 독립 판독하고 합의 결과를 반환.
    - 45문항이 모두 추출된 판독만 유효로 인정한다.
    - 유효 판독 중 과반(2개 이상)이 일치한 문항만 consensus 에 포함하고, 소수 의견은 dissent 에 남긴다.
    반환: {
        status: 'ok' | 'partial' | 'single_reader' | 'failed',
        readings: {모델라벨: {q: 원문자}}, consensus: {q: 원문자}, disputed: {q: {모델라벨: 원문자}},
        errors: [str], reader_count: int
    }
    """
    import base64
    import grammar_analyzer

    result: Dict[str, Any] = {"status": "failed", "readings": {}, "consensus": {}, "disputed": {}, "dissent": {}, "errors": [], "reader_count": 0}
    if not image_path or not os.path.exists(image_path):
        result["errors"].append("이미지 파일 없음")
        return result

    # 원문자(③/④/⑤) 혼동을 줄이기 위해 폭 1200px 미만 이미지는 2배 확대한 PNG로 전송
    try:
        img_bytes = None
        try:
            import pymupdf
            page = pymupdf.open(image_path)[0]
            if page.rect.width < 1200:
                img_bytes = page.get_pixmap(matrix=pymupdf.Matrix(2, 2)).tobytes("png")
        except Exception:
            img_bytes = None
        if img_bytes is None:
            with open(image_path, "rb") as f:
                img_bytes = f.read()
            mime_type = "image/jpeg" if image_path.lower().endswith((".jpg", ".jpeg")) else "image/png"
        else:
            mime_type = "image/png"
        b64_data = base64.b64encode(img_bytes).decode("utf-8")
    except Exception as e:
        result["errors"].append(f"이미지 읽기 실패: {e}")
        return result

    configs = [c for c in grammar_analyzer.get_active_ai_configs() if c.get("api_key")]
    if not configs:
        result["errors"].append("유효한 AI API Key가 설정되지 않음 (AI 설정에서 2개 이상 모델 활성화 필요)")
        return result

    for cfg in configs:
        label = cfg.get("label") or cfg.get("provider")
        try:
            raw = _vision_request(cfg["provider"], cfg["api_key"], cfg.get("model", ""), b64_data, mime_type)
            reading = _parse_answer_json(raw)
        except Exception as e:
            result["errors"].append(f"{label}: 호출/파싱 실패 ({e})")
            continue
        if len(reading) < ANSWER_IMAGE_EXPECTED_QUESTIONS:
            result["errors"].append(f"{label}: {len(reading)}/{ANSWER_IMAGE_EXPECTED_QUESTIONS}문항만 추출되어 판독 무효")
            continue
        result["readings"][label] = reading

    readings = result["readings"]
    result["reader_count"] = len(readings)
    if not readings:
        return result
    if len(readings) == 1:
        result["status"] = "single_reader"
        return result

    # 과반(2개 이상이며 나머지보다 많은) 판독을 합의로 인정, 소수 의견은 dissent 에 기록
    from collections import Counter
    n_readers = len(readings)
    for q in range(1, ANSWER_IMAGE_EXPECTED_QUESTIONS + 1):
        values = {label: r.get(q) for label, r in readings.items()}
        votes = Counter(v for v in values.values() if v)
        top, cnt = votes.most_common(1)[0] if votes else (None, 0)
        if top and cnt >= 2 and cnt > n_readers - cnt:
            result["consensus"][q] = top
            if cnt < n_readers:
                result["dissent"][q] = {label: v for label, v in values.items() if v != top}
        else:
            result["disputed"][q] = values
    result["status"] = "ok" if not result["disputed"] else "partial"
    print(f"[read_answer_image] {n_readers}개 모델 판독, 합의 {len(result['consensus'])}문항 (소수의견 {len(result['dissent'])}), 불일치 {len(result['disputed'])}문항")
    return result
