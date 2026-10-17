# 문항 오류 신고 내역 내 'TXT 지문 본문 텍스트' 오류 항목 추가 구현 계획서

## 1. 개요 및 목적
문항(지문) 오류 신고 시, 사용자가 PDF 이미지 오류뿐만 아니라 본문 텍스트의 오탈자·단락 누락·기호 깨짐 등을 명확하게 선택하여 신고할 수 있도록 기존 **1번 PDF 캡처 오류**와 **2번 해설지 오류** 사이에 **'2. TXT 지문 본문 텍스트'** 오류 유형을 신규 추가하고 관련 번호 체계와 인라인 에디터/AI 진단을 정합성 있게 연계합니다.

---

## 2. 진행 현황 표

| 작업 단계 | 내용 | 대상 파일 | 상태 |
|---|---|---|---|
| **1단계** | 지문 오류 신고 모달 UI 체크박스 추가 및 번호 체계 재정렬 | `templates/index.html` | ✅ 완료 |
| **2단계** | 오류 유형 라벨 매핑(`ERROR_TYPE_LABELS`) 및 인라인 에디터 필드 연동 | `static/js/reports.js` | ✅ 완료 |
| **3단계** | 백엔드 AI 진단 및 휴리스틱 폴백 필드 연계 보강 | `gichul/routers/reports.py` | ✅ 완료 |
| **4단계** | 터미널 구문 검증 및 동작 검증 | `reports.js`, `reports.py` | ✅ 완료 |

---

## 3. 현행 시스템 분석 및 변경 포인트

### 3.1 현행 오류 신고 모달 (`templates/index.html`)
현재 `#modalReportPassage`에는 5개의 오류 유형 체크박스가 정의되어 있습니다:
- 1. PDF 캡처 오류 (`pdf_capture`)
- 2. 해설지 오류 (`explanation`)
- 3. 정답 오류 (`answer`)
- 4. 정답률 오류 (`accuracy`)
- 5. 기타 오류 (`other`)

### 3.2 변경 후 오류 신고 모달 순서 및 구성
1번과 기존 2번 사이에 `passage_text`를 삽입하고 전체 번호를 1~6번으로 재정렬합니다:
1. **1. PDF 캡처 오류** (`value="pdf_capture"`)
   - 힌트: 이미지 잘림, 흑백 왜곡, 흐림, 다른 문항 노출 등
2. **2. TXT 지문 본문 텍스트** (`value="passage_text"`) 🌟 *(신규 추가)*
   - 힌트: 본문 텍스트 오탈자, 단락/단어 누락, 특수기호 깨짐, 밑줄 번호 누락 등
3. **3. 해설지 오류** (`value="explanation"`) *(기존 2번)*
   - 힌트: 해설 내용 오탈자, 해석 누락, 어색한 번역 등
4. **4. 정답 오류** (`value="answer"`) *(기존 3번)*
   - 힌트: 정답 번호 불일치, 복수 정답 등
5. **5. 정답률 오류** (`value="accuracy"`) *(기존 4번)*
   - 힌트: 정답률 수치 이상, 선지 선택률 누락/오표기 등
6. **6. 기타 오류** (`value="other"`) *(기존 5번)*
   - 힌트: 듣기 대본/음성 싱크 이상, 문제 유형 오분류 등

---

## 4. 상세 구현 명세

### 4.1 1단계: HTML 모달 체크박스 UI 추가 (`templates/index.html`)
- 파일: `templates/index.html` (약 2758~2795행)
- `report-types-grid` 내부에 `passage_text` 카드 신규 삽입:
  ```html
  <label class="report-type-card">
    <input type="checkbox" name="passageErrorType" value="passage_text">
    <div class="report-type-info">
      <span class="report-type-name">2. TXT 지문 본문 텍스트</span>
      <span class="report-type-hint">본문 텍스트 오탈자, 단락 누락, 특수문자 깨짐 등</span>
    </div>
  </label>
  ```
- 이후 기존 항목들의 타이틀 번호를 3~6번으로 순차 변경.

### 4.2 2단계: 프론트엔드 라벨 매핑 및 퀵 에디터 매핑 (`static/js/reports.js`)
- **라벨 매핑 확장:**
  ```javascript
  const ERROR_TYPE_LABELS = {
    pdf_capture: "PDF 캡처 오류",
    passage_text: "TXT 지문 본문 텍스트",
    explanation: "해설지 오류",
    answer: "정답 오류",
    accuracy: "정답률 오류",
    other: "기타 오류",
  };
  ```
- **신고 카드 인라인 에디터 기본 필드 결정 로직 개선:**
  - `isPassageText = (r.error_types || []).includes("passage_text") || (r.comment || "").includes("본문") || (r.comment || "").includes("지문");`
  - 만약 `passage_text` 오류로 신고된 경우:
    - `fieldKey = "passage_text"`
    - `fieldLabel = "📝 지문 본문 수정"`
    - `defaultText = r.passage_text || ""`
  - 이미 백엔드 `PATCH /api/passages/{passage_id}/text` 및 인라인 저장 로직(`handleInlineSave`)에 `fieldKey === "passage_text"` 처리가 구현되어 있으므로 매핑 즉시 동작.

### 4.3 3단계: 백엔드 AI 진단 및 휴리스틱 폴백 필드 연계 (`gichul/routers/reports.py`)
- `_diagnose_single_report(report)` 내에서:
  - `error_types`에 `"passage_text"`가 포함되어 있거나 코멘트에 "지문", "본문"이 있는 경우:
    - 진단 기본 필드를 `field_name = "passage_text"`, `before_text = cur_text`로 설정.
    - AI 진단 프롬프트에 `신고 오류 유형: TXT 지문 본문 텍스트`와 `현재 문항 본문 텍스트`를 함께 주입하여 본문 교정안(`correct_passage`)을 응답하도록 확장.
  - 일괄 저장 API(`batch-apply`)는 이미 `item.passage_text`가 넘어오면 `db.update_passage_text`를 정상 호출하고 있으므로 완벽 호환.

### 4.4 4단계: 정적 검증 및 무결성 확인
- Python 구문 검사:
  ```powershell
  python -m py_compile gichul/routers/reports.py
  ```
- JavaScript 구문 검사:
  ```powershell
  node -c static/js/reports.js
  ```

---

## 5. 실행 및 적용 가이드
- 본 문서는 `/ask` 모드로 작성되어 소스 코드를 변경하지 않았습니다.
- 작업 적용을 시작하려면 `/apply` 또는 `/action apply`를 입력해 주세요.
