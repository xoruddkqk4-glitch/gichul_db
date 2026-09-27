# Implementation Plan - 원본 파일 현황 5종 파일 다중 선택 미등록 필터링 시스템 구축

## 1. 개요 및 배경

### 1.1 현재 구조 및 문제점
- **단일 On/Off 필터의 한계**:
  - 현재 「원본 파일 현황 & 개별 업로드」 탭의 `[⚠️ 미등록 파일 있는 세트만 보기]`는 5종 파일(문제지, 해설지, 대본, 정답표, 정답률) 중 단 1개라도 결측되면 무조건 매칭되는 단일 체크박스 방식입니다.
  - 현재 전체 321개 시험지 중:
    - 문제지(PDF): 321 / 321 (100% 등록 완료)
    - 해설지(HWP): 320 / 321 (**1개 누락**)
    - 대본(PDF): 315 / 321 (**6개 누락**)
    - 정답표(이미지/JSON): 321 / 321 (100% 등록 완료)
    - 정답률(CSV): 70 / 321 (**251개 미등록**)
  - 이로 인해 체크박스를 켜면 CSV가 없는 251개 시험지가 한 번에 쏟아져 나와, 사용자가 실제로 찾고 싶어 하는 **"해설지가 빠진 1개 시험지"**나 **"대본이 빠진 6개 시험지"**, 또는 **"핵심 4종 파일(문제지·해설지·대본·정답표) 중 빠진 시험지"**를 선별해내기가 매우 불편합니다.

### 1.2 목표
1. **5종 파일별 개별/복수 선택 미등록 필터 드롭다운 구축**:
   - `문제지(PDF)`, `해설지(HWP)`, `대본/해설(PDF)`, `정답표(JSON/이미지)`, `정답률(CSV)` 5개 항목을 자유롭게 체크/해제할 수 있는 다중 선택 필터 메뉴 제공.
2. **상단 5대 통계 배지(Summary Badges) 원클릭 직관 연동**:
   - 상단 요약 배지(예: `📝 해설지: 320 / 321`, `📜 대본: 315 / 321`)를 클릭하면, 해당 파일이 미등록된 시험지만 즉시 테이블에 선별 렌더링되도록 구현.
3. **학년 / 연도 / 월 필터와의 완전한 유기적 결합**:
   - 기존의 학년/년도/월 다중 필터와 함께 복합적으로 작동하여, 예: `2024년 고3 중 대본이 없는 시험지` 등을 1초 만에 선별할 수 있도록 지원.

---

## 2. 세부 UI/UX 설계

### 2.1 미등록 파일 다중 선택 드롭다운 팝업 (`#dropdownMissingFiles`)
- 기존 단일 체크박스 위치를 개선하여 깔끔한 필터 버튼 및 팝오버 메뉴로 개편:
  ```html
  <div class="dropdown-filter-container" id="missingFilterContainer">
    <button type="button" class="btn-filter-trigger" id="btnTriggerMissingFilter">
      <span class="icon">⚠️</span>
      <span class="label">미등록 파일 필터</span>
      <span class="badge" id="badgeMissingFilterCount" style="display: none;">2</span>
      <span class="arrow">▾</span>
    </button>
    <div class="dropdown-filter-menu" id="menuMissingFilter" style="display: none;">
      <div class="menu-header">
        <span>누락 파일 선택</span>
        <div class="menu-actions">
          <button type="button" class="btn-mini-link" id="btnSelectAllMissing">전체</button>
          <button type="button" class="btn-mini-link" id="btnClearAllMissing">초기화</button>
        </div>
      </div>
      <div class="menu-body">
        <label class="filter-check-item">
          <input type="checkbox" class="chk-missing-item" value="pdf"> 📄 문제지 (PDF)
        </label>
        <label class="filter-check-item">
          <input type="checkbox" class="chk-missing-item" value="hwp"> 📝 해설지 (HWP)
        </label>
        <label class="filter-check-item">
          <input type="checkbox" class="chk-missing-item" value="script"> 📜 대본/해설 (PDF)
        </label>
        <label class="filter-check-item">
          <input type="checkbox" class="chk-missing-item" value="ans"> 🖼️ 정답표 (JSON / 이미지)
        </label>
        <label class="filter-check-item">
          <input type="checkbox" class="chk-missing-item" value="csv"> 📊 정답률 (CSV)
        </label>
      </div>
      <div class="menu-footer">
        <label class="mode-toggle" title="선택한 항목 중 하나라도 없으면 표시">
          <input type="checkbox" id="chkMissingMatchAll"> 모든 선택 파일 동시 결측(AND)
        </label>
      </div>
    </div>
  </div>
  ```

### 2.2 상단 요약 배지 원클릭 필터 인터랙션
- 상단의 5개 통계 카드 배지에 호버 효과(`cursor: pointer`, 미세 확대, 툴팁 `"클릭 시 미등록 N개 세트 즉시 보기"`) 부여:
  - `📝 해설지(HWP): 320 / 321` 클릭 시 ➔ `hwp` 누락 세트 단독 필터 활성화 (1건만 즉시 표시)
  - `📜 대본(PDF): 315 / 321` 클릭 시 ➔ `script` 누락 세트 단독 필터 활성화 (6건만 즉시 표시)
  - 배지 활성화 시 테두리 글로우 효과 및 우측에 `✕ 필터 해제` 버튼 동적 노출.

---

## 3. 프론트엔드 필터링 로직 구현 설계 (`static/js/files-status.js`)

### 3.1 상태 관리 객체 확장
```javascript
// 미등록 파일 다중 필터 상태
let missingFileFilters = {
  active: false,
  types: {
    pdf: false,
    hwp: false,
    script: false,
    ans: false,
    csv: false
  },
  matchAll: false // false: OR(선택 항목 중 하나라도 결측), true: AND(선택 항목 모두 결측)
};
```

### 3.2 테이블 렌더링 필터링 함수 개편
```javascript
function isExamMissingSelectedFiles(exam, filters) {
  const fs = exam.file_status || {};
  const hasMap = {
    pdf: Boolean(fs.pdf?.exists),
    hwp: Boolean(fs.hwp?.exists),
    script: Boolean(fs.script?.exists),
    ans: Boolean(fs.ans?.exists || (fs.ans?.answered_count > 0)),
    csv: Boolean(fs.csv?.exists || (fs.csv?.rated_count > 0))
  };

  const selectedKeys = Object.keys(filters.types).filter(k => filters.types[k]);
  if (selectedKeys.length === 0) return true; // 필터 미선택 시 통과

  if (filters.matchAll) {
    // 선택된 모든 파일이 동시에 누락된 경우
    return selectedKeys.every(k => !hasMap[k]);
  } else {
    // 선택된 파일 중 하나라도 누락된 경우
    return selectedKeys.some(k => !hasMap[k]);
  }
}
```

---

## 4. 변경 대상 파일

| 파일 경로 | 수정 내용 요약 |
| :--- | :--- |
| `templates/index.html` | 단일 체크박스를 다중 선택 드롭다운 팝오버 UI 및 통계 배지 클릭 가능 속성으로 개편 |
| `static/js/files-status.js` | 다중 필터 상태 머신 구현, 배지 클릭 이벤트 바인딩, 복합 결측 필터링 알고리즘 적용 |
| `static/css/style.css` | 미등록 드롭다운 메뉴, 칩 체크박스 스타일, 배지 호버 및 활성 배지 글로우 효과 추가 |

---

## 5. 검증 계획

1. **정적 문법 검증**:
   - `node -c static/js/files-status.js static/js/upload.js`
2. **단독 필터링 기능 테스트**:
   - `해설지(HWP)` 단독 선택 시 ➔ 정확히 1개 시험지만 필터링되는지 확인.
   - `대본(PDF)` 단독 선택 시 ➔ 정확히 6개 시험지만 필터링되는지 확인.
   - `정답률(CSV)` 제외 후 `문제지+해설지+대본+정답표` 선택 시 ➔ 핵심 파일 결측 7건만 정확히 선별되는지 확인.
3. **상단 배지 원클릭 연동 테스트**:
   - 상단 `대본(PDF)` 배지 클릭 시 테이블이 즉시 6건으로 축소되고, 다시 클릭하거나 해제 버튼 클릭 시 원복되는지 확인.
4. **기존 학년/연도/월 필터와의 연동 테스트**:
   - `고2` + `2013년` 선택 상태에서 `대본` 필터 선택 시 해당 조건 내 결측 세트만 정밀 노출되는지 확인.
