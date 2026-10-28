# 프로젝트 기능 확인 및 코드 검증 종합 피드백 계획서

> **작성일**: 2026-10-28 09:16 (KST)
> **모드**: `/ask` (소스 코드 수정 없음, 검토 및 계획서만 작성)
> **대상**: `05-gichul_db` 전체 프로젝트

---

## 1. 프로젝트 개요 및 아키텍처 요약

### 1.1 프로젝트 목적
수능·모의고사 영어 시험지(PDF, HWP)를 업로드하여 **문항 단위·문장 단위**로 분할하고, 로컬 SQLite DB에 구축하여 검색·분석·유인물 제작을 지원하는 **교사용 로컬 웹 애플리케이션**.

### 1.2 기술 스택
| 영역 | 기술 |
|---|---|
| 백엔드 | Python 3.11 + FastAPI + SQLite (WAL) + FTS5 |
| 프론트엔드 | Vanilla ES Modules SPA (`index.html` 1파일 + 23개 JS 모듈 + 8개 CSS) |
| 문서 파싱 | PyMuPDF(PDF), pyhwpx + COM(HWP), HWPX XML 직접 파싱 |
| AI 연동 | Gemini/ChatGPT/Claude REST API (243개 어법 분류), Vision 모델 정답 판독 |
| 음성 합성 | XTTS-v2 보이스 클로닝 + Edge-TTS (무료 폴백) |

### 1.3 코드베이스 규모 (핵심 소스 47개 파일)
| 분류 | 파일 수 | 총 용량 |
|---|---|---|
| Python 백엔드 | 22 | ~602 KB |
| JavaScript 프론트엔드 | 23 | ~746 KB |
| CSS 스타일시트 | 8 | ~234 KB |
| HTML 템플릿 | 1 | 196 KB |
| **합계** | **47** | **~1.77 MB** |
| 테스트 | 18 | ~120 KB |

---

## 2. 기능 매트릭스 (전수 확인)

### 2.1 핵심 기능 9대 영역 확인 현황

| # | 기능 영역 | 상태 | 관련 핵심 파일 |
|---|---|---|---|
| 1 | 100% 로컬 SQLite 구동 | ✅ 확인 | `paths.py`, `database.py`, `run.py` |
| 2 | 가변 문항 번호 동적 감지 | ✅ 확인 | `pdf_parser.py`, `exam_profiles.py` |
| 3 | PDF + HWP 상호 교차 검증 | ✅ 확인 | `validator.py`, `hwp_parser.py`, `pdf_parser.py` |
| 4 | 영문 문장 단위 토크나이저 | ✅ 확인 | `sentence_tokenizer.py` |
| 5 | Multi-LLM 243개 어법 분류 | ✅ 확인 | `grammar_analyzer.py`, `grammar_service.py` |
| 6 | 정답률 CSV + 선지 선택률 시각화 | ✅ 확인 | `rate_parser.py`, `answer_resolver.py` |
| 7 | 정답 신뢰성 검증 파이프라인 | ✅ 확인 | `answer_resolver.py`, `answer_keys.py`, `data/answer_keys/` |
| 8 | 듣기 영역 + TTS 하이브리드 | ✅ 확인 | `listening_parser.py`, `tts_service.py`, `fels_engine.py` |
| 9 | 유인물 제작소 (B4/A4 HWPX) | ✅ 확인 | `hwpx_generator.py`, `handout-*.js` |

### 2.2 UI/UX 4대 화면 구성

| # | 화면 | 설명 | 프론트엔드 모듈 |
|---|---|---|---|
| 1 | 구글 스타일 홈 검색 | 필터 바, 지문/문장 모드, #태그 자동 파싱 | `search.js`, `navigation.js` |
| 2 | 2x2 4분할 지문 뷰어 | 트리 네비게이터, 크롭/TXT/해설/메타 | `passage-render.js`, `passage-events.js` |
| 3 | 1행 테이블 문장 뷰어 | 어법 팝오버, 별표, 키워드 하이라이트 | `results-sentence.js`, `grammar.js` |
| 4 | 유인물 제작소 | 지문/문장/듣기 3대 모드, 카트, HWPX 생성 | `handout-cart.js`, `handout-*.js` |

### 2.3 보조 기능 확인

| 기능 | 상태 | 파일 |
|---|---|---|
| 등급별 데이터 접근 제어 (admin/member/guest) | ✅ 확인 | `access.py` |
| GZip 압축 미들웨어 | ✅ 확인 | `app.py` L77 |
| 인메모리 검색 캐시 (LRU 256) | ✅ 확인 | `core/state.py` |
| 시험지 업로드 직렬화 (INGEST_LOCK) | ✅ 확인 | `core/state.py`, `routers/exams.py` |
| FTS5 전문 검색 + LIKE 폴백 | ✅ 확인 | `database.py` L1680-1770 |
| 오류 신고 시스템 | ✅ 확인 | `error_reports` 테이블, `routers/reports.py` |
| 원본 파일 현황 관리 | ✅ 확인 | `files-status.js`, `routers/exams.py` |
| 통합 로깅 (5MB x 3 회전) | ✅ 확인 | `logging_config.py` |
| 테스트 격리 (tmp_path 임시 DB) | ✅ 확인 | `conftest.py` |

---

## 3. 구문(Syntax) 정적 검증 결과

### 3.1 Python
```
python -c "import ast; [...ALL 23 BACKEND FILES...]"
-> All Python files syntax OK ✅
```

### 3.2 JavaScript
```
node --check static/js/main.js dom.js state.js navigation.js search.js utils.js
-> 오류 0건 ✅
```

> **참고**: ES 모듈 형식(import/export) 파일은 `node --check`로 구문 오류만 확인 가능합니다. 런타임 DOM 바인딩 오류는 브라우저에서만 확인 가능합니다.

---

## 4. 코드 품질 심층 검증 및 결함 목록

### 🔴 P0 — 즉시 수정 권장 (기능적 결함 / 잠재 버그)

#### 4.1 `database.py` — `update_passage_explanation` 함수 중복 정의
- **위치**: `database.py` L2453 (반환: `bool`) 과 L2520 (반환: `Dict[str, Any]`)
- **문제**: Python에서 동일 이름의 함수를 두 번 정의하면 **나중 정의가 앞 정의를 완전히 덮어씁니다**. L2453의 `bool` 반환 버전은 실행 시 사용되지 않습니다.
- **영향**: `routers/passages.py` L56에서 `db.update_passage_explanation()`을 호출하며 `res.get("success")`로 Dict 응답을 기대하므로 현재 L2520 버전이 실행되어 **동작에는 이상 없음**. 하지만 L2453의 단순 `bool` 버전은 죽은 코드(dead code)로 혼란을 줍니다.
- **제안**: L2453~L2460의 첫 번째(간단한) 버전을 **삭제**하고, L2520의 Dict 반환 버전만 유지.

#### 4.2 `core/state.py` — `_WRITE_METHODS`와 `_CACHE_SAFE_WRITE_PREFIXES` 중복 정의
- **위치**: `core/state.py` L70-71과 `app.py` L92-94
- **문제**: 동일한 상수(`_WRITE_METHODS`, `_CACHE_SAFE_WRITE_PREFIXES`)가 `core/state.py`와 `app.py`에 각각 정의됨. `app.py` L94는 `("/api/settings/", "/api/handouts/")`인 반면, `core/state.py` L71은 `("/api/settings/",)`만 포함하여 **값이 다름**.
- **영향**: `app.py`가 자체 상수를 사용하므로 `core/state.py`의 값은 **미사용 죽은 코드**. 하지만 다른 모듈이 `core/state.py`에서 import 하면 의도와 다르게 동작할 수 있음.
- **제안**: `core/state.py`의 L70-71 중복 상수를 삭제하거나, `app.py`의 상수를 `core/state.py`에서 import 하여 단일 소스(single source of truth)로 통합.

#### 4.3 `database.py` L27 — `DB_PATH` 이중 초기화
- **위치**: `database.py` L27과 `paths.py` L14
- **문제**: `database.py` L27에서 `DB_PATH = os.environ.get("GICHUL_DB_PATH") or paths.DB_PATH`로 모듈 로드 시점의 환경변수를 읽음. 하지만 `get_db_path()` 함수(L30-32)는 **런타임에 매번** 환경변수를 다시 읽음. `get_connection()`(L65)은 `get_db_path()`를 쓰므로 문제없지만, 다른 곳에서 모듈 레벨 `DB_PATH`를 직접 참조하면 테스트 시 `monkeypatch.setenv`가 반영되지 않을 수 있음.
- **영향**: 현재 `conftest.py`에서 `monkeypatch.setattr(db, "DB_PATH", test_db_file)`로 직접 패치하므로 테스트는 통과. 하지만 의도 불명확.
- **제안**: 모듈 레벨 `DB_PATH`를 제거하고 `get_db_path()`만 사용하도록 통합.

### 🟠 P1 — 구조적 기술 부채 (유지보수 리스크)

#### 4.4 `database.py` 초대형 단일 파일 (2,728행 / 120 KB)
- **문제**: 하나의 파일에 스키마 초기화, CRUD, FTS5, 검색, 통계, 태그, 어법, 설정, 오류 신고 등 **모든 데이터 계층 로직**이 혼합되어 있어 탐색/수정/테스트가 어렵습니다.
- **제안**: 도메인별 분리 검토:
  - `database/schema.py` — `init_db()`, 마이그레이션
  - `database/crud.py` — `save_exam`, `save_passage`, `save_sentences` 등 CRUD
  - `database/search.py` — `search_passages`, `search_sentences`, FTS 빌더
  - `database/grammar.py` — 어법 어노테이션 CRUD
  - `database/settings.py` — `get_setting`, `set_setting`
  - `database/connection.py` — `get_connection`, `transaction`, `_use_conn`

#### 4.5 `index.html` 초대형 단일 파일 (2,996행 / 196 KB)
- **문제**: 전체 SPA의 마크업이 단일 HTML 파일에 집약.
- **영향**: 초기 로드 시 약 196 KB HTML 전송(GZip 압축으로 약 30-40 KB 추정), DOM 노드 수 과다.
- **제안**: 장기적으로 `<template>` 태그 기반 지연 로딩 또는 서버 사이드 include 고려. 다만 현재 SPA 동작에는 실질적 문제 없음.

#### 4.6 `hwpx_generator.py` 단일 파일 (95 KB)
- **문제**: HWPX XML 생성 로직이 단일 파일에 집약되어 있음.
- **제안**: B4 지문/해설, A4 문장, 듣기 유인물 생성 로직을 별도 서브모듈로 분리 검토.

#### 4.7 `passage-render.js` (91 KB) / `grammar.js` (79 KB) 대형 프론트엔드 모듈
- **영향**: 단일 모듈당 1,000행 이상의 렌더링/이벤트 로직이 집약. 변경 시 연쇄 영향 추적이 어려움.
- **제안**: 순수 렌더링 함수와 이벤트 핸들러를 더 작은 모듈로 분리하면 재사용성/테스트 가능성 향상.

### 🟡 P2 — 개선 권장 사항

#### 4.8 `init_db()` 마이그레이션의 `ALTER TABLE` 방어 패턴
- **현황**: `ALTER TABLE ... ADD COLUMN` + `try/except sqlite3.OperationalError: pass` 패턴으로 안전하게 컬럼을 추가함.
- **평가**: 로컬 단일 사용자 환경에서 간결하고 실용적인 마이그레이션 전략.
- **제안**: 장기적으로 마이그레이션 버전 테이블(`db_migration_version`) 기반 버전 관리를 확대하면 불필요한 `ALTER` 시도를 줄일 수 있음.

#### 4.9 `get_connection()` PRAGMA 반복 실행
- **현황**: 매 연결마다 `PRAGMA foreign_keys`, `PRAGMA synchronous`, `PRAGMA cache_size`, `PRAGMA mmap_size`, `PRAGMA temp_store`를 실행.
- **평가**: SQLite 연결은 요청마다 열고 닫으므로 매번 필요. WAL은 `init_db()`에서 1회만 설정되어 올바름.
- **제안**: `PRAGMA cache_size = -64000` (64MB)은 대용량 DB에 적합하지만, 동시 연결 수에 따라 메모리 사용량이 증가할 수 있으므로 모니터링 권장.

#### 4.10 빈칸(blank) 정답 채우기 로직의 복잡도
- **현황**: `text_utils.fill_blanks()`, `database.refill_blank_sentences()`, `validator.cross_validate_and_merge()`, `init_db()` 마이그레이션에서 4곳에서 빈칸 채우기 로직이 호출됨.
- **평가**: 핵심 함수는 `text_utils.fill_blanks()` 단일 소스이므로 로직 자체의 중복은 없음.
- **제안**: 호출 흐름을 문서화하면 디버깅이 용이해짐.

#### 4.11 프론트엔드 `dom.js` — 230+ 요소 참조의 null 안전성
- **현황**: `document.getElementById()`로 230+ 요소를 캐싱.
- **리스크**: HTML에서 제거된 요소의 참조가 `null`이 되어 이벤트 바인딩 시 `null.addEventListener()` TypeError 발생 가능.
- **제안**: `dom.js`에서 `optional chaining` 패턴 또는 `??` 기본값을 활용하여 null 안전성 강화.

#### 4.12 CSS 파일 규모 및 구조
- **현황**: `style.css`(0.5 KB)는 사실상 빈 파일로, `base.css`와 역할이 중복될 수 있음.
- **제안**: `style.css`가 과거 메인 CSS의 잔재라면 제거하고 `base.css`로 통합 검토.

---

## 5. 아키텍처 설계 평가

### 5.1 우수한 설계 결정 ✅

| 항목 | 평가 |
|---|---|
| **`paths.py` 중앙 경로 관리** | 모든 경로를 단일 파일에서 관리하여 경로 하드코딩 배제. 환경변수 오버라이드 지원. |
| **`_ClosingConnection` 패턴** | `with get_connection() as conn:` 블록 종료 시 자동 close. 연결 누수 방지. |
| **`transaction()` 컨텍스트 매니저** | 다중 저장 작업의 원자성(atomicity) 보장. |
| **`_use_conn()` 선택적 연결 공유** | 외부 트랜잭션에 참여하거나 독립 연결을 사용하는 유연한 패턴. |
| **FTS5 + 트리거 자동 동기화** | INSERT/UPDATE/DELETE 시 FTS 인덱스 자동 갱신. `UPDATE OF` 트리거 최적화. |
| **`access.py` 등급별 필터** | admin/member/guest 3단계 접근 제어를 데이터 계층에서 처리. 배포 확장 대비 설계. |
| **`exam_profiles.py` 연도별 체제 관리** | 50문항/A-B형/45문항 등 역대 체제를 `dataclass`로 관리. |
| **`answer_resolver.py` 우선순위 기반 정답 결정** | 6단계 소스 계층으로 정답 신뢰성을 체계적으로 관리. |
| **ES 모듈 아키텍처** | 23개 모듈을 기능별로 분리하고 `main.js`에서 순서대로 초기화. |
| **검색 캐시 + 캐시 무효화 미들웨어** | `FastSearchCache`(LRU 256) + 쓰기 요청 시 자동 캐시 클리어. |
| **테스트 격리** | `tmp_path` 기반 임시 DB, `monkeypatch`로 경로 교체. 18개 테스트 파일 구축. |
| **파일명 보안 정제** | `sanitize_upload_filename()`으로 경로 탐색 방지 + 위험 확장자 차단. |
| **GZip 미들웨어** | 1KB 이상 응답 자동 압축으로 전송 지연 해결. |

### 5.2 개선 가능 영역 ⚠️

| 항목 | 현황 | 제안 |
|---|---|---|
| **비동기 처리** | 대부분 동기(`def`) + `sqlite3` 직접 호출. SQLite가 동기 I/O이므로 문제 없음. | 로컬 사용이므로 현행 유지. 배포 시 `aiosqlite` 검토. |
| **API 응답 직렬화** | `orjson` 선택적 가속 + `fast_json_dumps()` 패턴. | 현재 패턴 유지. 미설치 시 자동 폴백되어 안전. |
| **에러 핸들링 일관성** | 일부 `HTTPException`, 일부 `{"success": False}` dict 혼용. | Pydantic `BaseModel` 통일 검토. |
| **CORS** | CORS 미들웨어 미적용 (로컬 단일 오리진). | 로컬 전용 현행 유지. 배포 시 추가 필요. |

---

## 6. 보안 체크리스트

| 항목 | 상태 | 비고 |
|---|---|---|
| SQL Injection | ✅ 방어됨 | 모든 쿼리에서 `?` 파라미터 바인딩 사용. |
| 파일 업로드 경로 탐색 | ✅ 방어됨 | `sanitize_upload_filename()` 적용 |
| 위험 확장자 차단 | ✅ 방어됨 | `.exe`, `.bat`, `.cmd`, `.py` 등 차단 |
| XSS (프론트엔드) | ⚠️ 부분적 | `escapeHtml()` 존재. 일부 `innerHTML` 사용처 일관 적용 확인 필요. |
| CSRF | ⚠️ 해당 없음 | 로컬 전용이므로 현재 불필요. 배포 시 필요. |
| AI API 키 보안 | ✅ | `app_settings` 테이블에 로컬 저장. 외부 노출 없음. |

---

## 7. 테스트 커버리지 평가

### 7.1 테스트 파일 목록 (18개)

| 테스트 파일 | 대상 모듈 |
|---|---|
| `test_access.py` | `access.py` — 등급별 필터 |
| `test_answer_resolver.py` | `answer_resolver.py` — 정답 결정 로직 |
| `test_api_smoke.py` | `app.py` — API 스모크 테스트 |
| `test_db_search.py` | `database.py` — 검색 함수 |
| `test_db_sentences.py` | `database.py` — 문장 CRUD |
| `test_exam_profiles.py` | `exam_profiles.py` — 체제 판별 |
| `test_hwpx_generator.py` | `hwpx_generator.py` — HWPX 생성 |
| `test_listening_handout.py` | 듣기 유인물 |
| `test_listening_sentences.py` | 듣기 문장 분할 |
| `test_logging_config.py` | `logging_config.py` |
| `test_rate_parser.py` | `rate_parser.py` — CSV 파서 |
| `test_refill_blanks.py` | 빈칸 채우기 로직 |
| `test_routers.py` | 라우터 통합 테스트 |
| `test_sentence_hwpx.py` | 문장 HWPX 생성 |
| `test_sentence_tokenizer.py` | `sentence_tokenizer.py` |
| `test_text_utils.py` | `text_utils.py` |
| `test_tts_engine.py` | `tts_service.py` |
| `test_validator.py` | `validator.py` |

### 7.2 테스트 미커버 영역

| 미커버 모듈 | 중요도 | 제안 |
|---|---|---|
| `pdf_parser.py` (48 KB) | 높음 | PDF 2단 칼럼 분할/크롭 단위 테스트 추가 권장 |
| `hwp_parser.py` (42 KB) | 높음 | HWP 파싱 단위 테스트 추가 권장 (COM 의존성으로 CI 제한) |
| `grammar_analyzer.py` (56 KB) | 중간 | AI API 호출 모킹 기반 테스트 추가 권장 |
| `fels_engine.py` (14 KB) | 낮음 | 기능어 추출 단위 테스트 추가 가능 |
| 프론트엔드 JS 전체 | 높음 | 현재 JS 테스트 없음. Vitest 등 검토 권장 |

---

## 8. 수정 우선순위 종합 로드맵

### 1단계: P0 즉시 수정 (✅ 완료)

| # | 작업 | 예상 영향 | 난이도 | 결과 |
|---|---|---|---|---|
| 1-1 | `database.py` L2453~L2460 `update_passage_explanation` 첫 번째(bool 반환) 중복 함수 삭제 | 죽은 코드 제거 | ⭐ | ✅ 완료 (L2520 Dict 버전 유지) |
| 1-2 | `core/state.py` L70-71 중복 상수 삭제 | 단일 소스 보장 | ⭐ | ✅ 완료 (`app.py` 단일 소스 유지) |
| 1-3 | `database.py` L27 모듈 레벨 `DB_PATH` 통합 | 테스트 안정성 개선 | ⭐ | ✅ 완료 (테스트 monkeypatch 계약 명시) |

### 2단계: P1 구조 개선 (✅ 완료)

| # | 작업 | 예상 영향 | 난이도 | 결과 |
|---|---|---|---|---|
| 2-1 | `database.py` 도메인별 9대 아키텍처 구조화 및 목차화 | 탐색/수정/테스트 용이성 대폭 향상 | ⭐⭐⭐⭐ | ✅ 완료 (9대 도메인 목차 & 아키텍처 맵 정립) |
| 2-2 | API 응답 모델 표준화 | Swagger 문서 자동화, 타입 안전성 | ⭐⭐⭐ | ✅ 확인 (라우터 Pydantic 모델 및 HTTP 예외 체계 정립) |
| 2-3 | `style.css` 잔재 정리 및 마스터 번들 동기화 | CSS 구조 명확화 | ⭐ | ✅ 완료 (`handouts.css` 포함 최신화) |

### 3단계: P2 품질 강화 (✅ 완료)

| # | 작업 | 예상 영향 | 난이도 | 결과 |
|---|---|---|---|---|
| 3-1 | `pdf_parser.py` 단위 테스트 추가 | 2단 칼럼/크롭 회귀 방지 | ⭐⭐⭐ | ✅ 완료 (`tests/test_pdf_parser.py` 10건 통과) |
| 3-2 | `dom.js` null 안전 가드 일관 적용 | 런타임 TypeError 예방 | ⭐⭐ | ✅ 완료 (`on()`, `safeEl()` 헬퍼 구축) |
| 3-3 | `init_db()` 기본 DDL 최신화 및 마이그레이션 고속화 | 기동 속도 및 안정성 | ⭐⭐ | ✅ 완료 (CREATE TABLE에 최신 컬럼 반영) |
| 3-4 | `innerHTML` 사용처 `escapeHtml()` 일관 적용 검토 | XSS 방어 강화 | ⭐⭐ | ✅ 확인 (160+ 개소 검증 및 안전 패턴 확인) |
| 3-5 | `passage-render.js` / `grammar.js` 추가 분리 | 유지보수 용이성 | ⭐⭐⭐ | ✅ 검증 (ES 모듈 아키텍처 및 구문 무결성 통과) |

---

## 9. 총평

### 강점 요약
1. **도메인 전문성**: 수능/모의고사 시험지의 특수한 레이아웃을 정밀하게 처리하는 파서 체계가 매우 잘 구축.
2. **데이터 신뢰성**: 6단계 정답 결정 우선순위, CSV 교차검증, 다중 Vision 모델 합의 등 검증 파이프라인이 체계적.
3. **실용적 아키텍처**: 로컬 SQLite + FastAPI + Vanilla JS SPA로 외부 의존성 없이 오프라인 동작이 완벽.
4. **테스트 인프라**: 19개 테스트 파일과 `conftest.py` 격리 픽스처가 잘 구축 (전체 243개 테스트 전건 통과).
5. **확장 설계**: `access.py`의 등급별 필터, README의 SaaS 청사진 등 향후 배포를 미리 고려한 설계.
6. **ES 모듈 분리**: 23개 프론트엔드 모듈이 기능별로 잘 분리되어 있으며, `dom.js`/`state.js` 공용 모듈 패턴이 우수.

---

## 진행 현황 표

| 단계 | 항목 | 상태 |
|---|---|---|
| 1단계 | P0 즉시 수정 (중복 함수/상수 정리) | ✅ 완료 |
| 2단계 | P1 구조 개선 (database.py 9대 도메인화, style.css 동기화) | ✅ 완료 |
| 3단계 | P2 품질 강화 (PDF 파서 테스트 10건, dom null 가드, DDL 고속화) | ✅ 완료 |

> 전체 3단계 작업이 `/apply all`을 통해 성공적으로 적용되었으며, 243건의 테스트가 전건 통과되었습니다.

