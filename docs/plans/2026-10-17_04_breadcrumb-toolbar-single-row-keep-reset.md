# 브레드크럼 바 내 '다른 시험 선택' 삭제 및 '검색 조건 초기화' 보존 단일 행(Single Row) 툴바 구현 계획서

## 1. 개요 및 목적
사용자의 변경된 요구사항에 따라, 상단 브레드크럼 바에서 **'검색 조건 초기화'**(`btnTreeResetExam`) 버튼은 **그대로 유지**하고, 불필요하게 공간을 차지하던 **'다른 시험 선택'**(`btnTreeChangeExam`) 버튼만 **선별 삭제**합니다.  
동시에 **5종 원본 파일 다운로드 툴바**(`breadcrumbExamFiles`), **'검색 조건 초기화'**, **'오류 신고'** 버튼이 2행으로 밀리지 않고 브레드크럼 우측에 **완벽하게 단일 행(Single Row)**으로 깔끔하게 배치되도록 레이아웃을 개편합니다.

---

## 2. 진행 현황 표

| 작업 단계 | 내용 | 대상 파일 | 상태 |
|---|---|---|---|
| **1단계** | '다른 시험 선택' 버튼만 삭제 및 우측 액션 통합 마크업 개편 | `templates/index.html` | ✅ 완료 |
| **2단계** | 단일 행(Single Row) 유지 및 버튼 콤팩트 규격 밸런스 조정 | `static/css/viewer.css`, `static/css/modal.css` | ✅ 완료 |
| **3단계** | '다른 시험 선택' JS 바인딩 정리 및 '검색 조건 초기화' 동작 유지 | `static/js/dom.js`, `static/js/passage-render.js` | ✅ 완료 |
| **4단계** | 터미널 정적 구문 검증 | `dom.js`, `passage-render.js` | ✅ 완료 |

---

## 3. 현행 시스템 분석 및 개선 설계

### 3.1 변경 전 (2행 분리 문제 발생 상태)
- **1행**: `📍 [ 고1 ] > [ 2024년 ] > [ 09월 · 교육청 ] (25문항)` + `[5종 파일 칩 툴바]`
- **2행(줄바꿈)**: `[↺ 검색 조건 초기화]` + `[🔄 다른 시험 선택]` + `[🚨 오류 신고]`
- **원인**: `[🔄 다른 시험 선택]`까지 3개의 버튼이 별도의 블록으로 존재하여 가로 공간 부족으로 아래 행으로 줄바꿈됨.

### 3.2 변경 후 (단일 행 Single Row 일체화 배치)
- **1행 단일 배치**:
  - **좌측**: `📍 [ 고1 ] > [ 2024년 ] > [ 09월 · 교육청 ] (25문항)`
  - **우측**: `[ 📄 문제 PDF ] [ 📝 해설 HWP ] [ 📜 대본 PDF ] [ 🖼️ 정답 JSON ] [ 📊 정답률 CSV ] [ 📦 ZIP ]` `[ ↺ 검색 조건 초기화 ]` `[ 🚨 오류 신고 ]`
- **핵심 개선점**:
  1. `[🔄 다른 시험 선택]` 버튼을 완전히 제거하여 가로 폭 약 120px 절약.
  2. `[↺ 검색 조건 초기화]` 버튼을 보존하고, 원본 5종 파일 칩과 `[🚨 오류 신고]`와 함께 하나의 우측 액션 컨테이너로 인라인 결합.
  3. `[↺ 검색 조건 초기화]`와 `[🚨 오류 신고]` 버튼의 높이/패딩/폰트 크기를 원본 파일 칩 규격(높이 약 28px)에 맞춰 콤팩트하게 다듬어 시각적 일체감 부여.
  4. `.tree-breadcrumb-bar`에 `flex-wrap: nowrap` 및 `overflow-x: auto`를 적용하여 2행 줄바꿈 원천 차단.

---

## 4. 상세 구현 명세

### 4.1 1단계: HTML 마크업 정리 (`templates/index.html`)
- 파일: `templates/index.html` (502~527행)
- `btnTreeChangeExam`(`🔄 다른 시험 선택`) 버튼 요소만 제거.
- `btnTreeResetExam`(`↺ 검색 조건 초기화`)은 유지.
- 우측 버튼 영역을 `breadcrumb-right-actions`로 구조화:

```html
<div class="tree-breadcrumb-bar" id="treeBreadcrumbBar">
  <div class="breadcrumb-left">
    <span class="breadcrumb-icon" id="treeBreadcrumbHome" title="처음(학년 선택)으로 복귀">📍</span>
    <div class="breadcrumb-trail" id="breadcrumbTrail"></div>
    <span id="passageTabCount" style="display: none;">0</span>
  </div>

  <div class="breadcrumb-right-actions" id="breadcrumbRightActions">
    <!-- 원본 5종 파일 다운로드/교체 툴바 -->
    <div class="breadcrumb-exam-files" id="breadcrumbExamFiles" style="display: none;"></div>

    <div class="breadcrumb-right" id="breadcrumbRight">
      <button type="button" class="btn-tree-reset-exam" id="btnTreeResetExam" style="display: none;" title="검색 조건 및 시험 선택 초기화">
        ↺ 검색 조건 초기화
      </button>
      <button type="button" class="btn btn-outline-danger btn-sm btn-report-passage" id="btnReportPassage" title="현재 열람 중인 문항의 오류를 신고합니다">
        🚨 오류 신고
      </button>
    </div>
  </div>
</div>
```

### 4.2 2단계: CSS 스타일링 최적화 (`static/css/viewer.css`)
- 파일: `static/css/viewer.css` (18~35행, 125~175행)
- `.tree-breadcrumb-bar`:
  - `flex-wrap: nowrap;` 부여로 2행 줄바꿈 원천 방지.
  - `gap: 0.5rem; justify-content: space-between; align-items: center;`
  - 화면 폭이 좁은 특수 해상도에서도 줄바꿈 대신 부드러운 가로 스크롤 지원 (`overflow-x: auto; scrollbar-width: none;`).
- `.breadcrumb-right-actions`:
  - `display: inline-flex; align-items: center; gap: 0.4rem; margin-left: auto; flex-shrink: 0;`
- `.breadcrumb-exam-files`:
  - `margin-left: 0; margin-right: 0;`
- `.btn-tree-reset-exam`:
  - 파일 칩과 높이(28px) 및 시각적 조화를 이루도록 규격 최적화:
  - `padding: 0.28rem 0.6rem; font-size: 0.78rem; font-weight: 700; height: 28px; box-sizing: border-box;`
- `.btn-report-passage`:
  - `padding: 0.28rem 0.65rem; font-size: 0.78rem; font-weight: 700; height: 28px; box-sizing: border-box; white-space: nowrap;`

### 4.3 3단계: 자바스크립트 정리 (`static/js/dom.js`, `static/js/passage-render.js`)
- `static/js/dom.js`:
  - `btnTreeChangeExam` export 제거.
- `static/js/passage-render.js`:
  - `btnTreeChangeExam` 관련 import, `style.display`, `onclick` 이벤트 바인딩 및 `clear2x2Panels` 내 숨김 로직 제거.
  - `btnTreeResetExam`(`↺ 검색 조건 초기화`)의 기존 동작(조건 초기화, 시험 선택 초기화, 오디오 정지 등)은 100% 정상 보존.

### 4.4 4단계: 터미널 정적 구문 검증
- JavaScript 구문 검사:
  ```powershell
  node -c static/js/dom.js static/js/passage-render.js
  ```

---

## 5. 실행 및 적용 완료
- `/apply` 지시에 따라 1단계부터 4단계까지 소스 코드 반영 및 정적 검증(`node -c`, `python -m py_compile`)을 성공적으로 완료하였습니다.
- Rule 3 & 4 정책에 따라 자동 Git 커밋/푸시는 수행하지 않으며 대기합니다. 반영 사항을 원격 저장소에 기록 및 커밋/푸시하려면 `/git-commit` 명령어를 실행해 주세요.
