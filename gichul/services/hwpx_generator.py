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
import math
import zipfile
import xml.etree.ElementTree as ET
from typing import List, Dict, Any, Optional, Tuple

from ..logging_config import get_logger
from ..text_utils import extract_choices, extract_answer_num, clean_hwp_glitches
from ..fels_engine import generate_fels_text, generate_fels_blank
from ..paths import HANDOUT_TEMPLATES_DIR, CUSTOM_TEMPLATES_DIR, UPLOADS_DIR

logger = get_logger("gichul.hwpx_generator")

# 템플릿 보관 디렉토리 (기본 내장 템플릿: static/data/templates, 사용자 업로드: uploads/templates)
os.makedirs(HANDOUT_TEMPLATES_DIR, exist_ok=True)
os.makedirs(CUSTOM_TEMPLATES_DIR, exist_ok=True)

DEFAULT_QUESTION_TEMPLATE = "default_b4_question.hwpx"
DEFAULT_EXPLANATION_TEMPLATE = "default_b4_explanation.hwpx"
DEFAULT_SENTENCE_TEMPLATE = "default_a4_sentence.hwpx"
DEFAULT_LISTENING_QUESTION_TEMPLATE = "listening_b4_question.hwpx"
DEFAULT_LISTENING_EXPLANATION_TEMPLATE = "listening_b4_explanation.hwpx"

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
    default_name = DEFAULT_EXPLANATION_TEMPLATE if is_explanation else DEFAULT_QUESTION_TEMPLATE

    # 템플릿명이 비어있거나, 해설지 생성인데 문제지 기본양식이 전달된 경우 (또는 반대) 올바른 기본 양식으로 교정
    effective_name = template_name
    if is_explanation:
        if not effective_name or effective_name in (DEFAULT_QUESTION_TEMPLATE, "default_b4-question.hwpx", "default_b4_template.hwpx"):
            effective_name = default_name
    else:
        if not effective_name or effective_name in (DEFAULT_EXPLANATION_TEMPLATE, "default_b4-explanation.hwpx", "default_b4_template.hwpx"):
            effective_name = default_name

    if effective_name:
        bname = os.path.basename(effective_name)
        # 1. 사용자 업로드 템플릿 폴더 우선 확인
        custom_path = os.path.join(CUSTOM_TEMPLATES_DIR, bname)
        if os.path.exists(custom_path):
            return custom_path
        # 2. 기본 내장 템플릿 폴더 확인
        builtin_path = os.path.join(HANDOUT_TEMPLATES_DIR, bname)
        if os.path.exists(builtin_path):
            return builtin_path
        # 대체 파일명 지원 (하이픈 <-> 언더스코어 상호 호환 지원)
        alt_bname = bname.replace("_", "-") if "_" in bname else bname.replace("-", "_")
        alt_builtin = os.path.join(HANDOUT_TEMPLATES_DIR, alt_bname)
        if os.path.exists(alt_builtin):
            return alt_builtin

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


def get_listening_template_path(template_name: Optional[str] = None, is_explanation: bool = False) -> str:
    """사용할 듣기 유인물 HWPX 템플릿의 절대 경로 반환"""
    default_name = DEFAULT_LISTENING_EXPLANATION_TEMPLATE if is_explanation else DEFAULT_LISTENING_QUESTION_TEMPLATE

    effective_name = template_name
    if is_explanation:
        if not effective_name or effective_name in (DEFAULT_LISTENING_QUESTION_TEMPLATE, "listening_b4-question.hwpx"):
            effective_name = default_name
    else:
        if not effective_name or effective_name in (DEFAULT_LISTENING_EXPLANATION_TEMPLATE, "listening_b4-explanation.hwpx"):
            effective_name = default_name

    if effective_name:
        bname = os.path.basename(effective_name)
        custom_path = os.path.join(CUSTOM_TEMPLATES_DIR, bname)
        if os.path.exists(custom_path):
            return custom_path
        builtin_path = os.path.join(HANDOUT_TEMPLATES_DIR, bname)
        if os.path.exists(builtin_path):
            return builtin_path
        alt_bname = bname.replace("_", "-") if "_" in bname else bname.replace("-", "_")
        alt_builtin = os.path.join(HANDOUT_TEMPLATES_DIR, alt_bname)
        if os.path.exists(alt_builtin):
            return alt_builtin

    default_path = os.path.join(HANDOUT_TEMPLATES_DIR, default_name)
    if os.path.exists(default_path):
        return default_path

    alt_name = default_name.replace("_", "-") if "_" in default_name else default_name.replace("-", "_")
    alt_path = os.path.join(HANDOUT_TEMPLATES_DIR, alt_name)
    if os.path.exists(alt_path):
        return alt_path

    raise FileNotFoundError(f"듣기 HWPX 템플릿 파일을 찾을 수 없습니다: {default_name}")


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
                        "기본 B4 해설지 양식" if fname in (DEFAULT_EXPLANATION_TEMPLATE, "default_b4-explanation.hwpx") else (
                            "기본 A4 문장 유인물 양식" if fname in (DEFAULT_SENTENCE_TEMPLATE, "default_a4-sentence.hwpx") else (
                                "기본 B4 듣기 문제지 양식" if fname in (DEFAULT_LISTENING_QUESTION_TEMPLATE, "listening_b4-question.hwpx") else (
                                    "기본 B4 듣기 해설지 양식" if fname in (DEFAULT_LISTENING_EXPLANATION_TEMPLATE, "listening_b4-explanation.hwpx") else fname
                                )
                            )
                        )
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


def _clean_borders_and_boxes(hdr_root: ET.Element):
    """
    header.xml 에서 녹색 테두리(#35A434, borderFill id=10 등) 및 불필요한 문단 테두리를 제거/무력화하여
    해설지나 문제지에 녹색 상자나 원치 않는 테두리가 출력되지 않도록 처리
    """
    # 1. borderFill 중 초록색 테두리(#35A434) 또는 id="10"인 항목의 모든 테두리를 NONE으로 변경
    for bf in hdr_root.findall(f".//{{{NS_HH}}}borderFill"):
        bf_id = bf.get("id")
        is_green = False
        for border_tag in ("leftBorder", "rightBorder", "topBorder", "bottomBorder"):
            b_elem = bf.find(f"{{{NS_HH}}}{border_tag}")
            if b_elem is not None:
                color = b_elem.get("color", "").upper()
                if "35A434" in color or bf_id == "10":
                    is_green = True
                    b_elem.set("type", "NONE")
                    b_elem.set("width", "0.1 mm")
                    b_elem.set("color", "#000000")
        if is_green or bf_id == "10":
            diag = bf.find(f"{{{NS_HH}}}diagonal")
            if diag is not None:
                diag.set("type", "NONE")

    # 2. paraPr 중 borderFillIDRef="10"을 참조하는 문단 테두리를 투명(borderFillIDRef="1")으로 변경
    for pp in hdr_root.findall(f".//{{{NS_HH}}}paraPr"):
        b_elem = pp.find(f"{{{NS_HH}}}border")
        if b_elem is not None and b_elem.get("borderFillIDRef") == "10":
            b_elem.set("borderFillIDRef", "1")


def _inject_char_properties(
    hdr_root: ET.Element,
    font_size_pt: int = 13,
    is_explanation: bool = False
) -> Tuple[str, str]:
    """
    header.xml 에 일반 본문용 charPr과 정답 형광펜용 charPr 등록 (ID 반환)
    - font_size_pt: 글자 크기 pt (문제지: 13pt -> 1300, 해설지: 11pt -> 1100 등)
    - bold 태그를 제거하여 본문이 볼드체로 인쇄되지 않도록 보장
    - 형광펜용 charPr에는 노란색 음영(shadeColor="#FFFF00") 주입
    """
    cps = hdr_root.find(f".//{{{NS_HH}}}charProperties")
    if cps is None:
        return "0", "0"

    # 기존 charPr id 확인
    existing_ids = {int(cp.get("id")) for cp in cps.findall(f"{{{NS_HH}}}charPr") if cp.get("id", "").isdigit()}
    max_id = max(existing_ids) if existing_ids else 100

    normal_char_id = str(max_id + 1)
    highlight_char_id = str(max_id + 2)

    # 0번 charPr (또는 첫 charPr) 가져오기
    cp0 = cps.find(f"{{{NS_HH}}}charPr")
    if cp0 is not None:
        # cp0 자체에서도 볼드 태그 제거 (기본 서식 볼드화 방지)
        b0 = cp0.find(f"{{{NS_HH}}}bold")
        if b0 is not None:
            cp0.remove(b0)

        # 돋움 폰트 id 탐색 (기본값 '1')
        dotum_id = "1"
        fontfaces = hdr_root.find(f".//{{{NS_HH}}}fontfaces")
        if fontfaces is not None:
            for ff in fontfaces.findall(f".//{{{NS_HH}}}fontface"):
                if ff.get("lang") == "HANGUL":
                    for f in ff.findall(f".//{{{NS_HH}}}font"):
                        if "돋움" in (f.get("face") or ""):
                            dotum_id = f.get("id") or "1"
                            break

        # 1) 일반 본문용 charPr: 지정된 pt 크기, 볼드 없음, 검은색 글자, 돋움체 강제
        cp_norm = copy.deepcopy(cp0)
        cp_norm.set("id", normal_char_id)
        cp_norm.set("height", str(font_size_pt * 100))
        cp_norm.set("textColor", "#000000")
        cp_norm.set("shadeColor", "none")
        b_norm = cp_norm.find(f"{{{NS_HH}}}bold")
        if b_norm is not None:
            cp_norm.remove(b_norm)
        fn_norm = cp_norm.find(f".//{{{NS_HH}}}fontRef")
        if fn_norm is not None:
            for k in list(fn_norm.attrib.keys()):
                fn_norm.set(k, dotum_id)
        cps.append(cp_norm)

        # 2) 형광펜용 charPr: 지정된 pt 크기, 볼드 없음, 노란색 음영(#FFFF00), 돋움체 강제
        cp_high = copy.deepcopy(cp0)
        cp_high.set("id", highlight_char_id)
        cp_high.set("height", str(font_size_pt * 100))
        cp_high.set("textColor", "#000000")
        cp_high.set("shadeColor", "#FFFF00")
        b_high = cp_high.find(f"{{{NS_HH}}}bold")
        if b_high is not None:
            cp_high.remove(b_high)
        fn_high = cp_high.find(f".//{{{NS_HH}}}fontRef")
        if fn_high is not None:
            for k in list(fn_high.attrib.keys()):
                fn_high.set(k, dotum_id)
        cps.append(cp_high)

        cps.set("itemCnt", str(len(cps.findall(f"{{{NS_HH}}}charPr"))))
    else:
        normal_char_id = "0"
        highlight_char_id = "99"

    # header.xml 내 빨간색(#FF0000) 플레이스홀더 글자색을 검은색으로 정규화 및 볼드 제거
    for cp in cps.findall(f"{{{NS_HH}}}charPr"):
        if cp.get("textColor", "").upper() == "#FF0000":
            cp.set("textColor", "#000000")
            b_red = cp.find(f"{{{NS_HH}}}bold")
            if b_red is not None:
                cp.remove(b_red)

    return normal_char_id, highlight_char_id


def _calc_text_effective_width(text: str) -> float:
    """텍스트의 유효 글자 폭(한글/전각=1.0, 영문/숫자/기호/공백=0.45~0.55) 계산"""
    units = 0.0
    for ch in (text or ""):
        if ('\uac00' <= ch <= '\ud7a3') or ('\u1100' <= ch <= '\u11ff') or ('\u4e00' <= ch <= '\u9fff'):
            units += 1.0
        elif ch in (' ', '\t'):
            units += 0.45
        elif ch in ('(', ')', '[', ']', '{', '}', ':', '-', '_', '.', ','):
            units += 0.4
        else:
            units += 0.55
    return max(units, 1.0)


def _get_dynamic_header_font_size(col_type: str, text: str) -> Tuple[int, int, int]:
    """
    머리말 텍스트 길이에 맞춰 셀 영역(높이/너비)을 벗어나지 않도록 동적 글자 크기, 장평, 자간 계산
    col_type: 'left' | 'center' | 'right'
    반환값: (height in 1/100 pt, ratio in %, spacing in %)
    """
    text = (text or "").strip()
    if not text:
        if col_type == "center":
            return (950, 100, 0)
        return (1000, 100, 0)

    units = _calc_text_effective_width(text)

    if col_type == "center":
        # 가운데 셀: 1x1 고정 테두리 박스 (가용너비 약 160pt, 셀 높이 약 18.5pt)
        # 상하 테두리가 머리말 밑줄을 침범하지 않도록 최대 10.5pt로 제한하고 길이에 따라 정밀 축소
        if units <= 6.0:
            return (1050, 100, 0)       # 10.5pt (매우 짧은 과목명)
        elif units <= 9.0:
            return (950, 98, -2)        # 9.5pt ('세계 문화와 영어' 등 8~9자)
        elif units <= 13.0:
            return (850, 95, -4)        # 8.5pt
        elif units <= 18.0:
            return (780, 93, -6)        # 7.8pt
        else:
            return (700, 90, -8)        # 7.0pt

    elif col_type == "right":
        # 오른쪽 셀: 가용너비 약 155pt, 줄바꿈(2줄 밀림) 방지가 최우선!
        # '2 학년 (  )반 (  )번 이름: (          )' -> 약 18~22 유닛
        if units <= 8.0:
            return (950, 100, 0)        # 9.5pt
        elif units <= 12.0:
            return (850, 98, -2)        # 8.5pt
        elif units <= 16.0:
            return (780, 95, -4)        # 7.8pt
        elif units <= 22.0:
            return (720, 92, -6)        # 7.2pt (긴 학년/반/번호/이름도 단 1줄에 쏙!)
        elif units <= 28.0:
            return (650, 88, -8)        # 6.5pt
        else:
            return (600, 85, -10)       # 6.0pt

    else:  # 'left'
        # 왼쪽 셀: 학교명 등
        if units <= 8.0:
            return (1000, 100, 0)       # 10.0pt ('홍대부여고' 등)
        elif units <= 13.0:
            return (900, 98, -2)        # 9.0pt
        elif units <= 18.0:
            return (800, 95, -4)        # 8.0pt
        else:
            return (720, 92, -6)        # 7.2pt


def _register_header_char_pr(
    hdr_root: ET.Element,
    height: int,
    ratio: int = 100,
    spacing: int = 0,
    bold: bool = False,
    base_char_id: str = "7"
) -> str:
    """header.xml의 charProperties에 지정된 크기/장평/자간의 charPr 등록 후 ID 반환"""
    cps = hdr_root.find(f".//{{{NS_HH}}}charProperties")
    if cps is None:
        return base_char_id

    existing_ids = {int(cp.get("id")) for cp in cps.findall(f"{{{NS_HH}}}charPr") if cp.get("id", "").isdigit()}
    new_id = str(max(existing_ids) + 1) if existing_ids else "60"

    base_cp = None
    for cp in cps.findall(f"{{{NS_HH}}}charPr"):
        if cp.get("id") == base_char_id:
            base_cp = cp
            break
    if base_cp is None:
        base_cp = cps.find(f"{{{NS_HH}}}charPr")

    new_cp = copy.deepcopy(base_cp) if base_cp is not None else ET.Element(f"{{{NS_HH}}}charPr")
    new_cp.set("id", new_id)
    new_cp.set("height", str(height))
    new_cp.set("textColor", "#000000")
    new_cp.set("shadeColor", "none")

    # 볼드 설정
    b_tag = new_cp.find(f"{{{NS_HH}}}bold")
    if bold:
        if b_tag is None:
            ET.SubElement(new_cp, f"{{{NS_HH}}}bold")
    else:
        if b_tag is not None:
            new_cp.remove(b_tag)

    # 장평 (ratio)
    ratio_tag = new_cp.find(f"{{{NS_HH}}}ratio")
    if ratio_tag is not None:
        for k in ratio_tag.attrib:
            ratio_tag.set(k, str(ratio))

    # 자간 (spacing)
    spacing_tag = new_cp.find(f"{{{NS_HH}}}spacing")
    if spacing_tag is not None:
        for k in spacing_tag.attrib:
            spacing_tag.set(k, str(spacing))

    cps.append(new_cp)
    cps.set("itemCnt", str(len(cps.findall(f"{{{NS_HH}}}charPr"))))
    return new_id


def _create_compact_header_para_pr(
    hdr_root: ET.Element,
    align_type: str = "CENTER",
    line_spacing: int = 130
) -> str:
    """머리말 박스 높이 초과를 방지하는 콤팩트 paraPr 등록 후 ID 반환"""
    pps = hdr_root.find(f".//{{{NS_HH}}}paraProperties")
    if pps is None:
        return "13"

    existing_ids = {int(pp.get("id")) for pp in pps.findall(f"{{{NS_HH}}}paraPr") if pp.get("id", "").isdigit()}
    new_id = str(max(existing_ids) + 1) if existing_ids else "60"

    base_pp = None
    for pp in pps.findall(f"{{{NS_HH}}}paraPr"):
        if pp.get("id") in ("13", "3", "15"):
            base_pp = pp
            break
    if base_pp is None:
        base_pp = pps.find(f"{{{NS_HH}}}paraPr")

    new_pp = copy.deepcopy(base_pp) if base_pp is not None else ET.Element(f"{{{NS_HH}}}paraPr")
    new_pp.set("id", new_id)

    # 정렬
    align_tag = new_pp.find(f"{{{NS_HH}}}align")
    if align_tag is not None:
        align_tag.set("horizontal", align_type)

    # 줄간격 콤팩트화 (120~130%)
    for ls in new_pp.iter(f"{{{NS_HH}}}lineSpacing"):
        ls.set("value", str(line_spacing))

    # 단락 위/아래 여백 제거
    margin_tag = new_pp.find(f"{{{NS_HH}}}margin")
    if margin_tag is not None:
        margin_tag.set("top", "0")
        margin_tag.set("bottom", "0")

    pps.append(new_pp)
    pps.set("itemCnt", str(len(pps.findall(f"{{{NS_HH}}}paraPr"))))
    return new_id


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
    # 빈 줄인 경우 테두리가 들어갈 가능성이 있는 para_pr_id(20, 21 등)를 안전한 '0'으로 정규화
    clean_para_pr_id = "0" if (not text and para_pr_id in ("20", "21")) else para_pr_id

    p = ET.Element(f"{{{NS_HP}}}p", {
        "id": str(abs(hash(text + str(page_break) + str(column_break) + str(os.urandom(4)))) % 2000000000),
        "paraPrIDRef": clean_para_pr_id,
        "styleIDRef": "0",
        "pageBreak": "1" if page_break else "0",
        "columnBreak": "1" if column_break else "0",
        "merged": "0",
    })

    if text:
        run = ET.SubElement(p, f"{{{NS_HP}}}run", {"charPrIDRef": char_pr_id})
        t = ET.SubElement(run, f"{{{NS_HP}}}t")
        t.text = text

    return p


def _extract_and_populate_header_table(
    first_p: Optional[ET.Element],
    normal_char_id: str,
    h_left: str,
    h_center: str,
    h_right: str,
    hdr_root: Optional[ET.Element] = None
) -> Tuple[Optional[ET.Element], Optional[ET.Element]]:
    """first_p 에서 secPr run과 상단 1x3 표 run을 추출하고 동적 글자 크기로 텍스트 주입"""
    sec_run = None
    tbl_run = None
    if first_p is not None:
        for r in first_p.findall(f"{{{NS_HP}}}run"):
            if r.find(f"{{{NS_HP}}}secPr") is not None:
                sec_run = copy.deepcopy(r)
            if (r.find(f".//{{{NS_HP}}}header") is not None or r.find(f".//{{{NS_HP}}}tbl") is not None) and tbl_run is None:
                tbl_run = copy.deepcopy(r)

    if tbl_run is not None:
        # 해설지 템플릿의 P0에 header run 직하위 본문 1x4 표가 붙어있는 경우 중복/중첩 방지를 위해 제거
        for direct_tbl in tbl_run.findall(f"{{{NS_HP}}}tbl"):
            tbl_run.remove(direct_tbl)

        tbl = tbl_run.find(f".//{{{NS_HP}}}tbl")
        if tbl is not None:
            # 동적 글자 크기 charPr 사전 등록 (hdr_root 가 주어진 경우)
            char_map = {}
            if hdr_root is not None:
                lh, lr, ls = _get_dynamic_header_font_size("left", h_left)
                char_map["0"] = _register_header_char_pr(hdr_root, lh, lr, ls, bold=False, base_char_id=normal_char_id)

                ch, cr, cs = _get_dynamic_header_font_size("center", h_center)
                char_map["1"] = _register_header_char_pr(hdr_root, ch, cr, cs, bold=True, base_char_id=normal_char_id)

                rh, rr, rs = _get_dynamic_header_font_size("right", h_right)
                char_map["2"] = _register_header_char_pr(hdr_root, rh, rr, rs, bold=False, base_char_id=normal_char_id)

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
                    # 가운데 셀 상하 여백을 줄여 테두리 박스가 아래 구분선을 침범하지 않도록 보호
                    cm = tc.find(f".//{{{NS_HP}}}cellMargin")
                    if cm is not None:
                        cm.set("top", "20")
                        cm.set("bottom", "20")
                elif col == "2":
                    val = h_right

                t_elems = tc.findall(f".//{{{NS_HP}}}t")
                for i, t in enumerate(t_elems):
                    t.text = val if i == 0 else ""

                target_char_id = char_map.get(col, normal_char_id)
                # 글자 모양을 동적 검은색 폰트로 교체
                for r in tc.findall(f".//{{{NS_HP}}}run"):
                    r.set("charPrIDRef", target_char_id)

    return sec_run, tbl_run


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


def _clean_explanation_lines(exp_text: str) -> List[str]:
    """
    해설 본문 텍스트의 선두에 중복으로 포함된 정답 표기(예: '[정답] ⑤', '⑤' 등) 및 불필요한 공백 행을 제거.
    유인물 상단에 이미 '{custom_q_num}번. [정답] {ans_display}'가 표시되므로 중복 표기를 방지.
    """
    raw_lines = [line.rstrip() for line in (exp_text or "").splitlines()]
    idx = 0
    while idx < len(raw_lines):
        line = raw_lines[idx].strip()
        if not line:
            idx += 1
            continue
        # [정답] ⑤, 정답: ⑤, 【정답】 ⑤ 등 정답 단독 표기 라인
        is_ans_header = bool(re.match(r"^(\[|【)?\s*정답\s*(\]|】)?\s*[:：]?\s*([①-⑤\d]+|\([1-5]\))?\s*$", line))
        # ⑤, (5), 1 등 단독 번호 표기 라인
        is_bare_num = bool(re.match(r"^([①-⑤]|\([1-5]\)|[1-5])$", line))

        if is_ans_header or is_bare_num:
            idx += 1
            continue
        break

    while idx < len(raw_lines) and not raw_lines[idx].strip():
        idx += 1

    return raw_lines[idx:]


def _create_source_table_run(
    template_tbl: Optional[ET.Element],
    year: str,
    grade: str,
    month: str,
    qnum: str,
    normal_char_id: str
) -> ET.Element:
    """1행 4열 기출 출처 표를 담은 <hp:run> 엘리먼트 생성 (셀 텍스트 세로 가운데 정렬 유지)"""
    run_id = str(abs(hash(f"src_tbl_{year}_{grade}_{month}_{qnum}_{os.urandom(4)}")) % 2000000000)
    run = ET.Element(f"{{{NS_HP}}}run", {"charPrIDRef": normal_char_id})

    if template_tbl is not None:
        tbl = copy.deepcopy(template_tbl)
        # 1) 표 자체에 고유 ID 부여
        tbl.set("id", str(abs(hash(f"tbl_{run_id}_{os.urandom(4)}")) % 2000000000))

        values = {"0": year, "1": grade, "2": month, "3": qnum}
        for tc_idx, tc in enumerate(tbl.findall(f".//{{{NS_HP}}}tc")):
            addr = tc.find(f".//{{{NS_HP}}}cellAddr")
            col = addr.get("colAddr") if addr is not None else str(tc_idx)
            val = values.get(col, "")

            # 2) 셀 내부를 OWPML 표준의 깨끗한 단일 문단 구조로 재구성
            # subList의 vertAlign="CENTER" 속성을 유지하여 텍스트 세로 가운데 정렬 보장
            subList = tc.find(f"{{{NS_HP}}}subList")
            if subList is not None:
                orig_p = subList.find(f"{{{NS_HP}}}p")
                cell_para_pr_id = orig_p.get("paraPrIDRef", "22") if orig_p is not None else "22"

                subList.set("vertAlign", "CENTER")
                for child in list(subList):
                    subList.remove(child)

                cell_p = ET.SubElement(subList, f"{{{NS_HP}}}p", {
                    "id": str(abs(hash(f"cell_p_{run_id}_{tc_idx}_{os.urandom(4)}")) % 2000000000),
                    "paraPrIDRef": cell_para_pr_id,
                    "styleIDRef": "0",
                    "pageBreak": "0",
                    "columnBreak": "0",
                    "merged": "0"
                })
                cell_run = ET.SubElement(cell_p, f"{{{NS_HP}}}run", {"charPrIDRef": normal_char_id})
                t_elem = ET.SubElement(cell_run, f"{{{NS_HP}}}t")
                t_elem.text = val

        run.append(tbl)
    else:
        t = ET.SubElement(run, f"{{{NS_HP}}}t")
        t.text = f"[출처: {year} {grade} {month} {qnum}]"

    return run


def _create_source_table_paragraph(
    template_tbl: Optional[ET.Element],
    year: str,
    grade: str,
    month: str,
    qnum: str,
    normal_char_id: str
) -> ET.Element:
    """1행 4열 출처 표를 담은 <hp:p paraPrIDRef='24'> 문단 생성"""
    p_id = str(abs(hash(f"src_tbl_p_{year}_{grade}_{month}_{qnum}_{os.urandom(4)}")) % 2000000000)
    p = ET.Element(f"{{{NS_HP}}}p", {
        "id": p_id,
        "paraPrIDRef": "24",
        "styleIDRef": "0",
        "pageBreak": "0",
        "columnBreak": "0",
        "merged": "0",
    })
    run = _create_source_table_run(template_tbl, year, grade, month, qnum, normal_char_id)
    p.append(run)
    return p


def generate_question_handout(items: List[Dict[str, Any]], options: Optional[Dict[str, Any]] = None) -> bytes:
    """
    선택한 문항 목록으로 B4 단면 2문항 문제지 HWPX 문서 생성
    - 글자 크기 13 pt 고정 (height="1300")
    - 본문 기본 텍스트 볼드체 해제 (non-bold)
    - 정답 선지 번호 노란색 형광펜 하이라이트 (charPr shadeColor #FFFF00 음영)
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

    # 1. header.xml 처리 (13pt 글자크기, non-bold, 형광펜 charPr 등록 및 테두리 정리)
    hdr_root = ET.fromstring(file_map["Contents/header.xml"])
    _clean_borders_and_boxes(hdr_root)
    normal_char_id, highlight_char_id = _inject_char_properties(hdr_root, font_size_pt=13, is_explanation=False)

    # 2. section0.xml 파싱
    sec0_root = ET.fromstring(file_map["Contents/section0.xml"])

    first_p = sec0_root.find(f"{{{NS_HP}}}p")
    sec_run, tbl_run = _extract_and_populate_header_table(
        first_p, normal_char_id, header_left, header_center, header_right, hdr_root=hdr_root
    )

    file_map["Contents/header.xml"] = ET.tostring(hdr_root, encoding="utf-8", xml_declaration=True)

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
        sec0_root.append(_create_paragraph("", para_pr_id="0"))
    else:
        if header_center:
            sec0_root.append(_create_paragraph(f"■ {header_center}", char_pr_id=normal_char_id, para_pr_id="26"))
        if header_right:
            sec0_root.append(_create_paragraph(f"  ({header_right})", char_pr_id=normal_char_id, para_pr_id="26"))
        if header_center or header_right:
            sec0_root.append(_create_paragraph("", para_pr_id="0"))

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

        # 1) 발문 문단: [사용자 지정 번호]. [발문] (13pt, non-bold, paraPr 26)
        full_title_text = f"{custom_q_num}. {pure_title}" if pure_title else f"{custom_q_num}. 다음 글을 읽고 물음에 답하시오."
        sec0_root.append(_create_paragraph(full_title_text, char_pr_id=normal_char_id, para_pr_id="26"))
        sec0_root.append(_create_paragraph("", para_pr_id="0"))  # 공백 행

        # 2) 지문 본문 문단 (줄 단위로 문단 생성, 13pt, non-bold, paraPr 35 양쪽정렬 승계)
        if body_text:
            body_lines = [line.strip() for line in body_text.splitlines() if line.strip()]
            for bline in body_lines:
                sec0_root.append(_create_paragraph(bline, char_pr_id=normal_char_id, para_pr_id="35"))
        else:
            sec0_root.append(_create_paragraph("(지문 본문이 비어 있습니다.)", char_pr_id=normal_char_id, para_pr_id="35"))

        sec0_root.append(_create_paragraph("", para_pr_id="0"))  # 선지 전 공백 행

        # 3) 선지 문단 (① ~ ⑤, 13pt, non-bold, paraPr 35)
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
                    # 정답 번호에 노란색 음영(shadeColor="#FFFF00") 스타일 적용 (OWPML 표준)
                    c_run_num = ET.SubElement(choice_p, f"{{{NS_HP}}}run", {"charPrIDRef": highlight_char_id})
                    t_num = ET.SubElement(c_run_num, f"{{{NS_HP}}}t")
                    t_num.text = circ

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
                sec0_root.append(_create_paragraph("", column_break=True, para_pr_id="0"))
            else:
                # 우측단 문항 완료 -> 다음 페이지로 나눔 (pageBreak=1)
                sec0_root.append(_create_paragraph("", page_break=True, para_pr_id="0"))
        else:
            if pos_in_page == 0:
                sec0_root.append(_create_paragraph("", column_break=True, para_pr_id="0"))
                sec0_root.append(_create_paragraph("[ 오답 정리 및 메모란 ]", char_pr_id=normal_char_id, para_pr_id="26"))
                for _ in range(8):
                    sec0_root.append(_create_paragraph("", para_pr_id="0"))

    # 꼬리말 안내 텍스트가 있으면 문서 끝에 삽입
    if footer_text:
        sec0_root.append(_create_paragraph("", para_pr_id="0"))
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
    - 본문 기본 텍스트 볼드체 해제 (non-bold)
    - 녹색 상자 테두리 완전 제거 및 공백 줄 paraPr 0 정규화
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

    # 1. header.xml 처리 (녹색 테두리 중화, non-bold charPr 등록)
    hdr_root = ET.fromstring(file_map["Contents/header.xml"])
    _clean_borders_and_boxes(hdr_root)
    normal_char_id, highlight_char_id = _inject_char_properties(hdr_root, font_size_pt=11, is_explanation=True)

    # 2. section0.xml 파싱
    sec0_root = ET.fromstring(file_map["Contents/section0.xml"])

    # 1행 4열 출처 표 템플릿 추출 (삭제 전 보관)
    source_tbl_template = _extract_source_table_template(sec0_root)

    first_p = sec0_root.find(f"{{{NS_HP}}}p")
    sec_run, tbl_run = _extract_and_populate_header_table(
        first_p, normal_char_id, header_left, header_center, header_right, hdr_root=hdr_root
    )

    file_map["Contents/header.xml"] = ET.tostring(hdr_root, encoding="utf-8", xml_declaration=True)

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
    else:
        if header_center:
            sec0_root.append(_create_paragraph(f"■ {header_center}", char_pr_id=normal_char_id, para_pr_id="24"))
        if header_right:
            sec0_root.append(_create_paragraph(f"  ({header_right})", char_pr_id=normal_char_id, para_pr_id="24"))
        if header_center or header_right:
            sec0_root.append(_create_paragraph("", para_pr_id="0"))

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

        if idx == 0 and tbl_run is not None:
            # 첫 문항(idx == 0) 출처 표는 new_first_p에 직접 결합하여 표 앞 불필요한 엔터/공백 행 원천 제거
            src_run0 = _create_source_table_run(source_tbl_template, y_str, g_str, m_str, q_str, normal_char_id)
            new_first_p.set("paraPrIDRef", "24")
            new_first_p.append(src_run0)
        else:
            src_p = _create_source_table_paragraph(source_tbl_template, y_str, g_str, m_str, q_str, normal_char_id)
            sec0_root.append(src_p)

        sec0_root.append(_create_paragraph("", para_pr_id="0"))  # 출처 표 아래 공백 행

        # 2) 문항 번호 및 정답 표시 (paraPr 25: non-bold normal_char_id)
        ans_line = f"{custom_q_num}번. [정답] {ans_display}"
        sec0_root.append(_create_paragraph(ans_line, char_pr_id=normal_char_id, para_pr_id="25"))
        sec0_root.append(_create_paragraph("", para_pr_id="0"))

        # 3) 해설 텍스트 본문 (paraPr 27: non-bold normal_char_id, 선두 중복 정답 표기 제거)
        exp_text = item.get("explanation_text") or "해설 정보가 등록되지 않았습니다."
        exp_lines = _clean_explanation_lines(exp_text)

        for eline in exp_lines:
            if not eline.strip():
                sec0_root.append(_create_paragraph("", para_pr_id="0"))
                continue
            sec0_root.append(_create_paragraph(eline, char_pr_id=normal_char_id, para_pr_id="27"))

        sec0_root.append(_create_paragraph("", para_pr_id="0"))

        # 4) 단 및 페이지 나눔
        if not is_last_item:
            if pos_in_page == 0:
                sec0_root.append(_create_paragraph("", column_break=True, para_pr_id="0"))
            else:
                sec0_root.append(_create_paragraph("", page_break=True, para_pr_id="0"))
        else:
            if pos_in_page == 0:
                sec0_root.append(_create_paragraph("", column_break=True, para_pr_id="0"))
                sec0_root.append(_create_paragraph("[ 메모 및 참고사항 ]", char_pr_id=normal_char_id, para_pr_id="25"))

    if footer_text:
        sec0_root.append(_create_paragraph("", para_pr_id="0"))
        sec0_root.append(_create_paragraph(f"[{footer_text}]", char_pr_id=normal_char_id, para_pr_id="24"))

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

    # 기본 문제지 양식명이 지정되어 있으면 해설지 전용 기본 양식으로 전환
    if exp_options.get("template_name") in (DEFAULT_QUESTION_TEMPLATE, "default_b4-question.hwpx", "default_b4_template.hwpx"):
        exp_options["template_name"] = DEFAULT_EXPLANATION_TEMPLATE

    e_bytes = generate_explanation_handout(items, exp_options)

    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("문제지_B4_유인물.hwpx", q_bytes)
        zf.writestr("해설지_B4_유인물.hwpx", e_bytes)

    return zip_buf.getvalue()


def get_sentence_template_path(template_name: Optional[str] = None) -> str:
    """사용할 A4 문장 HWPX 템플릿의 절대 경로 반환"""
    effective_name = template_name or DEFAULT_SENTENCE_TEMPLATE
    bname = os.path.basename(effective_name)
    # 1. 사용자 업로드 템플릿 폴더 우선 확인
    custom_path = os.path.join(CUSTOM_TEMPLATES_DIR, bname)
    if os.path.exists(custom_path):
        return custom_path
    # 2. 기본 내장 템플릿 폴더 확인
    builtin_path = os.path.join(HANDOUT_TEMPLATES_DIR, bname)
    if os.path.exists(builtin_path):
        return builtin_path
    alt_bname = bname.replace("_", "-") if "_" in bname else bname.replace("-", "_")
    alt_builtin = os.path.join(HANDOUT_TEMPLATES_DIR, alt_bname)
    if os.path.exists(alt_builtin):
        return alt_builtin

    default_path = os.path.join(HANDOUT_TEMPLATES_DIR, DEFAULT_SENTENCE_TEMPLATE)
    if os.path.exists(default_path):
        return default_path

    raise FileNotFoundError(f"문장 유인물 HWPX 템플릿 파일을 찾을 수 없습니다: {DEFAULT_SENTENCE_TEMPLATE}")


def format_sentence_source(raw_id: str) -> str:
    """문장 식별자 문자열에서 '[OOOO년 고O O월 OO번]' 형태의 표준 출처 표기 추출"""
    cleaned = (raw_id or "").strip("[]")
    m_year = re.search(r"(\d{4})년?", cleaned)
    m_grade = re.search(r"(고[123]|중[123])", cleaned)
    m_month = re.search(r"(\d{1,2})월", cleaned)
    m_q = re.search(r"(\d{1,2})번", cleaned)

    year = m_year.group(1) if m_year else "2024"
    grade = m_grade.group(1) if m_grade else "고3"
    month = str(int(m_month.group(1))) if m_month else "6"
    q_num = str(int(m_q.group(1))) if m_q else "1"

    return f"[{year}년 {grade} {month}월 {q_num}번]"


def generate_sentence_handout(items: List[Dict[str, Any]], options: Optional[Dict[str, Any]] = None) -> bytes:
    """
    선택한 문장 목록으로 A4 단면 문장 유인물 HWPX 문서 생성
    - 글자 크기 12 pt 고정 (height="1200", non-bold, 검은색)
    - 문장 간 충분한 줄간격 (줄간격 180% 문단 서식 및 문장 사이 공백 문단 주입)
    - 상단 1x3 머리말 표(왼쪽, 가운데, 오른쪽) 및 유인물 메인 제목([ 제목 ]) 주입
    - '개념 설명 1x1 테이블' 선택 옵션:
      - True (포함): 상단 Row 1 빈칸 유지 + 총 6문장 (또는 6개 단위)
      - False (미포함): 상단 Row 1 행 제거 + 총 10문장 (또는 10개 단위)
    - 각 문장 포맷: '1. [OOOO년 고O O월 OO번] 순수 영문 문장 텍스트' (사용자 지정 custom_num 지원)
    """
    options = options or {}
    template_path = get_sentence_template_path(options.get("template_name"))
    header_left = options.get("header_left", "").strip()
    header_center = options.get("header_center", "").strip() or options.get("header_title", "").strip()
    header_right = options.get("header_right", "").strip() or options.get("header_sub", "").strip()
    main_title = options.get("main_title", "").strip() or "핵심 기출 구문 분석"
    include_concept_table = bool(options.get("include_concept_table", True))

    with zipfile.ZipFile(template_path, "r") as zf:
        file_map = {name: zf.read(name) for name in zf.namelist()}

    # 1. header.xml 처리 (동적 머리말 charPr, 12pt 글자크기, non-bold, 줄간격 180% paraPr 등록 및 빨간색 폰트 정규화)
    hdr_root = ET.fromstring(file_map["Contents/header.xml"])

    # 템플릿 내 빨간색(#FF0000) 글자색을 검은색으로 정규화
    cps = hdr_root.find(f".//{{{NS_HH}}}charProperties")
    for cp in cps.findall(f"{{{NS_HH}}}charPr"):
        if cp.get("textColor", "").upper() == "#FF0000":
            cp.set("textColor", "#000000")

    # 머리말 3개 셀 동적 글자 크기, 장평, 자간 charPr 등록
    lh, lr, ls = _get_dynamic_header_font_size("left", header_left)
    left_char_id = _register_header_char_pr(hdr_root, lh, lr, ls, bold=False, base_char_id="7")

    ch, cr, cs = _get_dynamic_header_font_size("center", header_center)
    center_char_id = _register_header_char_pr(hdr_root, ch, cr, cs, bold=True, base_char_id="8")

    rh, rr, rs = _get_dynamic_header_font_size("right", header_right)
    right_char_id = _register_header_char_pr(hdr_root, rh, rr, rs, bold=False, base_char_id="7")

    # 가운데 상자 높이 초과를 방지하는 콤팩트 paraPr (lineSpacing 125%, margin 0)
    center_para_id = _create_compact_header_para_pr(hdr_root, align_type="CENTER", line_spacing=125)

    # 0. 문장 수 및 내용물 줄 수 추정
    max_limit = 6 if include_concept_table else 10
    target_sentences = items[:max_limit] if len(items) > max_limit else items

    # 텍스트 예상 줄 수 계산 (가용 셀 너비 50458: 줄당 영문 약 82자)
    text_lines = 0
    for s_idx, s in enumerate(target_sentences, 1):
        raw_id = s.get("id", "")
        src_str = format_sentence_source(raw_id)
        sent_text = (s.get("sentence_text") or "").strip()
        custom_num = str(s.get("custom_num") or s_idx).strip()
        full_line = f"{custom_num}. {src_str} {sent_text}"
        lines = max(1, math.ceil(len(full_line) / 82))
        text_lines += lines

    # 6문장은 문장 사이 빈 줄 2개씩(총 5*2=10줄), 10문장은 문장 사이 빈 줄 1개씩(총 9*1=9줄)
    empty_lines_per_gap = 2 if include_concept_table else 1
    total_gaps = max(0, len(target_sentences) - 1)
    bottom_enters = 2
    total_empty_lines = (total_gaps * empty_lines_per_gap) + bottom_enters
    total_lines = text_lines + total_empty_lines

    # 테이블 가용 최대 높이 (A4 1페이지 절대 초과 방지: 6문장=48000, 10문장=65000)
    max_tbl_height = 48000 if include_concept_table else 65000

    # 6문장과 10문장의 글자 크기와 줄간격을 12pt / 180% 로 완전히 일정하게 통일!
    sent_pt = 12.0
    base_line_spacing = 180

    # 1줄당 높이 계산 및 스케일링
    line_h = int(sent_pt * 100 * (base_line_spacing / 100))
    needed_height = (total_lines * line_h) + 1020

    if needed_height > max_tbl_height:
        scale = max_tbl_height / needed_height
        sent_line_spacing = max(155, int(base_line_spacing * scale))
        line_h = int(sent_pt * 100 * (sent_line_spacing / 100))
        needed_height = (total_lines * line_h) + 1020
    else:
        sent_line_spacing = base_line_spacing

    final_tbl_height = min(needed_height, max_tbl_height)

    # 본문 문장용 charPr 등록 (ID 반환, 12pt)
    char_sentence_id = _register_header_char_pr(
        hdr_root, height=int(sent_pt * 100), bold=False, base_char_id="0"
    )

    # 필기용 빈 줄(엔터) 전용 charPr (본문과 같은 12pt로 일정하게 유지)
    char_empty_id = _register_header_char_pr(
        hdr_root, height=int(sent_pt * 100), bold=False, base_char_id="0"
    )

    # 줄간격 설정된 문장 전용 paraPr 등록 (ID 반환)
    para_sentence_id = _create_compact_header_para_pr(
        hdr_root, align_type="LEFT", line_spacing=sent_line_spacing
    )

    # 필기용 빈 줄 전용 paraPr 등록 (동일 줄간격 적용으로 꽉 찬 시각적 효과)
    para_empty_id = _create_compact_header_para_pr(
        hdr_root, align_type="LEFT", line_spacing=sent_line_spacing
    )

    file_map["Contents/header.xml"] = ET.tostring(hdr_root, encoding="utf-8", xml_declaration=True)

    # 2. section0.xml 파싱 및 치환
    sec0_root = ET.fromstring(file_map["Contents/section0.xml"])

    # 상단 1열 2행 표 (tbl 1195242981) 찾기
    tbl_top = None
    for tbl in sec0_root.iter(f"{{{NS_HP}}}tbl"):
        if tbl.get("id") == "1195242981":
            tbl_top = tbl
            break

    if tbl_top is not None:
        trs = tbl_top.findall(f"{{{NS_HP}}}tr")
        if len(trs) >= 1:
            tr0 = trs[0]
            # 상단 1x3 표 (tbl 1195242984) 치환
            tbl_1x3 = None
            for tbl in tr0.iter(f"{{{NS_HP}}}tbl"):
                if tbl.get("id") == "1195242984":
                    tbl_1x3 = tbl
                    break
            if tbl_1x3 is not None:
                tcs_1x3 = tbl_1x3.findall(f".//{{{NS_HP}}}tc")
                vals = [header_left, header_center, header_right]
                char_ids = [left_char_id, center_char_id, right_char_id]
                for i, tc in enumerate(tcs_1x3[:3]):
                    # 가운데 셀의 상하 패딩을 축소하여 테두리 박스가 아래 검은 구분선을 침범하지 않도록 보호
                    if i == 1:
                        cm = tc.find(f".//{{{NS_HP}}}cellMargin")
                        if cm is not None:
                            cm.set("top", "20")
                            cm.set("bottom", "20")

                    # tc 내부 문단 및 텍스트를 깨끗하게 교체
                    for p in tc.iter(f"{{{NS_HP}}}p"):
                        if i == 1:
                            p.set("paraPrIDRef", center_para_id)
                        for child in list(p):
                            p.remove(child)
                        new_run = ET.SubElement(p, f"{{{NS_HP}}}run", {"charPrIDRef": char_ids[i]})
                        new_t = ET.SubElement(new_run, f"{{{NS_HP}}}t")
                        new_t.text = vals[i]

            # [ 제목 ] 문단 찾아서 main_title 주입 (단, 1x3 표가 담긴 header run은 보존)
            title_p = None
            for p in tr0.iter(f"{{{NS_HP}}}p"):
                if p.get("paraPrIDRef") == "13":
                    title_p = p
                    break
            if title_p is not None:
                for r in list(title_p.findall(f"{{{NS_HP}}}run")):
                    if r.find(f".//{{{NS_HP}}}header") is not None:
                        # header run은 보존하고 뒤따르는 텍스트/필드만 정리
                        for t in list(r.findall(f"{{{NS_HP}}}t")):
                            r.remove(t)
                        for ctrl in list(r.findall(f"{{{NS_HP}}}ctrl")):
                            if ctrl.find(f"{{{NS_HP}}}header") is None:
                                r.remove(ctrl)
                    else:
                        title_p.remove(r)
                run_title = ET.SubElement(title_p, f"{{{NS_HP}}}run", {"charPrIDRef": "9"})
                t_title = ET.SubElement(run_title, f"{{{NS_HP}}}t")
                t_title.text = f"[ {main_title} ]"

        # 개념 설명 1x1 테이블 처리 (Row 1)
        if len(trs) >= 2:
            tr1 = trs[1]
            if include_concept_table:
                # 개념 설명 포함: Row 1 유지, 내부 안내문구만 비워서 필기용 빈칸으로 확보
                for p in tr1.iter(f"{{{NS_HP}}}p"):
                    for child in list(p):
                        p.remove(child)
                    run_blank = ET.SubElement(p, f"{{{NS_HP}}}run", {"charPrIDRef": char_sentence_id})
                    t_blank = ET.SubElement(run_blank, f"{{{NS_HP}}}t")
                    t_blank.text = ""
            else:
                # 개념 설명 미선택:
                # 1) Row 1 완전 삭제 및 1x1 단일 행 표로 변경
                tbl_top.remove(tr1)
                tbl_top.set("rowCnt", "1")
                # 2) 제목이 포함된 1x1 테이블의 외곽 테두리를 완전히 투명(borderFillIDRef=1)으로 변경
                tbl_top.set("borderFillIDRef", "1")
                sz_elem = tbl_top.find(f"{{{NS_HP}}}sz")
                if sz_elem is not None:
                    sz_elem.set("height", "2500")

                # 3) 제목 셀(tc)의 아래쪽 구분선(borderFillIDRef=6)도 투명(1)으로 변경하여 테두리 완전 제거
                for tc in tr0.findall(f".//{{{NS_HP}}}tc"):
                    if tc.get("borderFillIDRef") == "6":
                        tc.set("borderFillIDRef", "1")
                        cm = tc.find(f".//{{{NS_HP}}}cellMargin")
                        if cm is not None:
                            cm.set("bottom", "0")

    # 예문 테이블 (tbl 1214106299)
    tbl_example = None
    for tbl in sec0_root.iter(f"{{{NS_HP}}}tbl"):
        if tbl.get("id") == "1214106299":
            tbl_example = tbl
            break

    if tbl_example is not None:
        # 내용물 높이에 정확히 일치시켜 아래쪽 빈 공간 없이 꽉 차도록 테이블 높이 최적화
        sz_ex = tbl_example.find(f".//{{{NS_HP}}}sz")
        if sz_ex is not None:
            sz_ex.set("height", str(final_tbl_height))
        for tc_ex in tbl_example.findall(f".//{{{NS_HP}}}tc"):
            csz_ex = tc_ex.find(f".//{{{NS_HP}}}cellSz")
            if csz_ex is not None:
                csz_ex.set("height", str(final_tbl_height))

        sublist = tbl_example.find(f".//{{{NS_HP}}}tc/{{{NS_HP}}}subList")
        if sublist is not None:
            # 기존 자식 p 모두 제거
            for child in list(sublist):
                sublist.remove(child)

            for s_idx, s in enumerate(target_sentences):
                raw_id = s.get("id", "")
                src_str = format_sentence_source(raw_id)
                sent_text = (s.get("sentence_text") or "").strip()
                custom_num = str(s.get("custom_num") or (s_idx + 1)).strip()
                full_line = f"{custom_num}. {src_str} {sent_text}"

                # 1) 문장 문단 생성 (6문장/10문장 일정한 180% 줄간격, 12pt)
                p_elem = ET.SubElement(sublist, f"{{{NS_HP}}}p", {
                    "id": str(3000000000 + s_idx * 10),
                    "paraPrIDRef": para_sentence_id,
                    "styleIDRef": "0",
                    "pageBreak": "0",
                    "columnBreak": "0",
                    "merged": "0"
                })
                run_elem = ET.SubElement(p_elem, f"{{{NS_HP}}}run", {"charPrIDRef": char_sentence_id})
                t_elem = ET.SubElement(run_elem, f"{{{NS_HP}}}t")
                t_elem.text = full_line

                # 2) 문장 간 충분한 줄간격을 위해 빈 줄 삽입 (6문장은 2줄, 10문장은 1줄)
                if s_idx < len(target_sentences) - 1:
                    for g_idx in range(empty_lines_per_gap):
                        p_spacer = ET.SubElement(sublist, f"{{{NS_HP}}}p", {
                            "id": str(3000000000 + s_idx * 10 + g_idx + 1),
                            "paraPrIDRef": para_empty_id,
                            "styleIDRef": "0",
                            "pageBreak": "0",
                            "columnBreak": "0",
                            "merged": "0"
                        })
                        run_spacer = ET.SubElement(p_spacer, f"{{{NS_HP}}}run", {"charPrIDRef": char_empty_id})
                        t_spacer = ET.SubElement(run_spacer, f"{{{NS_HP}}}t")
                        t_spacer.text = ""

            # 3) 맨 마지막 문장 아래 필기 공간 확보를 위한 엔터 2번 (빈 줄 2개 문단) 삽입
            for e_idx in range(bottom_enters):
                p_last_spacer = ET.SubElement(sublist, f"{{{NS_HP}}}p", {
                    "id": str(3000000000 + len(target_sentences) * 10 + e_idx + 1),
                    "paraPrIDRef": para_empty_id,
                    "styleIDRef": "0",
                    "pageBreak": "0",
                    "columnBreak": "0",
                    "merged": "0"
                })
                r_last = ET.SubElement(p_last_spacer, f"{{{NS_HP}}}run", {"charPrIDRef": char_empty_id})
                t_last = ET.SubElement(r_last, f"{{{NS_HP}}}t")
                t_last.text = ""

    file_map["Contents/section0.xml"] = ET.tostring(sec0_root, encoding="utf-8", xml_declaration=True)

    out_buf = io.BytesIO()
    with zipfile.ZipFile(out_buf, "w", compression=zipfile.ZIP_DEFLATED) as zf_out:
        for fname, fcontent in file_map.items():
            zf_out.writestr(fname, fcontent)

    return out_buf.getvalue()


# =========================================================================
# 듣기 유인물 (B4 Portrait 2x3 테이블 규격) 엔진
# =========================================================================

def get_listening_cell(tbl: ET.Element, col: int, row: int) -> Optional[ET.Element]:
    """테이블 내 특정 (colAddr, rowAddr) 위치의 tc 셀 반환"""
    for tc in tbl.findall(f".//{{{NS_HP}}}tc"):
        addr = tc.find(f"./{{{NS_HP}}}cellAddr")
        if addr is not None and addr.attrib.get("colAddr") == str(col) and addr.attrib.get("rowAddr") == str(row):
            return tc
    return None


def repair_listening_question_title(title: str, question_type: str = "") -> str:
    """잘린 듣기 문항 발문(예: '...응답으로 가장')을 온전한 표준 발문으로 복원"""
    t = (title or "").strip()
    if not t:
        return "대화를 듣고, 알맞은 것을 고르시오."

    # 이미 온전한 마침표나 물음표로 끝나는 경우
    if re.search(r"[\.\?\!]$", t):
        return t

    # 1. '가장'으로 끝나는 경우
    if re.search(r"(?:응답으로|것으로|말로|행동으로)\s*가장$", t) or t.endswith("가장"):
        return t + " 적절한 것을 고르시오."

    # 2. '것을' 또는 '것은'으로 끝나는 경우
    if t.endswith("것을") or t.endswith("것은"):
        return t + " 고르시오."

    # 3. '고', '고르' 등으로 잘린 경우
    if t.endswith("고"):
        return t + "르시오."
    if t.endswith("고르"):
        return t + "시오."
    if t.endswith("고르시"):
        return t + "오."

    # 4. '않는'으로 끝나는 경우
    if t.endswith("않는"):
        return t + " 것을 고르시오."

    # 5. '적절한' 또는 '알맞은'으로 끝나는 경우
    if t.endswith("적절한") or t.endswith("알맞은"):
        return t + " 것을 고르시오."

    # 6. '목적', '의견', '요지', '할 일', '이유' 등으로 끝나는 경우
    if any(t.endswith(k) for k in ("목적", "의견", "요지", "할 일", "할일", "이유")):
        return t + "으로 가장 적절한 것을 고르시오."

    if not re.search(r"[\.\?\!]$", t):
        return t + " 고르시오." if not t.endswith("시오") else t + "."

    return t


_PDF_QUESTION_CACHE: Dict[str, Dict[int, Dict[str, Any]]] = {}


def extract_listening_question_from_pdf(exam_id: str, q_num: int) -> Dict[str, Any]:
    """PDF 문제지에서 특정 문항(1~17번)의 온전한 전체 발문과 선지 ①~⑤ 추출"""
    import glob
    global _PDF_QUESTION_CACHE

    clean_exam_id = exam_id.strip("[]")
    if clean_exam_id in _PDF_QUESTION_CACHE:
        return _PDF_QUESTION_CACHE[clean_exam_id].get(q_num, {})

    uploads_dir = UPLOADS_DIR
    m_exam = re.search(r"(고[123]|중[123])[-_](\d{4})년?[-_](\d{1,2})월?", clean_exam_id)
    pdf_candidates = []
    if m_exam:
        grd, yr, mn = m_exam.group(1), m_exam.group(2), int(m_exam.group(3))
        patt1 = os.path.join(uploads_dir, f"{grd}_{yr}_{mn:02d}_*.pdf")
        patt2 = os.path.join(uploads_dir, f"*{yr}*{mn:02d}*.pdf")
        pdf_candidates = [p for p in glob.glob(patt1) if "_script" not in p and "대본" not in p and "_ans" not in p and "_exp" not in p]
        if not pdf_candidates:
            pdf_candidates = [p for p in glob.glob(patt2) if "_script" not in p and "대본" not in p and "_ans" not in p and "_exp" not in p]

    if not pdf_candidates:
        _PDF_QUESTION_CACHE[clean_exam_id] = {}
        return {}

    target_pdf = pdf_candidates[0]
    extracted_questions: Dict[int, Dict[str, Any]] = {}

    try:
        import pymupdf as fitz
        doc = fitz.open(target_pdf)
        pages_text = []
        for p_idx in range(min(3, len(doc))):
            pages_text.append(doc[p_idx].get_text())
        doc.close()
        full_text = "\n".join(pages_text)

        for q in range(1, 18):
            pattern = rf"(?:^|\n)\s*{q}\s*\.\s*(.+?)(?=(?:\n\s*{q + 1}\s*\.|\n\s*\[\d+[-~]\d+\]|\n\s*이제\s*듣기\s*문제가|\n\s*18\s*\.|$))"
            m = re.search(pattern, full_text, re.DOTALL)
            if not m:
                continue

            raw_block = m.group(1).strip()
            idx_circ1 = raw_block.find("①")
            if idx_circ1 != -1:
                title_part = raw_block[:idx_circ1].strip()
                choices_raw = raw_block[idx_circ1:].strip()
            else:
                title_part = raw_block.strip()
                choices_raw = ""

            choices = {}
            if choices_raw:
                c_matches = list(re.finditer(r"([①-⑤])\s*(.*?)(?=(?:[①-⑤]|$))", choices_raw, re.DOTALL))
                for cm in c_matches:
                    c_sym = cm.group(1)
                    c_txt = " ".join(cm.group(2).split()).strip()
                    c_idx = ["①", "②", "③", "④", "⑤"].index(c_sym) + 1
                    choices[c_idx] = c_txt

            clean_title = " ".join(title_part.split()).strip()
            clean_title = re.sub(r"^\s*\d{1,2}\s*[\.\)]\s*", "", clean_title).strip()
            clean_title = repair_listening_question_title(clean_title)
            clean_title = re.sub(r"^\s*\d{1,2}\s*[\.\)]\s*", "", clean_title).strip()

            extracted_questions[q] = {
                "title": clean_title,
                "choices": choices,
                "raw_block": raw_block
            }

        _PDF_QUESTION_CACHE[clean_exam_id] = extracted_questions
        return extracted_questions.get(q_num, {})
    except Exception as e:
        logger.warning("[extract_listening_question_from_pdf] 파싱 실패 (%s): %s", clean_exam_id, e)
        _PDF_QUESTION_CACHE[clean_exam_id] = {}
        return {}


def _prepare_listening_item_data(p: Dict[str, Any], custom_q_num: str = "1") -> Dict[str, Any]:
    """듣기 문항 1개의 데이터 정제 (문항 텍스트, FELS 약형드랩, 우리말 해석, 영문 script, 정답)"""
    q_title = p.get("question_title") or ""
    # 문항 번호(예: 1., 3), 03. 등) 완벽 제거 (반복 제거)
    pure_title = (p.get("question_title") or "").strip()
    while re.match(r"^\s*\d{1,2}\s*[\.\)]\s*", pure_title):
        pure_title = re.sub(r"^\s*\d{1,2}\s*[\.\)]\s*", "", pure_title).strip()
    pure_title = repair_listening_question_title(pure_title, p.get("question_type") or "")
    while re.match(r"^\s*\d{1,2}\s*[\.\)]\s*", pure_title):
        pure_title = re.sub(r"^\s*\d{1,2}\s*[\.\)]\s*", "", pure_title).strip()

    # 선지 추출 (지문 passage_text 우선, 없으면 explanation_text에서 추출)
    exp_text = p.get("explanation_text") or ""
    passage_txt = p.get("passage_text") or ""
    choices = extract_choices(passage_txt)
    if not choices:
        choices = extract_choices(exp_text)

    # 선지가 부족하거나 없는 경우 PDF 문제지 원본에서 직접 추출 시도
    exam_id = p.get("exam_id") or ""
    q_num = p.get("q_num") or 0
    if not q_num and p.get("id"):
        m_q = re.search(r"-(\d+)번?\]?$", str(p.get("id")))
        if m_q:
            q_num = int(m_q.group(1))

    if (not choices or len(choices) < 3) and exam_id and q_num:
        pdf_info = extract_listening_question_from_pdf(exam_id, q_num)
        if pdf_info:
            if pdf_info.get("title") and len(pdf_info["title"]) >= len(pure_title):
                p_title = pdf_info["title"].strip()
                while re.match(r"^\s*\d{1,2}\s*[\.\)]\s*", p_title):
                    p_title = re.sub(r"^\s*\d{1,2}\s*[\.\)]\s*", "", p_title).strip()
                pure_title = p_title
            if pdf_info.get("choices") and not choices:
                choices = pdf_info["choices"]

    choices_lines = []
    for c_idx in range(1, 6):
        c_val = choices.get(c_idx, "").strip()
        if c_val:
            circ = CIRCLE_NUMS.get(c_idx, f"({c_idx})")
            choices_lines.append(f"{circ} {c_val}")

    while re.match(r"^\s*\d{1,2}\s*[\.\)]\s*", pure_title):
        pure_title = re.sub(r"^\s*\d{1,2}\s*[\.\)]\s*", "", pure_title).strip()
    full_q_title = f"{custom_q_num}. {pure_title}"
    q_text_block = full_q_title
    if choices_lines:
        q_text_block += "\n\n" + "\n".join(choices_lines)
    elif "그림" in pure_title or p.get("question_type") == "그림 불일치":
        q_text_block += "\n\n[그림 참조 문항]"

    # 대본(script) 및 FELS 약형드랩 생성
    script_text = (p.get("script_text") or p.get("passage_text") or "").strip()
    fels_text = p.get("fels_text") or ""
    if not fels_text and script_text:
        fels_text = generate_fels_text(script_text)

    fels_blank = generate_fels_blank(
        fels_text,
        split_sentences_for_monologue=True,
        title=pure_title,
        question_type=p.get("question_type") or ""
    )

    # 우리말 해석 추출 (explanation_text의 [해석] 블록 정밀 추출)
    kor_trans = ""
    if exp_text:
        m_trans = re.search(r"\[해석\]\s*\n+(.*?)(?=\n+\[(?:출제\s*의도|풀이|해설|Words|어휘)|$)", exp_text, re.DOTALL)
        if m_trans:
            kor_trans = m_trans.group(1).strip()
        else:
            lines = [l.strip() for l in exp_text.splitlines() if re.search(r"[가-힣]", l) and not l.startswith("[")]
            # 출제의도 라인은 제외
            lines = [l for l in lines if not l.startswith("출제") and not l.startswith("담화") and not l.startswith("대화에서")]
            if lines:
                kor_trans = "\n".join(lines[:12])

    # 우리말 해석 데이터가 비어있는 경우 AI를 통해 자동 해석(번역) 수행 및 DB 영구 저장
    if not kor_trans and script_text:
        try:
            from ..grammar_analyzer import translate_listening_script
            ai_trans = translate_listening_script(script_text)
            if ai_trans:
                kor_trans = ai_trans.strip()
                if p.get("id"):
                    # DB explanation_text 보강 업데이트
                    updated_exp = (exp_text.strip() + f"\n\n[해석]\n{kor_trans}").strip()
                    from .. import database as db
                    db.update_passage_explanation(p["id"], updated_exp)
                    logger.info("AI 우리말 해석 자동 생성 및 DB 저장 성공: %s", p["id"])
        except Exception as e:
            logger.warning("AI 우리말 해석 자동 번역 실패: %s", e)

    # 정답 추출
    ans_num = extract_answer_num(p.get("answer_text") or "")
    if not ans_num and exp_text:
        m_ans = re.search(r"\[정답\]\s*([①-⑤\d]+)", exp_text)
        if m_ans:
            ans_num = extract_answer_num(m_ans.group(1))

    circ_ans = CIRCLE_NUMS.get(ans_num) if (ans_num and 1 <= ans_num <= 5) else (p.get("answer_text") or "-")

    return {
        "id": p.get("id"),
        "question_title": pure_title,
        "question_type": p.get("question_type") or "",
        "question_text": q_text_block,
        "fels_blank": fels_blank,
        "korean_translation": kor_trans,
        "script_text": script_text,
        "answer_display": circ_ans,
    }


def _set_listening_cell_paragraphs(
    tc: Optional[ET.Element],
    text: str,
    char_pr_id: str = "33",
    para_pr_id: str = "2"
) -> None:
    """tc 셀 내부 문단을 비우고 개행 기준 단락들을 주입"""
    if tc is None:
        return

    sublist = tc.find(f"{{{NS_HP}}}subList")
    container = sublist if sublist is not None else tc

    # 기존 p 문단 모두 제거
    for child in list(container.findall(f"{{{NS_HP}}}p")):
        container.remove(child)

    raw_lines = (text or "").replace("\r\n", "\n").replace("\r", "\n").split("\n")
    lines = [l.rstrip() for l in raw_lines]
    if not lines or (len(lines) == 1 and not lines[0]):
        lines = [""]

    for line in lines:
        p_elem = ET.SubElement(container, f"{{{NS_HP}}}p", {
            "paraPrIDRef": para_pr_id,
            "styleIDRef": "0",
            "pageBreak": "0",
            "columnBreak": "0",
            "merged": "0"
        })
        run_elem = ET.SubElement(p_elem, f"{{{NS_HP}}}run", {"charPrIDRef": char_pr_id})
        t_elem = ET.SubElement(run_elem, f"{{{NS_HP}}}t")
        t_elem.text = line


def _calculate_listening_line_count(text: str, line_capacity: int = 48) -> int:
    """
    B4 세로 듣기 셀(폭 약 105mm) 너비 및 단어 단위 줄바꿈을 반영한 정밀 환산 라인 수 계산
    - 한글/전각 문자: visual 폭 가중치 2
    - 영문/숫자/기호/빈칸: visual 폭 가중치 1
    - line_capacity = 48 (10pt 기준 셀 가용 폭 50~52단위 중 여백/단어줄바꿈 고려 안전치)
    """
    if not text:
        return 0
    raw_lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    total = 0
    for l in raw_lines:
        s = l.strip()
        if not s:
            total += 1
            continue
        # 한글/전각 문자는 가중치 2, 영문/기호는 1
        visual_len = sum(2 if ord(c) > 127 else 1 for c in s)
        total += max(1, math.ceil(visual_len / line_capacity))
    return total


def _ensure_listening_styles_in_header(hdr_root: ET.Element) -> None:
    """
    header.xml에 '돋움체' 전용 charPr(11.0pt~7.0pt: 101~106) 및
    순수 줄간격 paraPr(145%~105%: 101~106) 등록
    - 문제지/해설지 글씨체 '돋움체' 100% 강제 통일
    - 문단 번호 매기기(heading NUMBER 등) 절대 배제 (heading type='NONE' 보장)
    - 내용 길이에 따른 2문항 1페이지 완벽 안착 동적 스케일링 제공
    """
    char_props = hdr_root.find(f".//{{{NS_HH}}}charProperties")
    para_props = hdr_root.find(f".//{{{NS_HH}}}paraProperties")
    if char_props is None or para_props is None:
        return

    # 1. '돋움' 폰트 id 찾기 (기본값 '1')
    dotum_id = "1"
    fontfaces = hdr_root.find(f".//{{{NS_HH}}}fontfaces")
    if fontfaces is not None:
        for ff in fontfaces.findall(f".//{{{NS_HH}}}fontface"):
            if ff.get("lang") == "HANGUL":
                for f in ff.findall(f".//{{{NS_HH}}}font"):
                    if "돋움" in (f.get("face") or ""):
                        dotum_id = f.get("id") or "1"
                        break

    # 1-1. 기존 템플릿의 모든 paraPr 중 heading이 NUMBER나 OUTLINE인 항목들을 모조리 NONE으로 원천 무력화
    for pp in para_props.findall(f".//{{{NS_HH}}}paraPr"):
        hd = pp.find(f".//{{{NS_HH}}}heading")
        if hd is not None and hd.get("type") in ("NUMBER", "OUTLINE"):
            hd.set("type", "NONE")
            hd.set("idRef", "0")
            hd.set("level", "0")

    # 2. 전용 charPr 등록 (101: 11.0pt ~ 106: 7.0pt 돋움체)
    base_cp = char_props.find(f".//{{{NS_HH}}}charPr[@id='0']")
    if base_cp is None:
        all_cps = list(char_props.findall(f"{{{NS_HH}}}charPr"))
        if all_cps:
            base_cp = all_cps[0]

    if base_cp is not None:
        char_specs = [
            ("101", "1100"),  # 11.0pt (아주 짧은 문항: <= 12줄)
            ("102", "1000"),  # 10.0pt (보통 문항: 13~17줄)
            ("103", "900"),   # 9.0pt  (다소 긴 문항: 18~22줄)
            ("104", "820"),   # 8.2pt  (긴 문항: 23~27줄)
            ("105", "750"),   # 7.5pt  (매우 긴 문항: 28~32줄)
            ("106", "700"),   # 7.0pt  (초장문/복합 문항: >= 33줄)
        ]
        for cid, h in char_specs:
            cp = char_props.find(f".//{{{NS_HH}}}charPr[@id='{cid}']")
            if cp is None:
                cp = copy.deepcopy(base_cp)
                cp.set("id", cid)
                char_props.append(cp)
            cp.set("height", h)
            # 돋움체로 fontRef 통일
            fn = cp.find(f".//{{{NS_HH}}}fontRef")
            if fn is not None:
                for k in list(fn.attrib.keys()):
                    fn.set(k, dotum_id)

        char_props.set("itemCnt", str(len(char_props.findall(f".//{{{NS_HH}}}charPr"))))

    # 3. 전용 순수 줄간격 paraPr 등록 (101: 145% ~ 106: 105%)
    base_pp = para_props.find(f".//{{{NS_HH}}}paraPr[@id='0']")
    if base_pp is None:
        all_pps = list(para_props.findall(f"{{{NS_HH}}}paraPr"))
        if all_pps:
            base_pp = all_pps[0]

    if base_pp is not None:
        para_specs = [
            ("101", "145"),  # 145% (11.0pt용)
            ("102", "135"),  # 135% (10.0pt용)
            ("103", "125"),  # 125% (9.0pt용)
            ("104", "118"),  # 118% (8.2pt용)
            ("105", "112"),  # 112% (7.5pt용)
            ("106", "105"),  # 105% (7.0pt용)
        ]
        for pid, ls_val in para_specs:
            pp = para_props.find(f".//{{{NS_HH}}}paraPr[@id='{pid}']")
            if pp is None:
                pp = copy.deepcopy(base_pp)
                pp.set("id", pid)
                para_props.append(pp)
            # 문단 번호 매기기(heading NUMBER, OUTLINE) 절대 배제
            heading = pp.find(f".//{{{NS_HH}}}heading")
            if heading is not None:
                heading.set("type", "NONE")
                heading.set("idRef", "0")
                heading.set("level", "0")
            # 줄간격 설정
            ls = pp.find(f".//{{{NS_HH}}}lineSpacing")
            if ls is not None:
                ls.set("value", ls_val)
                ls.set("type", "PERCENT")

        para_props.set("itemCnt", str(len(para_props.findall(f".//{{{NS_HH}}}paraPr"))))


def _get_listening_style_for_lines(max_lines: int) -> Tuple[str, str]:
    """
    단일 문항 환산 라인 수에 따른 최적 (charPrID, paraPrID) 반환 (돋움체 전용)
    - <= 12줄: 11.0pt 돋움 (101), 줄간격 145% (101)
    - 13~17줄: 10.0pt 돋움 (102), 줄간격 135% (102)
    - 18~22줄:  9.0pt 돋움 (103), 줄간격 125% (103)
    - 23~27줄:  8.2pt 돋움 (104), 줄간격 118% (104)
    - 28~32줄:  7.5pt 돋움 (105), 줄간격 112% (105)
    - >= 33줄:  7.0pt 돋움 (106), 줄간격 105% (106)
    """
    if max_lines <= 12:
        return ("101", "101")
    elif max_lines <= 17:
        return ("102", "102")
    elif max_lines <= 22:
        return ("103", "103")
    elif max_lines <= 27:
        return ("104", "104")
    elif max_lines <= 32:
        return ("105", "105")
    else:
        return ("106", "106")


def _get_page_listening_styles(
    lines1: int,
    lines2: int
) -> Tuple[Tuple[str, str], Tuple[str, str]]:
    """
    B4 세로 1페이지에 배치되는 2개 문항이 다음 페이지로 밀려나지 않고
    반드시 1페이지에 온전히 안착되도록 개별 라인 수와 합산 라인 수를 복합 분석하여
    최적의 ((cp1, pp1), (cp2, pp2)) 반환
    """
    cp1, pp1 = _get_listening_style_for_lines(lines1)
    if lines2 <= 0:
        return (cp1, pp1), (cp1, pp1)

    cp2, pp2 = _get_listening_style_for_lines(lines2)

    total_lines = lines1 + lines2
    # 페이지 총합 기준 최소 보장 스타일 (합산 라인이 클 때 2문항이 1페이지를 넘지 못하도록 강제 하향)
    if total_lines <= 26:
        min_style = "101"
    elif total_lines <= 35:
        min_style = "102"
    elif total_lines <= 44:
        min_style = "103"
    elif total_lines <= 52:
        min_style = "104"
    elif total_lines <= 60:
        min_style = "105"
    else:
        min_style = "106"

    final_cp1 = max(cp1, min_style)
    final_cp2 = max(cp2, min_style)

    return (final_cp1, final_cp1), (final_cp2, final_cp2)


def _apply_listening_header(
    tbl0: Optional[ET.Element],
    header_left: str,
    header_center: str,
    header_right: str
) -> None:
    """듣기 유인물 상단 머리말 1x3 표 (Table 0) 내용 반영 (돋움체 적용)"""
    if tbl0 is None:
        return
    tc_left = get_listening_cell(tbl0, 0, 0)
    tc_center = get_listening_cell(tbl0, 1, 0)
    tc_right = get_listening_cell(tbl0, 2, 0)

    if tc_left is not None:
        _set_listening_cell_paragraphs(tc_left, header_left, char_pr_id="102", para_pr_id="102")
    if tc_center is not None:
        _set_listening_cell_paragraphs(tc_center, header_center, char_pr_id="101", para_pr_id="101")
    if tc_right is not None:
        _set_listening_cell_paragraphs(tc_right, header_right, char_pr_id="102", para_pr_id="102")


def generate_listening_question_handout(
    items: List[Dict[str, Any]],
    options: Dict[str, Any]
) -> bytes:
    """
    B4 세로(Portrait) 규격 듣기 문제 유인물 HWPX 생성
    - 한 페이지당 2문항 (2x3 테이블 구조)
    - 1열: 문항 텍스트 (발문 + 선지) - 돋움체 기본
    - 2열: FELS 약형드랩 [  ] - 돋움체 기본
    - 3열: [표현 정리] 5행 빈칸 표 (템플릿 서식 100% 보존)
    - 문단 번호 매기기 완전 배제, 내용 길이에 따른 폰트/줄간격 자동 스케일링
    """
    template_path = get_listening_template_path(options.get("template_name"), is_explanation=False)
    file_map = {}
    with zipfile.ZipFile(template_path, "r") as zf:
        for fname in zf.namelist():
            file_map[fname] = zf.read(fname)

    header_left = (options.get("header_left") or "").strip()
    header_center = (options.get("header_center") or "").strip()
    header_right = (options.get("header_right") or "").strip()

    # header.xml 컴팩트 스타일 등록 (돋움체 & 순수 줄간격)
    if "Contents/header.xml" in file_map:
        hdr_root = ET.fromstring(file_map["Contents/header.xml"])
        _ensure_listening_styles_in_header(hdr_root)
        file_map["Contents/header.xml"] = ET.tostring(hdr_root, encoding="utf-8", xml_declaration=True)

    sec0_root = ET.fromstring(file_map["Contents/section0.xml"])

    # 1. 머리말 Table 0 주입
    tbl0 = sec0_root.find(f".//{{{NS_HP}}}tbl[@id='1315644029']")
    _apply_listening_header(tbl0, header_left, header_center, header_right)

    # 2. 본문 Table 1 찾기
    tbl1 = sec0_root.find(f".//{{{NS_HP}}}tbl[@id='1216160613']")
    if tbl1 is None:
        raise ValueError("듣기 문제 유인물 템플릿에서 메인 표(id=1216160613)를 찾을 수 없습니다.")

    # 3. 페이지당 2문항 배치
    page_count = max(1, math.ceil(len(items) / 2))

    for p_idx in range(page_count):
        page_items = items[p_idx * 2 : p_idx * 2 + 2]
        item1 = page_items[0] if len(page_items) >= 1 else None
        item2 = page_items[1] if len(page_items) >= 2 else None

        if p_idx == 0:
            cur_tbl = tbl1
        else:
            cur_tbl = copy.deepcopy(tbl1)
            cur_tbl.set("id", str(1216160613 + p_idx * 1000))
            p_elem = ET.Element(f"{{{NS_HP}}}p", {
                "id": str(2000000000 + p_idx * 10),
                "paraPrIDRef": "102",
                "styleIDRef": "0",
                "pageBreak": "1",
                "columnBreak": "0",
                "merged": "0"
            })
            run_elem = ET.SubElement(p_elem, f"{{{NS_HP}}}run", {"charPrIDRef": "102"})
            run_elem.append(cur_tbl)
            sec0_root.append(p_elem)

        # 1) 문항 1 & 문항 2 데이터 사전 준비 및 라인 수 정밀 산출
        if item1:
            q_num_1 = str(item1.get("custom_q_num") or (p_idx * 2 + 1)).strip()
            data1 = _prepare_listening_item_data(item1, q_num_1)
            lines1 = max(
                _calculate_listening_line_count(data1["question_text"]),
                _calculate_listening_line_count(data1["fels_blank"])
            )
        else:
            data1 = None
            lines1 = 0

        if item2:
            q_num_2 = str(item2.get("custom_q_num") or (p_idx * 2 + 2)).strip()
            data2 = _prepare_listening_item_data(item2, q_num_2)
            lines2 = max(
                _calculate_listening_line_count(data2["question_text"]),
                _calculate_listening_line_count(data2["fels_blank"])
            )
        else:
            data2 = None
            lines2 = 0

        # 2) 두 문항이 1페이지에 반드시 함께 안착되도록 페이지 레벨 동적 스타일 쌍 도출
        (cp1, pp1), (cp2, pp2) = _get_page_listening_styles(lines1, lines2)

        # Question 1 (Row 0)
        tc_q1_text = get_listening_cell(cur_tbl, 0, 0)
        tc_q1_fels = get_listening_cell(cur_tbl, 1, 0)
        if item1 and data1:
            _set_listening_cell_paragraphs(tc_q1_text, data1["question_text"], char_pr_id=cp1, para_pr_id=pp1)
            _set_listening_cell_paragraphs(tc_q1_fels, data1["fels_blank"], char_pr_id=cp1, para_pr_id=pp1)
        else:
            _set_listening_cell_paragraphs(tc_q1_text, "", char_pr_id="102", para_pr_id="102")
            _set_listening_cell_paragraphs(tc_q1_fels, "", char_pr_id="102", para_pr_id="102")

        # Question 2 (Row 7)
        tc_q2_text = get_listening_cell(cur_tbl, 0, 7)
        tc_q2_fels = get_listening_cell(cur_tbl, 1, 7)
        if item2 and data2:
            _set_listening_cell_paragraphs(tc_q2_text, data2["question_text"], char_pr_id=cp2, para_pr_id=pp2)
            _set_listening_cell_paragraphs(tc_q2_fels, data2["fels_blank"], char_pr_id=cp2, para_pr_id=pp2)
        else:
            _set_listening_cell_paragraphs(tc_q2_text, "", char_pr_id="102", para_pr_id="102")
            _set_listening_cell_paragraphs(tc_q2_fels, "", char_pr_id="102", para_pr_id="102")

    file_map["Contents/section0.xml"] = ET.tostring(sec0_root, encoding="utf-8", xml_declaration=True)

    out_buf = io.BytesIO()
    with zipfile.ZipFile(out_buf, "w", compression=zipfile.ZIP_DEFLATED) as zf_out:
        for fname, fcontent in file_map.items():
            zf_out.writestr(fname, fcontent)

    return out_buf.getvalue()


def generate_listening_explanation_handout(
    items: List[Dict[str, Any]],
    options: Dict[str, Any]
) -> bytes:
    """
    B4 세로(Portrait) 규격 듣기 해설 유인물 HWPX 생성
    - 한 페이지당 2문항 (2x3 테이블 구조)
    - 1열: 문항 텍스트 + [정답] {ans} - 돋움체 기본
    - 2열: 우리말 해석 텍스트 (누락 시 AI 자동 번역 및 DB 캐싱) - 돋움체 기본
    - 3열: script 영문 전문 - 돋움체 기본
    - 문단 번호 매기기 완전 배제, 내용 길이에 따른 폰트/줄간격 자동 스케일링
    """
    template_path = get_listening_template_path(options.get("template_name"), is_explanation=True)
    file_map = {}
    with zipfile.ZipFile(template_path, "r") as zf:
        for fname in zf.namelist():
            file_map[fname] = zf.read(fname)

    header_left = (options.get("header_left") or "").strip()
    header_center = (options.get("header_center") or "").strip()
    header_right = (options.get("header_right") or "").strip()

    # header.xml 컴팩트 스타일 등록 (돋움체 & 순수 줄간격)
    if "Contents/header.xml" in file_map:
        hdr_root = ET.fromstring(file_map["Contents/header.xml"])
        _ensure_listening_styles_in_header(hdr_root)
        file_map["Contents/header.xml"] = ET.tostring(hdr_root, encoding="utf-8", xml_declaration=True)

    sec0_root = ET.fromstring(file_map["Contents/section0.xml"])

    # 1. 머리말 Table 0 주입
    tbl0 = sec0_root.find(f".//{{{NS_HP}}}tbl[@id='1315644029']")
    _apply_listening_header(tbl0, header_left, header_center, header_right)

    # 2. 본문 Table 1 찾기
    tbl1 = sec0_root.find(f".//{{{NS_HP}}}tbl[@id='1216160613']")
    if tbl1 is None:
        raise ValueError("듣기 해설 유인물 템플릿에서 메인 표(id=1216160613)를 찾을 수 없습니다.")

    # 3. 페이지당 2문항 배치
    page_count = max(1, math.ceil(len(items) / 2))

    for p_idx in range(page_count):
        page_items = items[p_idx * 2 : p_idx * 2 + 2]
        item1 = page_items[0] if len(page_items) >= 1 else None
        item2 = page_items[1] if len(page_items) >= 2 else None

        if p_idx == 0:
            cur_tbl = tbl1
        else:
            cur_tbl = copy.deepcopy(tbl1)
            cur_tbl.set("id", str(1216160613 + p_idx * 1000))
            p_elem = ET.Element(f"{{{NS_HP}}}p", {
                "id": str(2000000000 + p_idx * 10),
                "paraPrIDRef": "102",
                "styleIDRef": "0",
                "pageBreak": "1",
                "columnBreak": "0",
                "merged": "0"
            })
            run_elem = ET.SubElement(p_elem, f"{{{NS_HP}}}run", {"charPrIDRef": "102"})
            run_elem.append(cur_tbl)
            sec0_root.append(p_elem)

        # 1) 문항 1 & 문항 2 데이터 사전 준비 및 라인 수 정밀 산출
        if item1:
            q_num_1 = str(item1.get("custom_q_num") or (p_idx * 2 + 1)).strip()
            data1 = _prepare_listening_item_data(item1, q_num_1)
            q_text_ans1 = f"{data1['question_text']}\n\n[정답] {data1['answer_display']}"
            lines1 = max(
                _calculate_listening_line_count(q_text_ans1),
                _calculate_listening_line_count(data1["korean_translation"]),
                _calculate_listening_line_count(data1["script_text"])
            )
        else:
            data1 = None
            q_text_ans1 = ""
            lines1 = 0

        if item2:
            q_num_2 = str(item2.get("custom_q_num") or (p_idx * 2 + 2)).strip()
            data2 = _prepare_listening_item_data(item2, q_num_2)
            q_text_ans2 = f"{data2['question_text']}\n\n[정답] {data2['answer_display']}"
            lines2 = max(
                _calculate_listening_line_count(q_text_ans2),
                _calculate_listening_line_count(data2["korean_translation"]),
                _calculate_listening_line_count(data2["script_text"])
            )
        else:
            data2 = None
            q_text_ans2 = ""
            lines2 = 0

        # 2) 두 문항이 1페이지에 반드시 함께 안착되도록 페이지 레벨 동적 스타일 쌍 도출
        (cp1, pp1), (cp2, pp2) = _get_page_listening_styles(lines1, lines2)

        # Question 1 (Row 0)
        tc_q1_text = get_listening_cell(cur_tbl, 0, 0)
        tc_q1_trans = get_listening_cell(cur_tbl, 1, 0)
        tc_q1_script = get_listening_cell(cur_tbl, 2, 0)
        if item1 and data1:
            _set_listening_cell_paragraphs(tc_q1_text, q_text_ans1, char_pr_id=cp1, para_pr_id=pp1)
            _set_listening_cell_paragraphs(tc_q1_trans, data1["korean_translation"], char_pr_id=cp1, para_pr_id=pp1)
            _set_listening_cell_paragraphs(tc_q1_script, data1["script_text"], char_pr_id=cp1, para_pr_id=pp1)
        else:
            _set_listening_cell_paragraphs(tc_q1_text, "", char_pr_id="102", para_pr_id="102")
            _set_listening_cell_paragraphs(tc_q1_trans, "", char_pr_id="102", para_pr_id="102")
            _set_listening_cell_paragraphs(tc_q1_script, "", char_pr_id="102", para_pr_id="102")

        # Question 2 (Row 1)
        tc_q2_text = get_listening_cell(cur_tbl, 0, 1)
        tc_q2_trans = get_listening_cell(cur_tbl, 1, 1)
        tc_q2_script = get_listening_cell(cur_tbl, 2, 1)
        if item2 and data2:
            _set_listening_cell_paragraphs(tc_q2_text, q_text_ans2, char_pr_id=cp2, para_pr_id=pp2)
            _set_listening_cell_paragraphs(tc_q2_trans, data2["korean_translation"], char_pr_id=cp2, para_pr_id=pp2)
            _set_listening_cell_paragraphs(tc_q2_script, data2["script_text"], char_pr_id=cp2, para_pr_id=pp2)
        else:
            _set_listening_cell_paragraphs(tc_q2_text, "", char_pr_id="102", para_pr_id="102")
            _set_listening_cell_paragraphs(tc_q2_trans, "", char_pr_id="102", para_pr_id="102")
            _set_listening_cell_paragraphs(tc_q2_script, "", char_pr_id="102", para_pr_id="102")


    file_map["Contents/section0.xml"] = ET.tostring(sec0_root, encoding="utf-8", xml_declaration=True)

    out_buf = io.BytesIO()
    with zipfile.ZipFile(out_buf, "w", compression=zipfile.ZIP_DEFLATED) as zf_out:
        for fname, fcontent in file_map.items():
            zf_out.writestr(fname, fcontent)

    return out_buf.getvalue()


def generate_listening_handout_zip(
    items: List[Dict[str, Any]],
    options: Dict[str, Any]
) -> bytes:
    """듣기 문제 유인물과 해설 유인물을 동시 생성하여 단일 ZIP 압축 바이너리로 패키징"""
    q_bytes = generate_listening_question_handout(items, options)
    e_bytes = generate_listening_explanation_handout(items, options)

    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(f"듣기문제유인물_{len(items)}문항.hwpx", q_bytes)
        zf.writestr(f"듣기해설유인물_{len(items)}문항.hwpx", e_bytes)

    return zip_buf.getvalue()


