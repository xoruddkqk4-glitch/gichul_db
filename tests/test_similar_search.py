"""
단락 기반 다중 기준 유사 지문 검색 + 연속 3·4단어 N-gram 단위·통합 테스트 (tests/test_similar_search.py)
"""

import pytest

from gichul import access
from gichul.services import similarity_search


@pytest.fixture
def sim_db(tmp_db):
    """유사 지문 검색 및 N-gram 시뮬레이션 검증용 격리 테스트 DB"""
    exams = [
        {"id": "[고3-2025년-06월]", "grade": "고3", "year": 2025, "month": 6, "exam_type": "평가원", "reading_start_q": 18, "reading_end_q": 45},
        {"id": "[고2-2024년-09월]", "grade": "고2", "year": 2024, "month": 9, "exam_type": "교육청", "reading_start_q": 18, "reading_end_q": 45},
        {"id": "[고3-2023년-11월]", "grade": "고3", "year": 2023, "month": 11, "exam_type": "평가원", "reading_start_q": 18, "reading_end_q": 45},
    ]
    for ex in exams:
        tmp_db.save_exam(ex)

    passages = [
        {
            "id": "[고3-2025년-06월-31번]",
            "exam_id": "[고3-2025년-06월]",
            "q_num": 31,
            "question_title": "31. 다음 빈칸에 들어갈 말로 가장 적절한 것은?",
            "question_type": "빈칸",
            "passage_text": (
                "31. 다음 빈칸에 들어갈 말로 가장 적절한 것은? [3점]\n\n"
                "Human geography is becoming unclear as people move rapidly across borders. "
                "We are experiencing a phase shift when matter transitions from solid to liquid in quantum physics. "
                "Ancient medieval squares in Marrakesh and Siena remain vibrant city square markets today.\n"
                "① static\t② dynamic\t③ silent\t④ isolated\t⑤ rigid\n"
                "* vibrant: 활기찬"
            ),
            "answer_text": "②",
            "explanation_text": "[정답] ②\n[해설] 도시 광장과 인간 지리의 변화",
            "pdf_crop_image": "",
            "validation_ratio": 1.0,
            "remarks": "",
            "correct_rate": 45.2,
            "choice_rates": None,
            "area": "reading",
        },
        {
            "id": "[고2-2024년-09월-33번]",
            "exam_id": "[고2-2024년-09월]",
            "q_num": 33,
            "question_title": "33. 다음 글의 주제로 가장 적절한 것은?",
            "question_type": "글의주제",
            "passage_text": (
                "33. 다음 글의 주제로 가장 적절한 것은?\n\n"
                "One of the most common claims in economics is that on the other hand, "
                "the above graph shows rising productivity. In order to improve cognitive bias research, "
                "psychologists examine memory retention in laboratory conditions.\n"
                "① cognitive bias\t② economic cycle\t③ productivity\t④ memory loss\t⑤ climate"
            ),
            "answer_text": "①",
            "explanation_text": "[정답] ①",
            "pdf_crop_image": "",
            "validation_ratio": 1.0,
            "remarks": "",
            "correct_rate": 62.0,
            "choice_rates": None,
            "area": "reading",
        },
        {
            "id": "[고3-2023년-11월-36번]",
            "exam_id": "[고3-2023년-11월]",
            "q_num": 36,
            "question_title": "36. 주어진 글 다음에 이어질 글의 순서로 가장 적절한 것은?",
            "question_type": "글의순서",
            "passage_text": (
                "36. 주어진 글 다음에 이어질 글의 순서로 가장 적절한 것은?\n\n"
                "During the Industrial Revolution, steam engines transformed factory manufacturing across Europe. "
                "(A) Engineers calibrated coal boilers carefully. "
                "(B) Textile mills expanded rapidly along rivers. "
                "(C) Consequently, urban populations doubled within decades.\n"
                "① (A)-(C)-(B)\t② (B)-(A)-(C)\t③ (C)-(A)-(B)\t④ (A)-(B)-(C)\t⑤ (B)-(C)-(A)"
            ),
            "answer_text": "②",
            "explanation_text": "[정답] ②",
            "pdf_crop_image": "",
            "validation_ratio": 1.0,
            "remarks": "",
            "correct_rate": 51.5,
            "choice_rates": None,
            "area": "reading",
        },
        {
            "id": "[고3-2025년-06월-41번]",
            "exam_id": "[고3-2025년-06월]",
            "q_num": 41,
            "question_title": "41. [41~42] 다음 글을 읽고, 물음에 답하시오.",
            "question_type": "1지문2문항",
            "passage_text": (
                "41. [41~42] 다음 글을 읽고 물음에 답하시오.\n\n"
                "Scientists at NASA discovered microbial fossils preserved inside Martian meteorites. "
                "Astrobiology researchers examine extreme habitats on Earth to understand planetary survival.\n"
                "① Mars exploration\t② Ocean tides\t③ Solar wind\t④ Lunar dust\t⑤ Comet orbit"
            ),
            "answer_text": "①",
            "explanation_text": "[정답] ①",
            "pdf_crop_image": "",
            "validation_ratio": 1.0,
            "remarks": "",
            "correct_rate": 58.0,
            "choice_rates": None,
            "area": "reading",
        },
        {
            "id": "[고3-2025년-06월-42번]",
            "exam_id": "[고3-2025년-06월]",
            "q_num": 42,
            "question_title": "42. 밑줄 친 (a)~(e) 중에서 문맥상 낱말의 쓰임이 적절하지 않은 것은?",
            "question_type": "1지문2문항",
            "passage_text": (
                "42. 밑줄 친 (a)~(e) 중에서 문맥상 낱말의 쓰임이 적절하지 않은 것은?\n\n"
                "Scientists at NASA discovered microbial fossils preserved inside Martian meteorites. "
                "Astrobiology researchers examine extreme habitats on Earth to understand planetary survival.\n"
                "① (a)\t② (b)\t③ (c)\t④ (d)\t⑤ (e)"
            ),
            "answer_text": "③",
            "explanation_text": "[정답] ③",
            "pdf_crop_image": "",
            "validation_ratio": 1.0,
            "remarks": "",
            "correct_rate": 49.0,
            "choice_rates": None,
            "area": "reading",
        },
        {
            "id": "[고3-2025년-06월-05번]",
            "exam_id": "[고3-2025년-06월]",
            "q_num": 5,
            "question_title": "5. 대화를 듣고, 두 사람이 만나기로 한 시각을 고르시오.",
            "question_type": "할 일",
            "passage_text": "5. 대화를 듣고 고르시오.\n① 2 p.m.\t② 3 p.m.",
            "script_text": (
                "M: Good morning, Ms. Carter. Did you reserve the botanical garden tour in Kyoto?\n"
                "W: Yes, our botany club arrives at the Kyoto station at three o'clock."
            ),
            "answer_text": "②",
            "explanation_text": "[정답] ②",
            "pdf_crop_image": "",
            "validation_ratio": 1.0,
            "remarks": "",
            "correct_rate": None,
            "choice_rates": None,
            "area": "listening",
        },
    ]

    for p in passages:
        tmp_db.save_passage(p)
    tmp_db.add_passage_tag("[고3-2025년-06월-31번]", "도시공간")
    similarity_search.invalidate_similarity_index()
    return tmp_db


def test_clean_and_segment_removes_choices_korean_and_markers():
    """선지(①~⑤), 한글 발문, 각주, (A)/(B)/(C) 표식이 제거되어 가짜 a b c 구문이 차단되는지 검증"""
    raw = (
        "36. 다음 글의 순서로 가장 적절한 것은? [3점]\n\n"
        "Dr. Smith visited U.S. labs. "
        "(A) First sample arrived. (B) Second test failed. (C) Third trial succeeded.\n"
        "① (A)-(B)-(C)\t② (B)-(A)-(C)\n"
        "* sample: 표본"
    )
    cleaned = similarity_search.clean_passage_for_similarity(raw, area="reading")
    assert "적절한" not in cleaned
    assert "①" not in cleaned
    assert "표본" not in cleaned

    segs = similarity_search.split_clean_segments(raw, area="reading")
    all_ng3 = similarity_search.extract_consecutive_ngrams(segs, 3)
    assert "a b c" not in all_ng3
    assert "dr smith visited" in all_ng3        # Dr. 약어 보호로 문장이 분리되지 않음
    assert "labs first sample" not in all_ng3   # 마침표와 (A) 경계로 세그먼트 분리됨


def test_extract_proper_nouns_and_phrases(sim_db):
    """고유명사(문장 중 대문자, 복합 고유명사, 약어)와 핵심 표현(2~3gram) 추출 검증"""
    text = (
        "However, ancient squares in Marrakesh and Siena inspired city planners. "
        "During the Industrial Revolution, NASA scientists studied atmospheric gases in 1980s."
    )
    features = similarity_search.extract_paragraph_features(text, area="reading")
    entity_terms = {e["term"].lower() for e in features["proper_nouns"]}

    assert "marrakesh" in entity_terms
    assert "siena" in entity_terms
    assert "industrial revolution" in entity_terms
    assert "nasa" in entity_terms
    assert "1980s" in entity_terms
    assert "however" not in entity_terms

    phrase_terms = {p["term"] for p in features["phrases"]}
    assert "city planners" in phrase_terms or "atmospheric gases" in phrase_terms


def test_common_ngram_noise_filtering(sim_db):
    """상투 구문(one of the, on the other hand, the above graph shows)이 2중 필터에서 제외되고 토글 시 복원됨"""
    text = (
        "One of the most interesting facts is that on the other hand, "
        "the above graph shows cognitive bias in laboratory conditions."
    )
    filtered_res = similarity_search.extract_paragraph_features(
        text, area="reading", filter_common_ngrams=True, max_df_3gram=30, max_df_4gram=10
    )
    ng3_terms = {g["term"] for g in filtered_res["ngrams_3"]}
    ng4_terms = {g["term"] for g in filtered_res["ngrams_4"]}
    assert "one of the" not in ng3_terms
    assert "on the other hand" not in ng4_terms
    assert "the above graph shows" not in ng4_terms
    assert "cognitive bias in" in ng3_terms or "bias in laboratory conditions" in ng4_terms

    unfiltered_res = similarity_search.extract_paragraph_features(
        text, area="reading", filter_common_ngrams=False
    )
    # 내용어 규칙 통과분 중 DF 무제한에서도 상투어(content 없는 'one of the' 제외, 'the above graph shows' 등)는 DF 필터 off 시 통과
    all_raw = similarity_search.extract_consecutive_ngrams(
        similarity_search.split_clean_segments(text, area="reading"), 4
    )
    assert "on the other hand" in all_raw
    assert unfiltered_res["filtered_common_count"] <= filtered_res["filtered_common_count"]


def test_similar_search_presets_and_ngram_ranking(sim_db):
    """종합/고유명사/연속3단어/연속4단어/3+4단어 프리셋별로 정확한 지문이 1위로 랭킹됨"""
    # 1. 변형 단락으로 연속 4단어 / 원문 변형 탐색
    excerpt = (
        "When matter transitions from solid to liquid, human geography becomes unclear. "
        "Markets in Marrakesh and Siena remain vibrant city square hubs."
    )
    for preset in ("balanced", "near_duplicate", "proper_noun", "ngram_4", "ngram_3", "ngram_3_4"):
        res = similarity_search.search_similar_passages(text=excerpt, preset=preset, area="reading")
        assert res["count"] >= 1, f"preset={preset} returned 0 results"
        top = res["items"][0]
        assert top["id"] == "[고3-2025년-06월-31번]", f"preset={preset} top was {top['id']}"
        if preset in ("ngram_4", "ngram_3_4"):
            assert len(top["matched_ngrams_4"]) >= 1
            assert "matter transitions from solid" in top["matched_ngrams_4"]


def test_required_excluded_terms_and_min_ngram_hits(sim_db):
    """필수 포함(required_terms), 제외(excluded_terms), 최소 일치 구문 수(min_ngram_hits) 동작 검증"""
    text = (
        "Human geography is becoming unclear. "
        "We are experiencing a phase shift when matter transitions from solid to liquid."
    )
    # 최소 일치 수 2개 이상 요구 -> 31번은 2개 이상이라 통과
    res_ok = similarity_search.search_similar_passages(
        text=text, preset="ngram_4", min_ngram_hits=2, area="reading"
    )
    assert [it["id"] for it in res_ok["items"]] == ["[고3-2025년-06월-31번]"]

    # 존재하지 않는 필수어 지정 시 결과 0건
    res_req = similarity_search.search_similar_passages(
        text=text, preset="balanced", required_terms=["nonexistent_unicorn"], area="reading"
    )
    assert res_req["count"] == 0

    # 핵심 구문을 제외(excluded_terms)로 뺀 경우 해당 4-gram은 매칭에서 빠짐
    res_excl = similarity_search.search_similar_passages(
        text=text,
        preset="ngram_4",
        excluded_terms=["matter transitions from solid", "transitions from solid to", "from solid to liquid"],
        area="reading",
    )
    if res_excl["items"]:
        assert "matter transitions from solid" not in res_excl["items"][0]["matched_ngrams_4"]


def test_allow_gap_modified_phrase(sim_db):
    """allow_gap=1 설정 시 중간에 1단어가 삽입된 변형 문장도 연속 3단어 기준으로 포착됨"""
    # 원문 36번: "steam engines transformed factory manufacturing"
    # 변형 쿼리: "steam engines rapidly transformed factory" (4단어 'steam engines transformed factory' 사이에 'rapidly' 없음 -> 반대로 쿼리가 원문 일부 생략 혹은 삽입)
    # 여기서는 원문에 "urban populations doubled within decades"가 있고, 쿼리는 "urban populations within decades"
    modified_query = "urban populations within decades transformed europe."
    res_exact = similarity_search.search_similar_passages(
        text=modified_query, preset="ngram_4", allow_gap=0, area="reading"
    )
    assert res_exact["count"] == 0

    res_gap = similarity_search.search_similar_passages(
        text=modified_query, preset="ngram_4", allow_gap=1, area="reading"
    )
    assert res_gap["count"] >= 1
    assert res_gap["items"][0]["id"] == "[고3-2023년-11월-36번]"


def test_merge_overlapping_spans():
    """인접·중첩 일치한 3·4단어 구문이 단일 연속 스팬으로 병합됨 검증"""
    text = "We are experiencing a phase shift when matter transitions from solid to liquid in physics."
    merged = similarity_search.merge_overlapping_spans(
        text,
        ["matter transitions from solid", "transitions from solid to", "from solid to liquid"],
    )
    assert len(merged) == 1
    assert merged[0].lower() == "matter transitions from solid to liquid"


def test_composite_passage_dedup_and_listening_area(sim_db):
    """41~42번 복합 장문 중복 제거 및 듣기 영역 대본 검색 검증"""
    nasa_query = "Scientists at NASA discovered microbial fossils preserved inside Martian meteorites."
    res = similarity_search.search_similar_passages(text=nasa_query, preset="proper_noun", area="reading")
    ids = [it["id"] for it in res["items"]]
    # 41번과 42번이 같은 지문을 공유하므로 1건만 노출
    assert sum(1 for pid in ids if pid.endswith("41번]") or pid.endswith("42번]")) == 1

    listen_query = "Our botany club arrives at the Kyoto station for the botanical garden tour."
    res_l = similarity_search.search_similar_passages(text=listen_query, preset="balanced", area="listening")
    assert res_l["count"] == 1
    assert res_l["items"][0]["id"] == "[고3-2025년-06월-05번]"


def test_access_role_filtering(sim_db):
    """guest 등급일 때 메타 필터(tag/correct_rate_range) 무시 및 메타 필드 제거 검증"""
    query = "Ancient medieval squares in Marrakesh and Siena remain vibrant."
    res_guest = similarity_search.search_similar_passages(
        text=query,
        preset="balanced",
        tag="존재하지않는태그",
        user_role=access.ROLE_GUEST,
        area="reading",
    )
    assert res_guest["count"] >= 1
    first = res_guest["items"][0]
    assert "correct_rate" not in first
    assert "tags" not in first


def test_api_similar_extract_and_search_endpoints(isolated_client, sim_db):
    """POST /api/search/similar/extract 및 POST /api/search/similar 엔드포인트 스모크 테스트"""
    bad_ext = isolated_client.post("/api/search/similar/extract", json={"text": "hi"})
    assert bad_ext.status_code == 400

    bad_search = isolated_client.post("/api/search/similar", json={"text": "   "})
    assert bad_search.status_code == 400

    paragraph = (
        "Human geography is becoming unclear. "
        "We are experiencing a phase shift when matter transitions from solid to liquid in Marrakesh."
    )
    ext_resp = isolated_client.post("/api/search/similar/extract", json={"text": paragraph, "area": "reading"})
    assert ext_resp.status_code == 200
    ext_data = ext_resp.json()
    assert ext_data["word_count"] > 10
    assert any(x["term"] == "Marrakesh" for x in ext_data["proper_nouns"])
    assert len(ext_data["ngrams_4"]) >= 1

    srch_resp = isolated_client.post(
        "/api/search/similar",
        json={"text": paragraph, "preset": "ngram_3_4", "area": "reading", "top_k": 10},
    )
    assert srch_resp.status_code == 200
    srch_data = srch_resp.json()
    assert srch_data["count"] >= 1
    assert srch_data["items"][0]["id"] == "[고3-2025년-06월-31번]"
    assert srch_data["items"][0]["similarity_score"] > 0
