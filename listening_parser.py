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

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CAPTURES_DIR = os.path.join(BASE_DIR, "static", "captures")
os.makedirs(CAPTURES_DIR, exist_ok=True)


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
    answers_dict: Optional[Dict[int, str]] = None
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
        answers_dict=answers_dict
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
    listening_end_q: int = 17
) -> Dict[int, str]:
    """
    대본 PDF 또는 해설 PDF에서 각 듣기 문항의 대본(Script) 인쇄 영역만 고화질 크롭하여
    /static/captures/{grade}_{year}_{month:02d}_{q_num:02d}_script.png 로 저장
    
    반환: {1: "/static/captures/..._01_script.png", 2: ...}
    """
    if not os.path.exists(script_or_exp_pdf_path):
        return {}

    doc = fitz.open(script_or_exp_pdf_path)
    result_crops = {}

    q_pattern = re.compile(r"^\s*(\d{1,2})\s*\.(?:\s*(.*))?$")
    script_header_pattern = re.compile(r"(?:\[\s*대본\s*\]|【\s*대본\s*】|Script\b|\[Script\])", re.IGNORECASE)
    end_header_pattern = re.compile(r"(?:\[\s*해석\s*\]|【\s*해석\s*】|\[\s*해설\s*\]|【\s*해설\s*】|\[\s*어휘\s*\]|【\s*어휘\s*】)", re.IGNORECASE)

    # 해설 PDF의 경우 대본은 보통 앞쪽 1~4페이지 내에 위치
    max_scan_pages = min(len(doc), 6 if is_explanation_pdf else len(doc))

    for page_num in range(max_scan_pages):
        page = doc[page_num]
        rect = page.rect
        width, height = rect.width, rect.height

        # 페이지가 2단(좌/우 칼럼) 구조인지 판별
        mid_x = width / 2.0
        left_clip = fitz.Rect(30, 40, mid_x - 5, height - 35)
        right_clip = fitz.Rect(mid_x + 5, 40, width - 30, height - 35)

        # 칼럼 분할 분석
        for col_clip in [left_clip, right_clip]:
            raw_blocks = page.get_text("blocks", clip=col_clip)
            blocks = sorted(raw_blocks, key=lambda b: (b[1], b[0]))

            current_q = None
            script_recording = False
            script_rects = []

            for b in blocks:
                b_rect = fitz.Rect(b[0], b[1], b[2], b[3])
                b_text = b[4].strip()
                if not b_text:
                    continue

                # 문항 번호 확인 (예: 1., 2.)
                first_line = b_text.splitlines()[0].strip() if b_text.splitlines() else ""
                qm = q_pattern.match(first_line)

                if qm:
                    q_num = int(qm.group(1))
                    if listening_start_q <= q_num <= listening_end_q:
                        # 이전 문항 크롭 완료 저장
                        if current_q and script_rects:
                            _save_script_crop(doc, page_num, current_q, script_rects, grade, year, month, result_crops)
                            script_rects = []

                        current_q = q_num
                        # 단독 대본 PDF인 경우 문항 시작부터가 바로 대본
                        script_recording = not is_explanation_pdf
                        if script_recording:
                            script_rects.append(b_rect)
                        continue

                if current_q and listening_start_q <= current_q <= listening_end_q:
                    # 해설 PDF 모드인 경우 [대본] 헤더 시작 감지
                    if is_explanation_pdf:
                        if script_header_pattern.search(b_text):
                            script_recording = True
                            script_rects.append(b_rect)
                            continue
                        elif end_header_pattern.search(b_text):
                            script_recording = False
                            _save_script_crop(doc, page_num, current_q, script_rects, grade, year, month, result_crops)
                            script_rects = []
                            current_q = None
                            continue

                    if script_recording:
                        # M:, W: 대본 텍스트 블록 포함
                        script_rects.append(b_rect)

            # 칼럼 끝에서 진행 중인 문항 저장
            if current_q and script_rects:
                _save_script_crop(doc, page_num, current_q, script_rects, grade, year, month, result_crops)

    doc.close()
    return result_crops


def _save_script_crop(
    doc: fitz.Document,
    page_num: int,
    q_num: int,
    rects: List[fitz.Rect],
    grade: str,
    year: int,
    month: int,
    out_dict: Dict[int, str]
):
    """지정된 문항의 대본 영역 Bounding Box를 200 DPI로 캡처하여 저장"""
    if not rects:
        return

    page = doc[page_num]
    min_x = max(0, min(r.x0 for r in rects) - 6)
    min_y = max(0, min(r.y0 for r in rects) - 6)
    max_x = min(page.rect.width, max(r.x1 for r in rects) + 6)
    max_y = min(page.rect.height, max(r.y1 for r in rects) + 6)

    crop_rect = fitz.Rect(min_x, min_y, max_x, max_y)
    if crop_rect.width < 50 or crop_rect.height < 20:
        return

    img_filename = f"{grade}_{year}_{month:02d}_{q_num:02d}_script.png"
    img_filepath = os.path.join(CAPTURES_DIR, img_filename)
    web_url = f"/static/captures/{img_filename}"

    pix = page.get_pixmap(clip=crop_rect, dpi=200)
    pix.save(img_filepath)

    out_dict[q_num] = web_url


def sync_exam_listening(
    exam_id: str,
    script_pdf_path: Optional[str] = None,
    is_explanation_pdf: bool = False
) -> Dict[str, Any]:
    """
    특정 시험지에 대해 듣기 문항(1~17번) 자동 파싱 및 DB 동기화:
    1. uploads/ 내 해당 시험지의 PDF(문제지)와 HWP(해설지) 탐색
    2. HWP 해설에서 1~17번 정답, 해설, 영문 대본(script_text) 추출
    3. FELS 엔진을 통해 영문 대본을 FELS 텍스트(기능어 <괄호>)로 변환
    4. PDF 문제지에서 1~17번 고화질 크롭 이미지 생성
    5. 대본 PDF(또는 해설 PDF)가 주어지면 스크립트 크롭 이미지(_script.png) 생성
    6. passages 테이블에 area='listening'으로 문항 정보 등록/갱신
    """
    clean_id = exam_id.strip()
    if not clean_id.startswith("["):
        clean_id = f"[{clean_id}]"

    conn = db.get_connection()
    exam_row = conn.execute("SELECT * FROM exams WHERE id = ?", (clean_id,)).fetchone()
    if not exam_row:
        exam_row = conn.execute("SELECT * FROM exams WHERE id = ?", (clean_id.strip("[]"),)).fetchone()
    if not exam_row:
        raise ValueError(f"시험지를 찾을 수 없습니다: {clean_id}")

    grade = exam_row["grade"]
    year = exam_row["year"]
    month = exam_row["month"]
    start_q = exam_row["listening_start_q"] if "listening_start_q" in exam_row.keys() and exam_row["listening_start_q"] else 1
    end_q = exam_row["listening_end_q"] if "listening_end_q" in exam_row.keys() and exam_row["listening_end_q"] else 17

    uploads_dir = os.path.join(BASE_DIR, "uploads")
    pdf_files = [p for p in glob.glob(os.path.join(uploads_dir, f"{grade}_{year}_{month:02d}_*.pdf")) if "_ans_" not in p]
    if not pdf_files:
        pdf_files = [p for p in glob.glob(os.path.join(uploads_dir, f"*{year}*{month:02d}*.pdf")) if "_ans_" not in p]

    hwp_files = glob.glob(os.path.join(uploads_dir, f"{grade}_{year}_{month:02d}_*.hwp"))
    if not hwp_files:
        hwp_files = glob.glob(os.path.join(uploads_dir, f"*{year}*{month:02d}*.hwp"))

    explanations = {}
    if hwp_files:
        try:
            explanations = hwp_parser.parse_hwp_explanations(hwp_files[0])
        except Exception as e:
            print(f"[Sync Listening Warning] HWP 해설 파싱 실패: {e}")

    pdf_questions = {}
    if pdf_files:
        try:
            pdf_questions = extract_listening_question_crops(
                pdf_path=pdf_files[0],
                grade=grade,
                year=year,
                month=month,
                listening_start_q=start_q,
                listening_end_q=end_q
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
                listening_end_q=end_q
            )
        except Exception as e:
            print(f"[Sync Listening Warning] 대본 크롭 실패: {e}")

    saved_count = 0
    for q in range(start_q, end_q + 1):
        p_id = f"[{grade}-{year}년-{month:02d}월-{q:02d}번]"
        exp_info = explanations.get(q, {})
        ans_val = exp_info.get("answer", "")
        exp_text = exp_info.get("explanation", "")
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
            "question_type": "기타",
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
        "has_pdf": bool(pdf_files),
        "has_hwp": bool(hwp_files),
        "script_crops_count": len(script_crops)
    }

