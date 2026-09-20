"""
05-gichul_db: 멀티 LLM(Gemini, OpenRouter, ChatGPT, Claude) 문장 어법 범주 분석기 모듈
- grammar_categories.json 기준 243개 어법 체계 매칭
- Google Gemini, OpenRouter, OpenAI ChatGPT, Anthropic Claude REST API 직접 연동 (SDK 불필요)
- 단일 문장 실시간 분석 및 다중 문장 배치 분석 지원
"""

import os
import json
import urllib.request
import urllib.error
from typing import Dict, List, Any, Optional, Tuple

import database

# 범주표 로드 및 캐싱
DATA_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "data", "grammar_categories.json")

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


SUPPORTED_PROVIDERS = ["gemini", "openai", "claude", "openrouter"]

PROVIDER_NAMES = {
    "gemini": "Google Gemini",
    "openai": "OpenAI ChatGPT",
    "claude": "Anthropic Claude",
    "openrouter": "OpenRouter"
}

PROVIDER_DEFAULT_MODELS = {
    "gemini": "gemini-2.5-flash",
    "openai": "gpt-4o-mini",
    "claude": "claude-3-5-haiku-20241022",
    "openrouter": "deepseek/deepseek-chat"
}

PROVIDER_ENV_VARS = {
    "gemini": "GEMINI_API_KEY",
    "openai": "OPENAI_API_KEY",
    "claude": "ANTHROPIC_API_KEY",
    "openrouter": "OPENROUTER_API_KEY"
}


def resolve_gemini_model(api_key: str, requested_model: str = "") -> str:
    """Gemini 사용 가능한 최신 모델 자동 탐색 및 반환 (종료된 1.5-flash 자동 마이그레이션)"""
    req_m = (requested_model or "").strip()
    if req_m.startswith("models/"):
        req_m = req_m[len("models/"):]

    # 사용자가 명시한 모델이 있고 1.5-flash 계열이 아니면 그대로 사용
    if req_m and req_m not in ("gemini-1.5-flash", "gemini-1.5-flash-latest"):
        return req_m

    # Google API의 ListModels를 호출하여 현재 API Key로 지원되는 모델 실시간 목록 확인
    if api_key:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) GichulDB/1.0"})
            with urllib.request.urlopen(req, timeout=6) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                supported = []
                for m in data.get("models", []):
                    methods = m.get("supportedGenerationMethods", [])
                    if "generateContent" in methods:
                        name = m.get("name", "")
                        clean_name = name[len("models/"):] if name.startswith("models/") else name
                        supported.append(clean_name)

                if supported:
                    # 플래시 모델 우선 선별
                    flash_models = [m for m in supported if "flash" in m.lower()]
                    for pref in ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-2.5-flash-lite", "gemini-1.5-flash-8b"]:
                        if pref in flash_models:
                            return pref
                    if flash_models:
                        return flash_models[0]
                    return supported[0]
        except Exception as e:
            print(f"[Gemini Model Auto-Discovery Warning] {e}")

    return "gemini-2.5-flash"


def get_provider_config(provider: str) -> Tuple[str, str]:
    """특정 Provider의 (api_key, model) 조회 (DB 설정 -> 레거시 설정 -> 환경변수 -> 기본값 폴백)"""
    p = provider.lower()
    # 1. 개별 키 설정 조회
    api_key = database.get_setting(f"ai_key_{p}", "")
    model = database.get_setting(f"ai_model_{p}", "")

    # 2. 레거시 단일 설정 폴백 (기존에 단일로 저장해둔 경우)
    legacy_p = database.get_setting("ai_provider", "gemini").lower()
    if not api_key and legacy_p == p:
        api_key = database.get_setting("ai_api_key", "")
    if not model and legacy_p == p:
        model = database.get_setting("ai_model", "")

    # 3. 환경변수 폴백
    if not api_key:
        env_var = PROVIDER_ENV_VARS.get(p)
        if env_var:
            api_key = os.getenv(env_var, "")

    # 4. 기본 모델 폴백
    if not model:
        model = PROVIDER_DEFAULT_MODELS.get(p, "gemini-2.5-flash")
    elif p == "gemini" and model in ("gemini-1.5-flash", "gemini-1.5-flash-latest"):
        model = "gemini-2.5-flash"

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
            pass

    # 레거시 폴백: ai_provider에 설정된 단일 값
    legacy_p = database.get_setting("ai_provider", "gemini").lower()
    if legacy_p in SUPPORTED_PROVIDERS:
        return [legacy_p]
    return ["gemini"]


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

        providers_info[p] = {
            "name": PROVIDER_NAMES.get(p, p),
            "is_active": p in active_providers,
            "has_key": bool(api_key),
            "masked_key": masked_key,
            "model": model,
            "default_model": PROVIDER_DEFAULT_MODELS.get(p, "")
        }

    return {
        "active_providers": active_providers,
        "mode": "ensemble" if len(active_providers) > 1 else "single",
        "providers": providers_info
    }


def get_active_ai_configs() -> List[Dict[str, str]]:
    """현재 활성화되어 실제 분석에 사용될 Provider 설정 목록 반환"""
    active_names = get_active_providers()
    configs = []
    for p in active_names:
        key, model = get_provider_config(p)
        configs.append({
            "provider": p,
            "name": PROVIDER_NAMES.get(p, p),
            "api_key": key,
            "model": model
        })
    return configs


def get_ai_config() -> Tuple[str, str, str]:
    """(하위 호환용) 첫 번째 활성 AI 설정 (provider, api_key, model) 반환"""
    active = get_active_providers()
    primary = active[0] if active else "gemini"
    api_key, model = get_provider_config(primary)
    return primary, api_key, model


def test_connection(provider: str, api_key: str, model: str = "") -> Tuple[bool, str]:
    """선택된 Provider 및 API Key로 연결 핑 테스트 수행"""
    load_categories()
    provider = provider.lower()
    test_sentence = "Not only did he arrive late, but he also forgot his homework."

    try:
        resolved_model = model
        if provider == "gemini":
            resolved_model = resolve_gemini_model(api_key, model)
        results = _call_llm(test_sentence, provider, api_key, resolved_model)
        prov_name = PROVIDER_NAMES.get(provider, provider.upper())
        used_model = resolved_model or PROVIDER_DEFAULT_MODELS.get(provider, "기본 모델")
        return True, f"연결 성공! {prov_name} ({used_model}) 연결이 정상 확인되었습니다."
    except Exception as e:
        return False, f"연결 실패: {str(e)}"


def _call_llm(sentence: str, provider: str, api_key: str, model: str = "") -> List[Dict[str, Any]]:
    """Provider별 REST API 호출 및 JSON 응답 파싱"""
    load_categories()
    provider = provider.lower()
    if not api_key:
        raise ValueError(f"{provider.upper()} API Key가 설정되지 않았습니다.")

    user_content = f"""[분석할 영어 문장]
"{sentence}"

[어법 범주 기준표 (일부/전체)]
{_CATEGORIES_SUMMARY_PROMPT}

위 문장을 분석하여 지정된 JSON 형식으로 응답하십시오."""

    raw_json_str = ""

    try:
        if provider == "gemini":
            target_model = resolve_gemini_model(api_key, model)
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{target_model}:generateContent?key={api_key}"
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
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            try:
                with urllib.request.urlopen(req, timeout=30) as resp:
                    resp_data = json.loads(resp.read().decode("utf-8"))
                    try:
                        raw_json_str = resp_data["candidates"][0]["content"]["parts"][0]["text"]
                    except (KeyError, IndexError) as e:
                        raise ValueError(f"Gemini 응답 구조 오류: {resp_data}")
            except urllib.error.HTTPError as gemini_he:
                if gemini_he.code == 404:
                    # 404 발생 시 지원 모델(gemini-2.0-flash, gemini-2.5-flash-lite, gemini-2.5-pro)로 1회 자동 폴백
                    alt_candidates = ["gemini-2.0-flash", "gemini-2.5-flash-lite", "gemini-2.5-pro"]
                    fallback_success = False
                    for alt_m in alt_candidates:
                        if alt_m == target_model:
                            continue
                        try:
                            alt_url = f"https://generativelanguage.googleapis.com/v1beta/models/{alt_m}:generateContent?key={api_key}"
                            alt_req = urllib.request.Request(
                                alt_url,
                                data=json.dumps(payload).encode("utf-8"),
                                headers={"Content-Type": "application/json"},
                                method="POST"
                            )
                            with urllib.request.urlopen(alt_req, timeout=30) as alt_resp:
                                alt_data = json.loads(alt_resp.read().decode("utf-8"))
                                raw_json_str = alt_data["candidates"][0]["content"]["parts"][0]["text"]
                                database.set_setting("ai_model_gemini", alt_m)
                                fallback_success = True
                                break
                        except Exception:
                            continue
                    if not fallback_success:
                        raise gemini_he
                else:
                    raise gemini_he

        elif provider == "openrouter":
            target_model = model or "openai/gpt-4o-mini"
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
            target_model = model or "claude-3-5-haiku-20241022"
            url = "https://api.anthropic.com/v1/messages"
            payload = {
                "model": target_model,
                "max_tokens": 1024,
                "system": SYSTEM_PROMPT,
                "messages": [
                    {"role": "user", "content": user_content + "\n반드시 JSON 블록만 단독 출력하십시오."}
                ],
                "temperature": 0.1
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
                raw_json_str = resp_data["content"][0]["text"]

        else:
            raise ValueError(f"지원하지 않는 AI Provider: {provider}")

    except urllib.error.HTTPError as he:
        err_body = he.read().decode("utf-8", errors="ignore")
        err_detail = ""
        try:
            err_json = json.loads(err_body)
            err_detail = err_json.get("error", {}).get("message") or err_json.get("message") or err_body
        except Exception:
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

    return enriched_annos


def analyze_sentence(
    sentence_text: str,
    provider: Optional[str] = None,
    api_key: Optional[str] = None,
    model: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    문장 어법 분석 수행
    - provider 지정 시: 해당 단일 모델 단독 호출
    - provider 미지정 시: 활성화된 모든 모델 병렬 호출 후 '엄격 교집합(Strict Intersection, 전원 일치)' 판정
    """
    import concurrent.futures

    # 1. 특정 Provider 명시 호출 (테스트 또는 단일 지정 시)
    if provider:
        p = provider.lower()
        k = api_key or get_provider_config(p)[0]
        m = model or get_provider_config(p)[1]
        if not k:
            raise ValueError(f"{PROVIDER_NAMES.get(p, p.upper())} API Key가 설정되지 않았습니다.")
        return _call_llm(sentence_text, p, k, m)

    # 2. 복수 활성 모델 설정 조회
    active_configs = get_active_ai_configs()
    valid_configs = [c for c in active_configs if c["api_key"]]

    if not valid_configs:
        raise ValueError("활성화된 AI 모델 중 유효한 API Key가 설정된 모델이 없습니다. 상단 [🔑 AI 설정]에서 키를 등록해 주세요.")

    # 3. 단일 모델 활성화 시: 기존과 동일하게 단독 호출
    if len(valid_configs) == 1:
        c = valid_configs[0]
        return _call_llm(sentence_text, c["provider"], c["api_key"], c["model"])

    # 4. 2개 이상 모델 활성화 시: ThreadPoolExecutor로 병렬 비동기 호출 & 엄격 교집합(전원 일치) 산출
    results_by_provider: Dict[str, List[Dict[str, Any]]] = {}
    errors: List[str] = []

    def _worker(cfg):
        try:
            annos = _call_llm(sentence_text, cfg["provider"], cfg["api_key"], cfg["model"])
            return cfg["provider"], annos, None
        except Exception as ex:
            return cfg["provider"], [], str(ex)

    with concurrent.futures.ThreadPoolExecutor(max_workers=len(valid_configs)) as executor:
        future_map = {executor.submit(_worker, c): c for c in valid_configs}
        for future in concurrent.futures.as_completed(future_map):
            prov, annos, err = future.result()
            if err:
                prov_label = PROVIDER_NAMES.get(prov, prov.upper())
                errors.append(f"{prov_label}: {err}")
            else:
                results_by_provider[prov] = annos

    if errors:
        # 엄격 교집합 판정을 위해서는 모든 활성 모델이 정상 응답해야 하므로 실패 모델 안내
        raise ValueError(f"멀티 LLM 분석 중 오류 발생: {'; '.join(errors)}")

    # 각 모델별 검출된 category_id 집합화
    provider_cat_ids: Dict[str, set] = {}
    for prov, annos in results_by_provider.items():
        provider_cat_ids[prov] = {a["category_id"] for a in annos if a.get("category_id")}

    # 엄격 교집합(Strict Intersection): 모든 모델이 공통으로 채택한 범주만 추출
    common_cat_ids = set.intersection(*provider_cat_ids.values()) if provider_cat_ids else set()

    if not common_cat_ids:
        # 모델 간 일치하는 어법 범주가 하나도 없는 경우 빈 배열 반환 (화면에서 '해당사항 없음'으로 처리)
        return []

    # 모델명 표시 문자열 구성
    prov_names_list = [PROVIDER_NAMES.get(c["provider"], c["provider"]) for c in valid_configs]
    consensus_tag = f"[교차 검증: {', '.join(prov_names_list)} 전원 일치 ({len(valid_configs)}/{len(valid_configs)})]"

    consensus_annos: List[Dict[str, Any]] = []
    for cid in sorted(common_cat_ids):
        cat_meta = _CATEGORY_ID_MAP.get(cid, {})

        # 각 모델이 제출한 해설 및 타겟 어구 취합
        matching_annos = []
        for prov, annos in results_by_provider.items():
            for a in annos:
                if a.get("category_id") == cid:
                    matching_annos.append(a)
                    break

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
        print(f"[OpenRouter Models API 경고] 실시간 정보 로드 실패, 기본 캐시 사용: {e}")
        return DEFAULT_OPENROUTER_TOP_MODELS
