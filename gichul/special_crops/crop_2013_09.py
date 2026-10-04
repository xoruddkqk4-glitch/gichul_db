"""
gichul/special_crops/crop_2013_09.py (구 tools/crop_2013_09.py)
고3 2013년 9월 A형 및 B형 전용 고화질 200 DPI PDF 크롭 & 정답 형광펜 생성 모듈
벡터 곡선(Drawings)으로 변환된 문항 번호와 발문을 정밀 기하 레이아웃 및 여백 감지로 완벽 크롭
- 앱(gichul/app.py)이 실행 중에 import 합니다.
- 단독 실행: 프로젝트 루트에서 `python -m gichul.special_crops.crop_2013_09`
"""

import os
import sys
import sqlite3
import json
import fitz
from PIL import Image

from .. import paths

BASE_DIR = paths.ROOT_DIR
DB_PATH = paths.DB_PATH
CAPTURES_DIR = paths.CAPTURES_DIR
os.makedirs(CAPTURES_DIR, exist_ok=True)

# PDF paths
PDF_A = os.path.join(paths.UPLOADS_DIR, "고3_2013_09_고3-[2013-09-A].pdf")
PDF_B = os.path.join(paths.UPLOADS_DIR, "고3_2013_09_고3-[2013-09-B].pdf")

# Geometry
X_L0, X_L1 = 85.0, 420.0
X_R0, X_R1 = 422.0, 757.0
Y_TOP = 147.0
Y_BOT = 1067.0


def crop_rect_200dpi(doc, page_num, rect, out_path, highlight_rects=None):
    """지정된 Rect 영역을 200 DPI로 크롭하고 옵션으로 형광펜 주석 추가"""
    page = doc[page_num]
    annots = []
    if highlight_rects:
        for hr in highlight_rects:
            if hr:
                annot = page.add_highlight_annot(hr)
                annot.set_colors(stroke=(1.0, 0.91, 0.33)) # #FFE853
                annot.update()
                annots.append(annot)

    mat = fitz.Matrix(200 / 72.0, 200 / 72.0)
    pix = page.get_pixmap(matrix=mat, clip=rect)
    pix.save(out_path)

    for annot in annots:
        page.delete_annot(annot)


def get_a_boxes():
    """A형 45문항 (page_idx, x0, y0, x1, y1) 매핑"""
    b = {}
    # Page 1 (idx 0)
    # L: Q1, Q2, Q3, Q4
    b[1] = (0, X_L0, 147.0, X_L1, 468.5)
    b[2] = (0, X_L0, 468.5, X_L1, 649.4)
    b[3] = (0, X_L0, 649.4, X_L1, 828.9)
    b[4] = (0, X_L0, 828.9, X_L1, Y_BOT)
    # R: Q5 ~ Q12 (8 questions)
    r_splits_p1 = [147.0, 265.0, 365.3, 513.1, 626.9, 758.3, 838.5, 952.0, Y_BOT]
    for i in range(8):
        b[5 + i] = (0, X_R0, r_splits_p1[i], X_R1, r_splits_p1[i + 1])

    # Page 2 (idx 1)
    # L: Q13 ~ Q17 (5 questions)
    l_splits_p2 = [147.0, 269.4, 398.9, 511.2, 623.5, Y_BOT]
    for i in range(5):
        b[13 + i] = (1, X_L0, l_splits_p2[i], X_L1, l_splits_p2[i + 1])
    # R: Q18 ~ Q22 (5 questions)
    r_splits_p2 = [147.0, 324.5, 499.5, 691.9, 868.2, Y_BOT]
    for i in range(5):
        b[18 + i] = (1, X_R0, r_splits_p2[i], X_R1, r_splits_p2[i + 1])

    # Page 3 (idx 2)
    b[23] = (2, X_L0, 147.0, X_L1, 640.5)
    b[24] = (2, X_L0, 640.5, X_L1, Y_BOT)
    b[25] = (2, X_R0, 147.0, X_R1, 593.5)
    b[26] = (2, X_R0, 593.5, X_R1, Y_BOT)

    # Page 4 (idx 3)
    b[27] = (3, X_L0, 147.0, X_L1, 656.8)
    b[28] = (3, X_L0, 656.8, X_L1, Y_BOT)
    b[29] = (3, X_R0, 147.0, X_R1, Y_BOT)

    # Page 5 (idx 4)
    b[30] = (4, X_L0, 147.0, X_L1, Y_BOT)
    b[31] = (4, X_R0, 147.0, X_R1, Y_BOT)

    # Page 6 (idx 5)
    b[32] = (5, X_L0, 147.0, X_L1, 664.5)
    b[33] = (5, X_L0, 664.5, X_L1, Y_BOT)
    b[34] = (5, X_R0, 147.0, X_R1, 586.8)
    b[35] = (5, X_R0, 586.8, X_R1, Y_BOT)

    # Page 7 (idx 6)
    b[36] = (6, X_L0, 147.0, X_L1, 457.2)
    b[37] = (6, X_L0, 457.2, X_L1, 831.0)
    b[38] = (6, X_L0, 831.0, X_L1, Y_BOT)
    b[39] = (6, X_R0, 147.0, X_R1, 595.9)
    b[40] = (6, X_R0, 595.9, X_R1, Y_BOT)

    # Page 8 (idx 7)
    # 41~42 complex passage (L)
    b[41] = (7, X_L0, 147.0, X_L1, Y_BOT)
    b[42] = (7, X_L0, 147.0, X_L1, Y_BOT)
    # 43~45 complex passage (R)
    b[43] = (7, X_R0, 147.0, X_R1, Y_BOT)
    b[44] = (7, X_R0, 147.0, X_R1, Y_BOT)
    b[45] = (7, X_R0, 147.0, X_R1, Y_BOT)

    return b


def get_b_boxes():
    """B형 45문항 (page_idx, x0, y0, x1, y1) 매핑"""
    b = {}
    # Page 1 (idx 0)
    b[1] = (0, X_L0, 147.0, X_L1, 458.7)
    b[2] = (0, X_L0, 458.7, X_L1, 615.6)
    b[3] = (0, X_L0, 615.6, X_L1, 774.4)
    b[4] = (0, X_L0, 774.4, X_L1, Y_BOT)
    # R: Q5 ~ Q12 (8 questions)
    r_splits_p1 = [147.0, 265.0, 380.7, 543.1, 671.2, 790.0, 890.0, 970.0, Y_BOT]
    for i in range(8):
        b[5 + i] = (0, X_R0, r_splits_p1[i], X_R1, r_splits_p1[i + 1])

    # Page 2 (idx 1)
    # L: Q13 ~ Q17 (5 questions)
    l_splits_p2 = [147.0, 302.0, 398.2, 575.3, 725.2, Y_BOT]
    for i in range(5):
        b[13 + i] = (1, X_L0, l_splits_p2[i], X_L1, l_splits_p2[i + 1])
    # R: Q18 ~ Q22 (5 questions)
    r_splits_p2 = [147.0, 324.8, 499.2, 691.9, 866.3, Y_BOT]
    for i in range(5):
        b[18 + i] = (1, X_R0, r_splits_p2[i], X_R1, r_splits_p2[i + 1])

    # Page 3 (idx 2)
    b[23] = (2, X_L0, 147.0, X_L1, 548.6)
    b[24] = (2, X_L0, 548.6, X_L1, Y_BOT)
    b[25] = (2, X_R0, 147.0, X_R1, 690.4)
    b[26] = (2, X_R0, 690.4, X_R1, Y_BOT)

    # Page 4 (idx 3)
    b[27] = (3, X_L0, 147.0, X_L1, 692.6)
    b[28] = (3, X_L0, 692.6, X_L1, Y_BOT)
    b[29] = (3, X_R0, 147.0, X_R1, 630.9)
    b[30] = (3, X_R0, 630.9, X_R1, Y_BOT)

    # Page 5 (idx 4)
    b[31] = (4, X_L0, 147.0, X_L1, 626.6)
    b[32] = (4, X_L0, 626.6, X_L1, Y_BOT)
    b[33] = (4, X_R0, 147.0, X_R1, 605.5)
    b[34] = (4, X_R0, 605.5, X_R1, Y_BOT)

    # Page 6 (idx 5)
    b[35] = (5, X_L0, 147.0, X_L1, 587.7)
    b[36] = (5, X_L0, 587.7, X_L1, Y_BOT)
    b[37] = (5, X_R0, 147.0, X_R1, 611.7)
    b[38] = (5, X_R0, 611.7, X_R1, Y_BOT)

    # Page 7 (idx 6)
    b[39] = (6, X_L0, 147.0, X_L1, 497.5)
    b[40] = (6, X_L0, 497.5, X_L1, Y_BOT)
    # Page 7 R: 41~42 complex passage
    b[41] = (6, X_R0, 147.0, X_R1, Y_BOT)
    b[42] = (6, X_R0, 147.0, X_R1, Y_BOT)

    # Page 8 (idx 7)
    # Page 8 L+R: 43~45 complex passage
    b[43] = (7, X_L0, 147.0, X_R1, Y_BOT)
    b[44] = (7, X_L0, 147.0, X_R1, Y_BOT)
    b[45] = (7, X_L0, 147.0, X_R1, Y_BOT)

    return b


def find_answer_highlight_rect(page, rect, ans_num):
    """
    rect 영역 내에서 정답 번호(1~5)의 위치를 감지하여 형광펜 칠할 Rect 반환
    """
    if not ans_num or not (1 <= ans_num <= 5):
        return None

    # 원문자
    circs = ["①", "②", "③", "④", "⑤"]
    target_circ = circs[ans_num - 1]
    
    # 1. 텍스트 검색 (있을 경우)
    found = page.search_for(target_circ, clip=rect)
    if found:
        return fitz.Rect(found[0].x0 - 2, found[0].y0 - 2, found[0].x1 + 2, found[0].y1 + 2)

    # 2. 텍스트 블록 기반 (선지 앞 x 좌표)
    blocks = [b for b in page.get_text("blocks", clip=rect) if b[4].strip()]
    blocks.sort(key=lambda b: b[1])
    
    # 선지 블록들 추정 (하단부에 위치)
    opt_blocks = [b for b in blocks if b[1] > (rect.y0 + rect.height * 0.4)]
    if len(opt_blocks) >= 5:
        # 각 선지 앞 x0 - 15pt 부근
        target_b = opt_blocks[ans_num - 1]
        x0 = max(rect.x0 + 5, target_b[0] - 18)
        y0 = target_b[1]
        return fitz.Rect(x0, y0, x0 + 14, y0 + 14)

    return None


def generate_crops_for_exam(exam_id: str, subtype: str) -> bool:
    pdf_path = PDF_A if subtype == "A형" else PDF_B
    if not os.path.exists(pdf_path):
        print(f"[ERR] PDF 파일이 없습니다: {pdf_path}")
        return False

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    ans_rows = cur.execute("SELECT q_num, answer_text FROM passages WHERE exam_id=?", (exam_id,)).fetchall()
    answers = {}
    for q_n, a_str in ans_rows:
        try:
            answers[q_n] = int(a_str)
        except Exception:
            answers[q_n] = 0

    boxes = get_a_boxes() if subtype == "A형" else get_b_boxes()
    doc = fitz.open(pdf_path)

    updated_count = 0
    # 41-42 및 43-45 캐시
    combined_cache = {}

    for q_num in range(1, 46):
        if q_num not in boxes:
            continue
        p_idx, x0, y0, x1, y1 = boxes[q_num]
        rect = fitz.Rect(x0, y0, x1, y1)

        out_fn = f"고3_2013_09_{subtype}_{q_num:02d}.png"
        out_path = os.path.join(CAPTURES_DIR, out_fn)
        rel_url = f"/static/captures/{out_fn}"

        # 41~42 통합 크롭
        if q_num in (41, 42):
            if "41_42" not in combined_cache:
                ans41 = answers.get(41, 0)
                ans42 = answers.get(42, 0)
                hl_list = []
                r41 = find_answer_highlight_rect(doc[p_idx], rect, ans41)
                r42 = find_answer_highlight_rect(doc[p_idx], rect, ans42)
                if r41: hl_list.append(r41)
                if r42: hl_list.append(r42)
                crop_rect_200dpi(doc, p_idx, rect, out_path, hl_list)
                combined_cache["41_42"] = rel_url
            cur.execute("UPDATE passages SET pdf_crop_image=? WHERE exam_id=? AND q_num=?", (combined_cache["41_42"], exam_id, q_num))
            updated_count += 1
            continue

        # 43~45 통합 크롭
        if q_num in (43, 44, 45):
            if "43_45" not in combined_cache:
                ans43 = answers.get(43, 0)
                ans44 = answers.get(44, 0)
                ans45 = answers.get(45, 0)
                hl_list = []
                r43 = find_answer_highlight_rect(doc[p_idx], rect, ans43)
                r44 = find_answer_highlight_rect(doc[p_idx], rect, ans44)
                r45 = find_answer_highlight_rect(doc[p_idx], rect, ans45)
                if r43: hl_list.append(r43)
                if r44: hl_list.append(r44)
                if r45: hl_list.append(r45)
                crop_rect_200dpi(doc, p_idx, rect, out_path, hl_list)
                combined_cache["43_45"] = rel_url
            cur.execute("UPDATE passages SET pdf_crop_image=? WHERE exam_id=? AND q_num=?", (combined_cache["43_45"], exam_id, q_num))
            updated_count += 1
            continue

        # 개별 문항
        ans_num = answers.get(q_num, 0)
        hl_rect = find_answer_highlight_rect(doc[p_idx], rect, ans_num)
        crop_rect_200dpi(doc, p_idx, rect, out_path, [hl_rect] if hl_rect else None)

        cur.execute("UPDATE passages SET pdf_crop_image=? WHERE exam_id=? AND q_num=?", (rel_url, exam_id, q_num))
        updated_count += 1

    conn.commit()
    conn.close()
    doc.close()
    print(f"[OK] {exam_id} ({subtype}): 45문항 크롭 및 DB 동기화 완료! ({updated_count}문항)")
    return True


if __name__ == "__main__":
    generate_crops_for_exam("[고3-2013년-09월-A형]", "A형")
    generate_crops_for_exam("[고3-2013년-09월-B형]", "B형")
