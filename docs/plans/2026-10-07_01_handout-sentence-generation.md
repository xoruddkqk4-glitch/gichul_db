# 교사용 문장 유인물 자동 제작 기능 (A4 규격 default_a4_sentence.hwpx 연동) 구현 계획서

> [!NOTE]
> `/ask` 모드로 작성된 구현 계획서입니다. **기존 소스 코드는 일절 수정하지 않았으며 계획서 보강 및 설계만 진행되었습니다.**
> 추후 사용자의 명시적인 `/apply` 명령어를 통해 단계별로 코드에 안전하게 반영할 수 있습니다.

- **문서 번호**: PLAN-2026-10-07-01
- **작성 일시**: 2026-10-07 (KST)
- **대상 템플릿**: `static/data/templates/default_a4_sentence.hwpx`
- **상태**: ✅ 완료 (2026-10-07 반영 완료)

---

## 1. 개요 및 사용자 요구사항 반영

수능·모의고사 기출 검색 결과 중 원하는 문장들을 선택하여, 수업 및 구문 분석 훈련에 즉시 활용할 수 있는 **A4 단면 규격의 HWPX 문장 유인물**을 자동 생성하는 기능입니다.

### 🎯 핵심 요구사항 및 확정 사항

1. **템플릿 연동 (`default_a4_sentence.hwpx`)**:
   - `static/data/templates/default_a4_sentence.hwpx` A4 세로(Portrait) 양식을 마스터 템플릿으로 활용합니다.
   - 템플릿 상단의 1행 3열 표(학교명/메인제목/인적사항)와 유인물 메인 제목 `[ 제목 ]`을 동적으로 치환합니다.
2. **문장 추가 방식은 지문 추가 방식과 동일하게 구현**:
   - 지문 결과 화면에서 `[📄 유인물 담기]` 체크박스를 클릭하여 장바구니에 담듯이, **문장 검색 결과 화면(`sentenceViewContainer`)의 테이블 각 행에 `[ ] 유인물 담기` 체크박스를 추가**합니다.
   - 문장 체크 시 현재 활성 프로젝트의 문장 보관함에 즉시 추가되며, 하단 플로팅 카트 바(`handoutFloatingCart`)에 실시간으로 반영됩니다.
   - 상단 헤더에 `[☑ 선택 문장 일괄 담기]`, `[전체 선택]` 등의 교사 편의 도구를 제공합니다.
3. **'개념 설명' 1x1 테이블 선택 옵션 및 문장 수 규격 (6문장 vs 10문장)**:
   - 유인물 제작소에서 **'개념 설명 1x1 테이블 포함 여부'**를 교사가 체크박스로 선택할 수 있습니다.
   - **개념 설명 테이블 선택 시**:
     - 상단 1x1 '개념 정리' 표(height="17581")를 유지하고, 교사/학생 필기용 빈칸 공간으로 비워둡니다.
     - 하단 예문 표에 **총 6문장**을 배치합니다.
   - **개념 설명 테이블 미선택 시**:
     - 상단 1x1 '개념 정리' 표 행(Row 1)을 제거하여 상단 표를 컴팩트화하고,
     - 하단 예문 표에 **총 10문장**을 배치합니다.
4. **문장 포맷 및 충분한 줄간격 (구문 분석 및 필기 최적화)**:
   - **글자 크기**: 템플릿 가이드에 맞추어 **12 pt** (`height="1200"`) 적용.
   - **출처 표기**: 각 문장 시작 부분에 `[OOOO년 고O O월 OO번]` 규격으로 표시 (예: `[2024년 고3 6월 21번] The earliest humans lived...`).
   - **충분한 줄간격**: 학생들이 문장 아래에 슬래시(/) 구문 분석, 주어/동사 기호, 우리말 해석을 손필기할 수 있도록 **문단 줄간격 180%~200% 및 문장 간 빈 줄(Spaced Paragraph)**을 주입하여 쾌적한 필기 공간을 확보합니다.

---

## 2. 템플릿 XML 구조 정밀 분석 (`default_a4_sentence.hwpx`)

```
default_a4_sentence.hwpx (A4 세로형: 59528 x 84188, 본문 1단)
├── Contents/header.xml
│   ├── charProperties (글자 모양):
│   │   ├── id="8": 12.0pt 검은색
│   │   ├── id="15": 12.0pt 빨간색 (템플릿 플레이스홀더)
│   │   └── _inject_char_properties 로 12pt 검은색 non-bold charPr 등록
│   └── paraProperties (문단 모양):
│       └── id="19": 예문 전용 paraPr (lineSpacing 150%) ➜ 180%~200% 확장 또는 빈 문단 추가
└── Contents/section0.xml
    ├── P #0: 상단 헤더 및 개념 정리 1열 2행 테이블 (id: 1195242981)
    │   ├── Row 0: 1행 3열 머리말 표 (id: 1195242984)
    │   │   ├── Col 0: "왼쪽 상단" (학교명/과목)
    │   │   ├── Col 1: "가운데 상단" (교재명/시험명)
    │   │   └── Col 2: "오른쪽 상단" (인적사항/학번)
    │   │   └── 직하위 문단: [ 제목 ] (유인물 메인 타이틀)
    │   └── Row 1: '개념 정리(빈칸1x1)' 셀 (height: 17581)
    │       └── 🎯 '개념 설명 포함' 선택 시: 유지하고 빈칸화 / '미선택' 시: Row 1 완전 삭제
    └── P #1: 예문 본문 1열 1행 테이블 (id: 1214106299, height: 48428)
        └── tc > subList: 🎯 선택된 문장들 (6문장 또는 10문장)을 12pt, 충분한 줄간격으로 주입
```

---

## 3. 상세 화면 및 UX 흐름

```mermaid
flowchart TD
    A[문장 검색 결과 화면 (#sentenceViewContainer)] -->|각 행 체크박스 [ ] 유인물 담기| B[🛒 유인물 보관함 (Cart)]
    B -->|하단 플로팅 바 '문장 N개 유인물 만들기' 클릭| C[유인물 제작소 화면 (#handoutViewContainer)]

    subgraph C [유인물 제작소 화면]
        C_TAB{상단 탭 선택}
        C_TAB -->|지문 유인물 (B4)| C_PASSAGE[기존 지문 유인물 제작기]
        C_TAB -->|문장 유인물 (A4)| C_SENTENCE[문장 유인물 전용 제작기]

        subgraph C_SENTENCE [문장 유인물 제작기]
            S1[선택 문장 목록 / 순서 변경 / 삭제]
            S2[머리말 & 메인 제목 설정]
            S3[개념 설명 1x1 테이블 토글\n(☑ 포함: 6문장 / ⬜ 미포함: 10문장)]
            S4[다운로드 버튼]

            S1 --> S4
            S2 --> S4
            S3 --> S4
        end

        S4 -->|클릭| D[📝 문장 유인물 HWPX 다운로드\n(A4 단면, 개념설명 선택 반영, 12pt, 넓은 줄간격)]
    end
```

### 3-1. 문장 검색 결과 화면에서의 문장 선택 (`results-sentence.js`)
- 문장 테이블(`sentence-table`)의 첫 번째 열(⭐ 별표 옆)에 `[ ] 유인물 담기` 체크박스 컬럼 추가.
- 문장 행의 체크박스를 클릭하면 `toggleSentenceCart(sentenceId)`가 호출되어 프로젝트 장바구니에 담김.
- 상단 `sentence-header-actions`에 `[☑ 선택 문장 일괄 담기]` 편의 버튼 배치.
- 하단 플로팅 장바구니(`handoutFloatingCart`)에 현재 담긴 문장 수 실시간 표시:
  - 예: `지문 2문항 · 문장 6개` ➜ `[📄 유인물 제작소 이동]`.

### 3-2. 유인물 제작소 화면 (`#handoutViewContainer`)
- **상단 뷰 탭 전환기**:
  - `[ 📄 지문 유인물 (B4 단면 2문항) ]` | `[ 📝 문장 유인물 (A4 단면 구문 분석) ]`
- **문장 유인물 탭 활성화 시 화면 구성**:
  - **좌측 영역**: 선택된 문장 목록
    - 문장 카드별 순서 변경(`▲`, `▼`), 개별 삭제(`🗑️`), 전체 비우기
    - 문장 출처 배지 (예: `[2024년 고3 6월 21번]`) 및 문장 텍스트 프리뷰
    - 실시간 문장 수 및 권장 규격 안내:
      - 예: `현재 6문장 선택됨 (개념 설명 포함 시 1페이지 완성)`
  - **우측 영역**: 문장 유인물 서식 및 옵션 설정
    - **머리말 & 제목 설정**:
      - 왼쪽 상단 (예: `OO고등학교 영어과`)
      - 가운데 상단 (예: `2026학년도 1학기 기말고사 대비`)
      - 오른쪽 상단 (예: `제 2 학년 (   )반 (   )번  이름: (        )`)
      - 메인 제목 (예: `[ 관계대명사 that vs what 핵심 기출 뽀개기 ]`)
    - **'개념 설명' 1x1 테이블 옵션 스위치**:
      - `[☑ 개념 설명 1x1 테이블 포함 (총 6문장 권장)]`
      - 토글 체크 시: 상단 빈칸 개념 박스 생성 + 6문장 주입
      - 토글 해제 시: 상단 개념 박스 삭제 + 10문장 주입
    - **다운로드 액션 버튼**:
      - `[📝 문장 유인물 다운로드 (HWPX)]`

---

## 4. 백엔드 아키텍처 및 HWPX 생성 엔진 설계

### 4-1. HWPX 문장 유인물 생성 엔진 (`gichul/services/hwpx_generator.py`)

신규 함수 `generate_sentence_handout(items, options)` 추가:
1. **템플릿 로드**:
   - `static/data/templates/default_a4_sentence.hwpx`를 로드.
2. **글자 모양 및 문단 모양 설정 (`header.xml`)**:
   - 글자 크기 12pt (`height="1200"`), 검은색, non-bold charPr 등록.
   - 줄간격 180%~200%의 문장 전용 paraPr 등록.
3. **상단 표 조작 (`section0.xml` - `tbl` id=1195242981)**:
   - `Row 0`:
     - Col 0(왼쪽 상단), Col 1(가운데 상단), Col 2(오른쪽 상단) 텍스트 주입.
     - 메인 제목 문단: `[ {main_title} ]` 형태로 텍스트 치환.
   - `Row 1` ('개념 정리' 1x1 테이블):
     - `include_concept_table == True`: Row 1 유지, 기존 안내문구("개념 정리(빈칸1x1)") 제거 후 빈 문단(`""`)으로 비워 필기 공간 확보.
     - `include_concept_table == False`: `Row 1` 엘리먼트를 상단 테이블에서 완전히 제거(`tr.remove`), `tbl`의 `rowCnt`를 `"1"`로 갱신.
4. **예문 테이블 조작 (`section0.xml` - `tbl` id=1214106299)**:
   - 내부 셀(`tc > subList`)의 기존 힌트 필드를 모두 비움.
   - 개념 설명 포함 시 **최대 6문장**, 미포함 시 **최대 10문장** (선택 문장이 더 많을 경우 다페이지 생성 지원).
   - 각 문장 주입 포맷:
     - 출처 정규화: `[고3-2024년-06월-21번-3번째 문장]` ➜ `[2024년 고3 6월 21번]`
     - 문장 문단 생성: `[2024년 고3 6월 21번] {sentence_text}`
     - 문장 간 충분한 줄간격을 위해 각 문장 문단마다 줄간격 180%~200% 적용 및 문장 사이 공백 문단(`""`) 주입.

### 4-2. 유인물 REST API 라우터 (`gichul/routers/handouts.py`)

1. **문장 유인물 생성 엔드포인트**:
   - `POST /api/handouts/generate-sentence` (또는 `POST /api/handouts/generate` 내 `handout_type="sentence"` 분기 지원)
   - 파라미터:
     - `sentence_ids`: List[str]
     - `include_concept_table`: bool (True: 6문장, False: 10문장)
     - `header_left`, `header_center`, `header_right`, `main_title`: str
2. **문장 메타데이터 조회**:
   - DB에서 해당 문장들의 식별자, 순수 문장 텍스트, 기출 출처(연도/학년/월/번호)를 조회하여 HWPX 생성기로 전달.

---

## 5. 프론트엔드 모듈 격리 및 상태 관리 설계

### 5-1. 장바구니 상태 관리 (`static/js/handout-cart.js`)
기존 프로젝트 구조에 `sentence_items` 필드를 추가하여 지문과 문장을 프로젝트 단위로 완벽하게 공존 및 격리 관리:
```javascript
{
  id: "proj_default",
  name: "기본 프로젝트",
  items: [ /* 지문 ID 목록 */ ],
  sentence_items: [ /* 선택된 문장 ID 목록 */ ],
  sentence_settings: {
    include_concept_table: true,
    main_title: "핵심 기출 구문 분석",
    header_left: "OO고등학교 영어과",
    header_center: "2026학년도 기출 모의고사",
    header_right: "제 2 학년 (   )반 (   )번  이름: (        )"
  }
}
```
- 문장 전용 카트 함수 제공: `getSentenceCartItems()`, `addToSentenceCart(id)`, `removeFromSentenceCart(id)`, `toggleSentenceCart(id)`, `clearSentenceCart()`.

### 5-2. 문장 검색 결과 화면 (`static/js/results-sentence.js`)
- `createSentenceRow(s, currentQuery)`:
  - 1열에 `<input type="checkbox" class="handout-sentence-select-chk">` 렌더링.
  - 카트에 담겨있는지 여부에 따라 checked 동기화.
  - 클릭 시 `toggleSentenceCart(s.id)` 호출 및 하단 플로팅 바 갱신.
- 헤더에 `[☑ 선택 문장 담기]` 버튼 제공.

### 5-3. 문장 유인물 제작소 화면 (`static/js/handout-sentence.js` 또는 `handout-passage.js`)
- 유인물 제작소 상단에 `[지문 유인물]` / `[문장 유인물]` 탭 전환 UI 연동.
- 문장 유인물 탭에서 선택 문장 렌더링, 순서 변경, 개념 설명 테이블 체크박스 토글, HWPX 다운로드 비동기 요청 처리.

---

## 6. 단계별 구현 로드맵 (총 4단계)

```
[1단계: 백엔드 HWPX 문장 유인물 생성 엔진 구현]
 ├── gichul/services/hwpx_generator.py 내 generate_sentence_handout() 구현:
 │    ├── default_a4_sentence.hwpx 로드 및 12pt 글자크기/줄간격 서식 주입
 │    ├── 상단 1x3 표(머리말) 및 [ 제목 ] 치환
 │    ├── 개념 설명 1x1 테이블(Row 1) 선택 여부(True/False)에 따른 보존/삭제 분기
 │    ├── [OOOO년 고O O월 OO번] 출처 정규화 및 문장 텍스트(6개 / 10개) 주입
 │    └── 문장 간 넉넉한 줄간격 및 공백 문단 주입
 └── pytest 단위 테스트(tests/test_sentence_hwpx.py) 작성 및 HWPX 무결성 검증

[2단계: 문장 유인물 REST API 라우터 구현]
 ├── gichul/routers/handouts.py 에 문장 유인물 요청 모델(SentenceHandoutGenerateRequest) 추가
 ├── POST /api/handouts/generate-sentence 구현 (문장 데이터 DB 조회 및 HWPX 스트리밍)
 └── 터미널 정적 구문 검증 (python -m py_compile)

[3단계: 프론트엔드 장바구니 및 문장 검색 결과 화면 연동]
 ├── static/js/handout-cart.js 에 문장 보관함(sentence_items) 상태 관리 및 이벤트 추가
 ├── static/js/results-sentence.js 테이블 각 행에 유인물 담기 체크박스 연동
 └── 하단 플로팅 바(handoutFloatingCart)에 문장 선택 수 실시간 반영

[4단계: 유인물 제작소 문장 뷰 완성 및 HWPX 다운로드 연동]
 ├── templates/index.html 내 유인물 제작소 탭(지문/문장) 및 문장 유인물 설정 폼 추가
 ├── static/js/handout-passage.js (또는 신규 handout-sentence.js) 문장 유인물 뷰 로직 작성:
 │    ├── 선택 문장 목록 렌더링, 순서 변경(▲, ▼), 삭제(🗑️)
 │    ├── 개념 설명 1x1 테이블 포함 여부 체크박스(6문장 vs 10문장 가이드)
 │    └── HWPX 다운로드 비동기 호출 및 C드라이브 다운로드 폴더 저장 알림
 └── 터미널 정적 검증 (node -c, py_compile)
```

---

## 7. 진행 현황 (Tracking Table)

| 단계 | 작업 내용 | 상태 | 비고 |
|---|---|:---:|---|
| **설계** | A4 문장 유인물 템플릿 XML 분석 및 개념 설명(6/10문장) 규격 수립 | ✅ 완료 | 본 계획서 수립 |
| **1단계** | 백엔드 `generate_sentence_handout` 엔진 구현 및 12pt/줄간격 주입 | ✅ 완료 | `hwpx_generator.py` 구현 및 단위 테스트 통과 |
| **2단계** | 유인물 REST API (`POST /api/handouts/generate-sentence`) 구현 | ✅ 완료 | `handouts.py` 라우터 및 프리뷰 API 구현 |
| **3단계** | 문장 검색 테이블 체크박스 및 장바구니(`handout-cart.js`) 연동 | ✅ 완료 | `results-sentence.js` 및 플로팅 카트 바 연동 |
| **4단계** | 유인물 제작소 내 문장 유인물 탭, 개념 테이블 토글 및 다운로드 완성 | ✅ 완료 | `handout-sentence.js` 구현 및 HWPX 다운로드 연동 |

---

## 8. 검증 계획

1. **정적 구문 검증**:
   - `python -m py_compile gichul/services/hwpx_generator.py gichul/routers/handouts.py`
   - `node -c static/js/results-sentence.js static/js/handout-cart.js static/js/handout-passage.js`
2. **HWPX 생성 무결성 검증**:
   - `pytest tests/test_sentence_hwpx.py`:
     - 개념 설명 O 옵션: 상단 Row 1 보존, 6문장 주입, 글자크기 12pt 검증
     - 개념 설명 X 옵션: 상단 Row 1 삭제, 10문장 주입, 글자크기 12pt 검증
     - 출처 표기 `[OOOO년 고O O월 OO번]` 형식 일치 여부 검증
3. **Rule 1 & Rule 3 준수**:
   - 브라우저 자동 실행 없음.
   - 자동 Git 커밋/푸시 금지 (사용자의 명시적 `/git-commit` 수신 시에만 실행).
