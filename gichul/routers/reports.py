"""
05-gichul_db: 문항 및 문장 오류 신고 관리 라우터 (gichul/routers/reports.py)
"""

from typing import List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .. import database as db
from ..logging_config import get_logger

router = APIRouter()
logger = get_logger("gichul.routers.reports")


class ErrorReportCreateRequest(BaseModel):
    target_type: str                   # 'passage' | 'sentence'
    passage_id: Optional[str] = None
    sentence_id: Optional[str] = None
    exam_id: Optional[str] = None
    error_types: Optional[List[str]] = []
    comment: Optional[str] = ""


@router.post("/api/reports")
def api_create_report(req: ErrorReportCreateRequest):
    """문항 또는 문장 오류 신고 접수"""
    if req.target_type not in ("passage", "sentence"):
        raise HTTPException(status_code=400, detail="target_type은 'passage' 또는 'sentence'여야 합니다.")
    if req.target_type == "passage" and not req.passage_id:
        raise HTTPException(status_code=400, detail="지문 오류 신고 시 passage_id가 필요합니다.")
    if req.target_type == "sentence" and not req.sentence_id:
        raise HTTPException(status_code=400, detail="문장 오류 신고 시 sentence_id가 필요합니다.")

    try:
        res = db.create_error_report(
            target_type=req.target_type,
            passage_id=req.passage_id,
            sentence_id=req.sentence_id,
            exam_id=req.exam_id,
            error_types=req.error_types,
            comment=req.comment,
        )
        return res
    except Exception as e:
        logger.error(f"오류 신고 등록 실패: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"오류 신고 등록에 실패했습니다: {e}")


@router.get("/api/reports")
def api_get_reports(target_type: Optional[str] = None, status: str = "pending"):
    """신고된 오류 목록 조회"""
    try:
        reports = db.get_error_reports(target_type=target_type, status=status)
        return {"success": True, "count": len(reports), "reports": reports}
    except Exception as e:
        logger.error(f"오류 신고 목록 조회 실패: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"오류 신고 목록 조회에 실패했습니다: {e}")


@router.get("/api/reports/count")
def api_get_reports_count():
    """미해결 오류 건수 조회 (헤더 배지용)"""
    try:
        count = db.get_pending_reports_count()
        return {"success": True, "count": count}
    except Exception as e:
        logger.error(f"오류 신고 건수 조회 실패: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"오류 신고 건수 조회에 실패했습니다: {e}")


@router.delete("/api/reports/{report_id}")
def api_delete_report(report_id: int):
    """신고된 오류 항목 삭제 (수정 완료 처리)"""
    try:
        success = db.delete_error_report(report_id)
        if not success:
            raise HTTPException(status_code=404, detail="해당 오류 신고 항목을 찾을 수 없습니다.")
        return {"success": True, "deleted_id": report_id, "message": "오류 신고 항목이 삭제되었습니다."}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"오류 신고 항목 삭제 실패: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"오류 신고 항목 삭제에 실패했습니다: {e}")
