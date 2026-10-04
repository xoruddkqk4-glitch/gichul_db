"""
05-gichul_db: 문장 어법 분석 서비스 (services/grammar_service.py)
- 단일 분석 API / 배치 분석 API / 업로드 후 백그라운드 자동 분석 3곳에 복제되어 있던
  "전처리(빈칸 정답 채우기) → 문장 텍스트 갱신 → Multi-LLM 어법 분석 → 결과 저장" 흐름을 하나로 합친다.
"""

from typing import Any, Dict, List, Optional

from .. import database as db
from .. import grammar_analyzer


def get_cached_passage(passage_id: Optional[str], passage_cache: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """passage_id 에 해당하는 지문을 캐시에서 꺼내거나, 없으면 DB에서 읽어 캐시에 넣는다."""
    if not passage_id:
        return None
    if passage_id not in passage_cache:
        passage_cache[passage_id] = db.get_passage(passage_id)
    return passage_cache[passage_id]


def analyze_and_save_sentence(
    sentence_row: Dict[str, Any],
    passage_cache: Optional[Dict[str, Any]] = None,
    sentence_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    문장 1개를 어법 분석하고 결과를 DB에 저장한다.

    - sentence_row: 최소 "id", "sentence_text", "passage_id" 를 가진 dict.
      전처리로 문장이 바뀌면 sentence_row["sentence_text"] 도 함께 갱신된다 (기존 동작과 동일).
    - passage_cache: 같은 지문을 여러 번 읽지 않도록 공유하는 dict (없으면 이번 호출용으로 새로 만듦)
    - sentence_id: DB 갱신/저장에 쓸 ID. 생략하면 sentence_row["id"] 를 쓴다.
      (단일 분석 API 는 요청 경로에서 정규화한 ID 를 그대로 쓰던 기존 동작을 유지하려고 넘긴다)

    반환: {"sentence_id", "sentence_text", "annotations"}
    예외는 잡지 않고 그대로 올린다 (호출하는 쪽이 HTTP 500 / 결과 목록 / 로그 중 알맞게 처리).
    """
    if passage_cache is None:
        passage_cache = {}
    sid = sentence_id or sentence_row["id"]
    pid = sentence_row.get("passage_id")
    p_data = get_cached_passage(pid, passage_cache)

    passage_text = p_data.get("passage_text", "") if p_data else ""
    answer_text = p_data.get("answer_text", "") if p_data else ""
    explanation_text = p_data.get("explanation_text", "") if p_data else ""

    # 안전망: 이미 채워진 빈칸이 예전(현재 정답이 아닌) 선지로 남아 있으면 현재 정답으로 바로잡는다
    if pid:
        clean_sid = db.normalize_bracket_id(sid)
        for change in db.refill_blank_sentences(passage_ids=[pid]):
            if change["sentence_id"] == clean_sid:
                sentence_row["sentence_text"] = change["new_text"]

    # 밑줄 빈칸 문제의 경우 정답 선지를 반영하고 선지 기호를 정제하여 온전한 문장 생성
    prep_text = grammar_analyzer.prepare_sentence_for_analysis(
        sentence_row["sentence_text"],
        passage_id=pid,
        passage_text=passage_text,
        answer_text=answer_text,
        explanation_text=explanation_text,
    )
    if prep_text and prep_text != sentence_row["sentence_text"]:
        db.update_sentence_text(sid, prep_text)
        sentence_row["sentence_text"] = prep_text

    annos: List[Dict[str, Any]] = grammar_analyzer.analyze_sentence(
        sentence_row["sentence_text"],
        passage_id=pid,
        passage_text=passage_text,
        answer_text=answer_text,
        explanation_text=explanation_text,
    )
    db.save_grammar_annotations(sid, annos, source_type="AI", ai_model="Multi-LLM")
    return {
        "sentence_id": sid,
        "sentence_text": sentence_row["sentence_text"],
        "annotations": annos,
    }
