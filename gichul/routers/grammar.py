"""
05-gichul_db: 어법 분석, 어법 설정 및 어법 범주 주석 라우터 (gichul/routers/grammar.py)
"""

from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .. import database as db
from .. import grammar_analyzer
from ..services import grammar_service
from ..text_utils import normalize_bracket_id
from ..logging_config import get_logger

router = APIRouter()
logger = get_logger("gichul.routers.grammar")


class UserGrammarSettingsRequest(BaseModel):
    user_id: Optional[str] = "default_user"
    use_custom_tree: Optional[bool] = False
    custom_tree_json: Optional[str] = None
    custom_mapping_json: Optional[str] = None


class AddGrammarAnnotationRequest(BaseModel):
    category_id: Optional[int] = 0
    pos: Optional[str] = ""
    full_path: Optional[str] = ""
    leaf_name: str
    target_expression: Optional[str] = ""
    explanation: Optional[str] = "사용자 분석"
    source_type: Optional[str] = "USER"
    user_id: Optional[str] = "default_user"
    ai_model: Optional[str] = None


class BatchSetGrammarAnnotationsRequest(BaseModel):
    annotations: List[Dict[str, Any]] = []
    source_type: Optional[str] = "USER"
    user_id: Optional[str] = "default_user"


class BatchAnalyzeRequest(BaseModel):
    sentence_ids: Optional[List[str]] = None
    starred_only: Optional[bool] = False
    skip_already_analyzed: Optional[bool] = True
    limit: Optional[int] = 50


@router.post("/api/sentences/{sentence_id}/star")
def api_toggle_sentence_star(sentence_id: str):
    """문장 별표(⭐ 중요 문장 플래그) 토글 API"""
    clean_id = normalize_bracket_id(sentence_id)
    new_state = db.toggle_sentence_star(clean_id)
    return {"sentence_id": clean_id, "is_starred": new_state}


@router.post("/api/sentences/{sentence_id}/analyze-grammar")
def api_analyze_sentence_grammar(sentence_id: str):
    """단일 문장 실시간 AI 어법 분석 및 DB 저장"""
    clean_id = normalize_bracket_id(sentence_id)

    target = db.get_sentence(clean_id)
    if not target:
        found = db.search_sentences(sentence_ids=[clean_id])
        target = found[0] if found else None

    if not target:
        raise HTTPException(status_code=404, detail="문장을 찾을 수 없습니다.")

    try:
        result = grammar_service.analyze_and_save_sentence(target, sentence_id=clean_id)
        annos = result["annotations"]
        return {
            "success": True,
            "sentence_id": clean_id,
            "sentence_text": result["sentence_text"],
            "annotations": annos,
            "count": len(annos),
            "grammar_analyzed": 1
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI 어법 분석 실패: {str(e)}")


@router.get("/api/grammar/categories")
def api_get_grammar_categories(user_id: str = "default_user"):
    """현재 사용자에게 유효한 어법 범주표 및 커스텀 체계 메타데이터 반환"""
    return db.get_effective_grammar_categories(user_id)


@router.get("/api/grammar/settings")
def api_get_grammar_settings(user_id: str = "default_user"):
    """사용자 커스텀 어법 체계 설정 조회"""
    return db.get_user_grammar_settings(user_id)


@router.post("/api/grammar/settings")
def api_save_grammar_settings(req: UserGrammarSettingsRequest):
    """사용자 커스텀 어법 트리 및 매핑 설정 저장"""
    try:
        db.save_user_grammar_settings(
            user_id=req.user_id or "default_user",
            use_custom_tree=1 if req.use_custom_tree else 0,
            custom_tree_json=req.custom_tree_json,
            custom_mapping_json=req.custom_mapping_json
        )
        return {"success": True, "message": "어법 체계 설정이 성공적으로 저장되었습니다."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"어법 체계 저장 실패: {str(e)}")


@router.post("/api/grammar/settings/reset")
def api_reset_grammar_settings(user_id: str = "default_user"):
    """사용자 커스텀 어법 설정을 기본 243개 표준 체계로 초기화"""
    try:
        db.reset_user_grammar_settings(user_id)
        return {"success": True, "message": "기본 243개 표준 어법 체계로 복원되었습니다."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"어법 체계 초기화 실패: {str(e)}")


@router.post("/api/sentences/{sentence_id}/grammar-annotations")
def api_add_grammar_annotation(sentence_id: str, req: AddGrammarAnnotationRequest):
    """문장에 수동/사용자 어법 범주 추가"""
    clean_id = normalize_bracket_id(sentence_id)

    try:
        data = req.dict()
        db.add_sentence_grammar_annotation(
            clean_id, 
            data, 
            source_type=req.source_type or "USER", 
            user_id=req.user_id or "default_user",
            ai_model=req.ai_model
        )
        updated = db.get_sentence_grammar_annotations(clean_id)
        return {
            "success": True,
            "sentence_id": clean_id,
            "annotations": updated,
            "count": len(updated)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"어법 범주 추가 실패: {str(e)}")


@router.delete("/api/sentences/{sentence_id}/grammar-annotations/{identifier}")
def api_delete_grammar_annotation(sentence_id: str, identifier: int, source_type: Optional[str] = None):
    """문장의 특정 어법 범주 삭제 (source_type 선택적 필터)"""
    clean_id = normalize_bracket_id(sentence_id)

    try:
        db.delete_sentence_grammar_annotation(clean_id, identifier, source_type=source_type)
        updated = db.get_sentence_grammar_annotations(clean_id)
        return {
            "success": True,
            "sentence_id": clean_id,
            "annotations": updated,
            "count": len(updated)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"어법 범주 삭제 실패: {str(e)}")


@router.delete("/api/sentences/{sentence_id}/grammar")
def api_reset_sentence_grammar(sentence_id: str, source_type: Optional[str] = None):
    """문장의 어법 분석 결과 초기화 (AI 또는 USER 개별 초기화 또는 전체 초기화)"""
    clean_id = normalize_bracket_id(sentence_id)

    try:
        db.reset_sentence_grammar(clean_id, source_type=source_type)
        updated = db.get_sentence_grammar_annotations(clean_id)
        return {
            "success": True,
            "sentence_id": clean_id,
            "grammar_analyzed": 1 if updated else 0,
            "annotations": updated
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"어법 분석 초기화 실패: {str(e)}")


@router.post("/api/sentences/{sentence_id}/grammar-annotations/batch")
def api_batch_set_grammar_annotations(sentence_id: str, req: BatchSetGrammarAnnotationsRequest):
    """문장의 어법 범주 목록을 모달 선택값으로 일괄 저장 (지정된 source_type 항목만 교체)"""
    clean_id = normalize_bracket_id(sentence_id)

    try:
        updated = db.set_sentence_grammar_annotations(
            clean_id, 
            req.annotations, 
            source_type=req.source_type or "USER", 
            user_id=req.user_id or "default_user"
        )
        return {
            "success": True,
            "sentence_id": clean_id,
            "annotations": updated,
            "count": len(updated)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"어법 범주 일괄 설정 실패: {str(e)}")


@router.post("/api/sentences/batch-analyze-grammar")
def api_batch_analyze_grammar(req: BatchAnalyzeRequest):
    """다중 문장 배치 AI 어법 분석 (선택된 활성 모델 엄격 교집합 적용)"""
    active_configs = grammar_analyzer.get_active_ai_configs()
    valid_configs = [c for c in active_configs if c["api_key"]]
    if not valid_configs:
        raise HTTPException(status_code=400, detail="활성화된 AI 모델 중 유효한 API Key가 등록된 모델이 없습니다. 상단 [🔑 AI 설정]에서 먼저 등록해 주세요.")

    if req.sentence_ids:
        # 선택한 문장만 SQL에서 바로 조회 (전체 7만 문장을 읽고 거르던 방식 제거)
        sentences = db.search_sentences(sentence_ids=req.sentence_ids)
    else:
        limit_val = req.limit or 0
        sentences = db.search_sentences(is_starred=True if req.starred_only else None, limit=limit_val)

    # 이미 어법 분석이 완료된 문장 필터링
    if req.skip_already_analyzed:
        sentences = [s for s in sentences if not s.get("grammar_analyzed") and not s.get("grammar_annotations")]

    if not sentences:
        return {
            "total_processed": 0,
            "results": [],
            "message": "선택된 문장들이 이미 모두 어법 분석 완료 상태입니다."
        }

    passages_cache = {}
    results = []
    for s in sentences:
        grammar_service.get_cached_passage(s.get("passage_id"), passages_cache)

        try:
            result = grammar_service.analyze_and_save_sentence(s, passages_cache)
            annos = result["annotations"]
            results.append({
                "sentence_id": s["id"],
                "sentence_text": s.get("sentence_text", ""),
                "count": len(annos),
                "success": True,
                "annotations": annos,
                "grammar_analyzed": 1
            })
        except Exception as e:
            results.append({
                "sentence_id": s["id"],
                "sentence_text": s.get("sentence_text", ""),
                "error": str(e),
                "success": False,
                "annotations": [],
                "grammar_analyzed": 0
            })

    return {
        "total_processed": len(results),
        "results": results
    }
