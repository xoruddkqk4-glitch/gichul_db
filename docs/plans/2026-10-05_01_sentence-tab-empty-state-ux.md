# Implementation Plan - 결과창 [문장] 탭 클릭 시 빈 검색어 안내 화면(Empty State) 분리 및 UX 개선

> [!IMPORTANT]
> `/ask` 모드로 작성된 계획서입니다. **자동으로 소스 코드를 수정하거나 실행하지 않습니다.**
> 사용자가 내용을 검토한 뒤 **`/apply`** 명령어를 입력했을 때만 실제 구현을 시작합니다.

- 관련 문의: 첫 화면에서 검색창에 아무것도 입력하지 않은 상태에서 검색했을 때, 문장 결과창에 특정 모의고사(`[고2-2026년-09월-18번]`) 문장이 노출되는 현상 개선 요청 (대안 B 채택)
- 계획서 목록 및 진행 상태: [docs/README.md](../README.md)

---

## 1. 개요 및 배경

현재 웹앱 첫 화면(Home)에서 검색창을 비워둔 채 [검색]을 누른 뒤 결과 화면 상단의 **`[지문] | [문장]`** 탭 중 **`[문장]`**을 클릭하면, 사용자가 검색어를 입력하지 않았음에도 **`[고2-2026년-09월-18번] 문항 전체 문장 (9개)`**가 화면에 표시됩니다.

사용자는 검색창이 비어 있으므로 빈 결과 또는 검색 안내 화면을 기대하지만, 내부적으로 최신 기출 1번 지문(`passagesData[0]`)으로 강제 연결되면서 사용자의 멘탈 모델과 충돌하는 문제가 발생합니다.

본 계획서는 사용자가 선택한 **[대안 B: 결과창 [문장] 탭 동작 분리 및 안내 빈 화면(Empty Guidance State) 제공]**을 구현하여, 검색어 없이 `[문장]` 탭으로 전환했을 때 임의의 지문 문장으로 직행하지 않고 친절하고 직관적인 검색 안내 화면을 제공하도록 개선하는 계획을 정의합니다.

---

## 2. 현상 정밀 진단 및 원인 규명

### 2.1 결과창 `[문장]` 탭의 `showSentencesForPassage` 무조건 호출 ([navigation.js:L221-L226](file:///c:/Users/user/Desktop/web%20app/05-gichul_db/static/js/navigation.js#L221-L226))
- **현재 코드**:
  ```javascript
  if (resultsTabModeSentence) {
    resultsTabModeSentence.addEventListener("click", () => {
      if (appState.currentMode === "sentence") return;
      showSentencesForPassage(appState.currentPassageId);
    });
  }
  ```
- **문제점**:
  - 결과창 상단의 `[지문] | [문장]` 탭은 UI상 "검색 모드(지문 모드 vs 문장 모드)" 전환 스위치처럼 보입니다.
  - 하지만 실제 구현은 검색창의 키워드를 기반으로 문장 검색을 수행하는 것이 아니라, **"지문 뷰어의 특정 지문 전체 문장 보기(`showSentencesForPassage`)"**로 강제 바인딩되어 있습니다.

### 2.2 `showSentencesForPassage`의 첫 번째 지문 강제 폴백 결함 ([results-sentence.js:L47-L55](file:///c:/Users/user/Desktop/web%20app/05-gichul_db/static/js/results-sentence.js#L47-L55))
- **현재 코드**:
  ```javascript
  export async function showSentencesForPassage(passageId) {
    stopAllListeningAudio();
    if (!passageId) {
      if (appState.currentPassageId) {
        passageId = appState.currentPassageId;
      } else if (appState.currentExamQuestions && appState.currentExamQuestions.length > 0) {
        passageId = appState.currentExamQuestions[appState.currentPassageIndex]?.id;
      } else if (appState.passagesData && appState.passagesData.length > 0) {
        passageId = appState.passagesData[0].id; // 🚨 문제의 원인
      }
    }
  ```
- **문제점**:
  - 검색어 없이 검색하여 최상위 학년 선택 단계에 머물러 있는 상태에서 사용자가 `[문장]` 탭을 누르면, `currentPassageId`가 `null`이므로 메모리 캐시인 `passagesData[0]`의 ID를 꺼내옵니다.
  - DB 정렬 규칙(최신 연도 `2026`, 최신 월 `09`, 18번)에 따라 `[고2-2026년-09월-18번]`이 자동으로 할당되어, 의도치 않게 해당 9개 문장이 로드됩니다.

---

## 3. 해결 목표 및 핵심 설계 (대안 B)

| 구분 | 현재 상태 (Before) | 개선 후 (After - 대안 B) |
|---|---|---|
| **검색어 없을 때 [문장] 탭 클릭** | `passagesData[0]`(`고2 2026-09 18번`) 9개 문장 강제 표출 | **문장 검색 안내 빈 화면(Empty Guidance State)** 표출 + 검색창 포커스 |
| **검색어 있을 때 [문장] 탭 클릭** | 지문 문장으로 덮어씀 | 해당 검색어로 **전체 문장 검색(`executeSearch("results")`)** 즉시 실행 |
| **특정 지문 전체 문장 보기** | `[문장]` 탭과 기능 중복 혼선 | 헤더 슬롯의 **`[📝 해당 지문의 전체 문장]`** 전용 버튼으로만 명확히 작동 |
| **`showSentencesForPassage` 폴백** | 미선택 시 임의의 0번 지문 로드 | 지문이 없을 경우 억지 폴백하지 않고 안내 모드로 부드럽게 전환 |

---

## 4. 구체적 구현 계획

### 4.1 결과창 `[문장]` 탭 핸들러 분기 개선 ([static/js/navigation.js](file:///c:/Users/user/Desktop/web%20app/05-gichul_db/static/js/navigation.js))
- `resultsTabModeSentence` 클릭 시:
  1. `resultsSearchInput`에 텍스트가 입력되어 있는 경우:
     - `setMode("sentence")` 전환 후 `executeSearch("results")`를 실행하여 해당 키워드가 포함된 문장들을 검색합니다.
  2. `resultsSearchInput`이 비어 있는 경우:
     - `setMode("sentence")`로 모드 전환만 수행하고, 임의의 지문 문장을 불러오지 않습니다.
     - `showSentenceEmptyGuidance()` 함수를 호출하여 안내 빈 화면을 노출하고, `resultsSearchInput`에 자동으로 포커스를 부여합니다.

### 4.2 문장 검색 안내 빈 화면(Empty Guidance State) 렌더러 구현 ([static/js/results-sentence.js](file:///c:/Users/user/Desktop/web%20app/05-gichul_db/static/js/results-sentence.js))
- `showSentenceEmptyGuidance()` 신설:
  - `passageViewContainer.style.display = "none"`
  - `sentenceViewContainer.style.display = "none"`
  - `emptyResultsBox.style.display = "none"`
  - 전용 안내 컨테이너(`#sentenceEmptyGuidanceBox`) 표시:
    - 타이틀: `🔍 찾으시는 영어 문장이나 키워드를 검색해 보세요`
    - 서브 안내: `"상단 검색창에 영어 단어, 숙어, 출처([고3-2026년...])를 입력하거나, 필터 바의 어법(어법 대분류, 세부 어법)을 선택하여 원하는 문장을 모아볼 수 있습니다."`
    - 빠른 탐색 팁: 추천 검색 키워드 칩(`climate`, `technology`, `relationships`, `#어법`) 제공
- `showSentencesForPassage`에서 `passageId`가 없고 `currentPassageId`도 없을 때 `passagesData[0]`로 멋대로 덮어씌우는 로직 제거.

### 4.3 UI 템플릿 마크업 및 스타일링 ([templates/index.html](file:///c:/Users/user/Desktop/web%20app/05-gichul_db/templates/index.html), [static/css/search.css](file:///c:/Users/user/Desktop/web%20app/05-gichul_db/static/css/search.css))
- `templates/index.html` 내 문장 결과 섹션에 `#sentenceEmptyGuidanceBox` 템플릿 배치
- `static/css/search.css`에 파스텔톤 모던 카드 및 가이드 칩 스타일 추가

---

## 5. 진행 현황

| 작업 단계 | 내용 | 상태 |
|---|---|---|
| **1단계** | `navigation.js` 결과창 `[문장]` 탭 검색어 유무 분기 구현 (`resultsSearchInput` 입력 시 검색 실행, 빈 값 시 안내 화면 전환) | ✅ 완료 (2026-10-05) |
| **2단계** | `results-sentence.js` 0번 지문 자동 폴백 제거 및 `showSentenceEmptyGuidance` 렌더러 신설 | ✅ 완료 (2026-10-05) |
| **3단계** | `index.html` 및 `search.css` 문장 검색 안내 빈 화면(Empty State) 마크업/스타일링 및 추천 칩 클릭 이벤트 구현 | ✅ 완료 (2026-10-05) |
| **4단계** | `search.js` 검색 실행 및 초기화 연동, 정적 검증(`compileall`, `node -c`, `pytest` 206통과) 완료 | ✅ 완료 (2026-10-05) |

---

## 6. 검증 계획 (Rule 2)

- **터미널 정적 검증**:
  ```powershell
  python -m compileall gichul tests -q
  node -c static/js/navigation.js static/js/results-sentence.js
  python -m pytest tests -q
  ```
- **사용자 수동 확인**:
  1. 첫 화면(Home)에서 검색창을 비워둔 채 [검색] 클릭
  2. 결과창 상단의 `[문장]` 탭 클릭 시, 더 이상 `[고2-2026년-09월-18번]` 지문 문장 9개가 뜨지 않고 깔끔한 "문장 검색 안내 화면"이 나오는지 확인
  3. 특정 지문(예: 고3 18번)을 선택한 상태에서 헤더의 `[📝 해당 지문의 전체 문장]` 버튼 클릭 시에는 정상적으로 해당 지문의 문장이 열리는지 확인
