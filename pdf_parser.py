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
    ans_num = REVERSE_CIRCLED_MAP.get(str(ans_val).strip(), None)
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
                    min(target_anchor["x1"], target_anchor["x0"] + 12),
                    target_anchor["y1"]
                )

    if not target_rect:
        all_sym_rects = page.search_for(sym, clip=clip_rect)
        if all_sym_rects:
            target_rect = all_sym_rects[0]

    if not target_rect:
        return []

    # 3. 파스텔톤 노란색 형광펜 하이라이트 주석 생성 (정답 번호 기호에만 2pt 패딩 부여)
    hl_rect = fitz.Rect(target_rect.x0 - 2, target_rect.y0 - 2, target_rect.x1 + 2, target_rect.y1 + 2)
    annot = page.add_highlight_annot(hl_rect)
    annot.set_colors(stroke=(0.996, 0.941, 0.541))  # 부드러운 파스텔톤 형광 노란색 (#fef08a)
    annot.update()

    return [annot]



def detect_listening_range(full_text: str) -> Tuple[int, int]:
    """
    시험지 텍스트에서 듣기 평가 문항 번호 범위 감지
    기본값: 독해 시작 18, 끝 45 (안내문 발견 시 동적 설정)
    """
    match = re.search(r"1\s*번\s*부터\s*(\d{1,2})\s*번\s*까지\s*는\s*듣고", full_text)
    if match:
        return int(match.group(1)) + 1, 45
    else:
        match_ab = re.search(r"(\d{1,2})\s*번\s*까지는\s*듣고", full_text)
        if match_ab:
            return int(match_ab.group(1)) + 1, 45

    return 18, 45


def extract_pdf_columns_and_questions(
    pdf_path: str,
    grade: str = "고3",
    year: int = 2024,
    month: int = 6,
    reading_start: Optional[int] = None,
    reading_end: Optional[int] = None,
    answers_dict: Optional[Dict[int, str]] = None
) -> Dict[int, Dict]:
    """
    PDF 시험지에서 2단(Two-Column) 레이아웃을 칼럼별로 독립 분석하여
    문항별 텍스트 및 정확한 크롭 이미지 생성
    """
    doc = fitz.open(pdf_path)
    all_page_text = ""

    for page in doc:
        all_page_text += page.get_text() + "\n"

    detected_start, detected_end = detect_listening_range(all_page_text)
    start_q = reading_start if reading_start is not None else detected_start
    end_q = reading_end if reading_end is not None else detected_end

    # 문항 번호 감지 정규식 (예: "18. 다음 글의", "36.", "37. ")
    q_pattern = re.compile(r"^\s*(\d{1,2})\s*\.(?:\s*(.*))?")
    # 복합 지문 헤더 감지 정규식 (예: "[41~42] 다음 글을 읽고...")
    group_header_pattern = re.compile(r"^\s*\[\s*(\d{1,2})\s*[~～\-]\s*(\d{1,2})\s*\](?:\s*(.*))?")

    questions_data = {}
    shared_group_cache = {}  # (g_start, g_end): {'rects': [...], 'text': [...], 'page_num': int}

    for page_num in range(len(doc)):
        page = doc[page_num]
        rect = page.rect
        width, height = rect.width, rect.height
        mid_x = width / 2.0

        # 헤더(상단 155pt)와 푸터(하단 60pt)를 제외한 칼럼 클립 영역
        left_clip = fitz.Rect(35, 155, mid_x - 5, height - 60)
        right_clip = fitz.Rect(mid_x + 5, 155, width - 35, height - 60)

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
                if b_rect.y1 < 160 or b_rect.y0 > height - 65:
                    continue
                if b_text in ("영어 영역", "홀수형", "짝수형") or re.match(r"^\d{1,2}$", b_text):
                    continue

                lines = b_text.split("\n")
                first_line = lines[0].strip()

                # 복합 지문 헤더 확인 (예: [41~42])
                grp_match = group_header_pattern.match(first_line)
                if grp_match:
                    # 이전 문항이 있다면 종료
                    if current_q and current_text_lines:
                        ans_sym = (answers_dict or {}).get(current_q, "")
                        save_extracted_question(
                            doc, current_q, current_text_lines, current_rects,
                            grade, year, month, questions_data, shared_group_cache,
                            answer_symbol=ans_sym
                        )
                        current_q = None
                        current_text_lines = []
                        current_rects = []

                    g_s = int(grp_match.group(1))
                    g_e = int(grp_match.group(2))
                    active_group = (g_s, g_e)
                    group_text_lines = [b_text]
                    group_rects = [(page_num, b_rect)]
                    continue

                # 문항 번호 시작 확인
                q_match = q_pattern.match(first_line)
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
                                answer_symbol=ans_sym
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
                    answer_symbol=ans_sym
                )

            # 칼럼 끝에 공유 지문이 걸려있을 경우 캐시 저장
            if active_group and group_rects:
                shared_group_cache[active_group] = {
                    "page_num": page_num,
                    "rects": list(group_rects),
                    "text": list(group_text_lines)
                }

    # 1지문 3문항 (43~45번) 전용 고화질 크롭 & 세로 이어붙이기 수행
    merged_43_45_url = crop_and_merge_43_45(doc, grade, year, month, answers_dict)
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
    answer_symbol: str = ""
):
    """문항 텍스트 정제, 정답 선지 형광펜 하이라이트 및 고화질 이미지 크롭 저장"""
    full_q_text = "\n".join(text_lines)

    lines = [l.strip() for l in full_q_text.split("\n") if l.strip()]
    question_title = lines[0] if lines else f"{q_num}. 문항"
    passage_body = "\n".join(lines[1:]) if len(lines) > 1 else ""

    # 공유 지문에 속한 문항(예: 41번)인 경우 공유 지문 텍스트 및 영역 병합
    attached_group_rects = []
    for (g_s, g_e), g_data in shared_group_cache.items():
        if g_s <= q_num <= g_e:
            # 41번 또는 첫 문항의 경우 공유 지문 Bounding Box 포함하여 크롭
            if q_num == g_s:
                attached_group_rects = g_data.get("rects", [])
            # 본문이 비어있으면 공유 지문 텍스트 채우기
            if not passage_body and g_data.get("text"):
                passage_body = "\n".join(g_data["text"]) + "\n" + passage_body
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

    # 지문 식별자: [고3-2024년-06월-21번]
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

            crop_rect = fitz.Rect(
                max(0, min_x),
                max(0, min_y),
                min(page.rect.width, max_x),
                min(page.rect.height, max_y)
            )

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
    answers_dict: dict = None
) -> Optional[str]:
    """
    1지문 3문항(43~45번) 전용 고화질 크롭 & 세로 이어붙이기:
    - 지문 (좌측 칼럼 [43~45] + (A) 영역 & 우측 칼럼 (B)~(D) 영역)
    - 43번 문항 (정답 선지 형광펜 하이라이트)
    - 44번 문항 (정답 선지 형광펜 하이라이트)
    - 45번 문항 (정답 선지 형광펜 하이라이트)
    각 영역을 고화질로 따로 캡처하여 위에서 아래로 세로로 이어붙인 단일 이미지 생성
    """
    answers_dict = answers_dict or {}

    # 43~45번이 위치한 마지막 페이지 탐색
    target_page = None
    for p_idx in range(len(doc) - 1, -1, -1):
        p = doc[p_idx]
        if p.search_for("[43~45]") or p.search_for("43~45") or p.search_for("(A)"):
            target_page = p
            break

    if not target_page:
        return None

    page = target_page
    width, height = page.rect.width, page.rect.height
    mid_x = width / 2.0

    # 1. 좌측 칼럼 [43~45] 및 (A) 영역 Bounding Box
    r_grp = page.search_for("[43~45]") or page.search_for("43~45")
    y_start_left = 880
    if r_grp:
        y_start_left = max(160, r_grp[0].y0 - 8)
    rect_a = fitz.Rect(75, y_start_left, mid_x - 5, height - 60)

    # 2. 우측 칼럼 (B), (C), (D) 지문 영역 및 43, 44, 45번 문항 영역
    r_bcd = page.search_for("(B)")
    r_43 = page.search_for("43.")
    r_44 = page.search_for("44.")
    r_45 = page.search_for("45.")

    y_start_right = 165
    if r_bcd:
        r_bcd_right = [r for r in r_bcd if r.x0 > mid_x]
        if r_bcd_right:
            y_start_right = max(160, r_bcd_right[0].y0 - 8)

    y_43_start = 728
    if r_43:
        r_43_right = [r for r in r_43 if r.x0 > mid_x]
        if r_43_right:
            y_43_start = r_43_right[0].y0 - 6

    y_44_start = 833
    if r_44:
        r_44_right = [r for r in r_44 if r.x0 > mid_x]
        if r_44_right:
            y_44_start = r_44_right[0].y0 - 6

    y_45_start = 888
    if r_45:
        r_45_right = [r for r in r_45 if r.x0 > mid_x]
        if r_45_right:
            y_45_start = r_45_right[0].y0 - 6

    rect_bcd = fitz.Rect(mid_x + 5, y_start_right, width - 35, y_43_start)
    rect_43 = fitz.Rect(mid_x + 5, y_43_start, width - 35, y_44_start)
    rect_44 = fitz.Rect(mid_x + 5, y_44_start, width - 35, y_45_start)
    rect_45 = fitz.Rect(mid_x + 5, y_45_start, width - 35, height - 60)

    # 정답 선지 형광펜 하이라이트 주석 적용
    annots = []
    # 정답 선지 형광펜 하이라이트 주석 적용 (엄격한 기하학적 매칭 적용)
    annots = []
    for r_clip, q_idx in [(rect_43, 43), (rect_44, 44), (rect_45, 45)]:
        ans_val = answers_dict.get(q_idx, "")
        if ans_val:
            try:
                annots.extend(highlight_answer_choice(page, r_clip, ans_val))
            except Exception as e:
                print(f"[{q_idx}번 정답 하이라이트 경고] {e}")

    # 고화질(200 DPI) 렌더링
    parts = []
    for r in [rect_a, rect_bcd, rect_43, rect_44, rect_45]:
        pix = page.get_pixmap(clip=r, dpi=200)
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        parts.append(img)

    # 1. 지문 세로 결합 (A + BCD)
    pw = max(parts[0].width, parts[1].width)
    ph = parts[0].height + parts[1].height + 16
    img_passage = Image.new("RGB", (pw, ph), (255, 255, 255))
    img_passage.paste(parts[0], ((pw - parts[0].width) // 2, 0))
    img_passage.paste(parts[1], ((pw - parts[1].width) // 2, parts[0].height + 16))

    # 2. 전체 세로 결합: [지문, 43번, 44번, 45번]
    final_items = [img_passage, parts[2], parts[3], parts[4]]
    max_w = max(im.width for im in final_items)
    total_h = sum(im.height for im in final_items) + 20 * (len(final_items) - 1)
    final_img = Image.new("RGB", (max_w, total_h), (255, 255, 255))
    curr_y = 0
    for im in final_items:
        final_img.paste(im, ((max_w - im.width) // 2, curr_y))
        curr_y += im.height + 20

    img_filename = f"{grade}_{year}_{month:02d}_43.png"
    img_filepath = os.path.join(CAPTURES_DIR, img_filename)
    final_img.save(img_filepath)

    # 44번, 45번 문항 파일도 일관성을 위해 동일한 통합 이미지로 저장
    for q_n in (44, 45):
        q_file = os.path.join(CAPTURES_DIR, f"{grade}_{year}_{month:02d}_{q_n:02d}.png")
        final_img.save(q_file)

    for a in annots:
        try:
            page.delete_annot(a)
        except Exception:
            pass

    return f"/static/captures/{img_filename}"

