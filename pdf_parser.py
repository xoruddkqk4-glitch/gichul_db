"""
05-gichul_db: PDF 2단 레이아웃 파서 및 문항별 이미지 크롭 모듈 (pdf_parser.py)
- PyMuPDF(fitz) 기반
- 2단(좌/우 칼럼) 구조를 칼럼별로 독립 분할하여 문항 순서대로 텍스트 추출
- 듣기 안내문 기반 동적 문항 번호 감지 (하드코딩 배제)
- 각 문항의 좌표(Bounding Box)를 정밀 계산하여 고화질 문항 이미지(/static/captures/) 크롭 저장
- 칼럼 경계 및 헤더/푸터 침범을 차단하여 단일 문항 단위로만 정확히 크롭
"""

import os
import re
from typing import List, Dict, Tuple, Optional
import pymupdf as fitz
from PIL import Image

CAPTURES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "captures")
os.makedirs(CAPTURES_DIR, exist_ok=True)

CIRCLED_MAP = {"1": "①", "2": "②", "3": "③", "4": "④", "5": "⑤"}
REVERSE_CIRCLED_MAP = {"①": 1, "②": 2, "③": 3, "④": 4, "⑤": 5, "1": 1, "2": 2, "3": 3, "4": 4, "5": 5}


def extract_choice_words_geometrically(page: fitz.Page, clip_rect: fitz.Rect, ans_val: str) -> List[tuple]:
    """
    정답 선지 기호(①~⑤)를 기하학적으로 탐색하고,
    동일 행/열에 속하는 해당 정답 선지 텍스트 단어들만 엄격하게 필터링하여 반환
    (PDF 스트림 순서 왜곡으로 인한 다른 보기(①, ③ 등)의 오염 하이라이트 원천 방지)
    """
    if not ans_val:
        return []
    ans_num = REVERSE_CIRCLED_MAP.get(str(ans_val).strip(), None)
    if not ans_num:
        return []

    words = page.get_text("words", clip=clip_rect)
    if not words:
        return []

    # 1. 보기 기호 앵커 탐색
    anchors = []
    for w in words:
        w_text = w[4]
        for sym, num in REVERSE_CIRCLED_MAP.items():
            if sym in ("①", "②", "③", "④", "⑤") and sym in w_text:
                anchors.append({
                    "num": num,
                    "sym": sym,
                    "x0": w[0], "y0": w[1], "x1": w[2], "y1": w[3],
                    "cx": (w[0] + w[2]) / 2,
                    "cy": (w[1] + w[3]) / 2,
                    "word": w
                })

    target_anchor = next((a for a in anchors if a["num"] == ans_num), None)
    if not target_anchor:
        return []

    # 2. 동일 행(Y ±7pt)에 위치한 다른 앵커 중 우측 앵커 탐색 (수평 경계 제한)
    same_line_anchors = [
        a for a in anchors 
        if a["num"] != ans_num and abs(a["cy"] - target_anchor["cy"]) < 7
    ]
    right_limit_x = clip_rect.x1 + 10
    for sa in same_line_anchors:
        if sa["x0"] > target_anchor["x0"]:
            right_limit_x = min(right_limit_x, sa["x0"] - 3)

    # 3. 하단 경계 탐색 (다음 선지 시작 Y)
    below_anchors = [
        a for a in anchors 
        if a["y0"] > target_anchor["y1"] - 2 and (
            abs(a["x0"] - target_anchor["x0"]) < 45 or len(same_line_anchors) == 0
        )
    ]
    bottom_limit_y = clip_rect.y1
    if below_anchors:
        bottom_limit_y = min(a["y0"] for a in below_anchors) - 2

    # 4. 정밀 기하학적 단어 필터링
    matched = []
    for w in words:
        w_text = w[4]
        # 다른 선지 기호는 무조건 제외
        if any(sym in w_text for sym in ("①", "②", "③", "④", "⑤")) and w is not target_anchor["word"]:
            continue
        if w_text.startswith("*"):
            continue

        w_cx = (w[0] + w[2]) / 2
        w_cy = (w[1] + w[3]) / 2

        # A. 동일 행에 있는 텍스트
        if abs(w_cy - target_anchor["cy"]) < 7:
            if w[0] >= target_anchor["x0"] - 2 and w_cx < right_limit_x:
                matched.append(w)
        # B. 여러 줄로 이어지는 다행 선지 텍스트
        elif target_anchor["y1"] - 2 < w_cy < bottom_limit_y:
            if len(same_line_anchors) > 0:
                if target_anchor["x0"] - 10 <= w[0] and w_cx < right_limit_x:
                    matched.append(w)
            else:
                if w[0] >= clip_rect.x0 - 5:
                    matched.append(w)

    return matched


def highlight_answer_choice(page: fitz.Page, clip_rect: fitz.Rect, ans_val: str) -> List[fitz.Annot]:
    """
    정답 선지 번호(①~⑤)를 탐색하고,
    선지 텍스트는 제외한 채 오직 정답에 해당하는 번호 기호에만 파스텔톤 노란색 형광펜 주석 추가
    """
    if not ans_val:
        return []
    
    # 정답 값 정규화 (원문자 및 1~5 정수 지원, '3' 또는 '③' 또는 '[정답] 3' 등 대응)
    ans_str = str(ans_val).strip()
    m = re.search(r"[①②③④⑤1-5]", ans_str)
    if m:
        ans_str = m.group(0)
    ans_num = REVERSE_CIRCLED_MAP.get(ans_str, None)
    if not ans_num:
        return []

    sym = CIRCLED_MAP.get(str(ans_num), "")
    if not sym:
        return []

    words = page.get_text("words", clip=clip_rect)
    target_rect = None

    if words:
        anchors = []
        for w in words:
            w_text = w[4]
            for s_sym, num in REVERSE_CIRCLED_MAP.items():
                if s_sym in ("①", "②", "③", "④", "⑤") and s_sym in w_text:
                    anchors.append({
                        "num": num,
                        "sym": s_sym,
                        "x0": w[0], "y0": w[1], "x1": w[2], "y1": w[3],
                        "word": w
                    })

        target_anchor = next((a for a in anchors if a["num"] == ans_num), None)
        if target_anchor:
            # 단어 내에 다른 문자가 붙어있을 수 있으므로 국소 영역에서 search_for로 정확한 기호 좌표 추출
            local_rect = fitz.Rect(
                target_anchor["x0"] - 4,
                target_anchor["y0"] - 3,
                target_anchor["x1"] + 4,
                target_anchor["y1"] + 3
            )
            sym_rects = page.search_for(sym, clip=local_rect)
            if sym_rects:
                target_rect = sym_rects[0]
            else:
                target_rect = fitz.Rect(
                    target_anchor["x0"],
                    target_anchor["y0"],
                    min(target_anchor["x1"], target_anchor["x0"] + 13),
                    target_anchor["y1"]
                )

    # 2. 앵커 단어 분할이 안 된 경우 clip_rect 내 직접 검색 (원문자 -> 대체 표기 순)
    if not target_rect:
        all_sym_rects = page.search_for(sym, clip=clip_rect)
        if all_sym_rects:
            target_rect = all_sym_rects[0]
        else:
            for alt in (f"({ans_num})", f"{ans_num}.", f"[{ans_num}]"):
                alt_rects = page.search_for(alt, clip=clip_rect)
                if alt_rects:
                    target_rect = alt_rects[0]
                    break

    if not target_rect:
        return []

    # 3. 파스텔톤 노란색 형광펜 하이라이트 주석 생성 (기호 번호가 시각적으로 안정감 있게 덮이도록 적정 패딩 부여)
    hl_rect = fitz.Rect(
        target_rect.x0 - 2.5,
        target_rect.y0 - 2.0,
        target_rect.x1 + 2.5,
        target_rect.y1 + 2.0
    )
    annot = page.add_highlight_annot(hl_rect)
    # 산뜻하고 눈이 편안한 프리미엄 파스텔 노란색 (#FFE853 / RGB: 1.0, 0.91, 0.33)
    annot.set_colors(stroke=(1.0, 0.91, 0.33))
    annot.update()

    return [annot]



def detect_listening_range(full_text: str, year: Optional[int] = None) -> Tuple[int, int]:
    """
    시험지 텍스트에서 듣기/독해 영역 문항 번호 범위 감지
    - 발문 1: '1번부터 N번까지는 듣고 답하는 문제입니다...' (듣기 시작 안내 박스)
    - 발문 2: '이제 듣기·말하기 문제가 끝났습니다. M번부터는 문제지의 지시에 따라...' (독해 시작 안내 박스)
    - 2013년도(2014학년도 수준별 수능) 체제: 듣기 1~22번, 독해 23~45번 자동 감지
    - 구 50문항 체제(2006~2011년): 독해 끝 50번 자동 감지
    기본값: 독해 시작 18, 끝 45
    """
    is_50 = bool(
        re.search(r"(?:^|\n|\s)50\s*\.", full_text)
        or re.search(r"\[\s*49\s*[~～\-]\s*50\s*\]", full_text)
        or (year and 2006 <= year <= 2011)
    )
    default_end = 50 if is_50 else 45

    # 1. 종료 발문 (이제 듣기·말하기 문제가 끝났습니다. M번부터는 문제지의 지시에 따라...)
    m_end = re.search(r"(?:이제\s*)?(?:듣기[·\s]*말하기\s*문제|듣기\s*문제)[\s\S]{0,30}?(?:끝났습니다|끝났)[\s\S]{0,40}?(18|23)\s*번?\s*부터", full_text)
    if not m_end:
        m_end = re.search(r"(?:끝났습니다|끝났|ϱ⹮|ϴ)[\s\S]{0,40}?(18|23)\s*번?\s*부터", full_text)
    if not m_end:
        # CID 폰트 깨짐 대응: 끝났습니다 후 번호 단독 등장 (. 23)
        m_end = re.search(r"(?:끝났습니다|끝났|ϱ⹮|ϴ)[\s\S]{0,30}?\.\s*(18|23)\b", full_text)
    if m_end:
        return int(m_end.group(1)), default_end

    # 2. 시작 발문 표준 (1번부터 N번까지는 듣고 답하는 문제입니다...)
    m_start = re.search(r"1\s*번\s*부터\s*(\d{1,2})\s*번\s*까지\s*는?\s*(?:듣고|방송)", full_text)
    if m_start:
        return int(m_start.group(1)) + 1, default_end

    m_start_ab = re.search(r"(\d{1,2})\s*번\s*까지는?\s*(?:듣고|방송)", full_text)
    if m_start_ab:
        return int(m_start_ab.group(1)) + 1, default_end

    # 3. 깨진 폰트(CID ToUnicode 누락) 대비 시작 발문 숫자 시퀀스 패턴 (1 ... 22 ... 1 ... 20)
    m_loose = re.search(r"1[\s\S]{1,8}(17|22)[\s\S]{1,25}1[\s\S]{1,8}(?:15|20)", full_text)
    if m_loose:
        return int(m_loose.group(1)) + 1, default_end

    # 4. 연도 기본값 (2013년 전체 및 2012년 A/B형 수준별 시험은 듣기 22문항 -> 독해 23번 시작)
    if year == 2013 or (year == 2012 and full_text and ("A형" in full_text or "B형" in full_text or "22번까지" in full_text or "22." in full_text)):
        return 23, default_end

    return 18, default_end



def find_group_header(b_text: str, start_q: int, end_q: int) -> Optional[Tuple[int, int]]:
    """
    [41~42], [43~45], [46~48], [49~50], [41-42], [41 42],
    [46 ~ 다음 글을 읽고... 48], [3점] [43~45], 【46 - 48】, [46\\n48] 등
    다양한 괄호 기호 및 번호 중복 포맷의 1지문 다문항 헤더 번호 범위를 정밀 감지
    """
    # 1. 닫힌 괄호 쌍 내부 먼저 전수 검사
    bracket_iter = re.finditer(r"[\[［【〔〖〘]([\s\S]{1,80}?)[\]］】〕〗〙]", b_text)
    for m in bracket_iter:
        nums = [int(n) for n in re.findall(r"\b\d{1,2}\b", m.group(1))]
        valid_nums = [n for n in nums if start_q <= n <= end_q]
        if valid_nums:
            g_s = min(valid_nums)
            g_e = max(valid_nums)
            if g_s < g_e and (g_e - g_s) in (1, 2, 3):
                return g_s, g_e

    # 2. 닫는 괄호가 누락되거나 인코딩이 손상된 열린 괄호 구간 검사
    m_open = re.search(r"[\[［【〔〖〘]([\s\S]{1,80})", b_text)
    if m_open:
        nums = [int(n) for n in re.findall(r"\b\d{1,2}\b", m_open.group(1))]
        valid_nums = [n for n in nums if start_q <= n <= end_q]
        if valid_nums:
            g_s = min(valid_nums)
            g_e = max(valid_nums)
            if g_s < g_e and (g_e - g_s) in (1, 2, 3):
                return g_s, g_e

    return None


def find_notice_box_top(page: fitz.Page, min_x: float = 0.0, min_y: float = 0.0) -> Optional[float]:
    """
    시험지 마지막 페이지/칼럼 하단에 위치한 '※ 확인사항' (답안지 기입/표기 안내) 박스의 상단 Y 좌표 탐색
    문항 캡처 이미지에 불필요한 시험 안내문 및 테두리선이 침범하지 않도록 제외 기준선 제공
    """
    keywords = ["확인사항", "답안지의 해당란", "기입(표기)", "해당란을 정확히", "답안지의", "문제지와 답안지"]
    found_rects = []
    for kw in keywords:
        for r in page.search_for(kw):
            if r.x0 >= min_x - 40 and r.y0 >= min_y:
                found_rects.append(r)

    if not found_rects:
        return None

    notice_text_y0 = min(r.y0 for r in found_rects)
    box_top_y = notice_text_y0 - 10

    # 텍스트 위 50pt 이내에 위치한 박스 테두리선(벡터 드로잉) 탐색
    try:
        drawings = page.get_drawings()
        candidate_lines = []
        for d in drawings:
            dr = d.get("rect")
            if dr and dr.x0 >= min_x - 40:
                if notice_text_y0 - 45 <= dr.y0 <= notice_text_y0:
                    candidate_lines.append(dr.y0)
        if candidate_lines:
            box_top_y = min(candidate_lines) - 4
    except Exception:
        pass

    return box_top_y


def extract_pdf_columns_and_questions(
    pdf_path: str,
    grade: str = "고3",
    year: int = 2024,
    month: int = 6,
    reading_start: Optional[int] = None,
    reading_end: Optional[int] = None,
    start_q: Optional[int] = None,
    end_q: Optional[int] = None,
    answers_dict: Optional[Dict[int, str]] = None,
    subtype: Optional[str] = None,
    **kwargs
) -> Dict[int, Dict]:
    """
    PDF 시험지에서 2단(Two-Column) 레이아웃을 칼럼별로 독립 분석하여
    문항별 텍스트 및 정확한 크롭 이미지 생성
    """
    doc = fitz.open(pdf_path)
    all_page_text = ""

    for page in doc:
        all_page_text += page.get_text() + "\n"

    detected_start, detected_end = detect_listening_range(all_page_text, year=year)
    is_50 = (detected_end == 50) or (end_q is not None and end_q >= 48) or (reading_end is not None and reading_end >= 48) or (answers_dict and max(answers_dict.keys()) >= 48) or (2006 <= year <= 2011)
    if is_50 and (end_q is None or end_q == 45) and (reading_end is None or reading_end == 45):
        detected_end = 50

    if reading_start is not None:
        actual_start = reading_start
    elif start_q is not None and start_q != 18:
        actual_start = start_q
    else:
        actual_start = detected_start

    if reading_end is not None:
        actual_end = reading_end
    elif end_q is not None and end_q not in (45, 50):
        actual_end = end_q
    else:
        actual_end = detected_end

    start_q = actual_start
    end_q = actual_end

    # 문항 번호 감지 정규식 (예: "18. 다음 글의", "36.", "37. ")
    q_pattern = re.compile(r"^\s*(\d{1,2})\s*\.(?:\s*(.*))?")

    questions_data = {}
    shared_group_cache = {}  # (g_start, g_end): {'rects': [...], 'text': [...], 'page_num': int}

    for page_num in range(len(doc)):
        page = doc[page_num]
        rect = page.rect
        width, height = rect.width, rect.height
        # 세로 단 분할선(Vector Drawing) 탐색 (비대칭 여백 및 HWP 변환 문서 지원)
        divider_x = None
        try:
            v_lines = [
                d["rect"].x0 for d in page.get_drawings()
                if d.get("rect") and (d["rect"].y1 - d["rect"].y0) > (height * 0.4) and (d["rect"].x1 - d["rect"].x0) < 5
            ]
            mid_candidates = [x for x in v_lines if width * 0.35 <= x <= width * 0.65]
            if mid_candidates:
                divider_x = sum(mid_candidates) / len(mid_candidates)
        except Exception:
            pass

        if divider_x is None:
            divider_x = width / 2.0

        # 헤더(상단 50pt)와 푸터(하단 40pt)를 제외한 칼럼 클립 영역 (HWP 변환 문서 및 상단 발문 지원)
        left_clip = fitz.Rect(35, 50, divider_x - 3, height - 40)
        right_clip = fitz.Rect(divider_x + 3, 50, width - 35, height - 40)

        for col_idx, col_clip in [("L", left_clip), ("R", right_clip)]:
            raw_blocks = page.get_text("blocks", clip=col_clip)
            # Y좌표 우선 정렬
            blocks = sorted(raw_blocks, key=lambda b: (b[1], b[0]))

            current_q = None
            current_text_lines = []
            current_rects = []

            # 공유 지문 임시 버퍼
            active_group = None
            group_text_lines = []
            group_rects = []

            for b in blocks:
                b_rect = fitz.Rect(b[0], b[1], b[2], b[3])
                b_text = b[4].strip()
                if not b_text:
                    continue

                # 헤더/푸터/페이지 번호 단독 블록 필터링
                if b_rect.y0 > height - 40:
                    continue
                if b_rect.y1 < 65 and any(h in b_text for h in ("문제지", "영어 영역", "홀수형", "짝수형", "전국연합", "학력평가", "제 3 교시", "제 1 교시")):
                    continue
                if b_text in ("영어 영역", "홀수형", "짝수형") or re.match(r"^\d{1,2}$", b_text):
                    continue

                # 시험지 하단 '확인사항'(답안지 기입/표기 안내문) 블록 필터링
                if any(kw in b_text for kw in ("확인사항", "답안지의 해당란", "기입(표기)했는지", "기입(표기)")):
                    continue

                non_empty_lines = [l.strip() for l in b_text.split("\n") if l.strip()]
                first_line = non_empty_lines[0] if non_empty_lines else ""

                # 복합 지문 헤더 확인 (예: [41~42], [43~45], [46~48], [49~50], [46 ~ 읽고 답하시오 48] 등)
                grp_res = find_group_header(b_text, start_q, end_q)
                if grp_res:
                    g_s, g_e = grp_res
                    # 50문항 체제에서는 [41~42]가 공유 지문이 아니므로 안내 블록만 건너뜀
                    if is_50 and (g_s, g_e) == (41, 42):
                        continue

                    # 이전 문항이 있다면 종료
                    if current_q and current_text_lines:
                        ans_sym = (answers_dict or {}).get(current_q, "")
                        save_extracted_question(
                            doc, current_q, current_text_lines, current_rects,
                            grade, year, month, questions_data, shared_group_cache,
                            answer_symbol=ans_sym,
                            next_top_y=b_rect.y0,
                            col_clip=col_clip,
                            subtype=subtype
                        )
                        current_q = None
                        current_text_lines = []
                        current_rects = []

                    active_group = (g_s, g_e)
                    group_text_lines = [b_text]
                    group_rects = [(page_num, b_rect)]
                    continue

                # 문항 번호 시작 확인 (첫 줄 또는 블록 내 라인)
                q_match = None
                for l in non_empty_lines:
                    m = q_pattern.match(l)
                    if m:
                        q_match = m
                        break
                if q_match:
                    q_num = int(q_match.group(1))
                    if start_q <= q_num <= end_q:
                        # 복합 지문 버퍼가 있으면 캐시에 저장
                        if active_group:
                            shared_group_cache[active_group] = {
                                "page_num": page_num,
                                "rects": list(group_rects),
                                "text": list(group_text_lines)
                            }
                            active_group = None

                        # 이전 문항 마무리
                        if current_q and current_text_lines:
                            ans_sym = (answers_dict or {}).get(current_q, "")
                            save_extracted_question(
                                doc, current_q, current_text_lines, current_rects,
                                grade, year, month, questions_data, shared_group_cache,
                                answer_symbol=ans_sym,
                                next_top_y=b_rect.y0,
                                col_clip=col_clip,
                                subtype=subtype
                            )

                        current_q = q_num
                        current_text_lines = [b_text]
                        current_rects = [(page_num, b_rect)]
                        continue

                # 복합 지문 본문 누적
                if active_group:
                    group_text_lines.append(b_text)
                    group_rects.append((page_num, b_rect))
                    continue

                # 현재 문항 본문 누적
                if current_q:
                    current_text_lines.append(b_text)
                    current_rects.append((page_num, b_rect))

            # 칼럼 종료 시 열려있는 문항 마무리 (칼럼 간 침범 방지)
            if current_q and current_text_lines:
                ans_sym = (answers_dict or {}).get(current_q, "")
                save_extracted_question(
                    doc, current_q, current_text_lines, current_rects,
                    grade, year, month, questions_data, shared_group_cache,
                    answer_symbol=ans_sym,
                    next_top_y=col_clip.y1,
                    col_clip=col_clip,
                    subtype=subtype
                )

            # 칼럼 끝에 공유 지문이 걸려있을 경우 캐시 저장
            if active_group and group_rects:
                shared_group_cache[active_group] = {
                    "page_num": page_num,
                    "rects": list(group_rects),
                    "text": list(group_text_lines)
                }

    # 45문항 체제에서만 1지문 3문항 (43~45번) 전용 고화질 크롭 & 세로 이어붙이기 수행
    if not is_50:
        merged_43_45_url = crop_and_merge_43_45(doc, grade, year, month, answers_dict, subtype=subtype)
        if merged_43_45_url:
            for q_target in (43, 44, 45):
                if q_target in questions_data:
                    questions_data[q_target]["pdf_crop_image"] = merged_43_45_url

    doc.close()
    return questions_data


def save_extracted_question(
    doc: fitz.Document,
    q_num: int,
    text_lines: List[str],
    rects: List[Tuple[int, fitz.Rect]],
    grade: str,
    year: int,
    month: int,
    out_dict: dict,
    shared_group_cache: dict,
    answer_symbol: str = "",
    next_top_y: Optional[float] = None,
    col_clip: Optional[fitz.Rect] = None,
    subtype: Optional[str] = None
):
    """문항 텍스트 정제, 정답 선지 형광펜 하이라이트 및 고화질 이미지 크롭 저장"""
    full_q_text = "\n".join(text_lines)

    lines = [l.strip() for l in full_q_text.split("\n") if l.strip()]
    question_title = lines[0] if lines else f"{q_num}. 문항"
    passage_body = "\n".join(lines[1:]) if len(lines) > 1 else ""

    # 공유 지문에 속한 문항(예: 41번 또는 46번, 49번)인 경우 공유 지문 텍스트 및 영역 병합
    attached_group_rects = []
    for (g_s, g_e), g_data in shared_group_cache.items():
        if g_s <= q_num <= g_e:
            # 첫 문항(예: 41번, 46번, 49번)의 경우 공유 지문 Bounding Box 포함하여 크롭
            if q_num == g_s:
                attached_group_rects = g_data.get("rects", [])
                if g_data.get("text"):
                    passage_body = "\n".join(g_data["text"]) + ("\n\n" + passage_body if passage_body else "")
            elif not passage_body and g_data.get("text"):
                passage_body = "\n".join(g_data["text"])
            break

    # 하단 선택지(① ~ ⑤) 앞까지의 순수 지문 본문 정제 (문장 분할용)
    clean_passage_body = passage_body
    if q_num not in (29, 30, 35, 38, 39):
        choice_split = re.split(r"(?:^|\n)\s*[①1]\b|[①]", passage_body)
        if len(choice_split) > 1:
            clean_passage_body = choice_split[0].strip()

    # 지문 TXT: 문항 번호와 발문, 지문 본문, 그리고 객관식 선지(①~⑤)까지 모두 포함
    if passage_body:
        full_passage_text = f"{question_title}\n\n{passage_body.strip()}"
    else:
        full_passage_text = question_title

    # 지문 식별자: [고3-2024년-06월-21번] 또는 [고3-2013년-03월-A형-21번]
    if subtype:
        passage_id = f"[{grade}-{year}년-{month:02d}월-{subtype}-{q_num:02d}번]"
        img_filename = f"{grade}_{year}_{month:02d}_{subtype}_{q_num:02d}.png"
    else:
        passage_id = f"[{grade}-{year}년-{month:02d}월-{q_num:02d}번]"
        img_filename = f"{grade}_{year}_{month:02d}_{q_num:02d}.png"
    img_filepath = os.path.join(CAPTURES_DIR, img_filename)
    web_img_url = f"/static/captures/{img_filename}"

    all_crop_rects = list(attached_group_rects) + list(rects)

    if all_crop_rects:
        page_num = all_crop_rects[0][0]
        page = doc[page_num]

        same_page_rects = [r[1] for r in all_crop_rects if r[0] == page_num]
        if same_page_rects:
            min_x = min(r.x0 for r in same_page_rects) - 6
            min_y = min(r.y0 for r in same_page_rects) - 6
            max_x = max(r.x1 for r in same_page_rects) + 6
            max_y = max(r.y1 for r in same_page_rects) + 6

            # 칼럼 내 삽입 이미지 및 일러스트레이션/그림 탐지 및 크롭 영역 자동 확장
            col_left = col_clip.x0 if col_clip else 30
            col_right = col_clip.x1 if col_clip else (page.rect.width - 30)
            bottom_bound = next_top_y if (next_top_y is not None and next_top_y > min_y) else (col_clip.y1 if col_clip else page.rect.height - 40)

            # 1. 래스터 이미지(비트맵) 탐색 (듣기 4번 그림 문항, 독해 도표/그래프 등)
            try:
                for img_info in page.get_images(full=True):
                    for img_r in page.get_image_rects(img_info[0]):
                        if (img_r.x1 > col_left - 10 and img_r.x0 < col_right + 10 and
                            img_r.y1 > min_y and img_r.y0 < bottom_bound - 2):
                            min_x = min(min_x, img_r.x0 - 6)
                            max_x = max(max_x, img_r.x1 + 6)
                            max_y = max(max_y, img_r.y1 + 6)
            except Exception:
                pass

            # 2. 벡터 드로잉 탐색 (선, 다이어그램, 일러스트 패스)
            try:
                for d in page.get_drawings():
                    dr = d.get("rect")
                    if not dr:
                        continue
                    is_vert_divider = (dr.width < 5 and dr.height > 150)
                    is_horiz_divider = (dr.height < 5 and dr.width > 200)
                    if not is_vert_divider and not is_horiz_divider and dr.width > 15 and dr.height > 15:
                        if (dr.x1 > col_left - 10 and dr.x0 < col_right + 10 and
                            dr.y1 > min_y and dr.y0 < bottom_bound - 2):
                            min_x = min(min_x, dr.x0 - 6)
                            max_x = max(max_x, dr.x1 + 6)
                            max_y = max(max_y, dr.y1 + 6)
            except Exception:
                pass

            # 3. 그림 문항(듣기 4번 또는 '그림에서...' 발문) 안전 폴백: 다음 문항 직전까지 영역 확장
            is_picture_q = ("그림" in question_title or "그림" in full_q_text or q_num == 4)
            if is_picture_q and next_top_y is not None and next_top_y > max_y + 40:
                max_y = max(max_y, next_top_y - 8)

            crop_rect = fitz.Rect(
                max(0, min_x),
                max(0, min_y),
                min(page.rect.width, max_x),
                min(page.rect.height, max_y)
            )

            # 마지막 문항(45번, 50번 등) 또는 마지막 페이지 문항의 하단 확인사항(답안지 기입/표기 안내 박스) 침범 차단
            if q_num in (45, 50) or page_num == len(doc) - 1:
                notice_top = find_notice_box_top(page, min_x=crop_rect.x0, min_y=crop_rect.y0)
                if notice_top and notice_top > crop_rect.y0 + 30:
                    crop_rect.y1 = min(crop_rect.y1, notice_top)

            # 정답 선지 형광펜 하이라이트 주석 적용
            added_annots = []
            if answer_symbol:
                try:
                    added_annots = highlight_answer_choice(page, crop_rect, answer_symbol)
                except Exception as e:
                    print(f"[{q_num}번 정답 선지 하이라이트 경고] {e}")

            # 200 DPI로 고화질 크롭 이미지 생성
            pix = page.get_pixmap(clip=crop_rect, dpi=200)
            pix.save(img_filepath)

            # 임시 형광펜 주석 제거 (다음 문항 및 페이지 원본 무결성 보존)
            for annot in added_annots:
                try:
                    page.delete_annot(annot)
                except Exception:
                    pass
    else:
        web_img_url = ""

    out_dict[q_num] = {
        "passage_id": passage_id,
        "q_num": q_num,
        "question_title": question_title,
        "raw_text": full_q_text,
        "passage_body": clean_passage_body,
        "passage_text": full_passage_text,
        "pdf_crop_image": web_img_url
    }


def crop_and_merge_43_45(
    doc: fitz.Document,
    grade: str,
    year: int,
    month: int,
    answers_dict: dict = None,
    subtype: Optional[str] = None
) -> Optional[str]:
    """
    1지문 3문항(43~45번) 전용 고화질 크롭 & 세로 이어붙이기:
    - 지문 (좌/우 칼럼의 지문 영역만 정확히 캡처, 문항 번호 및 보기 중복 침범 방지)
    - 43번, 44번, 45번 문항을 각각 독립된 영역으로 크롭하고 정답 선지 형광펜 하이라이트 적용
    - 위에서 아래로 [지문, 43번, 44번, 45번] 순으로 세로 결합한 단일 고화질 이미지 생성
    """
    answers_dict = answers_dict or {}

    # 43~45번이 위치한 마지막 페이지 탐색
    target_page = None
    for p_idx in range(len(doc) - 1, -1, -1):
        p = doc[p_idx]
        if (
            p.search_for("[43~45]") or p.search_for("43~45") or
            p.search_for("[43～45]") or p.search_for("43～45") or
            p.search_for("(A)")
        ):
            target_page = p
            break

    if not target_page:
        return None

    page = target_page
    width, height = page.rect.width, page.rect.height

    # 세로 단 분할선 동적 감지
    divider_x = None
    try:
        v_lines = [
            d["rect"].x0 for d in page.get_drawings()
            if d.get("rect") and (d["rect"].y1 - d["rect"].y0) > (height * 0.4) and (d["rect"].x1 - d["rect"].x0) < 5
        ]
        mid_cands = [x for x in v_lines if width * 0.35 <= x <= width * 0.65]
        if mid_cands:
            divider_x = sum(mid_cands) / len(mid_cands)
    except Exception:
        pass
    if divider_x is None:
        divider_x = width / 2.0

    # 43, 44, 45번 문항 시작 위치 및 칼럼 소속(L/R) 정밀 탐색
    q_locs = {}
    for q in [43, 44, 45]:
        hits = (
            page.search_for(f"{q}.") or
            page.search_for(f"{q} .") or
            page.search_for(f"{q}\n.")
        )
        if hits:
            top_hit = min(hits, key=lambda r: r.y0)
            side = "L" if top_hit.x0 < divider_x else "R"
            q_locs[q] = {"side": side, "y0": top_hit.y0 - 6, "hit": top_hit}

    if not q_locs:
        return None

    # 각 문항별 정확한 Bounding Box 산출 (문항 간 침범 및 중복 방지)
    q_clips = {}
    for q, data in sorted(q_locs.items()):
        side = data["side"]
        y0 = data["y0"]
        x0 = 35 if side == "L" else divider_x + 3
        x1 = divider_x - 3 if side == "L" else width - 35

        # 같은 칼럼에서 이후에 시작하는 다음 문항이 있는지 확인
        subseq = [d["y0"] for k, d in q_locs.items() if d["side"] == side and d["y0"] > y0 + 10]
        if subseq:
            y1 = min(subseq)
        else:
            # 칼럼 하단 '확인사항' 박스 확인
            nb = [
                r for r in (page.search_for("확인") + page.search_for("답안지"))
                if (r.x0 < divider_x if side == "L" else r.x0 >= divider_x)
            ]
            if nb and any(r.y0 > y0 for r in nb):
                y1_limit = min(r.y0 for r in nb if r.y0 > y0) - 5
            else:
                y1_limit = height - 40

            # 실제 텍스트 블록의 바닥 좌표로 타이트하게 정밀 보정
            c_blocks = [
                b for b in page.get_text("blocks")
                if (b[0] < divider_x if side == "L" else b[0] >= divider_x)
                and b[1] >= y0 and b[3] <= y1_limit + 5
            ]
            if c_blocks:
                y1 = min(y1_limit, max(b[3] for b in c_blocks) + 10)
            else:
                y1 = y1_limit

        q_clips[q] = fitz.Rect(x0, y0, x1, y1)

    # 지문 영역 Bounding Box 산출 (문항이 시작되기 전 순수 지문 본문만 추출)
    r_grp = (
        page.search_for("[43~45]") or page.search_for("43~45") or
        page.search_for("[43～45]") or page.search_for("43～45")
    )
    y_start_l = max(60, r_grp[0].y0 - 8) if r_grp else 60

    # 1. 좌측 칼럼 지문 영역
    l_qs = [d["y0"] for d in q_locs.values() if d["side"] == "L"]
    if l_qs:
        y_end_l = min(l_qs)
    else:
        l_blocks = [
            b for b in page.get_text("blocks")
            if b[0] < divider_x and b[1] >= y_start_l and b[3] < height - 30
        ]
        y_end_l = max(b[3] for b in l_blocks) + 10 if l_blocks else height - 40
    rect_p_left = fitz.Rect(35, y_start_l, divider_x - 3, y_end_l)

    # 2. 우측 칼럼 지문 영역 (우측 문항 시작 전 지문 본문이 있는 경우에만 포함)
    rect_p_right = None
    r_qs = [d["y0"] for d in q_locs.values() if d["side"] == "R"]
    if r_qs:
        min_r_q = min(r_qs)
        r_blocks = [
            b for b in page.get_text("blocks")
            if b[0] >= divider_x and b[1] < min_r_q - 5 and b[3] > 60
        ]
        real_r = [
            b for b in r_blocks
            if not any(h in b[4] for h in ["홀수형", "짝수형", "영어 영역", "8", "문제지"])
        ]
        if real_r:
            y_start_r = max(60, min(b[1] for b in real_r) - 6)
            rect_p_right = fitz.Rect(divider_x + 3, y_start_r, width - 35, min_r_q)

    # 정답 선지 형광펜 하이라이트 주석 적용
    annots = []
    for q_idx in [43, 44, 45]:
        if q_idx in q_clips:
            ans_val = answers_dict.get(q_idx, "")
            if ans_val:
                try:
                    annots.extend(highlight_answer_choice(page, q_clips[q_idx], ans_val))
                except Exception as e:
                    print(f"[{q_idx}번 정답 하이라이트 경고] {e}")

    # 고화질(200 DPI) 렌더링
    parts = []
    for pr in [rect_p_left, rect_p_right]:
        if pr and pr.y1 > pr.y0 + 5:
            pix = page.get_pixmap(clip=pr, dpi=200)
            parts.append(Image.frombytes("RGB", [pix.width, pix.height], pix.samples))

    for q in [43, 44, 45]:
        if q in q_clips and q_clips[q].y1 > q_clips[q].y0 + 5:
            pix = page.get_pixmap(clip=q_clips[q], dpi=200)
            parts.append(Image.frombytes("RGB", [pix.width, pix.height], pix.samples))

    if not parts:
        return None

    # 전체 세로 결합: [지문(L), 지문(R)(있을 시), 43번, 44번, 45번]
    max_w = max(im.width for im in parts)
    total_h = sum(im.height for im in parts) + 20 * (len(parts) - 1)
    final_img = Image.new("RGB", (max_w, total_h), (255, 255, 255))
    curr_y = 0
    for im in parts:
        final_img.paste(im, ((max_w - im.width) // 2, curr_y))
        curr_y += im.height + 20

    if subtype:
        img_filename = f"{grade}_{year}_{month:02d}_{subtype}_43.png"
    else:
        img_filename = f"{grade}_{year}_{month:02d}_43.png"
    img_filepath = os.path.join(CAPTURES_DIR, img_filename)
    final_img.save(img_filepath)

    # 44번, 45번 문항 파일도 일관성을 위해 동일한 통합 이미지로 저장
    for q_n in (44, 45):
        if subtype:
            q_file = os.path.join(CAPTURES_DIR, f"{grade}_{year}_{month:02d}_{subtype}_{q_n:02d}.png")
        else:
            q_file = os.path.join(CAPTURES_DIR, f"{grade}_{year}_{month:02d}_{q_n:02d}.png")
        final_img.save(q_file)

    for a in annots:
        try:
            page.delete_annot(a)
        except Exception:
            pass

    return f"/static/captures/{img_filename}"

