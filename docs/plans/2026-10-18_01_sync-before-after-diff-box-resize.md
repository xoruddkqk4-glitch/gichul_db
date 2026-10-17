# AI 일괄 진단 Before/After 대조창 높이 동시 리사이징 동기화 구현 계획서

## 1. 개요 및 목적
AI 일괄 진단 결과 검토 모달(`AI 일괄 진단 결과 검토`)에서 사용자가 우측의 **'🟢 AI 제안 (After - 직접 수정 가능)'** 텍스트영역(`textarea.diff-box-after-textarea`)의 우측 하단 리사이즈 핸들을 드래그하여 높이를 키울 때, 좌측의 **'🔴 현재 DB (Before)'** 텍스트 창(`div.diff-box-before`)이 함께 커지지 않고 `max-height: 120px`로 고정되어 양쪽 대조 시각화가 어긋나는 문제를 해결합니다.  
사용자의 지적대로 **After 창 크기를 확대/축소할 때 Before 창의 크기도 실시간으로 1:1 완벽하게 함께 연동되어 커지도록** CSS 레이아웃 개선 및 JavaScript `ResizeObserver` 하이브리드 동기화 시스템을 구축합니다.

---

## 2. 진행 현황 표

| 작업 단계 | 내용 | 대상 파일 | 상태 |
|---|---|---|---|
| **1단계** | Before/After 대조 박스 CSS Flex·Grid 및 폰트/줄간격 규격 일체화 | `static/css/modal.css` | ✅ 완료 |
| **2단계** | JavaScript `ResizeObserver` 기반 실시간 1:1 높이 동기화 바인딩 | `static/js/reports.js` | ✅ 완료 |
| **3단계** | 모바일/반응형 분기 및 스크롤바 렌더링 최적화 | `static/css/modal.css` | ✅ 완료 |
| **4단계** | 터미널 정적 구문 및 파이썬 문법 검증 | `reports.js`, `run.py` | ✅ 완료 |

---

## 3. 현행 시스템 분석 및 문제 원인

### 3.1 현행 구조 및 문제 원인
1. **HTML 구조 (`static/js/reports.js` 778~787행)**:
   ```html
   <div class="review-item-diff-container">
     <div class="diff-col">
       <span class="diff-label diff-label-before">🔴 현재 DB (Before)</span>
       <div class="diff-box-before">${escapeHtml(d.before_text || "(비어 있음)")}</div>
     </div>
     <div class="diff-col">
       <span class="diff-label diff-label-after">🟢 AI 제안 (After - 직접 수정 가능)</span>
       <textarea class="diff-box-after-textarea" id="reviewAfterText-${idx}">${escapeHtml(d.after_text || "")}</textarea>
     </div>
   </div>
   ```
2. **CSS 구조 (`static/css/modal.css` 1008~1034행)**:
   - `.diff-box-before`: `max-height: 120px; overflow-y: auto;` (고정 상한선 존재, flex-grow 없음)
   - `.diff-box-after-textarea`: `height: 120px; resize: vertical;` (브라우저 네이티브 리사이즈 가능)
3. **발생 현상**:
   - 사용자가 우측 After textarea의 리사이즈 핸들을 아래로 드래그하면, 브라우저가 textarea 요소의 인라인 스타일에 `style="height: 350px;"`를 부여하여 우측 창만 길어집니다.
   - 좌측 Before 박스는 `max-height: 120px`에 갇혀 있어서, 우측 창이 아무리 커져도 좌측 창은 작은 채로 남아 대조 비교가 불가능해지고 심미성이 훼손됩니다.

---

## 4. 상세 개선 설계

### 4.1 CSS Flex/Grid 레이아웃 최적화 (`static/css/modal.css`)
- **Before 박스 규격 일체화**:
  - `max-height: 120px` 제한 제거.
  - `min-height: 120px; box-sizing: border-box; height: 100%; flex: 1 1 auto;` 부여.
  - 폰트 패밀리(`font-family: inherit`), 줄간격(`line-height: 1.45`), 폰트 크기(`0.8rem`), 패딩(`0.5rem`)을 우측 textarea와 100% 동일하게 맞춰 텍스트 행 높이 일치.
- **부모 컬럼 높이 확장 보장**:
  - `.diff-col`: `display: flex; flex-direction: column; gap: 0.25rem; height: 100%; min-height: 0;`

### 4.2 JavaScript `ResizeObserver` 실시간 높이 동기화 (`static/js/reports.js`)
- CSS Grid의 `stretch`에 더해, 브라우저별 textarea 리사이즈 렌더링 특성 차이를 완벽히 극복하기 위해 네이티브 `ResizeObserver` API를 연동합니다.
- `renderBatchDiagnosisReview` 함수 렌더링 후 이벤트 바인딩 시:
  ```javascript
  // Before-After 높이 실시간 동기화
  panel.querySelectorAll(".review-item-card").forEach((card) => {
    const textarea = card.querySelector(".diff-box-after-textarea");
    const beforeBox = card.querySelector(".diff-box-before");
    if (!textarea || !beforeBox) return;

    const ro = new ResizeObserver(() => {
      // textarea의 offsetHeight(보더/패딩 포함 높이)를 Before 박스에 즉시 주입
      const h = textarea.offsetHeight;
      if (h > 0) {
        beforeBox.style.height = `${h}px`;
      }
    });
    ro.observe(textarea);
  });
  ```
- 이로써 사용자가 마우스로 After 창을 부드럽게 드래그하는 찰나(매 프레임)마다 좌측 Before 창의 높이가 픽셀 단위로 정확하게 함께 늘어나고 줄어듭니다.

---

## 5. 단계별 구현 명세

### 1단계: CSS 스타일링 수정 (`static/css/modal.css`)
- `.diff-box-before`에 `min-height: 120px; flex: 1; line-height: 1.45; box-sizing: border-box;` 적용 및 `max-height` 제거.
- `.diff-box-after-textarea`에 `min-height: 120px;` 명시.
- `.diff-col`에 `height: 100%; min-height: 0;` 적용.

### 2단계: JS ResizeObserver 동기화 구현 (`static/js/reports.js`)
- `renderBatchDiagnosisReview` 내 카드별 `textarea`와 `beforeBox`를 매핑하여 `ResizeObserver` 관찰 등록.
- 패널 닫기/취소/적용 시 옵저버 누수 방지 및 클린업.

### 3단계: 엣지 케이스 점검
- 초기 로드 시 텍스트 내용 길이에 따른 초기 높이 균형 점검.
- 모바일(화면 폭 640px 이하 1열 배치) 환경에서의 자연스러운 단독 표시 확인.

### 4단계: 터미널 정적 구문 검증
- `node -c static/js/reports.js`
- `python -m py_compile run.py`

---

## 6. 실행 및 적용 완료
- `/apply` 지시에 따라 1단계부터 4단계까지 소스 코드 반영 및 터미널 정적 검증(`node -c`, `python -m py_compile`)을 성공적으로 완료하였습니다.
- Rule 3 & 4 정책에 따라 자동 Git 커밋/푸시는 수행하지 않고 대기합니다. 작업 결과를 원격 저장소에 커밋/푸시하려면 `/git-commit` 명령어를 입력해 주세요.
