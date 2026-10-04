"""
05-gichul_db: 등급별 데이터 접근 필터 (access.py)

배포에 대비해 등급(role)별로 응답 데이터를 거르는 자리를 미리 마련해 둔다.
- 지금은 로그인/인증이 없으므로 모든 호출이 DEFAULT_ROLE(관리자)로 들어오고, 동작은 예전과 같다.
- 배포할 때는 app.get_current_role()만 세션/토큰 기반으로 바꾸면 된다. DB 테이블은 등급별로 나누지 않는다.

등급별 공개 범위
- 관리자(admin): 모든 데이터
- 회원(member): 코어 문항 데이터(문제·지문, 해설, 정답) + 문항 메타 정보(정답률·선지 선택률, 어법 범주, 태그)
- 비회원(guest): 코어 문항 데이터만

필터 원칙
- 관리자는 원본 dict를 그대로 돌려준다 (복사 비용 0, 로컬 동작 불변)
- 그 밖의 등급은 숨길 필드를 뺀 얕은 복사본을 돌려준다 (원본 dict는 바꾸지 않는다)
- 알 수 없는 등급 문자열은 가장 낮은 등급(guest)으로 본다 (fail-closed)
- 응답 필드만이 아니라 검색 조건도 거른다: 비회원이 정답률/태그/어법 범주로 걸러 보면 메타 정보가 간접적으로 드러나기 때문
"""

from typing import Any, Dict, Iterable, List, Optional

ROLE_ADMIN = "admin"
ROLE_MEMBER = "member"
ROLE_GUEST = "guest"
ROLES = (ROLE_ADMIN, ROLE_MEMBER, ROLE_GUEST)

# 인증이 붙기 전까지의 기본 등급 (로컬 단독 사용 = 관리자)
DEFAULT_ROLE = ROLE_ADMIN

# 회원 이상에게만 공개하는 문항 메타 정보
PASSAGE_META_FIELDS = frozenset({
    "correct_rate",       # 정답률
    "choice_rates",       # 선지 선택률 (JSON 문자열)
    "choice_rates_obj",   # 선지 선택률 (파싱 결과)
    "tags",               # 지문 태그
})
SENTENCE_META_FIELDS = frozenset({
    "tags",                 # 문장 태그
    "grammar_annotations",  # 어법 범주 (AI/사용자 분석 결과)
    "grammar_analyzed",     # 어법 분석 완료 여부
    "correct_rate",         # (문장 검색 결과에 지문 정답률이 함께 실릴 때)
    "choice_rates",
})

# 관리자에게만 공개하는 운영/개인 데이터
PASSAGE_ADMIN_FIELDS = frozenset({
    "user_memo",
    "user_memo_updated_at",
    "answer_source",      # 정답 출처 (verified_key / csv / image_consensus ...)
    "answer_verified",    # 정답 검증 상태
    "validation_ratio",   # HWP-PDF 일치율
    "remarks",
})
SENTENCE_ADMIN_FIELDS = frozenset({
    "is_starred",         # 관리자 개인 즐겨찾기
    "remarks",
})


def normalize_role(role: Optional[str]) -> str:
    """등급 문자열 정규화. None/빈 값은 기본 등급, 모르는 값은 guest(가장 낮은 등급)."""
    if not role:
        return DEFAULT_ROLE
    r = str(role).strip().lower()
    return r if r in ROLES else ROLE_GUEST


def is_admin(role: Optional[str]) -> bool:
    return normalize_role(role) == ROLE_ADMIN


def can_view_meta(role: Optional[str]) -> bool:
    """정답률·선지 선택률, 어법 범주, 태그를 볼 수 있는 등급인지 (회원 이상)"""
    return normalize_role(role) in (ROLE_ADMIN, ROLE_MEMBER)


def _hidden_fields(role: str, meta_fields: frozenset, admin_fields: frozenset) -> frozenset:
    if role == ROLE_ADMIN:
        return frozenset()
    if role == ROLE_MEMBER:
        return admin_fields
    return admin_fields | meta_fields


def _strip(item: Optional[Dict[str, Any]], hidden: frozenset) -> Optional[Dict[str, Any]]:
    if not item or not hidden:
        return item
    return {k: v for k, v in item.items() if k not in hidden}


def filter_passage(passage: Optional[Dict[str, Any]], role: Optional[str] = DEFAULT_ROLE) -> Optional[Dict[str, Any]]:
    """지문 dict 하나를 등급에 맞게 거른다 (관리자면 원본 그대로)."""
    r = normalize_role(role)
    return _strip(passage, _hidden_fields(r, PASSAGE_META_FIELDS, PASSAGE_ADMIN_FIELDS))


def filter_passages(passages: Iterable[Dict[str, Any]], role: Optional[str] = DEFAULT_ROLE) -> List[Dict[str, Any]]:
    """지문 dict 목록을 등급에 맞게 거른다 (관리자면 원본 목록 그대로)."""
    r = normalize_role(role)
    if r == ROLE_ADMIN:
        return passages if isinstance(passages, list) else list(passages)
    hidden = _hidden_fields(r, PASSAGE_META_FIELDS, PASSAGE_ADMIN_FIELDS)
    return [_strip(p, hidden) for p in passages]


def filter_sentence(sentence: Optional[Dict[str, Any]], role: Optional[str] = DEFAULT_ROLE) -> Optional[Dict[str, Any]]:
    """문장 dict 하나를 등급에 맞게 거른다 (관리자면 원본 그대로)."""
    r = normalize_role(role)
    return _strip(sentence, _hidden_fields(r, SENTENCE_META_FIELDS, SENTENCE_ADMIN_FIELDS))


def filter_sentences(sentences: Iterable[Dict[str, Any]], role: Optional[str] = DEFAULT_ROLE) -> List[Dict[str, Any]]:
    """문장 dict 목록을 등급에 맞게 거른다 (관리자면 원본 목록 그대로)."""
    r = normalize_role(role)
    if r == ROLE_ADMIN:
        return sentences if isinstance(sentences, list) else list(sentences)
    hidden = _hidden_fields(r, SENTENCE_META_FIELDS, SENTENCE_ADMIN_FIELDS)
    return [_strip(s, hidden) for s in sentences]


def allowed_search_filters(role: Optional[str] = DEFAULT_ROLE) -> Dict[str, bool]:
    """등급별로 쓸 수 있는 검색 조건.

    meta:  정답률 구간, 태그, 어법 범주/품사 조건 (회원 이상)
    admin: 즐겨찾기(is_starred) 조건 (관리자 전용)
    """
    r = normalize_role(role)
    return {"meta": r in (ROLE_ADMIN, ROLE_MEMBER), "admin": r == ROLE_ADMIN}
