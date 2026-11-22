"""
05-gichul_db: 단락 기반 다중 기준 유사 지문 검색 엔진 (gichul/services/similarity_search.py)

주요 기능:
1. 순수 영문 본문 정제 및 문장·절 경계 분리 (발문/선지/각주/화자태그/표식 노이즈 차단)
2. 4대 검색 시그널 자동 추출:
   - 고유명사·개체명 (문장 중 대문자, 복합 고유명사, 올캡 약어, 연도/세기)
   - 핵심 표현·연어 조합 (내용어 2-gram, 내용어+전치사+내용어 3-gram)
   - 핵심 내용어 (TF-IDF + 경량 어간 정규화)
   - 연속 3단어·4단어 구문 (3-gram / 4-gram, 2중 상투어 필터 및 FTS5 Phrase/NEAR 하이브리드 회수)
3. 8대 검색 기준 프리셋 (5대 다중 시그널 프리셋 + 3대 연속 N-gram 전용 프리셋) 및 커스텀 가중치 스코어링
4. 필수 포함/제외 칩 필터, 선택적 AI 의미 키워드 확장, 복합 장문(41~42/43~45) 병합 및 겹침 구문 스팬 병합
"""

import math
import re
import sqlite3
import threading
import time
from collections import Counter, defaultdict
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

from .. import access
from .. import database as db
from ..fels_engine import FUNCTION_WORDS
from ..logging_config import get_logger

logger = get_logger("gichul.services.similarity_search")

# =====================================================================
# 1. 프리셋, 불용어 및 도메인 상수
# =====================================================================

SIMILARITY_PRESETS: Dict[str, Dict[str, float]] = {
    "balanced": {"keyword": 0.40, "phrase": 0.30, "proper_noun": 0.20, "shingle": 0.10},
    "near_duplicate": {"keyword": 0.25, "phrase": 0.25, "proper_noun": 0.15, "shingle": 0.35},
    "proper_noun": {"keyword": 0.25, "phrase": 0.15, "proper_noun": 0.55, "shingle": 0.05},
    "phrase_combo": {"keyword": 0.30, "phrase": 0.55, "proper_noun": 0.10, "shingle": 0.05},
    "topic_broad": {"keyword": 0.65, "phrase": 0.20, "proper_noun": 0.10, "shingle": 0.05},
    "ngram_3": {"keyword": 0.0, "phrase": 0.0, "proper_noun": 0.0, "shingle": 1.0},
    "ngram_4": {"keyword": 0.0, "phrase": 0.0, "proper_noun": 0.0, "shingle": 1.0},
    "ngram_3_4": {"keyword": 0.0, "phrase": 0.0, "proper_noun": 0.0, "shingle": 1.0},
}

NGRAM_ONLY_PRESETS = {"ngram_3", "ngram_4", "ngram_3_4"}

_GENERAL_STOP_WORDS: Set[str] = {
    "about", "above", "across", "after", "again", "against", "almost", "alone", "along",
    "already", "also", "although", "always", "among", "another", "any", "anyone", "anything",
    "around", "away", "back", "based", "because", "become", "became", "becomes", "becoming",
    "before", "behind", "below", "between", "beyond", "blank", "both", "but", "came", "can",
    "cannot", "case", "cases", "chart", "come", "comes", "coming", "could", "day", "days",
    "did", "does", "doing", "done", "down", "during", "each", "either", "else", "end",
    "enough", "even", "ever", "every", "everyone", "everything", "example", "fact", "far",
    "few", "find", "finds", "finding", "first", "following", "found", "from", "further",
    "furthermore", "gave", "get", "gets", "getting", "give", "given", "gives", "giving",
    "goes", "going", "gone", "good", "got", "graph", "great", "had", "hand", "has", "have",
    "having", "here", "high", "higher", "highest", "however", "indeed", "instead", "into",
    "its", "just", "keep", "kept", "knew", "know", "known", "knows", "large", "larger",
    "last", "later", "least", "less", "let", "life", "like", "likely", "little", "long",
    "longer", "look", "looked", "looking", "looks", "lot", "lots", "made", "make", "makes",
    "making", "many", "may", "mean", "means", "might", "more", "moreover", "most", "mostly",
    "much", "must", "near", "need", "needs", "neither", "never", "new", "next", "none",
    "nor", "not", "nothing", "now", "number", "numbers", "often", "old", "once", "one",
    "ones", "only", "onto", "order", "other", "others", "otherwise", "out", "outside",
    "over", "own", "part", "parts", "passage", "people", "percent", "percentage", "perhaps",
    "person", "persons", "place", "places", "point", "points", "possible", "put", "quite",
    "rather", "really", "result", "results", "said", "same", "saw", "say", "says", "saying",
    "second", "see", "seem", "seemed", "seems", "seen", "sees", "several", "shall", "should",
    "show", "showed", "shown", "shows", "since", "small", "smaller", "some", "someone",
    "something", "sometimes", "soon", "still", "such", "table", "take", "taken", "takes",
    "taking", "tell", "telling", "tells", "than", "that", "their", "them", "then", "there",
    "therefore", "these", "they", "thing", "things", "think", "thinking", "thinks", "third",
    "this", "those", "though", "thought", "three", "through", "throughout", "thus", "time",
    "times", "today", "together", "told", "too", "took", "toward", "towards", "two",
    "under", "unless", "until", "upon", "use", "used", "uses", "using", "usually", "very",
    "want", "wanted", "wants", "way", "ways", "well", "went", "were", "what", "whatever",
    "when", "whenever", "where", "whereas", "wherever", "whether", "which", "while", "who",
    "whom", "whose", "why", "will", "with", "within", "without", "work", "worked", "working",
    "works", "world", "would", "year", "years", "yet",
}

STOP_WORDS: Set[str] = {w.lower() for w in FUNCTION_WORDS} | _GENERAL_STOP_WORDS

SENTENCE_START_COMMON_CAPS: Set[str] = STOP_WORDS | {
    "actually", "additionally", "afterwards", "alternatively", "apparently", "accordingly",
    "basically", "briefly", "certainly", "clearly", "consequently", "conversely", "currently",
    "despite", "eventually", "evidently", "finally", "fortunately", "generally", "hence",
    "historically", "imagine", "importantly", "increasingly", "initially", "interestingly",
    "lately", "likewise", "meanwhile", "merely", "naturally", "nevertheless", "nonetheless",
    "normally", "notably", "obviously", "occasionally", "originally", "overall", "particularly",
    "personally", "practically", "presumably", "previously", "primarily", "probably", "recently",
    "regardless", "remarkably", "sadly", "secondly", "similarly", "simply", "specifically",
    "strangely", "subsequently", "suddenly", "supposedly", "surprisingly", "thankfully",
    "theoretically", "thirdly", "traditionally", "truly", "typically", "ultimately", "undoubtedly",
    "unfortunately", "unlike", "virtually", "yes", "no", "dear", "hello", "hi", "welcome",
    "please", "remember", "consider", "suppose", "notice", "attention", "everyone",
}

PHRASE_LINK_PREPS: Set[str] = {
    "of", "in", "to", "for", "with", "on", "from", "by", "at", "as", "into", "over", "between",
    "through", "about",
}

COMMON_4GRAM_LOW_INFO_CONTENT: Set[str] = {
    "hand", "time", "most", "end", "rest", "graph", "chart", "shows", "show", "above",
    "fact", "way", "order", "part", "case", "same", "other", "first", "second", "number",
    "percent", "result", "example", "addition", "contrast", "table", "figure", "study",
    "research", "people", "world", "life", "thing", "things", "point",
}

_ABBR_RE = re.compile(
    r"\b(Mr|Mrs|Ms|Dr|Prof|Sr|Jr|St|No|vs|etc|e\.g|i\.e|U\.S|U\.K|A\.M|P\.M)\.",
    re.IGNORECASE,
)
_SPEAKER_TAG_RE = re.compile(
    r"(?im)^\s*(?:[MW]\d*|Man|Woman|Boy|Girl|Male|Female|Teacher|Student|Host|Speaker|"
    r"Doctor|Patient|Clerk|Officer|Interviewer|Interviewee|남|여)\d*\s*[:：]\s*"
)
_Q_HEADER_RE = re.compile(r"^\s*\d{1,2}\s*[\.\)]\s*(?:\[\s*\d{1,2}\s*[~∼\-]\s*\d{1,2}\s*\]\s*)?")
_BRACKET_RANGE_RE = re.compile(r"\[\s*\d{1,2}\s*(?:[~∼\-]\s*\d{1,2}|점)\s*\]")
_FOOTNOTE_LINE_RE = re.compile(r"(?m)^\s*\*+.*$")
_MARKER_BOUNDARY_RE = re.compile(
    r"(?:\(\s*[A-Ea-e1-5]\s*\)|\[\s*[A-Ea-e]\s*\]|[①②③④⑤]|_{2,}|—{2,}|\[빈칸\]|\(빈칸\)|\[밑줄\]|\(밑줄\))"
)
_CHOICE_CUTOFF_RE = re.compile(r"(?:^|\n|\s)①\s*")
_WORD_LOWER_RE = re.compile(r"[a-z]+(?:'[a-z]+)?")
_PROPER_UPPER_SEQ_RE = re.compile(
    r"\b([A-Z][a-zA-Z0-9'-]*(?:\s+(?:(?:of|the|and|for|in|on|at|de|la|van|von)\s+)?[A-Z][a-zA-Z0-9'-]*)+)\b"
)
_SINGLE_CAP_RE = re.compile(r"\b([A-Z][a-zA-Z'-]{1,}|[A-Z]{2,6})\b")
_YEAR_CENTURY_RE = re.compile(r"\b(?:(?:1[4-9]\d{2}|20\d{2})s?|\d{1,2}(?:st|nd|rd|th)\s+century)\b", re.IGNORECASE)

_IRREGULAR_LEMMAS: Dict[str, str] = {
    "children": "child", "men": "man", "women": "woman", "people": "person",
    "mice": "mouse", "teeth": "tooth", "feet": "foot", "geese": "goose",
    "studies": "study", "studied": "study", "studying": "study",
    "cities": "city", "societies": "society", "countries": "country",
    "stories": "story", "theories": "theory", "bodies": "body",
    "tried": "try", "tries": "try", "trying": "try",
    "carried": "carry", "carries": "carry", "carrying": "carry",
    "better": "good", "best": "good", "worse": "bad", "worst": "bad",
    "less": "little", "least": "little", "more": "much", "most": "much",
    "went": "go", "gone": "go", "saw": "see", "seen": "see",
    "took": "take", "taken": "take", "made": "make", "found": "find",
    "gave": "give", "given": "give", "knew": "know", "known": "know",
    "thought": "think", "brought": "bring", "taught": "teach", "caught": "catch",
    "wrote": "write", "written": "write", "spoke": "speak", "spoken": "speak",
    "broke": "break", "broken": "break", "chose": "choose", "chosen": "choose",
    "grew": "grow", "grown": "grow", "felt": "feel", "kept": "keep",
    "built": "build", "spent": "spend", "sent": "send", "lost": "lose",
    "held": "hold", "led": "lead", "read": "read", "understood": "understand",
    "became": "become", "ran": "run", "began": "begin", "begun": "begin",
    "driven": "drive", "drove": "drive", "fallen": "fall", "fell": "fall",
}

# =====================================================================
# 2. 텍스트 정제, 경계 분할 및 경량 어간 정규화
# =====================================================================


def normalize_lemma(word: str) -> str:
    """외부 NLP 패키지 없이 영어 단어의 굴절(복수/시제/분사/소유격)을 경량 정규화."""
    w = (word or "").strip().lower().replace("’", "'")
    if not w:
        return ""
    if w.endswith("'s"):
        w = w[:-2]
    elif w.endswith("'"):
        w = w[:-1]
    if not w:
        return ""
    if w in _IRREGULAR_LEMMAS:
        return _IRREGULAR_LEMMAS[w]
    if len(w) <= 3:
        return w

    # 복수/3인칭 단수
    if w.endswith("ies") and len(w) > 4:
        return w[:-3] + "y"
    if w.endswith("ied") and len(w) > 4:
        return w[:-3] + "y"
    if w.endswith("ing") and len(w) > 5:
        stem = w[:-3]
        if len(stem) >= 3 and stem[-1] == stem[-2] and stem[-1] not in ("s", "l", "z"):
            stem = stem[:-1]
        return stem
    if w.endswith("ed") and len(w) > 4:
        stem = w[:-2]
        if len(stem) >= 3 and stem[-1] == stem[-2] and stem[-1] not in ("s", "l", "z"):
            stem = stem[:-1]
        return stem
    if re.search(r"(?:sh|ch|x|z|ss)es$", w) and len(w) > 4:
        return w[:-2]
    if w.endswith("s") and not w.endswith(("ss", "us", "is", "as")) and len(w) > 3:
        return w[:-1]
    return w


def clean_passage_for_similarity(
    text: str,
    area: str = "reading",
    script_text: Optional[str] = None,
    preserve_case: bool = True,
) -> str:
    """발문·선지·각주·한글 지시문·화자 태그·표식을 제거해 순수 영문 본문만 추출한다."""
    raw = ""
    if area == "listening" and (script_text or "").strip():
        raw = script_text or ""
    else:
        raw = text or ""
        if not raw.strip() and script_text:
            raw = script_text

    if not raw:
        return ""

    s = raw.replace("\u00ad", "").replace("\u200b", "").replace("\ufeff", "")
    s = s.replace("“", '"').replace("”", '"').replace("‘", "'").replace("’", "'")

    if area == "listening":
        s = _SPEAKER_TAG_RE.sub("", s)
    else:
        # 선지 영역(① 이후) 절단 — 단, 문장 맨 처음이 아닌 본문 뒤쪽 선택지 영역 대상
        m_choice = _CHOICE_CUTOFF_RE.search(s)
        if m_choice and m_choice.start() > 15:
            s = s[:m_choice.start()]
        s = _Q_HEADER_RE.sub("", s)
        s = _BRACKET_RANGE_RE.sub(" | ", s)
        s = _FOOTNOTE_LINE_RE.sub(" ", s)
        # 한글 지시문/발문 조각은 문장 경계 구분자로 치환
        s = re.sub(r"[가-힣]+", " | ", s)

    # 문단 표식 (A)~(E), (a)~(e), (1)~(5), 빈칸(____) -> 경계 구분자로 치환하여 'a b c' 가짜 구문 차단
    s = _MARKER_BOUNDARY_RE.sub(" | ", s)
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"(?:\s*\|\s*){2,}", " | ", s)
    s = s.strip(" |\r\n\t")
    return s if preserve_case else s.lower()


def _protect_abbreviations(text: str) -> str:
    t = re.sub(r"(\d)\.(\d)", r"\1<DOT>\2", text)
    t = _ABBR_RE.sub(lambda m: m.group(0).replace(".", "<DOT>"), t)
    t = re.sub(r"\b([A-Za-z])\.(?=\s+[A-Z])", r"\1<DOT>", t)
    return t


def split_clean_segments(
    text: str,
    area: str = "reading",
    script_text: Optional[str] = None,
    cleaned_override: Optional[str] = None,
) -> List[List[str]]:
    """정제된 영문 본문을 문장·절 경계로 나누고 각 세그먼트의 소문자 단어 토큰 목록을 반환한다."""
    cleaned = cleaned_override if cleaned_override is not None else clean_passage_for_similarity(
        text, area=area, script_text=script_text, preserve_case=True
    )
    if not cleaned:
        return []

    protected = _protect_abbreviations(cleaned)
    raw_segments = re.split(r"[.!?;|\r\n]+", protected)
    segments: List[List[str]] = []
    for seg in raw_segments:
        seg_clean = seg.replace("<DOT>", ".").strip()
        if not seg_clean:
            continue
        toks = _WORD_LOWER_RE.findall(seg_clean.lower())
        if toks:
            segments.append(toks)
    return segments


def extract_proper_nouns(
    cleaned_case_text: str,
    index_lemma_df: Optional[Dict[str, int]] = None,
    corpus_size: int = 0,
) -> List[str]:
    """대소문자를 보존한 정제 영문 텍스트에서 고유명사·복합개체명·약어·연도를 추출한다."""
    if not cleaned_case_text:
        return []

    protected = _protect_abbreviations(cleaned_case_text)
    sentences = [s.replace("<DOT>", ".").strip() for s in re.split(r"[.!?;|\r\n]+", protected) if s.strip()]

    mid_sentence_caps: Set[str] = set()
    candidates: List[str] = []

    # 1차 패스: 문장 중간에 대문자로 나타나는 단어 수집
    for sent in sentences:
        words = re.findall(r"[A-Za-z0-9'-]+", sent)
        for idx, w in enumerate(words):
            if idx > 0 and len(w) >= 2 and w[0].isupper():
                mid_sentence_caps.add(w.lower())

    # 2차 패스: 복합 고유명사, 문장 중 대문자, 약어, 연도/세기 추출
    for sent in sentences:
        # (A) 연속 대문자 복합 고유명사
        for m in _PROPER_UPPER_SEQ_RE.finditer(sent):
            phrase = m.group(1).strip()
            parts = phrase.split()
            # 문장 첫 단어가 일반 시작어("The United States", "When Darwin")면 앞 단어 벗김
            while parts and parts[0].lower() in SENTENCE_START_COMMON_CAPS:
                parts.pop(0)
            while parts and parts[-1].lower() in {"of", "the", "and", "for", "in", "on", "at"}:
                parts.pop()
            if len(parts) >= 2:
                candidates.append(" ".join(parts))
            elif len(parts) == 1 and parts[0][0].isupper():
                w = parts[0]
                if w.lower() not in SENTENCE_START_COMMON_CAPS:
                    candidates.append(w)

        # (B) 단일 대문자/약어
        sent_tokens = list(re.finditer(r"[A-Za-z][A-Za-z'-]*", sent))
        for idx, m in enumerate(sent_tokens):
            w = m.group(0)
            wl = w.lower()
            is_all_caps = len(w) >= 2 and len(w) <= 6 and w.isupper()
            if is_all_caps and wl not in {"i", "a", "am", "pm", "ok", "tv", "cd", "pc", "us", "uk"}:
                if wl not in STOP_WORDS:
                    candidates.append(w)
                continue
            if not w[0].isupper() or len(w) < 2:
                continue
            if wl in SENTENCE_START_COMMON_CAPS or wl in STOP_WORDS:
                continue
            if idx > 0:
                candidates.append(w)
            else:
                # 문장 첫 단어인 경우: 같은 단락 문장 중간에도 대문자로 등장했거나 대규모 코퍼스에서 극희소인 경우만 승격
                is_rare_in_large_corpus = bool(
                    index_lemma_df is not None
                    and corpus_size >= 200
                    and index_lemma_df.get(normalize_lemma(wl), 9999) <= 15
                )
                if wl in mid_sentence_caps or is_rare_in_large_corpus:
                    candidates.append(w)

        # (C) 연도 및 세기
        for m in _YEAR_CENTURY_RE.finditer(sent):
            candidates.append(m.group(0).strip())

    # 중복 제거 (대소문자 무시, 다어 구문 및 원형 표기 우선 유지)
    seen: Set[str] = set()
    unique: List[str] = []
    for c in candidates:
        key = c.lower()
        if key in seen:
            continue
        seen.add(key)
        unique.append(c)
    return unique


def extract_content_phrases(segments: List[List[str]]) -> List[str]:
    """각 세그먼트 내부에서 내용어 2-gram 및 (내용어+전치사+내용어) 3-gram 표현 조합을 추출한다."""
    seen: Set[str] = set()
    phrases: List[str] = []
    for seg in segments:
        n = len(seg)
        for i in range(n - 1):
            w1, w2 = seg[i], seg[i + 1]
            if len(w1) >= 3 and len(w2) >= 3 and w1 not in STOP_WORDS and w2 not in STOP_WORDS:
                p2 = f"{w1} {w2}"
                if p2 not in seen:
                    seen.add(p2)
                    phrases.append(p2)
            if i < n - 2:
                w3 = seg[i + 2]
                if (
                    len(w1) >= 3
                    and w2 in PHRASE_LINK_PREPS
                    and len(w3) >= 3
                    and w1 not in STOP_WORDS
                    and w3 not in STOP_WORDS
                ):
                    p3 = f"{w1} {w2} {w3}"
                    if p3 not in seen:
                        seen.add(p3)
                        phrases.append(p3)
    return phrases


def extract_consecutive_ngrams(segments: List[List[str]], n: int) -> List[str]:
    """문장·절 세그먼트 내부에서만 연속 n단어(n-gram) 구문을 추출한다 (순서 유지 중복 제거)."""
    if n <= 0:
        return []
    seen: Set[str] = set()
    out: List[str] = []
    for seg in segments:
        if len(seg) < n:
            continue
        for i in range(len(seg) - n + 1):
            gram = " ".join(seg[i : i + n])
            if gram not in seen:
                seen.add(gram)
                out.append(gram)
    return out


def is_informative_ngram(ngram: str, n: Optional[int] = None) -> bool:
    """연속 3·4단어 구문이 상투적 기능어 조합이 아닌 정보성 있는 표현인지 검사한다."""
    toks = ngram.strip().lower().split()
    effective_n = n or len(toks)
    if len(toks) < 2:
        return False
    content_tokens = [w for w in toks if len(w) >= 3 and w not in STOP_WORDS]
    if effective_n <= 3:
        return len(content_tokens) >= 1
    # 4단어 이상: 내용어 2개 이상 또는 내용어 1개라도 저정보 상투어가 아닐 것
    if len(content_tokens) >= 2:
        return True
    if len(content_tokens) == 1:
        return content_tokens[0] not in COMMON_4GRAM_LOW_INFO_CONTENT
    return False


# =====================================================================
# 3. 인메모리 경량 역색인 및 IDF 캐시 (_SimilarityIndex)
# =====================================================================


class _SimilarityIndex:
    """영역별(reading / listening) 경량 인메모리 역색인 및 TF-IDF/DF 캐시."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._built_db_path: Optional[str] = None
        self._by_area: Dict[str, Dict[str, Any]] = {}

    def invalidate(self) -> None:
        with self._lock:
            self._by_area.clear()
            self._built_db_path = None

    def get_area_index(self, area: str = "reading") -> Dict[str, Any]:
        norm_area = "listening" if area == "listening" else "reading"
        cur_db_path = db.get_db_path()
        with self._lock:
            if self._built_db_path != cur_db_path:
                self._by_area.clear()
                self._built_db_path = cur_db_path
            if norm_area not in self._by_area:
                self._by_area[norm_area] = self._build_area_index(norm_area)
            return self._by_area[norm_area]

    def _build_area_index(self, area: str) -> Dict[str, Any]:
        t0 = time.perf_counter()
        area_filter = "p.area = 'listening'" if area == "listening" else "(p.area = 'reading' OR p.area IS NULL)"
        query = f"""
            SELECT p.id, p.exam_id, p.q_num, p.area, p.question_type, p.correct_rate,
                   p.passage_text, p.script_text,
                   e.grade, e.year, e.month, e.exam_type
            FROM passages p
            JOIN exams e ON p.exam_id = e.id
            WHERE {area_filter}
        """
        with db.get_connection() as conn:
            rows = conn.execute(query).fetchall()

        docs: List[Dict[str, Any]] = []
        id_to_idx: Dict[str, int] = {}
        lemma_df: Counter = Counter()
        entity_df: Counter = Counter()
        phrase_df: Counter = Counter()
        inverted_lemma: Dict[str, Set[int]] = defaultdict(set)
        inverted_entity: Dict[str, Set[int]] = defaultdict(set)
        inverted_phrase: Dict[str, Set[int]] = defaultdict(set)

        for r in rows:
            raw_text = r["passage_text"] or ""
            raw_script = r["script_text"] or ""
            clean_text = clean_passage_for_similarity(
                raw_text, area=area, script_text=raw_script, preserve_case=True
            )
            segments = split_clean_segments(raw_text, area=area, script_text=raw_script, cleaned_override=clean_text)

            lemma_tf: Counter = Counter()
            all_lemmas: Set[str] = set()
            for seg in segments:
                for tok in seg:
                    lem = normalize_lemma(tok)
                    if not lem:
                        continue
                    all_lemmas.add(lem)
                    if tok not in STOP_WORDS and len(tok) >= 3:
                        lemma_tf[lem] += 1

            entities_raw = extract_proper_nouns(clean_text)
            entities_lower = {e.lower() for e in entities_raw}
            phrases_list = extract_content_phrases(segments)
            phrases_set = set(phrases_list)

            idx = len(docs)
            id_to_idx[r["id"]] = idx
            docs.append({
                "id": r["id"],
                "exam_id": r["exam_id"],
                "q_num": r["q_num"],
                "area": r["area"] or area,
                "question_type": r["question_type"] or "기타",
                "correct_rate": r["correct_rate"],
                "grade": r["grade"] or "",
                "year": r["year"] or 0,
                "month": r["month"] or 0,
                "exam_type": r["exam_type"] or "",
                "clean_text": clean_text,
                "segments": segments,
                "lemma_tf": lemma_tf,
                "all_lemmas": all_lemmas,
                "entities_lower": entities_lower,
                "phrases_set": phrases_set,
                "tfidf_norm": 1.0,
            })

            for lem in all_lemmas:
                inverted_lemma[lem].add(idx)
            for lem in lemma_tf.keys():
                lemma_df[lem] += 1
            for ent in entities_lower:
                entity_df[ent] += 1
                inverted_entity[ent].add(idx)
            for phr in phrases_set:
                phrase_df[phr] += 1
                inverted_phrase[phr].add(idx)

        n_docs = len(docs)
        lemma_idf: Dict[str, float] = {}
        for lem, df_val in lemma_df.items():
            lemma_idf[lem] = math.log((n_docs + 1.0) / (df_val + 1.0)) + 1.0

        for doc in docs:
            sq = 0.0
            for lem, cnt in doc["lemma_tf"].items():
                w = (1.0 + math.log(cnt)) * lemma_idf.get(lem, 1.0)
                sq += w * w
            doc["tfidf_norm"] = math.sqrt(sq) if sq > 0 else 1.0

        elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 1)
        logger.info("[SimilarityIndex] area=%s docs=%d built in %.1f ms", area, n_docs, elapsed_ms)

        return {
            "area": area,
            "n_docs": n_docs,
            "docs": docs,
            "id_to_idx": id_to_idx,
            "lemma_df": lemma_df,
            "lemma_idf": lemma_idf,
            "entity_df": entity_df,
            "phrase_df": phrase_df,
            "inverted_lemma": inverted_lemma,
            "inverted_entity": inverted_entity,
            "inverted_phrase": inverted_phrase,
        }


_similarity_index = _SimilarityIndex()


def invalidate_similarity_index() -> None:
    """DB 쓰기 작업 후 인메모리 유사도 인덱스를 무효화한다."""
    _similarity_index.invalidate()


# =====================================================================
# 4. N-gram 정밀 검증 및 FTS5/역색인 하이브리드 후보 회수
# =====================================================================


def _segments_match_ngram(segments: List[List[str]], gram_tokens: List[str], allow_gap: int = 0) -> bool:
    """세그먼트 목록에서 gram_tokens가 순서대로 연속(allow_gap=0) 또는 간격 허용으로 일치하는지 검사."""
    m = len(gram_tokens)
    if m == 0:
        return False
    first = gram_tokens[0]
    for seg in segments:
        seg_len = len(seg)
        if seg_len < m:
            continue
        if allow_gap <= 0:
            for i in range(seg_len - m + 1):
                if seg[i] == first and seg[i : i + m] == gram_tokens:
                    return True
        else:
            # 첫 토큰 위치에서 순서대로 각 인접 단어 사이 간격 <= allow_gap 검증
            for i in range(seg_len - m + 1):
                if seg[i] != first:
                    continue
                pos = i
                ok = True
                for nxt in gram_tokens[1:]:
                    limit = min(seg_len, pos + 1 + allow_gap + 1)
                    found = -1
                    for j in range(pos + 1, limit):
                        if seg[j] == nxt:
                            found = j
                            break
                    if found < 0:
                        ok = False
                        break
                    pos = found
                if ok:
                    return True
    return False


def _fts_phrase_candidates(ngrams: List[str], area: str, allow_gap: int = 0) -> Set[str]:
    """passages_fts의 Phrase 또는 NEAR 쿼리로 후보 passage_id를 1차 회수한다 (실패 시 빈 집합)."""
    if not ngrams:
        return set()
    col_prefix = "{passage_text script_text} : " if area == "listening" else "passage_text : "
    found_ids: Set[str] = set()
    batch_size = 20

    try:
        with db.get_connection() as conn:
            cursor = conn.cursor()
            for i in range(0, len(ngrams), batch_size):
                batch = ngrams[i : i + batch_size]
                clauses = []
                for g in batch:
                    toks = [re.sub(r"[^a-z0-9]", "", w) for w in g.lower().split()]
                    toks = [t for t in toks if t]
                    if len(toks) < 2:
                        continue
                    if allow_gap <= 0:
                        clauses.append('"' + " ".join(toks) + '"')
                    else:
                        quoted = " ".join(f'"{t}"' for t in toks)
                        clauses.append(f"NEAR({quoted}, {int(allow_gap)})")
                if not clauses:
                    continue
                fts_expr = col_prefix + "(" + " OR ".join(clauses) + ")"
                cursor.execute("SELECT passage_id FROM passages_fts WHERE passages_fts MATCH ?", (fts_expr,))
                for row in cursor.fetchall():
                    found_ids.add(row["passage_id"])
    except sqlite3.OperationalError as e:
        logger.debug("[Similarity FTS Ngram Fallback] %s", e)
        return set()
    except Exception as e:
        logger.debug("[Similarity FTS Ngram Error] %s", e)
        return set()
    return found_ids


def _retrieve_ngram_candidates(
    area_idx: Dict[str, Any],
    ngrams: List[str],
    allow_gap: int = 0,
    filter_common_ngrams: bool = True,
    max_df_3gram: int = 30,
    max_df_4gram: int = 10,
) -> Dict[str, Any]:
    """
    연속 3·4단어 구문 목록에 대해 FTS5 + 역색인 하이브리드로 후보 문서를 회수하고,
    각 구문의 정확한 DF 및 문서별 일치 구문 목록을 계산한다.
    """
    docs = area_idx["docs"]
    id_to_idx = area_idx["id_to_idx"]
    inverted_lemma = area_idx["inverted_lemma"]
    area = area_idx["area"]

    # 1. FTS5 1차 회수 (실패하거나 빈 경우에도 아래 역색인 보강으로 누락 방지)
    fts_ids = _fts_phrase_candidates(ngrams, area=area, allow_gap=allow_gap)
    cand_indices: Set[int] = {id_to_idx[pid] for pid in fts_ids if pid in id_to_idx}

    # 2. 역색인(inverted_lemma) 교집합 보강 (어포스트로피/FTS 토크나이저 차이 및 FTS 미동기화 테스트 방어)
    gram_tok_map: Dict[str, List[str]] = {}
    for g in ngrams:
        toks = _WORD_LOWER_RE.findall(g.lower())
        if len(toks) < 2:
            continue
        gram_tok_map[g] = toks
        sets_for_gram = []
        for t in toks:
            lem = normalize_lemma(t)
            if lem in inverted_lemma:
                sets_for_gram.append(inverted_lemma[lem])
        if sets_for_gram:
            sets_for_gram.sort(key=len)
            inter = set(sets_for_gram[0])
            for s in sets_for_gram[1:]:
                inter &= s
                if not inter:
                    break
            cand_indices |= inter

    # 3. 후보 문서들의 segments에서 순서/연속성 정밀 검증
    gram_df: Counter = Counter()
    doc_matched_grams: Dict[int, List[str]] = defaultdict(list)

    for doc_idx in cand_indices:
        segs = docs[doc_idx]["segments"]
        for g, toks in gram_tok_map.items():
            if _segments_match_ngram(segs, toks, allow_gap=allow_gap):
                gram_df[g] += 1
                doc_matched_grams[doc_idx].append(g)

    # 4. DF 상한 필터링 (상투 구문 제외)
    filtered_common_count = 0
    kept_grams: Set[str] = set()
    for g, toks in gram_tok_map.items():
        df_val = gram_df.get(g, 0)
        n_len = len(toks)
        limit_df = max_df_3gram if n_len <= 3 else max_df_4gram
        if filter_common_ngrams and df_val > limit_df:
            filtered_common_count += 1
            continue
        kept_grams.add(g)

    if filter_common_ngrams and filtered_common_count > 0:
        filtered_doc_grams: Dict[int, List[str]] = {}
        for doc_idx, matched in doc_matched_grams.items():
            kept = [g for g in matched if g in kept_grams]
            if kept:
                filtered_doc_grams[doc_idx] = kept
        doc_matched_grams = filtered_doc_grams

    return {
        "gram_df": gram_df,
        "kept_grams": kept_grams,
        "doc_matched_grams": doc_matched_grams,
        "filtered_common_count": filtered_common_count,
    }


# =====================================================================
# 5. 자질 추출 미리보기 & 겹침 스팬 병합
# =====================================================================


def extract_paragraph_features(
    text: str,
    area: str = "reading",
    filter_common_ngrams: bool = True,
    max_df_3gram: int = 30,
    max_df_4gram: int = 10,
) -> Dict[str, Any]:
    """붙여 넣은 단락에서 고유명사, 표현 조합, 핵심 단어, 연속 3·4단어 구문을 추출하고 IDF를 계산한다."""
    area_idx = _similarity_index.get_area_index(area)
    n_docs = max(1, area_idx["n_docs"])
    lemma_df = area_idx["lemma_df"]
    lemma_idf = area_idx["lemma_idf"]
    entity_df = area_idx["entity_df"]
    phrase_df = area_idx["phrase_df"]

    cleaned = clean_passage_for_similarity(text, area=area, preserve_case=True)
    segments = split_clean_segments(text, area=area, cleaned_override=cleaned)
    all_words = [w for seg in segments for w in seg]
    word_count = len(all_words)

    # 1. 고유명사
    raw_entities = extract_proper_nouns(cleaned, index_lemma_df=lemma_df, corpus_size=area_idx["n_docs"])
    proper_nouns = []
    for ent in raw_entities[:15]:
        df_val = entity_df.get(ent.lower(), 0)
        idf_val = round(math.log((n_docs + 1.0) / (df_val + 1.0)) + 1.0, 2)
        proper_nouns.append({"term": ent, "df": df_val, "idf": idf_val})

    # 2. 표현/연어 조합 (2~3gram)
    raw_phrases = extract_content_phrases(segments)
    phrase_items = []
    for phr in raw_phrases:
        df_val = phrase_df.get(phr, 0)
        toks = phr.split()
        base_idf = sum(lemma_idf.get(normalize_lemma(w), math.log(n_docs + 1.0) + 1.0) for w in toks if w not in STOP_WORDS)
        phr_idf = math.log((n_docs + 1.0) / (df_val + 1.0)) + 1.0
        phrase_items.append({
            "term": phr,
            "df": df_val,
            "idf": round(0.6 * phr_idf + 0.4 * (base_idf / max(1, len(toks))), 2),
        })
    phrase_items.sort(key=lambda x: (-x["idf"], x["term"]))
    phrase_items = phrase_items[:18]

    # 3. 핵심 내용어
    tf_by_lemma: Counter = Counter()
    rep_word_by_lemma: Dict[str, str] = {}
    for w in all_words:
        if len(w) < 3 or w in STOP_WORDS:
            continue
        lem = normalize_lemma(w)
        if not lem:
            continue
        tf_by_lemma[lem] += 1
        if lem not in rep_word_by_lemma:
            rep_word_by_lemma[lem] = w

    keyword_items = []
    default_idf = math.log(n_docs + 1.0) + 1.0
    for lem, cnt in tf_by_lemma.items():
        df_val = lemma_df.get(lem, 0)
        idf_val = lemma_idf.get(lem, default_idf)
        score = (1.0 + math.log(cnt)) * idf_val
        keyword_items.append({
            "term": rep_word_by_lemma[lem],
            "lemma": lem,
            "df": df_val,
            "idf": round(idf_val, 2),
            "_score": score,
        })
    keyword_items.sort(key=lambda x: (-x["_score"], x["term"]))
    for item in keyword_items:
        item.pop("_score", None)
    keyword_items = keyword_items[:22]

    # 4. 연속 3단어 / 4단어 (2중 상투어 필터)
    raw_ng3 = [g for g in extract_consecutive_ngrams(segments, 3) if is_informative_ngram(g, 3)]
    raw_ng4 = [g for g in extract_consecutive_ngrams(segments, 4) if is_informative_ngram(g, 4)]

    # 전체 raw 개수 중 내용어 규칙으로 탈락한 수 + DF 상한으로 탈락한 수 합산
    all_raw_ng3_cnt = len(extract_consecutive_ngrams(segments, 3))
    all_raw_ng4_cnt = len(extract_consecutive_ngrams(segments, 4))
    rule_filtered_cnt = (all_raw_ng3_cnt - len(raw_ng3)) + (all_raw_ng4_cnt - len(raw_ng4))

    ng_res = _retrieve_ngram_candidates(
        area_idx,
        raw_ng3 + raw_ng4,
        allow_gap=0,
        filter_common_ngrams=filter_common_ngrams,
        max_df_3gram=max_df_3gram,
        max_df_4gram=max_df_4gram,
    )
    gram_df = ng_res["gram_df"]
    kept_grams = ng_res["kept_grams"]

    ngrams_3 = []
    for g in raw_ng3:
        if g not in kept_grams:
            continue
        df_val = gram_df.get(g, 0)
        idf_val = round(math.log((n_docs + 1.0) / (df_val + 1.0)) + 1.0, 2)
        ngrams_3.append({"term": g, "df": df_val, "idf": idf_val})
    ngrams_3.sort(key=lambda x: (-x["idf"], x["df"], x["term"]))
    ngrams_3 = ngrams_3[:25]

    ngrams_4 = []
    for g in raw_ng4:
        if g not in kept_grams:
            continue
        df_val = gram_df.get(g, 0)
        idf_val = round(math.log((n_docs + 1.0) / (df_val + 1.0)) + 1.0, 2)
        ngrams_4.append({"term": g, "df": df_val, "idf": idf_val})
    ngrams_4.sort(key=lambda x: (-x["idf"], x["df"], x["term"]))
    ngrams_4 = ngrams_4[:25]

    recommended = "proper_noun" if (len(proper_nouns) >= 2 and word_count <= 140) else "balanced"

    return {
        "word_count": word_count,
        "proper_nouns": proper_nouns,
        "phrases": phrase_items,
        "keywords": keyword_items,
        "ngrams_3": ngrams_3,
        "ngrams_4": ngrams_4,
        "filtered_common_count": rule_filtered_cnt + ng_res["filtered_common_count"],
        "recommended_preset": recommended,
    }


def merge_overlapping_spans(text: str, matched_terms: List[str], max_spans: int = 12) -> List[str]:
    """원문 텍스트에서 일치한 3·4단어 구문들이 연속으로 겹칠 경우 단일 연속 스팬으로 병합한다."""
    if not text or not matched_terms:
        return []

    intervals: List[Tuple[int, int]] = []
    for term in matched_terms:
        toks = _WORD_LOWER_RE.findall(term.lower())
        if not toks:
            continue
        sep = r"[^A-Za-z0-9']+"
        pattern = r"(?<![A-Za-z0-9'])" + sep.join(re.escape(t) for t in toks) + r"(?![A-Za-z0-9'])"
        for m in re.finditer(pattern, text, flags=re.IGNORECASE):
            intervals.append((m.start(), m.end()))

    if not intervals:
        return []

    intervals.sort(key=lambda x: (x[0], -x[1]))
    merged: List[List[int]] = [[intervals[0][0], intervals[0][1]]]
    for s, e in intervals[1:]:
        prev_s, prev_e = merged[-1]
        if s <= prev_e:
            merged[-1][1] = max(prev_e, e)
        elif re.fullmatch(r"[\s,.;:!?\"'()-]*", text[prev_e:s] or ""):
            merged[-1][1] = e
        else:
            merged.append([s, e])

    seen: Set[str] = set()
    spans: List[str] = []
    for s, e in merged:
        snippet = re.sub(r"\s+", " ", text[s:e]).strip()
        if not snippet:
            continue
        key = snippet.lower()
        if key not in seen:
            seen.add(key)
            spans.append(snippet)
            if len(spans) >= max_spans:
                break
    return spans


def _build_snippet(clean_text: str, highlight_terms: List[str], max_len: int = 240) -> str:
    """일치 표현이 가장 많이 포함된 위치를 중심으로 본문 미리보기 스니펫을 생성한다."""
    if not clean_text:
        return ""
    flat = re.sub(r"\s*\|\s*", " ", clean_text)
    flat = re.sub(r"\s+", " ", flat).strip()
    if len(flat) <= max_len:
        return flat

    best_pos = 0
    flat_lower = flat.lower()
    for term in highlight_terms:
        t = (term or "").strip().lower()
        if not t:
            continue
        idx = flat_lower.find(t)
        if idx >= 0:
            best_pos = max(0, idx - 60)
            break

    snippet = flat[best_pos : best_pos + max_len].strip()
    if best_pos > 0:
        snippet = "..." + snippet
    if best_pos + max_len < len(flat):
        snippet = snippet + "..."
    return snippet


# =====================================================================
# 6. 다중 기준 유사 지문 검색 본체 (search_similar_passages)
# =====================================================================


def _passes_meta_filters(
    doc: Dict[str, Any],
    grade: str = "",
    year: Optional[int] = None,
    years: Optional[List[int]] = None,
    month: Optional[int] = None,
    exam_type: str = "",
    question_type: str = "",
    correct_rate_range: str = "",
) -> bool:
    if grade and doc["grade"] != grade:
        return False
    if years and len(years) > 0:
        if doc["year"] not in years:
            return False
    elif year and doc["year"] != year:
        return False
    if month and doc["month"] != month:
        return False
    if exam_type and doc["exam_type"] != exam_type:
        return False
    if question_type and doc["question_type"] != question_type:
        return False
    if correct_rate_range:
        cr = doc.get("correct_rate")
        if cr is None:
            return False
        rk = correct_rate_range.strip().lower()
        if rk == "under20" and not (cr < 20.0):
            return False
        elif rk == "20to30" and not (20.0 <= cr < 30.0):
            return False
        elif rk == "30to40" and not (30.0 <= cr < 40.0):
            return False
        elif rk == "40to50" and not (40.0 <= cr < 50.0):
            return False
        elif rk == "50to60" and not (50.0 <= cr < 60.0):
            return False
        elif rk == "60to70" and not (60.0 <= cr < 70.0):
            return False
        elif rk == "70to80" and not (70.0 <= cr < 80.0):
            return False
        elif rk == "over80" and not (cr >= 80.0):
            return False
    return True


def _doc_contains_term(doc: Dict[str, Any], term: str) -> bool:
    """필수 포함(required_terms) 검사용: 단일 단어는 어간/원문 매칭, 구문은 토큰 연속 매칭."""
    t_clean = (term or "").strip()
    if not t_clean:
        return True
    toks = _WORD_LOWER_RE.findall(t_clean.lower())
    if not toks:
        return True
    if len(toks) == 1:
        lem = normalize_lemma(toks[0])
        if lem in doc["all_lemmas"]:
            return True
        if toks[0] in doc["entities_lower"]:
            return True
        return bool(re.search(rf"(?<![a-z0-9']){re.escape(toks[0])}(?![a-z0-9'])", doc["clean_text"], re.IGNORECASE))
    # 다단어 구문
    if _segments_match_ngram(doc["segments"], toks, allow_gap=0):
        return True
    return t_clean.lower() in doc["clean_text"].lower()


def _composite_group_key(doc: Dict[str, Any]) -> Tuple[str, str]:
    """동일 시험의 41~42 또는 43~45 복합 장문을 하나로 묶어 중복 순위를 제거하기 위한 키."""
    q = int(doc.get("q_num") or 0)
    eid = doc.get("exam_id") or ""
    if 41 <= q <= 42:
        return (eid, "41-42")
    if 43 <= q <= 45:
        return (eid, "43-45")
    return (eid, str(q))


def _load_full_passages_by_ids(passage_ids: List[str], user_role: str) -> Dict[str, Dict[str, Any]]:
    if not passage_ids:
        return {}
    placeholders = ",".join(["?"] * len(passage_ids))
    query = f"""
        SELECT p.*, e.grade, e.year, e.month, e.exam_type, e.subtype,
               e.reading_start_q, e.reading_end_q, e.listening_start_q, e.listening_end_q
        FROM passages p
        JOIN exams e ON p.exam_id = e.id
        WHERE p.id IN ({placeholders})
    """
    with db.get_connection() as conn:
        cursor = conn.cursor()
        rows = cursor.execute(query, passage_ids).fetchall()
        tags_by_pid: Dict[str, List[str]] = defaultdict(list)
        t_rows = cursor.execute(
            f"SELECT passage_id, tag_name FROM passage_tags WHERE passage_id IN ({placeholders}) ORDER BY id ASC",
            passage_ids,
        ).fetchall()
        for tr in t_rows:
            tags_by_pid[tr["passage_id"]].append(tr["tag_name"])

    import json

    result: Dict[str, Dict[str, Any]] = {}
    for r in rows:
        p_dict = dict(r)
        p_dict["tags"] = tags_by_pid.get(r["id"], [])
        if p_dict.get("choice_rates") and isinstance(p_dict["choice_rates"], str):
            try:
                p_dict["choice_rates_obj"] = json.loads(p_dict["choice_rates"])
            except Exception:
                p_dict["choice_rates_obj"] = None
        result[p_dict["id"]] = p_dict

    filtered = access.filter_passages(list(result.values()), user_role)
    return {p["id"]: p for p in filtered}


def search_similar_passages(
    text: str = "",
    preset: str = "balanced",
    weights: Optional[Dict[str, float]] = None,
    selected_proper_nouns: Optional[List[str]] = None,
    selected_phrases: Optional[List[str]] = None,
    selected_keywords: Optional[List[str]] = None,
    selected_ngrams: Optional[List[str]] = None,
    required_terms: Optional[List[str]] = None,
    required_ngrams: Optional[List[str]] = None,
    excluded_terms: Optional[List[str]] = None,
    custom_terms: Optional[List[str]] = None,
    use_ai_expansion: bool = False,
    ngram_mode: Optional[str] = None,
    min_ngram_hits: int = 1,
    filter_common_ngrams: bool = True,
    max_df_3gram: int = 30,
    max_df_4gram: int = 10,
    allow_gap: int = 0,
    min_score: float = 0.05,
    top_k: int = 30,
    area: str = "reading",
    grade: str = "",
    year: Optional[int] = None,
    years: Optional[List[int]] = None,
    month: Optional[int] = None,
    exam_type: str = "",
    question_type: str = "",
    correct_rate_range: str = "",
    tag: str = "",
    user_role: str = access.DEFAULT_ROLE,
) -> Dict[str, Any]:
    """단락 텍스트에서 다중 시그널을 추출·조합해 유사 기출 지문을 검색·순위화한다."""
    t0 = time.perf_counter()

    # 등급별 검색 조건 제한 (access.py 일관 적용)
    if not access.allowed_search_filters(user_role)["meta"]:
        correct_rate_range = ""
        tag = ""

    norm_area = "listening" if area == "listening" else "reading"
    area_idx = _similarity_index.get_area_index(norm_area)
    docs = area_idx["docs"]
    n_docs = max(1, area_idx["n_docs"])
    lemma_idf = area_idx["lemma_idf"]
    inverted_lemma = area_idx["inverted_lemma"]
    inverted_entity = area_idx["inverted_entity"]
    inverted_phrase = area_idx["inverted_phrase"]

    preset_key = preset if preset in SIMILARITY_PRESETS else "balanced"
    top_k = max(1, min(100, int(top_k or 30)))
    min_ngram_hits = max(1, int(min_ngram_hits or 1))
    allow_gap = max(0, min(2, int(allow_gap or 0)))

    # 1. 제외/필수/직접추가 집합 정리
    excluded_set = {t.strip().lower() for t in (excluded_terms or []) if t and t.strip()}
    excluded_lemmas = {normalize_lemma(t) for t in excluded_set if " " not in t}

    all_required = [t.strip() for t in (required_terms or []) + (required_ngrams or []) if t and t.strip()]
    custom_clean = [t.strip() for t in (custom_terms or []) if t and t.strip() and t.strip().lower() not in excluded_set]

    # 2. 단락 자질 추출
    features = extract_paragraph_features(
        text or "",
        area=norm_area,
        filter_common_ngrams=filter_common_ngrams,
        max_df_3gram=max_df_3gram,
        max_df_4gram=max_df_4gram,
    )

    # 사용자가 명시적으로 선택한 목록이 있으면 우선 적용, 없으면 자동 추출 사용
    q_entities = (
        [e.strip() for e in selected_proper_nouns if e and e.strip()]
        if selected_proper_nouns is not None
        else [x["term"] for x in features["proper_nouns"]]
    )
    q_entities = [e for e in q_entities if e.lower() not in excluded_set]

    q_phrases = (
        [p.strip() for p in selected_phrases if p and p.strip()]
        if selected_phrases is not None
        else [x["term"] for x in features["phrases"]]
    )
    q_phrases = [p for p in q_phrases if p.lower() not in excluded_set]

    q_keyword_words = (
        [k.strip() for k in selected_keywords if k and k.strip()]
        if selected_keywords is not None
        else [x["term"] for x in features["keywords"]]
    )
    q_keyword_words = [
        k for k in q_keyword_words if k.lower() not in excluded_set and normalize_lemma(k) not in excluded_lemmas
    ]

    # 직접 추가 단어/구문 합류
    for ct in custom_clean:
        toks = _WORD_LOWER_RE.findall(ct.lower())
        if len(toks) >= 2:
            if ct.lower() not in {p.lower() for p in q_phrases}:
                q_phrases.append(ct.lower())
        elif len(toks) == 1:
            if ct[0].isupper() and ct.lower() not in {e.lower() for e in q_entities}:
                q_entities.append(ct)
            elif toks[0] not in {k.lower() for k in q_keyword_words}:
                q_keyword_words.append(toks[0])

    # 선택적 AI 동의어·주제어 확장
    ai_expansion_info: Dict[str, Any] = {"used": False, "keywords": [], "phrases": []}
    ai_bonus_lemmas: Dict[str, float] = {}
    if use_ai_expansion and (text or "").strip():
        try:
            from .. import grammar_analyzer

            ai_res = grammar_analyzer.expand_similarity_keywords(text)
            if ai_res.get("used"):
                ai_expansion_info = ai_res
                for ak in ai_res.get("keywords", []):
                    lem = normalize_lemma(ak)
                    if lem and lem not in excluded_lemmas and ak.lower() not in STOP_WORDS:
                        ai_bonus_lemmas[lem] = 0.6
                for ap in ai_res.get("phrases", []):
                    ap_low = ap.strip().lower()
                    if ap_low and ap_low not in excluded_set and ap_low not in q_phrases:
                        q_phrases.append(ap_low)
        except Exception as ai_err:
            logger.warning("[Similarity AI Expand] 실패 (로컬 엔진 계속): %s", ai_err)

    # 3. 연속 3·4단어 N-gram 대상 결정
    effective_ngram_mode = ngram_mode
    if not effective_ngram_mode and preset_key in NGRAM_ONLY_PRESETS:
        effective_ngram_mode = {"ngram_3": "3", "ngram_4": "4", "ngram_3_4": "3_4"}[preset_key]

    if selected_ngrams is not None:
        pool_ng = [g.strip().lower() for g in selected_ngrams if g and g.strip() and g.strip().lower() not in excluded_set]
        target_ng3 = [g for g in pool_ng if len(g.split()) == 3]
        target_ng4 = [g for g in pool_ng if len(g.split()) >= 4]
    else:
        target_ng3 = [x["term"] for x in features["ngrams_3"] if x["term"].lower() not in excluded_set]
        target_ng4 = [x["term"] for x in features["ngrams_4"] if x["term"].lower() not in excluded_set]

    for ct in custom_clean:
        toks = _WORD_LOWER_RE.findall(ct.lower())
        if len(toks) == 3 and " ".join(toks) not in target_ng3:
            target_ng3.append(" ".join(toks))
        elif len(toks) == 4 and " ".join(toks) not in target_ng4:
            target_ng4.append(" ".join(toks))

    active_ngrams: List[str] = []
    if effective_ngram_mode == "3":
        active_ngrams = target_ng3
    elif effective_ngram_mode == "4":
        active_ngrams = target_ng4
    else:
        active_ngrams = target_ng4 + target_ng3

    ng_res = _retrieve_ngram_candidates(
        area_idx,
        active_ngrams,
        allow_gap=allow_gap,
        filter_common_ngrams=filter_common_ngrams,
        max_df_3gram=max_df_3gram,
        max_df_4gram=max_df_4gram,
    )
    gram_df = ng_res["gram_df"]
    doc_matched_grams = ng_res["doc_matched_grams"]
    kept_grams = ng_res["kept_grams"]

    # 4. 쿼리 키워드 TF-IDF 벡터 구축
    default_idf = math.log(n_docs + 1.0) + 1.0
    q_lemma_weights: Dict[str, float] = {}
    q_lemma_to_surface: Dict[str, str] = {}
    raw_seg_words = [w for seg in split_clean_segments(text or "", area=norm_area) for w in seg]
    raw_lemma_counts = Counter(normalize_lemma(w) for w in raw_seg_words if w not in STOP_WORDS and len(w) >= 3)

    for kw in q_keyword_words:
        lem = normalize_lemma(kw)
        if not lem or lem in excluded_lemmas:
            continue
        cnt = max(1, raw_lemma_counts.get(lem, 1))
        idf_val = lemma_idf.get(lem, default_idf)
        q_lemma_weights[lem] = (1.0 + math.log(cnt)) * idf_val
        if lem not in q_lemma_to_surface:
            q_lemma_to_surface[lem] = kw

    for lem, mult in ai_bonus_lemmas.items():
        if lem not in q_lemma_weights:
            idf_val = lemma_idf.get(lem, default_idf)
            q_lemma_weights[lem] = mult * idf_val
            q_lemma_to_surface[lem] = lem

    q_norm = math.sqrt(sum(v * v for v in q_lemma_weights.values())) or 1.0

    # 5. 가중치 결정 (고유명사 없으면 해당 가중치를 키워드·표현으로 자동 재분배)
    is_ngram_mode = preset_key in NGRAM_ONLY_PRESETS
    applied_weights = dict(SIMILARITY_PRESETS[preset_key])
    if weights and not is_ngram_mode:
        for k in ("keyword", "phrase", "proper_noun", "shingle"):
            if k in weights and weights[k] is not None:
                applied_weights[k] = max(0.0, float(weights[k]))
    if not is_ngram_mode and not q_entities:
        ent_w = applied_weights["proper_noun"]
        applied_weights["proper_noun"] = 0.0
        applied_weights["keyword"] += ent_w * 0.6
        applied_weights["phrase"] += ent_w * 0.4
    w_sum = sum(applied_weights.values()) or 1.0
    applied_weights = {k: round(v / w_sum, 4) for k, v in applied_weights.items()}

    # 6. 후보 회수
    candidate_indices: Set[int] = set()
    if is_ngram_mode:
        candidate_indices = set(doc_matched_grams.keys())
    else:
        for lem in q_lemma_weights:
            candidate_indices |= inverted_lemma.get(lem, set())
        for ent in q_entities:
            ent_l = ent.lower()
            candidate_indices |= inverted_entity.get(ent_l, set())
            for w in _WORD_LOWER_RE.findall(ent_l):
                lem = normalize_lemma(w)
                if lem:
                    candidate_indices |= inverted_lemma.get(lem, set())
        for phr in q_phrases:
            candidate_indices |= inverted_phrase.get(phr.lower(), set())
        candidate_indices |= set(doc_matched_grams.keys())

    # #태그 DB 필터링
    tag_allowed_ids: Optional[Set[str]] = None
    if tag and tag.strip():
        with db.get_connection() as conn:
            t_rows = conn.execute(
                "SELECT DISTINCT passage_id FROM passage_tags WHERE tag_name LIKE ?",
                (f"%{tag.strip()}%",),
            ).fetchall()
            tag_allowed_ids = {r["passage_id"] for r in t_rows}

    # 7. 후보 스코어링
    q_phrase_token_pairs: List[Tuple[str, str, str]] = []
    for phr in q_phrases:
        ptoks = [normalize_lemma(w) for w in phr.lower().split() if w not in STOP_WORDS]
        if len(ptoks) >= 2:
            q_phrase_token_pairs.append((phr, ptoks[0], ptoks[-1]))

    active_ng3_total_w = sum(math.log((n_docs + 1.0) / (gram_df.get(g, 0) + 1.0)) + 1.0 for g in target_ng3 if g in kept_grams)
    active_ng4_total_w = sum((math.log((n_docs + 1.0) / (gram_df.get(g, 0) + 1.0)) + 1.0) * 2.0 for g in target_ng4 if g in kept_grams)
    total_ngram_denom = max(1e-6, active_ng3_total_w + active_ng4_total_w)
    if effective_ngram_mode == "3":
        total_ngram_denom = max(1e-6, active_ng3_total_w)
    elif effective_ngram_mode == "4":
        total_ngram_denom = max(1e-6, active_ng4_total_w)

    scored_docs: List[Dict[str, Any]] = []

    for doc_idx in candidate_indices:
        doc = docs[doc_idx]
        if tag_allowed_ids is not None and doc["id"] not in tag_allowed_ids:
            continue
        if not _passes_meta_filters(doc, grade, year, years, month, exam_type, question_type, correct_rate_range):
            continue

        # 필수 포함 하드 필터
        if all_required:
            if not all(_doc_contains_term(doc, req_t) for req_t in all_required):
                continue

        matched_grams = doc_matched_grams.get(doc_idx, [])
        matched_ng3 = [g for g in matched_grams if len(g.split()) == 3]
        matched_ng4 = [g for g in matched_grams if len(g.split()) >= 4]
        ngram_hit_count = len(matched_ng3) + len(matched_ng4)

        if (is_ngram_mode or ngram_mode) and ngram_hit_count < min_ngram_hits:
            continue

        # (A) 고유명사 매칭 & 점수
        matched_entities: List[str] = []
        for ent in q_entities:
            ent_l = ent.lower()
            if ent_l in doc["entities_lower"]:
                matched_entities.append(ent)
            else:
                ent_toks = _WORD_LOWER_RE.findall(ent_l)
                if ent_toks and (
                    (len(ent_toks) == 1 and normalize_lemma(ent_toks[0]) in doc["all_lemmas"])
                    or (len(ent_toks) >= 2 and _segments_match_ngram(doc["segments"], ent_toks, allow_gap=0))
                ):
                    matched_entities.append(ent)
        s_ent = min(1.0, len(matched_entities) / len(q_entities)) if q_entities else 0.0

        # (B) 핵심어 TF-IDF 코사인 + 커버리지 혼합
        dot = 0.0
        matched_kw_surfaces: List[str] = []
        doc_tf = doc["lemma_tf"]
        for lem, qw in q_lemma_weights.items():
            cnt = doc_tf.get(lem, 0)
            if cnt > 0:
                dw = (1.0 + math.log(cnt)) * lemma_idf.get(lem, default_idf)
                dot += qw * dw
                matched_kw_surfaces.append(q_lemma_to_surface.get(lem, lem))
            elif lem in doc["all_lemmas"]:
                dot += qw * 0.5
                matched_kw_surfaces.append(q_lemma_to_surface.get(lem, lem))

        cosine_kw = dot / (q_norm * doc["tfidf_norm"]) if dot > 0 else 0.0
        cov_kw = (len(matched_kw_surfaces) / len(q_lemma_weights)) if q_lemma_weights else 0.0
        s_kw = min(1.0, 0.70 * cosine_kw + 0.30 * cov_kw)

        # (C) 표현 조합 + 공출현 점수
        matched_phrases: List[str] = []
        phrase_score_sum = 0.0
        for phr, l1, l2 in q_phrase_token_pairs:
            phr_l = phr.lower()
            if phr_l in doc["phrases_set"] or _segments_match_ngram(doc["segments"], _WORD_LOWER_RE.findall(phr_l), allow_gap=0):
                matched_phrases.append(phr)
                phrase_score_sum += 1.0
            elif l1 in doc["all_lemmas"] and l2 in doc["all_lemmas"]:
                phrase_score_sum += 0.35
        s_phr = min(1.0, phrase_score_sum / len(q_phrase_token_pairs)) if q_phrase_token_pairs else 0.0

        # (D) N-gram / Shingle 점수
        ng_w_sum = 0.0
        for g in matched_ng3:
            ng_w_sum += math.log((n_docs + 1.0) / (gram_df.get(g, 0) + 1.0)) + 1.0
        for g in matched_ng4:
            ng_w_sum += (math.log((n_docs + 1.0) / (gram_df.get(g, 0) + 1.0)) + 1.0) * 2.0
        s_shg = min(1.0, ng_w_sum / total_ngram_denom) if (matched_ng3 or matched_ng4) else 0.0

        if is_ngram_mode:
            # 1개 이상 일치 시 최소 점수 보장과 함께 히트 비율+희소도 반영
            hit_ratio = min(1.0, ngram_hit_count / max(1, min(6, len(active_ngrams))))
            final_ratio = min(1.0, 0.65 * s_shg + 0.35 * hit_ratio)
        else:
            final_ratio = (
                applied_weights["keyword"] * s_kw
                + applied_weights["phrase"] * s_phr
                + applied_weights["proper_noun"] * s_ent
                + applied_weights["shingle"] * s_shg
            )

        if final_ratio < min_score and not is_ngram_mode:
            continue

        merged_spans = merge_overlapping_spans(doc["clean_text"], matched_ng4 + matched_ng3)

        scored_docs.append({
            "_doc": doc,
            "_final_ratio": final_ratio,
            "_sort_key": (
                round(final_ratio, 6),
                len(matched_ng4),
                len(matched_ng3),
                len(matched_entities),
                doc["year"],
                doc["month"],
            ),
            "similarity_score": round(final_ratio * 100.0, 1),
            "score_breakdown": {
                "keyword": round(s_kw * 100.0, 1),
                "phrase": round(s_phr * 100.0, 1),
                "proper_noun": round(s_ent * 100.0, 1),
                "shingle": round(s_shg * 100.0, 1),
            },
            "matched_proper_nouns": matched_entities,
            "matched_phrases": matched_phrases,
            "matched_keywords": matched_kw_surfaces[:15],
            "matched_ngrams_3": matched_ng3,
            "matched_ngrams_4": matched_ng4,
            "ngram_hit_count": ngram_hit_count,
            "merged_matched_spans": merged_spans,
        })

    # 8. 정렬 및 복합 장문(41~42, 43~45) 중복 정리
    scored_docs.sort(key=lambda x: x["_sort_key"], reverse=True)

    seen_groups: Set[Tuple[str, str]] = set()
    deduped: List[Dict[str, Any]] = []
    for item in scored_docs:
        gkey = _composite_group_key(item["_doc"])
        if gkey in seen_groups:
            continue
        seen_groups.add(gkey)
        deduped.append(item)
        if len(deduped) >= top_k:
            break

    # 9. 상위 top_k 전체 DB 행 로드 및 access.filter_passages 적용
    top_ids = [item["_doc"]["id"] for item in deduped]
    full_map = _load_full_passages_by_ids(top_ids, user_role=user_role)

    final_items: List[Dict[str, Any]] = []
    for item in deduped:
        doc = item["_doc"]
        full_p = full_map.get(doc["id"])
        if not full_p:
            continue
        hl_terms = item["merged_matched_spans"] + item["matched_proper_nouns"] + item["matched_phrases"] + item["matched_keywords"]
        full_p["similarity_score"] = item["similarity_score"]
        full_p["score_breakdown"] = item["score_breakdown"]
        full_p["matched_proper_nouns"] = item["matched_proper_nouns"]
        full_p["matched_phrases"] = item["matched_phrases"]
        full_p["matched_keywords"] = item["matched_keywords"]
        full_p["matched_ngrams_3"] = item["matched_ngrams_3"]
        full_p["matched_ngrams_4"] = item["matched_ngrams_4"]
        full_p["ngram_hit_count"] = item["ngram_hit_count"]
        full_p["merged_matched_spans"] = item["merged_matched_spans"]
        full_p["snippet"] = _build_snippet(doc["clean_text"], hl_terms)
        final_items.append(full_p)

    elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 2)

    return {
        "preset": preset_key,
        "applied_weights": applied_weights,
        "elapsed_ms": elapsed_ms,
        "count": len(final_items),
        "extracted": {
            "proper_nouns": features["proper_nouns"],
            "phrases": features["phrases"],
            "keywords": features["keywords"],
            "ngrams_3": features["ngrams_3"],
            "ngrams_4": features["ngrams_4"],
            "filtered_common_count": features["filtered_common_count"],
            "ai_expansion": ai_expansion_info,
        },
        "items": final_items,
    }
