# Implementation Plan - 독해 ↔ 듣기 영역 전환 시 캡처 이미지 미노출 버그 해결 및 고속 캐시 최적화

## 1. 개요 및 배경

현재 지문 검색 화면에서 동일 모의고사 세트를 조회 중인 상태에서 상단 **독해(Reading) ↔ 듣기(Listening)** 영역 전환 버튼을 클릭하면, 문항 번호(1번 ↔ 18번)는 정상 이동하지만 **PDF 문항 캡처 이미지(또는 듣기 대본 크롭 이미지)가 표시되지 않고 "캡처 이미지가 생성되지 않았습니다" 플레이스홀더 상태로 머무는 현상**이 발생하고 있습니다.

본 계획서는 이 문제의 근본 원인을 정밀 분석하고, 영역 전환 시에도 0.00초 만에 100% 정상 캡처 이미지가 즉각 표출되도록 인메모리 캐시 아키텍처와 경량 프로젝션 쿼리를 개선하는 기술 계획을 정의합니다.

---

## 2. 현상 정밀 진단 및 근본 원인 규명

### 2.1 프론트엔드 `loadedExamsCache` (Set) 단방향 플래그 결함 (`results-passage.js`)
- **현재 로직**:
  ```javascript
  const loadedExamsCache = new Set();

  export async function ensureExamPassagesLoaded(examId) {
    if (!examId || loadedExamsCache.has(examId)) return; // 🚨 치명적 병목
    ...
    loadedExamsCache.add(examId);
  }
  ```
- **발생 메커니즘**:
  1. 사용자가 특정 시험(예: `[고2-2025년-06월]`)의 독해(18~45번)를 먼저 조회하면, `ensureExamPassagesLoaded("[고2-2025년-06월]")`가 호출되어 `loadedExamsCache.add("[고2-2025년-06월]")`가 등록됩니다.
  2. 사용자가 상단에서 **[듣기]** 영역 버튼을 누르면, `search.js`의 `executeSearch`가 실행되어 `appState.passagesData` 배열 전체가 듣기 문항(1~17번) 메타데이터 객체들로 **완전히 새로 교체**됩니다.
  3. 교체된 신규 듣기 1번 문항을 렌더링하기 위해 `ensureExamPassagesLoaded("[고2-2025년-06월]")`가 호출되지만, **`loadedExamsCache.has(examId)`가 이미 `true`이므로 아무 작업도 하지 않고 즉시 `return`**합니다!
  4. 결과적으로 새로 들어온 듣기 문항 객체들에 `pdf_crop_image`, `script_crop_image`, 본문 텍스트가 채워지지 않아, 화면에 **"🖼️ 문제지 캡처 이미지가 생성되지 않았습니다."** 플레이스홀더가 노출됩니다.
  5. 듣기에서 독해로 전환할 때도 동일한 메커니즘으로 인해 독해 18번 문항의 캡처가 안 된 상태로 보이게 됩니다.

### 2.2 `meta_only=true` 경량 프로젝션 쿼리의 캡처 이미지 경로 누락 (`database.py`)
- **현재 백엔드 쿼리 (`database.py:1253`)**:
  ```python
  if meta_only:
      select_clause = """
          p.id, p.exam_id, p.q_num, p.question_type, p.area, p.correct_rate,
          (p.passage_text IS NOT NULL AND LENGTH(p.passage_text) > 0) AS has_passage_text,
          e.grade, e.year, e.month, e.exam_type, e.subtype, e.reading_start_q, e.reading_end_q
      """
  ```
  - 검색 속도를 위해 대용량 텍스트(`passage_text`, `explanation_text`)를 제외하는 과정에서, **단 30바이트에 불과한 가벼운 이미지 URL 필드(`p.pdf_crop_image`, `p.script_crop_image`)까지 함께 제외**되어 있습니다.
  - 이로 인해 프론트엔드가 상세 API(`GET /api/exams/{id}/passages`)를 추가로 받아오기 전까지는 찰나의 순간에도 캡처 이미지를 그릴 수 없는 구조적 한계가 존재합니다.

---

## 3. 해결 목표 및 핵심 아키텍처

| 구분 | 현재 상태 (Before) | 개선 후 (After) | 기대 효과 |
|---|---|---|---|
| **영역 전환 시 캡처 표출** | 플레이스홀더 노출 (미캡처 상태) | **전환 즉시 100% 정상 캡처 노출** | 부드럽고 완벽한 영역 전환 UX |
| **`meta_only` 프로젝션** | `pdf_crop_image` 누락 | **이미지 경로(`pdf/script`) 포함** | 백그라운드 로딩 전에도 0초 즉각 캡처 표출 |
| **프론트엔드 시험 캐시** | `loadedExamsCache` (Set) | **`examFullPassagesCache` (Map)** | 메모리 재활용으로 네트워크 중복 요청 0회 (0ms 반응) |

---

## 4. 구체적 구현 계획

### 🚀 전략 1: `meta_only=true` 경량 쿼리에 캡처 이미지 필드 추가 (`database.py`)
- `database.py`의 `search_passages` 내 `meta_only` select_clause에 이미지 경로 컬럼 추가:
  ```sql
  p.id, p.exam_id, p.q_num, p.question_type, p.area, p.correct_rate,
  p.pdf_crop_image, p.script_crop_image,
  (p.passage_text IS NOT NULL AND LENGTH(p.passage_text) > 0) AS has_passage_text,
  e.grade, e.year, e.month, e.exam_type, e.subtype, e.reading_start_q, e.reading_end_q
  ```
- **효과**: 이미지 경로는 문자열 35바이트 수준으로 74KB 페이로드에 영향을 전혀 주지 않으면서(0.01MB 미만 증가), 영역 전환 시 브라우저가 상세 데이터를 비동기로 로드하기 전에도 **PDF 문항 및 대본 캡처 이미지를 0.00초 만에 즉각 렌더링**함.

### 🚀 전략 2: 프론트엔드 `examFullPassagesCache` (Map) 고속 인메모리 캐시 구축 (`results-passage.js`)
- 단순 `Set` 플래그 대신, 서버에서 가져온 45개 전체 문항 상세 데이터(`Map<passageId, passageData>`)를 메모리에 영구 보관:
  ```javascript
  const examFullPassagesCache = new Map(); // examId -> Map<passageId, itemData>
  ```
- **동작 방식**:
  1. `ensureExamPassagesLoaded(examId)` 호출 시:
     - 이미 `examFullPassagesCache.has(examId)`에 캐시가 존재하면:
       - 네트워크 요청 없이 즉시 메모리에서 현재 `appState.passagesData` 및 `appState.currentExamQuestions`에 상세 필드(`pdf_crop_image`, `script_crop_image`, `passage_text`, `explanation_text`, `fels_text`, `user_memo` 등)를 **0ms 동기 병합(Merge)**.
       - 활성 문항(`loadPassageDetail`)을 즉시 리프레시하여 캡처 이미지 완벽 표시.
     - 캐시가 없으면 서버(`GET /api/exams/{id}/passages`)에서 비동기로 받아와 `examFullPassagesCache.set(examId, freshMap)`에 저장 후 병합.
  2. 독해 ↔ 듣기 영역 전환으로 문항 리스트가 새로 생성되더라도, 메모리에 저장된 원본 상세 맵을 통해 0초 만에 완벽하게 복원.

### 🚀 전략 3: `loadPassageDetail` 및 `selectPassageTab` 시점 캡처 동기화 안전장치 (`results-passage.js`)
- `loadPassageDetail(p)` 진입 시:
  - 현재 문항 `p`의 `pdf_crop_image`나 `passage_text`가 비어있더라도, `p.exam_id`에 해당하는 캐시 맵(`examFullPassagesCache`)이 있으면 즉시 `Object.assign(p, cachedItem)`으로 채워주고 캡처 이미지를 렌더링.
  - 캐시가 없는 경우에만 `ensureExamPassagesLoaded(p.exam_id)`를 호출하도록 2중 안전망 구축.

---

## 5. 변경 대상 파일 및 작업 체크리스트

| 대상 파일 | 수정 항목 및 상세 내용 |
|---|---|
| **`database.py`** | `search_passages`의 `meta_only=True` 프로젝션 쿼리에 `p.pdf_crop_image`, `p.script_crop_image` 컬럼 추가 |
| **`static/js/results-passage.js`** | 1. `loadedExamsCache` (Set)을 `examFullPassagesCache` (Map)으로 전면 교체<br>2. `ensureExamPassagesLoaded`에서 캐시 히트 시 0ms 즉각 동기 병합 지원<br>3. `loadPassageDetail` 진입 시 캐시 맵 직접 조회 및 즉각 캡처 복원 안전장치 적용 |

---

## 6. 검증 계획

1. **영역 전환 런타임 검증**:
   - 고2-[2025-06] 등 임의의 시험지에서 독해(18번) 조회 $\rightarrow$ 캡처 이미지 정상 확인.
   - 상단 [듣기] 버튼 클릭 $\rightarrow$ 듣기 1번 문항으로 이동 시 **"캡처 이미지가 생성되지 않았습니다" 플레이스홀더 없이 문제지 캡처 + 대본 크롭 이미지가 100% 즉시 노출**되는지 확인.
   - 다시 [독해] 버튼 클릭 $\rightarrow$ 독해 18번 문항으로 복귀 시 캡처 이미지가 온전히 유지되는지 확인.
2. **정적 오류 검사 (Rule 2)**:
   - `python -m py_compile database.py` 파이썬 구문 오류 검사 (Exit Code: 0).
   - `node -c static/js/results-passage.js` 자바스크립트 문법 검사 (Exit Code: 0).

---

> [!NOTE]
> 본 문서는 **`/ask` 질의응답 및 계획 전용 모드 정책 (Rule 5)**에 따라 작성되었습니다.  
> 실제 소스 코드는 수정되지 않았으며, 계획서 내용을 검토하신 후 코드에 즉시 반영하시려면 **`/apply`** 명령어를 입력해 주시기 바랍니다.
