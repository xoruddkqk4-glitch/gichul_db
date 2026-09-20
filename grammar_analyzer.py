"""
05-gichul_db: 멀티 LLM(Gemini, ChatGPT, Claude) 문장 어법 범주 분석기 모듈
- grammar_categories.json 기준 243개 어법 체계 매칭
- Google Gemini, OpenAI ChatGPT, Anthropic Claude REST API 직접 연동 (SDK 불필요)
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


def get_ai_config() -> Tuple[str, str, str]:
    """저장된 AI 설정 (provider, api_key, model) 조회"""
    provider = database.get_setting("ai_provider", "gemini").lower()
    api_key = database.get_setting("ai_api_key", "")
    model = database.get_setting("ai_model", "")

    # 환경변수 폴백 지원
    if not api_key:
        if provider == "gemini":
            api_key = os.getenv("GEMINI_API_KEY", "")
        elif provider == "openai":
            api_key = os.getenv("OPENAI_API_KEY", "")
        elif provider == "claude":
            api_key = os.getenv("ANTHROPIC_API_KEY", "")

    # 기본 모델 폴백
    if not model:
        if provider == "gemini":
            model = "gemini-1.5-flash"
        elif provider == "openai":
            model = "gpt-4o-mini"
        elif provider == "claude":
            model = "claude-3-5-haiku-20241022"

    return provider, api_key, model


def test_connection(provider: str, api_key: str, model: str = "") -> Tuple[bool, str]:
    """선택된 Provider 및 API Key로 연결 핑 테스트 수행"""
    load_categories()
    provider = provider.lower()
    test_sentence = "Not only did he arrive late, but he also forgot his homework."

    try:
        results = _call_llm(test_sentence, provider, api_key, model)
        return True, f"연결 성공! {provider.upper()} ({model or '기본 모델'}) 연결이 정상 확인되었습니다."
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

    if provider == "gemini":
        target_model = model or "gemini-1.5-flash"
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
        with urllib.request.urlopen(req, timeout=30) as resp:
            resp_data = json.loads(resp.read().decode("utf-8"))
            try:
                raw_json_str = resp_data["candidates"][0]["content"]["parts"][0]["text"]
            except (KeyError, IndexError) as e:
                raise ValueError(f"Gemini 응답 구조 오류: {resp_data}")

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

    # JSON 파싱 및 표준화
    parsed = json.loads(raw_json_str)
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
    """단일 문장 어법 분석 수행"""
    cfg_p, cfg_k, cfg_m = get_ai_config()
    p = provider or cfg_p
    k = api_key or cfg_k
    m = model or cfg_m

    if not k:
        raise ValueError("AI API Key가 설정되지 않았습니다. 상단 [🔑 AI 설정]에서 키를 등록해 주세요.")

    return _call_llm(sentence_text, p, k, m)
