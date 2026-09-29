"""
05-gichul_db: FELS(Function-Embedded Listening Skills, 약형드랩) 교사용 엔진 (fels_engine.py)

기능 및 역할:
- 영어 청취 학습에서 강세가 탈락하고 약형(Weak Form)으로 발음되어 연음·탈락의 주원인이 되는
  7대 기능어(Function Words: 관사, 전치사, 대명사, be/조동사, 접속사, 부정어, 축약형)를 지능적으로 감지.
- 교사용 영문 대본에서 기능어 단어들을 자동으로 <단어> 괄호로 감싸 '약형드랩(FELS)' 텍스트로 변환.
- 화자 태그(M:, W:, Man:, Woman: 등)와 마침표, 쉼표, 물음표 등 문장부호는 훼손 없이 정확히 보존.
- 원클릭 복사용 학습지 텍스트 및 기능어 통계(출현 비율 등) 산출.
"""

import re
from typing import Dict, Any, Tuple, Set, List, Union

# 1. 관사 (Articles)
ARTICLES: Set[str] = {
    "a", "an", "the"
}

# 2. 전치사 (Prepositions)
PREPOSITIONS: Set[str] = {
    "to", "of", "in", "for", "on", "with", "at", "by", "from", "up",
    "about", "into", "over", "after", "under", "above", "through",
    "between", "before", "behind", "during", "without", "against",
    "along", "across", "towards", "toward", "upon", "within", "down",
    "off", "out", "near", "past", "since", "until", "till", "beside",
    "below", "beneath", "beyond", "inside", "outside", "onto"
}

# 3. 대명사 (Pronouns)
PRONOUNS: Set[str] = {
    # 인칭 대명사 (주격/목적격/소유격/소유대명사/재귀대명사)
    "i", "me", "my", "mine", "myself",
    "you", "your", "yours", "yourself", "yourselves",
    "he", "him", "his", "himself",
    "she", "her", "hers", "herself",
    "it", "its", "itself",
    "we", "us", "our", "ours", "ourselves",
    "they", "them", "their", "theirs", "themselves",
    # 지시대명사
    "this", "that", "these", "those",
    # 의문/관계대명사
    "who", "whom", "whose", "which", "what",
    # 부정대명사
    "someone", "anyone", "everyone", "no one",
    "something", "anything", "everything", "nothing",
    "somebody", "anybody", "everybody", "nobody",
    "some", "any", "all", "both", "each", "either", "neither",
    "one", "ones", "other", "others", "another"
}

# 4. Be/조동사 (Auxiliary / Be / Modal Verbs)
AUXILIARIES: Set[str] = {
    "am", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "having",
    "do", "does", "did",
    "will", "would", "shall", "should", "can", "could", "may", "might", "must", "ought"
}

# 5. 접속사 (Conjunctions)
CONJUNCTIONS: Set[str] = {
    "and", "but", "or", "so", "because", "if", "when", "while",
    "that", "as", "than", "though", "although", "since", "unless",
    "until", "whether", "nor", "yet", "where", "how", "why",
    "whereas", "wherever", "whenever"
}

# 6. 부정어 및 소사 (Negatives & Particles)
NEGATIVES: Set[str] = {
    "not", "no"
}

# 7. 축약형 (Contractions & Combined Forms)
CONTRACTIONS: Set[str] = {
    "i'm", "you're", "he's", "she's", "it's", "we're", "they're",
    "i've", "you've", "we've", "they've",
    "i'll", "you'll", "he'll", "she'll", "it'll", "we'll", "they'll",
    "i'd", "you'd", "he'd", "she'd", "we'd", "they'd",
    "isn't", "aren't", "wasn't", "weren't",
    "haven't", "hasn't", "hadn't",
    "don't", "doesn't", "didn't",
    "won't", "wouldn't", "can't", "couldn't", "shouldn't", "mustn't",
    "there's", "what's", "that's", "who's", "here's", "how's", "where's",
    "let's", "ain't"
}

# 7대 기능어 통합 Set (O(1) 해시 룩업)
FUNCTION_WORDS: Set[str] = (
    ARTICLES | PREPOSITIONS | PRONOUNS | AUXILIARIES | CONJUNCTIONS | NEGATIVES | CONTRACTIONS
)

# 화자 레이블 정규식 (줄 시작부 화자 태그 감지)
SPEAKER_PREFIX_REGEX = re.compile(
    r"^(\s*(?:[MW]|Man|Woman|Girl|Boy|Teacher|Student|Clerk|Host|Father|Mother|Son|Daughter|Interviewer|Interviewee|Doctor|Patient|Officer)\s*[:：]\s*)",
    re.IGNORECASE
)

# 영문 단어 및 기타 토큰 분리 정규식
WORD_TOKEN_REGEX = re.compile(r"([A-Za-z]+(?:'[A-Za-z]+)?|[^\w\s]+|\s+)")


def is_function_word(word: str) -> bool:
    """단어가 7대 기능어(Function Word)에 속하는지 여부 판별"""
    if not word:
        return False
    # 아포스트로피 정규화 (’ -> ')
    cleaned = word.strip().replace("’", "'").lower()
    return cleaned in FUNCTION_WORDS


def generate_fels_text(script_text: str) -> str:
    """
    영문 대본을 FELS(기능어 [괄호] 삽입) 텍스트로 자동 변환
    - 화자 태그(M:, W: 등)는 괄호 적용에서 제외
    - 기능어만 [기능어] 형태로 감싸고 내용어(명사, 동사, 형용사 등)는 원문 유지
    - 대소문자 및 문장부호 온전히 보존
    """
    if not script_text:
        return ""

    result_lines = []
    for line in script_text.splitlines():
        if not line.strip():
            result_lines.append("")
            continue

        prefix = ""
        body = line

        # 1. 화자 태그 분리 (M:, W: 등)
        m_speaker = SPEAKER_PREFIX_REGEX.match(line)
        if m_speaker:
            prefix = m_speaker.group(1)
            body = line[m_speaker.end():]

        # 2. 본문 토크나이징 및 기능어 괄호 래핑
        tokens = WORD_TOKEN_REGEX.findall(body)
        transformed_tokens = []
        for t in tokens:
            # 영문 단어인 경우
            if re.match(r"^[A-Za-z]+(?:['’][A-Za-z]+)?$", t):
                if is_function_word(t):
                    transformed_tokens.append(f"[{t}]")
                else:
                    transformed_tokens.append(t)
            else:
                # 공백, 문장부호 등
                transformed_tokens.append(t)

        result_lines.append(prefix + "".join(transformed_tokens))

    return "\n".join(result_lines)


def is_dialogue_script(text: str, title: str = "", question_type: str = "") -> bool:
    """
    스크립트 텍스트와 발문(question_title)/문제유형(question_type)을 2중 교차 검증하여
    대화문(True) / 담화문(False) 판정
    """
    title_clean = (title or "").strip()
    q_type_clean = (question_type or "").strip()
    text_clean = (text or "").strip()

    # 1. 발문(Title) 및 문제유형(Type) 키워드 신호 분석
    has_dialogue_title = bool(re.search(r'(?:대화|두\s*사람)', title_clean))
    has_monologue_title = bool(re.search(r'(?:다음을\s*듣고|하는\s*말|담화|안내\s*방송|안내문|설명을\s*듣고|이야기를\s*듣고)', title_clean))
    if "담화" in q_type_clean:
        has_monologue_title = True

    # 2. 스크립트(Script) 화자 턴 신호 분석
    speaker_regex = re.compile(
        r"(?:^|\n)\s*(?:[MW]|Man|Woman|Boy|Girl|Male|Female|Teacher|Student|Doctor|Father|Mother|Son|Daughter|Host|Officer)\s*[:：]",
        re.IGNORECASE
    )
    speaker_tags = speaker_regex.findall(text_clean)
    speaker_count = len(speaker_tags)

    # 3. 2중 교차 검증(Dual Verification) 종합 판정
    if has_dialogue_title and speaker_count >= 2:
        return True
    if has_monologue_title and speaker_count <= 1:
        return False
    if has_dialogue_title and not has_monologue_title:
        return True
    if has_monologue_title and not has_dialogue_title:
        return False

    return speaker_count >= 2


def split_fels_monologue_sentences(fels_text: str, as_list: bool = False) -> Union[str, List[str]]:
    """담화문(Monologue) FELS 텍스트에서 화자 태그(M:, W: 등)를 제거하고 문장 단위로 분할하여 번호(1. , 2. ...) 부여"""
    if not fels_text:
        return [] if as_list else ""

    body = fels_text.strip()
    # 1. 화자 태그(M:, W:, Man:, Woman: 등) 완전 제거
    body = re.sub(
        r"(?:^|\n)\s*(?:[MW]|Man|Woman|Boy|Girl|Host|Speaker|Teacher|Doctor|Officer|Male|Female|남|여)\d*\s*[:：]\s*",
        " ",
        body,
        flags=re.IGNORECASE
    ).strip()

    # 2. 공백 및 개행 정규화
    cleaned = re.sub(r"[\r\n]+", " ", body)
    cleaned = re.sub(r"[ \t]+", " ", cleaned).strip()

    # 3. 약어 및 마침표 보호
    cleaned = re.sub(r"(\d+)\.(\d+)", r"\1<PERIOD>\2", cleaned)
    abbr_pattern = r"\b(mr|mrs|ms|dr|prof|sr|jr|e\.g|i\.e|etc|vs|u\.s|u\.k|no)\."
    cleaned = re.sub(abbr_pattern, lambda m: m.group(0).replace(".", "<PERIOD>"), cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\b([A-Za-z])\.\s+", r"\1<PERIOD> ", cleaned)
    cleaned = re.sub(r"\.{2,}", "<ELLIPSIS>", cleaned)

    # 4. 문장 분할: 마침표/물음표/느낌표 뒤 공백 + 대문자 또는 [단어]/<단어>/빈칸 시작
    split_pattern = re.compile(r'([.?!]["\')\]]?)\s+(?=[A-Z"\'(0-9]|\[|<)')
    splits = split_pattern.split(cleaned)

    raw_sentences = []
    i = 0
    while i < len(splits):
        s = splits[i]
        if i + 1 < len(splits) and re.match(r'^[.?!]["\')\]]?$', splits[i + 1]):
            s += splits[i + 1]
            i += 2
        else:
            i += 1
        s = s.strip()
        if s:
            raw_sentences.append(s)

    final_sentences = [
        f"{idx + 1}. {s.replace('<PERIOD>', '.').replace('<ELLIPSIS>', '...')}"
        for idx, s in enumerate(raw_sentences)
    ]

    return final_sentences if as_list else "\n".join(final_sentences)


def number_dialogue_turns(text: str) -> str:
    """대화문(Dialogue) 텍스트의 각 턴에 화자별 순번(M1:, W1:, M2:, W2: ...) 부여"""
    if not text:
        return ""
    lines = text.split("\n")
    m_count = 0
    w_count = 0
    numbered_lines = []

    speaker_turn_re = re.compile(r"^([MW]|Man|Woman|Boy|Girl|Male|Female|남|여)\d*\s*[:：]\s*(.*)$", re.IGNORECASE)

    for line in lines:
        trimmed = line.strip()
        if not trimmed:
            continue
        m = speaker_turn_re.match(trimmed)
        if m:
            spk = m.group(1)
            rest = m.group(2).strip()
            is_male = bool(re.match(r"^(M|Man|Boy|Male|남)$", spk, re.IGNORECASE))
            if is_male:
                m_count += 1
                label = f"M{m_count}:"
            else:
                w_count += 1
                label = f"W{w_count}:"
            numbered_lines.append(f"{label} {rest}")
        else:
            numbered_lines.append(trimmed)

    return "\n".join(numbered_lines)


def format_fels_text(fels_text: str, mode: str = "blank", title: str = "", question_type: str = "") -> str:
    """
    FELS 텍스트를 학생용(blank) 또는 교사용(answer) 규격으로 서식화
    - 담화문: 화자 태그 제거 + 문장 단위 분할 + 문장 번호(1. , 2. ...) 부여
    - 대화문: M1:, W1:, M2:, W2: 화자별 순번 부여
    - 빈칸(blank): 텍스트 내 최장 단어 글자수 기준 균일 공백([        ]) 적용 (공백 축소 없이 100% 보존)
    - 정답(answer): [단어] 정답 표시
    """
    if not fels_text:
        return ""

    is_dialogue = is_dialogue_script(fels_text, title=title, question_type=question_type)

    if is_dialogue:
        structured_text = number_dialogue_turns(fels_text)
    else:
        structured_text = split_fels_monologue_sentences(fels_text)

    words = []
    for m in re.finditer(r"<([^>]+?)>|\[([^\]]+?)\]", fels_text):
        w = (m.group(1) or m.group(2) or "").strip()
        if w:
            words.append(w)
    max_len = max([len(w) for w in words], default=5)

    if mode == "blank":
        blank_str = f"[{' ' * max_len}]"
        def _replace_blank(m):
            content = (m.group(1) or m.group(2) or "").strip()
            return blank_str if content else m.group(0)
        return re.sub(r"<([^>]+?)>|\[([^\]]+?)\]", _replace_blank, structured_text)
    else:
        return re.sub(r"<([^>]+?)>", r"[\1]", structured_text)


def generate_fels_blank(fels_text: str, split_sentences_for_monologue: bool = True, title: str = "", question_type: str = "") -> str:
    """
    FELS 텍스트에서 [단어] 또는 <단어>를 최장 기능어 글자수에 맞춘 균일한 [       ] 빈칸으로 변환
    - 개별 단어의 글자수와 무관하게 해당 지문 내 최장 단어 글자수만큼의 공백을 모든 [ ]에 동일 적용
    - 담화문의 경우 1문장 = 1행 유인물 형태로 자동 분할 (발문 + 스크립트 2중 검증)
    """
    if not fels_text:
        return ""
    if split_sentences_for_monologue:
        return format_fels_text(fels_text, mode="blank", title=title, question_type=question_type)

    words = []
    for m in re.finditer(r"<([^>]+?)>|\[([^\]]+?)\]", fels_text):
        w = (m.group(1) or m.group(2) or "").strip()
        if w:
            words.append(w)
    max_len = max([len(w) for w in words], default=5)
    blank_str = f"[{' ' * max_len}]"

    def _replace(m):
        content = (m.group(1) or m.group(2) or "").strip()
        return blank_str if content else m.group(0)

    return re.sub(r"<([^>]+?)>|\[([^\]]+?)\]", _replace, fels_text)


def analyze_fels(script_text: str) -> Dict[str, Any]:
    """
    대본 텍스트에 대한 FELS 변환 및 통계(기능어 수, 내용어 수, 비율) 분석
    """
    if not script_text:
        return {
            "fels_text": "",
            "total_words": 0,
            "function_word_count": 0,
            "content_word_count": 0,
            "function_word_ratio": 0.0
        }

    fels_text = generate_fels_text(script_text)

    # 단어 통계 계산
    words = re.findall(r"\b[A-Za-z]+(?:['’][A-Za-z]+)?\b", script_text)
    total = len(words)
    fn_count = sum(1 for w in words if is_function_word(w))
    content_count = total - fn_count
    ratio = round((fn_count / total * 100), 1) if total > 0 else 0.0

    return {
        "fels_text": fels_text,
        "total_words": total,
        "function_word_count": fn_count,
        "content_word_count": content_count,
        "function_word_ratio": ratio
    }
