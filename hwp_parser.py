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
from typing import Dict, Optional, Tuple


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


def extract_hwp_text_pyhwpx(file_path: str) -> str:
    """pyhwpx를 사용하여 HWP 텍스트 추출 (백그라운드 OLE)"""
    try:
        from pyhwpx import Hwp
        hwp = Hwp(new=True, visible=False)
        try:
            hwp.Open(os.path.abspath(file_path))
            text = hwp.GetTextFile("TEXT")
            return sanitize_text(text)
        finally:
            hwp.Quit()
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


def parse_hwp_questions(
    hwp_path: str,
    grade: str = "고3",
    year: int = 2024,
    month: int = 6,
    start_q: int = 18,
    end_q: int = 45
) -> Dict[int, Dict]:
    """
    HWP 시험지에서 독해 문항별 발문, 지문, 보기 추출
    """
    full_text = get_hwp_text(hwp_path)
    if not full_text:
        return {}

    lines = full_text.splitlines()
    q_pattern = re.compile(r"^\s*(\d{1,2})\s*\.\s*(.+)")

    questions = {}
    current_q = None
    current_lines = []

    for line in lines:
        line_s = line.strip()
        if not line_s:
            continue

        match = q_pattern.match(line_s)
        if match:
            q_num = int(match.group(1))
            if start_q <= q_num <= end_q:
                if current_q and current_lines:
                    questions[current_q] = format_hwp_question(
                        current_q, current_lines, grade, year, month
                    )
                current_q = q_num
                current_lines = [line_s]
                continue

        if current_q:
            current_lines.append(line_s)

    if current_q and current_lines:
        questions[current_q] = format_hwp_question(
            current_q, current_lines, grade, year, month
        )

    return questions


def format_hwp_question(
    q_num: int,
    lines: list,
    grade: str,
    year: int,
    month: int
) -> dict:
    """문항 본문과 발문 정리"""
    title = lines[0] if lines else f"{q_num}. 문항"
    body = "\n".join(lines[1:]) if len(lines) > 1 else ""

    # 보기(① ~ ⑤) 앞까지의 영문 지문 추출
    choice_split = re.split(r"(?:^|\n)\s*①", body, maxsplit=1)
    passage_text = choice_split[0].strip() if choice_split else body.strip()

    passage_id = f"[{grade}-{year}년-{month:02d}월-{q_num:02d}번]"

    return {
        "passage_id": passage_id,
        "q_num": q_num,
        "question_title": title,
        "passage_text": passage_text,
        "full_text": "\n".join(lines)
    }


def parse_hwp_explanations(hwp_path: str) -> Dict[int, Dict[str, str]]:
    """
    해설지 HWP 파일에서 문항별 정답 및 해설/해석/어휘 추출
    지원 패턴:
    - [21번] 또는 21. [정답] ③ [해설] ...
    - [문항 21] ...
    """
    full_text = get_hwp_text(hwp_path)
    if not full_text:
        return {}

    # 문항 번호 헤더 감지 패턴
    # 예: "21. 정답 ③", "[21]", "21번", "[21번]"
    header_pattern = re.compile(
        r"(?:^|\n)\s*(?:\[|\b)(\d{1,2})(?:번|\.|\s*\])(?:\s*(?:정답|\[정답\])\s*([①②③④⑤1-5]))?"
    )

    matches = list(header_pattern.finditer(full_text))
    explanations = {}

    for i in range(len(matches)):
        m = matches[i]
        q_num = int(m.group(1))
        answer = m.group(2) or ""

        start_idx = m.end()
        end_idx = matches[i + 1].start() if i + 1 < len(matches) else len(full_text)

        content = full_text[start_idx:end_idx].strip()

        # 정답 번호가 본문 안에 따로 있는 경우 추가 탐지
        if not answer:
            ans_match = re.search(r"(?:정답|답)\s*[:：]?\s*([①②③④⑤1-5])", content)
            if ans_match:
                answer = ans_match.group(1)

        explanations[q_num] = {
            "answer": answer,
            "explanation": content
        }

    return explanations
