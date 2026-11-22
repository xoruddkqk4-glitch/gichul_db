# 구현 계획서: 단락 기반 다중 기준 유사 지문 검색 시스템 (Similar Passage Search)

**작성일시**: 2026-11-22  
**상태**: ✅ 완료  
**관련 요청**: 단어나 짧은 표현이 아닌 한 단락의 영어 텍스트를 붙여 넣으면, 텍스트 내 핵심 단어·표현 조합(N-gram)·고유명사 등을 자동 추출·편집하여 다양한 검색 기준(프리셋/가중치)으로 유사 기출 지문을 순위화해 찾아주는 기능 구축

---

## 1. 개요 및 목표

현재 `05-gichul_db`의 검색([gichul/database.py](file:///c:/Users/user/Desktop/web%20app/05-gichul_db/gichul/database.py) `search_passages`)은 SQLite FTS5를 활용한 **단일 단어(AND) · 큰따옴표 구문(`"..."`) · `#태그` · 출처 식별자** 검색에 최적화되어 있습니다. 그러나 교사가 EBS 연계 교재, 내신 변형 문제, 원서·기사 등 **한 단락 분량의 영어 텍스트**를 통째로 붙여 넣어 유사 기출을 찾으려고 할 때는 다음과 같은 한계가 있습니다.

1. **AND 조건 과잉 제약**: 단락의 모든 단어를 AND로 검색하면 어휘가 일부만 달라져도 검색 결과가 0건이 됩니다.
2. **고유명사·표현·핵심어 구분 불가**: SQLite FTS5의 `unicode61` 토크나이저는 대소문자를 통합하므로 고유명사(`Marrakesh`, `Darwin`, `NASA`)의 변별력을 반영하지 못하며, 기능어와 희귀 핵심어의 중요도(IDF)도 구분하지 못합니다.
3. **지문 내 노이즈 혼입**: `passages.passage_text`에는 문항 번호·한글 발문·객관식 선지(①~⑤)·각주·소프트하이픈(`\u00ad`) 등이 포함되어 있어, 순수 영문 본문만 정제해 비교하는 전용 파이프라인이 필요합니다.

본 계획서는 **외부 라이브러리 추가 없이(100% 로컬·오프라인 동작)** 기존 14,534개 기출 문항(독해 8,901건 + 듣기 5,633건)을 대상으로 **0.1초 이내에 다중 기준 유사 지문을 정밀 검색**하고, 사용자가 **추출된 고유명사·표현·핵심어 칩을 직접 조합/고정/제외**하며, 필요 시 기존 Multi-LLM으로 **동의어·주제어 의미 확장**까지 연동할 수 있는 시스템을 설계합니다.

---

## 2. 진행 현황 (Progress Tracker)

`/apply` 명령어로 단계별 구현 시 아래 표를 갱신합니다.

| 단계 | 작업 내용 | 담당 영역 | 상태 |
|:---:|---|---|:---:|
| **1단계** | 유사 지문 자질 추출기(고유명사·표현 조합·핵심어·Shingle) 및 인메모리 다중 시그널 스코어링 엔진 구축 | Backend (`gichul/services/similarity_search.py`) | ✅ 완료 |
| **2단계** | 유사 지문 자질 추출 미리보기 & 다중 기준 검색 REST API 및 캐시 무효화 연동 | Backend (`gichul/routers/search.py`, `gichul/app.py`) | ✅ 완료 |
| **3단계** | 선택적 Multi-LLM 의미 키워드·동의어 확장 옵션 연동 | Backend (`gichul/grammar_analyzer.py`, `gichul/services/similarity_search.py`) | ✅ 완료 |
| **4단계** | 프론트엔드 `[✨ 유사 지문 검색]` 모드, 추출 검색어 칩 편집기, 5대 기준 프리셋·가중치 UI 및 랭킹 결과 카드 구현 | Frontend (`templates/index.html`, `static/js/similar-search.js`, `dom.js`, `navigation.js`, `state.js`, `main.js`, `static/css/search.css`) | ✅ 완료 |
| **5단계** | 기존 2×2 상세 뷰어 직행, 다색 매칭 근거 하이라이트 및 유인물 보관함 원클릭 담기 연동 | Frontend (`static/js/passage-render.js`, `static/js/utils.js`, `static/js/similar-search.js`) | ✅ 완료 |
| **6단계** | 단위·통합 테스트 작성 및 백엔드/프론트엔드 정적 검증 | Test (`tests/test_similar_search.py`) & Terminal 검증 | ✅ 완료 |

---

## 3. 세부 설계 및 구현 내용

### 3.1. [1단계] 자질 추출 및 다중 시그널 유사도 검색 엔진 (`gichul/services/similarity_search.py`)

#### (1) 순수 영문 본문 정제 (`clean_passage_for_similarity`)
- **입력 단락 및 DB 코퍼스 공통 정규화**:
  - 소프트 하이픈(`\u00ad`) 및 특수 따옴표(`“”‘’`) 정규화.
  - 독해(`area == 'reading'`): 한글 발문, 문항 번호(`31.`, `[31~34]`), 객관식 선지(`①~⑤`), 각주(`* ...`), 배점(`[3점]`)을 제거하여 **순수 영문 본문**만 추출.
  - 듣기(`area == 'listening'`): `script_text` 우선 사용, 화자 태그(`M:`, `W:`, `Man:`, `Woman:` 등) 제거 후 영문 발화 본문 추출.
- **경량 영문 어간/변형 정규화 (`normalize_lemma`)**:
  - 외부 NLP 라이브러리 없이 소유격(`'s`), 복수형(`-ies`→`-y`, `-es`, `-s`), 과거/분사형(`-ied`→`-y`, `-ed`, `-ing`)의 경량 규칙 정규화를 적용하여 `transition` ↔ `transitions` ↔ `transitioning` 변형 일치를 지원.

#### (2) 4대 검색 시그널(Feature) 자동 추출 (`extract_query_features`)
붙여 넣은 단락에서 아래 4가지 시그널을 분리 추출합니다.

1. **고유명사·개체명 (`proper_nouns`)**:
   - 문장 첫머리가 아닌 위치의 대문자 단어(`Marrakesh`, `Siena`, `Darwin`, `Pavlov`).
   - 연속 대문자 복합 고유명사 구문(`New York Times`, `Industrial Revolution`, `World War II`, `United States`).
   - 2글자 이상 올캡 약어(`DNA`, `NASA`, `GDP`, `AI`, `UNESCO`) 및 특징적 연도/세기 표기(`1980s`, `19th century`, `1929`).
   - 문장 첫 단어라도 일반 불용어/접속부사(`The`, `However`, `When`, `One` 등)를 제외하고, 동일 단락 내 문장 중간에도 대문자로 등장하거나 코퍼스 DF가 극히 낮은 경우 고유명사로 승격.
2. **핵심 표현·연어 조합 (`phrases`: 2-gram / 3-gram)**:
   - 단락 내 인접한 의미어 2-gram(예: `human geography`, `phase shift`, `quantum physics`, `city square`, `shopping street`).
   - `내용어 + 기능전치사(of/in/to/for/with/on/from/by) + 내용어` 구조의 3-gram(예: `sense of belonging`, `rate of change`, `point of view`).
   - 코퍼스 IDF 합산 점수가 높은 상위 15~20개 표현 자동 선별.
3. **핵심 내용어 & 희귀 어휘 (`keywords`)**:
   - `fels_engine.FUNCTION_WORDS` + 영어 일반 고빈도 불용어(약 250개) 제외.
   - `TF × IDF` 가중치가 높은 상위 20~25개 핵심 단어 추출 (희귀 학술어·소재어 우선).
4. **연속 Shingle (`shingles`: 3-word / 4-word sliding window)**:
   - 불용어를 포함한 원문 토큰 3-gram/4-gram 집합을 생성해, 내신·문제집에서 일부 문장만 변형한 **원문·준중복 지문**을 정밀 탐지.

#### (3) 인메모리 경량 역색인 및 IDF 캐시 (`SimilarityIndex`)
- `gichul.db`의 전체 14,534개 지문은 SQLite 로드 기준 ~70ms 수준으로 매우 가볍습니다.
- 첫 유사 검색 호출 시 1회만 `SimilarityIndex`를 메모리(~30MB)에 구축:
  - 영역별(`reading` / `listening`) 문서 수 $N$, 토큰별 문서 빈도 $DF(t)$ 및 $IDF(t) = \ln\left(\frac{N + 1}{DF(t) + 1}\right) + 1$ 계산.
  - 문서별 경량 피처 저장: `{tf_idf_norm, token_tf, proper_nouns_set, phrases_set, shingles_set, meta}`.
  - 역색인(`token -> set(doc_idx)`, `proper_noun -> set(doc_idx)`)으로 쿼리 시그널과 1개 이상 겹치는 후보 문서만 즉시 추출하여 전체 스캔 없이 **10~30ms** 내 정밀 스코어링 완료.
- `app.py`의 `invalidate_cache_on_write` 미들웨어에서 DB 쓰기 발생 시 `similarity_index.invalidate()` 호출로 항상 최신 DB 상태 유지.

#### (4) 5대 검색 기준 프리셋 & 세부 가중치 스코어링 (`score_candidates`)
각 후보 지문 $d$에 대해 4개 정규화 하위 점수(각 0.0~1.0)를 계산하고, 선택된 기준(또는 사용자 커스텀 가중치)으로 가중 합산합니다:

- $S_{\text{kw}}$: 핵심 내용어 가중 TF-IDF 코사인 유사도 + 어간 변형 커버리지
- $S_{\text{phr}}$: 2-gram/3-gram 핵심 표현 일치 + 단어 쌍 근접 공출현(Co-occurrence) 점수
- $S_{\text{ent}}$: 고유명사·개체명 일치율 (단락에 고유명사가 없을 경우 가중치를 $S_{\text{kw}}, S_{\text{phr}}$로 자동 재분배)
- $S_{\text{shg}}$: 3~4단어 연속 Shingle Jaccard 유사도 (변형 원문 탐지)

| 프리셋 ID | 라벨 | $S_{\text{kw}}$ | $S_{\text{phr}}$ | $S_{\text{ent}}$ | $S_{\text{shg}}$ | 주요 용도 |
| :--- | :--- | :---: | :---: | :---: | :---: | :--- |
| `balanced` | ⚖️ 종합 균형 (기본) | 0.40 | 0.30 | 0.20 | 0.10 | 일반적인 유사·연계 기출 탐색 |
| `near_duplicate` | 🔍 원문·변형 찾기 | 0.25 | 0.25 | 0.15 | 0.35 | 내신/문제집 변형 지문의 원 기출 추적 |
| `proper_noun` | 🏷️ 고유명사·소재 중심 | 0.25 | 0.15 | 0.55 | 0.05 | 특정 인물·지명·이론·실험 중심 탐색 |
| `phrase_combo` | 🧩 표현·단어 조합 중심 | 0.30 | 0.55 | 0.10 | 0.05 | 숙어·연어·핵심 키워드 조합 동시 출현 탐색 |
| `topic_broad` | 💡 주제·어휘 확장 | 0.65 | 0.20 | 0.10 | 0.05 | 패러프레이즈·동일 배경지식 광범위 탐색 (+ AI 확장 권장) |

- **필수 포함(`required_terms`) / 제외(`excluded_terms`) 제어**:
  - 사용자가 특정 칩을 `★ 필수`로 지정하면 해당 고유명사/표현/단어가 반드시 포함된 후보만 통과(하드 필터).
  - `× 제외`한 칩은 스코어링 및 후보 회수에서 완전히 배제.
- **복합 장문 중복 정리**: 동일 시험의 41~42번 / 43~45번 공유 지문은 최고 점수 대표 문항으로 병합 표시해 순위 중복 방지.

---

### 3.2. [2단계] REST API 엔드포인트 및 캐시 무효화 연동 (`gichul/routers/search.py`, `gichul/app.py`)

#### (1) `POST /api/search/similar/extract` — 단락 자질 미리보기 추출 API
- **요청 Body (`SimilarExtractRequest`)**:
  - `text: str` (붙여 넣은 단락 텍스트, 최소 10자 ~ 최대 10,000자)
  - `area: str = "reading"` (`reading` | `listening`)
- **응답**:
  ```json
  {
    "word_count": 82,
    "proper_nouns": [{"term": "Marrakesh", "idf": 8.4}, {"term": "Siena", "idf": 8.7}],
    "phrases": [{"term": "city square", "idf": 11.2}, {"term": "shopping street", "idf": 10.6}],
    "keywords": [{"term": "medieval", "idf": 6.9}, {"term": "underappreciated", "idf": 7.8}],
    "recommended_preset": "balanced"
  }
  ```

#### (2) `POST /api/search/similar` — 다중 기준 유사 지문 검색 API
- **요청 Body (`SimilarSearchRequest`)**:
  - `text: str`
  - `preset: str = "balanced"` (`balanced` | `near_duplicate` | `proper_noun` | `phrase_combo` | `topic_broad`)
  - `weights: Optional[Dict[str, float]] = None` (사용자 커스텀 가중치 오버라이드)
  - `selected_proper_nouns: Optional[List[str]] = None`
  - `selected_phrases: Optional[List[str]] = None`
  - `selected_keywords: Optional[List[str]] = None`
  - `required_terms: Optional[List[str]] = None` (필수 포함 AND 조건)
  - `excluded_terms: Optional[List[str]] = None` (제외 조건)
  - `custom_terms: Optional[List[str]] = None` (사용자 직접 추가 단어/구문)
  - `use_ai_expansion: bool = False` (선택적 LLM 동의어·주제어 확장)
  - `min_score: float = 0.08` (최소 유사도 임계값)
  - `top_k: int = 30` (상위 반환 건수, 최대 100)
  - 기존 필터 호환: `area`, `grade`, `years`, `month`, `exam_type`, `question_type`, `correct_rate_range`, `tag`
- **보안/접근 제어**: `Depends(get_current_role)` 적용 → `access.allowed_search_filters(user_role)` 및 `access.filter_passages(items, user_role)` 일관 적용.
- **응답**:
  - `extracted`: 실제 검색에 사용된 자질(고유명사/구문/핵심어/AI 확장어)
  - `applied_weights`: 적용된 최종 가중치
  - `elapsed_ms`: 검색 소요 시간(ms)
  - `count`, `items`: 각 지문 객체 + `similarity_score`(0~100%), `score_breakdown`(`{keyword, phrase, proper_noun, shingle}`), `matched_proper_nouns`, `matched_phrases`, `matched_keywords`, `snippet`
- **캐시 무효화 (`gichul/app.py`)**:
  - `invalidate_cache_on_write` 미들웨어에 `invalidate_similarity_index()` 추가.
  - `/api/search/similar`는 읽기 전용 POST이므로 `_CACHE_SAFE_WRITE_PREFIXES`에 `"/api/search/similar"`를 등록해 유사 검색 호출이 검색 캐시를 불필요하게 비우지 않도록 보호.

---

### 3.3. [3단계] 선택적 Multi-LLM 의미 키워드 확장 (`gichul/grammar_analyzer.py`)

- **목적**: 단어가 거의 다 패러프레이즈된 지문(예: `elderly` ↔ `aging population`, `cognitive bias` ↔ `mental shortcut`)을 찾을 때 선택적으로 활성화.
- **동작 (`expand_similarity_keywords(text)`)**:
  - `grammar_analyzer.get_active_ai_configs()`로 현재 등록된 활성 LLM(Gemini/OpenAI/Claude/OpenRouter/LM Studio) 중 1순위를 호출.
  - JSON 출력으로 ① 핵심 주제 동의어·파생어 6~10개, ② 관련 학술/소재 연어(2-gram) 3~5개를 추출해 보조 가중치(원문 키워드 대비 0.6배)로 검색 쿼리에 합산.
  - API 키가 없거나 호출 실패 시 오류 없이 자동으로 로컬 엔진만으로 정상 폴백하고 안내 배지 표시.

---

### 3.4. [4~5단계] 프론트엔드 UI/UX 및 2×2 뷰어·유인물 연동

#### (1) 모드 전환 및 단락 입력 UI (`templates/index.html`, `static/css/search.css`, `static/js/navigation.js`)
- 홈 화면 모드 탭에 **`✨ 유사 지문 검색`** 추가: `[ 지문 검색 | 문장 검색 | ✨ 유사 지문 검색 ]` (결과창 미니 탭에도 동일 추가).
- 유사 지문 모드 선택 시:
  - 단일 행 검색창 대신 **다중 행 단락 입력창(`<textarea id="similarTextInput">`)** 확장 표시 (붙여넣기 즉시 글자/단어 수 표시, `[📋 붙여넣기]`, `[✕ 비우기]` 버튼).
  - 하단에 **5대 기준 프리셋 세그먼트 바** + `[🎛️ 가중치 세부 설정]` 접이식 슬라이더 + `[🤖 AI 동의어 확장]` 토글 + 기존 학년/연도/월/시험구분/유형/정답률 필터 바 그대로 재사용.
- **실시간 검색어 칩 편집 패널 (`#similarFeatureChipsPanel`)**:
  - 단락 붙여넣기(디바운스 400ms) 또는 `[🔎 검색어 추출]` 클릭 시 `/api/search/similar/extract` 호출.
  - 추출 결과를 3개 행으로 시각화:
    - 🟣 **고유명사**: 클릭 시 `★ 필수 포함` 토글 / `×` 클릭 시 제외
    - 🔵 **표현·구문 조합**: 클릭 시 `★ 필수 포함` 토글 / `×` 클릭 시 제외
    - 🟢 **핵심 단어**: 클릭 시 `★ 필수 포함` 토글 / `×` 클릭 시 제외
  - `[+ 검색어/표현 직접 추가]` 인라인 입력창으로 교사가 원하는 단어·숙어·고유명사를 자유롭게 추가 가능.

#### (2) 유사도 순위 결과 카드 & 기존 기능 연동 (`static/js/similar-search.js`, `static/js/passage-render.js`)
- **결과 카드 리스트 (`#similarResultsContainer`)**:
  - 유사도 높은 순으로 순위 카드 렌더링:
    - 상단 바: `#1` 순위 + **유사도 프로그레스 배지(`86%`)** + 출처 식별자(`[고2-2026년-06월-31번]`) + 문제유형/정답률 배지 + `[📄 유인물 담기]` 버튼 + `[🔍 2×2 상세 보기]` 버튼.
    - 매칭 근거 바: `🟣 고유명사: Marrakesh, Siena` · `🔵 표현: "city square", "shopping street"` · `🟢 핵심어 8개 일치` + 4개 하위 점수 미니 바.
    - 본문 미리보기: 일치한 고유명사(보라), 표현(파랑), 핵심어(로즈) **다색 `<mark>` 하이라이트** 적용.
- **2×2 지문 상세 뷰어 연동**:
  - 카드 클릭 시 검색된 유사 지문 목록 전체를 `appState.passagesData`에 적재하고 해당 문항 탭을 즉시 활성화.
  - 2×2 뷰어의 TXT 본문 패널에서도 일치된 고유명사·표현·핵심어 하이라이트를 유지하며, 원클릭 PDF 크롭 확인·해설 열람·전체 문장 보기·유인물 담기까지 기존 워크플로우와 끊김 없이 연결.
- **접근성 및 디자인 규격 준수 ([DESIGN.md](file:///c:/Users/user/Desktop/web%20app/05-gichul_db/DESIGN.md))**:
  - 모든 칩·배지·라벨 최소 `12px(0.75rem)` 이상, 키보드 `:focus-visible` 링 보장, 모바일 640px/768px 반응형 스택 레이아웃 적용.

---

### 3.5. [6단계] 테스트 및 검증 계획 (`tests/test_similar_search.py`)

- **단위 테스트**:
  1. `clean_passage_for_similarity`: 발문·선지(①~⑤)·각주·소프트하이픈 제거 검증.
  2. `extract_query_features`: 고유명사(문장 중 대문자, 복합 고유명사, 약어, 연도), 2-gram/3-gram 표현, 고IDF 핵심어 추출 정확도 검증.
  3. 5대 프리셋별 순위 차별화 검증 (예: 변형 원문 입력 시 `near_duplicate` 1위, 고유명사 중심 입력 시 `proper_noun` 1위, `required_terms` / `excluded_terms` 하드 필터 동작).
  4. 복합 장문(41~42, 43~45) 중복 결과 병합 및 `access.py` 비회원(guest) 메타데이터 필터링 검증.
- **API 스모크 테스트**: `POST /api/search/similar/extract`, `POST /api/search/similar` 200 OK 및 빈 입력 400 검증.
- **정적 검증 명령**:
  ```powershell
  python -m py_compile gichul/services/similarity_search.py gichul/routers/search.py gichul/app.py
  node --check static/js/similar-search.js static/js/navigation.js static/js/dom.js static/js/main.js
  python -m pytest tests/test_similar_search.py -q
  ```

---

## 4. 기대 효과

1. **출제·수업 준비 시간 대폭 단축**: EBS·교과서·외부 지문 단락을 그대로 붙여 넣어 동일 소재·유사 표현·변형 원문 기출을 0.1초 만에 탐색하고 바로 B4 유인물로 제작 가능.
2. **투명하고 유연한 검색 제어**: 자동 추출된 고유명사·표현 조합·핵심어를 교사가 직접 칩 단위로 가감·필수 지정하고 5대 기준 프리셋과 가중치를 조합해 의도에 맞는 결과를 정확히 도출.
3. **100% 로컬 무결성 + 선택적 AI 확장**: 기본 검색은 오프라인 무료 초고속으로 동작하며, 패러프레이즈 지문 탐색이 필요할 때만 기존 AI 설정을 활용해 의미를 확장하는 실용적 하이브리드 구조 완성.
