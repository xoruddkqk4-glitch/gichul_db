"""
05-gichul_db: PDF 2단 레이아웃 파서 및 문항별 이미지 크롭 모듈 (pdf_parser.py)
- PyMuPDF(fitz) 기반
- 2단(좌/우 칼럼) 구조를 분할하여 문항 순서대로 텍스트 추출
- 듣기 안내문 기반 동적 문항 번호 감지 (하드코딩 배제)
- 각 문항의 좌표(Bounding Box)를 계산하여 고화질 문항 이미지(/static/captures/) 크롭 저장
"""

import os
import re
from typing import List, Dict, Tuple, Optional
import pymupdf as fitz

CAPTURES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "captures")
os.makedirs(CAPTURES_DIR, exist_ok=True)


def detect_listening_range(full_text: str) -> Tuple[int, int]:
    """
    시험지 텍스트에서 듣기 평가 문항 번호 범위 감지
    기본값: 독해 시작 18, 끝 45 (안내문 발견 시 동적 설정)
    """
    # 패턴 예: "1번부터 17번까지는 듣고", "1번부터 22번까지는 듣고"
    match = re.search(r"1\s*번\s*부터\s*(\d{1,2})\s*번\s*까지\s*는\s*듣고", full_text)
    if match:
        listening_end = int(match.group(1))
        return listening_end + 1, 45  # 독해 시작 번호, 기본 끝 번호

    # 2014년 수준별 수능(22번까지 듣기) 등 다른 패턴 탐색
    if "A형" in full_text or "B형" in full_text:
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
    reading_end: Optional[int] = None
) -> Dict[str, Dict]:
    """
    PDF 시험지에서 2단(Two-Column) 레이아웃을 분리 분석하여
    문항별 텍스트 및 크롭 이미지 생성
    """
    doc = fitz.open(pdf_path)
    all_page_text = ""

    # 전체 텍스트 수집 (듣기 범위 동적 탐지용)
    for page in doc:
        all_page_text += page.get_text() + "\n"

    detected_start, detected_end = detect_listening_range(all_page_text)
    start_q = reading_start if reading_start is not None else detected_start
    end_q = reading_end if reading_end is not None else detected_end

    # 문항 번호 감지 정규식 (예: "18. 다음 글의", "19 . 다음")
    q_pattern = re.compile(r"(?:^|\n)\s*(\d{1,2})\s*\.\s*(.+)")

    # 칼럼 단위로 블록 수집
    # 각 블록: (page_num, col_idx, rect, text)
    column_blocks = []

    for page_num in range(len(doc)):
        page = doc[page_num]
        rect = page.rect
        width, height = rect.width, rect.height
        mid_x = width / 2.0

        # 좌측 칼럼 (상단 여백 40pt, 하단 여백 40pt 제외)
        left_clip = fitz.Rect(20, 30, mid_x - 10, height - 30)
        # 우측 칼럼
        right_clip = fitz.Rect(mid_x + 10, 30, width - 20, height - 30)

        # 좌측 칼럼 블록
        left_text_blocks = page.get_text("blocks", clip=left_clip)
        left_text_blocks.sort(key=lambda b: (b[1], b[0]))  # Y좌표 정렬
        column_blocks.append((page_num, "L", left_clip, left_text_blocks))

        # 우측 칼럼 블록
        right_text_blocks = page.get_text("blocks", clip=right_clip)
        right_text_blocks.sort(key=lambda b: (b[1], b[0]))
        column_blocks.append((page_num, "R", right_clip, right_text_blocks))

    # 문항별 영역 탐지 및 데이터 추출
    questions_data = {}

    # 모든 블록을 순서대로 순회하며 문항 번호 매핑
    current_q = None
    current_text_lines = []
    current_rects = []  # (page_num, rect)

    for page_num, col_idx, col_rect, blocks in column_blocks:
        page = doc[page_num]
        for b in blocks:
            b_rect = fitz.Rect(b[0], b[1], b[2], b[3])
            b_text = b[4].strip()
            if not b_text:
                continue

            # 문항 시작 검사
            match = q_pattern.match(b_text)
            if match:
                q_num = int(match.group(1))
                if start_q <= q_num <= end_q:
                    # 이전 문항 마무리
                    if current_q and current_text_lines:
                        save_extracted_question(
                            doc, current_q, current_text_lines, current_rects,
                            grade, year, month, questions_data
                        )

                    current_q = q_num
                    current_text_lines = [b_text]
                    current_rects = [(page_num, b_rect)]
                    continue

            if current_q:
                current_text_lines.append(b_text)
                current_rects.append((page_num, b_rect))

    # 마지막 문항 마무리
    if current_q and current_text_lines:
        save_extracted_question(
            doc, current_q, current_text_lines, current_rects,
            grade, year, month, questions_data
        )

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
    out_dict: dict
):
    """문항 텍스트 정제 및 PDF 해당 문항 고화질 이미지 크롭 저장"""
    full_q_text = "\n".join(text_lines)

    # 발문(문제 제목)과 본문/보기 분리
    lines = [l.strip() for l in full_q_text.split("\n") if l.strip()]
    question_title = lines[0] if lines else f"{q_num}. 문항"
    passage_body = "\n".join(lines[1:]) if len(lines) > 1 else ""

    # 지문 ID: [O학년-OOOO년-OO월-OO번]
    passage_id = f"[{grade}-{year}년-{month:02d}월-{q_num:02d}번]"
    img_filename = f"{grade}_{year}_{month:02d}_{q_num:02d}.png"
    img_filepath = os.path.join(CAPTURES_DIR, img_filename)
    web_img_url = f"/static/captures/{img_filename}"

    # 문항 영역 크롭 이미지 생성
    if rects:
        # 동일 페이지 내 영역 통합
        page_num = rects[0][0]
        page = doc[page_num]

        # 첫 번째 페이지 내의 모든 rect 합치기
        same_page_rects = [r[1] for r in rects if r[0] == page_num]
        if same_page_rects:
            min_x = min(r.x0 for r in same_page_rects) - 5
            min_y = min(r.y0 for r in same_page_rects) - 5
            max_x = max(r.x1 for r in same_page_rects) + 5
            max_y = max(r.y1 for r in same_page_rects) + 5

            # 경계 벗어남 방지
            crop_rect = fitz.Rect(
                max(0, min_x),
                max(0, min_y),
                min(page.rect.width, max_x),
                min(page.rect.height, max_y)
            )

            # 200 DPI로 선명하게 렌더링
            pix = page.get_pixmap(clip=crop_rect, dpi=200)
            pix.save(img_filepath)
    else:
        web_img_url = ""

    out_dict[q_num] = {
        "passage_id": passage_id,
        "q_num": q_num,
        "question_title": question_title,
        "raw_text": full_q_text,
        "passage_body": passage_body,
        "pdf_crop_image": web_img_url
    }
