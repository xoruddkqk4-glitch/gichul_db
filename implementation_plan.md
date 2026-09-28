# Implementation Plan - 데이터 초고속 검색 아키텍처 구축 (Speed-First Optimization)

## 1. 개요 및 배경

### 1.1 현재 상황 및 병목 원인 진단
사용자의 핵심 요구사항은 **"데이터 검색 속도를 좀 더 빠르게 해줘. 이 프로그램의 가장 큰 장점이 속도 이어야 해"**입니다.
현재 검색 시 화면에 `"데이터를 검색하고 있습니다..."` 스피너가 길게 체감되는 원인을 정밀 프로파일링한 결과, 다음과 같은 심각한 병목들이 확인되었습니다:

1. **과도한 페이로드 크기 (Payload Bloat: 15.4MB ~ 30.4MB)**
   - 지문 검색(`passages` 14,399건) 시 `SELECT p.*`로 인해 `explanation_text`(상세 해설 수 KB), `passage_text`, `script_text`, `choice_rates` 등 대용량 텍스트가 모두 직렬화되어 한 번에 **30.4MB**가 전송됨 (네트워크 전송만 약 1초 소요).
   - 문장 검색(`sentences` 71,872건) 시 학년 필터 하나만 걸어도 29,731건의 데이터가 한꺼번에 실려 **15.4MB**가 전송되고 브라우저가 수초간 멈춤.
2. **N+1 태그 쿼리 분할 실행 오버헤드**
   - `search_passages`에서 지문 ID 목록을 900개씩 chunk 분할하여 최대 16회의 추가 SQL 쿼리를 반복 실행(`passage_tags` 테이블)하고, 수만 번의 Python dict 매핑 루프가 CPU 시간을 소모.
3. **LIKE '%keyword%' 풀스캔 방식에 의한 DB 부하**
   - 현재 `whole_word=False`(기본값)일 때 14,000개 지문과 71,000개 문장 텍스트 전체를 `LIKE '%...%'`로 무차별 전체 테이블 풀스캔(Full Table Scan) 수행 (키워드 1개당 DB 조회에만 350~500ms 소요).
   - 이미 구축된 FTS5(전문 검색 가상 테이블 `passages_fts`, `sentences_fts`)가 있음에도 `whole_word=True` 옵션을 켤 때만 제한적으로 사용됨.
4. **브라우저 메인 스레드 렌더링 블로킹**
   - 30MB에 달하는 JSON을 `await res.json()`으로 파싱하고 수천~수만 개의 DOM 노드를 한꺼번에 다루느라 JavaScript 엔진(V8)의 힙 메모리 폭증 및 화면 렌더링 락(Freeze) 발생.

---

## 2. 최적화 목표 (Target Metrics)

| 구분 | 현재 상태 (Before) | 최적화 목표 (After) | 개선 효과 |
|---|---|---|---|
| **키워드 검색 DB 소요 시간** | 350ms ~ 570ms | **3ms ~ 15ms** | **95% 이상 단축** |
| **단일 검색 페이로드 크기** | 15.4MB ~ 30.4MB | **200KB ~ 800KB** | **97% 페이로드 감량** |
| **첫 화면 체감 렌더링 속도** | 1.8초 ~ 3.5초 | **0.1초 (100ms 이내 즉각 표출)** | **즉각 반응(Instant UI)** |
| **반복 검색 / 필터 전환** | 1,000ms+ | **1ms ~ 5ms (인메모리 캐시)** | **체감 딜레이 0초** |

---

## 3. 핵심 아키텍처 및 구현 계획

### 🚀 전략 1: FTS5 전문 검색 상시 가속화 (DB 검색 350ms → 5ms)
- **개념**: 단어 검색뿐만 아니라 일반 키워드 검색 시에도 FTS5 전문 검색 인덱스를 최우선 활용하도록 개선.
- **적용 방안**:
  - `keyword` 입력 시 FTS5 쿼리 문법으로 접두사(prefix) 검색(`keyword*`)을 우선 시도.
  - FTS5 매칭 결과를 기반으로 커버링 인덱스를 활용하여 지문/문장 ID를 2~3ms 만에 빠르게 픽업.
  - 한글/특수 키워드의 경우에도 최적화된 FTS 서브쿼리 및 SQLite 인덱스 복합 조건(`idx_passages_area`, `idx_exams_filter`)을 결합하여 풀스캔 완전 제거.

### 🚀 전략 2: N+1 태그 쿼리 단일화 (GROUP_CONCAT 최적화)
- **개념**: 검색 결과 지문들의 태그를 가져오기 위해 16번씩 추가 쿼리를 날리는 chunk 루프 제거.
- **적용 방안**:
  - `passages` 검색 시 서브쿼리 또는 `LEFT JOIN (SELECT passage_id, GROUP_CONCAT(tag_name, '||') as tag_list FROM passage_tags GROUP BY passage_id)`를 활용하거나, 단일 윈도우 함수/단일 배치 쿼리로 1번에 태그를 로드.
  - 파이썬 레벨의 불필요한 루프 오버헤드를 100% 제거.

### 🚀 전략 3: 페이로드 프로젝션 경량화 (Payload Projection: 30MB → 500KB)
- **개념**: 목록/그리드/테이블 뷰에서 당장 필요하지 않은 대용량 필드(`explanation_text` 전문, 중복 텍스트)를 목록 API에서 배제하거나 요약본만 전달.
- **적용 방안**:
  - `GET /api/search/passages` 응답 시:
    - 목록 및 2x2 카드 렌더링에 꼭 필요한 컬럼(`id`, `q_num`, `question_title`, `question_type`, `passage_text`, `grade`, `year`, `month`, `exam_type`, `correct_rate`, `tags`)만 선택 조회(`SELECT`).
    - 해설 전문(`explanation_text`)은 지문 상세 조회(`GET /api/passages/{id}`) 시 지연 로딩(Lazy Loading)하거나, 목록에서는 첫 100건만 즉시 포함하고 나머지는 스트리밍 제공.
  - 불필요한 직렬화 데이터 제거로 JSON 파싱 시간 90% 이상 단축.

### 🚀 전략 4: 백엔드 인메모리 고속 캐시 레이어 (Memory Cache Layer)
- **개념**: 자주 조회되는 학년/연도/유형별 기출 데이터셋을 프로세스 메모리에 캐싱.
- **적용 방안**:
  - `functools.lru_cache` 또는 TTL 기반 전용 `SearchCache`(128MB 상한)를 신설.
  - 동일한 검색 파라미터(예: `area=reading&grade=고3`, `keyword=빈칸` 등)가 요청될 경우 DB 접근 자체를 건너뛰고 **1ms 이내**에 캐시된 압축 JSON 바이트를 즉각 스트리밍 응답(`Content-Encoding: gzip`).
  - 신규 파일 업로드 또는 문제 수정 시 캐시 무효화(`cache.clear()`) 트리거 연동.

### 🚀 전략 5: 프론트엔드 가상화 및 점진적 0.1초 청크 렌더링 (Progressive Chunk Rendering)
- **개념**: 1만 건의 데이터가 들어오더라도 사용자의 눈에 보이는 첫 50~100건을 10ms 안에 먼저 띄우고, 로딩 스피너를 즉시 닫음.
- **적용 방안**:
  - `search.js` / `results-passage.js` / `results-sentence.js`:
    - 검색 응답을 받자마자 첫 번째 50개 항목을 즉각 DOM에 렌더링하고 `loadingIndicator.style.display = "none"` 처리!
    - 사용자는 검색 버튼을 누르자마자 0.1초 만에 결과가 뜬 것으로 체감.
    - 나머지 데이터는 `requestIdleCallback` 또는 `setTimeout(..., 0)`을 통해 브라우저가 유휴 상태일 때 백그라운드에서 부드럽게 점진적으로 렌더링하거나 가상 스크롤(Virtual Windowing)을 유지.

---

## 4. 단계별 구현 대상 파일 및 작업 내역

1. **`database.py` (백엔드 DB 쿼리 엔진)**
   - `search_passages`:
     - FTS5 접두사 매칭 우선 라우팅 적용.
     - `p.*` 대신 경량화된 컬럼 프로젝션 적용.
     - 900개 청크 분할 N+1 쿼리 제거 및 `GROUP_CONCAT` 단일 조인화.
   - `search_sentences`:
     - 문장 FTS5 접두사 인덱스 연동.
     - 불필요 컬럼 제거 및 복합 인덱스(`idx_sentences_pid_order`, `idx_exams_filter`) 최적화 활용.
2. **`app.py` (FastAPI 엔드포인트 및 인메모리 캐시)**
   - `SearchQueryCache` 인메모리 캐시 모듈 적용: 동일 쿼리 1ms 즉시 반환.
   - 대용량 응답에 대해 gzip 압축 버퍼 스트리밍 최적화.
   - 지문 개별 상세 해설 지연 조회 엔드포인트 보강 (`GET /api/passages/{id}/detail`).
3. **`static/js/search.js` & `static/js/results-passage.js` & `static/js/results-sentence.js` (프론트엔드)**
   - 첫 50개 항목 0.1초 즉시 렌더링(`Fast-path Initial Render`) 및 스피너 즉시 닫기.
   - 백그라운드 점진적 청크 병합(`requestAnimationFrame` / `requestIdleCallback`).
   - 사용자가 스크롤을 내릴 때 지연 로딩 처리로 DOM 메모리 점유 최소화.

---

## 5. 검증 및 벤치마크 계획

1. **DB 쿼리 시간 측정**:
   - `keyword='climate'` 검색: 350ms $\rightarrow$ 10ms 이내 확인.
   - `grade='고3'` 전체 지문 검색: 460ms $\rightarrow$ 30ms 이내 확인.
2. **HTTP API 응답 시간 및 페이로드 크기 측정**:
   - 페이로드: 30MB $\rightarrow$ 1MB 이하 압축 전송 확인.
   - API 응답 속도: 1,800ms $\rightarrow$ **50ms ~ 100ms** (캐시 히트 시 **2ms**) 확인.
3. **UI 렌더링 체감 속도 검증**:
   - 검색 버튼 클릭 시 `"데이터를 검색하고 있습니다..."` 문구가 오래 멈추지 않고, **0.1초 만에 즉시 닫히며 첫 화면 결과가 즉시 표시**되는지 터미널 정적 검증 및 응답 시간 측정으로 확인.

---

> [!NOTE]
> 본 문서는 `/ask` 모드 정책(Rule 5)에 따라 작성된 기술 구현 계획서입니다.  
> 실제 소스 코드 수정은 진행되지 않았으며, 사용자의 명시적인 `/apply` 명령어 수신 시에만 단계별 코드 반영이 시작됩니다.
