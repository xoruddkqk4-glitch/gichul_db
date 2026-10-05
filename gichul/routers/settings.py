"""
05-gichul_db: AI 및 TTS 환경 설정, 모델 목록, 연결 테스트 라우터 (gichul/routers/settings.py)
"""

import json
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Body
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from .. import database as db
from .. import grammar_analyzer
from .. import tts_service
from ..logging_config import get_logger

router = APIRouter()
logger = get_logger("gichul.routers.settings")


class SingleProviderTestRequest(BaseModel):
    provider: str
    api_key: Optional[str] = ""
    model: Optional[str] = ""
    base_url: Optional[str] = ""


class AISettingsRequest(BaseModel):
    provider: Optional[str] = None
    api_key: Optional[str] = ""
    model: Optional[str] = ""
    test_now: Optional[bool] = False
    active_providers: Optional[List[str]] = None
    consensus_mode: Optional[str] = None
    providers: Optional[Dict[str, Dict[str, str]]] = None
    openrouter_ensemble: Optional[bool] = None
    openrouter_ensemble_models: Optional[List[str]] = None
    # TTS 엔진 설정 (Edge-TTS 및 ElevenLabs)
    tts_engine: Optional[str] = None
    edge_tts_voice_male: Optional[str] = None
    edge_tts_voice_female: Optional[str] = None
    edge_tts_rate: Optional[str] = None
    elevenlabs_api_key: Optional[str] = None
    elevenlabs_voice_male: Optional[str] = None
    elevenlabs_voice_female: Optional[str] = None
    elevenlabs_model_id: Optional[str] = None


class TTSEngineRequest(BaseModel):
    engine: str


def describe_non_ascii(value: str) -> str:
    """문자열에 ASCII 외 문자가 있으면 '위치: 문자' 목록을 반환 (없으면 빈 문자열)"""
    found = [f"{i + 1}번째 '{ch}'" for i, ch in enumerate(value) if ord(ch) > 127]
    return ", ".join(found[:5]) + (" 외" if len(found) > 5 else "")


@router.get("/api/settings/ai")
def api_get_ai_settings():
    """현재 저장된 모든 AI Provider의 설정 및 활성화 현황 종합 반환"""
    cfg = grammar_analyzer.get_all_ai_configs()
    # 레거시 하위 호환 필드 결합
    legacy_p, legacy_k, legacy_m = grammar_analyzer.get_ai_config()
    cfg["provider"] = legacy_p
    cfg["model"] = legacy_m
    cfg["has_key"] = bool(legacy_k)
    cfg["masked_key"] = cfg["providers"].get(legacy_p, {}).get("masked_key", "")
    cfg["tts"] = tts_service.get_tts_config()
    return cfg


@router.get("/api/openrouter/top-models")
def api_get_openrouter_top_models(force_refresh: bool = False):
    """OpenRouter Top 5 추천 모델 정보 실시간 조회 및 반환"""
    models = grammar_analyzer.get_openrouter_top_models(force_refresh=force_refresh)
    return {"success": True, "models": models}


@router.get("/api/openrouter/models")
def api_get_openrouter_all_models(force_refresh: bool = False):
    """OpenRouter 전체 실시간 모델 목록 및 현재 설정된 앙상블 3개 모델 반환"""
    models = grammar_analyzer.get_all_openrouter_models(force_refresh=force_refresh)
    top_models = grammar_analyzer.get_openrouter_top_models(force_refresh=force_refresh)
    ensemble = grammar_analyzer.get_openrouter_ensemble_models()
    return {
        "success": True,
        "total": len(models),
        "models": models,
        "top_models": top_models,
        "current_ensemble": ensemble
    }


@router.get("/api/lmstudio/models")
def api_get_lmstudio_models(base_url: Optional[str] = None):
    """LM Studio 로컬 서버에서 다운로드/로드된 모델 목록 실시간 조회"""
    b_url = base_url or grammar_analyzer.get_lmstudio_base_url()
    models = grammar_analyzer.get_available_lmstudio_models(b_url)
    return {"success": True, "models": models, "total": len(models)}


@router.post("/api/settings/ai/test")
def api_test_single_ai_provider(req: SingleProviderTestRequest):
    """특정 AI Provider 개별 연결 핑 테스트"""
    p = req.provider.strip().lower()
    k = req.api_key.strip() if req.api_key else ""
    m = req.model.strip() if req.model else ""
    b_url = req.base_url.strip() if req.base_url else ""

    if p == "lmstudio":
        if b_url:
            grammar_analyzer.set_lmstudio_base_url(b_url)
        if not k:
            existing_k, _ = grammar_analyzer.get_provider_config(p)
            k = existing_k or "lm-studio"
    else:
        if not k:
            existing_k, existing_m = grammar_analyzer.get_provider_config(p)
            k = existing_k
            if not m:
                m = existing_m

        if not k:
            prov_label = grammar_analyzer.PROVIDER_NAMES.get(p, p)
            return JSONResponse(status_code=400, content={"success": False, "message": f"{prov_label} API Key를 입력해 주세요."})

        # HTTP 헤더(x-api-key 등)는 latin-1 만 허용되므로 ASCII 외 문자가 섞인 키는 전송 전에 차단
        bad = describe_non_ascii(k)
        if bad:
            return JSONResponse(status_code=400, content={"success": False, "message": f"API Key에 허용되지 않는 문자가 있습니다 ({bad}). 콘솔에서 전체 키를 다시 복사해 붙여 주세요 (말줄임표 '…'나 공백이 섞인 잘린 키인지 확인)."})

    if p == "gemini":
        m = grammar_analyzer.resolve_gemini_model(k, m)

    ok, msg, used_model = grammar_analyzer.test_connection(p, k, m, base_url=b_url)
    if not ok:
        return JSONResponse(status_code=400, content={"success": False, "message": msg})
    return {"success": True, "provider": p, "model": used_model, "message": msg}


@router.post("/api/settings/ai")
def api_save_ai_settings(req: AISettingsRequest):
    """AI 설정 일괄/단일 저장 및 연결 테스트"""
    # 1. 활성 Provider 목록 및 합의 판정 방식 저장 (복수 선택 지원)
    if req.active_providers is not None:
        valid_actives = [p for p in req.active_providers if p in grammar_analyzer.SUPPORTED_PROVIDERS]
        if not valid_actives:
            valid_actives = ["gemini"]
        db.set_setting("ai_active_providers", json.dumps(valid_actives))
        db.set_setting("ai_provider", valid_actives[0])

    if req.consensus_mode is not None:
        grammar_analyzer.set_consensus_mode(req.consensus_mode)

    # 2. 프로바이더별 개별 키 및 모델 설정 저장
    if req.providers:
        for p, p_data in req.providers.items():
            p_clean = p.lower()
            if p_clean in grammar_analyzer.SUPPORTED_PROVIDERS:
                k = (p_data.get("api_key") or "").strip()
                m = (p_data.get("model") or "").strip()
                if p_clean == "lmstudio":
                    b_url = (p_data.get("base_url") or "").strip()
                    if b_url:
                        grammar_analyzer.set_lmstudio_base_url(b_url)
                if k:
                    bad = describe_non_ascii(k)
                    if bad:
                        prov_label = grammar_analyzer.PROVIDER_NAMES.get(p_clean, p_clean)
                        return JSONResponse(status_code=400, content={"success": False, "message": f"{prov_label} API Key에 허용되지 않는 문자가 있습니다 ({bad}). 저장하지 않았습니다. 콘솔에서 전체 키를 다시 복사해 주세요."})
                    db.set_setting(f"ai_key_{p_clean}", k)
                if m:
                    db.set_setting(f"ai_model_{p_clean}", m)

    # 3. 레거시 단일 필드 호환 처리
    if req.provider:
        p = req.provider.strip().lower()
        k = (req.api_key or "").strip()
        m = (req.model or "").strip()
        db.set_setting("ai_provider", p)
        if k:
            db.set_setting(f"ai_key_{p}", k)
            db.set_setting("ai_api_key", k)
        if m:
            db.set_setting(f"ai_model_{p}", m)
            db.set_setting("ai_model", m)

    # 4. OpenRouter 3개 모델 앙상블(교차 검토) 모드 설정 저장
    if req.openrouter_ensemble is not None:
        grammar_analyzer.set_openrouter_ensemble(req.openrouter_ensemble)
    if req.openrouter_ensemble_models is not None:
        grammar_analyzer.set_openrouter_ensemble_models(req.openrouter_ensemble_models)

    # 5. TTS 엔진 및 세부 설정 저장 (Edge-TTS 및 ElevenLabs)
    if req.tts_engine is not None:
        db.set_setting("tts_engine", req.tts_engine.strip())
    if req.edge_tts_voice_male is not None:
        db.set_setting("edge_tts_voice_male", req.edge_tts_voice_male.strip())
    if req.edge_tts_voice_female is not None:
        db.set_setting("edge_tts_voice_female", req.edge_tts_voice_female.strip())
    if req.edge_tts_rate is not None:
        db.set_setting("edge_tts_rate", req.edge_tts_rate.strip())

    # 6. test_now인 경우 첫 번째 활성 프로바이더 연결 테스트
    test_msg = ""
    if req.test_now:
        active = grammar_analyzer.get_active_providers()
        target_p = active[0] if active else "gemini"
        tk, tm = grammar_analyzer.get_provider_config(target_p)
        if tk:
            ok, test_msg, _ = grammar_analyzer.test_connection(target_p, tk, tm)
            if not ok:
                return JSONResponse(status_code=400, content={"success": False, "message": test_msg})

    return {
        "success": True,
        "message": test_msg or "AI 및 TTS 설정이 성공적으로 저장되었습니다."
    }


@router.post("/api/settings/tts-engine")
def api_set_tts_engine(req: TTSEngineRequest):
    """지문 헤더 툴바 등에서 빠른 TTS 엔진(xtts 또는 edge-tts) 전환"""
    engine = (req.engine or "").strip().lower()
    if engine not in ("xtts", "edge-tts"):
        return JSONResponse(
            status_code=400,
            content={"success": False, "message": "지원하지 않는 TTS 엔진입니다. (xtts 또는 edge-tts)"}
        )
    db.set_setting("tts_engine", engine)
    return {"success": True, "engine": engine}


@router.get("/api/settings/tts/hardware")
def api_get_tts_hardware():
    """현재 머신의 GPU(CUDA) 및 XTTS 설치 하드웨어 상태 반환"""
    return tts_service.get_hardware_status()


@router.post("/api/settings/tts/preview")
async def api_preview_tts(req: Dict[str, Any] = Body(...)):
    """XTTS-v2 수능 성우 복제 및 Edge-TTS 목소리 샘플 미리듣기 생성"""
    try:
        engine = (req.get("engine") or "xtts").strip()
        gender = (req.get("gender") or "male").strip()
        rate = (req.get("rate") or "+0%").strip()
        preview_url = await tts_service.generate_tts_preview(engine=engine, gender=gender, rate=rate)
        return {"success": True, "audio_url": preview_url}
    except Exception as e:
        logger.error(f"TTS 미리듣기 실패: {e}")
        return JSONResponse(status_code=400, content={"success": False, "message": str(e)})


@router.post("/api/settings/edge-tts/preview")
async def api_preview_edge_tts(req: Dict[str, Any] = Body(...)):
    """Edge-TTS 목소리 샘플 미리듣기 생성 (호환용)"""
    try:
        voice = (req.get("voice") or "en-US-GuyNeural").strip()
        rate = (req.get("rate") or "+0%").strip()
        gender = "female" if "Jenny" in voice or "female" in voice.lower() else "male"
        preview_url = await tts_service.generate_tts_preview(engine="edge-tts", gender=gender, rate=rate)
        return {"success": True, "audio_url": preview_url}
    except Exception as e:
        logger.error(f"Edge-TTS 미리듣기 실패: {e}")
        return JSONResponse(status_code=400, content={"success": False, "message": str(e)})
