"""
FastAPI 주요 API 스모크 및 미들웨어 통합 테스트 (tests/test_api_smoke.py)
- 태그 추가/삭제 시 검색 캐시 무효화 및 검색 결과 즉시 반영 검증
- 존재하지 않는 시험지의 듣기 ZIP 다운로드 시 404 반환 검증
- AI API 키 미등록 시 배치 어법 분석 400 반환 검증
- 정적 JS 파일 서빙 시 no-cache 헤더 적용 검증
"""

import pytest


@pytest.fixture
def seeded_passage(tmp_db):
    """API 테스트용 기본 시험지, 지문, 문장 생성"""
    exam = {
        "id": "[고3-2099년-06월]",
        "grade": "고3",
        "year": 2099,
        "month": 6,
        "exam_type": "평가원",
        "reading_start_q": 18,
        "reading_end_q": 45,
    }
    tmp_db.save_exam(exam)

    pid = "[고3-2099년-06월-18번]"
    passage = {
        "id": pid,
        "exam_id": exam["id"],
        "q_num": 18,
        "question_title": "18. 다음 글의 목적으로 가장 적절한 것은?",
        "question_type": "목적",
        "passage_text": "We are planning a special workshop on artificial intelligence.",
        "answer_text": "①",
        "explanation_text": "[정답] ①",
        "pdf_crop_image": "",
        "validation_ratio": 1.0,
        "remarks": "",
    }
    tmp_db.save_passage(passage)

    sid = f"{pid}-01"
    sentences = [
        {
            "id": sid,
            "passage_id": pid,
            "order_index": 1,
            "sentence_text": "We are planning a special workshop on artificial intelligence.",
            "word_count": 9,
            "remarks": "",
        }
    ]
    tmp_db.save_sentences(sentences)
    return {"exam_id": exam["id"], "passage_id": pid, "sentence_id": sid}


def test_tag_mutation_invalidates_cache_and_updates_search(isolated_client, seeded_passage):
    """지문/문장 태그 추가 및 삭제 시 캐시가 무효화되어 검색에 즉각 반영되는지 검증"""
    client = isolated_client
    pid = seeded_passage["passage_id"]
    sid = seeded_passage["sentence_id"]

    # 1. 지문 첫 검색 (캐시 적재, 태그 없음)
    res1 = client.get("/api/search/passages?keyword=workshop")
    assert res1.status_code == 200
    items1 = res1.json().get("items", [])
    assert len(items1) == 1
    assert items1[0]["tags"] == []

    # 2. 지문 태그 추가 (POST -> invalidate_cache_on_write 동작)
    res_tag = client.post(f"/api/passages/{pid}/tags", json={"tag_name": "AI워크숍"})
    assert res_tag.status_code == 200
    assert "AI워크숍" in res_tag.json().get("tags", [])

    # 3. 재검색 시 캐시가 비워져 신규 태그가 즉시 반영되어야 함
    res2 = client.get("/api/search/passages?keyword=workshop")
    assert res2.status_code == 200
    items2 = res2.json().get("items", [])
    assert len(items2) == 1
    assert "AI워크숍" in items2[0]["tags"]

    # 4. 문장 태그 추가 및 문장 검색 반영 검증
    res_stag = client.post(f"/api/sentences/{sid}/tags", json={"tag_name": "핵심표현"})
    assert res_stag.status_code == 200

    res_s_search = client.get("/api/search/sentences?keyword=workshop")
    assert res_s_search.status_code == 200
    s_items = res_s_search.json().get("items", [])
    assert len(s_items) == 1
    assert "핵심표현" in s_items[0]["tags"]

    # 5. 지문 태그 삭제 후 재검색 시 제거 확인
    res_del = client.delete(f"/api/passages/{pid}/tags/AI워크숍")
    assert res_del.status_code == 200

    res3 = client.get("/api/search/passages?keyword=workshop")
    assert res3.status_code == 200
    assert "AI워크숍" not in res3.json()["items"][0]["tags"]


def test_listening_zip_download_404_for_nonexistent_exam(isolated_client):
    """존재하지 않거나 듣기 음원이 없는 시험지 ID로 ZIP 요청 시 404 Not Found 반환"""
    client = isolated_client
    res = client.get("/api/exams/non-existent-exam-2099/download-listening-zip")
    assert res.status_code == 404
    assert res.json().get("detail") or res.json().get("message")


def test_batch_analyze_grammar_missing_ai_key_returns_400(isolated_client, seeded_passage):
    """AI API 키가 미등록된 상태에서 일괄 어법 분석 요청 시 400 Bad Request 반환"""
    client = isolated_client
    sid = seeded_passage["sentence_id"]

    res = client.post("/api/sentences/batch-analyze-grammar", json={"sentence_ids": [sid]})
    assert res.status_code == 400
    detail = res.json().get("detail", "")
    assert "API Key" in detail or "키" in detail


def test_single_sentence_analyze_grammar_missing_sentence_returns_404(isolated_client):
    """존재하지 않는 문장 ID에 대해 어법 분석 요청 시 404 Not Found 반환"""
    client = isolated_client
    res = client.post("/api/sentences/non-existent-sentence-99/analyze-grammar")
    assert res.status_code == 404


def test_static_js_no_cache_header(isolated_client):
    """ES 모듈 정적 파일(/static/js/*.js) 요청 시 Cache-Control: no-cache 헤더 반환 검증"""
    client = isolated_client
    res = client.get("/static/js/main.js")
    # 파일이 존재하면 200 및 no-cache 헤더 검증
    if res.status_code == 200:
        assert res.headers.get("Cache-Control") == "no-cache"


def test_delete_exam_normalizes_bracket_id(isolated_client, seeded_passage):
    """DELETE /api/exams/{exam_id} 호출 시 대괄호 없는 ID도 normalize_bracket_id 정규화 후 정상 삭제"""
    client = isolated_client
    exam_id = seeded_passage["exam_id"]  # "[고3-2024년-06월]"
    raw_id_without_brackets = exam_id.strip("[]")  # "고3-2024년-06월"

    # 대괄호 없는 식별자로 삭제 요청
    res = client.delete(f"/api/exams/{raw_id_without_brackets}")
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data["exam_id"] == exam_id

    # 이미 삭제되었으므로 다시 삭제 시 404 반환
    res_again = client.delete(f"/api/exams/{raw_id_without_brackets}")
    assert res_again.status_code == 404


def test_seed_sample_data_endpoint_removed(isolated_client):
    """실데이터 덮어쓰기 위험이 있던 /api/seed-sample-data 엔드포인트가 제거되어 404 반환 검증"""
    client = isolated_client
    res = client.post("/api/seed-sample-data")
    assert res.status_code in (404, 405)

