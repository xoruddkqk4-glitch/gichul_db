# 브레드크럼 바 내 중복 버튼 제거 및 단일 행(Single Row) 툴바 배치 구현 계획서

## 1. 개요 및 목적
문항 상세 결과 화면 상단의 브레드크럼 바에서 기능적으로 중복되는 **'검색 조건 초기화'**(`btnTreeResetExam`)와 **'다른 시험 선택'**(`btnTreeChangeExam`) 버튼을 완전히 제거하고, **5종 원본 파일 다운로드 툴바**(`breadcrumbExamFiles`)와 **'오류 신고'**(`btnReportPassage`) 버튼을 브레드크럼 우측에 나란히 결합하여 **단일 행(Single Row)**으로 깔끔하게 배치합니다.

---

## 2. 진행 현황 표

| 작업 단계 | 내용 | 대상 파일 | 상태 |
|---|---|---|---|
| **1단계** | 브레드크럼 바 내 중복 버튼 제거 및 우측 툴바 통합 마크업 개편 | `templates/index.html` | ⬜ 대기 |
| **2단계** | 단일 행 가로 정렬(Single Row) 및 버튼 스타일 밸런스 조정 | `static/css/viewer.css` | ⬜ 대기 |
| **3단계** | 삭제된 버튼 관련 JS 바인딩 및 표시 로직 안전 정리 | `static/js/dom.js`, `static/js/passage-render.js` | ⬜ 대기 |
| **4단계** | 터미널 정적 구문 검증 | `dom.js`, `passage-render.js` | ⬜ 대기 |

---

## 3. 현행 시스템 분석 및 문제점

### 3.1 현행 브레드크럼 바 구조 (`templates/index.html`)
현재 `#treeBreadcrumbBar`는 3개의 블록으로 나뉘어 있습니다:
1. `breadcrumb-left`: `📍 [ 고1 ] > [ 2024년 ] > [ 09월 · 교육청 ] (25문항)`
2. `breadcrumb-exam-files`: `[문제 PDF] [해설 HWP] [대본 PDF] [정답 JSON/PNG] [정답률 CSV] [ZIP]`
3. `breadcrumb-right`:
   - `[↺ 검색 조건 초기화]` (`#btnTreeResetExam`)
   - `[🔄 다른 시험 선택]` (`#btnTreeChangeExam`)
   - `[🚨 오류 신고]` (`#btnReportPassage`)

### 3.2 문제점 및 불필요성
- 브레드크럼 내의 각 단계 칩(`[고1]`, `[2024년]`) 클릭 및 `📍` 홈 아이콘 클릭으로 상위 단계 이동 및 시험 변경이 이미 직관적으로 지원됩니다.
- 또한 메인 상단 헤더와 검색창 영역에도 상시 `검색 조건 초기화` 버튼이 존재합니다.
- 따라서 브레드크럼 바의 `검색 조건 초기화`와 `다른 시험 선택`은 기능이 완전히 중복되며, 가로 폭을 과도하게 차지하여 `breadcrumb-right` 전체가 2행(아래 줄)으로 떨어져 여백 낭비와 시각적 어색함을 초래하고 있습니다.

---

## 4. 상세 구현 명세

### 4.1 1단계: HTML 마크업 정리 (`templates/index.html`)
- 파일: `templates/index.html` (502~527행)
- `btnTreeResetExam`과 `btnTreeChangeExam` 버튼 요소를 제거합니다.
- `breadcrumb-right`에는 오직 `btnReportPassage`(`🚨 오류 신고`)만 남기거나, `breadcrumb-exam-files`와 `breadcrumb-right`를 감싸는 우측 액션 그룹(`breadcrumb-right-group`)으로 단일화하여 1행 배치를 보장합니다.

```html
<div class="tree-breadcrumb-bar" id="treeBreadcrumbBar">
  <div class="breadcrumb-left">
    <span class="breadcrumb-icon" id="treeBreadcrumbHome" title="처음(학년 선택)으로 복귀">📍</span>
    <div class="breadcrumb-trail" id="breadcrumbTrail"></div>
    <span id="passageTabCount" style="display: none;">0</span>
  </div>

  <div class="breadcrumb-right-group">
    <!-- 원본 5종 파일 다운로드/교체 툴바 -->
    <div class="breadcrumb-exam-files" id="breadcrumbExamFiles" style="display: none;"></div>

    <!-- 오류 신고 버튼 -->
    <button type="button" class="btn btn-outline-danger btn-sm btn-report-passage" id="btnReportPassage" title="현재 열람 중인 문항의 오류를 신고합니다">
      🚨 오류 신고
    </button>
  </div>
</div>
```

### 4.2 2단계: CSS 스타일링 최적화 (`static/css/viewer.css`)
- 파일: `static/css/viewer.css` (18~35행, 160~175행)
- `.tree-breadcrumb-bar`:
  - `flex-wrap: nowrap;` 적용으로 브레드크럼과 우측 버튼군이 무조건 단일 1행에 위치하도록 보장.
  - 가로 스크롤 또는 유연한 축소(`overflow-x: auto`) 지원.
- `.breadcrumb-right-group`:
  - `display: inline-flex; align-items: center; gap: 0.5rem; margin-left: auto;`
- `.btn-report-passage`:
  - 원본 5종 파일 칩(`height: 28px` 내외)과 자연스럽게 어울리도록 높이, 폰트 크기(`0.8rem`), 패딩(`0.3rem 0.7rem`), 둥근 모서리(`6px`) 최적화.

### 4.3 3단계: 자바스크립트 정리 (`static/js/dom.js`, `static/js/passage-render.js`)
- `static/js/dom.js`:
  - 삭제된 `btnTreeResetExam`, `btnTreeChangeExam` 요소 export 제거 또는 `null` 안전 처리.
- `static/js/passage-render.js`:
  - `updateTreeUI` 내 `btnTreeResetExam`과 `btnTreeChangeExam`의 `style.display` 및 `onclick` 이벤트 바인딩 코드 제거.
  - `clear2x2Panels` 내 `btnTreeChangeExam.style.display = "none"` 정리.

### 4.4 4단계: 터미널 정적 구문 검증
- JavaScript 구문 검사:
  ```powershell
  node -c static/js/dom.js static/js/passage-render.js
  ```

---

## 5. 실행 및 적용 가이드
- 본 문서는 `/ask` 모드 규칙에 따라 소스 코드를 변경하지 않고 계획서만 작성 및 등록한 상태입니다.
- 작업 적용을 시작하려면 **/apply** 명령어를 입력해 주세요.
