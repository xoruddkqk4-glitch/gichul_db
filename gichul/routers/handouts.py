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
    generate_sentence_handout,
    generate_listening_question_handout,
    generate_listening_explanation_handout,
    generate_listening_handout_zip,
    _prepare_listening_item_data,
    format_sentence_source,
    list_templates,
    save_uploaded_template,
)
from ..tts_service import (
    merge_listening_mp3s,
    AUDIO_DIR,
    sanitize_filename,
    check_listening_audio_status,
    start_listening_audio_merge_task,
    cancel_listening_audio_merge,
    get_listening_audio_merge_progress,
    get_listening_audio_merge_result,
)
from ..logging_config import get_logger

logger = get_logger("gichul.routers.handouts")
router = APIRouter(prefix="/api/handouts", tags=["handouts"])


class HandoutGenerateRequest(BaseModel):
    handout_type: str = Field(default="question", description="question | explanation | both_zip")
    passage_ids: List[str] = Field(default_factory=list, description="선택된 지문 ID 목록 (정렬 순서 유지)")
    custom_q_nums: Dict[str, str] = Field(default_factory=dict, description="지문 ID별 사용자 지정 문항 번호 맵")
    header_left: Optional[str] = Field(default="", description="왼쪽 상단 텍스트")
    header_center: Optional[str] = Field(default="", description="가운데 상단 텍스트 (메인 제목)")
    header_right: Optional[str] = Field(default="", description="오른쪽 상단 텍스트 (인적사항/소속)")
    header_title: Optional[str] = Field(default="", description="머리말 제목 (하위 호환)")
    header_sub: Optional[str] = Field(default="", description="머리말 소제목/인적사항 (하위 호환)")
    footer_text: Optional[str] = Field(default="", description="꼬리말 텍스트")
    highlight_answer: bool = Field(default=True, description="정답 형광펜 표시 여부 (문제지용)")
    template_name: Optional[str] = Field(default=None, description="선택된 템플릿 파일명")


class HandoutPreviewRequest(BaseModel):
    passage_ids: List[str] = Field(default_factory=list, description="지문 ID 목록")


class SentenceHandoutGenerateRequest(BaseModel):
    sentence_ids: List[str] = Field(default_factory=list, description="선택된 문장 ID 목록 (정렬 순서 유지)")
    custom_sentence_nums: Dict[str, str] = Field(default_factory=dict, description="문장 ID별 사용자 지정 문장 번호 맵")
    start_num: int = Field(default=1, description="미지정 시 순차 시작 번호")
    include_concept_table: bool = Field(default=True, description="개념 설명 1x1 테이블 포함 여부 (True: 6문장, False: 10문장)")
    main_title: Optional[str] = Field(default="핵심 기출 구문 분석", description="문장 유인물 메인 제목")
    header_left: Optional[str] = Field(default="", description="왼쪽 상단 텍스트")
    header_center: Optional[str] = Field(default="", description="가운데 상단 텍스트")
    header_right: Optional[str] = Field(default="", description="오른쪽 상단 텍스트")
    template_name: Optional[str] = Field(default=None, description="선택된 템플릿 파일명")


class SentenceHandoutPreviewRequest(BaseModel):
    sentence_ids: List[str] = Field(default_factory=list, description="문장 ID 목록")


class ListeningHandoutGenerateRequest(BaseModel):
    handout_type: str = Field(default="question", description="question | explanation | zip")
    passage_ids: List[str] = Field(default_factory=list, description="선택된 지문 ID 목록 (정렬 순서 유지)")
    custom_q_nums: Dict[str, str] = Field(default_factory=dict, description="지문 ID별 사용자 지정 문항 번호 맵")
    header_left: Optional[str] = Field(default="", description="왼쪽 상단 텍스트")
    header_center: Optional[str] = Field(default="", description="가운데 상단 텍스트")
    header_right: Optional[str] = Field(default="", description="오른쪽 상단 텍스트")
    template_name: Optional[str] = Field(default=None, description="선택된 템플릿 파일명")


class ListeningHandoutPreviewRequest(BaseModel):
    passage_ids: List[str] = Field(default_factory=list, description="선택된 지문 ID 목록")


class ListeningAudioDownloadRequest(BaseModel):
    passage_ids: List[str] = Field(default_factory=list, description="선택된 지문 ID 목록")
    project_name: Optional[str] = Field(default="듣기유인물", description="프로젝트 명칭")


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
        "header_left": (req.header_left or "").strip(),
        "header_center": (req.header_center or req.header_title or "").strip(),
        "header_right": (req.header_right or req.header_sub or "").strip(),
        "header_title": (req.header_center or req.header_title or "").strip(),
        "header_sub": (req.header_right or req.header_sub or "").strip(),
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


@router.post("/sentence-preview-info")
def api_get_sentence_preview_info(req: SentenceHandoutPreviewRequest):
    """선택된 문장들의 유인물 제작소 표시용 메타데이터 반환"""
    if not req.sentence_ids:
        return {"items": []}

    items = []
    for sid in req.sentence_ids:
        s = db.get_sentence(sid)
        if s:
            items.append({
                "id": s["id"],
                "sentence_text": s.get("sentence_text", ""),
                "source_label": format_sentence_source(s["id"]),
                "passage_id": s.get("passage_id", ""),
                "order_index": s.get("order_index", 0),
            })
        else:
            items.append({
                "id": sid,
                "sentence_text": "",
                "source_label": format_sentence_source(sid),
                "passage_id": "",
                "order_index": 0,
            })

    return {"items": items}


@router.post("/generate-sentence")
def api_generate_sentence_handout(req: SentenceHandoutGenerateRequest):
    """A4 단면 문장 유인물 HWPX 생성 및 바이너리 다운로드 스트리밍"""
    if not req.sentence_ids:
        raise HTTPException(status_code=400, detail="유인물로 제작할 문장을 1개 이상 선택해야 합니다.")

    items = []
    custom_map = req.custom_sentence_nums or {}
    start_n = req.start_num or 1
    for idx, sid in enumerate(req.sentence_ids):
        s = db.get_sentence(sid)
        if s:
            s_dict = dict(s)
            s_dict["custom_num"] = str(custom_map.get(sid, str(start_n + idx))).strip()
            items.append(s_dict)
        else:
            logger.warning("유인물 생성 대상 문장을 찾을 수 없음: %s", sid)

    if not items:
        raise HTTPException(status_code=404, detail="선택된 문장의 데이터를 DB에서 찾을 수 없습니다.")

    options = {
        "header_left": (req.header_left or "").strip(),
        "header_center": (req.header_center or "").strip(),
        "header_right": (req.header_right or "").strip(),
        "main_title": (req.main_title or "").strip() or "핵심 기출 구문 분석",
        "include_concept_table": req.include_concept_table,
        "template_name": req.template_name,
    }

    try:
        file_bytes = generate_sentence_handout(items, options)
        actual_cnt = min(len(items), 6 if req.include_concept_table else 10)
        default_filename = f"문장유인물_A4_{actual_cnt}문장.hwpx"

        encoded_filename = urllib.parse.quote(default_filename)
        fallback_ascii = f"sentence_handout_{actual_cnt}.hwpx"
        headers = {
            "Content-Disposition": f'attachment; filename="{fallback_ascii}"; filename*=UTF-8\'\'{encoded_filename}',
            "Access-Control-Expose-Headers": "Content-Disposition",
        }

        return Response(content=file_bytes, media_type="application/haansofthwpx", headers=headers)

    except Exception as e:
        logger.error("문장 유인물 HWPX 생성 실패: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"문장 유인물 생성 중 오류가 발생했습니다: {e}")


@router.post("/listening/preview-info")
def api_get_listening_preview_info(req: ListeningHandoutPreviewRequest):
    """선택된 듣기 문항들의 유인물 제작소 표시용 상세 데이터(약형드랩, 우리말 해석, script, 정답, 음원 여부) 반환"""
    if not req.passage_ids:
        return {"items": []}

    items = []
    for pid in req.passage_ids:
        clean_id = normalize_bracket_id(pid)
        p = db.get_passage(pid) or db.get_passage(clean_id)
        if p:
            p_dict = dict(p)
            data = _prepare_listening_item_data(p_dict)
            audio_url = p_dict.get("audio_file_path") or p_dict.get("audio_url")
            has_audio = False
            if audio_url:
                local_rel = audio_url.replace("/static/audio/", "")
                cand = os.path.join(AUDIO_DIR, local_rel)
                has_audio = os.path.exists(cand)
            if not has_audio:
                safe_id = sanitize_filename(p_dict.get("id", ""))
                cand = os.path.join(AUDIO_DIR, f"{safe_id}.mp3")
                has_audio = os.path.exists(cand)

            items.append({
                "id": p_dict.get("id"),
                "question_title": data["question_title"],
                "question_type": data["question_type"],
                "question_text": data["question_text"],
                "fels_blank": data["fels_blank"],
                "korean_translation": data["korean_translation"],
                "script_text": data["script_text"],
                "answer_display": data["answer_display"],
                "has_audio": has_audio,
            })
        else:
            items.append({
                "id": pid,
                "question_title": "",
                "question_type": "",
                "question_text": "",
                "fels_blank": "",
                "korean_translation": "",
                "script_text": "",
                "answer_display": "-",
                "has_audio": False,
            })

    return {"items": items}


@router.post("/listening/download")
def api_download_listening_handout(req: ListeningHandoutGenerateRequest):
    """B4 세로 듣기 문제지 / 해설지 / 일괄 ZIP 파일 다운로드 스트리밍"""
    if not req.passage_ids:
        raise HTTPException(status_code=400, detail="유인물로 제작할 듣기 문항을 1개 이상 선택해야 합니다.")

    items = _resolve_passages_with_custom_nums(req.passage_ids, req.custom_q_nums)
    if not items:
        raise HTTPException(status_code=404, detail="선택된 문항의 데이터를 DB에서 찾을 수 없습니다.")

    options = {
        "header_left": (req.header_left or "").strip(),
        "header_center": (req.header_center or "").strip(),
        "header_right": (req.header_right or "").strip(),
        "template_name": req.template_name,
    }

    try:
        htype = (req.handout_type or "question").lower()
        if htype == "question":
            file_bytes = generate_listening_question_handout(items, options)
            default_filename = f"듣기문제유인물_B4_{len(items)}문항.hwpx"
            media_type = "application/haansofthwpx"
        elif htype == "explanation":
            file_bytes = generate_listening_explanation_handout(items, options)
            default_filename = f"듣기해설유인물_B4_{len(items)}문항.hwpx"
            media_type = "application/haansofthwpx"
        elif htype in ("zip", "both_zip"):
            file_bytes = generate_listening_handout_zip(items, options)
            default_filename = f"듣기유인물_일괄패키지_B4_{len(items)}문항.zip"
            media_type = "application/zip"
        else:
            raise HTTPException(status_code=400, detail=f"지원하지 않는 듣기 유인물 종류입니다: {htype}")

        encoded_filename = urllib.parse.quote(default_filename)
        fallback_ascii = f"listening_{htype}_{len(items)}.hwpx" if not default_filename.endswith(".zip") else f"listening_{len(items)}.zip"
        headers = {
            "Content-Disposition": f'attachment; filename="{fallback_ascii}"; filename*=UTF-8\'\'{encoded_filename}',
            "Access-Control-Expose-Headers": "Content-Disposition",
        }

        return Response(content=file_bytes, media_type=media_type, headers=headers)

    except HTTPException:
        raise
    except Exception as e:
        logger.error("듣기 유인물 생성 실패: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"듣기 유인물 생성 중 오류가 발생했습니다: {e}")


@router.post("/listening/download-audio")
async def api_download_listening_merged_audio(req: ListeningAudioDownloadRequest):
    """선택된 듣기 문항들을 순서대로 결합한 단일 통합 MP3 오디오 스트리밍"""
    if not req.passage_ids:
        raise HTTPException(status_code=400, detail="오디오로 결합할 듣기 문항이 없습니다.")

    try:
        audio_bytes = await merge_listening_mp3s(req.passage_ids)
        safe_proj = re.sub(r'[^a-zA-Z0-9가-힣_\-]', '_', (req.project_name or "듣기유인물").strip()) or "듣기유인물"
        default_filename = f"{safe_proj}_전체통합듣기_{len(req.passage_ids)}문항.mp3"

        encoded_filename = urllib.parse.quote(default_filename)
        fallback_ascii = f"listening_merged_{len(req.passage_ids)}.mp3"
        headers = {
            "Content-Disposition": f'attachment; filename="{fallback_ascii}"; filename*=UTF-8\'\'{encoded_filename}',
            "Access-Control-Expose-Headers": "Content-Disposition",
        }

        return Response(content=audio_bytes, media_type="audio/mpeg", headers=headers)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("듣기 통합 MP3 생성 실패: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"듣기 통합 MP3 결합 중 오류가 발생했습니다: {e}")


@router.post("/listening/audio-status")
async def api_get_listening_audio_status(req: ListeningAudioDownloadRequest):
    """선택된 듣기 문항들의 MP3 음원 파일 존재 여부 및 상세 상태 반환"""
    if not req.passage_ids:
        raise HTTPException(status_code=400, detail="문항 목록이 비어있습니다.")
    try:
        status_info = check_listening_audio_status(req.passage_ids)
        return status_info
    except Exception as e:
        logger.error("듣기 음원 상태 조회 실패: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"듣기 음원 상태 확인 중 오류가 발생했습니다: {e}")


@router.post("/listening/start-merge-audio")
async def api_start_merge_listening_audio(req: ListeningAudioDownloadRequest):
    """비동기 통합 MP3 음원 결합 및 인코딩 작업 시작 (job_id 발급)"""
    if not req.passage_ids:
        raise HTTPException(status_code=400, detail="결합할 듣기 문항이 없습니다.")
    try:
        job_id = start_listening_audio_merge_task(req.passage_ids, req.project_name or "듣기유인물")
        return {"job_id": job_id, "status": "processing", "message": "작업이 시작되었습니다."}
    except Exception as e:
        logger.error("통합 MP3 작업 시작 실패: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"작업 시작 실패: {e}")


@router.get("/listening/merge-audio-progress/{job_id}")
async def api_get_merge_audio_progress(job_id: str):
    """통합 MP3 결합 작업의 실시간 진행률 및 상태 폴링"""
    progress = get_listening_audio_merge_progress(job_id)
    if progress.get("status") == "not_found":
        raise HTTPException(status_code=404, detail="해당 작업을 찾을 수 없습니다.")
    return progress


@router.post("/listening/cancel-merge-audio/{job_id}")
async def api_cancel_merge_listening_audio(job_id: str):
    """진행 중인 통합 MP3 음원 생성/결합 작업 즉시 중단"""
    success = cancel_listening_audio_merge(job_id)
    return {"job_id": job_id, "cancelled": success, "message": "중단 요청이 전달되었습니다." if success else "진행 중인 작업이 아니거나 이미 완료되었습니다."}


@router.get("/listening/download-merged-result/{job_id}")
async def api_download_merged_audio_result(job_id: str):
    """완료된 통합 MP3 결과 파일 스트리밍 다운로드"""
    audio_bytes, filename = get_listening_audio_merge_result(job_id)
    if not audio_bytes:
        raise HTTPException(status_code=404, detail="완료된 오디오 파일이 없거나 아직 작업 중입니다.")

    safe_filename = filename or f"listening_merged_{job_id[:8]}.mp3"
    encoded_filename = urllib.parse.quote(safe_filename)
    fallback_ascii = f"listening_merged_{job_id[:8]}.mp3"
    headers = {
        "Content-Disposition": f'attachment; filename="{fallback_ascii}"; filename*=UTF-8\'\'{encoded_filename}',
        "Access-Control-Expose-Headers": "Content-Disposition",
    }
    return Response(content=audio_bytes, media_type="audio/mpeg", headers=headers)

