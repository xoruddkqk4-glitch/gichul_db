"""
05-gichul_db: 정교한 영어 문장 분할 모듈 (sentence_tokenizer.py)
- 약어(e.g., i.e., etc., U.S., Dr., Mr.), 소수점, 인용부호 예외를 완벽 처리
- 문장 번호 부여 및 [O학년-OOOO년-OO월-OO번-O번째 문장] 규격 식별자 생성
"""

import re
from typing import List, Dict

# 보호해야 할 일반 약어 목록 (소문자 기준)
ABBREVIATIONS = {
    "mr", "mrs", "ms", "dr", "prof", "sr", "jr", "gen", "col", "capt",
    "e.g", "i.e", "etc", "vs", "v", "al", "approx", "dept", "corp", "inc", "ltd",
    "no", "fig", "vol", "p", "pp", "est", "min", "max",
    "jan", "feb", "mar", "apr", "jun", "jul", "aug", "sep", "sept", "oct", "nov", "dec",
    "mon", "tue", "wed", "thu", "fri", "sat", "sun"
}

# 국가 및 지역 약어
GEO_ABBREVIATIONS = {"u.s", "u.k", "u.n", "e.u", "d.c", "n.y", "l.a"}


def split_sentences(text: str) -> List[str]:
    """
    영어 지문 텍스트를 문장 단위로 정확하게 분할
    """
    if not text or not text.strip():
        return []

    # 1. 공백 및 줄바꿈 정규화 (지문 내 단락 줄바꿈을 공백 하나로 변환하되 가독성 유지)
    cleaned = re.sub(r"[ \t]+", " ", text).strip()
    cleaned = re.sub(r"\r\n|\r|\n", " ", cleaned)

    # 2. 임시 토큰 치환을 통한 마침표 보호
    # 2-1. 소수점 보호 (예: 3.14 -> 3<PERIOD>14)
    protected = re.sub(r"(\d+)\.(\d+)", r"\1<PERIOD>\2", cleaned)

    # 2-2. 약어 및 국가 약어 보호 (e.g., i.e., U.S., Dr., Mr. 등)
    abbr_pattern = (
        r"\b(mr|mrs|ms|dr|prof|sr|jr|gen|col|capt|"
        r"e\.g|i\.e|etc|vs|al|approx|dept|corp|inc|ltd|"
        r"no|fig|vol|pp|est|min|max|"
        r"u\.s|u\.k|u\.n|e\.u|d\.c|n\.y|l\.a)\."
    )
    protected = re.sub(
        abbr_pattern,
        lambda m: m.group(0).replace(".", "<PERIOD>"),
        protected,
        flags=re.IGNORECASE
    )

    # 단일 알파벳 약어/이니셜 (예: p. 12, J. K. Rowling)
    protected = re.sub(r"\b([A-Za-z])\.\s+", r"\1<PERIOD> ", protected)

    # 2-3. 말줄임표 보호 (...)
    protected = re.sub(r"\.{2,}", "<ELLIPSIS>", protected)

    # 3. 문장 종결 패턴 분할
    # 마침표, 물음표, 느낌표 뒤에 닫는 따옴표/괄호가 올 수 있고, 그 뒤에 공백 및 대문자(또는 따옴표로 시작하는 대문자)가 올 때 분할
    pattern = r"([.?!][\"'”’)]?)\s+(?=[A-Z\"'“‘(0-9])"
    splits = re.split(pattern, protected)

    # re.split으로 쪼개진 종결부호와 본문 합치기
    raw_sentences = []
    i = 0
    while i < len(splits):
        sent = splits[i]
        if i + 1 < len(splits) and re.match(r"^[.?!][\"'”’)]?$", splits[i + 1]):
            sent += splits[i + 1]
            i += 2
        else:
            i += 1
        sent = sent.strip()
        if sent:
            raw_sentences.append(sent)

    # 4. 보호된 토큰 복원
    final_sentences = []
    for s in raw_sentences:
        s = s.replace("<PERIOD>", ".")
        s = s.replace("<ELLIPSIS>", "...")
        s = s.strip()
        if s:
            final_sentences.append(s)

    return final_sentences


def create_sentence_records(passage_id: str, passage_text: str) -> List[Dict]:
    """
    지문 ID([고3-2024년-06월-21번])와 텍스트를 받아
    각 문장에 [고3-2024년-06월-21번-1번째 문장] 형태의 식별자를 부여한 레코드 목록 생성
    """
    sentence_strings = split_sentences(passage_text)
    records = []

    for idx, sent_text in enumerate(sentence_strings, 1):
        # 식별자: [고3-2024년-06월-21번-1번째 문장]
        # passage_id가 대괄호로 둘러싸여 있을 경우와 아닐 경우 유연 처리
        base_id = passage_id.strip("[]")
        sent_id = f"[{base_id}-{idx}번째 문장]"

        # 단어 수 계산
        words = re.findall(r"\b[\w'-]+\b", sent_text)
        word_count = len(words)

        records.append({
            "id": sent_id,
            "passage_id": passage_id if passage_id.startswith("[") else f"[{passage_id}]",
            "order_index": idx,
            "sentence_text": sent_text,
            "word_count": word_count,
            "remarks": ""
        })

    return records
