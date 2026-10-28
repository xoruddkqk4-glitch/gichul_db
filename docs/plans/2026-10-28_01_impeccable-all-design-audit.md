# Impeccable-All 종합 디자인 감사 보고서 및 구현 계획서
> 프로젝트: `05-gichul_db` (Gichul DB — 수능·모의고사 영어 기출 DB)
> 감사 일시: 2026-10-28 KST
> 감사 대상: `templates/index.html`, `static/css/*.css` (7개 파일)

---

## 📌 진행 현황

| 단계 | 항목 | 대상 파일 | 상태 |
|:---|:---|:---|:---:|
| Step 1 | 전역 접근성 & CSS 토큰 확장 | `static/css/base.css` | ✅ 완료 |
| Step 2 | 폰트 크기 및 아웃라인 개선 | `static/css/viewer.css` | ✅ 완료 |
| Step 3 | 반응형 및 포커스 아웃라인 개선 | `static/css/search.css` | ✅ 완료 |
| Step 4 | 접근성 포커스 링 보완 | `grammar.css`, `handouts.css`, `modal.css`, `upload.css` | ✅ 완료 |
| Step 5 | 검색 0건 Empty State UI 추가 | `templates/index.html`, `search.css` | ✅ 완료 |
| Step 6 | 반응형 Breakpoint 및 레이아웃 보강 | `static/css/viewer.css` | ✅ 완료 |
| Step 7 | 디자인 시스템 명세서 작성 | `DESIGN.md` | ✅ 완료 |

---

## 📊 25개 전수 검사 스코어카드

| # | 도메인 | 항목 | 판정 | 핵심 발견 사항 |
|---|:---|:---|:---:|:---|
| 1 | 시스템 & 컨텍스트 | `detect` (안티패턴 스캔) | ⚠️ WARN | `viewer.css` 내 `.choice-star`·`.choice-trap-tag`에 9.6px/9.2px 서브-픽셀 폰트 사용 (`0.64rem`, `0.66rem`); `breadcrumb-item`에 `1.45rem` 과대 폰트 (주석: "기존 0.78rem 대비 2배 확대", 레이아웃 붕괴 의심) |
| 2 | 시스템 & 컨텍스트 | `doctor` (규격 드리프트) | ⚠️ WARN | `prefers-reduced-motion` 선언이 `viewer.css` 단 1곳 (`.tts-lock-fill`)에만 한정; `base.css`, `grammar.css`, `handouts.css`의 애니메이션에 미적용 |
| 3 | 시스템 & 컨텍스트 | `init` (CSS 변수 토큰 활용) | ⚠️ WARN | `viewer.css`·`grammar.css`·`handouts.css` 전반에 Slate 계열 하드코딩 색상(`#334155`, `#0f172a`, `#1e293b` 등) 500+ 건 직접 기술; `base.css` `:root` 토큰으로 추상화 필요 |
| 4 | 시스템 & 컨텍스트 | `document` (DESIGN.md 정합) | ⚠️ WARN | DESIGN.md 문서 부재 — 디자인 토큰, 컬러 시스템, 타이포그래피 스케일 문서 없음 |
| 5 | 시스템 & 컨텍스트 | `extract` (컴포넌트 재사용성) | ✅ PASS | `btn`, `filter-select`, `modal-*` 등 공통 컴포넌트 클래스 체계가 `base.css` + 도메인 CSS 분리 구조로 잘 정립됨 |
| 6 | 사용성 & 접근성 | `critique` (닐슨 10대 휴리스틱) | ⚠️ WARN | ① 시스템 상태 피드백: 검색 결과 0건 시 명시적 피드백 HTML 요소 미발견; ② 일관성: `breadcrumb-item` 1.45rem과 인접 `.breadcrumb-hint` 1.05rem 간 폰트 위계 혼선 |
| 7 | 사용성 & 접근성 | `audit` (WCAG 2.1 AA) | ❌ FAIL | 키보드 접근성: `:focus-visible` 선언이 `viewer.css`의 `.tts-tool-btn` 단 1곳에만 있음; 나머지 버튼·입력 요소 25+ 곳에서 `outline: none`으로 포커스 링 제거 후 대체 스타일 미제공 → WCAG 2.1 SC 2.4.7 위반 |
| 8 | 사용성 & 접근성 | `clarify` (UX 라이팅) | ✅ PASS | 버튼 레이블·`title` 속성·플레이스홀더 문구가 충분히 구체적이고 한국어로 명확하게 기술됨 |
| 9 | 시각 & 타이포그래피 | `typeset` (폰트 스케일·위계) | ⚠️ WARN | `.breadcrumb-item` `1.45rem` 이상 과대 선언; `.choice-star`·`.choice-trap-tag` 0.64–0.66rem (10.2–10.6px) WCAG 최소 12px 하한 위반; `--font-xs: 0.75rem` 기준선 미준수 |
| 10 | 시각 & 타이포그래피 | `colorize` (색상 역할 분리) | ⚠️ WARN | 상태 배지 컬러(success/warning/danger)는 `:root` 토큰으로 잘 관리되나, 지문뷰 어법 분석 인라인 배지가 독자적인 하드코딩 색상을 다량 사용 |
| 11 | 시각 & 타이포그래피 | `layout` (8pt 그리드 여백 리듬) | ✅ PASS | `gap`, `padding`, `margin`이 4/8/12/16/20/24px 계열 기준으로 일관성 있게 사용됨 |
| 12 | 시각 & 타이포그래피 | `bolder` (무채색 UI 생동감) | ✅ PASS | `.brand-badge` 파랑 그라디언트, `.area-toggle-btn.active` 블루 그라디언트, 토스트 다크 글래스모피즘 등 충분한 시각 포인트 존재 |
| 13 | 시각 & 타이포그래피 | `quieter` (시각 노이즈 완화) | ✅ PASS | 불필요한 과채도 없음; 섀도·테두리 강도가 계층별로 적절히 조정됨 |
| 14 | 디테일 & 인터랙션 | `polish` (곡률 & 보더 일관성) | ⚠️ WARN | `--radius-sm: 6px`, `--radius-md: 10px`, `--radius-lg: 16px` 토큰 존재하나 도메인 CSS에서 `border-radius: 8px`, `4px` 등 임의 픽셀값 직접 사용 건 다수 (`viewer.css` 60+ 곳) |
| 15 | 디테일 & 인터랙션 | `animate` (마이크로 트랜지션) | ✅ PASS | 호버·포커스 트랜지션이 `0.15s–0.28s cubic-bezier(0.16,1,0.3,1)` 범위로 일관되게 적용됨 |
| 16 | 디테일 & 인터랙션 | `delight` (인터랙션 완성도) | ✅ PASS | 플로팅 장바구니 `slideUpFloating`, 모달 `modalScale`, 토스트 `slideDownToast` 등 진입 애니메이션 다수 구현 |
| 17 | 디테일 & 인터랙션 | `overdrive` (과도한 효과) | ✅ PASS | 과한 파티클·파래럭스 없음; 효과 강도가 실용적 수준으로 제어됨 |
| 18 | 견고성 & 상태 처리 | `harden` (에러 & 빈 상태) | ⚠️ WARN | 검색 0건 시 메인 결과 섹션(`#resultsView`) 내 별도 Empty State HTML 요소 미발견; JS 렌더링에만 의존하면 CSS 전환 애니메이션 적용 불가 |
| 19 | 견고성 & 상태 처리 | `onboard` (신규 사용자 안내) | ✅ PASS | 홈 화면 도움말 팝오버(`💡 도움말`) 및 검색 가이드가 명시적으로 제공됨 |
| 20 | 견고성 & 상태 처리 | `distill` (불필요한 복잡도 제거) | ⚠️ WARN | `!important` 선언이 `grammar.css`, `handouts.css`, `upload.css`에 걸쳐 180+ 건; 대부분 셀렉터 특이도 경쟁을 `!important`로 해결한 구조적 부채 |
| 21 | 견고성 & 상태 처리 | `adapt` (모바일·태블릿 적응성) | ⚠️ WARN | `@media` breakpoint가 각 CSS 파일별 산발적 (640/768/900/992/1024/1050/1500px); 통일된 체계 부재; `google-search-input`의 `min-width: 500px` 고정 → 모바일 오버플로 위험 |
| 22 | 견고성 & 상태 처리 | `optimize` (렌더링 성능) | ✅ PASS | `backdrop-filter`, `will-change` 남용 없음; CSS 파일 분할로 불필요한 블로킹 최소화 |
| 23 | 구조 & 대안 탐색 | `shape` (정보 아키텍처 적합성) | ✅ PASS | 홈 → 검색 결과 → 지문 뷰 → 문장 뷰 → 유인물 제작소의 5단계 SPA 흐름이 명확한 섹션 분리 구조로 구현 |
| 24 | 구조 & 대안 탐색 | `live` (컴포넌트 변형 가능성) | ✅ PASS | `.btn-sm`, `.compact`, `.mini-mode-btn` 등 variant 클래스 체계 존재; 확장성 양호 |
| 25 | 구조 & 대안 탐색 | `generate` (시각 대안 탐색) | ⚠️ WARN | 다크 모드(`prefers-color-scheme: dark`) 미지원; 라이트 모드 단일 테마만 제공 |

---

## 🏆 종합 스코어

| 구분 | 결과 | 비율 |
|:---|:---|:---|
| ✅ PASS | 11개 | 44% |
| ⚠️ WARN | 12개 | 48% |
| ❌ FAIL | 1개 (WCAG 키보드 접근성) | 8% |

**총점: 68/100**

---

## 📝 파일별 구체적 코드 수정 지침

### Step 1: `static/css/base.css` — 전역 접근성 & 토큰 확장
- `--radius-xs: 4px;` 추가 및 Breakpoint 토큰 주석 추가
- 전역 `:focus-visible` 포커스 링 추가 (`outline: 2px solid var(--border-focus); outline-offset: 2px;`)
- `@media (prefers-reduced-motion: reduce)` 애니메이션 완화 블록 추가

### Step 2: `static/css/viewer.css` — 폰트 크기·아웃라인 정정
- `.breadcrumb-item` 폰트 크기 `0.85rem`으로 정상화
- `.choice-star`, `.choice-trap-tag`, `.memo-char-count`, `.btn-memo-save`, `.memo-footer` 폰트 `0.75rem` 이상으로 상향 (12px 보장)
- `outline: none`에 인접한 `:focus-visible` 대체 포커스 링 제공

### Step 3: `static/css/search.css` — 반응형 & 아웃라인
- `.google-search-input`의 `min-width: 500px`를 `min-width: min(500px, 100%)`로 수정
- `outline: none` 요소에 대응하는 `:focus-visible` 스타일 보완

### Step 4: `grammar.css` + `handouts.css` + `modal.css` — 접근성
- 각 파일의 `outline: none` 선언부에 `:focus-visible` 스타일 보완

### Step 5: `templates/index.html` & `search.css` — Empty State 요소 추가
- `#resultsView` 내에 `.results-empty-state` HTML 마크업 및 CSS 스타일 정의

### Step 6: `viewer.css` — 반응형 Breakpoint 보강
- 1024px, 768px 미디어 쿼리 보강

### Step 7: `DESIGN.md` 신설 — 디자인 시스템 문서화
- 디자인 토큰, 컬러 팔레트, 타이포그래피, 컴포넌트 규격 문서화
