# Gichul DB 디자인 시스템 규격서 (DESIGN.md)

> **프로젝트:** `05-gichul_db` (수능·모의고사 영어 기출 DB)  
> **버전:** 1.0.0 (2026-10-28)  
> **표준 규격:** WCAG 2.1 AA 준수, 8pt 그리드 시스템 기반

---

## 1. 디자인 원칙 (Design Principles)

1. **학습 및 교사용 가독성 최우선 (High Legibility)**:
   - 최소 폰트 크기 `12px`(`0.75rem`) 하한선을 엄격히 준수합니다.
   - 본문 텍스트는 WCAG 2.1 AA 기준 4.5:1 이상의 대비율(`--text-muted: #475569`, `--text-main: #1e293b`)을 유지합니다.
2. **명확하고 예측 가능한 인터랙션 (Accessible & Predictable)**:
   - 모든 대화형 요소(입력창, 셀렉트박스, 버튼, 링크)는 키보드 조작 시 명확한 `:focus-visible` 포커스 링을 제공합니다.
3. **사용자 환경 배려 (Inclusive Motion)**:
   - `prefers-reduced-motion: reduce` 환경에서는 모든 CSS 애니메이션과 전환 시간을 즉각 단축하여 시각적 불편을 최소화합니다.

---

## 2. 디자인 토큰 (Design Tokens)

### 2.1 컬러 팔레트 (Color Palette)

| 토큰명 | CSS 변수 | HEX / RGB | 용도 및 설명 |
|:---|:---|:---|:---|
| **Primary** | `--primary` | `#2563eb` (Blue 600) | 주요 작업 버튼, 활성 탭, 브랜드 강조 |
| **Primary Hover** | `--primary-hover` | `#1d4ed8` (Blue 700) | 버튼 및 인터랙션 호버 상태 |
| **Primary Light** | `--primary-light` | `#eff6ff` (Blue 50) | 활성 배경, 선택된 셀/아이템 배경 |
| **Primary Border** | `--primary-border` | `#bfdbfe` (Blue 200) | 활성 카드 및 탭 테두리 |
| **Success** | `--success` | `#10b981` (Emerald 500) | 완료, 정답 형광펜, 정상 상태 배지 |
| **Success Light** | `--success-light` | `#ecfdf5` (Emerald 50) | 정답/성공 알림 배경 |
| **Warning** | `--warning` | `#f59e0b` (Amber 500) | 주의, 미완료, 검토 필요 배지 |
| **Warning Light** | `--warning-light` | `#fffbeb` (Amber 50) | 경고 배경 |
| **Danger** | `--danger` | `#ef4444` (Red 500) | 오류 신고, 삭제, 오답 선지 |
| **Danger Light** | `--danger-light` | `#fef2f2` (Red 50) | 오류 알림 및 오답 배경 |
| **Bg Main** | `--bg-main` | `#f8fafc` (Slate 50) | 전체 페이지 기본 배경 |
| **Bg Card** | `--bg-card` | `#ffffff` | 컨텐츠 카드, 모달, 패널 표면 |
| **Text Main** | `--text-main` | `#1e293b` (Slate 800) | 본문 및 주요 헤딩 (대비율 12:1+) |
| **Text Muted** | `--text-muted` | `#475569` (Slate 600) | 부가 설명, 메타정보 (대비율 5.6:1+) |
| **Text Light** | `--text-light` | `#64748b` (Slate 500) | 아이콘, 보조 플레이스홀더 |
| **Border** | `--border` | `#e2e8f0` (Slate 200) | 기본 구분선 및 입력창 테두리 |
| **Border Focus**| `--border-focus`| `#3b82f6` (Blue 500) | 키보드 포커스 링 및 입력 포커스 |

---

### 2.2 타이포그래피 스케일 (Typography Scale)

* **기본 폰트 패밀리**: `'Pretendard', -apple-system, BlinkMacSystemFont, system-ui, Roboto, 'Noto Sans KR', sans-serif`

| 토큰명 | CSS 변수 | 크기 (rem / px) | Line Height | 주 용도 |
|:---|:---|:---|:---|:---|
| **Font XS** | `--font-xs` | `0.75rem` (12px) | 1.35 | 배지, 태그, 툴팁, 최소 가독성 하한 |
| **Font SM** | `--font-sm` | `0.8125rem` (13px) | 1.45 | 보조 설명, 테이블 서브텍스트, 메타데이터 |
| **Font MD** | `--font-md` | `0.875rem` (14px) | 1.50 | 폼 입력창, 셀렉트 박스, 일반 버튼 |
| **Font Base** | `--font-base` | `0.9375rem` (15px) | 1.60 | 지문 본문, 일반 리스트, 카드 타이틀 |
| **Heading 3** | — | `1.15rem` (18.4px) | 1.40 | 모달 제목, 패널 헤더, Empty State 제목 |
| **Heading 2** | — | `1.35rem` (21.6px) | 1.35 | 섹션 타이틀, 검색 결과 헤더 |
| **Heading 1** | — | `1.75rem` (28px) | 1.30 | 앱 메인 헤더, 대형 브랜딩 |

> **규칙**: 인라인 배지나 라벨이라도 `0.75rem`(12px) 미만의 폰트 사용은 금지됩니다.

---

### 2.3 모서리 곡률 (Border Radius Tokens)

| 토큰명 | CSS 변수 | 값 | 주 용도 |
|:---|:---|:---|:---|
| **Radius XS** | `--radius-xs` | `4px` | 인라인 태그, 초소형 배지, 소형 인풋 |
| **Radius SM** | `--radius-sm` | `6px` | 폼 컨트롤, 콤팩트 버튼, 테이블 액션 |
| **Radius MD** | `--radius-md` | `10px` | 기본 카드, 드롭다운 팝오버, 표준 버튼 |
| **Radius LG** | `--radius-lg` | `16px` | 대형 모달, 메인 섹션 컨테이너 |
| **Radius Full** | `--radius-full` | `9999px` | 원형 태그, 캡슐형 토글 버튼, 펄스 닷 |

---

### 2.4 그림자 계층 (Elevation & Shadow Tokens)

| 토큰명 | CSS 변수 | 속성값 | 주 용도 |
|:---|:---|:---|:---|
| **Shadow SM** | `--shadow-sm` | `0 1px 2px 0 rgb(0 0 0 / 0.05)` | 입력창, 기본 카드 |
| **Shadow MD** | `--shadow-md` | `0 4px 6px -1px rgb(0 0 0 / 0.08)` | 드롭다운 메뉴, 팝오버, 탭 바 |
| **Shadow LG** | `--shadow-lg` | `0 10px 15px -3px rgb(0 0 0 / 0.08)` | 모달 팝업, 플로팅 장바구니 |
| **Shadow Hover** | `--shadow-hover`| `0 20px 25px -5px rgb(0 0 0 / 0.1)` | 카드 호버 시 플로팅 피드백 |

---

### 2.5 표준 반응형 Breakpoints (Responsive System)

| 구분 | 약칭 | 폭 (Width) | 대상 환경 및 레이아웃 조정 |
|:---|:---|:---|:---|
| **Small** | `--bp-sm` | `640px` | 스마트폰 화면 (단일 컬럼, 검색 팝오버 압축) |
| **Medium** | `--bp-md` | `768px` | 태블릿 세로 (브레드크럼 축소, 툴바 줄바꿈) |
| **Large** | `--bp-lg` | `1024px` | 태블릿 가로 / 소형 노트북 (사이드 패널 접기) |
| **Extra Large** | `--bp-xl` | `1280px` | 일반 데스크톱 (2x2 그리드 표준 뷰) |
| **2X Large** | `--bp-2xl`| `1500px` | 고해상도 모니터 (지문 뷰어 최대 가로폭 최적화) |

---

## 3. 웹 접근성 (WCAG 2.1 AA Checklist)

1. **키보드 접근성 (SC 2.4.7 포커스 표시)**:
   - 모든 대화형 요소는 키보드 포커스 시 `outline: 2px solid var(--border-focus); outline-offset: 2px;` 또는 동등 이상의 `box-shadow` 포커스 링을 표시해야 합니다.
   - `outline: none;`을 단독으로 사용하여 포커스 표시를 제거하는 것은 엄격히 금지됩니다.
2. **최소 폰트 크기 준수**:
   - 보조 문구라도 12px(`0.75rem`) 이상으로 렌더링되어 저시력자 사용자에게 가독성을 보장합니다.
3. **모션 감소 (prefers-reduced-motion)**:
   - 사용자가 OS 수준에서 '움직임 줄이기'를 활성화한 경우 트랜지션 및 애니메이션 시간을 `0.01ms`로 제한하여 시각적 현기증을 방지합니다.

---

## 4. 컴포넌트 패턴 가이드 (Component Patterns)

### 4.1 버튼 (Buttons)
- **Primary**: `background: var(--primary); color: #fff;` (주요 실행 버튼)
- **Secondary**: `background: #f1f5f9; color: var(--text-main); border: 1px solid var(--border);`
- **Compact / SM**: `padding: 0.25rem 0.65rem; font-size: 0.78rem;`

### 4.2 빈 상태 (Empty State)
- 아이콘 (`2.5rem` ~ `2.75rem`), 명확한 제목 (`1.15rem`, 볼드), 구체적인 검색 제안 문구, 초기화 액션 버튼을 필수로 포함합니다.

### 4.3 토스트 알림 (Toast Notifications)
- 우측 상단 슬라이드 다운 애니메이션, 다크 글래스모피즘(`backdrop-filter: blur(10px)`), 상태별(info/success/warning/error) 좌측 보더 강조.
