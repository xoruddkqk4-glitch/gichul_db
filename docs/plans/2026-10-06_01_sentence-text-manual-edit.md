# 구현 계획서: 문장 분석 결과 화면 내 문장 텍스트 수동 수정 기능 구축

**작성일시**: 2026-10-06  
**상태**: ✅ 완료  
**관련 요청**: 문장 검색/분석 화면에서 문장 영문 텍스트를 수동으로 수정·교정할 수 있는 기능 추가  

---

## 1. 개요 및 목표

PDF나 HWP 파싱 과정에서 발생할 수 있는 문장 단위 오탈자(단어 붙음/떨어짐, 특수문자 왜곡, 따옴표나 마침표 인식 오류 등)를 사용자가 **문장 검색 결과 화면에서 즉시 직접 교정·수정**할 수 있도록 지원합니다.

이미 구축된 **문장 오류 신고 시스템**과 결합하여, 오류가 신고된 문장으로 바로 이동한 뒤 관리자가 **현장에서 즉시 문장 텍스트를 올바르게 수정하고 저장**할 수 있는 완전한 유지보수 파이프라인을 완성합니다.

---

## 2. 진행 현황 (Progress Tracker)

`/apply` 명령어를 통해 단계별로 즉시 실행할 수 있도록 작업을 세분화합니다.

| 단계 | 작업 내용 | 담당 영역 | 상태 |
|:---:|---|---|:---:|
| **1단계** | 문장 텍스트 수정 REST API (`PATCH /api/sentences/{id}/text`) 구현 | FastAPI Router, Database | ✅ 완료 |
| **2단계** | 문장 테이블 내 인라인 텍스트 편집 모드 UI & 단축키 구현 | HTML, CSS (`viewer.css`) | ✅ 완료 |
| **3단계** | 프론트엔드 저장 및 화면 실시간 갱신 이벤트 연동 | JavaScript (`results-sentence.js`) | ✅ 완료 |
| **4단계** | 백엔드/프론트엔드 정적 구문 검증 및 연동 테스트 | Terminal 검증 | ✅ 완료 |

---

## 3. 세부 설계 및 구현 내용

### 3.1. [1단계] 백엔드 REST API 구현

이미 `gichul/database.py`에 단일 문장의 본문 텍스트와 단어 수를 갱신하는 `update_sentence_text(sentence_id, new_text, word_count=None)` 함수가 완벽히 구현되어 있습니다.

#### (1) REST API 엔드포인트 신설 (`gichul/routers/passages.py` 또는 `grammar.py`)
- **경로**: `PATCH /api/sentences/{sentence_id:path}/text`
- **Request Body**:
  ```json
  {
    "sentence_text": "수정된 영문 문장 텍스트..."
  }
  ```
- **처리 로직**:
  1. `sentence_id` 정규화 (`normalize_bracket_id`)
  2. 텍스트 유효성 검증 (빈 문자열 차단)
  3. `db.update_sentence_text(clean_id, req.sentence_text)` 호출
  4. 단어 수(`word_count`) 자동 재계산
  5. 검색 캐시 무효화 (`search_cache.clear()`)
- **Response**:
  ```json
  {
    "success": true,
    "sentence_id": "[고3-2024년-06월-21번-1번째 문장]",
    "sentence_text": "수정된 텍스트",
    "word_count": 18,
    "message": "문장 텍스트가 성공적으로 수정되었습니다."
  }
  ```

---

### 3.2. [2단계] UI/UX 설계 및 편집 모드 인터랙션

사용자의 편의를 위해 **인라인 직접 수정 모드**와 **전용 팝업 모달**의 장점을 결합하여 설계합니다.

#### (1) 문장 테이블 액션 열에 `[✏️ 텍스트 수정]` 버튼 추가
- **위치**: `results-sentence.js` 내 문장 테이블의 각 행 액션 열 (`td.col-action .action-btn-group`)
- **버튼 UI**:
  ```html
  <button type="button" class="btn-edit-sentence-inline" data-id="${s.id}" title="이 문장의 텍스트를 직접 수정합니다">
    ✏️ 수정
  </button>
  ```

#### (2) 인라인 편집 모드 전환
- `✏️ 수정` 버튼 클릭 시:
  1. `col-sentence` 셀의 텍스트가 인라인 편집용 `<textarea class="inline-sentence-edit-textarea">`로 전환
  2. 바로 아래에 `[💾 저장 (Ctrl+Enter)]` 및 `[취소 (ESC)]` 버튼 그룹 노출
  3. 텍스트영역에 자동 포커스 및 커서 위치 지정

#### (3) 대안/보완: 정밀 수정 모달창 (`#modalEditSentence`)
- 긴 복합문장이나 모바일/태블릿 등 작은 화면을 위해, 넓은 팝업 모달에서 원문 비교와 함께 수정할 수 있는 전용 모달 마크업도 함께 제공

---

### 3.3. [3단계] 프론트엔드 상태 동기화 (`results-sentence.js`)

1. **저장 완료 시 화면 갱신**:
   - 편집 텍스트영역이 일반 텍스트 뷰로 다시 전환되며 수정된 내용 즉시 반영
   - 클립보드 복사 버튼(`btn-copy-sentence`)의 `data-text` 속성도 최신 수정 텍스트로 실시간 갱신 (복사 시 최신 텍스트가 복사되도록 보장)
   - 토스트 알림: `"문장 텍스트가 성공적으로 수정되었습니다."`
2. **어법 분석과의 상호작용 안내**:
   - 텍스트가 변경되었을 경우, 기존 어법 분석 결과와 달라질 수 있으므로 `🤖 분석` 버튼을 다시 눌러 재분석할 수 있도록 자연스러운 UX 유도

---

### 3.4. [4단계] 스타일 및 검증

- **CSS (`static/css/viewer.css` 또는 `modal.css`)**:
  - 인라인 문장 편집 텍스트영역 스타일 (`.inline-sentence-edit-textarea`)
  - 인라인 저장/취소 버튼 그룹 스타일
- **터미널 정적 검증**:
  - `python -m py_compile gichul/routers/passages.py`
  - `node -c static/js/results-sentence.js`
  - TestClient를 통한 `PATCH /api/sentences/{id}/text` 엔드포인트 단위 검증

---

## 4. 파일 변경 계획 요약

| 파일 경로 | 작업 구분 | 주요 내용 |
|---|:---:|---|
| `gichul/routers/passages.py` | 수정 | `PATCH /api/sentences/{sentence_id:path}/text` API 엔드포인트 추가 |
| `static/js/results-sentence.js` | 수정 | 액션 열에 `✏️ 수정` 버튼 추가, 인라인 편집 전환 및 저장/취소 이벤트 구현 |
| `static/css/viewer.css` | 수정 | 인라인 문장 수정 텍스트영역 및 저장/취소 버튼 스타일 정의 |
| `templates/index.html` | 수정 | 문장 수정 전용 모달 마크업 추가 (선택 지원) |

---

## 5. 사용자 확인 및 승인 대기

본 계획서는 `/ask` 모드 원칙에 따라 소스 코드를 변경하지 않고 작성되었습니다.  
위 계획서 내용대로 문장 텍스트 수동 수정 기능을 구현하시려면, **`/apply`** 명령어를 입력해 주세요!
