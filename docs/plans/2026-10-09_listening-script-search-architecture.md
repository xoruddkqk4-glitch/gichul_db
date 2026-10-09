# 듣기 영역 대본(Script) 기준 검색 아키텍처 개편 계획서

## 1. 개요 및 배경

- **작성일자**: 2026-10-09
- **관련 사용자 질의**: "듣기 영역의 검색은 script가 기준이 되어야 할 것 같아. 지금은 문제 기준 아니야?"
- **목적**: 듣기 영역(1~17번) 기출 데이터 검색 시, 한국어 문제 발문(`question_title`) 중심이 아닌 **실제 영어 듣기 대본(`script_text`)을 핵심 기준으로 검색**되도록 데이터 모델, FTS5 인덱스, 검색 API 및 문장 단위 검색 체계를 전면 개편합니다.

---

## 2. 현재 시스템 진단 및 실태 분석 (Fact Check)

사용자께서 지적하신 바와 같이, 현재 시스템은 **문제 발문 기준과 대본 기준이 혼재되어 있거나, 문장 단위 검색에서는 듣기 영역이 아예 배제되어 있는 상태**입니다.

### ① 지문 검색 (`search_passages`, FTS5 전문 검색)
- **현재 검색 쿼리**:
  - `passages_fts` 및 LIKE 조건에 `p.passage_text`, `p.question_title`(한국어 문제 발문), `p.explanation_text`, `p.script_text`(영문 대본)가 **모두 단순 OR 조건**으로 결합되어 있습니다.
  - 이로 인해 "그림", "언급", "일치", "어색한" 등 한국어 문제 유형/발문 키워드를 입력했을 때 듣기 문항이 대량 검색되며, 영문 대본 내의 핵심 구문이나 어휘 중심 검색 결과와 뒤섞이는 현상이 발생합니다.
- **대본 미추출 문항 현황**:
  - DB 내 전체 5,582개 듣기 문항 중 **321개 문항은 `script_text`가 빈값(`''`)**이고, `passage_text`에 문제 발문(예: `"16. 남자가 하는 말의 주제로 가장 적절한 것은?"`)이나 문제 번호(`"1."`)만 들어가 있습니다.
  - 이 321건은 사실상 **오직 한국어 문제 발문으로만 검색**되고 있습니다.

### ② 클라이언트 "결과 내 재검색" 필터링 누락 (`static/js/search.js` L460)
- 검색 결과 목록에서 상단 "결과 내 재검색"을 실행할 때, 다음 필드만 검사합니다:
  ```javascript
  const inBody = checkTextMatch(p.passage_text, kwRaw, isWholeWordActive);
  const inTitle = checkTextMatch(p.question_title, kwRaw, isWholeWordActive);
  const inId = (p.display_id || p.id || "").toLowerCase().includes(kw);
  const inExp = checkTextMatch(p.explanation_text, kwRaw, isWholeWordActive);
  const inType = (p.question_type || "").toLowerCase().includes(kw);
  const inTags = (p.tags || []).some(t => t.toLowerCase().includes(kw));
  ```
  - **`p.script_text`가 조건에서 완전히 누락**되어 있어, 복합 지문이 아닌 단일 듣기 문항에서 `passage_text`와 `script_text`가 분리되어 있을 경우 대본 텍스트 매칭이 실패합니다.

### ③ 문장 단위 검색 (`search_sentences`, 상단 [문장] 탭)
- **충격적인 실태**:
  - `Reading sentences count`: **71,866건**
  - `Listening sentences count`: **0건**
- 현재 `sentences` 테이블 및 문장 토큰화 파이프라인은 독해 문항(18~45번)만 대상으로 동작하고 있습니다.
- 따라서 사용자가 상단에서 **[🎧 듣기]** 영역을 선택하고 **[문장]** 탭으로 검색하면 **검색 결과가 0건**으로 나타납니다.

---

## 3. 개선 방향 및 목표 아키텍처

```
[사용자 검색 입력] ──> 영역: 'listening' (듣기)
                           │
       ┌───────────────────┴───────────────────┐
       ▼                                       ▼
 [지문 검색 모드]                        [문장 검색 모드]
 • 제1 검색 기준: script_text(대본)       • sentences 테이블에 듣기 대본 문장 적재
 • 발문(question_title) 매칭 분리/제외   • 화자 태그(M:, W:) 제외 순수 영문 문장
 • 대본 텍스트 하이라이트 일원화         • 문장 단위 구문 분석 및 유인물 담기 지원
```

### 핵심 개편 원칙
1. **듣기 영역 지문 검색의 본질 확립**:
   - `area == 'listening'`인 경우, 검색 대상의 중심을 `script_text`로 한정하거나 우선 가중치를 부여합니다.
   - 한국어 발문 검색이 필요한 경우(예: "언급되지 않은 것")는 `question_type` 필터나 명시적 옵션으로 지원하고, 일반 검색어 입력 시에는 대본 내용과의 일치를 최우선으로 합니다.
2. **듣기 대본의 문장 토큰화(`sentences`) 파이프라인 구축**:
   - 듣기 대본(`script_text`)을 문장 단위로 분할하여 `sentences` 테이블에 적재합니다.
   - 화자 식별자(`M:`, `W:`)를 제거한 순수 영문 문장으로 저장하여 어법 분석기 및 문장 유인물 제작소와의 호환성을 확보합니다.
3. **클라이언트 결과 내 검색 버그 즉시 수정**:
   - `search.js` 내 필터링 조건에 `p.script_text`를 명시적으로 추가합니다.

---

## 4. 단계별 상세 구현 로드맵

### 1단계: 클라이언트 결과 내 검색 및 지문 검색 쿼리 정비
- [x] `static/js/search.js` L460: 결과 내 검색 시 `p.script_text` 매칭 조건 추가
- [x] `gichul/database.py` `search_passages`:
  - `area == 'listening'`인 경우, `script_text` 대상 매칭을 우선하도록 FTS/LIKE 조건 정교화
  - 대본이 있는 문항은 `script_text`를 우선 검색하고, 발문 검색과 명확히 구분
- [x] `static/js/passage-render.js`: 검색어 하이라이트 시 `script_text` 영역에 정확히 하이라이트 적용

### 2단계: 듣기 대본 문장 토큰화 (`sentences`) 파이프라인 구현
- [x] `gichul/sentence_tokenizer.py` & `gichul/listening_parser.py`:
  - 대본 텍스트(`script_text`)를 화자 분기별/문장부호(`. `, `? `, `! `)별로 분할하는 `split_script_sentences`, `create_script_sentence_records` 구현
  - `sync_exam_listening` 완료 시 `db.replace_passage_sentences()`를 호출하여 `sentences` 테이블에 자동 동기화
- [x] `gichul/database.py`:
  - 듣기 문항 문장의 `order_index`, `remarks`("듣기 대본 문장") 규격 확립

### 3단계: 기존 DB 듣기 문항 대본 문장 일괄 마이그레이션 스크립트
- [x] 기존 5,261개 대본 보유 듣기 문항의 문장들을 일괄 토큰화하여 `sentences` 테이블에 주입하는 마이그레이션 도메인 함수 구현 (`tools/migrate_listening_sentences.py`)
- [x] 80,686건의 듣기 문장 `sentences` 및 FTS5 `sentences_fts` 가상 테이블 동기화 완료

### 4단계: 검증 및 회귀 테스트
- [x] 듣기 영역 선택 후 키워드 검색 시 대본 기준 검색 검증
- [x] 듣기 영역 선택 후 [문장] 탭에서 대본 문장 검색 및 유인물 담기 동작 검증
- [x] 전체 pytest 단위/통합 테스트 (226개) 100% 통과

---

## 5. 진행 현황 (Progress Status)

| 단계 | 작업 항목 | 상태 | 비고 |
|---|---|---|---|
| 1단계 | 클라이언트 결과 내 검색 `script_text` 누락 수정 및 지문 쿼리 정비 | ✅ 완료 | `search.js`, `database.py` 적용 완료 |
| 2단계 | 듣기 대본 문장 토큰화 및 `sentences` 테이블 적재 로직 구현 | ✅ 완료 | `sentence_tokenizer.py`, `listening_parser.py` 적용 완료 |
| 3단계 | 기존 DB 듣기 대본 문장 일괄 마이그레이션 | ✅ 완료 | 5,257개 지문, 80,686개 문장 적재 완료 |
| 4단계 | 단위/통합 테스트 및 전체 검증 | ✅ 완료 | 226개 pytest 100% 통과 |
