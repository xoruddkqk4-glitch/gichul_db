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
    header_title = options.get("header_title", "").strip()
    header_sub = options.get("header_sub", "").strip()
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

    # 첫 문단(secPr 보관용) 유지
    first_p = sec0_root.find(f"{{{NS_HP}}}p")
    sec_pr = None
    if first_p is not None:
        sec_pr = first_p.find(f".//{{{NS_HP}}}secPr")

    # 기존 문단 비우기
    sec0_root.clear()

    # secPr을 담은 첫 문단 재구성
    new_first_p = ET.SubElement(sec0_root, f"{{{NS_HP}}}p", {
        "id": "1000000001",
        "paraPrIDRef": "0",
        "styleIDRef": "0",
        "pageBreak": "0",
        "columnBreak": "0",
        "merged": "0",
    })
    first_run = ET.SubElement(new_first_p, f"{{{NS_HP}}}run", {"charPrIDRef": normal_char_id})
    if sec_pr is not None:
        first_run.append(sec_pr)

    # 머리말 상단 텍스트가 지정된 경우 첫 페이지 상단에 표출
    if header_title:
        title_p = _create_paragraph(f"■ {header_title}", char_pr_id=normal_char_id)
        sec0_root.append(title_p)
    if header_sub:
        sub_p = _create_paragraph(f"  ({header_sub})", char_pr_id=normal_char_id)
        sec0_root.append(sub_p)
    if header_title or header_sub:
        # 빈 줄 하나 삽입
        sec0_root.append(_create_paragraph(""))

    # 문항들 순회 (1페이지당 2개 문항: 좌단 1문항, 우단 1문항)
    total_q = len(items)
    for idx, item in enumerate(items):
        pos_in_page = (idx % 2)  # 0: 좌측단 (첫 번째 문항), 1: 우측단 (두 번째 문항)
        is_last_item = (idx == total_q - 1)

        custom_q_num = str(item.get("custom_q_num", idx + 1)).strip() or str(idx + 1)
        q_title = item.get("question_title", "")
        p_text = item.get("passage_text", "")
        ans_text = item.get("answer_text", "")
        ans_num = extract_answer_num(ans_text)

        pure_title, body_text, choices = _clean_passage_body_and_title(p_text, q_title)

        # 1) 발문 문단: [사용자 지정 번호]. [발문]
        full_title_text = f"{custom_q_num}. {pure_title}" if pure_title else f"{custom_q_num}. 다음 글을 읽고 물음에 답하시오."
        sec0_root.append(_create_paragraph(full_title_text, char_pr_id=normal_char_id))
        sec0_root.append(_create_paragraph(""))  # 공백 행

        # 2) 지문 본문 문단 (줄 단위로 문단 생성)
        if body_text:
            body_lines = [line.strip() for line in body_text.splitlines() if line.strip()]
            for bline in body_lines:
                sec0_root.append(_create_paragraph(bline, char_pr_id=normal_char_id))
        else:
            sec0_root.append(_create_paragraph("(지문 본문이 비어 있습니다.)", char_pr_id=normal_char_id))

        sec0_root.append(_create_paragraph(""))  # 선지 전 공백 행

        # 3) 선지 문단 (① ~ ⑤)
        if choices:
            for c_idx in range(1, 6):
                c_text = choices.get(c_idx, "").strip()
                if not c_text:
                    continue
                circ = CIRCLE_NUMS.get(c_idx, f"({c_idx})")
                is_correct = (highlight_answer and ans_num == c_idx)

                # 정답인 경우 원문자에 형광펜 서식 주입
                choice_p = ET.Element(f"{{{NS_HP}}}p", {
                    "id": str(abs(hash(f"{custom_q_num}_{c_idx}_{os.urandom(4)}")) % 2000000000),
                    "paraPrIDRef": "0",
                    "styleIDRef": "0",
                    "pageBreak": "0",
                    "columnBreak": "0",
                    "merged": "0",
                })

                if is_correct:
                    # 원문자 번호에 형광펜 칠하기
                    c_run_num = ET.SubElement(choice_p, f"{{{NS_HP}}}run", {"charPrIDRef": highlight_char_id})
                    ET.SubElement(c_run_num, f"{{{NS_HP}}}markPenBegin", {"color": "#FFFF00"})
                    t_num = ET.SubElement(c_run_num, f"{{{NS_HP}}}t")
                    t_num.text = circ
                    ET.SubElement(c_run_num, f"{{{NS_HP}}}markPenEnd")
                    # 선지 본문은 일반 폰트
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
                sec0_root.append(_create_paragraph("", column_break=True))
            else:
                # 우측단 문항 완료 -> 다음 페이지로 나눔 (pageBreak=1)
                sec0_root.append(_create_paragraph("", page_break=True))
        else:
            # 마지막 문항인데 좌측단(홀수 번째)에서 끝난 경우 우측단에 메모 공간 마련
            if pos_in_page == 0:
                sec0_root.append(_create_paragraph("", column_break=True))
                sec0_root.append(_create_paragraph("[ 오답 정리 및 메모란 ]", char_pr_id=normal_char_id))
                for _ in range(8):
                    sec0_root.append(_create_paragraph(""))

    # 꼬리말 안내 텍스트가 있으면 문서 끝에 삽입
    if footer_text:
        sec0_root.append(_create_paragraph(""))
        sec0_root.append(_create_paragraph(f"[{footer_text}]", char_pr_id=normal_char_id))

    file_map["Contents/section0.xml"] = ET.tostring(sec0_root, encoding="utf-8", xml_declaration=True)

    # 3. 새 HWPX 바이트 생성
    out_buf = io.BytesIO()
    with zipfile.ZipFile(out_buf, "w", compression=zipfile.ZIP_DEFLATED) as zf_out:
        for fname, fcontent in file_map.items():
            zf_out.writestr(fname, fcontent)

    return out_buf.getvalue()


def generate_explanation_handout(items: List[Dict[str, Any]], options: Optional[Dict[str, Any]] = None) -> bytes:
    """
    선택한 문항 목록으로 B4 단면 2문항 해설지 HWPX 문서 생성
    - 지문 결과 화면 좌측 하단 패널(explanation_text) 텍스트 주입
    - 사용자 지정 문항 번호와 원출처 명시 (예: 1번 [원출처: 2024년 고3 6월 21번 / 정답률 48%])
    """
    options = options or {}
    template_path = get_template_path(options.get("template_name"), is_explanation=True)
    header_title = options.get("header_title", "").strip() or "정답 및 해설"
    header_sub = options.get("header_sub", "").strip()
    footer_text = options.get("footer_text", "").strip()

    with zipfile.ZipFile(template_path, "r") as zf:
        file_map = {name: zf.read(name) for name in zf.namelist()}

    # 1. header.xml 처리
    hdr_root = ET.fromstring(file_map["Contents/header.xml"])
    normal_char_id, highlight_char_id = _inject_char_properties(hdr_root)
    file_map["Contents/header.xml"] = ET.tostring(hdr_root, encoding="utf-8", xml_declaration=True)

    # 2. section0.xml 파싱 및 본문 조립
    sec0_root = ET.fromstring(file_map["Contents/section0.xml"])

    first_p = sec0_root.find(f"{{{NS_HP}}}p")
    sec_pr = None
    if first_p is not None:
        sec_pr = first_p.find(f".//{{{NS_HP}}}secPr")

    sec0_root.clear()

    new_first_p = ET.SubElement(sec0_root, f"{{{NS_HP}}}p", {
        "id": "2000000001",
        "paraPrIDRef": "0",
        "styleIDRef": "0",
        "pageBreak": "0",
        "columnBreak": "0",
        "merged": "0",
    })
    first_run = ET.SubElement(new_first_p, f"{{{NS_HP}}}run", {"charPrIDRef": normal_char_id})
    if sec_pr is not None:
        first_run.append(sec_pr)

    if header_title:
        sec0_root.append(_create_paragraph(f"■ {header_title}", char_pr_id=normal_char_id))
    if header_sub:
        sec0_root.append(_create_paragraph(f"  ({header_sub})", char_pr_id=normal_char_id))
    if header_title or header_sub:
        sec0_root.append(_create_paragraph(""))

    total_q = len(items)
    for idx, item in enumerate(items):
        pos_in_page = (idx % 2)
        is_last_item = (idx == total_q - 1)

        custom_q_num = str(item.get("custom_q_num", idx + 1)).strip() or str(idx + 1)
        raw_id = item.get("id", "").strip("[]")
        q_num = item.get("q_num", "")
        crate = item.get("correct_rate")
        crate_str = f" / 정답률 {crate}%" if crate is not None else ""

        # 출처 헤더 작성
        source_label = f"{custom_q_num}번  [원출처: {raw_id}{crate_str}]"
        sec0_root.append(_create_paragraph(f"▶ {source_label}", char_pr_id=highlight_char_id))
        sec0_root.append(_create_paragraph(""))

        # 해설 텍스트 (지문 결과 화면 좌측 하단 패널 텍스트)
        exp_text = item.get("explanation_text") or "해설 정보가 등록되지 않았습니다."
        exp_lines = [line.rstrip() for line in exp_text.splitlines()]

        for eline in exp_lines:
            if not eline.strip():
                sec0_root.append(_create_paragraph(""))
                continue
            # [정답], [해석], [해설], [어휘] 헤더는 살짝 강조
            if re.match(r"^\s*\[(정답|해석|해설|의도|어휘|어구|구문)\]", eline):
                sec0_root.append(_create_paragraph(eline, char_pr_id=normal_char_id))
            else:
                sec0_root.append(_create_paragraph(eline, char_pr_id=normal_char_id))

        sec0_root.append(_create_paragraph(""))

        # 단 및 페이지 나눔
        if not is_last_item:
            if pos_in_page == 0:
                sec0_root.append(_create_paragraph("", column_break=True))
            else:
                sec0_root.append(_create_paragraph("", page_break=True))
        else:
            if pos_in_page == 0:
                sec0_root.append(_create_paragraph("", column_break=True))
                sec0_root.append(_create_paragraph("[ 메모 및 참고사항 ]", char_pr_id=normal_char_id))

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
