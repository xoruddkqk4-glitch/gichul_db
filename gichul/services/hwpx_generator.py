"""
05-gichul_db: 교사용 B4 단면 2문항 HWPX 유인물 생성 엔진 (hwpx_generator.py)
- 개방형 HWPX(ZIP+XML) 포맷을 순수 Python(zipfile, xml.etree.ElementTree)으로 고속 파싱/조립
- B4 단면 가로 2단 레이아웃 (1페이지 = 2개 문항, 좌단/우단 배치)
- 사용자 지정 문항 번호(custom_q_num) 반영
- 문제지: 출처 배제, 발문 + 지문 본문 + 선지(①~⑤) + 정답 노란색 형광펜 하이라이트
- 해설지: 사용자 지정 번호 + 원출처 명시, 지문 결과 화면 좌측 하단 패널(explanation_text) 텍스트 주입
- 머리말(Header) / 꼬리말(Footer) 동적 입력값 주입
- 문제지 / 해설지 개별 HWPX 및 ZIP 일괄 패키징 스트리밍 지원
"""

import os
import re
import io
import copy
import zipfile
import xml.etree.ElementTree as ET
from typing import List, Dict, Any, Optional, Tuple

from ..logging_config import get_logger
from ..text_utils import extract_choices, extract_answer_num, clean_hwp_glitches
from ..paths import HANDOUT_TEMPLATES_DIR, CUSTOM_TEMPLATES_DIR

logger = get_logger("gichul.hwpx_generator")

# 템플릿 보관 디렉토리 (기본 내장 템플릿: static/data/templates, 사용자 업로드: uploads/templates)
os.makedirs(HANDOUT_TEMPLATES_DIR, exist_ok=True)
os.makedirs(CUSTOM_TEMPLATES_DIR, exist_ok=True)

DEFAULT_QUESTION_TEMPLATE = "default_b4_question.hwpx"
DEFAULT_EXPLANATION_TEMPLATE = "default_b4_explanation.hwpx"

# HWPX XML 네임스페이스
NS_HP = "http://www.hancom.co.kr/hwpml/2011/paragraph"
NS_HS = "http://www.hancom.co.kr/hwpml/2011/section"
NS_HH = "http://www.hancom.co.kr/hwpml/2011/head"
NS_HC = "http://www.hancom.co.kr/hwpml/2011/core"

ET.register_namespace("hp", NS_HP)
ET.register_namespace("hs", NS_HS)
ET.register_namespace("hh", NS_HH)
ET.register_namespace("hc", NS_HC)

# 원문자 맵
CIRCLE_NUMS = {1: "①", 2: "②", 3: "③", 4: "④", 5: "⑤"}


def get_template_path(template_name: Optional[str] = None, is_explanation: bool = False) -> str:
    """사용할 HWPX 템플릿의 절대 경로 반환"""
    if template_name:
        bname = os.path.basename(template_name)
        # 1. 사용자 업로드 템플릿 폴더 우선 확인
        custom_path = os.path.join(CUSTOM_TEMPLATES_DIR, bname)
        if os.path.exists(custom_path):
            return custom_path
        # 2. 기본 내장 템플릿 폴더 확인
        builtin_path = os.path.join(HANDOUT_TEMPLATES_DIR, bname)
        if os.path.exists(builtin_path):
            return builtin_path

    default_name = DEFAULT_EXPLANATION_TEMPLATE if is_explanation else DEFAULT_QUESTION_TEMPLATE
    default_path = os.path.join(HANDOUT_TEMPLATES_DIR, default_name)
    if os.path.exists(default_path):
        return default_path

    # 대체 파일명 지원 (하이픈 <-> 언더스코어 상호 호환 지원)
    alt_name = default_name.replace("_", "-") if "_" in default_name else default_name.replace("-", "_")
    alt_path = os.path.join(HANDOUT_TEMPLATES_DIR, alt_name)
    if os.path.exists(alt_path):
        return alt_path

    fallback_path = os.path.join(HANDOUT_TEMPLATES_DIR, "default_b4_template.hwpx")
    if os.path.exists(fallback_path):
        return fallback_path

    raise FileNotFoundError(f"HWPX 템플릿 파일을 찾을 수 없습니다: {default_name}")


def list_templates() -> List[Dict[str, Any]]:
    """등록된 템플릿 파일 목록 조회 (기본 내장 static/data/templates + 사용자 업로드 uploads/templates)"""
    templates = []
    seen_files = set()

    # 1. 기본 내장 템플릿 (static/data/templates)
    if os.path.exists(HANDOUT_TEMPLATES_DIR):
        for fname in os.listdir(HANDOUT_TEMPLATES_DIR):
            if fname.lower().endswith(".hwpx") and fname not in seen_files:
                seen_files.add(fname)
                fpath = os.path.join(HANDOUT_TEMPLATES_DIR, fname)
                stat = os.stat(fpath)
                templates.append({
                    "filename": fname,
                    "name": "기본 B4 문제지 양식" if fname in (DEFAULT_QUESTION_TEMPLATE, "default_b4-question.hwpx") else (
                        "기본 B4 해설지 양식" if fname in (DEFAULT_EXPLANATION_TEMPLATE, "default_b4-explanation.hwpx") else fname
                    ),
                    "is_default": True,
                    "size_kb": round(stat.st_size / 1024, 1),
                    "updated_at": stat.st_mtime,
                })

    # 2. 사용자 업로드 템플릿 (uploads/templates)
    if os.path.exists(CUSTOM_TEMPLATES_DIR):
        for fname in os.listdir(CUSTOM_TEMPLATES_DIR):
            if fname.lower().endswith(".hwpx") and fname not in seen_files:
                seen_files.add(fname)
                fpath = os.path.join(CUSTOM_TEMPLATES_DIR, fname)
                stat = os.stat(fpath)
                templates.append({
                    "filename": fname,
                    "name": fname,
                    "is_default": False,
                    "size_kb": round(stat.st_size / 1024, 1),
                    "updated_at": stat.st_mtime,
                })

    return sorted(templates, key=lambda x: (not x["is_default"], x["name"]))


def save_uploaded_template(filename: str, file_bytes: bytes) -> str:
    """선생님이 업로드한 커스텀 HWPX 양식 검증 및 저장 (uploads/templates/)"""
    # 1. HWPX/ZIP 구조 기본 검증
    try:
        with zipfile.ZipFile(io.BytesIO(file_bytes), "r") as zf:
            namelist = zf.namelist()
            if not any(n.startswith("Contents/section") for n in namelist):
                raise ValueError("올바른 HWPX 문서가 아닙니다. (Contents/section XML 부재)")
    except Exception as e:
        raise ValueError(f"유효하지 않은 HWPX 파일입니다: {e}")

    # 2. 안전한 파일명으로 uploads/templates 에 저장
    clean_name = re.sub(r'[^a-zA-Z0-9가-힣_\-\.]', '_', filename)
    if not clean_name.lower().endswith(".hwpx"):
        clean_name += ".hwpx"

    save_path = os.path.join(CUSTOM_TEMPLATES_DIR, clean_name)
    with open(save_path, "wb") as f:
        f.write(file_bytes)

    logger.info("새 HWPX 템플릿 저장 완료 (uploads/templates): %s (%d bytes)", clean_name, len(file_bytes))
    return clean_name


def _clean_passage_body_and_title(passage_text: str, question_title: str) -> Tuple[str, str, Dict[int, str]]:
    """지문 텍스트에서 발문 제목, 순수 영문 본문, 선지 1~5번 분리"""
    p_text = clean_hwp_glitches(passage_text or "").strip()
    q_title = clean_hwp_glitches(question_title or "").strip()

    # 선지 추출
    choices = extract_choices(p_text)

    # 발문 제목 정리 (기존 18. 번호 형태 분리)
    clean_title = q_title
    if not clean_title and p_text:
        # 첫 줄이 발문인 경우 탐색
        first_line = p_text.splitlines()[0].strip()
        if re.match(r"^\s*\d{1,2}\s*[\.\)]", first_line):
            clean_title = first_line

    # 발문에서 원래 번호(예: '18. ', '21) ') 제거하여 순수 발문 본문만 추출
    m_num = re.match(r"^\s*\d{1,2}\s*[\.\)]\s*(.*)$", clean_title)
    if m_num:
        pure_title_body = m_num.group(1).strip()
    else:
        pure_title_body = clean_title

    # 본문 추출: 발문 부분 제거
    body = p_text
    if clean_title and body.startswith(clean_title):
        body = body[len(clean_title):].strip()
    else:
        body = re.sub(r"^\s*\d{1,2}\s*[\.\)]\s*[^\n]+\n*", "", body).strip()

    # 본문에서 선지 부분 제거 (첫 번째 원문자 ① 이전까지만 본문으로 취득)
    p1 = body.rfind("①")
    if p1 != -1 and len(choices) >= 2:
        body = body[:p1].strip()

    return pure_title_body, body, choices


def _inject_char_properties(hdr_root: ET.Element) -> Tuple[str, str]:
    """header.xml 에 일반 텍스트용 charPr과 노란색 형광펜용 charPr 등록 (ID 반환)"""
    cps = hdr_root.find(f".//{{{NS_HH}}}charProperties")
    if cps is None:
        return "0", "0"

    # 기존 charPr 확인
    normal_id = "0"
    highlight_id = "99"

    # 혹시 이미 99가 있으면 새 ID 생성
    existing_ids = {cp.get("id") for cp in cps.findall(f"{{{NS_HH}}}charPr")}
    if highlight_id in existing_ids:
        highlight_id = str(max([int(x) for x in existing_ids if x.isdigit()] + [100]) + 1)

    # 0번 charPr 복제하여 노란색 음영(shadeColor="#FFFF00") 추가
    cp0 = cps.find(f"{{{NS_HH}}}charPr")
    if cp0 is not None:
        cp_high = copy.deepcopy(cp0)
        cp_high.set("id", highlight_id)
        cp_high.set("shadeColor", "#FFFF00")
        cps.append(cp_high)
        cps.set("itemCnt", str(int(cps.get("itemCnt", "7")) + 1))

    return normal_id, highlight_id


def _create_paragraph(
    text: str = "",
    char_pr_id: str = "0",
    page_break: bool = False,
    column_break: bool = False,
    bold: bool = False,
    highlight: bool = False,
    para_pr_id: str = "0"
) -> ET.Element:
    """HWPX 문단(<hp:p>) 엘리먼트 생성 헬퍼"""
    p = ET.Element(f"{{{NS_HP}}}p", {
        "id": str(abs(hash(text + str(page_break) + str(column_break) + str(os.urandom(4)))) % 2000000000),
        "paraPrIDRef": para_pr_id,
        "styleIDRef": "0",
        "pageBreak": "1" if page_break else "0",
        "columnBreak": "1" if column_break else "0",
        "merged": "0",
    })

    if text:
        run = ET.SubElement(p, f"{{{NS_HP}}}run", {"charPrIDRef": char_pr_id})
        if highlight:
            ET.SubElement(run, f"{{{NS_HP}}}markPenBegin", {"color": "#FFFF00"})
        t = ET.SubElement(run, f"{{{NS_HP}}}t")
        t.text = text
        if highlight:
            ET.SubElement(run, f"{{{NS_HP}}}markPenEnd")

    return p


def _extract_and_populate_header_table(
    first_p: Optional[ET.Element],
    normal_char_id: str,
    h_left: str,
    h_center: str,
    h_right: str
) -> Tuple[Optional[ET.Element], Optional[ET.Element]]:
    """first_p 에서 secPr run과 상단 1x3 표 run을 추출하고 텍스트(왼쪽 상단, 가운데 상단, 오른쪽 상단)를 주입"""
    sec_run = None
    tbl_run = None
    if first_p is not None:
        for r in first_p.findall(f"{{{NS_HP}}}run"):
            if r.find(f"{{{NS_HP}}}secPr") is not None:
                sec_run = r
            if r.find(f".//{{{NS_HP}}}tbl") is not None and tbl_run is None:
                tbl_run = r

    if tbl_run is not None:
        tbl = tbl_run.find(f".//{{{NS_HP}}}tbl")
        if tbl is not None:
            for tc in tbl.findall(f".//{{{NS_HP}}}tc"):
                addr = tc.find(f".//{{{NS_HP}}}cellAddr")
                if addr is None:
                    continue
                col = addr.get("colAddr")
                val = ""
                if col == "0":
                    val = h_left
                elif col == "1":
                    val = h_center
                elif col == "2":
                    val = h_right

                t_elems = tc.findall(f".//{{{NS_HP}}}t")
                for i, t in enumerate(t_elems):
                    t.text = val if i == 0 else ""
                # 글자 모양을 일반 검은색 폰트로 정규화
                for r in tc.findall(f".//{{{NS_HP}}}run"):
                    if r.get("charPrIDRef") in ("30", "31", "32", "27", "28"):
                        r.set("charPrIDRef", normal_char_id)

    return sec_run, tbl_run


def generate_question_handout(items: List[Dict[str, Any]], options: Optional[Dict[str, Any]] = None) -> bytes:
    """
    선택한 문항 목록으로 B4 단면 2문항 문제지 HWPX 문서 생성
    - options:
        - header_title: 머리말 제목
        - header_sub: 머리말 소제목
        - footer_text: 꼬리말
        - highlight_answer: 정답 형광펜 표시 여부 (기본 True)
        - template_name: 사용자 선택 템플릿 파일명
    """
    options = options or {}
    template_path = get_template_path(options.get("template_name"), is_explanation=False)
    header_left = options.get("header_left", "").strip()
    header_center = options.get("header_center", "").strip() or options.get("header_title", "").strip()
    header_right = options.get("header_right", "").strip() or options.get("header_sub", "").strip()
    footer_text = options.get("footer_text", "").strip()
    highlight_answer = bool(options.get("highlight_answer", True))

    with zipfile.ZipFile(template_path, "r") as zf:
        file_map = {name: zf.read(name) for name in zf.namelist()}

    # 1. header.xml 수정 (형광펜 charPr 등록)
    hdr_root = ET.fromstring(file_map["Contents/header.xml"])
    normal_char_id, highlight_char_id = _inject_char_properties(hdr_root)
    file_map["Contents/header.xml"] = ET.tostring(hdr_root, encoding="utf-8", xml_declaration=True)

    # 2. section0.xml 파싱 및 본문 조립
    sec0_root = ET.fromstring(file_map["Contents/section0.xml"])

    # 첫 문단(secPr 및 상단 1x3 표 보관용) 확인
    first_p = sec0_root.find(f"{{{NS_HP}}}p")
    sec_run, tbl_run = _extract_and_populate_header_table(
        first_p, normal_char_id, header_left, header_center, header_right
    )

    # 기존 문단 비우기
    sec0_root.clear()

    # secPr과 상단 1x3 표를 담은 첫 문단 재구성
    new_first_p = ET.SubElement(sec0_root, f"{{{NS_HP}}}p", {
        "id": "1000000001",
        "paraPrIDRef": "0",
        "styleIDRef": "0",
        "pageBreak": "0",
        "columnBreak": "0",
        "merged": "0",
    })
    if sec_run is not None:
        new_first_p.append(sec_run)
    else:
        ET.SubElement(new_first_p, f"{{{NS_HP}}}run", {"charPrIDRef": normal_char_id})

    if tbl_run is not None:
        new_first_p.append(tbl_run)
        # 상단 표 아래 공백 문단 추가
        sec0_root.append(_create_paragraph(""))
    else:
        # 상단 표가 없는 템플릿의 경우 텍스트로 폴백
        if header_center:
            sec0_root.append(_create_paragraph(f"■ {header_center}", char_pr_id=normal_char_id))
        if header_right:
            sec0_root.append(_create_paragraph(f"  ({header_right})", char_pr_id=normal_char_id))
        if header_center or header_right:
            sec0_root.append(_create_paragraph(""))

    # 문항들 순회 (1페이지당 2개 문항: 좌단 1문항, 우단 1문항)
    total_q = len(items)
def _parse_passage_source_parts(item: Dict[str, Any]) -> Tuple[str, str, str, str]:
    """지문 데이터에서 기출 메타데이터 (년도, 학년, 월, 번호) 문자열 추출"""
    raw_id = item.get("id", "").strip("[]")
    m = re.search(r"(고[123]|중[123])?-?(\d{4})년?-?(\d{1,2})월?-?(\d{1,2})번?", raw_id)
    if m:
        grade = m.group(1) or str(item.get("grade") or "")
        year = m.group(2) or str(item.get("year") or "")
        month = m.group(3) or str(item.get("month") or "")
        q_num = m.group(4) or str(item.get("q_num") or "")
    else:
        grade = str(item.get("grade") or "")
        year = str(item.get("year") or "")
        month = str(item.get("month") or "")
        q_num = str(item.get("q_num") or "")

    year_str = f"{year}년" if year and not year.endswith("년") else (year or "-")
    grade_str = grade or "-"
    month_str = f"{month}월" if month and not month.endswith("월") else (month or "-")
    q_num_str = f"{q_num}번" if q_num and not q_num.endswith("번") else (q_num or "-")
    return year_str, grade_str, month_str, q_num_str


def _extract_source_table_template(sec0_root: ET.Element) -> Optional[ET.Element]:
    """해설지 템플릿에서 1행 4열 기출 출처 표 엘리먼트를 deepcopy하여 추출"""
    for tbl in sec0_root.findall(f".//{{{NS_HP}}}tbl"):
        if tbl.get("rowCnt") == "1" and tbl.get("colCnt") == "4":
            return copy.deepcopy(tbl)
    return None


def _create_source_table_paragraph(
    template_tbl: Optional[ET.Element],
    year: str,
    grade: str,
    month: str,
    qnum: str,
    normal_char_id: str
) -> ET.Element:
    """1행 4열 출처 표를 담은 <hp:p paraPrIDRef='24'> 문단 생성"""
    p = ET.Element(f"{{{NS_HP}}}p", {
        "id": str(abs(hash(f"src_tbl_{year}_{grade}_{month}_{qnum}_{os.urandom(4)}")) % 2000000000),
        "paraPrIDRef": "24",
        "styleIDRef": "0",
        "pageBreak": "0",
        "columnBreak": "0",
        "merged": "0",
    })

    if template_tbl is not None:
        tbl = copy.deepcopy(template_tbl)
        values = {"0": year, "1": grade, "2": month, "3": qnum}
        for tc in tbl.findall(f".//{{{NS_HP}}}tc"):
            addr = tc.find(f".//{{{NS_HP}}}cellAddr")
            if addr is None:
                continue
            col = addr.get("colAddr")
            val = values.get(col, "")
            t_elems = tc.findall(f".//{{{NS_HP}}}t")
            for i, t in enumerate(t_elems):
                t.text = val if i == 0 else ""
            for r in tc.findall(f".//{{{NS_HP}}}run"):
                r.set("charPrIDRef", normal_char_id)

        run = ET.SubElement(p, f"{{{NS_HP}}}run", {"charPrIDRef": normal_char_id})
        run.append(tbl)
    else:
        # 폴백: 표가 없는 경우 텍스트 박스로 생성
        run = ET.SubElement(p, f"{{{NS_HP}}}run", {"charPrIDRef": normal_char_id})
        t = ET.SubElement(run, f"{{{NS_HP}}}t")
        t.text = f"[출처: {year} {grade} {month} {qnum}]"

    return p


def generate_question_handout(items: List[Dict[str, Any]], options: Optional[Dict[str, Any]] = None) -> bytes:
    """
    선택한 문항 목록으로 B4 단면 2문항 문제지 HWPX 문서 생성
    - 발문(paraPr 26), 지문 본문(paraPr 35 양쪽정렬), 선지(paraPr 35)
    - 홀수 문항 후 columnBreak=1, 짝수 문항 후 pageBreak=1 다페이지 레이아웃
    """
    options = options or {}
    template_path = get_template_path(options.get("template_name"), is_explanation=False)
    header_left = options.get("header_left", "").strip()
    header_center = options.get("header_center", "").strip() or options.get("header_title", "").strip()
    header_right = options.get("header_right", "").strip() or options.get("header_sub", "").strip()
    footer_text = options.get("footer_text", "").strip()
    highlight_answer = bool(options.get("highlight_answer", True))

    with zipfile.ZipFile(template_path, "r") as zf:
        file_map = {name: zf.read(name) for name in zf.namelist()}

    # 1. header.xml 처리 (형광펜 charPr 등록)
    hdr_root = ET.fromstring(file_map["Contents/header.xml"])
    normal_char_id, highlight_char_id = _inject_char_properties(hdr_root)
    file_map["Contents/header.xml"] = ET.tostring(hdr_root, encoding="utf-8", xml_declaration=True)

    # 2. section0.xml 파싱
    sec0_root = ET.fromstring(file_map["Contents/section0.xml"])

    first_p = sec0_root.find(f"{{{NS_HP}}}p")
    sec_run, tbl_run = _extract_and_populate_header_table(
        first_p, normal_char_id, header_left, header_center, header_right
    )

    sec0_root.clear()

    # 첫 단락: secPr 과 tbl_run 주입
    new_first_p = ET.SubElement(sec0_root, f"{{{NS_HP}}}p", {
        "id": "1000000001",
        "paraPrIDRef": "0",
        "styleIDRef": "0",
        "pageBreak": "0",
        "columnBreak": "0",
        "merged": "0",
    })
    if sec_run is not None:
        new_first_p.append(sec_run)
    else:
        ET.SubElement(new_first_p, f"{{{NS_HP}}}run", {"charPrIDRef": normal_char_id})

    if tbl_run is not None:
        new_first_p.append(tbl_run)
        sec0_root.append(_create_paragraph("", para_pr_id="26"))
    else:
        if header_center:
            sec0_root.append(_create_paragraph(f"■ {header_center}", char_pr_id=normal_char_id, para_pr_id="26"))
        if header_right:
            sec0_root.append(_create_paragraph(f"  ({header_right})", char_pr_id=normal_char_id, para_pr_id="26"))
        if header_center or header_right:
            sec0_root.append(_create_paragraph("", para_pr_id="26"))

    # 문항들 순회 (1페이지당 2개 문항: 좌단 1문항, 우단 1문항)
    total_q = len(items)
    for idx, item in enumerate(items):
        pos_in_page = (idx % 2)  # 0: 좌측단, 1: 우측단
        is_last_item = (idx == total_q - 1)

        custom_q_num = str(item.get("custom_q_num", idx + 1)).strip() or str(idx + 1)
        q_title = item.get("question_title", "")
        p_text = item.get("passage_text", "")
        ans_text = item.get("answer_text", "")
        ans_num = extract_answer_num(ans_text)

        pure_title, body_text, choices = _clean_passage_body_and_title(p_text, q_title)

        # 1) 발문 문단: [사용자 지정 번호]. [발문] (paraPr 26)
        full_title_text = f"{custom_q_num}. {pure_title}" if pure_title else f"{custom_q_num}. 다음 글을 읽고 물음에 답하시오."
        sec0_root.append(_create_paragraph(full_title_text, char_pr_id=normal_char_id, para_pr_id="26"))
        sec0_root.append(_create_paragraph("", para_pr_id="26"))  # 공백 행

        # 2) 지문 본문 문단 (줄 단위로 문단 생성, paraPr 35 양쪽정렬 승계)
        if body_text:
            body_lines = [line.strip() for line in body_text.splitlines() if line.strip()]
            for bline in body_lines:
                sec0_root.append(_create_paragraph(bline, char_pr_id=normal_char_id, para_pr_id="35"))
        else:
            sec0_root.append(_create_paragraph("(지문 본문이 비어 있습니다.)", char_pr_id=normal_char_id, para_pr_id="35"))

        sec0_root.append(_create_paragraph("", para_pr_id="35"))  # 선지 전 공백 행

        # 3) 선지 문단 (① ~ ⑤, paraPr 35)
        if choices:
            for c_idx in range(1, 6):
                c_text = choices.get(c_idx, "").strip()
                if not c_text:
                    continue
                circ = CIRCLE_NUMS.get(c_idx, f"({c_idx})")
                is_correct = (highlight_answer and ans_num == c_idx)

                choice_p = ET.Element(f"{{{NS_HP}}}p", {
                    "id": str(abs(hash(f"{custom_q_num}_{c_idx}_{os.urandom(4)}")) % 2000000000),
                    "paraPrIDRef": "35",
                    "styleIDRef": "0",
                    "pageBreak": "0",
                    "columnBreak": "0",
                    "merged": "0",
                })

                if is_correct:
                    c_run_num = ET.SubElement(choice_p, f"{{{NS_HP}}}run", {"charPrIDRef": highlight_char_id})
                    ET.SubElement(c_run_num, f"{{{NS_HP}}}markPenBegin", {"color": "#FFFF00"})
                    t_num = ET.SubElement(c_run_num, f"{{{NS_HP}}}t")
                    t_num.text = circ
                    ET.SubElement(c_run_num, f"{{{NS_HP}}}markPenEnd")
                    c_run_txt = ET.SubElement(choice_p, f"{{{NS_HP}}}run", {"charPrIDRef": normal_char_id})
                    t_txt = ET.SubElement(c_run_txt, f"{{{NS_HP}}}t")
                    t_txt.text = f" {c_text}"
                else:
                    c_run = ET.SubElement(choice_p, f"{{{NS_HP}}}run", {"charPrIDRef": normal_char_id})
                    t_all = ET.SubElement(c_run, f"{{{NS_HP}}}t")
                    t_all.text = f"{circ} {c_text}"

                sec0_root.append(choice_p)

        # 4) 문항 간 구분 및 단/페이지 나눔 제어
        if not is_last_item:
            if pos_in_page == 0:
                # 좌측단 문항 완료 -> 우측단으로 나눔 (columnBreak=1)
                sec0_root.append(_create_paragraph("", column_break=True, para_pr_id="26"))
            else:
                # 우측단 문항 완료 -> 다음 페이지로 나눔 (pageBreak=1)
                sec0_root.append(_create_paragraph("", page_break=True, para_pr_id="26"))
        else:
            if pos_in_page == 0:
                sec0_root.append(_create_paragraph("", column_break=True, para_pr_id="26"))
                sec0_root.append(_create_paragraph("[ 오답 정리 및 메모란 ]", char_pr_id=normal_char_id, para_pr_id="26"))
                for _ in range(8):
                    sec0_root.append(_create_paragraph("", para_pr_id="26"))

    # 꼬리말 안내 텍스트가 있으면 문서 끝에 삽입
    if footer_text:
        sec0_root.append(_create_paragraph("", para_pr_id="26"))
        sec0_root.append(_create_paragraph(f"[{footer_text}]", char_pr_id=normal_char_id, para_pr_id="26"))

    file_map["Contents/section0.xml"] = ET.tostring(sec0_root, encoding="utf-8", xml_declaration=True)

    out_buf = io.BytesIO()
    with zipfile.ZipFile(out_buf, "w", compression=zipfile.ZIP_DEFLATED) as zf_out:
        for fname, fcontent in file_map.items():
            zf_out.writestr(fname, fcontent)

    return out_buf.getvalue()


def generate_explanation_handout(items: List[Dict[str, Any]], options: Optional[Dict[str, Any]] = None) -> bytes:
    """
    선택한 문항 목록으로 B4 단면 2문항 해설지 HWPX 문서 생성
    - 템플릿의 1행 4열 기출 출처 표(년도|학년|월|번호) 보존 및 데이터 주입
    - 정답 및 문항 번호(paraPr 25), 해설 본문(paraPr 27 양쪽정렬) 승계
    - 홀수 문항 후 columnBreak=1, 짝수 문항 후 pageBreak=1 다페이지 레이아웃
    """
    options = options or {}
    template_path = get_template_path(options.get("template_name"), is_explanation=True)
    header_left = options.get("header_left", "").strip()
    header_center = options.get("header_center", "").strip() or options.get("header_title", "").strip() or "정답 및 해설"
    header_right = options.get("header_right", "").strip() or options.get("header_sub", "").strip()
    footer_text = options.get("footer_text", "").strip()

    with zipfile.ZipFile(template_path, "r") as zf:
        file_map = {name: zf.read(name) for name in zf.namelist()}

    # 1. header.xml 처리
    hdr_root = ET.fromstring(file_map["Contents/header.xml"])
    normal_char_id, highlight_char_id = _inject_char_properties(hdr_root)
    file_map["Contents/header.xml"] = ET.tostring(hdr_root, encoding="utf-8", xml_declaration=True)

    # 2. section0.xml 파싱
    sec0_root = ET.fromstring(file_map["Contents/section0.xml"])

    # 1행 4열 출처 표 템플릿 추출 (삭제 전 보관)
    source_tbl_template = _extract_source_table_template(sec0_root)

    first_p = sec0_root.find(f"{{{NS_HP}}}p")
    sec_run, tbl_run = _extract_and_populate_header_table(
        first_p, normal_char_id, header_left, header_center, header_right
    )

    sec0_root.clear()

    new_first_p = ET.SubElement(sec0_root, f"{{{NS_HP}}}p", {
        "id": "2000000001",
        "paraPrIDRef": "0",
        "styleIDRef": "0",
        "pageBreak": "0",
        "columnBreak": "0",
        "merged": "0",
    })
    if sec_run is not None:
        new_first_p.append(sec_run)
    else:
        ET.SubElement(new_first_p, f"{{{NS_HP}}}run", {"charPrIDRef": normal_char_id})

    if tbl_run is not None:
        new_first_p.append(tbl_run)
        sec0_root.append(_create_paragraph("", para_pr_id="24"))
    else:
        if header_center:
            sec0_root.append(_create_paragraph(f"■ {header_center}", char_pr_id=normal_char_id, para_pr_id="24"))
        if header_right:
            sec0_root.append(_create_paragraph(f"  ({header_right})", char_pr_id=normal_char_id, para_pr_id="24"))
        if header_center or header_right:
            sec0_root.append(_create_paragraph("", para_pr_id="24"))

    total_q = len(items)
    for idx, item in enumerate(items):
        pos_in_page = (idx % 2)
        is_last_item = (idx == total_q - 1)

        custom_q_num = str(item.get("custom_q_num", idx + 1)).strip() or str(idx + 1)
        ans_text = (item.get("answer_text") or "").strip()
        ans_clean = extract_answer_num(ans_text)
        ans_display = CIRCLE_NUMS.get(ans_clean, ans_text or "-")

        # 1) 1행 4열 기출 출처 표 주입 (년도 | 학년 | 월 | 번호)
        y_str, g_str, m_str, q_str = _parse_passage_source_parts(item)
        src_p = _create_source_table_paragraph(source_tbl_template, y_str, g_str, m_str, q_str, normal_char_id)
        sec0_root.append(src_p)
        sec0_root.append(_create_paragraph("", para_pr_id="24"))  # 공백 행

        # 2) 문항 번호 및 정답 표시 (paraPr 25: 14pt 진하게)
        ans_line = f"{custom_q_num}번. [정답] {ans_display}"
        sec0_root.append(_create_paragraph(ans_line, char_pr_id=normal_char_id, para_pr_id="25"))
        sec0_root.append(_create_paragraph("", para_pr_id="20"))

        # 3) 해설 텍스트 본문 (paraPr 27: 14pt 양쪽정렬)
        exp_text = item.get("explanation_text") or "해설 정보가 등록되지 않았습니다."
        exp_lines = [line.rstrip() for line in exp_text.splitlines()]

        for eline in exp_lines:
            if not eline.strip():
                sec0_root.append(_create_paragraph("", para_pr_id="20"))
                continue
            sec0_root.append(_create_paragraph(eline, char_pr_id=normal_char_id, para_pr_id="27"))

        sec0_root.append(_create_paragraph("", para_pr_id="20"))

        # 4) 단 및 페이지 나눔
        if not is_last_item:
            if pos_in_page == 0:
                sec0_root.append(_create_paragraph("", column_break=True, para_pr_id="25"))
            else:
                sec0_root.append(_create_paragraph("", page_break=True, para_pr_id="25"))
        else:
            if pos_in_page == 0:
                sec0_root.append(_create_paragraph("", column_break=True, para_pr_id="25"))
                sec0_root.append(_create_paragraph("[ 메모 및 참고사항 ]", char_pr_id=normal_char_id, para_pr_id="25"))

    if footer_text:
        sec0_root.append(_create_paragraph(""))
        sec0_root.append(_create_paragraph(f"[{footer_text}]", char_pr_id=normal_char_id))

    file_map["Contents/section0.xml"] = ET.tostring(sec0_root, encoding="utf-8", xml_declaration=True)

    out_buf = io.BytesIO()
    with zipfile.ZipFile(out_buf, "w", compression=zipfile.ZIP_DEFLATED) as zf_out:
        for fname, fcontent in file_map.items():
            zf_out.writestr(fname, fcontent)

    return out_buf.getvalue()


def generate_handout_zip(items: List[Dict[str, Any]], options: Optional[Dict[str, Any]] = None) -> bytes:
    """문제지 HWPX와 해설지 HWPX를 하나로 묶은 ZIP 아카이브 바이너리 반환"""
    options = options or {}
    q_bytes = generate_question_handout(items, options)
    
    # 해설지 옵션 복사 및 머리말 보정
    exp_options = dict(options)
    if "header_title" in exp_options and exp_options["header_title"]:
        if not "해설" in exp_options["header_title"]:
            exp_options["header_title"] = f"{exp_options['header_title']} (정답 및 해설)"
    e_bytes = generate_explanation_handout(items, exp_options)

    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("문제지_B4_유인물.hwpx", q_bytes)
        zf.writestr("해설지_B4_유인물.hwpx", e_bytes)

    return zip_buf.getvalue()
