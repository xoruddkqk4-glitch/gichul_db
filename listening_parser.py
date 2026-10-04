"""
05-gichul_db: 영어 듣기 문항 및 대본 추출·크롭 파서 (listening_parser.py)

기능:
1. 문제지 PDF에서 듣기 문항(1~17번) 영역 기하학적 2단 분석 및 고화질 크롭 이미지 생성
2. 해설지(HWP/PDF) 및 대본집에서 순수 영문 대본(M:, W: 화자 턴) 지능형 텍스트 추출
3. 별도 대본 PDF 또는 해설 PDF 내 [대본] 섹션 자동 감지 및 스크립트 이미지 정밀 크롭 (_script.png)
4. FELS 엔진 및 ElevenLabs TTS 입력용 정제된 영문 스크립트 데이터 제공
"""

import os
import re
import glob
from typing import Dict, Any, List, Optional, Tuple
import pymupdf as fitz
from PIL import Image

import pdf_parser
import fels_engine
import database as db
import hwp_parser
import answer_keys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CAPTURES_DIR = os.path.join(BASE_DIR, "static", "captures")
os.makedirs(CAPTURES_DIR, exist_ok=True)

# 12대 듣기 문제 유형 정의 (+ 기타)
LISTENING_QUESTION_TYPES = [
    "화자의 목적/의견/요지",
    "그림 불일치",
    "화자의 할일",
    "금액",
    "이유",
    "언급되지 않은 것",
    "불일치",
    "도표 불일치",
    "짧은 응답",
    "긴 응답",
    "할 말",
    "1담화 2문항",
    "기타"
]


def classify_listening_question_type(title: str, q_num: int = 0) -> str:
    """듣기 문항의 발문(title)과 문항 번호(q_num)에 따라 12대 듣기 문제유형 + 기타 분류"""
    t = (title or "").strip()

    # 1. 그림 불일치 (4번 또는 그림 키워드)
    if "그림" in t and ("일치하지" in t or "불일치" in t or q_num == 4):
        return "그림 불일치"

    # 2. 도표 불일치 (10번 또는 표 키워드)
    if ("표를" in t or "도표" in t) or (q_num == 10 and "표" in t):
        return "도표 불일치"

    # 3. 화자의 할일 (5번)
    if "할 일" in t or "할일" in t:
        return "화자의 할일"

    # 4. 금액 (6번)
    if "금액" in t or "지불" in t:
        return "금액"

    # 5. 이유 (7번)
    if "이유" in t:
        return "이유"

    # 6. 언급되지 않은 것 (8번)
    if "언급되지 않은" in t or "언급하지 않은" in t or "언급되지않은" in t:
        return "언급되지 않은 것"

    # 7. 화자의 목적/의견/요지 (1, 2, 3번)
    if any(k in t for k in ["목적", "의견", "요지"]):
        return "화자의 목적/의견/요지"

    # 8. 상황 설명 -> 할 말 (15번)
    if "할 말" in t or "할말" in t or "상황 설명" in t:
        return "할 말"

    # 9. 응답 (11, 12, 13, 14번)
    if "응답" in t:
        if q_num in (11, 12) or "짧은" in t:
            return "짧은 응답"
        elif q_num in (13, 14) or "긴" in t:
            return "긴 응답"

    # 10. 1담화 2문항 (16, 17번 및 22, 23번, 21~22번 등)
    if q_num in (16, 17, 21, 22, 23) or any(k in t for k in ["16번", "17번", "22번", "23번", "16~17", "22~23", "21~22", "1담화"]):
        return "1담화 2문항"

    # 11. 불일치 (9번)
    if "일치하지 않는" in t or "일치하지않는" in t or "불일치" in t:
        return "불일치"

    # 문항 번호 기반 안전 폴백
    if q_num in (1, 2, 3):
        return "화자의 목적/의견/요지"
    elif q_num == 4:
        return "그림 불일치"
    elif q_num == 5:
        return "화자의 할일"
    elif q_num == 6:
        return "금액"
    elif q_num == 7:
        return "이유"
    elif q_num == 8:
        return "언급되지 않은 것"
    elif q_num == 9:
        return "불일치"
    elif q_num == 10:
        return "도표 불일치"
    elif q_num in (11, 12):
        return "짧은 응답"
    elif q_num in (13, 14):
        return "긴 응답"
    elif q_num == 15:
        return "할 말"
    elif q_num in (16, 17, 21, 22, 23):
        return "1담화 2문항"

    return "기타"


def clean_script_text(text: str) -> str:
    """영문 대본 텍스트 유니코드 및 문장부호 정제 (한국어 해석/어휘/화자 라인 완전 배제)"""
    if not text:
        return ""
    # 유니코드 따옴표 표준화
    t = text.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    # 서로게이트 및 널 문자 제거
    t = re.sub(r"[\ud800-\udfff\x00]", "", t)
    # 한 줄에 여러 화자(W: ... M: ...)가 뭉쳐있는 경우 줄바꿈 분리
    t = re.sub(r"(\s+)([MW]|Man|Woman|Girl|Boy|Teacher|Student)\s*[:：]\s*", r"\n\2: ", t)
    # 다중 공백 정리 및 비문장 어휘/해설 라인 엄격 필터링
    lines = [l.strip() for l in t.splitlines() if l.strip()]
    clean_lines = []
    dialogue_started = False

    for line in lines:
        # 한국어 해석/풀이/어휘 종료 헤더 감지 시 즉시 중단
        if any(h in line for h in ("[해석]", "【해석】", "[풀이]", "【풀이】", "[정답]", "【정답】", "[어휘]", "【어휘】", "[Words", "Words & Phrases", "Words and Phrases")):
            break
        # 한글 화자 태그(남:, 여:, 선생님:, 학생: 등) 시작 시 우리말 해석 블록이므로 즉시 중단
        if re.match(r"^\s*(?:남|여|남학생|여학생|선생님|학생|아버지|어머니|엄마|아빠)\s*[:：]", line):
            break
        # 한국어 문자가 포함된 라인(우리말 해석, 어휘 설명 등)은 영문 대본에서 완전 제외
        if re.search(r"[\uac00-\ud7a3]", line):
            continue

        is_speaker = bool(re.match(r"^(?:[MW]|Man|Woman|Girl|Boy|Teacher|Student|Clerk|Host|Doctor|Officer)\s*[:：]", line, re.IGNORECASE))
        if is_speaker:
            dialogue_started = True

        # 대화 시작 후, 화자 태그 없고 구두점(. ? !)으로 끝나지 않으며 단어수가 적은 어휘 라인 제외
        if dialogue_started and not is_speaker:
            if not re.search(r"[\.\?\!\"\'\)]$", line):
                words = line.split()
                if len(words) <= 5:
                    continue

        clean_lines.append(line)

    return "\n".join(clean_lines)


def extract_script_text_from_explanation(explanation_text: str) -> str:
    """
    HWP 또는 PDF 해설 텍스트에서 순수 영문 대본(Script) 블록만 지능적으로 추출
    - [대본] / Script 헤더 또는 M:, W: 시작점부터 [해석], [해설], [풀이], [어휘] 직전까지 추출
    - 우리말 해석(남: ... 여: ...)은 완전히 배제하고 오직 순수 영문 스크립트만 반환
    """
    if not explanation_text:
        return ""

    exp = explanation_text.strip()

    # 1. 명시적 [대본] 또는 【대본】 헤더 탐색
    m_script_hdr = re.search(r"(?:\[\s*대본\s*\]|【\s*대본\s*】|\[\s*듣기\s*대본\s*\]|Script\b|\[Script\])", exp, re.IGNORECASE)
    if m_script_hdr:
        after_hdr = exp[m_script_hdr.end():]
        # 종료 헤더: [해석], [해설], [풀이], [정답], [어휘], [출제의도] 또는 개행 후 남:/여:
        m_end = re.search(r"(?:\[\s*해석\s*\]|【\s*해석\s*】|\[\s*해설\s*\]|【\s*해설\s*】|\[\s*풀이\s*\]|【\s*풀이\s*\]|\[\s*어휘\s*\]|【\s*어휘\s*】|\[\s*정답\s*\]|(?:\n|\r\n?)\s*(?:남|여)\s*[:：])", after_hdr)
        if m_end:
            script_raw = after_hdr[:m_end.start()]
        else:
            script_raw = after_hdr
        return clean_script_text(script_raw)

    # 2. 헤더 없이 M:, W: 화자 태그로 바로 시작하는 경우
    lines = exp.splitlines()
    script_lines = []
    recording = False

    for line in lines:
        line_s = line.strip()
        if not line_s:
            continue

        # 종료 조건 헤더 감지
        if any(h in line_s for h in ("[해석]", "[해설]", "[풀이]", "[어휘]", "[정답]", "【해석】", "【해설】", "【풀이】", "【어휘】")):
            if recording:
                break
            continue
        if re.match(r"^\s*(?:남|여|남학생|여학생|선생님|학생)\s*[:：]", line_s):
            if recording:
                break
            continue

        # 화자 태그 감지 시작
        if re.match(r"^(?:[MW]|Man|Woman|Girl|Boy|Teacher|Student|Clerk|Host)\s*[:：]", line_s, re.IGNORECASE):
            recording = True

        if recording:
            script_lines.append(line_s)

    if script_lines:
        return clean_script_text("\n".join(script_lines))

    # 3. 화자 태그 없는 단독 담화문인 경우: 영문 비율이 높은 줄들을 필터링
    eng_lines = []
    for l in lines:
        l_s = l.strip()
        if not l_s:
            continue
        if any(h in l_s for h in ("[의도]", "[출제의도]", "[해석]", "[해설]", "[풀이]", "[어휘]", "[정답]")):
            continue
        if re.match(r"^\s*(?:남|여)\s*[:：]", l_s):
            break
        # 영문 알파벳 비율이 60% 이상인 줄
        eng_chars = len(re.findall(r"[A-Za-z]", l_s))
        if eng_chars >= 15 and (eng_chars / len(l_s)) > 0.5:
            eng_lines.append(l_s)

    return clean_script_text("\n".join(eng_lines))


def extract_listening_question_crops(
    pdf_path: str,
    grade: str = "고3",
    year: int = 2024,
    month: int = 6,
    listening_start_q: int = 1,
    listening_end_q: int = 17,
    answers_dict: Optional[Dict[int, str]] = None,
    subtype: Optional[str] = None
) -> Dict[int, Dict[str, Any]]:
    """
    문제지 PDF의 1~2페이지에서 듣기 문항(1~17번) 크롭 이미지 및 메타데이터 추출
    """
    if not os.path.exists(pdf_path):
        return {}

    questions = pdf_parser.extract_pdf_columns_and_questions(
        pdf_path=pdf_path,
        grade=grade,
        year=year,
        month=month,
        reading_start=listening_start_q,
        reading_end=listening_end_q,
        start_q=listening_start_q,
        end_q=listening_end_q,
        answers_dict=answers_dict,
        subtype=subtype
    )

    # 듣기 문항 범위(1~17번)만 엄격 필터링
    listening_questions = {
        q: data for q, data in questions.items()
        if listening_start_q <= q <= listening_end_q
    }

    return listening_questions


def extract_listening_script_crops(
    script_or_exp_pdf_path: str,
    grade: str = "고3",
    year: int = 2024,
    month: int = 6,
    is_explanation_pdf: bool = False,
    listening_start_q: int = 1,
    listening_end_q: int = 17,
    subtype: Optional[str] = None
) -> Dict[int, str]:
    """
    대본 PDF 또는 해설 PDF에서 각 듣기 문항의 대본(Script) 인쇄 영역을
    1단/2단 레이아웃 자동 판별 및 벡터 테두리선(Drawings) 감지를 통해 온전하게 200 DPI로 크롭
    
    반환: {1: "/static/captures/..._01_script.png", 2: ...}
    """
    if not os.path.exists(script_or_exp_pdf_path):
        return {}

    doc = fitz.open(script_or_exp_pdf_path)
    result_crops = {}

    single_q_pattern = re.compile(r"^\s*(\d{1,2})\s*\.(?:\s*(.*))?$")
    set_q_pattern = re.compile(r"\[\s*(\d{1,2})\s*[-~～]\s*(\d{1,2})\s*\]")
    script_header_pattern = re.compile(r"(?:\[\s*대본\s*\]|【\s*대본\s*】|Script\b|\[Script\])", re.IGNORECASE)
    end_header_pattern = re.compile(r"(?:\[\s*해석\s*\]|【\s*해석\s*】|\[\s*해설\s*\]|【\s*해설\s*】|\[\s*어휘\s*\]|【\s*어휘\s*】)", re.IGNORECASE)

    # 해설 PDF의 경우 대본은 보통 앞쪽 1~8페이지 내에 위치
    max_scan_pages = min(len(doc), 8 if is_explanation_pdf else len(doc))

    for page_num in range(max_scan_pages):
        page = doc[page_num]
        rect = page.rect
        width, height = rect.width, rect.height
        mid_x = width / 2.0

        # 페이지 내 텍스트 블록으로 1단(Single column) vs 2단(Two columns) 레이아웃 자동 판별
        raw_page_blocks = page.get_text("blocks")
        content_page_blocks = [
            b for b in raw_page_blocks
            if len(b[4].strip()) >= 8 and b[1] > 35 and b[3] < height - 40
        ]

        spanning_blocks = [
            b for b in content_page_blocks
            if b[0] < mid_x - 30 and b[2] > mid_x + 30
        ]

        # 우측 칼럼 영역(mid_x + 20 이상)에 유의미한 블록이 2개 미만이면 무조건 1단(Single Column)
        right_blocks = [b for b in content_page_blocks if b[0] > mid_x + 20]

        is_single_column = (len(right_blocks) < 2) or (len(spanning_blocks) >= 2) or (
            len(content_page_blocks) > 0 and (len(spanning_blocks) / len(content_page_blocks)) >= 0.20
        )

        if is_single_column:
            col_clips = [fitz.Rect(15, 35, width - 15, height - 45)]
        else:
            left_clip = fitz.Rect(15, 35, mid_x - 5, height - 35)
            right_clip = fitz.Rect(mid_x + 5, 35, width - 15, height - 35)
            col_clips = [left_clip, right_clip]

        for col_clip in col_clips:
            raw_blocks = page.get_text("blocks", clip=col_clip)
            blocks = sorted(raw_blocks, key=lambda b: (b[1], b[0]))

            current_qs = []
            script_recording = False
            script_rects = []

            for b in blocks:
                b_rect = fitz.Rect(b[0], b[1], b[2], b[3])
                b_text = b[4].strip()
                if not b_text:
                    continue

                # 하단 푸터 및 페이지 번호 제외
                if b[1] > height - 60 and len(b_text) <= 5:
                    continue

                # 방송 안내 / 시그널 블록 제외
                if any(k in b_text for k in ["ANN:", "Signal", "시그널", "안내방송", "듣기평가 안내"]):
                    continue

                # (10 seconds) 등 단순 대기 시간 블록 제외
                if re.match(r"^\(\s*\d+\s*seconds?\s*\)$", b_text, re.IGNORECASE):
                    continue

                lines = [l.strip() for l in b_text.splitlines() if l.strip()]
                first_line = lines[0] if lines else ""

                # 세트 문항 확인 (예: [16 ~ 17])
                sm = set_q_pattern.search(b_text)
                
                # 단일 문항 번호 감지 (다양한 대본 PDF 포맷 대응)
                cand_q = None
                for idx, l in enumerate(lines[:4]):
                    # 1. "1.", "1. 대화를...", "1번", "1번 대화를..."
                    m = re.match(r"^(\d{1,2})\s*[\.번](?:\s.*)?$", l)
                    if m:
                        cq = int(m.group(1))
                        if listening_start_q <= cq <= listening_end_q:
                            cand_q = cq
                            break
                    # 2. "번 1" 또는 "번1"
                    m = re.match(r"^번\s*(\d{1,2})(?:\s.*)?$", l)
                    if m:
                        cq = int(m.group(1))
                        if listening_start_q <= cq <= listening_end_q:
                            cand_q = cq
                            break
                    # 3. 줄바꿈 분리형: 이번 줄이 "번", 다음 줄이 "1"
                    if l == "번" and idx + 1 < len(lines):
                        m = re.match(r"^(\d{1,2})(?:\s.*)?$", lines[idx + 1])
                        if m:
                            cq = int(m.group(1))
                            if listening_start_q <= cq <= listening_end_q:
                                cand_q = cq
                                break
                    # 4. 숫자만 단독으로 있는 줄
                    m = re.match(r"^(\d{1,2})$", l)
                    if m:
                        cq = int(m.group(1))
                        if listening_start_q <= cq <= listening_end_q:
                            cand_q = cq
                            break

                if not cand_q:
                    m = re.search(r'(?:^|\n)\s*(\d{1,2})\s*[\.번]', b_text)
                    if m:
                        cq = int(m.group(1))
                        if listening_start_q <= cq <= listening_end_q:
                            cand_q = cq

                qm = cand_q

                if sm:
                    start_s = int(sm.group(1))
                    end_s = int(sm.group(2))
                    if listening_start_q <= start_s <= listening_end_q:
                        if current_qs and script_rects:
                            _save_script_crop(doc, page_num, current_qs, script_rects, grade, year, month, result_crops, col_clip, subtype=subtype)
                            script_rects = []

                        current_qs = list(range(start_s, min(end_s, listening_end_q) + 1))
                        script_recording = not is_explanation_pdf
                        if script_recording:
                            script_rects.append(b_rect)
                        continue
                elif qm:
                    q_num = qm
                    if listening_start_q <= q_num <= listening_end_q:
                        if current_qs and script_rects:
                            _save_script_crop(doc, page_num, current_qs, script_rects, grade, year, month, result_crops, col_clip, subtype=subtype)
                            script_rects = []

                        current_qs = [q_num]
                        script_recording = not is_explanation_pdf
                        if script_recording:
                            script_rects.append(b_rect)
                        continue

                if current_qs:
                    if is_explanation_pdf:
                        if script_header_pattern.search(b_text):
                            script_recording = True
                            script_rects.append(b_rect)
                            continue
                        elif end_header_pattern.search(b_text):
                            script_recording = False
                            _save_script_crop(doc, page_num, current_qs, script_rects, grade, year, month, result_crops, col_clip, subtype=subtype)
                            script_rects = []
                            current_qs = []
                            continue

                    if script_recording:
                        # 페이지 하단 쪽번호(예: '4/17', '1 / 17') 또는 페이지 최하단 45pt 이내 쪽번호 배제
                        b_strip = b_text.strip()
                        if re.search(r'^\s*\d+\s*/\s*\d+\s*$', b_strip):
                            continue
                        if page.rect.height - b_rect.y1 < 45 and (re.search(r'^\s*\d+\s*$', b_strip) or re.search(r'\d+/\d+', b_strip)):
                            continue
                        script_rects.append(b_rect)

            if current_qs and script_rects:
                _save_script_crop(doc, page_num, current_qs, script_rects, grade, year, month, result_crops, col_clip, subtype=subtype)

    doc.close()
    return result_crops


def _save_script_crop(
    doc: fitz.Document,
    page_num: int,
    q_nums: List[int],
    rects: List[fitz.Rect],
    grade: str,
    year: int,
    month: int,
    out_dict: Dict[int, str],
    col_clip: Optional[fitz.Rect] = None,
    subtype: Optional[str] = None
):
    """지정된 문항들의 대본 영역 Bounding Box를 200 DPI로 캡처하여 저장 (테두리 상자선 벡터 감지 포함)"""
    if not rects or not q_nums:
        return

    # 이미 처리된 문항들만 있으면 스킵
    target_qs = [q for q in q_nums if q not in out_dict]
    if not target_qs:
        return

    page = doc[page_num]
    w, h = page.rect.width, page.rect.height

    # Y좌표 기준 정렬 및 인접 블록 간 80pt 초과 거대 갭 발생 시 하단 잔여물(쪽번호 등) 분리
    rects_sorted = sorted(rects, key=lambda r: r.y0)
    filtered_rects = []
    for idx, r in enumerate(rects_sorted):
        if idx > 0 and (r.y0 - filtered_rects[-1].y1) > 80:
            break
        filtered_rects.append(r)
    rects = filtered_rects or rects_sorted

    min_x = min(r.x0 for r in rects)
    min_y = min(r.y0 for r in rects)
    max_x = max(r.x1 for r in rects)
    max_y = max(r.y1 for r in rects)

    # 대본 박스를 둘러싼 벡터 드로잉 사각형 선 감지하여 Bbox 확장
    try:
        drawings = page.get_drawings()
        for d in drawings:
            dr = d.get("rect")
            if not dr:
                continue
            # 문항 영역과 수직으로 교차하고 적절한 너비의 사각형 선
            if dr.y1 >= min_y - 12 and dr.y0 <= max_y + 12 and dr.width >= 60:
                # 2단 레이아웃인 경우 다른 칼럼을 침범하지 않도록 확인
                if col_clip is None or (dr.x0 >= col_clip.x0 - 15 and dr.x1 <= col_clip.x1 + 15):
                    min_x = min(min_x, dr.x0 - 4)
                    max_x = max(max_x, dr.x1 + 4)
                    min_y = min(min_y, dr.y0 - 4)
                    max_y = max(max_y, dr.y1 + 4)
    except Exception:
        pass

    # 여유 있는 패딩 적용 (좌우 최소 10pt, 상하 8pt)
    min_x = max(0, min_x - 10)
    min_y = max(0, min_y - 8)
    max_x = min(w, max_x + 10)
    max_y = min(h, max_y + 8)

    # 칼럼 클립이 있으면 안전하게 제한
    if col_clip:
        min_x = max(col_clip.x0, min_x)
        max_x = min(col_clip.x1, max_x)

    crop_rect = fitz.Rect(min_x, min_y, max_x, max_y)
    if crop_rect.width < 50 or crop_rect.height < 20:
        return

    pix = page.get_pixmap(clip=crop_rect, dpi=200)

    for q in target_qs:
        sub_part = f"_{subtype}" if subtype else ""
        img_filename = f"{grade}_{year}_{month:02d}{sub_part}_{q:02d}_script.png"
        img_filepath = os.path.join(CAPTURES_DIR, img_filename)
        web_url = f"/static/captures/{img_filename}"
        pix.save(img_filepath)
        out_dict[q] = web_url


def sync_exam_listening(
    exam_id: str,
    script_pdf_path: Optional[str] = None,
    is_explanation_pdf: bool = False,
    question_pdf_path: Optional[str] = None,
    explanation_hwp_path: Optional[str] = None,
    answers_dict: Optional[Dict[int, str]] = None,
    **kwargs
) -> Dict[str, Any]:
    """
    특정 시험지에 대해 듣기 문항(1~17번) 자동 파싱 및 DB 동기화:
    1. uploads/ 내 해당 시험지의 PDF(문제지)와 HWP(해설지) 탐색
    2. HWP 해설 및 answer_keys에서 1~17번 정답, 해설, 영문 대본(script_text) 추출
    3. FELS 엔진을 통해 영문 대본을 FELS 텍스트(기능어 <괄호>)로 변환
    4. PDF 문제지에서 1~17번 고화질 크롭 이미지 생성 (정답 선지 파스텔톤 노란색 형광펜 주석 연동)
    5. 대본 PDF(또는 해설 PDF)가 주어지면 스크립트 크롭 이미지(_script.png) 생성
    6. passages 테이블에 area='listening'으로 문항 정보 등록/갱신
    """
    clean_id = exam_id.strip()
    if not clean_id.startswith("["):
        clean_id = f"[{clean_id}]"

    # 필요한 DB 값(시험지 정보, 기존 듣기 정답)을 먼저 읽고 연결을 바로 닫는다
    # (예전에는 with 없이 연 연결이 파싱 내내 열려 있었음)
    db_answers = {}
    with db.get_connection() as conn:
        exam_row = conn.execute("SELECT * FROM exams WHERE id = ?", (clean_id,)).fetchone()
        if not exam_row:
            exam_row = conn.execute("SELECT * FROM exams WHERE id = ?", (clean_id.strip("[]"),)).fetchone()
        if exam_row:
            try:
                rows = conn.execute(
                    "SELECT q_num, answer_text FROM passages WHERE exam_id = ? AND area = 'listening'", (clean_id,)
                ).fetchall()
                for r in rows:
                    if r["answer_text"]:
                        db_answers[r["q_num"]] = r["answer_text"]
            except Exception:
                pass
    if not exam_row:
        raise ValueError(f"시험지를 찾을 수 없습니다: {clean_id}")

    grade = exam_row["grade"]
    year = exam_row["year"]
    month = exam_row["month"]
    subtype = exam_row["subtype"] if "subtype" in exam_row.keys() else None
    if not subtype:
        m_sub = re.search(r"-([AB]형)", clean_id)
        if m_sub:
            subtype = m_sub.group(1)
    start_q = exam_row["listening_start_q"] if "listening_start_q" in exam_row.keys() and exam_row["listening_start_q"] else 1
    end_q = exam_row["listening_end_q"] if "listening_end_q" in exam_row.keys() and exam_row["listening_end_q"] else 17

    uploads_dir = os.path.join(BASE_DIR, "uploads")
    def _is_prob_pdf(p: str) -> bool:
        pl = p.lower()
        if "_ans_" in pl or "_script" in pl or "대본" in pl or "_exp_" in pl:
            return False
        if re.search(r"[-_]A\.pdf$", p, re.I):
            return False
        return True

    pdf_files = [p for p in glob.glob(os.path.join(uploads_dir, f"{grade}_{year}_{month:02d}_*.pdf")) if _is_prob_pdf(p)]
    if not pdf_files:
        pdf_files = [p for p in glob.glob(os.path.join(uploads_dir, f"*{year}*{month:02d}*.pdf")) if _is_prob_pdf(p)]

    # script_pdf_path가 지정되지 않았을 때 uploads/ 폴더에서 대본 또는 해설 PDF 자동 감지
    if not script_pdf_path:
        cand_scripts = [p for p in glob.glob(os.path.join(uploads_dir, f"{grade}_{year}_{month:02d}_*.pdf")) if "_script" in p.lower() or "대본" in p]
        if cand_scripts:
            script_pdf_path = cand_scripts[0]
            is_explanation_pdf = False
        else:
            cand_exps = [p for p in glob.glob(os.path.join(uploads_dir, f"{grade}_{year}_{month:02d}_*.pdf")) if re.search(r"[-_]A\.pdf$", p, re.I) or "_exp" in p.lower()]
            if cand_exps:
                script_pdf_path = cand_exps[0]
                is_explanation_pdf = True

    target_hwp = explanation_hwp_path if (explanation_hwp_path and os.path.exists(explanation_hwp_path)) else None
    if not target_hwp:
        hwp_files = glob.glob(os.path.join(uploads_dir, f"{grade}_{year}_{month:02d}_*.hwp"))
        if not hwp_files:
            hwp_files = glob.glob(os.path.join(uploads_dir, f"*{year}*{month:02d}*.hwp"))
        if hwp_files:
            target_hwp = hwp_files[0]

    explanations = {}
    if target_hwp:
        try:
            explanations = hwp_parser.parse_hwp_explanations(target_hwp)
        except Exception as e:
            print(f"[Sync Listening Warning] HWP 해설 파싱 실패: {e}")

    # 정답 사전 사전 구축 (verified_key 우선, answers_dict 결합, DB 기존값(위에서 읽음) 및 HWP 해설 보완)
    verified_key = answer_keys.load_answer_key(grade, year, month)

    listening_answers = {}
    for q in range(start_q, end_q + 1):
        ans_val = ""
        if answers_dict and q in answers_dict and answers_dict[q]:
            ans_val = str(answers_dict[q])
        elif q in verified_key and verified_key[q]:
            ans_val = str(verified_key[q])
        elif q in db_answers and db_answers[q]:
            ans_val = str(db_answers[q])
        elif q in explanations and explanations[q].get("answer"):
            ans_val = str(explanations[q]["answer"])
        if ans_val:
            listening_answers[q] = ans_val

    pdf_questions = {}
    target_prob_pdf = question_pdf_path if (question_pdf_path and os.path.exists(question_pdf_path)) else (pdf_files[0] if pdf_files else None)
    if target_prob_pdf:
        try:
            pdf_questions = extract_listening_question_crops(
                pdf_path=target_prob_pdf,
                grade=grade,
                year=year,
                month=month,
                listening_start_q=start_q,
                listening_end_q=end_q,
                answers_dict=listening_answers,
                subtype=subtype
            )
        except Exception as e:
            print(f"[Sync Listening Warning] PDF 듣기 크롭 실패: {e}")

    script_crops = {}
    if script_pdf_path and os.path.exists(script_pdf_path):
        try:
            script_crops = extract_listening_script_crops(
                script_or_exp_pdf_path=script_pdf_path,
                grade=grade,
                year=year,
                month=month,
                is_explanation_pdf=is_explanation_pdf,
                listening_start_q=start_q,
                listening_end_q=end_q,
                subtype=subtype
            )
        except Exception as e:
            print(f"[Sync Listening Warning] 대본 크롭 실패: {e}")

    saved_count = 0
    for q in range(start_q, end_q + 1):
        if subtype:
            p_id = f"[{grade}-{year}년-{month:02d}월-{subtype}-{q:02d}번]"
        else:
            p_id = f"[{grade}-{year}년-{month:02d}월-{q:02d}번]"
        exp_info = explanations.get(q, {})
        ans_val = listening_answers.get(q, "")
        if not ans_val:
            ans_val = exp_info.get("answer", "")
            if q in verified_key and verified_key[q]:
                ans_val = verified_key[q]

        exp_text = exp_info.get("explanation", "")
        if ans_val and not re.search(r"^\s*\[\s*정답\s*\]", exp_text):
            exp_text = f"[정답] {ans_val}\n\n{exp_text}".strip()

        q_title = pdf_questions.get(q, {}).get("question_title", f"{q}. 문항")
        crop_img = pdf_questions.get(q, {}).get("pdf_crop_image", "")
        script_crop_img = script_crops.get(q, None)

        script_txt = extract_script_text_from_explanation(exp_text)
        fels_txt = fels_engine.generate_fels_text(script_txt) if script_txt else ""

        p_data = {
            "id": p_id,
            "exam_id": clean_id,
            "q_num": q,
            "question_title": q_title,
            "question_type": classify_listening_question_type(q_title, q),
            "passage_text": script_txt or q_title,
            "answer_text": ans_val,
            "explanation_text": exp_text,
            "pdf_crop_image": crop_img,
            "validation_ratio": 1.0,
            "remarks": "듣기 문항",
            "area": "listening",
            "script_crop_image": script_crop_img,
            "script_text": script_txt,
            "fels_text": fels_txt,
            "audio_file_path": None
        }
        db.save_passage(p_data)
        saved_count += 1

    return {
        "success": True,
        "exam_id": clean_id,
        "saved_count": saved_count,
        "synced_count": saved_count,
        "has_pdf": bool(pdf_files),
        "has_hwp": bool(target_hwp),
        "script_crops_count": len(script_crops)
    }


def sync_all_missing_listening_answers() -> int:
    """
    DB 내 전체 듣기 문항(area='listening') 중 answer_text가 비어있는 문항들에 대해
    answer_keys 키 파일의 정답(1~17번)을 매칭하여 즉시 일괄 동기화
    """
    updated_count = 0
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, grade, year, month FROM exams")
        exams = cursor.fetchall()
        for ex in exams:
            grade, year, month = ex["grade"], ex["year"], ex["month"]
            clean_id = ex["id"]
            verified_key = answer_keys.load_answer_key(grade, year, month)
            if not verified_key:
                continue

            cursor.execute(
                "SELECT id, q_num, answer_text, explanation_text FROM passages WHERE exam_id = ? AND area = 'listening'",
                (clean_id,)
            )
            passages = cursor.fetchall()
            for p in passages:
                q = int(p["q_num"])
                current_ans = (p["answer_text"] or "").strip()
                if not current_ans and q in verified_key and verified_key[q]:
                    target_ans = verified_key[q]
                    exp_text = p["explanation_text"] or ""
                    if not re.search(r"^\s*\[\s*정답\s*\]", exp_text):
                        new_exp = f"[정답] {target_ans}\n\n{exp_text}".strip()
                    else:
                        new_exp = re.sub(r"^\s*\[\s*정답\s*\]\s*[①②③④⑤1-5]?", f"[정답] {target_ans}", exp_text)
                    cursor.execute(
                        "UPDATE passages SET answer_text = ?, explanation_text = ?, answer_source = 'verified_key', answer_verified = 1 WHERE id = ?",
                        (target_ans, new_exp, p["id"])
                    )
                    updated_count += 1
        conn.commit()
    return updated_count

