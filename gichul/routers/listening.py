"""
05-gichul_db: 듣기 문항 오디오 생성, ZIP 다운로드 및 동기화 라우터 (gichul/routers/listening.py)
"""

import os
from typing import Optional
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse, FileResponse

from .. import tts_service
from .. import listening_parser
from ..text_utils import normalize_bracket_id
from ..core.state import _ingest_serialized
from ..logging_config import get_logger

router = APIRouter()
logger = get_logger("gichul.routers.listening")


@router.get("/api/tts/progress/{job_id}")
def api_tts_progress(job_id: str):
    """음성 합성 진행률 조회 (프론트가 생성 요청 시 넘긴 job_id 기준)"""
    return tts_service.get_tts_progress(job_id)


@router.post("/api/passages/{passage_id:path}/generate-audio")
async def api_generate_passage_audio(passage_id: str, job_id: Optional[str] = None):
    """특정 듣기 문항의 대본을 Edge-TTS 또는 ElevenLabs M/W 듀얼 보이스로 합성하여 MP3 생성
    (job_id 쿼리를 주면 /api/tts/progress/{job_id}로 진행률을 조회할 수 있다)"""
    try:
        clean_id = normalize_bracket_id(passage_id)
        result = await tts_service.generate_passage_audio(clean_id, job_id=job_id)
        if not result.get("success"):
            return JSONResponse(status_code=400, content=result)
        return result
    except Exception as e:
        logger.error(f"문항 음성 합성 실패 ({passage_id}): {e}")
        return JSONResponse(
            status_code=400,
            content={"success": False, "message": str(e), "detail": str(e)}
        )


@router.post("/api/exams/{exam_id:path}/generate-listening-audio")
async def api_generate_exam_listening_audio(exam_id: str, job_id: Optional[str] = None):
    """시험지의 1~17번 전체 듣기 문항 오디오를 일괄 생성 (job_id로 진행률 조회 가능)"""
    try:
        clean_id = normalize_bracket_id(exam_id)
        result = await tts_service.generate_exam_listening_audio(clean_id, job_id=job_id)
        return result
    except Exception as e:
        logger.error(f"시험지 전체 음성 합성 실패 ({exam_id}): {e}")
        return JSONResponse(
            status_code=400,
            content={"success": False, "message": str(e), "detail": str(e)}
        )


@router.get("/api/exams/{exam_id}/download-listening-zip")
def api_download_listening_zip(exam_id: str):
    """시험지의 전체 듣기 MP3 파일들을 ZIP 파일로 묶어서 다운로드"""
    clean_id = normalize_bracket_id(exam_id)
    try:
        result = tts_service.create_listening_zip(clean_id)
    except ValueError as e:
        # 듣기 문항이 없거나 생성된 MP3가 하나도 없는 경우
        raise HTTPException(status_code=404, detail=str(e))
    zip_path = os.path.join(tts_service.AUDIO_DIR, result["zip_filename"])
    if not os.path.exists(zip_path):
        raise HTTPException(status_code=404, detail="생성된 듣기 오디오 파일이 없거나 압축 생성에 실패했습니다.")
    safe_name = clean_id.replace("[", "").replace("]", "").replace(" ", "_")
    filename = f"{safe_name}_listening_audio.zip"
    return FileResponse(zip_path, media_type="application/zip", filename=filename)


@router.post("/api/exams/{exam_id}/sync-listening")
@_ingest_serialized
def api_sync_exam_listening(exam_id: str):
    """기존 시험지의 듣기 문항(1~17번) 크롭 이미지 및 대본/FELS 재동기화"""
    clean_id = normalize_bracket_id(exam_id)
    result = listening_parser.sync_exam_listening(clean_id)
    # sync_exam_listening은 dict를 반환하므로 개수만 꺼낸다 (기존에는 dict 전체가 synced_count로 나감)
    synced = result.get("synced_count", 0) if isinstance(result, dict) else result
    return {"success": True, "exam_id": clean_id, "synced_count": synced}
