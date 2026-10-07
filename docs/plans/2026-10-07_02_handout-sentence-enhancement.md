# 교사용 유인물 제작소 화면·프로젝트 분리 및 문장 번호 부여 고도화 계획서

> [!NOTE]
> `/ask` 모드로 작성된 구현 계획서입니다. **기존 소스 코드는 일절 수정하지 않았으며 분석 및 설계만 진행되었습니다.**
> 본 계획서는 사용자의 명시적인 `/apply` 명령어를 통해 안전하게 코드에 단계별로 반영될 예정입니다.

- **문서 번호**: PLAN-2026-10-07-02
- **작성 일시**: 2026-10-07 (KST)
- **관련 계획서**: [PLAN-2026-10-07-01 (문장 유인물 자동 제작)](plans/2026-10-07_01_handout-sentence-generation.md)
- **상태**: ✅ 완료 (2026-10-07 반영 완료)

---

## 1. 개요 및 사용자 요구사항 분석

교사용 유인물 제작소에 문장 유인물 기능이 추가된 후, 실제 수업 준비 워크플로우를 극대화하기 위해 접수된 4가지 핵심 개선 사항을 체계적으로 설계합니다.

### 🎯 4대 핵심 요구사항 및 분석

1. **문장 유인물은 해설 유인물이 불필요 (문제/구문분석 단일 유인물 전용)**:
   - 지문 유인물은 모의고사 형식이므로 `문제지 HWPX`, `해설지 HWPX`, `일괄 다운로드 ZIP`이 필요합니다.
   - 반면, 문장 유인물은 수업 현장의 구문 분석 및 필기 연습용 A4 단면 인쇄물이므로 **해설 유인물(정답지)이 필요하지 않습니다**.
   - 따라서 문장 유인물 화면에서는 해설 관련 옵션이나 버튼을 일절 노출하지 않고, 오직 `[📝 문장 유인물 다운로드 (HWPX)]` 단일 다운로드 워크플로우를 유지 및 명확화합니다.

2. **'유인물 제작소' 화면에서 지문 유인물과 문장 유인물 화면의 명확한 분리 및 선택**:
   - 기존에는 상단에 "교사용 지문 유인물 제작소"라는 고정 헤더와 단일 프로젝트 바가 최상단에 있고, 그 아래에 작은 탭이 배치되어 있어 지문 유인물 화면에 문장 유인물이 종속된 것처럼 보였습니다.
   - 개선: 유인물 제작소 진입 시 상단에 **대형 모드 선택기(Segmented Mode Switcher)**를 배치하여,
     - **[📄 지문 유인물 제작소 (B4 2문항)]**
     - **[📝 문장 유인물 제작소 (A4 구문분석)]**
     두 화면의 헤더 설명, 통계 배지, 프로젝트 관리 바, 복귀 버튼이 서로 독립적으로 분리되어 동작하도록 구성합니다.

3. **'유인물 제작소'의 프로젝트를 지문용과 문장용으로 완전 분리**:
   - 기존에는 하나의 프로젝트 안에 `items`(지문 ID)와 `sentence_items`(문장 ID)가 혼재되어, 프로젝트를 만들거나 변경할 때 지문 묶음과 문장 묶음이 뒤섞였습니다.
   - 개선: **지문 프로젝트 목록(`passage_projects`)**과 **문장 프로젝트 목록(`sentence_projects`)**을 저장소(`localStorage`) 및 UI 셀렉터 레벨에서 완전히 분리합니다.
     - 지문 제작소: `📁 지문 프로젝트:` (지문 프로젝트만 표시/추가/변경/삭제)
     - 문장 제작소: `📁 문장 프로젝트:` (문장 프로젝트만 표시/추가/변경/삭제)
     - 하단 플로팅 카트 바: 지문 검색 화면에서는 지문 프로젝트/지문 카트 연동, 문장 검색 화면에서는 문장 프로젝트/문장 카트 연동.
     - 기존 단일 프로젝트 데이터는 첫 실행 시 지문/문장 프로젝트로 유실 없이 자동 마이그레이션.

4. **문장 유인물에 '문장 번호' 추가 (1번부터 / N번부터 재부여 지원)**:
   - 기존 문장 유인물은 `[2024년 고3 6월 21번] The earliest humans lived...` 형태로 출처와 문장 본문만 표기되어 수업 중 번호(예: "3번 문장 봅시다")로 호명하기 어려웠습니다.
   - 개선:
     - 유인물에 출력될 때 각 문장 앞에 **문장 번호**를 반드시 주입합니다:
       `1. [2024년 고3 6월 21번] The earliest humans lived...`
     - 지문 유인물과 동일하게 문장 유인물 툴바에 **번호 재부여 도구**를 제공합니다:
       - `[🔢 1번부터 순차 재부여]` 버튼
       - `[시작 번호(N) 입력창]` + `[번부터 부여]` 버튼
     - 각 문장 카드 좌측 상단에 인라인 번호 배지 및 입력 필드를 제공하여 특정 번호 직접 수정 지원.

---

## 2. 화면 구조 및 UX 전환 흐름도

```mermaid
flowchart TD
    MAIN[메인 화면] -->|📄 유인물 제작소 클릭| HANDOUT_VIEW[유인물 제작소 #handoutViewContainer]
    
    subgraph HANDOUT_VIEW [교사용 유인물 제작소]
        MODE_BAR[상단 대형 모드 선택기\n[ 📄 지문 유인물 제작소 ] ↔ [ 📝 문장 유인물 제작소 ]]
        
        MODE_BAR -->|지문 유인물 선택| PASSAGE_VIEW[지문 유인물 전용 화면]
        MODE_BAR -->|문장 유인물 선택| SENTENCE_VIEW[문장 유인물 전용 화면]
        
        subgraph PASSAGE_VIEW [지문 유인물 모드]
            P_HDR[헤더: B4 2문항 문제지/해설지 안내 & 지문 문항 수]
            P_PROJ[지문 전용 프로젝트 바\n(📁 지문 기본 프로젝트, ➕새 프로젝트, ✏️이름, 🗑️삭제)]
            P_LIST[선택 지문 카드 목록 (1번부터/N번부터 재부여)]
            P_SET[서식 & 머리말/꼬리말 & 정답형광펜]
            P_BTN[다운로드 3종: 문제지 / 해설지 / 일괄 ZIP]
            
            P_HDR --> P_PROJ --> P_LIST & P_SET --> P_BTN
        end
        
        subgraph SENTENCE_VIEW [문장 유인물 모드]
            S_HDR[헤더: A4 단면 구문 분석 훈련 안내 (해설 불필요) & 문장 수]
            S_PROJ[문장 전용 프로젝트 바\n(📁 문장 기본 프로젝트, ➕새 프로젝트, ✏️이름, 🗑️삭제)]
            S_LIST[선택 문장 카드 목록\n(🔢 1번부터 순차 재부여 / N번부터 부여 / 개별 번호 수정)]
            S_SET[머리말 & 메인 제목 & 개념 설명 1x1 테이블 토글(6개/10개)]
            S_BTN[단일 다운로드: 📝 문장 유인물 다운로드 (HWPX)]
            
            S_HDR --> S_PROJ --> S_LIST & S_SET --> S_BTN
        end
    end
```

---

## 3. 상세 설계

### 3-1. 프로젝트 상태 분리 및 마이그레이션 (`static/js/handout-cart.js`)

#### 1) 저장소 키(Storage Key) 완전 분리
```javascript
// 지문 전용 프로젝트 키
const KEY_PASSAGE_PROJECTS = "gichul_handout_passage_projects";
const KEY_CURRENT_PASSAGE_PROJECT_ID = "gichul_handout_cur_passage_proj_id";

// 문장 전용 프로젝트 키
const KEY_SENTENCE_PROJECTS = "gichul_handout_sentence_projects";
const KEY_CURRENT_SENTENCE_PROJECT_ID = "gichul_handout_cur_sentence_proj_id";
```

#### 2) 기존 데이터 자동 마이그레이션 로직
- 브라우저 로컬스토리지에 기존 통합 키(`gichul_handout_projects`)가 존재하는 경우:
  - 지문 문항(`items`)이 포함된 데이터 ➜ `gichul_handout_passage_projects`로 자동 이전.
  - 문장 문항(`sentence_items`)이 포함된 데이터 ➜ `gichul_handout_sentence_projects`로 자동 이전.
  - 기존 사용자의 작업 데이터가 100% 안전하게 보존되도록 구현.

#### 3) 독립적인 프로젝트 API 세트 제공
- **지문 프로젝트 API**:
  - `getPassageProjects()`, `getCurrentPassageProject()`, `setCurrentPassageProject(id)`, `createPassageProject(name)`, `renamePassageProject(id, name)`, `deletePassageProject(id)`
  - `getCartItems()` (지문 아이템 목록), `addToCart(id)`, `removeFromCart(id)` 등
- **문장 프로젝트 API**:
  - `getSentenceProjects()`, `getCurrentSentenceProject()`, `setCurrentSentenceProject(id)`, `createSentenceProject(name)`, `renameSentenceProject(id, name)`, `deleteSentenceProject(id)`
  - `getSentenceCartItems()` (문장 아이템 목록: `{ id, custom_num }`), `addToSentenceCart(id)`, `removeFromSentenceCart(id)`, `reorderSentenceCart(...)`, `updateSentenceCustomNums(numMap)`

#### 4) 하단 플로팅 카트 바 (`handoutFloatingCart`) 모드별 동적 연동
- 검색 모드가 지문 모드(`passage`)일 때:
  - 지문 프로젝트 드롭다운 표시, 지문 담긴 수 배지(`N문항`), 클릭 시 지문 유인물 제작소로 이동.
- 검색 모드가 문장 모드(`sentence`)일 때:
  - 문장 프로젝트 드롭다운 표시, 문장 담긴 수 배지(`N문장`), 클릭 시 문장 유인물 제작소로 이동.

---

### 3-2. 유인물 제작소 화면 분리 및 UI 마크업 (`templates/index.html`, `static/css/handouts.css`)

#### 1) 최상단 대형 모드 선택기 (Segmented Switcher)
- 기존의 작은 탭 버튼을 세련되고 직관적인 **대형 모드 선택 카드 버튼**으로 승격:
  ```html
  <div class="handout-mode-selector-bar" id="handoutModeSelectorBar">
    <button type="button" class="btn-handout-mode-selector active" id="tabHandoutPassage" data-tab="passage">
      <span class="mode-icon">📄</span>
      <div class="mode-text-wrap">
        <span class="mode-title">지문 유인물 제작소</span>
        <span class="mode-desc">B4 단면 2문항 규격 (문제지·해설지)</span>
      </div>
    </button>
    <button type="button" class="btn-handout-mode-selector" id="tabHandoutSentence" data-tab="sentence">
      <span class="mode-icon">📝</span>
      <div class="mode-text-wrap">
        <span class="mode-title">문장 유인물 제작소</span>
        <span class="mode-desc">A4 단면 구문 분석 훈련 (문제지 전용)</span>
      </div>
    </button>
  </div>
  ```

#### 2) 프로젝트 바 분리
- **지문 전용 프로젝트 바 (`handoutPassageProjectBar`)**:
  - `#selectHandoutPassageProject`, `#btnCreatePassageProject`, `#btnRenamePassageProject`, `#btnDeletePassageProject`
  - 지문 프로젝트 메타 정보(`txtPassageProjectMetaInfo`) 표시.
- **문장 전용 프로젝트 바 (`handoutSentenceProjectBar`)**:
  - `#selectHandoutSentenceProject`, `#btnCreateSentenceProject`, `#btnRenameSentenceProject`, `#btnDeleteSentenceProject`
  - 문장 프로젝트 메타 정보(`txtSentenceProjectMetaInfo`) 표시.

#### 3) 문장 유인물 툴바에 문장 번호 재부여 컨트롤 추가
- 문장 목록 툴바(`handout-sentence-toolbar`)에 번호 부여 도구 배치:
  ```html
  <div class="handout-toolbar-actions">
    <button type="button" class="btn-handout-tool" id="btnSentenceRenumber1" title="모든 문장 번호를 1번부터 차례대로 다시 매깁니다">
      🔢 1번부터 순차 재부여
    </button>
    <div style="display: inline-flex; align-items: center; gap: 4px;">
      <input type="number" class="input-start-num" id="inputSentenceStartNum" value="1" min="1" max="999" title="시작 번호">
      <button type="button" class="btn-handout-tool" id="btnSentenceRenumberN" title="지정한 시작 번호부터 차례대로 다시 매깁니다">
        번부터 부여
      </button>
    </div>
    <button type="button" class="btn-handout-tool" id="btnSentenceClearAll" style="color: #ef4444;" title="모든 문장을 비웁니다">
      🗑️ 전체 비우기
    </button>
  </div>
  ```

---

### 3-3. 문장 번호 부여 프론트 및 백엔드 로직

#### 1) 문장 카드 인라인 번호 편집 (`static/js/handout-sentence.js`)
- 각 문장 카드 렌더링 시 문장 번호 배지 및 입력 필드 표시:
  - `<input type="number" class="sentence-num-input" data-id="${s.id}" value="${customNum}" min="1" max="999">`
- `custom_sentence_nums` 맵 객체 관리 (문장 ID ➜ 지정된 번호).
- 번호 재부여 버튼 클릭 시 즉시 카드들의 번호를 1, 2, 3... 또는 N, N+1, N+2...로 갱신.
- 다운로드 요청 시 `custom_sentence_nums`를 API 페이로드에 전달.

#### 2) REST API 모델 확장 (`gichul/routers/handouts.py`)
```python
class SentenceHandoutGenerateRequest(BaseModel):
    sentence_ids: List[str] = Field(default_factory=list)
    custom_sentence_nums: Dict[str, str] = Field(default_factory=dict, description="문장 ID별 지정 번호 맵")
    start_num: int = Field(default=1, description="미지정 문장 시작 번호")
    include_concept_table: bool = Field(default=True)
    main_title: Optional[str] = Field(default="핵심 기출 구문 분석")
    header_left: Optional[str] = Field(default="")
    header_center: Optional[str] = Field(default="")
    header_right: Optional[str] = Field(default="")
    template_name: Optional[str] = Field(default=None)
```

#### 3) HWPX 문장 생성 엔진 번호 주입 (`gichul/services/hwpx_generator.py`)
- `generate_sentence_handout(items, options)`:
  - 각 문장에 번호 주입:
    ```python
    custom_num = str(s.get("custom_num") or (s_idx + 1)).strip()
    full_line = f"{custom_num}. {src_str} {sent_text}"
    ```
  - 결과 출력 예시:
    `1. [2024년 고3 6월 21번] The earliest humans lived in small groups...`
    `2. [2024년 고3 9월 29번] In the modern era, technological advances...`
  - 12pt 글자크기 및 180% 줄간격 서식과 결합되어 가독성이 극대화됩니다.

---

## 4. 단계별 구현 계획 (Roadmap)

```
[1단계: 프로젝트 저장소(Storage) 지문/문장 완전 분리]
 ├── static/js/handout-cart.js 수정:
 │    ├── KEY_PASSAGE_PROJECTS 및 KEY_SENTENCE_PROJECTS 분리
 │    ├── 기존 통합 프로젝트 데이터 자동 마이그레이션 함수 구현
 │    ├── 지문/문장 프로젝트 CRUD 함수 독립화
 │    └── 하단 플로팅 카트 바(handoutFloatingCart) 현재 모드(지문/문장) 맞춤 동적 연동
 └── 터미널 구문 검증 (node -c)

[2단계: 유인물 제작소 화면 분리 마크업 및 스타일링]
 ├── templates/index.html 수정:
 │    ├── 상단 대형 모드 선택기(Segmented Mode Switcher) 도입
 │    ├── 헤더 바(타이틀/안내문구/통계/복귀버튼) 모드별 동적 전환 지원
 │    ├── 지문 프로젝트 바(#handoutPassageProjectBar)와 문장 프로젝트 바(#handoutSentenceProjectBar) 분리
 │    └── 문장 툴바에 번호 재부여(1번부터 / N번부터) 컨트롤 추가
 ├── static/css/handouts.css 수정:
 │    └── 대형 모드 선택 카드 및 문장 번호 인라인 입력 스타일 추가
 └── 터미널 검증

[3단계: 문장 유인물 전용 뷰 및 번호 관리 프론트 연동]
 ├── static/js/handout-sentence.js 수정:
 │    ├── 문장 프로젝트 바 이벤트(선택/생성/이름/삭제) 독립 바인딩
 │    ├── 문장 번호 상태(custom_sentence_nums) 관리
 │    ├── 1번부터 / N번부터 재부여 버튼 이벤트 구현
 │    ├── 문장 카드별 인라인 번호 편집 및 순서 이동 시 번호 연동
 │    └── 다운로드 요청 시 custom_sentence_nums 전달
 ├── static/js/handout-passage.js 수정:
 │    └── 지문 프로젝트 바 독립 바인딩 확인
 ├── static/js/navigation.js 수정:
 │    └── 지문/문장 모드 전환 시 헤더 텍스트, 프로젝트 바, 레이아웃 동기화
 └── 터미널 구문 검증 (node -c)

[4단계: 백엔드 문장 번호 수신 및 HWPX 주입 엔진 완성]
 ├── gichul/routers/handouts.py 수정:
 │    └── SentenceHandoutGenerateRequest에 custom_sentence_nums 추가 및 아이템 매핑
 ├── gichul/services/hwpx_generator.py 수정:
 │    └── generate_sentence_handout()에서 문장 번호({custom_num}. [출처] {본문}) 주입
 ├── tests/test_sentence_hwpx.py 수정:
 │    └── 문장 번호 주입(1., 2. 또는 사용자 지정 번호) 검증 테스트 케이스 추가
 └── 터미널 검증 (pytest, py_compile)
```

---

## 5. 진행 현황 (Tracking Table)

| 단계 | 작업 내용 | 상태 | 비고 |
|---|---|:---:|---|
| **설계** | 화면·프로젝트 분리, 문장 번호 부여, 해설 제외 규격 수립 | ✅ 완료 | 본 계획서 수립 |
| **1단계** | 프로젝트 저장소(localStorage) 지문용 / 문장용 완전 분리 및 마이그레이션 | ✅ 완료 | `handout-cart.js` 분리 및 모드별 플로팅 바 동기화 |
| **2단계** | 유인물 제작소 상단 대형 모드 선택기 및 지문/문장 프로젝트 바 마크업 분리 | ✅ 완료 | `index.html`, `handouts.css` 세그먼트 스위처 적용 |
| **3단계** | 문장 유인물 전용 뷰, 번호 재부여(1번/N번) 및 인라인 편집 로직 구현 | ✅ 완료 | `handout-sentence.js` 번호 재부여 및 편집 연동 |
| **4단계** | 백엔드 API 및 HWPX 엔진 문장 번호 주입 완성 및 단위 테스트 통과 | ✅ 완료 | `hwpx_generator.py`, `handouts.py`, `test_sentence_hwpx.py` 12개 통과 |

---

## 6. 검증 계획

1. **정적 구문 검증 (Rule 2)**:
   - `python -m py_compile gichul/services/hwpx_generator.py gichul/routers/handouts.py`
   - `node -c static/js/handout-cart.js static/js/handout-sentence.js static/js/handout-passage.js static/js/navigation.js`
2. **단위 및 통합 테스트**:
   - `pytest tests/test_sentence_hwpx.py`:
     - 문장 번호 주입 형식 검증: `r"^\d+\.\s+\[\d{4}년.*\]"`
     - 지정 번호(custom_sentence_nums) 반영 확인
     - 해설지 없이 단일 문제지 스트리밍 정상 여부 확인
3. **규칙 준수 (Rule 1 & Rule 3)**:
   - 브라우저 자동 실행 없음.
   - 자동 Git 커밋/푸시 금지 (사용자의 명시적 `/git-commit` 수신 시에만 실행).
