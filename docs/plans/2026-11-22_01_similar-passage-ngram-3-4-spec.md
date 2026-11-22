# 추가 구현 계획서: 유사 지문 검색 — 연속 3단어·4단어(N-gram) 전용 기준 스펙

**작성일시**: 2026-11-22  
**상태**: ✅ 완료  
**기반 계획서**: [2026-11-22_similar-passage-search.md](2026-11-22_similar-passage-search.md)  
**관련 요청**: 붙여 넣은 단락 내 **연속된 3단어(3-gram)** 또는 **연속된 4단어(4-gram)** 구문을 독립 검색 기준으로 설정하여 유사 지문·변형 원문을 고정밀 탐색할 수 있는 세부 스펙 정의

---

## 1. 배경 및 실측 근거 (`gichul.db` 독해 8,901건 기준)

기반 계획서([2026-11-22_similar-passage-search.md](2026-11-22_similar-passage-search.md))의 4대 시그널 중 `Shingle(3~4단어)`을 단순 보조 점수(10~35%)에 그치지 않고, **교사가 직접 선택·조작할 수 있는 독립 검색 기준 모드**로 격상합니다.

실제 구축된 `gichul.db` 독해 8,901개 지문을 대상으로 사전 시뮬레이션한 결과는 다음과 같습니다.

| 지표 | 연속 3단어 (3-gram) | 연속 4단어 (4-gram) |
| :--- | :---: | :---: |
| 코퍼스 전체 고유 구문 수 | 730,601개 | 858,518개 |
| 희소 구문 비율 (높은 변별력) | **98.6%**가 5개 이하 지문에만 출현 | **99.4%**가 3개 이하 지문에만 출현 |
| 60단어 단락 검색 응답 시간 | **~24 ms** (3+4단어 동시) | 동일 |
| 대표 상투 노이즈 (필터 필수) | `one of the`(514), `in order to`(200), `a lot of`(187), `a b c`(275) | `one of the most`(132), `on the other hand`(118), `the above graph shows`(110) |

- **연속 4단어 기준**: 99.4%가 3개 이하 지문에만 등장하는 고유 지문(Fingerprint) 역할을 하므로, 내신·문제집 변형 지문의 원 기출 추적 및 동일 원서·기사 발췌 지문 탐지에 탁월합니다.
- **연속 3단어 기준**: 원문이 상당 부분 축약·치환되었거나, 동일한 핵심 학술 구문·표현을 공유하는 연계 기출을 폭넓게 찾을 때 적합합니다.

---

## 2. 진행 현황 (Progress Tracker)

`/apply` 명령어로 기반 계획서와 함께 또는 후속 단계로 구현 시 아래 표를 갱신합니다.

| 단계 | 작업 내용 | 담당 영역 | 상태 |
|:---:|---|---|:---:|
| **1단계** | 문장 경계 존중 연속 3·4단어 추출기, `(A)~(E)`/`(a)~(e)` 표식 정제 및 2중 상투어(내용어+DF) 필터 구축 | Backend (`gichul/services/similarity_search.py`) | ✅ 완료 |
| **2단계** | FTS5 Phrase/NEAR 하이브리드 후보 회수 및 `ngram_3`·`ngram_4`·`ngram_3_4` 전용 스코어링·랭킹 엔진 구현 | Backend (`gichul/services/similarity_search.py`) | ✅ 완료 |
| **3단계** | REST API(`/api/search/similar/extract`, `/api/search/similar`)에 연속 3·4단어 파라미터 및 일치 구문 근거 응답 확장 | Backend (`gichul/routers/search.py`) | ✅ 완료 |
| **4단계** | 프론트엔드 연속 3·4단어 전용 컨트롤(N값 선택·최소 일치 수·상투어 제외·1단어 간격 허용·구문 칩 편집) 및 병합 하이라이트 구현 | Frontend (`templates/index.html`, `static/js/similar-search.js`, `static/js/passage-render.js`, `static/js/utils.js`, `static/css/search.css`) | ✅ 완료 |
| **5단계** | 연속 3·4단어 전용 단위·통합 테스트 작성 및 정적 검증 | Test (`tests/test_similar_search.py`) & Terminal 검증 | ✅ 완료 |

---

## 3. 세부 기술 스펙

### 3.1. [1단계] 문장 경계 존중 N-gram 추출 및 2중 노이즈 차단 (`gichul/services/similarity_search.py`)

#### (1) 전처리 및 문장·절 경계 분리 (`split_clean_segments`)
- 기존 본문 정제(`clean_passage_for_similarity`)에 아래 규칙을 보강합니다:
  1. 문단/선지 표식 제거: `(A)~(E)`, `(a)~(e)`, `(1)~(5)`, `①~⑤`, 밑줄/빈칸(`____`)을 공백이 아닌 **경계 구분자**로 치환하여 `a b c` (실측 275건), `a e a` (실측 200건) 같은 가짜 연속 구문 생성을 원천 차단.
  2. 문장 경계 분리: 마침표(`.`), 물음표(`?`), 느낌표(`!`), 세미콜론(`;`), 줄바꿈 기준으로 세그먼트를 분할(단, `Mr.`, `Dr.`, `U.S.`, `e.g.`, `i.e.`, 소수점 `3.5`는 기존 `sentence_tokenizer.py` 규칙으로 보호).
  3. 각 세그먼트 내부에서만 슬라이딩 윈도우로 연속 3단어(`3-gram`)와 연속 4단어(`4-gram`)를 생성해, 앞 문장 끝단어와 뒷 문장 첫단어가 억지로 이어지는 가짜 구문을 방지.

#### (2) 2중 상투 구문(노이즈) 필터 (`filter_informative_ngrams`)
1. **내용어 최소 포함 규칙**:
   - `fels_engine.FUNCTION_WORDS` + 일반 불용어를 제외한 **내용어(Content Word)** 개수를 검사:
     - **연속 3단어**: 내용어 **1개 이상** 필수 (예: `one of the`, `in order to`, `there is a`, `in front of` 자동 제외).
     - **연속 4단어**: 내용어 **1개 이상** 필수이며, 내용어가 1개뿐인 경우 해당 내용어가 초고빈도 일반어가 아닌 것만 채택 (`one of the most`, `on the other hand`, `at the same time` 자동 제외).
2. **코퍼스 문서 빈도(DF) 상한 필터 (토글 가능)**:
   - 기본값(`filter_common_ngrams=True`):
     - **연속 3단어**: `DF ≤ 30` (기본값, 사용자 조정 가능)
     - **연속 4단어**: `DF ≤ 10` (기본값, 사용자 조정 가능)
     - 도표 상투구(`the above graph shows` 등) 자동 제외.
   - 사용자가 UI에서 `상투 구문 포함`을 켜면 DF 상한을 해제해 모든 연속 구문 기준으로도 탐색 가능.

---

### 3.2. [2단계] FTS5 Phrase/NEAR 하이브리드 검색 및 전용 스코어링

#### (1) 전용 프리셋 3종 추가
기반 계획서의 5대 프리셋에 **연속 구문 전용 프리셋 3종**을 추가합니다:

| 프리셋 ID | 라벨 | 동작 방식 |
| :--- | :--- | :--- |
| `ngram_3` | 🔤 연속 3단어 기준 | 단락 내 유효 연속 3단어(3-gram) 일치 개수 및 희소도(IDF) 중심 순위화 |
| `ngram_4` | 🔎 연속 4단어 기준 | 단락 내 유효 연속 4단어(4-gram) 일치 개수 및 희소도(IDF) 중심 순위화 (변형 원문 추적 특화) |
| `ngram_3_4` | 🧩 연속 3+4단어 혼합 | 4단어 일치에 높은 가중치(2.0배), 3단어 일치에 기본 가중치(1.0배)를 부여해 정밀도·재현율 동시 확보 |

#### (2) 후보 회수 전략 (메모리 절약 + 초고속)
- **정확 일치 모드 (`allow_gap = 0`, 기본값)**:
  - 추출된 유효 3단어/4단어 구문(IDF 상위 최대 60개, 배치 분할)을 기존 `passages_fts`의 FTS5 Phrase Query(`"w1 w2 w3" OR "w2 w3 w4" ...`)로 1차 후보 회수(수 ms, 별도 대용량 3·4-gram 역색인 RAM 0MB!).
  - 회수된 후보 지문 본문에 대해 전체 유효 구문 집합과의 정확한 교집합(`matched_ngrams_3`, `matched_ngrams_4`)을 계산.
- **간격 허용 모드 (`allow_gap = 1` 또는 `2`, 선택 옵션)**:
  - 변형 문제에서 형용사·부사 1~2단어만 중간에 삽입된 경우(예: `phase shift like` → `rapid phase shift like`)를 포착하기 위해 FTS5 `NEAR("w1" "w2" "w3", gap)` 쿼리로 확장 회수하고, 후보 본문 내 토큰 거리 검증 후 보조 점수(정확 일치 대비 0.7배)로 반영.

#### (3) 연속 구문 전용 점수 산식 및 최소 일치 수 필터
- **최소 일치 구문 수 필터 (`min_ngram_hits`)**:
  - 기본값 `1` (1개 이상 일치 시 노출), 교사가 `2개 이상` / `3개 이상`으로 상향해 노이즈를 더욱 엄격히 차단 가능.
- **정렬 점수**:
  - 각 일치 구문 $g$의 희소 가중치 $w(g) = \ln\left(\frac{N + 1}{DF(g) + 1}\right) + 1$ (4단어 구문은 1.5~2.0배 보너스)를 합산하고 단락 내 유효 구문 총 가중치로 정규화하여 **0~100% 점수**와 **실제 일치 구문 개수(`ngram_hit_count`)**를 함께 반환.
  - 동점 시 `4단어 일치 개수 DESC → 3단어 일치 개수 DESC → 최신 연도 DESC` 순으로 정렬.

---

### 3.3. [3단계] REST API 파라미터 및 응답 확장 (`gichul/routers/search.py`)

#### (1) `POST /api/search/similar/extract` 응답 필드 추가
```json
{
  "word_count": 60,
  "proper_nouns": [...],
  "phrases": [...],
  "keywords": [...],
  "ngrams_3": [
    {"term": "human geography is", "df": 1, "idf": 8.7},
    {"term": "phase shift like", "df": 1, "idf": 8.7}
  ],
  "ngrams_4": [
    {"term": "human geography is becoming", "df": 1, "idf": 8.7},
    {"term": "particles in quantum physics", "df": 1, "idf": 8.7}
  ],
  "filtered_common_count": 4
}
```

#### (2) `POST /api/search/similar` 요청/응답 필드 추가
- **요청 파라미터 추가**:
  - `preset`: 기존 5종 + `"ngram_3"` | `"ngram_4"` | `"ngram_3_4"`
  - `ngram_mode`: `Optional[str] = None` (`"3"` | `"4"` | `"3_4"`) — 종합 모드와 병행하거나 단독 실행 제어
  - `min_ngram_hits: int = 1` (최소 일치 구문 개수: 1, 2, 3...)
  - `filter_common_ngrams: bool = True` (고빈도 상투 구문 DF 자동 제외 여부)
  - `max_df_3gram: int = 30`, `max_df_4gram: int = 10`
  - `allow_gap: int = 0` (`0`: 완전 연속 일치, `1`: 중간 1단어 삽입 허용, `2`: 최대 2단어 허용)
  - `selected_ngrams: Optional[List[str]] = None` (사용자가 칩 편집기로 남긴 3·4단어 구문 목록)
  - `required_ngrams: Optional[List[str]] = None` (필수 포함 `★` 고정한 3·4단어 구문)
- **결과 항목(`items[]`) 추가 필드**:
  - `matched_ngrams_3: List[str]`
  - `matched_ngrams_4: List[str]`
  - `ngram_hit_count: int` (중복 제거된 고유 일치 구문 수)
  - `merged_matched_spans: List[str]` (연속 겹침 구문을 병합한 원문 표시용 스팬 — 예: `"a b c"` + `"b c d"` → `"a b c d"`)

---

### 3.4. [4단계] 프론트엔드 UI/UX 및 겹침 구문 병합 하이라이트

1. **연속 구문 전용 컨트롤 바 (`#similarNgramOptionsBar`)**:
   - `연속 3단어` / `연속 4단어` / `연속 3+4단어` 프리셋 선택 시 즉시 노출:
     - **연속 길이**: `[ 3단어 ]` `[ 4단어 ]` `[ 3+4단어 ]`
     - **최소 일치 수**: `[ 1개 이상 ▾ ]` (`1개` / `2개` / `3개` / `5개`)
     - **상투 구문 제외 토글**: `[ ✓ 상투어 자동 제외 ]` (제외된 상투어 개수 툴팁 표시)
     - **변형 간격 허용**: `[ 완전 연속 ▾ ]` (`완전 연속(0)` / `1단어 삽입 허용` / `2단어 삽입 허용`)
2. **추출 3·4단어 구문 칩 패널**:
   - 🟠 **연속 3·4단어 구문 칩** 행 추가: 각 칩에 희소도/DB 출현 건수 미니 배지(`DB 1건` 등) 표기.
   - 클릭 시 `★ 필수 포함` 토글, `×` 클릭 시 제외.
3. **겹침 구문 병합 하이라이트 (`mergeOverlappingSpans`)**:
   - 예컨대 원문에서 `"matter transitions from solid"`와 `"transitions from solid to"`가 연속으로 겹쳐 일치한 경우, 쪼개서 칠하지 않고 하나의 연속 스팬 `"matter transitions from solid to"`로 병합해 깔끔하게 형광펜 처리.
   - 결과 카드 배지: `🔎 4단어 4건 · 3단어 7건 일치` 형태로 직관적 근거 제시, 카드 클릭 시 2×2 상세 뷰어의 TXT 패널에도 동일 병합 형광펜 유지.

---

### 3.5. [5단계] 테스트 및 검증 계획 (`tests/test_similar_search.py`)

- **신규 테스트 케이스**:
  1. **문장 경계 차단**: 마침표·물음표·줄바꿈을 넘나드는 가짜 3·4-gram이 생성되지 않음 검증.
  2. **기출 표식 노이즈 차단**: `(A) ... (B) ... (C)` 및 `(a)~(e)` 표식이 제거되어 `a b c` 같은 가짜 3-gram이 생성되지 않음 검증.
  3. **상투 구문 2중 필터**: `one of the`, `in order to`, `on the other hand`가 기본 필터에서 제외되고, `filter_common_ngrams=False` 시 포함됨 검증.
  4. **연속 3단어 vs 4단어 정밀도 검증**: 1~2문장만 발췌·변형한 쿼리로 `ngram_4` 검색 시 원 기출 지문이 1위로 정확히 매칭됨 검증.
  5. **최소 일치 수(`min_ngram_hits`) & 간격 허용(`allow_gap=1`)**: 1단어 삽입 변형 문장 탐지 및 최소 일치 수 미달 후보 필터링 검증.
  6. **겹침 스팬 병합(`mergeOverlappingSpans`)**: 인접·중첩 3·4-gram이 단일 연속 구문 스팬으로 병합됨 검증.
- **정적 검증 명령**:
  ```powershell
  python -m py_compile gichul/services/similarity_search.py gichul/routers/search.py
  node --check static/js/similar-search.js static/js/passage-render.js
  python -m pytest tests/test_similar_search.py -q
  ```
