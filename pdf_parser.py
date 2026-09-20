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

CAPTURES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "captures")
os.makedirs(CAPTURES_DIR, exist_ok=True)

CIRCLED_MAP = {"1": "①", "2": "②", "3": "③", "4": "④", "5": "⑤"}


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
                target_sym = CIRCLED_MAP.get(str(answer_symbol).strip(), str(answer_symbol).strip())
                try:
                    words = page.get_text("words", clip=crop_rect)
                    choice_words = []
                    collecting = False
                    for w in words:
                        w_text = w[4]
                        if target_sym in w_text:
                            collecting = True
                            choice_words.append(w)
                            continue
                        if collecting:
                            if any(sym in w_text for sym in ("①", "②", "③", "④", "⑤")) or w_text.startswith("*"):
                                collecting = False
                                break
                            choice_words.append(w)

                    # 줄(line) 단위로 묶기 (y 좌표 5pt 이내)
                    lines_grouped = []
                    curr_line = []
                    for w in choice_words:
                        if not curr_line:
                            curr_line.append(w)
                        else:
                            if abs(w[1] - curr_line[0][1]) < 5:
                                curr_line.append(w)
                            else:
                                lines_grouped.append(curr_line)
                                curr_line = [w]
                    if curr_line:
                        lines_grouped.append(curr_line)

                    for l in lines_grouped:
                        lx0 = min(w[0] for w in l) - 3
                        ly0 = min(w[1] for w in l) - 2
                        lx1 = max(w[2] for w in l) + 3
                        ly1 = max(w[3] for w in l) + 2
                        hl_rect = fitz.Rect(lx0, ly0, lx1, ly1)
                        annot = page.add_highlight_annot(hl_rect)
                        annot.set_colors(stroke=(1.0, 0.95, 0.1))  # 선명한 형광 노란색
                        annot.update()
                        added_annots.append(annot)
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
