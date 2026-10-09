"""
05-gichul_db: 멀티 LLM(Gemini, OpenRouter, ChatGPT, Claude) 문장 어법 범주 분석기 모듈
- grammar_categories.json 기준 243개 어법 체계 매칭
- Google Gemini, OpenRouter, OpenAI ChatGPT, Anthropic Claude REST API 직접 연동 (SDK 불필요)
- 단일 문장 실시간 분석 및 다중 문장 배치 분석 지원
"""

import os
import json
import re
import urllib.request
import urllib.error
from typing import Dict, List, Any, Optional, Tuple

from . import database
from . import paths
from .logging_config import get_logger

logger = get_logger("gichul.grammar_analyzer")

# 범주표 로드 및 캐싱
DATA_PATH = paths.GRAMMAR_CATEGORIES_JSON

_CATEGORIES_DATA: Optional[Dict[str, Any]] = None
_CATEGORY_ID_MAP: Dict[int, Dict[str, Any]] = {}
_CATEGORIES_SUMMARY_PROMPT: str = ""


def load_categories():
    """grammar_categories.json 로드 및 캐시 생성"""
    global _CATEGORIES_DATA, _CATEGORY_ID_MAP, _CATEGORIES_SUMMARY_PROMPT
    if _CATEGORIES_DATA is not None:
        return

    if not os.path.exists(DATA_PATH):
        return

    with open(DATA_PATH, "r", encoding="utf-8") as f:
        _CATEGORIES_DATA = json.load(f)

    for item in _CATEGORIES_DATA.get("list", []):
        cid = item.get("id")
        _CATEGORY_ID_MAP[cid] = item

    # 프롬프트 주입용 요약 텍스트 (ID: 전체경로)
    lines = []
    for item in _CATEGORIES_DATA.get("list", []):
        lines.append(f"[{item['id']}] {item['full_path']}")
    _CATEGORIES_SUMMARY_PROMPT = "\n".join(lines)


# 모듈 로드 시 카테고리 적재
load_categories()


SYSTEM_PROMPT = """당신은 대한민국 대학수학능력시험 및 전국연합학력평가 영어과 최고의 어법·문법 전문가입니다.
주어진 영어 문장을 정밀 분석하여, 아래 [어법 범주 기준표(ID: 1~243)]에 명시된 출제 기준에 해당하는 어법 요소들을 모두 찾아내어 JSON으로 추출하십시오.

[분석 규칙]
1. 반드시 아래 [어법 범주 기준표]에 명시된 category_id(1~243)와 정확한 full_path 중에서만 매칭하십시오. 임의의 어법명을 지어내지 마십시오.
2. 하나의 문장에 2개 이상의 어법 포인트가 포함된 경우(예: 가정법 도치 + 관계대명사), 해당하는 모든 어법을 배열에 포함하십시오.
3. 고교 수능·모의고사 어법 출제 포인트(도치, 가정법, 분사구문, 수일치, 관계사, 5형식, 수동태 등)가 없는 지극히 평이한 단순 서술문이거나 해당 기준에 명확히 부합하지 않는 경우, 억지로 매칭하지 말고 빈 배열 `[]`을 반환하십시오.
4. 각 어법 포인트마다:
   - category_id: 기준표의 번호 (정수)
   - target_expression: 해당 문장 내에서 어법이 적용된 정확한 영어 단어/어구
   - explanation: 해당 어법에 대한 명쾌하고 친절한 1~2문장의 한국어 어법 해설

5. [선지 번호 및 밑줄 처리 규칙]
   - 문장 내 선지 번호(1~5, ①~⑤, (1)~(5), (a)~(e) 등)는 어법 분석 대상에서 완전히 제외하고 순수 문장 성분만 분석하십시오.
   - 밑줄/빈칸에 정답 어구가 채워진 문장은 채워진 어구를 포함한 완성된 문장의 전체 통사 구조 및 문법 요소를 기준으로 분석하십시오.

반드시 다음 JSON 형식으로만 응답하십시오:
{
  "annotations": [
    {
      "category_id": 200,
      "target_expression": "문장 내 어구",
      "explanation": "한국어 해설"
    }
  ]
}
"""


SUPPORTED_PROVIDERS = ["gemini", "openai", "claude", "openrouter", "lmstudio"]

PROVIDER_NAMES = {
    "gemini": "Google Gemini",
    "openai": "OpenAI ChatGPT",
    "claude": "Anthropic Claude",
    "openrouter": "OpenRouter",
    "lmstudio": "LM Studio (Local LLM)"
}

PROVIDER_DEFAULT_MODELS = {
    "gemini": "gemini-3.6-flash",
    "openai": "gpt-4o-mini",
    "claude": "claude-haiku-4-5",
    "openrouter": "deepseek/deepseek-chat",
    "lmstudio": "qwen2.5-14b-instruct"
}

PROVIDER_ENV_VARS = {
    "gemini": "GEMINI_API_KEY",
    "openai": "OPENAI_API_KEY",
    "claude": "ANTHROPIC_API_KEY",
    "openrouter": "OPENROUTER_API_KEY",
    "lmstudio": "LMSTUDIO_API_KEY"
}

RETIRED_GEMINI_MODELS = {
    "gemini-1.5-flash", "gemini-1.5-flash-latest", "gemini-1.5-pro",
    "gemini-2.0-flash", "gemini-2.0-flash-exp", "gemini-2.5-flash"
}

# OpenRouter 3개 모델 앙상블 기본 설정
DEFAULT_OPENROUTER_ENSEMBLE_MODELS: List[str] = [
    "deepseek/deepseek-chat",
    "openai/gpt-4o-mini",
    "anthropic/claude-sonnet-4.5"
]

OPENROUTER_MODEL_SHORT_NAMES: Dict[str, str] = {
    "deepseek/deepseek-chat": "DeepSeek V3",
    "openai/gpt-4o-mini": "GPT-4o-mini",
    "anthropic/claude-sonnet-4.5": "Claude Sonnet 4.5",
    "openai/gpt-4o": "GPT-4o",
    "meta-llama/llama-3.3-70b-instruct": "Llama 3.3 70B",
    "google/gemini-2.5-flash": "Gemini 2.5 Flash",
    "anthropic/claude-3-5-haiku-20241022": "Claude 3.5 Haiku",
}


def get_model_short_name(model_id: str) -> str:
    """OpenRouter 모델 ID의 가독성 높은 짧은 이름 반환"""
    if model_id in OPENROUTER_MODEL_SHORT_NAMES:
        return OPENROUTER_MODEL_SHORT_NAMES[model_id]
    if "/" in model_id:
        return model_id.split("/")[-1]
    return model_id


def is_openrouter_ensemble_enabled() -> bool:
    """OpenRouter 3개 모델 앙상블(교차 검토) 모드 활성화 여부"""
    return database.get_setting("openrouter_ensemble", "0") == "1"


def set_openrouter_ensemble(enabled: bool):
    """OpenRouter 3개 모델 앙상블(교차 검토) 모드 설정 저장"""
    database.set_setting("openrouter_ensemble", "1" if enabled else "0")


def get_openrouter_ensemble_models() -> List[str]:
    """OpenRouter 앙상블에 사용될 3개 모델 ID 목록 반환"""
    raw = database.get_setting("openrouter_ensemble_models", "")
    if raw:
        try:
            arr = json.loads(raw)
            if isinstance(arr, list) and len(arr) == 3:
                return arr
        except Exception:
            logger.debug("Failed to parse openrouter_ensemble_models json", exc_info=True)
    return list(DEFAULT_OPENROUTER_ENSEMBLE_MODELS)


def set_openrouter_ensemble_models(models: List[str]):
    """OpenRouter 앙상블 모델 목록 저장"""
    if isinstance(models, list) and len(models) >= 2:
        database.set_setting("openrouter_ensemble_models", json.dumps(models[:3]))



def get_available_gemini_models(api_key: str) -> List[str]:
    """API Key로 generateContent가 가능한 실제 Gemini 모델 목록 실시간 조회"""
    if not api_key:
        return []
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) GichulDB/1.0"}
        )
        with urllib.request.urlopen(req, timeout=6) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            supported = []
            for m in data.get("models", []):
                methods = m.get("supportedGenerationMethods", [])
                if "generateContent" in methods:
                    name = m.get("name", "")
                    clean_name = name[len("models/"):] if name.startswith("models/") else name
                    if clean_name not in RETIRED_GEMINI_MODELS:
                        supported.append(clean_name)
            return supported
    except Exception as e:
        logger.warning("[Gemini ListModels Warning] %s", e)
        return []


def resolve_gemini_model(api_key: str, requested_model: str = "") -> str:
    """Gemini 사용 가능한 최신 모델 자동 탐색 및 반환 (종료된 1.5-flash/2.5-flash 자동 마이그레이션)"""
    req_m = (requested_model or "").strip()
    if req_m.startswith("models/"):
        req_m = req_m[len("models/"):]

    # 사용자가 명시한 모델이 있고 서비스 종료 모델군에 속하지 않으면 그대로 사용
    if req_m and req_m not in RETIRED_GEMINI_MODELS:
        return req_m

    # Google API의 ListModels를 호출하여 현재 API Key로 지원되는 모델 실시간 목록 확인
    if api_key:
        supported = get_available_gemini_models(api_key)
        if supported:
            # 최신 플래시 모델 우선 순위 선별
            for pref in ["gemini-3.6-flash", "gemini-2.5-flash-lite", "gemini-3.7-flash", "gemini-3.5-flash", "gemini-3-flash"]:
                if pref in supported:
                    return pref
            flash_models = [m for m in supported if "flash" in m.lower() and m not in RETIRED_GEMINI_MODELS]
            if flash_models:
                return flash_models[0]
            return supported[0]

    return "gemini-3.6-flash"


def is_valid_api_key_format(provider: str, key: str) -> bool:
    """API 키가 더미 문자열이 아닌 실제 유효한 형식인지 검증 (LM Studio는 로컬 특성상 키 선택사항)"""
    p = provider.lower()
    if p == "lmstudio":
        return True
    if not key or not isinstance(key, str):
        return False
    k = key.strip()
    if "test-key" in k.lower() or k.endswith("...") or len(k) < 15:
        return False
    if p == "openrouter":
        return k.startswith("sk-or-") and len(k) >= 30
    elif p == "openai":
        return k.startswith("sk-") and len(k) >= 25
    elif p == "claude":
        return k.startswith("sk-ant-") and len(k) >= 25
    elif p == "gemini":
        return len(k) >= 20
    return len(k) >= 15


def get_provider_config(provider: str) -> Tuple[str, str]:
    """특정 Provider의 (api_key, model) 조회 (DB 설정 -> 유효성 검증 레거시 폴백 -> 환경변수 -> 기본값 폴백)"""
    p = provider.lower()
    # 1. 개별 키 설정 조회
    api_key = database.get_setting(f"ai_key_{p}", "").strip()
    model = database.get_setting(f"ai_model_{p}", "").strip()

    # 2. 개별 키가 유효하지 않은 경우 레거시 단일 설정(ai_api_key) 자동 폴백 및 복구
    if not is_valid_api_key_format(p, api_key):
        legacy_key = database.get_setting("ai_api_key", "").strip()
        if is_valid_api_key_format(p, legacy_key):
            api_key = legacy_key
            try:
                database.set_setting(f"ai_key_{p}", legacy_key)
            except Exception:
                logger.debug("Failed to set legacy api key into ai_key_%s", p, exc_info=True)

    if not model:
        legacy_p = database.get_setting("ai_provider", "gemini").lower()
        if legacy_p == p:
            model = database.get_setting("ai_model", "").strip()

    # 3. 환경변수 폴백
    if not api_key:
        env_var = PROVIDER_ENV_VARS.get(p)
        if env_var:
            api_key = os.getenv(env_var, "").strip()

    # 4. 기본 모델 폴백
    if not model:
        model = PROVIDER_DEFAULT_MODELS.get(p, "gemini-3.6-flash")
    elif p == "gemini" and model in RETIRED_GEMINI_MODELS:
        model = "gemini-3.6-flash"

    return api_key, model


def get_active_providers() -> List[str]:
    """현재 활성화된(체크된) AI Provider 목록 반환"""
    raw = database.get_setting("ai_active_providers", "")
    if raw:
        try:
            arr = json.loads(raw)
            if isinstance(arr, list) and len(arr) > 0:
                # 지원하는 provider만 필터링
                valid = [str(x).lower() for x in arr if str(x).lower() in SUPPORTED_PROVIDERS]
                if valid:
                    return valid
        except Exception:
            logger.debug("Failed to parse ai_active_providers json", exc_info=True)

    # 레거시 폴백: ai_provider에 설정된 단일 값
    legacy_p = database.get_setting("ai_provider", "gemini").lower()
    if legacy_p in SUPPORTED_PROVIDERS:
        return [legacy_p]
    return ["gemini"]


def get_consensus_mode() -> str:
    """합의 판정 방식 조회 (majority, at_least_2, strict) - 기본값: majority (다수결 합의)"""
    return database.get_setting("ai_consensus_mode", "majority")


def set_consensus_mode(mode: str):
    """합의 판정 방식 저장"""
    clean_mode = (mode or "").strip().lower()
    if clean_mode not in ["majority", "at_least_2", "strict"]:
        clean_mode = "majority"
    database.set_setting("ai_consensus_mode", clean_mode)


def get_lmstudio_base_url() -> str:
    """LM Studio 로컬 서버 Base URL 조회 (기본값: http://localhost:1234/v1)"""
    url = database.get_setting("ai_base_url_lmstudio", "").strip()
    return url if url else "http://localhost:1234/v1"


def set_lmstudio_base_url(url: str):
    """LM Studio 로컬 서버 Base URL 저장"""
    clean_url = (url or "http://localhost:1234/v1").strip().rstrip("/")
    if not clean_url.endswith("/v1"):
        clean_url = f"{clean_url}/v1"
    database.set_setting("ai_base_url_lmstudio", clean_url)


def get_available_lmstudio_models(base_url: str = "") -> List[str]:
    """LM Studio 로컬 서버(/v1/models)에서 사용 가능한 로컬 모델 ID 목록 조회"""
    b_url = (base_url or get_lmstudio_base_url()).rstrip("/")
    url = f"{b_url}/models"
    try:
        req = urllib.request.Request(
            url,
            headers={"Content-Type": "application/json"},
            method="GET"
        )
        with urllib.request.urlopen(req, timeout=1.0) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            models = []
            for item in data.get("data", []):
                m_id = item.get("id")
                if m_id:
                    models.append(m_id)
            return models
    except Exception as e:
        logger.warning("[LM Studio ListModels Error] %s", e)
        return []


def get_all_ai_configs() -> Dict[str, Any]:
    """모든 지원 모델의 설정 현황 및 활성화 목록 종합 조회"""
    active_providers = get_active_providers()
    providers_info = {}

    for p in SUPPORTED_PROVIDERS:
        api_key, model = get_provider_config(p)
        masked_key = ""
        if api_key:
            if len(api_key) > 8:
                masked_key = api_key[:4] + "•" * (len(api_key) - 8) + api_key[-4:]
            else:
                masked_key = "••••••••"
        elif p == "lmstudio":
            masked_key = "로컬 인증 (키 불필요)"

        p_info = {
            "name": PROVIDER_NAMES.get(p, p),
            "is_active": p in active_providers,
            "has_key": bool(api_key) or (p == "lmstudio"),
            "masked_key": masked_key,
            "model": model,
            "default_model": PROVIDER_DEFAULT_MODELS.get(p, "")
        }
        if p == "lmstudio":
            p_info["base_url"] = get_lmstudio_base_url()
        providers_info[p] = p_info

    is_or_ensemble = is_openrouter_ensemble_enabled()
    is_ensemble = (len(active_providers) > 1) or ("openrouter" in active_providers and is_or_ensemble)

    return {
        "active_providers": active_providers,
        "mode": "ensemble" if is_ensemble else "single",
        "consensus_mode": get_consensus_mode(),
        "providers": providers_info,
        "openrouter_ensemble": is_or_ensemble,
        "openrouter_ensemble_models": get_openrouter_ensemble_models(),
        "lmstudio_base_url": get_lmstudio_base_url()
    }


def get_active_ai_configs() -> List[Dict[str, Any]]:
    """현재 활성화되어 실제 분석에 사용될 Provider/Model 설정 목록 반환"""
    active_names = get_active_providers()
    configs = []
    for p in active_names:
        key, model = get_provider_config(p)
        if p == "openrouter" and is_openrouter_ensemble_enabled():
            ensemble_models = get_openrouter_ensemble_models()
            for em in ensemble_models:
                s_name = get_model_short_name(em)
                configs.append({
                    "provider": "openrouter",
                    "name": f"OpenRouter ({s_name})",
                    "label": f"OpenRouter: {s_name}",
                    "short_label": s_name,
                    "api_key": key,
                    "model": em,
                    "is_openrouter_ensemble": True
                })
        else:
            configs.append({
                "provider": p,
                "name": PROVIDER_NAMES.get(p, p),
                "label": PROVIDER_NAMES.get(p, p),
                "short_label": PROVIDER_NAMES.get(p, p),
                "api_key": key,
                "model": model,
                "is_openrouter_ensemble": False
            })
    return configs


def get_ai_config() -> Tuple[str, str, str]:
    """(하위 호환용) 첫 번째 활성 AI 설정 (provider, api_key, model) 반환"""
    active = get_active_providers()
    primary = active[0] if active else "gemini"
    api_key, model = get_provider_config(primary)
    return primary, api_key, model


def _call_gemini_with_resilience(user_content: str, api_key: str, requested_model: str = "") -> Tuple[str, str]:
    """
    Google Gemini API 고가용성 복원력 호출
    - 503 (High Demand / Spikes in demand) 발생 시 1.5초 지수 백오프 1회 재시도
    - 503 재시도 실패, 429(Rate Limit), 404(Model Deprecated) 발생 시 사용 가능한 대체 모델로 자동 페일오버
    - 성공 시 (raw_json_str, used_model) 반환 및 필요 시 DB 활성 모델 자동 갱신
    """
    import time

    req_m = (requested_model or "").strip()
    if req_m.startswith("models/"):
        req_m = req_m[len("models/"):]
    if req_m in RETIRED_GEMINI_MODELS:
        req_m = "gemini-3.6-flash"

    # 실시간 지원 모델 목록 탐색
    supported_models = get_available_gemini_models(api_key)

    # 후보 모델 우선순위 큐 구성 (중복 배제 및 종료 모델 필터링)
    candidates = []

    # 1. 사용자가 명시한 모델 우선
    if req_m and req_m not in RETIRED_GEMINI_MODELS:
        candidates.append(req_m)

    # 2. 우선 권장 모델 순서 (3.6-flash가 503이면 가벼운 2.5-flash-lite, 3.7-flash, 3.5-flash 순으로 전환)
    preferred_order = [
        "gemini-3.6-flash",
        "gemini-2.5-flash-lite",
        "gemini-3.7-flash",
        "gemini-3.5-flash",
        "gemini-3-flash",
        "gemini-2.5-pro"
    ]

    for p in preferred_order:
        if (not supported_models or p in supported_models) and p not in candidates and p not in RETIRED_GEMINI_MODELS:
            candidates.append(p)

    # 3. ListModels에서 조회된 나머지 지원 모델들 추가
    for sm in supported_models:
        if sm not in candidates and sm not in RETIRED_GEMINI_MODELS:
            candidates.append(sm)

    if not candidates:
        candidates = ["gemini-3.6-flash", "gemini-2.5-flash-lite", "gemini-3.7-flash"]

    payload = {
        "contents": [
            {
                "parts": [
                    {"text": SYSTEM_PROMPT + "\n\n" + user_content}
                ]
            }
        ],
        "generationConfig": {
            "response_mime_type": "application/json",
            "temperature": 0.1
        }
    }
    post_data = json.dumps(payload).encode("utf-8")

    last_error_code = None
    last_error_detail = ""

    for cand_idx, cand_model in enumerate(candidates):
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{cand_model}:generateContent?key={api_key}"

        # 각 모델당 503 발생 시 최대 2회 시도 (1회 실패 후 1.5초 대기 후 1회 재시도)
        max_attempts = 2
        for attempt in range(1, max_attempts + 1):
            req = urllib.request.Request(
                url,
                data=post_data,
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            try:
                with urllib.request.urlopen(req, timeout=30) as resp:
                    resp_data = json.loads(resp.read().decode("utf-8"))
                    raw_text = resp_data["candidates"][0]["content"]["parts"][0]["text"]

                    # 만약 요청 모델과 다른 모델로 폴백 성공했다면 DB 설정 및 로깅
                    if cand_model != req_m:
                        logger.info("[Gemini Auto-Failover] Switched from %s to responsive %s successfully.", req_m, cand_model)
                        database.set_setting("ai_model_gemini", cand_model)

                    return raw_text, cand_model

            except urllib.error.HTTPError as he:
                last_error_code = he.code
                err_body = he.read().decode("utf-8", errors="ignore")
                try:
                    err_json = json.loads(err_body)
                    err_detail = err_json.get("error", {}).get("message") or err_json.get("message") or err_body
                except Exception:
                    logger.debug("Failed to parse Gemini error json", exc_info=True)
                    err_detail = err_body
                last_error_detail = err_detail

                # 인증 오류(400, 401, 403)는 키 자체의 문제이므로 다른 모델을 시도할 필요 없이 즉시 중단
                if he.code in (400, 401, 403):
                    raise ValueError(f"GEMINI API 인증/요청 오류 ({he.code}): {err_detail}")

                # 503 (High demand / Unavailable): 일시적 트래픽 스파이크
                if he.code == 503:
                    if attempt < max_attempts:
                        logger.warning("[Gemini 503 Spikes] %s demand spike on attempt %d. Retrying in 1.5s...", cand_model, attempt)
                        time.sleep(1.5)
                        continue
                    else:
                        logger.warning("[Gemini 503 Failover] %s still 503 after %d attempts. Trying next model...", cand_model, max_attempts)
                        break

                # 404 (Not Found / Model deprecated) or 429 (Rate limit): 다음 후보 모델로 즉시 전환
                if he.code in (404, 429):
                    logger.warning("[Gemini %d Fallback] %s failed with HTTP %d. Trying next model...", he.code, cand_model, he.code)
                    break

                # 기타 HTTP 오류: 다음 모델로 전환
                break

            except Exception as e:
                last_error_detail = str(e)
                break

    # 모든 후보 모델 호출이 실패한 경우
    if last_error_code == 503:
        raise ValueError(
            "Google Gemini 서버 트래픽 일시 폭주 (503): Google 측 일시적 수요 급증으로 모델 호출이 지연되고 있습니다. "
            "잠시 후(1~2분 뒤) 다시 테스트하시거나, 안정적인 OpenRouter, ChatGPT, Claude 등 다른 AI 모델을 선택하여 사용해 주십시오."
        )
    elif last_error_code == 429:
        raise ValueError(
            "Google Gemini 호출 한도 초과 (429): API 요청량 한도(Rate Limit/Quota)에 도달했습니다. "
            "잠시 후 다시 시도해 주시거나 다른 AI Provider를 선택해 주십시오."
        )
    elif last_error_code == 404:
        raise ValueError(
            f"Google Gemini 모델 사용 불가 (404): {last_error_detail} "
            "(Google AI Studio에서 활성화된 모델명을 확인해 주세요.)"
        )
    else:
        raise ValueError(f"GEMINI API 호출 오류 ({last_error_code or 'Unknown'}): {last_error_detail}")


def test_connection(provider: str, api_key: str, model: str = "", base_url: str = "") -> Tuple[bool, str, str]:
    """선택된 Provider 및 API Key로 연결 핑 테스트 수행 (성공여부, 메시지, 사용된 모델)"""
    load_categories()
    provider = provider.lower()
    test_sentence = "Not only did he arrive late, but he also forgot his homework."

    try:
        resolved_model = model
        if provider == "gemini":
            resolved_model = resolve_gemini_model(api_key, model)
        elif provider == "lmstudio":
            if not api_key:
                api_key = "lm-studio"
            if base_url:
                set_lmstudio_base_url(base_url)
        results, used_model = _call_llm(test_sentence, provider, api_key, resolved_model, return_model=True)
        prov_name = PROVIDER_NAMES.get(provider, provider.upper())
        msg = f"연결 성공! {prov_name} ({used_model}) 연결이 정상 확인되었습니다."
        if provider == "gemini" and model and used_model != model:
            msg += f" (참고: 요청 모델 {model}의 일시적 Google 트래픽 과부하(503)로 인해 안정적인 {used_model} 모델로 자동 전환되었습니다.)"
        return True, msg, used_model
    except Exception as e:
        err_msg = str(e)
        if provider == "lmstudio" and ("Connection refused" in err_msg or "WinError 10061" in err_msg or "URLError" in str(type(e))):
            target_url = base_url or get_lmstudio_base_url()
            err_msg = f"LM Studio 서버({target_url})에 연결할 수 없습니다. LM Studio의 'Local Server' 탭에서 [Start Server]를 켜두셨는지 확인해 주세요."
        return False, f"연결 실패: {err_msg}", model


# 순수 텍스트 함수는 text_utils 로 이동 (기존 import 경로 하위 호환을 위해 다시 내보냄)
from .text_utils import (  # noqa: E402,F401
    extract_answer_num,
    extract_choices,
    clean_choice_markers,
    fill_blanks,
)


def prepare_sentence_for_analysis(
    sentence_text: str,
    passage_id: Optional[str] = None,
    passage_text: str = "",
    answer_text: str = "",
    explanation_text: str = ""
) -> str:
    """
    문장 분석(어법/문법 분석)을 위한 전처리.
    지문 정보(passage_text / answer_text)가 부족하면 DB에서 보강한 뒤 text_utils.fill_blanks 를 호출한다.
    (실제 정제·빈칸 채우기 규칙은 text_utils.fill_blanks 참고)
    """
    if not sentence_text:
        return ""

    # passage_id가 없거나 passage 정보가 부족한 경우 자동 DB 보강
    if not passage_text or not answer_text:
        if not passage_id:
            try:
                with database.get_connection() as conn:
                    cur = conn.cursor()
                    cur.execute("SELECT passage_id FROM sentences WHERE sentence_text = ? LIMIT 1", (sentence_text,))
                    row = cur.fetchone()
                    if row:
                        passage_id = row["passage_id"]
            except Exception:
                logger.debug("Failed to query passage_id for sentence", exc_info=True)

        if passage_id:
            try:
                p_data = database.get_passage(passage_id)
                if p_data:
                    passage_text = passage_text or p_data.get("passage_text", "")
                    answer_text = answer_text or p_data.get("answer_text", "")
                    explanation_text = explanation_text or p_data.get("explanation_text", "")
            except Exception:
                logger.debug("Failed to fetch passage for passage_id %s", passage_id, exc_info=True)

    return fill_blanks(sentence_text, passage_text, answer_text, explanation_text)


def _call_llm(
    sentence: str,
    provider: str,
    api_key: str,
    model: str = "",
    return_model: bool = False
) -> Any:
    """Provider별 REST API 호출 및 JSON 응답 파싱"""
    load_categories()
    provider = provider.lower()
    if not api_key:
        if provider == "lmstudio":
            api_key = "lm-studio"
        else:
            raise ValueError(f"{provider.upper()} API Key가 설정되지 않았습니다.")

    user_content = f"""[분석할 영어 문장]
"{sentence}"

[어법 범주 기준표 (일부/전체)]
{_CATEGORIES_SUMMARY_PROMPT}

위 문장을 분석하여 지정된 JSON 형식으로 응답하십시오."""

    raw_json_str = ""
    used_model = model or PROVIDER_DEFAULT_MODELS.get(provider, "기본 모델")

    try:
        if provider == "gemini":
            raw_json_str, used_model = _call_gemini_with_resilience(user_content, api_key, model)

        elif provider == "openrouter":
            target_model = model or "openai/gpt-4o-mini"
            used_model = target_model
            url = "https://openrouter.ai/api/v1/chat/completions"
            payload = {
                "model": target_model,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_content}
                ],
                "response_format": {"type": "json_object"},
                "temperature": 0.1
            }
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {api_key}",
                    "HTTP-Referer": "http://localhost:8000",
                    "X-Title": "Gichul DB Grammar Analyzer"
                },
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=35) as resp:
                resp_data = json.loads(resp.read().decode("utf-8"))
                raw_json_str = resp_data["choices"][0]["message"]["content"]

        elif provider == "openai":
            target_model = model or "gpt-4o-mini"
            used_model = target_model
            url = "https://api.openai.com/v1/chat/completions"
            payload = {
                "model": target_model,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_content}
                ],
                "response_format": {"type": "json_object"},
                "temperature": 0.1
            }
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {api_key}"
                },
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                resp_data = json.loads(resp.read().decode("utf-8"))
                raw_json_str = resp_data["choices"][0]["message"]["content"]

        elif provider == "claude":
            target_model = model or "claude-haiku-4-5"
            used_model = target_model
            url = "https://api.anthropic.com/v1/messages"
            payload = {
                "model": target_model,
                "max_tokens": 4096,  # thinking 토큰이 포함되므로 여유 확보
                "system": SYSTEM_PROMPT,
                "messages": [
                    {"role": "user", "content": user_content + "\n반드시 JSON 블록만 단독 출력하십시오."}
                ]
                # 현행 Claude 모델(Opus 5/Sonnet 5 등)은 temperature 파라미터를 거부(400)하므로 보내지 않음
            }
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={
                    "Content-Type": "application/json",
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01"
                },
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                resp_data = json.loads(resp.read().decode("utf-8"))
                # 현행 모델은 content 앞에 thinking 블록이 올 수 있으므로 text 블록만 모아서 사용
                raw_json_str = "".join(b.get("text", "") for b in resp_data.get("content", []) if b.get("type") == "text")

        elif provider == "lmstudio":
            target_model = model or PROVIDER_DEFAULT_MODELS.get("lmstudio", "qwen2.5-14b-instruct")
            used_model = target_model
            base_url = get_lmstudio_base_url().rstrip("/")
            url = f"{base_url}/chat/completions"
            payload = {
                "model": target_model,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_content}
                ],
                "response_format": {"type": "json_object"},
                "temperature": 0.1
            }
            auth_header = f"Bearer {api_key}" if api_key else "Bearer lm-studio"
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={
                    "Content-Type": "application/json",
                    "Authorization": auth_header
                },
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=120) as resp:
                resp_data = json.loads(resp.read().decode("utf-8"))
                raw_json_str = resp_data["choices"][0]["message"]["content"]

        else:
            raise ValueError(f"지원하지 않는 AI Provider: {provider}")

    except urllib.error.HTTPError as he:
        err_body = he.read().decode("utf-8", errors="ignore")
        err_detail = ""
        try:
            err_json = json.loads(err_body)
            err_detail = err_json.get("error", {}).get("message") or err_json.get("message") or err_body
        except Exception:
            logger.debug("Failed to parse HTTP error body as JSON", exc_info=True)
            err_detail = err_body
        raise ValueError(f"{provider.upper()} API 호출 오류 ({he.code}): {err_detail}")

    # JSON 파싱 및 표준화 (마크다운 코드블록 ```json ... ``` 자동 제거 지원)
    cleaned_str = raw_json_str.strip()
    if cleaned_str.startswith("```"):
        lines = cleaned_str.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        cleaned_str = "\n".join(lines).strip()

    try:
        parsed = json.loads(cleaned_str)
    except Exception:
        logger.debug("Initial JSON parse failed, trying substring extraction", exc_info=True)
        start_brace = cleaned_str.find("{")
        end_brace = cleaned_str.rfind("}")
        if start_brace != -1 and end_brace != -1 and end_brace > start_brace:
            parsed = json.loads(cleaned_str[start_brace:end_brace+1])
        else:
            raise ValueError(f"AI 응답에서 유효한 JSON을 파싱할 수 없습니다: {raw_json_str[:200]}")

    raw_annos = parsed.get("annotations", [])
    if isinstance(parsed, list):
        raw_annos = parsed

    enriched_annos = []
    for item in raw_annos:
        cid = item.get("category_id")
        if not cid:
            continue
        try:
            cid = int(cid)
        except (ValueError, TypeError):
            continue

        cat_meta = _CATEGORY_ID_MAP.get(cid)
        if not cat_meta:
            continue

        enriched_annos.append({
            "category_id": cid,
            "pos": cat_meta.get("pos", ""),
            "full_path": cat_meta.get("full_path", ""),
            "leaf_name": cat_meta.get("leaf", ""),
            "target_expression": item.get("target_expression", ""),
            "explanation": item.get("explanation", "")
        })

    if return_model:
        return enriched_annos, used_model
    return enriched_annos


def analyze_sentence(
    sentence_text: str,
    provider: Optional[str] = None,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
    passage_id: Optional[str] = None,
    passage_text: str = "",
    answer_text: str = "",
    explanation_text: str = ""
) -> List[Dict[str, Any]]:
    """
    문장 어법 분석 수행
    - 전처리: 선지 번호(1~5, ①~⑤ 등) 제외 및 지문 밑줄/빈칸에 정답 선지 자동 채움
    - provider 지정 시: 해당 단일 모델 단독 호출
    - provider 미지정 시: 활성화된 모든 모델 병렬 호출 후 '다수결 합의(Majority Vote)' 판정
    """
    import concurrent.futures

    # 문장 전처리: 선지 번호 제외 및 밑줄에 정답 선지 삽입
    clean_text = prepare_sentence_for_analysis(
        sentence_text,
        passage_id=passage_id,
        passage_text=passage_text,
        answer_text=answer_text,
        explanation_text=explanation_text
    )
    if not clean_text:
        clean_text = sentence_text

    # 1. 특정 Provider 명시 호출 (테스트 또는 단일 지정 시)
    if provider:
        p = provider.lower()
        if p == "openrouter" and is_openrouter_ensemble_enabled() and not model:
            # 모델 미지정 OpenRouter 호출 시 앙상블 모드로 자동 처리
            pass
        else:
            k = api_key or get_provider_config(p)[0]
            m = model or get_provider_config(p)[1]
            if not k:
                raise ValueError(f"{PROVIDER_NAMES.get(p, p.upper())} API Key가 설정되지 않았습니다.")
            return _call_llm(clean_text, p, k, m)

    # 2. 복수 활성 모델 설정 조회
    active_configs = get_active_ai_configs()
    valid_configs = [c for c in active_configs if c["api_key"]]

    if not valid_configs:
        raise ValueError("활성화된 AI 모델 중 유효한 API Key가 설정된 모델이 없습니다. 상단 [🔑 AI 설정]에서 키를 등록해 주세요.")

    # 3. 단일 모델 활성화 시: 기존과 동일하게 단독 호출
    if len(valid_configs) == 1:
        c = valid_configs[0]
        return _call_llm(clean_text, c["provider"], c["api_key"], c["model"])

    # 4. 2개 이상 모델 활성화 시 (복수 프로바이더 또는 OpenRouter 3개 모델 앙상블):
    #    ThreadPoolExecutor로 병렬 비동기 호출 & 다수결 합의(Majority Vote) 산출
    results_by_worker: Dict[str, List[Dict[str, Any]]] = {}
    errors: List[str] = []

    def _worker(cfg):
        try:
            annos = _call_llm(clean_text, cfg["provider"], cfg["api_key"], cfg["model"])
            w_label = cfg.get("short_label") or cfg.get("label") or cfg.get("name") or cfg["provider"]
            return w_label, annos, None
        except Exception as ex:
            w_label = cfg.get("short_label") or cfg.get("label") or cfg.get("name") or cfg["provider"]
            return w_label, [], str(ex)

    with concurrent.futures.ThreadPoolExecutor(max_workers=len(valid_configs)) as executor:
        future_map = {executor.submit(_worker, c): c for c in valid_configs}
        for future in concurrent.futures.as_completed(future_map):
            w_label, annos, err = future.result()
            if err:
                errors.append(f"{w_label}: {err}")
            else:
                results_by_worker[w_label] = annos

    # 모든 활성화된 모델이 전원 실패한 경우에만 최종 예외 발생
    if len(results_by_worker) == 0:
        raise ValueError(f"활성화된 모든 AI 모델 호출 실패: {'; '.join(errors)}")

    # 실패한 모델이 일부 있지만 1개 이상의 모델이 성공한 경우: 성공한 모델들로 무중단 분석 진행
    failed_labels = []
    if errors:
        failed_labels = [prov_err.split(":")[0].strip() for prov_err in errors]

    # 살아남은 성공 모델 수 기준으로 모수(surviving_N) 동적 조정
    surviving_N = len(results_by_worker)
    consensus_mode = get_consensus_mode()

    if surviving_N == 1:
        min_votes = 1
    elif consensus_mode == "strict":
        min_votes = surviving_N
    elif consensus_mode == "at_least_2":
        min_votes = min(2, surviving_N)
    else:  # "majority" (과반수 찬성)
        min_votes = max(2, (surviving_N // 2) + 1)

    # 각 category_id별 찬성한 모델 및 어노테이션 집계
    cat_votes: Dict[int, List[str]] = {}
    cat_annos: Dict[int, List[Dict[str, Any]]] = {}

    for w_label, annos in results_by_worker.items():
        for a in annos:
            cid = a.get("category_id")
            if cid:
                if cid not in cat_votes:
                    cat_votes[cid] = []
                    cat_annos[cid] = []
                if w_label not in cat_votes[cid]:
                    cat_votes[cid].append(w_label)
                cat_annos[cid].append(a)

    # 찬성 모델 수가 기준(min_votes) 이상인 범주만 채택
    accepted_cat_ids = [cid for cid, voters in cat_votes.items() if len(voters) >= min_votes]

    if not accepted_cat_ids:
        # 모델 간 합의 기준을 충족하는 어법 범주가 없는 경우 빈 배열 반환 (화면에서 '해당사항 없음'으로 처리)
        return []

    consensus_annos: List[Dict[str, Any]] = []
    fallback_note = f" ({', '.join(failed_labels)} 일시 실패로 제외)" if failed_labels else ""

    is_pure_openrouter_ensemble = all(c.get("provider") == "openrouter" for c in valid_configs)

    for cid in sorted(accepted_cat_ids):
        cat_meta = _CATEGORY_ID_MAP.get(cid, {})
        voters = cat_votes[cid]
        num_votes = len(voters)

        # 다수결 합의 태그 구성 (전원 일치 vs 다수결 찬성 vs 단독 반영)
        prefix = "OpenRouter 앙상블" if is_pure_openrouter_ensemble else "다수결 합의"
        if surviving_N == 1:
            consensus_tag = f"[{prefix} 단독 채택: {', '.join(voters)}]{fallback_note}"
        elif num_votes == surviving_N:
            consensus_tag = f"[{prefix} 전원 일치 ({num_votes}/{surviving_N}): {', '.join(voters)}]{fallback_note}"
        else:
            consensus_tag = f"[{prefix} 찬성 ({num_votes}/{surviving_N}): {', '.join(voters)}]{fallback_note}"

        matching_annos = cat_annos[cid]

        target_exp = ""
        for a in matching_annos:
            if a.get("target_expression"):
                target_exp = a.get("target_expression")
                break

        # 가장 상세한 해설 선정
        best_exp = ""
        if matching_annos:
            best_exp = max((a.get("explanation", "") for a in matching_annos), key=len)

        explanation_with_consensus = f"{consensus_tag} {best_exp}".strip()

        consensus_annos.append({
            "category_id": cid,
            "pos": cat_meta.get("pos", ""),
            "full_path": cat_meta.get("full_path", ""),
            "leaf_name": cat_meta.get("leaf", ""),
            "target_expression": target_exp,
            "explanation": explanation_with_consensus
        })

    return consensus_annos


# OpenRouter Top 5 모델 기본 메타데이터 (네트워크 장애 대비 폴백용 & 초기값)
DEFAULT_OPENROUTER_TOP_MODELS: List[Dict[str, Any]] = [
    {
        "id": "deepseek/deepseek-chat",
        "name": "DeepSeek: DeepSeek V3",
        "badge": "🥇 인기 1위",
        "tag": "초저비용 고성능",
        "prompt_price": "$0.32/1M",
        "completion_price": "$0.89/1M",
        "context_length": "160k",
        "description": "OpenRouter 이용량 1위의 초가성비 고성능 LLM (추론 및 한국어 번역 우수)"
    },
    {
        "id": "openai/gpt-4o-mini",
        "name": "OpenAI: GPT-4o-mini",
        "badge": "🥈 가성비 1위",
        "tag": "초고속 & 저비용",
        "prompt_price": "$0.15/1M",
        "completion_price": "$0.60/1M",
        "context_length": "128k",
        "description": "초고속 응답 속도와 매우 저렴한 비용의 OpenAI 표준 추천 경량 모델"
    },
    {
        "id": "anthropic/claude-sonnet-4.5",
        "name": "Anthropic: Claude Sonnet 4.5",
        "badge": "🥉 어법정밀 1위",
        "tag": "최고급 문해력",
        "prompt_price": "$3.00/1M",
        "completion_price": "$15.00/1M",
        "context_length": "976k",
        "description": "가장 정밀한 언어 이해 및 문법/어법 범주 다중 분류 최고 정확도"
    },
    {
        "id": "openai/gpt-4o",
        "name": "OpenAI: GPT-4o",
        "badge": "4위 플래그십",
        "tag": "표준 플래그십",
        "prompt_price": "$2.50/1M",
        "completion_price": "$10.00/1M",
        "context_length": "128k",
        "description": "복합 지문 이해 및 심층 문맥 추론용 업계 표준 플래그십 모델"
    },
    {
        "id": "meta-llama/llama-3.3-70b-instruct",
        "name": "Meta: Llama 3.3 70B Instruct",
        "badge": "5위 오픈소스",
        "tag": "초저가 오픈소스",
        "prompt_price": "$0.10/1M",
        "completion_price": "$0.32/1M",
        "context_length": "128k",
        "description": "최저 수준의 단가로 405B급 고성능을 제공하는 Meta의 최신 오픈소스 모델"
    }
]

_OPENROUTER_CACHE: Dict[str, Any] = {
    "timestamp": 0,
    "models": []
}


def get_openrouter_top_models(force_refresh: bool = False) -> List[Dict[str, Any]]:
    """OpenRouter의 실시간 모델 API(https://openrouter.ai/api/v1/models)에서 Top 5 모델 정보 동적 추출 및 반환"""
    import time
    global _OPENROUTER_CACHE

    now = time.time()
    # 30분 캐시 유지 (force_refresh가 아닌 경우)
    if not force_refresh and _OPENROUTER_CACHE.get("models") and (now - _OPENROUTER_CACHE.get("timestamp", 0) < 1800):
        return _OPENROUTER_CACHE["models"]

    try:
        url = "https://openrouter.ai/api/v1/models"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) GichulDB/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            all_models = data.get("data", [])

        model_dict = {m.get("id"): m for m in all_models if "id" in m}

        updated_models = []
        for default_m in DEFAULT_OPENROUTER_TOP_MODELS:
            mid = default_m["id"]
            live_m = model_dict.get(mid)
            if live_m:
                prompt_p = float(live_m.get("pricing", {}).get("prompt", 0)) * 1_000_000
                comp_p = float(live_m.get("pricing", {}).get("completion", 0)) * 1_000_000
                ctx = live_m.get("context_length", 0) // 1024
                ctx_str = f"{ctx}k" if ctx > 0 else default_m["context_length"]

                updated_models.append({
                    "id": mid,
                    "name": live_m.get("name", default_m["name"]),
                    "badge": default_m["badge"],
                    "tag": default_m["tag"],
                    "prompt_price": f"${prompt_p:.2f}/1M",
                    "completion_price": f"${comp_p:.2f}/1M",
                    "context_length": ctx_str,
                    "description": live_m.get("description", default_m["description"])[:110] + "..." if live_m.get("description") else default_m["description"]
                })
            else:
                updated_models.append(default_m)

        _OPENROUTER_CACHE = {
            "timestamp": now,
            "models": updated_models
        }
        return updated_models
    except Exception as e:
        logger.warning("[OpenRouter Models API 경고] 실시간 정보 로드 실패, 기본 캐시 사용: %s", e)
        return DEFAULT_OPENROUTER_TOP_MODELS


_ALL_OPENROUTER_CACHE: Dict[str, Any] = {
    "timestamp": 0,
    "models": []
}


def get_all_openrouter_models(force_refresh: bool = False) -> List[Dict[str, Any]]:
    """OpenRouter의 실시간 모델 API(https://openrouter.ai/api/v1/models)에서 전체 텍스트 모델 목록 조회 및 캐시"""
    import time
    global _ALL_OPENROUTER_CACHE

    now = time.time()
    if not force_refresh and _ALL_OPENROUTER_CACHE.get("models") and (now - _ALL_OPENROUTER_CACHE.get("timestamp", 0) < 1800):
        return _ALL_OPENROUTER_CACHE["models"]

    try:
        url = "https://openrouter.ai/api/v1/models"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) GichulDB/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            all_raw = data.get("data", [])

        clean_models = []
        for m in all_raw:
            mid = m.get("id", "")
            if not mid:
                continue
            pricing = m.get("pricing", {}) or {}
            try:
                prompt_p = float(pricing.get("prompt", 0) or 0) * 1_000_000
            except Exception:
                logger.debug("Failed to parse prompt price", exc_info=True)
                prompt_p = 0.0
            try:
                comp_p = float(pricing.get("completion", 0) or 0) * 1_000_000
            except Exception:
                logger.debug("Failed to parse completion price", exc_info=True)
                comp_p = 0.0

            ctx = (m.get("context_length", 0) or 0) // 1024
            ctx_str = f"{ctx}k" if ctx > 0 else "-"
            prov = mid.split("/")[0] if "/" in mid else "other"

            clean_models.append({
                "id": mid,
                "name": m.get("name") or mid,
                "provider": prov,
                "prompt_price": f"${prompt_p:.2f}/1M" if prompt_p > 0 else "무료",
                "completion_price": f"${comp_p:.2f}/1M" if comp_p > 0 else "무료",
                "context_length": ctx_str,
                "description": (m.get("description") or "")[:120]
            })

        priority_providers = ["deepseek", "openai", "anthropic", "google", "meta-llama", "mistralai", "qwen"]
        def sort_key(item):
            p = item["provider"].lower()
            try:
                idx = priority_providers.index(p)
            except ValueError:
                idx = 999
            return (idx, item["name"].lower())

        clean_models.sort(key=sort_key)

        _ALL_OPENROUTER_CACHE = {
            "timestamp": now,
            "models": clean_models
        }
        return clean_models
    except Exception as e:
        logger.error("[OpenRouter All Models API 오류] %s", e, exc_info=True)
        if _ALL_OPENROUTER_CACHE.get("models"):
            return _ALL_OPENROUTER_CACHE["models"]
        return [
            {
                "id": m["id"],
                "name": m["name"],
                "provider": m["id"].split("/")[0],
                "prompt_price": m["prompt_price"],
                "completion_price": m["completion_price"],
                "context_length": m["context_length"],
                "description": m["description"]
            }
            for m in DEFAULT_OPENROUTER_TOP_MODELS
        ]


def translate_listening_script(script_text: str) -> str:
    """
    영어 듣기 대본(Script)을 설정된 AI 모델(OpenRouter, Gemini, OpenAI, Claude 등)을 통해
    수능 표준 대화체 한국어 해설 텍스트로 고품질 1:1 번역
    """
    if not script_text or not script_text.strip():
        return ""

    active_configs = get_active_ai_configs()
    valid_configs = [c for c in active_configs if c.get("api_key")]
    if not valid_configs:
        logger.warning("[translate_listening_script] 유효한 AI API Key가 설정되지 않았습니다.")
        return ""

    cfg = valid_configs[0]
    provider = cfg["provider"]
    api_key = cfg["api_key"]
    model = cfg["model"]

    system_prompt = (
        "당신은 대한민국 대학수학능력시험 영어 듣기 평가 전문 번역가입니다.\n"
        "주어진 영어 듣기 대본(Script)을 정밀하고 자연스러운 고품질 한국어 대화체로 1:1 번역하십시오.\n"
        "[번역 규칙]\n"
        "1. 화자 태그(W:, M:, Girl:, Boy:, Teacher:, Woman:, Man: 등)를 자연스러운 한국어 화자 태그('여:', '남:' 등)로 번역하십시오.\n"
        "2. 빈칸(____)이나 밑줄은 형태를 그대로 유지하십시오.\n"
        "3. 오직 번역된 대본 텍스트만 출력하십시오. 추가 설명, 인사말, 마크다운 코드블록(```)은 절대 출력하지 마십시오."
    )
    user_prompt = f"다음 영어 듣기 대본을 한국어로 번역하십시오:\n\n{script_text.strip()}"

    try:
        if provider == "openrouter":
            url = "https://openrouter.ai/api/v1/chat/completions"
            payload = {
                "model": model or "openai/gpt-4o-mini",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                "temperature": 0.2
            }
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {api_key}",
                    "HTTP-Referer": "http://localhost:8000",
                    "X-Title": "Gichul DB Listening Translator"
                },
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=35) as resp:
                resp_data = json.loads(resp.read().decode("utf-8"))
                return resp_data["choices"][0]["message"]["content"].strip()

        elif provider == "openai":
            url = "https://api.openai.com/v1/chat/completions"
            payload = {
                "model": model or "gpt-4o-mini",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                "temperature": 0.2
            }
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                resp_data = json.loads(resp.read().decode("utf-8"))
                return resp_data["choices"][0]["message"]["content"].strip()

        elif provider == "claude":
            url = "https://api.anthropic.com/v1/messages"
            payload = {
                "model": model or "claude-haiku-4-5",
                "max_tokens": 2048,
                "system": system_prompt,
                "messages": [{"role": "user", "content": user_prompt}]
            }
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json", "x-api-key": api_key, "anthropic-version": "2023-06-01"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                resp_data = json.loads(resp.read().decode("utf-8"))
                return resp_data["content"][0]["text"].strip()

        elif provider == "gemini":
            cand_m = resolve_gemini_model(api_key, model)
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{cand_m}:generateContent?key={api_key}"
            payload = {
                "contents": [{"parts": [{"text": f"{system_prompt}\n\n{user_prompt}"}]}],
                "generationConfig": {"temperature": 0.2}
            }
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                resp_data = json.loads(resp.read().decode("utf-8"))
                return resp_data["candidates"][0]["content"]["parts"][0]["text"].strip()

        elif provider == "lmstudio":
            url = f"{get_lmstudio_base_url().rstrip('/')}/chat/completions"
            payload = {
                "model": model or "local-model",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                "temperature": 0.2
            }
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=40) as resp:
                resp_data = json.loads(resp.read().decode("utf-8"))
                return resp_data["choices"][0]["message"]["content"].strip()

    except Exception as e:
        logger.error(f"[translate_listening_script] {provider} 호출 실패: {e}")
        return ""

    return ""


