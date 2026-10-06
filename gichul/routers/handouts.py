"""
05-gichul_db: 교사용 B4 유인물 생성 및 템플릿 관리 REST API (gichul/routers/handouts.py)
- 선택된 문항 목록으로 B4 문제지 HWPX / 해설지 HWPX / ZIP 일괄 생성
- 사용자 지정 문항 번호(custom_q_num) 적용
- 머리말(Header) / 꼬리말(Footer) 동적 반영
- HWPX 양식 템플릿 목록 조회 및 커스텀 양식 업로드 API
"""

import os
import re
import urllib.parse
from typing import List, Dict, Optional, Any
from fastapi import APIRouter, HTTPException, UploadFile, File, Response
from pydantic import BaseModel, Field

from .. import database as db
from ..text_utils import normalize_bracket_id
from ..services.hwpx_generator import (
    generate_question_handout,
    generate_explanation_handout,
    generate_handout_zip,
    list_templates,
    save_uploaded_template,
)
from ..logging_config import get_logger

logger = get_logger("gichul.routers.handouts")
router = APIRouter(prefix="/api/handouts", tags=["handouts"])


class HandoutGenerateRequest(BaseModel):
    handout_type: str = Field(default="question", description="question | explanation | both_zip")
    passage_ids: List[str] = Field(default_factory=list, description="선택된 지문 ID 목록 (정렬 순서 유지)")
    custom_q_nums: Dict[str, str] = Field(default_factory=dict, description="지문 ID별 사용자 지정 문항 번호 맵")
    header_title: Optional[str] = Field(default="", description="머리말 제목")
    header_sub: Optional[str] = Field(default="", description="머리말 소제목/인적사항")
    footer_text: Optional[str] = Field(default="", description="꼬리말 텍스트")
    highlight_answer: bool = Field(default=True, description="정답 형광펜 표시 여부 (문제지용)")
    template_name: Optional[str] = Field(default=None, description="선택된 템플릿 파일명")


class HandoutPreviewRequest(BaseModel):
    passage_ids: List[str] = Field(default_factory=list, description="지문 ID 목록")


def _resolve_passages_with_custom_nums(passage_ids: List[str], custom_q_nums: Dict[str, str]) -> List[Dict[str, Any]]:
    """요청된 지문 ID 목록을 순회하여 DB에서 조회하고 custom_q_num을 매핑"""
    items = []
    for idx, pid in enumerate(passage_ids):
        clean_id = normalize_bracket_id(pid)
        # 세트 문항 처리 (예: [고3-2024년-06월-41~42번])
        set_match = re.search(r"-(\d{1,2})~(\d{1,2})번\]?$", clean_id)
        if set_match:
            start_q = int(set_match.group(1))
            end_q = int(set_match.group(2))
            exam_prefix = re.sub(r"-\d{1,2}~\d{1,2}번\]?$", "", clean_id).strip("[]")
            
            # 첫 번째 문항으로 기본 정보 조회
            first_sub_id = f"[{exam_prefix}-{start_q}번]"
            p = db.get_passage(first_sub_id)
            if p:
                p_dict = dict(p)
                p_dict["id"] = clean_id
                c_num = custom_q_nums.get(pid) or custom_q_nums.get(clean_id) or str(idx + 1)
                p_dict["custom_q_num"] = str(c_num).strip()
                items.append(p_dict)
            continue

        p = db.get_passage(clean_id)
        if p:
            p_dict = dict(p)
            c_num = custom_q_nums.get(pid) or custom_q_nums.get(clean_id) or str(idx + 1)
            p_dict["custom_q_num"] = str(c_num).strip()
            items.append(p_dict)
        else:
            logger.warning("유인물 생성 대상 지문을 찾을 수 없음: %s", clean_id)

    return items


@router.get("/templates")
def api_list_templates():
    """등록된 HWPX 양식 템플릿 목록 반환"""
    try:
        templates = list_templates()
        return {"success": True, "templates": templates}
    except Exception as e:
        logger.error("템플릿 목록 조회 실패: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"템플릿 목록을 조회하지 못했습니다: {e}")


@router.post("/templates/upload")
async def api_upload_template(file: UploadFile = File(...)):
    """교사 자체 B4 HWPX 양식 파일 업로드 및 저장"""
    if not file.filename.lower().endswith(".hwpx"):
        raise HTTPException(status_code=400, detail="HWPX 파일(.hwpx)만 업로드 가능합니다.")

    try:
        content = await file.read()
        saved_name = save_uploaded_template(file.filename, content)
        templates = list_templates()
        return {
            "success": True,
            "filename": saved_name,
            "message": f"'{saved_name}' 양식이 성공적으로 저장되었습니다.",
            "templates": templates
        }
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.error("템플릿 업로드 실패: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"템플릿 저장 중 오류가 발생했습니다: {e}")


@router.post("/preview-info")
def api_get_preview_info(req: HandoutPreviewRequest):
    """선택된 지문들의 유인물 제작소 표시용 메타데이터 반환"""
    if not req.passage_ids:
        return {"items": []}

    items = _resolve_passages_with_custom_nums(req.passage_ids, {})
    return {
        "items": [
            {
                "id": p["id"],
                "exam_id": p.get("exam_id", ""),
                "q_num": p.get("q_num", 0),
                "question_title": p.get("question_title", ""),
                "question_type": p.get("question_type", "기타"),
                "answer_text": p.get("answer_text", ""),
                "correct_rate": p.get("correct_rate"),
                "explanation_text": p.get("explanation_text", ""),
            }
            for p in items
        ]
    }


@router.post("/generate")
def api_generate_handout(req: HandoutGenerateRequest):
    """B4 문제지 HWPX / 해설지 HWPX / ZIP 일괄 생성 및 바이너리 다운로드"""
    if not req.passage_ids:
        raise HTTPException(status_code=400, detail="유인물로 제작할 문항을 1개 이상 선택해야 합니다.")

    items = _resolve_passages_with_custom_nums(req.passage_ids, req.custom_q_nums)
    if not items:
        raise HTTPException(status_code=404, detail="선택된 문항의 데이터를 DB에서 찾을 수 없습니다.")

    options = {
        "header_title": req.header_title or "",
        "header_sub": req.header_sub or "",
        "footer_text": req.footer_text or "",
        "highlight_answer": req.highlight_answer,
        "template_name": req.template_name,
    }

    try:
        htype = req.handout_type.lower()
        if htype == "question":
            file_bytes = generate_question_handout(items, options)
            default_filename = f"문제지_B4_유인물_{len(items)}문항.hwpx"
            media_type = "application/haansofthwpx"
        elif htype == "explanation":
            file_bytes = generate_explanation_handout(items, options)
            default_filename = f"해설지_B4_유인물_{len(items)}문항.hwpx"
            media_type = "application/haansofthwpx"
        elif htype in ("both_zip", "zip"):
            file_bytes = generate_handout_zip(items, options)
            default_filename = f"유인물_B4_패키지_{len(items)}문항.zip"
            media_type = "application/zip"
        else:
            raise HTTPException(status_code=400, detail=f"지원하지 않는 유인물 유형입니다: {req.handout_type}")

        # RFC 5987 한글 파일명 인코딩 및 RFC 2616 호환 fallback
        encoded_filename = urllib.parse.quote(default_filename)
        fallback_ascii = f"handout_{len(items)}.hwpx" if default_filename.endswith(".hwpx") else f"handout_{len(items)}.zip"
        headers = {
            "Content-Disposition": f'attachment; filename="{fallback_ascii}"; filename*=UTF-8\'\'{encoded_filename}',
            "Access-Control-Expose-Headers": "Content-Disposition",
        }

        return Response(content=file_bytes, media_type=media_type, headers=headers)

    except Exception as e:
        logger.error("유인물 HWPX 생성 실패: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"유인물 생성 중 오류가 발생했습니다: {e}")
