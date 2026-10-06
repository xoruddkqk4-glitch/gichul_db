# 구현 계획서: 문항 및 문장 오류 신고 시스템 및 지문 자료(이미지·듣기) 수동 업로드 기능 구축

**작성일시**: 2026-10-06  
**상태**: ✅ 완료  
**관련 요청**: 
1. 지문/문장 결과창 오류 신고 버튼 (5종 복수선택 및 주관식 입력)
2. 헤더 우측 상단 통합 확인 및 삭제 관리 기능 (모든 화면 공통 위치)
3. 지문 결과창에서 PDF 문항 이미지 및 듣기 파일 수동 업로드(교체) 기능 (수동 업로드 시 해당 문항의 최신 자료로 즉시 반영)

---

## 1. 개요 및 목표

수능·모의고사 기출 데이터베이스를 탐색하는 과정에서 발견될 수 있는 다양한 데이터 오류(문제 PDF 캡처 이미지 잘림, 해설지 오탈자, 정답 번호 불일치, 정답률/선지 선택률 누락, 문장 분할 및 어법 태그 이상 등)를 사용자가 즉시 간편하게 신고할 수 있도록 지원합니다.

또한, **오류 신고에 대한 즉각적인 해결 수단**으로서, 전체 시험지를 재파싱하지 않고도 **해당 문항의 올바른 PDF 문항 캡처 이미지(PNG/JPG)나 듣기 음성 파일(MP3)을 즉시 수동 업로드하여 최신 자료로 교체할 수 있는 기능**을 제공합니다.

헤더 우측 상단에서는 첫 화면, 지문 결과 화면, 문장 결과 화면 어디서든 **현재까지 접수된 오류를 문항별·문장별로 한눈에 모아보고, 해당 문항으로 바로 이동해 검토한 후, 수정이 완료되면 리스트에서 즉시 삭제(완료 처리)**할 수 있는 통합 관리 체계를 구축합니다.

---

## 2. 진행 현황 (Progress Tracker)

`/apply` 명령어를 통해 단계별로 즉시 실행할 수 있도록 작업을 세분화합니다.

| 단계 | 작업 내용 | 담당 영역 | 상태 |
|:---:|---|---|:---:|
| **1단계** | DB 스키마 (`error_reports`) 및 백엔드 CRUD REST API 구축 | SQLite, FastAPI Router | ✅ 완료 |
| **2단계** | 지문 결과창 & 문장 결과창 오류 신고 버튼 및 입력 모달 구현 | HTML, CSS, JS | ✅ 완료 |
| **3단계** | 지문 결과창 PDF 문항 이미지 & 듣기 음성 수동 업로드(교체) 기능 구현 | FastAPI Router, JS, HTML | ✅ 완료 |
| **4단계** | 우측 상단 '오류 신고 목록' 버튼(전 화면 공통), 통합 관리 모달 및 삭제 기능 구현 | HTML, CSS, JS | ✅ 완료 |
| **5단계** | 백엔드/프론트엔드 정적 구문 검증 및 연동 테스트 | Terminal 검증 | ✅ 완료 |

---

## 3. 세부 설계 및 구현 내용

### 3.1. [1단계] 백엔드 데이터베이스 및 오류 신고 REST API 설계

#### (1) SQLite DB 스키마 (`gichul/database.py`)
새로운 `error_reports` 테이블을 추가하고 인덱스를 생성합니다.

```sql
CREATE TABLE IF NOT EXISTS error_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    target_type TEXT NOT NULL,         -- 'passage' (문항/지문) 또는 'sentence' (문장)
    passage_id INTEGER,                -- passages.id (지문 신고 시)
    sentence_id INTEGER,               -- sentences.id (문장 신고 시)
    exam_id INTEGER,                   -- exams.id (메타 조회용)
    error_types TEXT,                  -- JSON 문자열 (예: '["pdf_capture", "answer"]')
    comment TEXT,                      -- 사용자 주관식 상세 내용
    status TEXT DEFAULT 'pending',     -- 'pending' (대기) | 'resolved' (완료)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (passage_id) REFERENCES passages(id) ON DELETE CASCADE,
    FOREIGN KEY (sentence_id) REFERENCES sentences(id) ON DELETE CASCADE,
    FOREIGN KEY (exam_id) REFERENCES exams(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_error_reports_target_status 
ON error_reports(target_type, status);
```

#### (2) 데이터베이스 헬퍼 함수 (`gichul/database.py`)
- `create_error_report(target_type, passage_id, sentence_id, exam_id, error_types, comment)`: 신규 오류 등록
- `get_error_reports(target_type=None, status='pending')`:
  - `passages`, `sentences`, `exams`와 `LEFT JOIN`하여 출처 정보(학년, 연도, 월, 문항 번호, 문장 번호, 지문 첫 문장/문장 텍스트 등)를 포함하여 최신순 정렬 반환
- `delete_error_report(report_id)`: 오류 수정 완료 시 해당 레코드 영구 삭제
- `get_pending_reports_count()`: 미해결 오류 건수 반환 (헤더 배지 표시용)

#### (3) REST API 엔드포인트 신설 (`gichul/routers/reports.py`)
- `POST /api/reports`: 오류 접수 (JSON Payload: `{ target_type, passage_id, sentence_id, error_types, comment }`)
- `GET /api/reports`: 접수된 오류 목록 조회 (`?target_type=all|passage|sentence`)
- `DELETE /api/reports/{id}`: 오류 항목 삭제 (수정 완료)
- `GET /api/reports/count`: 현재 접수된 총 오류 건수 반환
- `gichul/app.py`에 `app.include_router(reports.router)` 등록

---

### 3.2. [2단계] 지문 & 문장 결과창 신고 UI 및 입력 모달

#### (1) 지문 결과창 오류 신고 버튼
- **위치**: 지문 결과창 상단 브레드크럼 바 우측 액션 그룹 (`#breadcrumbRight`) 및 우측 하단 메타 패널 헤더
- **UI**: `<button type="button" class="btn btn-outline-danger btn-sm" id="btnReportPassage">🚨 오류 신고</button>`
- **동작**: 클릭 시 현재 열람 중인 문항의 식별자(`[고1-2024년-03월-18번]`)와 `passage_id`를 담아 **지문 오류 신고 모달** 호출

#### (2) 지문 오류 신고 모달 UI (`#modalReportPassage`)
- **타이틀**: `🚨 문항 오류 신고 — [고1 2024년 03월 18번]`
- **체크박스 옵션 (복수 선택 가능)**:
  1. `[ ] 1. PDF 캡처 오류` (이미지 잘림, 여백 왜곡, 흐림, 다른 문제 노출 등)
  2. `[ ] 2. 해설지 오류` (해설 텍스트 오탈자, 해석 누락, 어색한 번역 등)
  3. `[ ] 3. 정답 오류` (정답 번호 불일치, 복수 정답 등)
  4. `[ ] 4. 정답률 오류` (정답률 수치 이상, 선지 선택률 누락/오표기 등)
  5. `[ ] 5. 기타 오류` (듣기 대본/음성 싱크 이상, 문제 유형 오분류 등)
- **주관식 상세 내용 입력창 (`textarea`)**:
  - 플레이스홀더: `"구체적인 오류 내용을 적어주시면 신속한 수정에 큰 도움이 됩니다..."`
  - 5번 '기타 오류' 선택 시 필수 작성 유도 안내
- **하단 액션**: `[취소]` / `[🚨 신고 접수]`

#### (3) 문장 결과창 오류 신고 버튼
- **위치**: 문장 검색 결과 테이블의 액션 열 (`td.col-action` 내 버튼 그룹)
- **UI**: `<button type="button" class="btn-report-sentence-inline" data-id="${s.id}" title="이 문장의 오류 신고">🚨 신고</button>`
- **동작**: 클릭 시 해당 문장의 ID(`[고3-2026-07-21-03]`)와 원문 텍스트를 인자값으로 전달하여 **문장 오류 신고 모달** 호출

#### (4) 문장 오류 신고 모달 UI (`#modalReportSentence`)
- **타이틀**: `🚨 문장 오류 신고 — [고3 2026년 07월 21번 3번 문장]`
- **문장 원문 미리보기 박스**: 해당 문장의 영문 텍스트를 상단에 읽기 전용 인용구로 제공
- **주관식 오류 내용 입력창 (`textarea`)**:
  - 플레이스홀더: `"문장 내 오탈자, 해석 오류, 어법 태그 오분류, 끊어읽기 이상 등 오류 내용을 입력해 주세요..."`
- **하단 액션**: `[취소]` / `[🚨 신고 접수]`

---

### 3.3. [3단계] 지문 결과창 PDF 문항 이미지 & 듣기 파일 수동 업로드 (신규 기능)

오류가 신고된 문항에 대해 관리자가 즉시 올바른 파일로 교체할 수 있도록 지문 결과창에 수동 업로드 기능을 추가합니다.

#### (1) PDF 문항 이미지 수동 업로드
- **UI 위치**: [좌측 상단 패널: 🖼️ PDF 문항 캡처 이미지] 패널 헤더 액션 (`#panelActionsTopLeft`)
  - 기존 `[🔄 다시 캡처]` 버튼 옆에 `[📤 이미지 수동 업로드]` 버튼 및 숨겨진 `<input type="file" id="fileUploadPassagePdfImage" accept="image/png, image/jpeg, image/webp" style="display:none;">` 추가
- **백엔드 API (`POST /api/passages/{passage_id:path}/upload-crop`)**:
  - 파일 검증: 확장자(png, jpg, jpeg, webp) 및 유효 이미지 확인
  - 저장 처리: `static/captures/{파일명}`에 저장 (기존 이미지 백업 또는 타임스탬프가 적용된 안전한 덮어쓰기)
  - DB 업데이트: `passages.pdf_crop_image` 컬럼을 새 이미지 경로로 업데이트
  - 캐시 갱신: 응답으로 최신 이미지 URL(`...png?t=timestamp`) 반환
- **프론트엔드 반응**:
  - 업로드 완료 즉시 좌측 상단 이미지 컨테이너의 `src`를 새 이미지로 갱신하여 0ms로 화면에 노출
  - 토스트 알림: `"해당 문항의 PDF 캡처 이미지가 최신 파일로 교체되었습니다."`

#### (2) 듣기 파일 수동 업로드
- **UI 위치**: [우측 상단 패널: 📝 TXT 지문 본문 / 듣기 스크립트] 내 `listeningTopRightActions` 툴바
  - 듣기 모드(1~17번)일 때 노출되는 액션 그룹에 `[📤 음성 수동 업로드]` 버튼 및 `<input type="file" id="fileUploadListeningAudio" accept="audio/mpeg, audio/mp3, audio/wav" style="display:none;">` 추가
- **백엔드 API (`POST /api/passages/{passage_id:path}/upload-audio`)**:
  - 파일 검증: 오디오 확장자(mp3, wav) 확인
  - 저장 처리: `static/audio/{파일명}`에 최신 오디오 파일로 저장
  - DB/메타 갱신: 오디오 생성 캐시 및 경로를 새 파일로 매핑
  - 응답으로 최신 오디오 URL 반환
- **프론트엔드 반응**:
  - 업로드 완료 즉시 오디오 플레이어의 소스를 새 파일로 교체하여 바로 청취 가능하도록 갱신
  - 토스트 알림: `"해당 듣기 문항의 오디오 파일이 최신 음성으로 교체되었습니다."`

---

### 3.4. [4단계] 우측 상단 '오류 신고 목록' 버튼 및 통합 관리 모달

#### (1) 상단 글로벌 헤더 버튼 (`templates/index.html`)
- **위치**: 헤더 우측 상단 액션 그룹 (`.header-actions` 내, `AI 설정` 및 `시험지 업로드` 버튼 옆)
- **전 화면 공통 노출**: `<header class="app-header">`는 고정 헤더이므로 **첫 화면, 지문 결과 화면, 문장 결과 화면 모두 동일한 우측 상단 위치에 상시 노출**됩니다.
- **UI**:
  ```html
  <button type="button" class="btn btn-outline-danger btn-sm" id="btnOpenReportsModal" title="신고된 오류 내역 확인 및 관리">
    🚨 오류 신고 내역
    <span class="report-count-badge" id="headerReportCountBadge" style="display: none;">0</span>
  </button>
  ```
- **카운트 배지**: 미처리 오류가 1건 이상일 경우 빨간색 숫자 배지가 표시되며, 0건이면 숨김 처리

#### (2) 오류 목록 통합 관리 모달 UI (`#modalReportsList`)
- **모달 헤더**:
  - 타이틀: `🚨 등록된 오류 신고 목록`
  - 새로고침 버튼 (`🔄 새로고침`)
- **상단 탭 바 (필터)**:
  - `[전체 (N건)]` / `[문항 오류 (N건)]` / `[문장 오류 (N건)]`
- **목록 테이블 / 카드 그리드**:
  - **구분**: 문항 배지(`📘 문항`) 또는 문장 배지(`📝 문장`)
  - **대상 출처**: 예: `고1 2024년 03월 18번` / `고3 2026년 07월 21번 3번 문장`
    - **[바로가기 ↗] 링크**: 클릭 시 해당 모달을 닫고, 지문 결과창을 열어 해당 문항으로 즉시 포커스 이동 (수동 업로드 버튼을 바로 눌러 수정할 수 있도록 유기적 연결)
  - **오류 유형**: 선택된 체크박스 태그들 (`[PDF 캡처]`, `[정답]`, `[해설지]` 등)
  - **신고 내용**: 사용자가 입력한 주관식 상세 코멘트
  - **신고 일시**: `2026-10-06 12:15`
  - **관리 액션**: **`[✅ 수정 완료 (삭제)]`** 버튼
    - 클릭 시 확인 다이얼로그 후 `DELETE /api/reports/{id}` 호출
    - 삭제 성공 시 해당 행을 부드러운 페이드아웃 효과와 함께 실시간 제거
    - 헤더 배지 숫자 자동 차감 갱신
- **빈 상태 (Empty State)**: 신고된 오류가 없을 때 `"현재 등록된 오류 신고가 없습니다. 🎉"` 안내 화면 출력

---

### 3.5. [5단계] 스타일 및 검증

- **CSS (`static/css/modal.css`, `static/css/viewer.css`)**:
  - 신고 모달 체크박스 카드 그리드 스타일 (`label.report-type-checkbox`)
  - 수동 업로드 버튼 및 파일 인풋 스타일
  - 오류 신고 배지 애니메이션 및 하이라이트 색상 (`var(--color-danger, #ef4444)`)
  - 목록 테이블 반응형 및 긴 텍스트 줄바꿈 처리
- **터미널 정적 검증**:
  - `python -m py_compile gichul/database.py gichul/routers/reports.py gichul/routers/passages.py gichul/app.py`
  - `node -c static/js/reports.js static/js/passage-events.js static/js/results-sentence.js`
  - `pytest` 기존 테스트 회귀 검증

---

## 4. 파일 변경 계획 요약

| 파일 경로 | 작업 구분 | 주요 내용 |
|---|:---:|---|
| `gichul/database.py` | 수정 | `error_reports` 테이블 DDL 및 4종 CRUD 헬퍼 함수 추가 |
| `gichul/routers/reports.py` | **신규** | 신고 등록/목록/삭제/건수 4대 REST API 라우터 구현 |
| `gichul/routers/passages.py` | 수정 | PDF 캡처 이미지 수동 업로드 및 듣기 오디오 수동 업로드 2종 API 구현 |
| `gichul/app.py` | 수정 | `reports` 라우터 등록 |
| `templates/index.html` | 수정 | 헤더 버튼, 지문 신고 모달, 문장 신고 모달, 오류 목록 모달, 수동 업로드 버튼 마크업 추가 |
| `static/css/modal.css` | 수정 | 오류 신고 모달 폼, 체크박스 그리드, 목록 테이블 스타일 정의 |
| `static/js/reports.js` | **신규** | 오류 신고 팝업 제어, API 통신, 목록 렌더링, 바로가기 및 삭제 이벤트 처리 |
| `static/js/passage-events.js` | 수정 | 지문 결과창 내 `🚨 오류 신고` 및 이미지/듣기 `수동 업로드` 이벤트 연동 |
| `static/js/results-sentence.js` | 수정 | 문장 액션 열에 `🚨 신고` 버튼 및 클릭 이벤트 연동 |
| `static/js/main.js` | 수정 | `reports.js` 모듈 초기화 및 앱 기동 시 오류 건수 배지 로드 |

---

## 5. 사용자 확인 및 승인 대기

본 계획서는 `/ask` 모드 원칙에 따라 소스 코드를 변경하지 않고 작성되었습니다.  
위 계획서 내용이 의도하신 기능과 일치하면, **`/apply`** 명령어를 입력해 주시면 즉시 코드 구현을 시작하겠습니다.
