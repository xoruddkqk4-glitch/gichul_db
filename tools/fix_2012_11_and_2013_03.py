import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import fitz
import pdf_parser
import sqlite3
from PIL import Image

sys.stdout.reconfigure(encoding='utf-8')

CAPTURES_DIR = "static/captures"
os.makedirs(CAPTURES_DIR, exist_ok=True)

CIRCLED = {1: '①', 2: '②', 3: '③', 4: '④', 5: '⑤'}
REVERSE_CIRCLED = {'①': 1, '②': 2, '③': 3, '④': 4, '⑤': 5, '1': 1, '2': 2, '3': 3, '4': 4, '5': 5}

def highlight_answer(page, rect, ans_num):
    if not ans_num or ans_num not in [1, 2, 3, 4, 5]:
        return None
    circ = CIRCLED[ans_num]
    hits = page.search_for(circ, clip=rect)
    if hits:
        hit = hits[0]
        annot = page.add_highlight_annot(fitz.Rect(hit.x0 - 2, hit.y0 - 2, hit.x1 + 2, hit.y1 + 2))
        annot.set_colors(stroke=(1.0, 0.91, 0.33)) # #FFE853
        annot.update()
        return annot
    return None

def crop_and_stack_a_exam(pdf_path, grade, year, month, subtype, answers, rect_left, rect_r_top, rect_r_bot):
    doc = fitz.open(pdf_path)
    page = doc[len(doc) - 1] # page 8
    zoom = 200 / 72.0
    mat = fitz.Matrix(zoom, zoom)

    annots = []
    for q, rect in [(41, rect_left), (42, rect_left), (43, rect_r_top), (44, rect_r_bot), (45, rect_r_bot)]:
        a = highlight_answer(page, rect, answers.get(q))
        if a: annots.append(a)

    # 1. 41~43 결합
    pix_left = page.get_pixmap(matrix=mat, clip=rect_left)
    pix_rtop = page.get_pixmap(matrix=mat, clip=rect_r_top)
    im_left = Image.frombytes("RGB", [pix_left.width, pix_left.height], pix_left.samples)
    im_rtop = Image.frombytes("RGB", [pix_rtop.width, pix_rtop.height], pix_rtop.samples)

    w_41_43 = max(im_left.width, im_rtop.width)
    h_41_43 = im_left.height + im_rtop.height + 25
    stacked_41_43 = Image.new("RGB", (w_41_43, h_41_43), (255, 255, 255))
    stacked_41_43.paste(im_left, ((w_41_43 - im_left.width) // 2, 0))
    stacked_41_43.paste(im_rtop, ((w_41_43 - im_rtop.width) // 2, im_left.height + 25))

    file_41 = f"{grade}_{year}_{month:02d}_{subtype}_41.png"
    stacked_41_43.save(os.path.join(CAPTURES_DIR, file_41))
    for q in [42, 43]:
        stacked_41_43.save(os.path.join(CAPTURES_DIR, f"{grade}_{year}_{month:02d}_{subtype}_{q}.png"))

    # 2. 44~45
    pix_rbot = page.get_pixmap(matrix=mat, clip=rect_r_bot)
    im_rbot = Image.frombytes("RGB", [pix_rbot.width, pix_rbot.height], pix_rbot.samples)
    file_44 = f"{grade}_{year}_{month:02d}_{subtype}_44.png"
    im_rbot.save(os.path.join(CAPTURES_DIR, file_44))
    im_rbot.save(os.path.join(CAPTURES_DIR, f"{grade}_{year}_{month:02d}_{subtype}_45.png"))

    for a in annots:
        page.delete_annot(a)
    doc.close()

    return f"/static/captures/{file_41}", f"/static/captures/{file_44}"

conn = sqlite3.connect('gichul.db')
c = conn.cursor()

# -------------------------------------------------------------
# 1. 고2-2012-11-A (A형)
# -------------------------------------------------------------
print("=== 1. 고2-2012-11-A 크롭 및 DB 갱신 ===")
ans_2012_11_a = {41: 2, 42: 3, 43: 3, 44: 2, 45: 2}
c41_a12, c44_a12 = crop_and_stack_a_exam(
    "uploads/고2_2012_11_고2-[2012-11-A].pdf",
    "고2", 2012, 11, "A형", ans_2012_11_a,
    fitz.Rect(75, 155, 420, 1065),
    fitz.Rect(424, 155, 760, 290),
    fitz.Rect(424, 320, 760, 1065)
)
print("  Generated crops:", c41_a12, c44_a12)

# DB 업데이트 (41~43은 1지문3문항, 44~45는 1지문2문항)
for q in [41, 42, 43]:
    c.execute("UPDATE passages SET question_type='1지문3문항', pdf_crop_image=? WHERE exam_id='[고2-2012년-11월]' AND q_num=?", (c41_a12, q))
for q in [44, 45]:
    c.execute("UPDATE passages SET question_type='1지문2문항', pdf_crop_image=? WHERE exam_id='[고2-2012년-11월]' AND q_num=?", (c44_a12, q))

# -------------------------------------------------------------
# 2. 고2-2013-03-A (A형)
# -------------------------------------------------------------
print("\n=== 2. 고2-2013-03-A 크롭 및 DB 갱신 ===")
ans_2013_03_a = {41: 4, 42: 3, 43: 5, 44: 5, 45: 2}
c41_a13, c44_a13 = crop_and_stack_a_exam(
    "uploads/고2_2013_03_고2-[2013-03-A].pdf",
    "고2", 2013, 3, "A형", ans_2013_03_a,
    fitz.Rect(55, 110, 295, 788),
    fitz.Rect(300, 110, 535, 205),
    fitz.Rect(300, 205, 535, 765)
)
print("  Generated crops:", c41_a13, c44_a13)

for q in [41, 42, 43]:
    c.execute("UPDATE passages SET question_type='1지문3문항', pdf_crop_image=? WHERE exam_id='[고2-2013년-03월]' AND q_num=?", (c41_a13, q))
for q in [44, 45]:
    c.execute("UPDATE passages SET question_type='1지문2문항', pdf_crop_image=? WHERE exam_id='[고2-2013년-03월]' AND q_num=?", (c44_a13, q))

# -------------------------------------------------------------
# 3. 고2-2012-11-B (B형 정답표 및 크롭 갱신)
# -------------------------------------------------------------
print("\n=== 3. 고2-2012-11-B 정답표 및 크롭 갱신 ===")
B_ANS_2012_11 = {
    1: '②', 2: '④', 3: '③', 4: '①', 5: '③', 6: '①', 7: '④', 8: '①', 9: '⑤', 10: '④',
    11: '③', 12: '①', 13: '⑤', 14: '③', 15: '⑤', 16: '③', 17: '③', 18: '②', 19: '①', 20: '①',
    21: '④', 22: '④', 23: '④', 24: '②', 25: '②', 26: '②', 27: '④', 28: '⑤', 29: '④', 30: '③',
    31: '①', 32: '③', 33: '①', 34: '①', 35: '③', 36: '⑤', 37: '⑤', 38: '③', 39: '⑤', 40: '②',
    41: '②', 42: '①', 43: '②', 44: '⑤', 45: '⑤'
}

doc_b12 = fitz.open("uploads/고2_2012_11_고2-[2012-11-B].pdf")
c41_b12 = pdf_parser.crop_and_merge_41_42(doc_b12, "고2", 2012, 11, B_ANS_2012_11, "B형")
c43_b12 = pdf_parser.crop_and_merge_43_45(doc_b12, "고2", 2012, 11, B_ANS_2012_11, "B형")
doc_b12.close()

for q_num, ans_sym in B_ANS_2012_11.items():
    if q_num in [41, 42]:
        c.execute("UPDATE passages SET answer_text=?, question_type='1지문2문항', pdf_crop_image=?, answer_verified=1 WHERE exam_id='[고2-2012년-11월-B형]' AND q_num=?", (ans_sym, c41_b12, q_num))
    elif q_num in [43, 44, 45]:
        c.execute("UPDATE passages SET answer_text=?, question_type='1지문3문항', pdf_crop_image=?, answer_verified=1 WHERE exam_id='[고2-2012년-11월-B형]' AND q_num=?", (ans_sym, c43_b12, q_num))
    else:
        c.execute("UPDATE passages SET answer_text=?, answer_verified=1 WHERE exam_id='[고2-2012년-11월-B형]' AND q_num=?", (ans_sym, q_num))

# -------------------------------------------------------------
# 4. 고2-2013-03-B (B형 정답표 및 크롭 갱신)
# -------------------------------------------------------------
print("\n=== 4. 고2-2013-03-B 정답표 및 크롭 갱신 ===")
B_ANS_2013_03 = {
    1: '①', 2: '②', 3: '②', 4: '①', 5: '③', 6: '⑤', 7: '①', 8: '④', 9: '⑤', 10: '①',
    11: '④', 12: '④', 13: '④', 14: '③', 15: '④', 16: '⑤', 17: '②', 18: '①', 19: '②', 20: '②',
    21: '⑤', 22: '⑤', 23: '②', 24: '④', 25: '②', 26: '②', 27: '④', 28: '⑤', 29: '④', 30: '③',
    31: '②', 32: '③', 33: '④', 34: '③', 35: '①', 36: '③', 37: '①', 38: '⑤', 39: '③', 40: '①',
    41: '④', 42: '⑤', 43: '③', 44: '⑤', 45: '③'
}

doc_b13 = fitz.open("uploads/고2_2013_03_고2-[2013-03-B].pdf")
c41_b13 = pdf_parser.crop_and_merge_41_42(doc_b13, "고2", 2013, 3, B_ANS_2013_03, "B형")
c43_b13 = pdf_parser.crop_and_merge_43_45(doc_b13, "고2", 2013, 3, B_ANS_2013_03, "B형")
doc_b13.close()

for q_num, ans_sym in B_ANS_2013_03.items():
    if q_num in [41, 42]:
        c.execute("UPDATE passages SET answer_text=?, question_type='1지문2문항', pdf_crop_image=?, answer_verified=1 WHERE exam_id='[고2-2013년-03월-B형]' AND q_num=?", (ans_sym, c41_b13, q_num))
    elif q_num in [43, 44, 45]:
        c.execute("UPDATE passages SET answer_text=?, question_type='1지문3문항', pdf_crop_image=?, answer_verified=1 WHERE exam_id='[고2-2013년-03월-B형]' AND q_num=?", (ans_sym, c43_b13, q_num))
    else:
        c.execute("UPDATE passages SET answer_text=?, answer_verified=1 WHERE exam_id='[고2-2013년-03월-B형]' AND q_num=?", (ans_sym, q_num))

conn.commit()
conn.close()
print("\n=== 모든 DB 갱신 및 고화질 크롭 이미지 생성 완료! ===")
