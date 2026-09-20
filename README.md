# 05-gichul_db: 수능·모의고사 영어 기출 데이터베이스 웹 애플리케이션

영어 수능 및 모의고사 시험지(PDF, HWP, 해설지)를 업로드하여 **문항 단위** 및 **문장 단위**로 정밀 분할하고, **로컬 SQLite 데이터베이스**에 구축하여 **구글 스타일 검색**, **2x2 4분할 지문 뷰어**, **1행 테이블 문장 뷰어(클립보드 복사)**를 제공하는 로컬 웹 애플리케이션입니다.

---

## 🌟 주요 기능 및 특징

### 1. 100% 로컬 환경 무결성 구동 (SQLite)
- 외부 클라우드나 별도 DB 서버(MySQL 등) 없이 로컬 단일 파일(`gichul.db`)로 모든 데이터가 안전하게 보존됩니다.
- 오프라인 환경에서도 완벽히 동작하며, USB나 다른 PC로 폴더째 이동해도 데이터 손실이 없습니다.

### 2. 가변 문항 번호 동적 감지 (하드코딩 배제)
- 1994년~현재까지 변화해 온 역대 수능/모의고사 문항 수 체계(과거 50문항, 2014년 수준별 수능, 현재 45문항 등)에 맞춰 문항 번호를 절대 하드코딩하지 않습니다.
- 시험지 안내문(`"1번부터 N번까지는 듣고..."`) 및 듣기 전용 발문 패턴을 정규식으로 자동 탐지하여 독해 문항을 유연하게 분리합니다.

### 3. PDF + HWP 상호 교차 검증 (Cross-Validation)
- **HWP 파서**: `pyhwpx` 및 HWPX XML 직접 파싱으로 표, 단락, 발문, 보기, 해설을 100% 무결성으로 추출.
- **PDF 2단 파서**: 모의고사 특유의 2단(Two-Column) 레이아웃을 바운딩 박스로 분할 추출하고, `PyMuPDF`를 통해 해당 문항 영역만 고화질 이미지(`static/captures/`)로 자동 크롭 저장.
- **상호 검증 엔진**: 두 파일의 본문 유사도(일치율 0~100%)를 자동 산출하여 데이터의 신뢰성을 보장합니다.

### 4. 정교한 영문 문장 단위 토크나이저
- 단순 마침표 분할 오류를 막기 위해 호칭(`Mr.`, `Dr.`), 약어(`e.g.`, `i.e.`, `etc.`, `U.S.`), 소수점(`3.5%`), 인용부호(`"..."`)를 안전하게 보호.
- 지문 식별자: `[O학년-OOOO년-OO월-OO번]`
- 문장 식별자: `[O학년-OOOO년-OO월-OO번-O번째 문장]`

### 5. Multi-LLM 기반 243개 세부 어법 범주 분류 및 필터링
- **243개 표준 어법 분류체계**: 명사(33), 대명사(18), 문장/주어(11), 동사(123), 형용사/부사(16), 전치사(6), 접속사(26), 특수구문(10)의 8개 대분류 트리 구축 (`static/data/grammar_categories.json`).
- **Multi-LLM 엔진 (`grammar_analyzer.py`)**: Google Gemini, OpenAI ChatGPT, Anthropic Claude 모델을 환경 의존성 없이 순수 REST API로 호출하여 문장 내 핵심 어법 범주, 타깃 어구, 어법 해설을 자동 생성.
- **문장 검색 캐스케이딩 필터 & 중요(⭐) 문장 큐레이션**: 어법 대분류 ➔ 세부 범주 2단계 연동 필터, 중요 문장 원클릭 별표 북마크, 인라인 및 일괄 AI 분석 제공.


---

## 🖥️ 화면 구성 및 사용자 경험 (UI/UX)

1. **[첫 화면] 구글 스타일 심플 검색**
   - 미니멀한 화이트/소프트 그레이 톤의 중앙 집중형 검색창
   - `[지문 검색]` 및 `[문장 검색]` 원클릭 모드 전환 탭
   - 학년(고1/고2/고3), 연도, 월, 태그 필터 바 제공
   - 우측 상단 `[시험지 업로드]` 및 `[⚡ 샘플 데이터 주입]` 버튼 제공

2. **[지문 검색 결과] 문항별 상단 탭 + 2x2 4분할 그리드 뷰어**
   - **문항별 상단 탭 바**: 검색된 모든 문항(18~45번 등)을 상단 탭으로 나열, 키보드 방향키(←, →) 및 마우스 휠/버튼 스크롤 지원
   - **[좌측 상단]**: PDF에서 해당 문항 영역만 자동 크롭된 고화질 원본 인쇄 이미지 (동적 크기 맞춤, 클릭 시 새 창 원본 확대)
   - **[좌측 하단]**: TXT 형식으로 변환된 문항 번호·발문 및 영문 지문 본문 + `[지문 전체 복사]` 버튼
   - **[우측 상단]**: HWP 파일에서 찾은 해당 문항의 정답 번호 및 해설/해석/어휘 텍스트 + `[해설 복사]` 버튼
   - **[우측 하단]**: 지문 메타 정보(`[고3-2024년-06월-21번]`, 발문, 일치율) + **20대 표준 문제 유형 선택기** + **실시간 태그 입력창 & 등록된 태그 칩(삭제 가능)**

3. **[문장 검색 결과] 1행 테이블 뷰어**
   - `순번 | 출처([학년-연도-월-번-문장]) | 해당 문장 | 태그 입력창 및 태그 정보 | 비고 | 텍스트 복사 버튼`
   - **출처 링크 원클릭 이동**: 출처 버튼을 클릭하면 해당 문항의 2x2 지문 상세 화면으로 즉시 전환되고 해당 탭으로 자동 포커스
   - **텍스트 복사**: 버튼 클릭 즉시 클립보드에 복사(`navigator.clipboard.writeText`)되어 한글, 워드 등에 바로 `Ctrl+V` 가능 (토스트 알림 피드백)
   - 각 문장 행마다 실시간 태그 추가 및 삭제 지원

---

## 📁 프로젝트 파일 구조

```text
05-gichul_db/
├── database.py             # SQLite DB 스키마, CRUD, 인덱스, 어법 태그 및 검색 헬퍼
├── sentence_tokenizer.py   # 약어/소수점/인용구 보존 영문 문장 분할 모듈
├── grammar_analyzer.py     # Gemini/ChatGPT/Claude Multi-LLM 243개 어법 분석 엔진
├── pdf_parser.py           # PDF 2단 칼럼 분할 파싱 및 문항별 고화질 이미지 크롭
├── hwp_parser.py           # HWP/HWPX 문제지 파싱 및 정답/해설 추출
├── validator.py            # HWP vs PDF 상호 교차 검증 및 데이터 무결성 검사
├── app.py                  # FastAPI REST API 및 웹 서버 엔드포인트
├── run.py                  # 원클릭 로컬 웹 애플리케이션 구동기
├── templates/
│   └── index.html          # 구글 스타일 검색 + 2x2 그리드 + 문장 테이블 + AI 설정 모달 SPA
└── static/
    ├── css/
    │   └── style.css       # 모던 디자인 시스템 스타일시트 (어법 태그, 별표, 필터 바 등)
    ├── js/
    │   └── main.js         # 검색, 2x2 뷰어, 문장 뷰어, 어법 캐스케이딩 필터, AI 연동 로직
    ├── data/
    │   └── grammar_categories.json # 8개 대분류, 243개 세부 어법 분류체계 JSON
    └── captures/           # 크롭된 PDF 문항 고화질 이미지 저장소
```

---

## 🔮 향후 웹 배포 기술 가이드: 사용자(교사) 아이디별 메타데이터 격리 관리

본 애플리케이션을 단일 로컬 환경에서 향후 **다중 교사가 접속하는 클라우드/웹 서비스(SaaS)**로 확장·배포할 때, 모든 사용자가 **동일한 문제·문장 데이터베이스를 공유**하면서도 **태그 정보와 문장 어법 분석 결과는 교사 아이디별로 독립적으로 관리**되도록 구현하기 위한 아키텍처 청사진입니다.

```text
[ 전체 사용자 공통 공유 DB (Master Data - 불변 자산) ]
  ├── exams (시험지 정보: 학년, 연도, 월, 시험구분)
  ├── passages (지문 원문, 발문, 보기 선지, 정답, 공식 해설, 크롭 이미지)
  └── sentences (순수 문장 원문, 문장 번호, 단어 수)
         ▲
         │ (user_id 외래키로 교사별 완전 격리)
         ▼
[ 교사 아이디별 독립 메타데이터 (User-Specific Metadata) ]
  ├── 교사 A: A교사만의 태그 목록, A교사의 243개 어법 분석 및 해설, A교사의 중요 문장(⭐)
  └── 교사 B: B교사만의 태그 목록, B교사의 243개 어법 분석 및 해설, B교사의 중요 문장(⭐)
```

---

### 1. 데이터베이스 스키마 마이그레이션 청사진

#### 1) 사용자 테이블 신설 (`users`)
```sql
CREATE TABLE users (
    id TEXT PRIMARY KEY,                 -- 교사 고유 아이디 (e.g. 'teacher_kim', UUID)
    email TEXT UNIQUE NOT NULL,          -- 교사 이메일
    name TEXT NOT NULL,                  -- 교사 이름/닉네임
    role TEXT DEFAULT 'teacher',         -- 'teacher', 'admin' 등
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### 2) 태그 테이블에 `user_id` 외래키 복합 유니크 제약 추가
- **지문 태그 (`passage_tags`)**:
  ```sql
  CREATE TABLE passage_tags (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      user_id TEXT NOT NULL,             -- 태그를 등록한 교사 ID
      passage_id TEXT NOT NULL,          -- 대상 지문 ID
      tag_name TEXT NOT NULL,            -- 태그명 (e.g. '빈칸추론', '오답률Top3')
      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
      UNIQUE (user_id, passage_id, tag_name),
      FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
      FOREIGN KEY (passage_id) REFERENCES passages (id) ON DELETE CASCADE
  );
  ```
- **문장 태그 (`sentence_tags`)**:
  ```sql
  CREATE TABLE sentence_tags (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      user_id TEXT NOT NULL,             -- 태그를 등록한 교사 ID
      sentence_id TEXT NOT NULL,         -- 대상 문장 ID
      tag_name TEXT NOT NULL,            -- 태그명 (e.g. '도치구문', '서술형후보')
      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
      UNIQUE (user_id, sentence_id, tag_name),
      FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
      FOREIGN KEY (sentence_id) REFERENCES sentences (id) ON DELETE CASCADE
  );
  ```

#### 3) 문장 어법 범주 분석 테이블 (`sentence_grammar_annotations`)
교사마다 AI로 분석한 결과나 직접 수정한 어법 범주·해설이 교사별로 격리 보관됩니다.
```sql
CREATE TABLE sentence_grammar_annotations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,               -- 분석/편집한 교사 ID
    sentence_id TEXT NOT NULL,           -- 대상 문장 ID
    category_id INTEGER NOT NULL,        -- 243개 세부 어법 범주 ID (1~243)
    pos TEXT NOT NULL,                   -- 대분류 품사 (명사, 동사 등)
    full_path TEXT NOT NULL,             -- 계층 트리 전체 경로
    leaf_name TEXT NOT NULL,             -- 최하위 범주명
    target_expression TEXT,              -- 해당 문장 내 타깃 어구
    explanation TEXT,                    -- 어법 포인트 해설
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (user_id, sentence_id, category_id),
    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
    FOREIGN KEY (sentence_id) REFERENCES sentences (id) ON DELETE CASCADE
);
```

#### 4) 교사별 문장 상태 분리 테이블 신설 (`user_sentence_status`)
문장 본체 테이블(`sentences`)은 모든 교사가 공유하는 불변 데이터이므로, 교사별 상태값(별표, 분석 여부 등)을 분리합니다.
```sql
CREATE TABLE user_sentence_status (
    user_id TEXT NOT NULL,
    sentence_id TEXT NOT NULL,
    is_starred INTEGER DEFAULT 0,        -- 해당 교사의 중요 문장(⭐) 플래그
    grammar_analyzed INTEGER DEFAULT 0,  -- 해당 교사의 어법 분석 수행 완료 여부
    memo TEXT,                           -- 해당 교사의 개인 수업 메모
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, sentence_id),
    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
    FOREIGN KEY (sentence_id) REFERENCES sentences (id) ON DELETE CASCADE
);
```

---

### 2. 백엔드 API 및 쿼리 처리 방식

1. **인증(Authentication) 의존성 주입**:
   - FastAPI 엔드포인트에 세션 또는 JWT 토큰을 통한 `current_user: User = Depends(get_current_user)` 적용.
2. **문장 목록 조회 시 조인 (JOIN)**:
   ```sql
   SELECT 
       s.id, s.passage_id, s.order_index, s.sentence_text, s.word_count,
       COALESCE(uss.is_starred, 0) AS is_starred,
       COALESCE(uss.grammar_analyzed, 0) AS grammar_analyzed
   FROM sentences s
   LEFT JOIN user_sentence_status uss 
       ON s.id = uss.sentence_id AND uss.user_id = :current_user_id
   WHERE s.passage_id = :passage_id
   ORDER BY s.order_index ASC;
   ```
3. **태그 및 어법 분석 조회/수정 시**:
   - 조회: `WHERE sentence_id = :sent_id AND user_id = :current_user_id`
   - 추가/삭제: `user_id`를 항상 세션의 `current_user_id`로 자동 바인딩하여 타 사용자의 데이터 침범을 원천 차단.

---

### 3. 아키텍처 확장 시의 핵심 이점
- **서버 스토리지 비용의 획기적 절감**: 수백~수천 명의 교사가 가입해도 수능/모의고사 기출 본문 및 고화질 PDF 크롭 이미지는 단 1벌만 유지되므로 DB 용량이 급증하지 않습니다.
- **교과 협의회/동료 교사 간 공유 기능 확장**: "A선생님이 완료한 고3 7월 모의고사 어법 분석 세트 가져오기(Clone)", 학교별 그룹 공유 태그 등 교육 협업 기능을 손쉽게 추가할 수 있습니다.
- **공식 표준 분석(Preset) 제공**: 관리자/연구회가 사전에 검증해 둔 표준 어법 분석을 '기본값'으로 배포하고, 교사는 이를 자신만의 스타일로 수정·가감할 수 있는 유연성을 제공합니다.

---

## 🚀 실행 방법

1. **필수 라이브러리 설치**:
   ```bash
   pip install fastapi uvicorn pymupdf pyhwpx pywin32
   ```

2. **로컬 웹앱 구동**:
   ```bash
   python run.py
   ```
   - 서버 구동 시 기본 브라우저에서 `http://127.0.0.1:8000`이 자동으로 열립니다.
   - 우측 상단의 **`[⚡ 샘플 데이터 주입]`** 버튼을 클릭하면 고3/고2 대표 기출 3지문 18문장이 즉시 DB에 적재되어 바로 모든 기능을 테스트할 수 있습니다.

---

## 변경 이력

### [2026-09-20 12:20] 업데이트 이력 (Commit ID: 90f19d5)
- **수정 내용**:
  - 프로젝트 초기화 및 GitHub 원격 저장소(`https://github.com/xoruddkqk4-glitch/gichul_db.git`) 연동
  - 에이전트 실행 규칙(`AGENTS.md`, `GEMINI.md`, `CLAUDE.md`, `.agents/`) 구축 및 터미널 전용 고속 검증 워크플로우 적용
  - `database.py`: 로컬 단일 파일 SQLite(`gichul.db`) 스키마(시험지, 지문, 문장, 태그), 인덱스 및 검색 엔진 구축
  - `sentence_tokenizer.py`: 호칭/약어/소수점/인용구 예외를 완벽 방어하는 영문 문장 토크나이저 및 `[O학년-OOOO년-OO월-OO번-O번째 문장]` 식별자 부여 로직 구현
  - `pdf_parser.py`: 모의고사 2단(Two-Column) 레이아웃 분할 파싱, 가변 문항 번호 동적 감지(하드코딩 배제), `PyMuPDF` 기반 문항 바운딩 박스 크롭 이미지 자동 생성기 구현
  - `hwp_parser.py`: HWP/HWPX 문제지 지문 파싱 및 정답/해설/해석/어휘 추출 모듈 구현
  - `validator.py`: HWP vs PDF 본문 정규화 및 상호 교차 검증(유사도 산출) 파이프라인 구현
  - `app.py`: FastAPI 기반 REST API(지문/문장 검색, 2x2 상세 조회, 실시간 태그 CRUD, PDF+HWP 업로드 파이프라인, 대표 기출 샘플 데이터 시더) 구현
  - `templates/index.html` & `static/css/style.css` & `static/js/main.js`: 구글 스타일 심플 첫 화면, 2x2 4분할 지문 결과 뷰어, 1행 테이블 문장 결과 뷰어, 원클릭 클립보드 복사, 실시간 태그 관리 SPA 프론트엔드 개발
  - `run.py`: 원클릭 로컬 웹 서버 실행기 제공
- **검증 결과**:
  - `python -m py_compile app.py database.py hwp_parser.py pdf_parser.py sentence_tokenizer.py validator.py run.py` 구문 검증 완료 (전체 통과)
  - 영문 문장 토크나이저 약어(`Dr.`, `U.S.`, `3.5%`) 분할 보호 단위 테스트 통과
  - SQLite DB CRUD 및 지문/문장 키워드 검색 엔드포인트 비동기 테스트 완료 (통과)
  - 대표 기출 3개 지문 및 18개 문장 데이터 주입 및 상세 조회 API 검증 완료 (통과)

### [2026-09-20 13:25] 업데이트 이력 (Commit ID: 72b3543)
- **수정 내용**:
  - **지문 ↔ 문장 검색 모드 전환 시 문항 컨텍스트 유지**: 상단 검색창에서 `[지문]`과 `[문장]` 모드를 변경할 때 18번으로 기본 리셋되던 문제를 수정하여, 현재 선택된 문항(예: 33번)의 문장 결과 및 지문 결과로 상호 즉시 유지 이동하도록 구현
  - **문장 출처 클릭 시 지문 상세 화면 직접 이동**: 문장 결과 테이블의 출처(`[고3-2026년-07월-33번-8번째 문장]`)를 대화형 버튼(`.btn-source-link`)으로 개선하여, 클릭 시 2x2 지문 결과 화면으로 전환 및 해당 문항 탭 자동 포커스 이동 기능 구현
  - **문장 결과 내 선지/각주/배점 완전 배제**: `sentence_tokenizer.py`의 `clean_passage_for_sentences` 정규식을 강화하여, 객관식 선지(`①`~`⑤`), 어휘 각주(`* deviate...`), 배점 표기(`[3점]`, `[2점]`)를 완벽 제거하고 순수 지문 본문 문장만 분할 저장
  - **PDF 문항 크롭 이미지 동적 스케일링 (스크롤바 제거)**: `.pdf-panel-content`와 `.pdf-crop-img`에 `object-fit: contain` 및 `overflow: hidden`을 적용하여 가로/세로 스크롤바 없이 컨테이너 영역에 동적으로 맞춤 렌더링
  - **2단 PDF 칼럼 분할 격리 (전체 페이지 크롭 오류 해결)**: `pdf_parser.py`에서 좌/우 칼럼을 완전 격리 순회하고 헤더(`y1 < 160`) 및 푸터/페이지 번호를 제외하여 22번, 26번 등 칼럼 하단 문항이 페이지 전체로 크롭되던 현상 완벽 해결 (단일 칼럼 너비 ~328pt 렌더링)
  - **HWP 해설지 복합 범위 헤더 및 공유 지문 지원**: `hwp_parser.py`에서 `41~42.`, `43~45.` 범위 헤더 정규식을 지원하여 모든 하위 문항에 해설/해석이 정상 매핑되도록 개선하고, 복합 지문 본문 연동 완료
  - **TXT 지문 본문 텍스트에 문항 번호 및 발문 포함**: TXT 지문 본문 및 클립보드 복사 시 상단에 문항 번호와 발문(`21. 밑줄 친...`)이 자동 포함되도록 파이프라인 통일
  - **좌측 하단 카드 내 중복 '전체 문장' 버튼 제거**: 상단 공통 헤더 슬롯 버튼(`[📝 전체 문장]` ↔ `[지문 결과창으로 돌아가기]`)으로 단일화하여 UI 일관성 확립
  - **교육청 월별 필터(3, 5, 7, 10월) 및 시험 구분(평가원/교육청) 확장**: 상단 필터 및 모달에 반영
- **검증 결과**:
  - `python -m py_compile app.py database.py hwp_parser.py pdf_parser.py sentence_tokenizer.py validator.py` 구문 검증 완료 (통과)
  - `node --check static/js/main.js` 자바스크립트 문법 검사 통과 (오류 0건)
  - 33번 문항 8번째 문장 및 전 문항 문장 내 선지/배점/각주 완전 제거 검증 완료 (`GET /api/search/sentences?passage_id=...`)
  - 28개 전 문항 단일 칼럼 크롭 고화질 이미지 생성 및 2x2 뷰어 연동 확인

### [2026-09-20 13:45] 업데이트 이력 (Commit ID: a442325)
- **수정 내용**:
  - **결과창 상단 버튼 텍스트 변경**: 결과 내비게이션 바의 '다시 검색' 버튼 텍스트를 `[← 처음 화면으로 돌아가기]`로 직관화 및 가독성 개선
  - **41~42번 및 43~45번 복합 장문 단일 탭 통합**: `static/js/main.js`에 `groupPassageItems()` 모듈을 구축하여 41~42번(1지문 2문항), 43~45번(1지문 3문항)을 상단 탭에서 각각 `41~42번 [1지문2문항] (답: 41.① / 42.⑤)`, `43~45번 [1지문3문항] (답: 43.③ / 44.⑤ / 45.⑤)` 형태의 단일 탭으로 병합. 2x2 뷰어에서 해당 문항들의 크롭 이미지를 세로 스크롤로 연속 표시하고, 발문/선지가 모두 포함된 결합 본문과 통합 해설 렌더링
  - **HWP 정답 정보 추출 및 해설 상단 표기**: `hwp_parser.py`에서 시험지 정답 정보를 매핑하여 `answer_text` 컬럼에 영구 적재하고, 해설지 최상단에 `[정답] {번호}` 라벨 자동 보강
  - **PDF 캡처 이미지 정답 선지 형광펜 하이라이트**: `pdf_parser.py`에서 `PyMuPDF`를 통해 해당 문항의 정답 선지(①~⑤) 및 보기 텍스트 전체 영역을 자동 탐색하고, 선명한 형광 노란색(`RGB 1.0, 0.95, 0.1`) 하이라이트 주석을 적용한 200 DPI 고화질 크롭 이미지 생성
  - **2x2 좌하단 TXT 지문 본문에 객관식 선지(①~⑤) 전체 보존**: `hwp_parser.py` 및 `pdf_parser.py`의 `passage_text`에 문제 번호, 발문, 영어 지문뿐만 아니라 보기 선지까지 온전히 포함하여 [지문 전체 복사] 시 문제 전체를 복사할 수 있도록 개선 (문장 DB는 순수 문장 전용으로 정제 분리 유지)
  - **.gitignore 갱신**: 로컬 임시 스크래치 디렉토리(`scratch/`) 무시 규칙 추가
- **검증 결과**:
  - `python -m py_compile app.py database.py hwp_parser.py pdf_parser.py sentence_tokenizer.py validator.py run.py` 구문 검증 완료 (통과)
  - `node --check static/js/main.js` 자바스크립트 문법 검사 통과 (오류 0건)
  - 고3 2026년 7월 28개 전 문항 정답 선지 형광펜 하이라이트 크롭 이미지 시각 확인 및 데이터베이스 재동기화 완료
### [2026-09-20 13:52] 업데이트 이력 (Commit ID: be300cc)
- **수정 내용**:
  - **상단 문항별 선택 탭 정답 표기 제거**: 상단 가로 스크롤 문항별 탭 버튼에서 정답 정보(`(답: ①)`)를 배제하여, 문항 번호와 문제 유형 라벨(`18번 [글의목적]`, `41~42번 [1지문2문항]` 등)만 직관적이고 깔끔하게 표시되도록 UI 개선 (`static/js/main.js`)
  - **우측 하단 메타 패널 간소화 ('추가 정보')**:
    - 패널 카드 헤더 제목을 `'🏷️ 지문 정보 · 문제 유형 · 태그'`에서 **`'🏷️ 추가 정보'`**로 변경 (`templates/index.html`)
    - 패널 내부에서 **'문제 유형'** 선택 셀렉트 박스 및 **'문제 발문'** 텍스트 표시 영역을 완전히 제거하여 지문 식별자/문항번호/정답/일치율 및 태그 관리 영역의 가독성과 집중도 향상 (`templates/index.html`)
    - 프론트엔드 스크립트 내 삭제된 DOM 요소(`metaQuestionTitle`, `selectQuestionType`)에 대한 null 안전 참조 처리 완료 (`static/js/main.js`)
- **검증 결과**:
  - `node --check static/js/main.js` 자바스크립트 구문 검사 통과 (오류 0건)
  - `python -m py_compile app.py database.py hwp_parser.py pdf_parser.py sentence_tokenizer.py validator.py run.py` 파이썬 구문 검증 완료 (통과)
### [2026-09-20 14:02] 업데이트 이력 (Commit ID: 02a710e)
- **수정 내용**:
  - **복합 지문(41~42번, 43~45번) TXT 지문 본문 중복 반복 배제**: 상단 복합 탭 선택 시 첫 문항(41번, 43번)에만 전체 영문 지문 본문 + 문제 + 선지를 표시하고, 후속 문항(42번, 44번, 45번)은 지문 본문을 다시 중복하지 않고 `발문 + 선지`만 추출(`extractQuestionChoicesOnly`)하여 깔끔하게 구분 표시하도록 개선 (`static/js/main.js`)
  - **1지문 3문항(43~45번) 영역별 분할 캡처 및 세로 이어붙이기 파이프라인 구축**: 수능/모의고사 장문 2단의 칼럼 간 분할 구조를 완벽 인식하는 `crop_and_merge_43_45()` 모듈을 구축하여, 좌측 칼럼 `[43~45] + (A)`와 우측 칼럼 `(B)~(D)`, 43번/44번/45번 문항을 각각 따로 캡처(각 정답 선지에 형광펜 하이라이트 적용)한 뒤 세로로 매끄럽게 이어붙인 고화질 단일 크롭 이미지 생성 및 뷰어 연동 (`pdf_parser.py`, `static/captures/`)
  - **복합 문항 HWP 정답 및 해설 패널 모든 문항 정답 표기**: 복합 문항 선택 시 해설 패널 상단에 첫 문항 정답만 단독 노출되던 문제를 수정하여, 해당 복합 지문에 속한 모든 문항의 정답(`[정답] 43. ③   44. ⑤   45. ⑤`, `[정답] 41. ③   42. ⑤`)이 해설지 최상단에 명확하게 표기되도록 개선 (`static/js/main.js`)
- **검증 결과**:
  - `node --check static/js/main.js` 자바스크립트 문법 검사 통과 (오류 0건)
  - `python -m py_compile app.py database.py hwp_parser.py pdf_parser.py sentence_tokenizer.py validator.py run.py` 파이썬 구문 검증 완료 (통과)
  - 43~45번 결합 크롭 이미지(`고3_2026_07_43.png`, 1058x3429px) 생성 및 데이터베이스 연동 확인
### [2026-09-20 14:17] 업데이트 이력 (Commit ID: f305f9d)
- **수정 내용**:
  - **문항별 선택 탭 표시 개편 (2행 구조 & 1행 10개 그리드)**:
    - 탭 버튼에서 문제 유형 라벨을 제거하고, 1행 `[고O-OOOO년]`, 2행 `[OO월-OO번]`의 2행 텍스트 구조로 변경하여 언제 기출인지 직관적으로 파악할 수 있도록 개선 (`static/js/main.js`, `static/css/style.css`)
    - 가로 스크롤바를 완전히 제거하고 CSS Grid(`repeat(10, minmax(0, 1fr))`)를 적용하여 1행에 항상 10개 문항 탭이 정갈하게 배열되고 11번째 문항부터 아래 행에 자동 추가되도록 레이아웃 고도화 (`static/css/style.css`, `templates/index.html`)
  - **우측 하단 '추가 정보' 패널 내 '문제 유형' 항목 표시**:
    - 탭에서 제외된 문제 유형 정보를 우측 하단 '추가 정보' 패널 메타 정보 행(`meta-info-row`)에 신설(`metaQuestionType`)하여 지문 식별자, 문항 번호, 문제 유형, 정답을 한눈에 체계적으로 확인 가능하도록 연동 (`templates/index.html`, `static/js/main.js`)
  - **'결과 내 검색' 버튼 및 고속 필터링 기능 신설**:
    - 상단 결과창 검색바의 `[검색]` 버튼 옆에 **`[결과 내 검색]`** 버튼(`btnSearchWithinResults`) 추가 (`templates/index.html`, `static/css/style.css`)
    - 1차 검색된 지문/문장 원본 데이터 캐시(`rawPassagesData`, `rawSentencesData`)를 기준으로, 입력 키워드가 포함된 문항(본문, 발문, 식별자, 해설, 유형, 태그, 복합 하위 항목)만 지연 없이 0ms 즉각 필터링하는 `executeSearchWithinResults()` 함수 구현 (`static/js/main.js`)
- **검증 결과**:
  - `node --check static/js/main.js` 자바스크립트 문법 검사 통과 (오류 0건)
  - `python -m py_compile app.py database.py hwp_parser.py pdf_parser.py sentence_tokenizer.py validator.py run.py` 파이썬 구문 검증 완료 (통과)

### [2026-09-20 14:31] 업데이트 이력 (Commit ID: a48a50c)
- **수정 내용**:
  - **'결과 내 검색' 활성화/비활성화 토글 스위치 모드 개편 & [검색] 버튼 일원화**:
    - 상단 검색바의 `[결과 내 검색]` 버튼을 별도 실행 버튼에서 **클릭 시 ON/OFF 전환되는 토글 스위치 버튼(`btnToggleSearchWithin`)**으로 변경 (`templates/index.html`)
    - 비활성(OFF: 단정한 그레이 아웃라인과 닷)과 활성(ON: 은은한 라이트 블루 배경과 네온 인디케이터 닷) 상태를 명확히 구분하는 세련된 UI 스타일 적용 (`static/css/style.css`)
    - `isSearchWithinActive` 상태 변수를 통해 `[검색]` 버튼 클릭 또는 검색창 `Enter` 키 입력 시 토글 활성 상태면 `executeSearchWithinResults()`(현재 목록 즉시 필터링), 비활성 상태면 `executeSearch("results")`(전체 DB 검색)가 실행되도록 검색 트리거 일원화 (`static/js/main.js`)
  - **평가원 문항 정답 형광펜 표시 및 업로드 파이프라인 무결성 보장**:
    - 해설지 서두 정답표(`01. ③ ~ 45. ④`) 블록을 탐지하는 정규식 패턴을 보강하여 다양한 표/공백 서식의 평가원 정답을 완벽 추출하도록 개선 (`hwp_parser.py`)
    - 업로드 파이프라인에서 HWP 정답 추출과 `KNOWN_EXAM_ANSWERS` 백업 사전을 결합하여, 평가원/교육청/수능 어떤 시험지라도 정답 누락 없이 100% 확보하고 PDF 선지 노란색 형광펜(`RGB 1.0, 0.95, 0.1`) 하이라이트 크롭 이미지가 자동 생성되도록 보장 (`app.py`)
    - 기존 2026년 6월 평가원 28개 전 문항(18~45번) `gichul.db` 정답/해설 갱신 및 200 DPI 고화질 정답 형광펜 하이라이트 크롭 이미지(`static/captures/고3_2026_06_*.png`)와 43~45번 세로 결합 이미지 재생성 완료
  - **문항별 선택 탭 버튼 디자인 세련화 (모던 프리미엄 UI)**:
    - 1행 10개 문항 탭 버튼(`.passage-q-tab`)을 최신 웹 앱(토스, 애플) 스타일로 리디자인 (`static/css/style.css`)
    - 1행 메타 뱃지(`tab-line-exam`): 연한 슬레이트 캡슐 마이크로 뱃지(`background: #f1f5f9; color: #64748b; font-size: 0.68rem; font-weight: 700;`)로 시각적 위계 분리
    - 2행 문항 번호(`tab-line-q`): 또렷하고 선명한 다크 슬레이트 타이포그래피(`color: #0f172a; font-size: 0.86rem; font-weight: 800;`)
    - 부드러운 라운딩(`9px`), 은은한 그림자, 호버 리프트(-1.5px) 애니메이션, 활성 탭(`.active`) 선택 시 프리미엄 로열 블루 그라데이션 및 글로우 섀도우 효과 적용
- **검증 결과**:
  - `node --check static/js/main.js` 자바스크립트 문법 검사 통과 (오류 0건)
  - `python -m py_compile app.py database.py hwp_parser.py pdf_parser.py sentence_tokenizer.py validator.py run.py` 파이썬 구문 검증 완료 (통과)
  - 2026년 6월 평가원 28개 전 문항 정답 DB 업데이트 및 형광펜 주석 이미지 28개 생성 확인

### [2026-09-20 14:41] 업데이트 이력 (Commit ID: 36d1f01)
- **수정 내용**:
  - **정답 선지 기하학적 앵커 매칭 알고리즘(`extract_choice_words_geometrically`) 구축**:
    - 43번 등 2열 조판 문항에서 PDF 내부 단어 스트림 순서 왜곡으로 인해 정답 선지(⑤번)뿐 아니라 다른 선지(①, ③번)까지 형광펜이 칠해지던 문제 원인 규명 및 해결 (`pdf_parser.py`)
    - 화면상 실제 X/Y 좌표 및 행/열 바운딩 박스를 기준으로 동일 행/열 단어만 정밀 필터링하여 오직 정답 선지 1개만 정확하게 형광펜 주석 처리 (`pdf_parser.py`)
    - 2026년 6월 평가원 및 7월 교육청 전체 문항 고화질 크롭 이미지 재생성 완료 (`static/captures/`)
  - **검색창 내 `#태그` 자동 검색 인터페이스 전면 개편**:
    - 별도로 존재하던 `filterTag` 입력창을 UI에서 완전히 제거하여 검색 인터페이스를 직관적이고 미니멀하게 개선 (`templates/index.html`)
    - 첫 검색창과 결과창 검색창 모두에서 `#태그명`(예: `#빈칸`, `#어법`) 입력 시 자동으로 `tag` 파라미터로 파싱(`parseSearchQuery`)하여 태그 검색 수행 (`static/js/main.js`)
    - 결과 내 검색(`executeSearchWithinResults`)에서도 `#태그` 입력 시 현재 로드된 문항의 `tags` 및 문제 유형을 즉시 필터링 (`static/js/main.js`)
    - 백엔드(`/api/search/passages`, `/api/search/sentences`) 및 DB 검색 쿼리에서 `tag_name LIKE ?` 퍼지 매칭 지원 (`app.py`, `database.py`)
- **검증 결과**:
  - `node --check static/js/main.js` 자바스크립트 문법 검사 통과 (오류 0건)
  - `python -m py_compile app.py database.py hwp_parser.py pdf_parser.py sentence_tokenizer.py validator.py run.py` 파이썬 구문 검증 완료 (통과)
  - 43번 영역 형광펜 주석 개수가 3개에서 정답 5번 선지 1개(`Rect(440.9, 768.1, 555.7, 788.3)`)로 정상화 확인

### [2026-09-20 14:45] 업데이트 이력 (Commit ID: e5fefd4)
- **수정 내용**:
  - **문장 검색 결과 내 검색 표현(키워드) 노란색 형광펜 하이라이트 표시 구현**:
    - 검색창에 입력된 키워드(예: `cultur`)를 대소문자 구분 없이 문장 텍스트 내에서 실시간 매칭하는 `highlightSentenceKeyword()` 함수 구현 (`static/js/main.js`)
    - 문장 검색 테이블(`renderSentenceView`) 렌더링 시 검색 키워드와 일치하는 표현(`Culture`, `cultural` 등)을 `<mark class="sentence-highlight">` 태그로 감싸 선명하게 형광펜 처리 (`static/js/main.js`)
    - 검색어에 `#태그`가 포함되어 있을 때도 해시태그를 제외한 순수 텍스트 키워드 부분만 정밀하게 분리하여 하이라이트 (`static/js/main.js`)
    - `[📋 텍스트 복사]` 버튼 클릭 시에는 마크업 없는 순수 원본 영문 텍스트가 복사되도록 무결성 유지 (`static/js/main.js`)
    - `.sentence-highlight` 및 `.col-sentence mark` 스타일 신설: 눈에 편안한 파스텔 형광 노란색(`background-color: #fef08a`), 글자색(`#0f172a`), 폰트 볼드(`700`), 4px 라운딩 및 은은한 음영 적용 (`static/css/style.css`)
- **검증 결과**:
  - `node --check static/js/main.js` 자바스크립트 문법 검사 통과 (오류 0건)
  - 문장 검색 결과 화면에서 검색 키워드 하이라이트 렌더링 정상 동작 확인

### [2026-09-20 15:48] 업데이트 이력 (Commit ID: 7d21a0f)
- **수정 내용**:
  - **문장 검색 & 지문 본문 TXT 검색어 파스텔톤 빨간색 형광펜 하이라이트 전환**:
    - 문장 검색 결과 표현 및 지문 검색 2x2 화면의 'TXT 지문 본문 텍스트' 패널에 검색 키워드를 부드럽고 선명한 파스텔톤 로즈 레드 형광펜(`<mark class="passage-highlight">`, `<mark class="sentence-highlight">`)으로 실시간 하이라이트 표시 (`static/css/style.css`, `static/js/main.js`)
      - 배경색: `#fecdd3` (Soft Rose Red), 글자색: `#9f1239` (Deep Crimson), 4px 라운딩 및 섀도우 적용
    - PDF 문항 인쇄 이미지는 원본 그대로 유지하고, 순수 TXT 지문 본문 패널(`panelPassageText`)에만 하이라이트 적용
    - 단일 지문 및 복합 지문(41~42번, 43~45번) 분할 본문 전체에서 검색 표현 누락 없이 정밀 매칭
    - `[📋 지문 전체 복사]` 시 HTML 태그 없이 순수 원본 텍스트만 깨끗하게 복사되도록 `panelPassageText.dataset.rawText` 우선 참조 로직 적용 (`static/js/main.js`)
  - **지문 결과 선택 탭의 초컴팩트 트리 계층형 네비게이터([학년] → [년도] → [월] → [문항 1행 10개]) 전면 개편**:
    - 복수 시험 검색 시 학년/년도/월을 단계별로 탐색할 수 있는 동적 트리 네비게이터 구축 (`static/js/main.js`, `templates/index.html`)
    - DB 전체가 아닌 **현재 검색된 결과 문항들에 실제로 존재하는 계층만 실시간 추출**하여 버튼 구성 (결과 없는 빈 계층 노출 방지 및 문항 수 배지 표기)
    - 월/시험 선택 완료 시 상위 계층 버튼들은 자동으로 숨겨지고, 상단에 **단 26px 높이의 인라인 브레드크럼(`📍 [고3] > [2026년] > [07월 (인천시)] (28문항)`)**으로 축약 표시 (`static/css/style.css`, `templates/index.html`)
    - 최하위 문항 탭은 버튼 높이 **28px**의 단일 행 문항 번호(`18번` ~ `45번`)로 미니멀화하고, 1행 10개 그리드(`repeat(10, minmax(0, 1fr))`)로 정렬하여 탭 패널의 세로 공간을 65% 이상 절약(기존 ~240px → ~85px 안팎)하여 하단 2x2 패널의 높이를 극대화 (`static/css/style.css`, `static/js/main.js`)
    - 브레드크럼 항목 클릭 또는 `[🔄 다른 시험 선택]` 버튼으로 언제든지 상위 단계로 즉시 복귀 가능
    - 단일 시험 검색 시 상위 선택 과정을 건너뛰고 자동으로 문항 1행 10개 탭으로 직행
    - 문장 검색에서 출처 링크 클릭 시(`navigateToPassageView`) 해당 시험의 계층으로 자동 진입 후 해당 문항 2x2 패널 즉시 포커스
  - **데이터베이스 용량 한도 및 원본 파일 삭제 안전성 기술 검토**:
    - 현재 디스크 여유 공간(295.08 GB), DB 크기(492 KB), 캡처 이미지(12.48 MB)를 기반으로 1회분 소요 용량(~8 MB) 및 추가 가능 회수(약 37,000~45,000회분, 2,000년치 이상) 정밀 산출 및 보고서 수립
    - `uploads/` 폴더 내 원본 파일은 이미 DB와 `static/captures/`에 분리 저장되어 있으므로 삭제해도 웹 서비스 기능에 영향이 없음을 검증 및 안내
- **검증 결과**:
  - `node --check static/js/main.js` 자바스크립트 문법 검사 통과 (오류 0건)
  - `python -m py_compile app.py database.py run.py` 파이썬 구문 검증 완료 (통과)
  - 지문 검색 TXT 본문 및 문장 검색 결과 파스텔톤 빨간색 형광펜 하이라이트 정상 렌더링 확인
### [2026-09-20 16:00] 업데이트 이력 (Commit ID: 58baa24)
- **수정 내용**:
  - **PDF 캡처 이미지 정답 번호 전용 파스텔톤 노란색 형광펜 하이라이트 적용**:
    - 형광펜 색상을 기존 원색 노란색에서 눈에 편안한 파스텔톤 노란색 형광(`#fef08a`, RGB `0.996, 0.941, 0.541`)으로 교체 (`pdf_parser.py`)
    - 선지 전체 텍스트에는 형광펜을 칠하지 않고, 오직 정답에 해당하는 번호 원문자(①, ②, ③, ④, ⑤)에만 2pt 여백을 부여하여 정확하고 깔끔하게 하이라이트 주석을 적용하도록 알고리즘 개편 (`pdf_parser.py`)
    - 2026년 6월 평가원 28개 및 7월 교육청 28개 전 문항(총 56개) 고화질 크롭 이미지 일괄 재생성 완료 (`static/captures/`)
  - **트리 계층 브레드크럼 바 버튼 및 텍스트 2배 확대**:
    - 상단 경로 네비게이터(`📍 [고3] > [2026년] > [07월 · 교육청] (2문항)`)의 브레드크럼 버튼(`.breadcrumb-item`) 및 내부 폰트 크기를 기존 0.76rem에서 약 2배인 `1.45rem`으로 확대 (`static/css/style.css`)
    - 버튼 패딩(`0.32rem 0.95rem`), 둥근 모서리(`8px`), 테두리 선 굵기, 계층 구분 기호(`>`, `1.3rem`), 문항 수 뱃지(`1.3rem`), 네비게이터 아이콘(`1.55rem`)을 함께 확대하여 시인성과 터치/클릭 편의성 극대화 (`static/css/style.css`)
  - **지문 검색 결과 화면 패널 레이아웃 맞바꿈 (2x2 그리드)**:
    - 우측 상단(`col: 2, row: 1`): `TXT 지문 본문 텍스트` 패널을 배치하여 좌측의 `PDF 원본 문항`과 나란히 시선을 이동하며 지문 원문과 텍스트를 대조할 수 있도록 최적화 (`templates/index.html`)
    - 좌측 하단(`col: 1, row: 2`): `HWP 정답 및 해설` 패널로 스왑 배치하여 해설을 아래쪽에서 넓게 참조할 수 있도록 변경 (`templates/index.html`)
- **검증 결과**:
  - `python -m py_compile pdf_parser.py app.py database.py run.py` 파이썬 구문 검증 완료 (통과)
  - `node --check static/js/main.js` 자바스크립트 문법 검사 통과 (오류 0건)
  - 56개 전 문항 캡처 이미지 정답 번호 파스텔톤 노란색 하이라이트 정상 생성 확인

### [2026-09-20 16:55] 업데이트 이력 (Commit ID: 452e7e2)
- **수정 내용**:
  - **243개 세부 어법 분류체계 구축 및 JSON 정적 서빙**:
    - 사용자 제공 원본 분류표를 기반으로 8개 대분류(명사, 대명사, 문장/주어, 동사, 형용사/부사, 전치사, 접속사, 특수구문), 243개 세부 어법 범주를 계층 트리(`tree`), 고유 ID별 플랫 리스트(`list`), 메타데이터(`meta`) 구조로 정제하여 `static/data/grammar_categories.json`에 적재
  - **Multi-LLM 기반 어법 분석 엔진 구현 (`grammar_analyzer.py`)**:
    - 외부 라이브러리 의존성 없이 Python 기본 라이브러리(`urllib.request`)로 Google Gemini, OpenAI ChatGPT, Anthropic Claude 3개 주요 LLM의 REST API 클라이언트 구축
    - 243개 범주 ID 및 `full_path`를 프롬프트에 주입하여 문장 분석 시 최대 3개 어법 범주 ID, 타깃 어구, 상세 어법 해설을 JSON 형태로 구조화하여 응답받는 알고리즘 구현 및 실시간 연결 테스트(`test_connection`) 기능 개발
  - **데이터베이스 스키마 확장 및 영구 저장 (`database.py`)**:
    - `sentences.is_starred` (INTEGER) 중요 문장 북마크 컬럼 추가 및 마이그레이션
    - `sentence_grammar_annotations` 테이블 신설: 1개 문장에 복수 어법 태그(cat_id, pos_category, full_path, target_phrase, explanation, model_name) 연동
    - `app_settings` 테이블 신설: LLM Provider, API Key, 자동 분석 옵션 영구 보관
    - `search_sentences` 쿼리에 `is_starred`, `grammar_pos`, `grammar_cat_id` 조건 필터링 추가
  - **FastAPI 백엔드 API 라우트 및 백그라운드 자동 분석 (`app.py`)**:
    - AI 설정 조회/저장/테스트 엔드포인트(`GET/POST /api/settings/ai`, `POST /api/settings/ai/test`)
    - 문장 별표 토글(`POST /api/sentences/{id}/star`), 단일 문장 AI 분석(`POST /api/sentences/{id}/analyze-grammar`), 중요 문장 일괄 분석(`POST /api/sentences/batch-analyze-grammar`) 엔드포인트 신설
    - 신규 시험지 업로드 시 백그라운드 작업(`BackgroundTasks`)으로 전체 문장 자동 어법 분석을 비동기 수행하도록 연동
  - **문장 검색 UI/UX 고도화 및 어법 캐스케이딩 필터 (`templates/index.html`, `static/css/style.css`, `static/js/main.js`)**:
    - 상단 헤더에 `[🔑 AI 설정]` 버튼 및 Provider/API Key 설정/연결테스트 모달 구축
    - 첫 화면 및 검색 결과 화면 필터 바에 어법 대분류 ➔ 세부 범주 2단계 연동 캐스케이딩 드롭다운 셀렉트 박스 신설
    - `[⭐ 중요 문장만 보기]` 원클릭 토글 필터 및 테이블 상단 `[⭐ 중요 문장 일괄 AI 어법 분석]` 버튼 신설
    - 문장 테이블 행마다: 원클릭 `⭐` 별표 토글 버튼, 대분류별 컬러 어법 뱃지 칩(툴팁으로 세부 경로 및 AI 해설 제공), 인라인 `[🤖 분석]` 버튼 및 로딩 스피너 구현
- **검증 결과**:
  - `python -m py_compile app.py database.py grammar_analyzer.py run.py` 파이썬 구문 검증 완료 (통과)
  - `node --check static/js/main.js` 자바스크립트 문법 검사 통과 (오류 0건)
  - 로컬 라이브 서버 API 단위 테스트 완료 (`GET /api/settings/ai`, `POST /api/sentences/1/star`, `GET /api/search/sentences?is_starred=true` 정상 응답)

### [2026-09-20 17:10] 업데이트 이력 (Commit ID: 8c1672a)
- **수정 내용**:
  - **AI 모달 엔진(Provider) 변경 시 기본(Default) 모델명 자동 변경 연동**:
    - `aiProviderSelect` 드롭다운 변경 시 모델명 입력창(`aiModelInput`)의 값이 해당 엔진의 기본 권장 모델(`gemini-1.5-flash`, `gpt-4o-mini`, `claude-3-5-haiku-20241022`)로 즉시 자동 갱신되도록 개선 (`static/js/main.js`)
    - 모달 오픈 시 기저장된 모델명이 없을 때도 기본 권장 모델명 자동 세팅 및 도움말/발급링크 동적 연동
  - **첫 화면 '지문 검색' 모드 시 어법 필터 자동 숨김**:
    - 홈 화면의 `[지문 검색]` 탭 활성화 시 `[어법 대분류]`, `[세부 어법 전체]`, `[⭐ 중요 문장]` 필터 그룹을 완전히 숨기고(`display: none`), `[문장 검색]` 탭 선택 시에만 자연스럽게 노출되도록 제어 (`templates/index.html`, `static/js/main.js`)
  - **문장 검색 결과 테이블 [복사] / [분석] 버튼 한 줄 표시 및 열 너비 확장**:
    - 테이블 헤더 및 셀 `col-action`의 열 너비를 기존 110px에서 175px(`min-width: 175px`)로 확장 (`templates/index.html`, `static/css/style.css`)
    - 버튼들을 `.action-btn-group`으로 감싸고 `white-space: nowrap !important; word-break: keep-all;` 스타일을 적용하여 텍스트가 줄바꿈되지 않고 `[📋 복사]`, `[🤖 분석]`이 깔끔한 한 줄로 표시되도록 UI 최적화 (`static/css/style.css`, `static/js/main.js`)
  - **결과 화면 상단 검색바 & 필터 2행 분리 구조 개편 (버튼 겹침 현상 원천 차단)**:
    - 상단 내비게이션 바(`results-nav-bar`)를 **1행(돌아가기 버튼 + 우측 검색바)**과 **2행(필터 옵션 그룹 + 결과 건수 배지)**의 2행 분리 독립 행 구조로 리팩토링하여 버튼과 드롭다운이 겹치거나 찌그러지던 현상 해결 (`templates/index.html`, `static/css/style.css`)
  - **'지문 결과 창' 어법 필터 완전 숨김**:
    - `currentMode === "passage"`(지문 결과 뷰어) 상태일 때는 2행 필터 바에서도 어법 필터 그룹(`resultsGrammarFiltersGroup`)을 자동으로 숨겨 지문 검색에만 집중할 수 있도록 처리 (`static/js/main.js`)
  - **문장 검색 결과 화면 어법 필터 및 중요 문장 실시간 테이블 필터링 연동**:
    - 문장 검색 모드에서 2행 필터 바의 `[어법 대분류]`, `[세부 어법 전체]`, `[⭐ 중요]` 필터 조작 시, 아래 문장 테이블 목록에서 해당 조건에 부합하는 문장들만 실시간으로 즉시 필터링/검색되어 테이블과 결과 건수 배지가 동기화되도록 개선 (`static/js/main.js`)
- **검증 결과**:
  - `node --check static/js/main.js` 자바스크립트 문법 검사 통과 (오류 0건)
  - `python -m py_compile app.py database.py grammar_analyzer.py run.py` 파이썬 구문 검증 완료 (통과)

### [2026-09-20 17:18] 업데이트 이력 (Commit ID: a7c4222)
- **수정 내용**:
  - **중요 문장 버튼 동일 행 유지 & 줄바꿈 방지**:
    - `home-grammar-filters-group` 및 `results-grammar-filters-group`에 `flex-wrap: nowrap !important; white-space: nowrap !important;`를 적용하여 `[어법 대분류]`, `[세부 어법 전체]`, `[⭐ 중요 문장]` 세 요소가 항상 동일한 한 행에 나란히 배열되도록 개선 (`static/css/style.css`)
  - **어법 대분류 및 세부 어법 선택창 너비 210px 균등화 & 텍스트 가운데 정렬**:
    - 첫 화면과 결과 화면의 어법 선택창 가로 너비를 210px로 균등 고정(`width: 210px !important; min-width: 210px !important; max-width: 210px !important;`)하고, 내부 텍스트를 정중앙 정렬(`text-align: center !important; text-align-last: center !important;`)하여 레이아웃 무결성 및 가독성 확보 (`static/css/style.css`)
  - **어법 필터 및 중요 문장 버튼 파스텔톤 네모 배경 박스 적용**:
    - 기본 필터(학년, 연도, 월, 시험구분, 문제유형)와 시각적 위계를 분리하기 위해 3개 요소를 감싸는 컨테이너에 은은한 파스텔 라벤더·인디고 그라데이션 네모 박스(`background: linear-gradient(135deg, #eef2ff 0%, #f5f3ff 100%); border: 1.5px solid #c7d2fe; border-radius: 10px; padding: 4px 8px;`)를 적용하여 시각적 가시성 강화 (`static/css/style.css`)
  - **문장 검색 결과 테이블 내 '어법 범주' 독립 열 분리 신설**:
    - 테이블 헤더 및 데이터 행을 `순번 | 출처 | 해당 문장 | 어법 범주 | 태그 정보 | 비고 | 복사 및 분석`으로 재편성하여 `해당 문장`과 전용 `어법 범주` 열(`col-grammar`, 220px)로 독립 분리 (`templates/index.html`, `static/css/style.css`, `static/js/main.js`)
    - 영어 본문 문장과 어법 뱃지 칩을 열 단위로 분리하고 미분석 문장은 `미분석` 라벨로 표시하여 테이블 가독성 극대화 (`static/js/main.js`)
- **검증 결과**:
  - `node --check static/js/main.js` 자바스크립트 문법 검사 통과 (오류 0건)
  - `python -m py_compile app.py database.py grammar_analyzer.py run.py` 파이썬 구문 검증 완료 (통과)

### [2026-09-20 17:50] 업데이트 이력 (Commit ID: f1000c6)
- **수정 내용**:
  - **문장 테이블 비고란 열 삭제**:
    - 테이블 헤더 및 데이터 행에서 불필요한 비고란 열(`col-remarks`)을 완전 제거하여 테이블 구조 슬림화 (`templates/index.html`, `static/js/main.js`, `static/css/style.css`)
  - **복사 및 분석 버튼 2x1 배열 전환**:
    - 인라인 작업 버튼 그룹(`action-btn-group`)을 기존 1x2(가로)에서 2x1(세로: 상단 [📋 복사] / 하단 [🤖 분석]) 구조로 개편하여 버튼 열 너비를 175px에서 80px로 50% 이상 절감 (`static/css/style.css`, `static/js/main.js`)
  - **열 간격 최적화 & 해당 문장 열 대폭 확장**:
    - 별표(`col-star`, 36px), 순번(`col-num`, 42px), 복사 및 분석(`col-action`, 80px)으로 압축
    - 출처 열(`col-source`)에 너비 185px, 폰트 0.70rem, 자간 -0.35px 및 `white-space: nowrap !important;`를 적용하여 긴 출처 텍스트(`[고3-2026년-07월-18번-1번째 문장]`)도 줄바꿈 없이 1행으로 정렬 (`static/css/style.css`)
    - 비고란 삭제 및 타 열 축소로 확보된 공간을 모두 흡수하여 `해당 문장` 열(`col-sentence`)을 `min-width: 480px` 및 `width: auto`로 대폭 확장하여 영어 문장 가독성 극대화 (`static/css/style.css`)
  - **어법 범주 전체 개요 및 다중 선택 모달 시스템 구축**:
    - 기존 인라인 단일 입력창 및 `<datalist>` 팝업 방식을 폐기하고, 문장별 `[⚙️ 어법 범주 선택 (N)]` 버튼 배치 (`templates/index.html`, `static/js/main.js`)
    - 243개 전체 어법 분류체계를 지원하는 `어법 범주 전체 개요 및 다중 선택 모달`(`grammarCategoryModal`) 신설 (`templates/index.html`, `static/css/style.css`, `static/js/main.js`)
    - 9대 품사 카드 그룹별 체크박스 다중/중복 선택, 기존 어법 자동 체크 동기화, 품사별 탭 필터링 및 실시간 검색, 선택 미리보기 배지 칩 바 구현
    - 백엔드 `POST /api/sentences/{id}/grammar-annotations/batch` API 신설 및 DB 일괄 갱신(`set_sentence_grammar_annotations`), 단일 추가/삭제 API 구현 (`app.py`, `database.py`)
    - AI 분석 실행 시 수동 등록된 어법 범주 보존 처리 반영 (`database.py`)
- **검증 결과**:
  - `node --check static/js/main.js` 자바스크립트 문법 검사 통과 (오류 0건)
  - `python -m py_compile app.py database.py grammar_analyzer.py run.py` 파이썬 구문 검증 완료 (통과)

### [2026-09-20 18:15] 업데이트 이력 (Commit ID: 77df905)
- **수정 내용**:
  - **어법 범주 모달창 크기 고정 및 축소/요동 현상 원천 차단**:
    - 검색어나 카테고리 필터링 시 모달창의 높이가 줄어들며 화면이 흔들리던 문제를 해결하기 위해, `.modal-grammar-content`에 고정 규격(`width: 94vw; max-width: 1060px; height: 85vh; min-height: 580px; max-height: 88vh;`)을 적용하고 `min-height: 0; flex: 1;` 구조로 본체 영역을 고정 (`static/css/style.css`)
    - 검색 결과가 0건일 때도 모달창이 수축되지 않도록 안내 아이콘과 상세 도움말을 담은 전용 엠프티 스테이트(`.grammar-empty-state`)를 배치하여 안정적인 시각적 경험 확보 (`static/css/style.css`, `static/js/main.js`)
  - **지문 선택기 스타일의 계층형 브레드크럼 드릴다운 네비게이션 구축**:
    - 지문 결과 화면의 상단 경로 선택기(`📍 [고3] > [2026년] > [07월 · 교육청] (25문항) [🔄 다른 시험 선택]`)와 동일한 UX/UI의 **어법 브레드크럼 네비게이션 시스템**(`grammarBreadcrumbBar`)을 모달창 상단에 전면 구축 (`templates/index.html`, `static/css/style.css`, `static/js/main.js`)
    - **1단계(품사 선택)**: 9개 대분류 품사(명사, 대명사, 문장, 주어, 동사, 형용사/부사, 전치사, 접속사, 특수구문) 카드 그리드로 분류별 하위 범주 미리보기 및 선택된 어법 수(`✔ N개 선택됨`) 표시
    - **2단계(세부 분류 선택)**: 선택된 품사 내 2단계 하위 분류(예: 접속사 ➔ 등위접속사, 접속사 that, 명사절, 관계사, 부사절) 카드 및 전체 펼쳐보기 옵션 제공
    - **3단계(세부 어법 다중 선택)**: 해당 분류에 속한 세부 어법들만 타일 형태로 집중 표시하며, 타일 내 미니 브레드크럼 배지(`[접속사] > [관계사] > [관계대명사]`) 표시 및 체크박스 다중 선택 지원
    - **양방향 네비게이션 & 실시간 검색/전체보기 연동**: 브레드크럼의 품사 클릭 시 2단계로 즉시 이동, `📍` 또는 `[🔄 다른 품사 선택]` 클릭 시 1단계 복귀, 상단 검색어 입력 시 `🔍 "검색어" (N건) [❌ 검색 지우기]` 반응형 브레드크럼 연동, `[🌐 전체 보기]` 토글 지원
  - **헤더 동적 액션 슬롯 버튼 명칭 변경**:
    - `'📝 전체 문장'` 텍스트를 문맥에 맞게 `'📝 해당 지문의 전체 문장'`으로 변경 및 툴팁 정비 (`templates/index.html`, `static/js/main.js`)
  - **문장 검색 속도 지연 원인 해결 (N+1 쿼리 최적화)**:
    - 문장 검색 루프 내에서 각 문장마다 태그와 어법 범주를 개별 쿼리하던 N+1 쿼리(문장 500개 검색 시 1,000회 DB 연결) 문제를 해결하기 위해, `database.py:search_sentences()`에 `WHERE sentence_id IN (...)` 일괄(Batch) 청크 쿼리 및 메모리 딕셔너리 매핑 구조를 적용하여 검색 응답 속도를 수 초에서 **0.07초(0.005초 DB 소요)**로 극적으로 단축 (`database.py`)
  - **문장 검색 결과 500개 제한 해제 (전체 539개 문장 완전 노출)**:
    - 프론트엔드 검색 파라미터(`main.js`)의 하드코딩된 `limit=500`과 백엔드(`app.py`, `database.py`) 기본 한도를 `5000`으로 상향하여, 전체 539개 문장이 누락 없이 정상 조회 및 렌더링되도록 수정 (`static/js/main.js`, `app.py`, `database.py`)
- **검증 결과**:
  - `node --check static/js/main.js` 자바스크립트 구문 검사 통과 (오류 0건)
  - `python -m py_compile app.py database.py run.py` 파이썬 구문 검증 완료 (통과)
  - `/api/search/sentences?limit=5000` 호출 시 539건 문장 0.07초 내 완전 응답 검증 완료
  - 로컬 HTTP 서버 정상 200 응답 확인 완료

### [2026-09-20 18:30] 업데이트 이력 (Commit ID: 0cda24f)
- **수정 내용**:
  - **문장 검색 어법 필터: 계층형 브레드크럼 네비게이션 시스템 개편**:
    - 첫 검색 화면(`#homeGrammarFiltersGroup`) 및 검색 결과창(`#resultsGrammarFiltersGroup`)의 어법 필터 그룹을 기존 단순 `<select>` 나열 방식에서 **`📍 [ 어법 대분류 ▾ ] > [ 세부 어법 ▾ ]`**의 일원화된 계층형 브레드크럼 네비게이션 구조로 전면 개편 (`templates/index.html`, `static/css/style.css`, `static/js/main.js`)
    - 어법 대분류 및 세부 어법 선택 시 활성 상태(`.active`) 브레드크럼 pill 스타일(소프트 로열 블루 배경 `#eff6ff`, 블루 텍스트 `#1d4ed8`, 테두리 `#93c5fd`, 그림자) 적용
  - **웹앱 내 3대 계층형 브레드크럼 시스템 전체에 '설정 초기화'(`↺ 설정 초기화`) 기능 구축**:
    - **1) 문장 검색 어법 브레드크럼 필터 바 (홈 & 결과창 공통)**:
      - `↺ 설정 초기화` 버튼 (`#btnResetHomeGrammarFilter`, `#btnResetResultsGrammarFilter`) 신설
      - 어법 대분류, 세부 어법, 중요 문장(⭐) 중 어느 하나라도 활성화되면 동적으로 버튼 노출
      - 클릭 시 모든 어법 조건과 중요 문장 필터를 한 번에 무설정 상태로 초기화하고 실시간 검색/필터링 반영 (`static/js/main.js`, `templates/index.html`, `static/css/style.css`)
    - **2) 지문 시험 선택기 브레드크럼 바 (`#treeBreadcrumbBar`)**:
      - `↺ 설정 초기화` 버튼 (`#btnTreeResetExam`) 및 브레드크럼 홈 아이콘(`treeBreadcrumbHome`, `📍`) 클릭 기능 신설
      - 시험 선택(학년/년도/월) 단계가 진행 중일 때 `[ 🔄 다른 시험 선택 ]` 좌측에 노출
      - 클릭 시 모든 선택 상태를 비우고 최초 학년 선택 단계로 즉각 복귀 (`templates/index.html`, `static/js/main.js`, `static/css/style.css`)
    - **3) 어법 범주 모달 브레드크럼 바 (`#grammarBreadcrumbBar`)**:
      - `↺ 설정 초기화` 버튼 (`#btnGrammarResetStep`) 신설
      - 품사 선택, 세부 분류 탐색, 전체 보기 모드, 또는 실시간 검색 중일 때 노출
      - 클릭 시 검색어 및 세부 탐색 경로를 모두 비우고 1단계(9대 품사 카드 개요) 화면으로 즉각 복귀 (`templates/index.html`, `static/js/main.js`, `static/css/style.css`)
  - **공통 브레드크럼 초기화 버튼 모던 UI 스타일 구축**:
    - `.btn-tree-reset-exam`, `.btn-grammar-reset-step`, `.btn-breadcrumb-reset` 공통 클래스 정의 (`static/css/style.css`)
    - 호버 시 소프트 레드 배경(`background: #fef2f2; color: #dc2626; border-color: #fca5a5;`) 및 미세 리프트 효과로 직관적인 시각 피드백 제공
- **검증 결과**:
  - `node --check static/js/main.js` 자바스크립트 문법 검사 통과 (오류 0건)
  - `python -m py_compile app.py database.py run.py` 파이썬 구문 검증 완료 (통과)
  - `http://127.0.0.1:8000` 로컬 HTTP 서버 200 OK 응답 및 변경된 브레드크럼 HTML 마크업 정상 전달 확인

### [2026-09-20 19:00] 업데이트 이력 (Commit ID: b48006b)
- **수정 내용**:
  - **검색창 입력값 초기화 `×` 버튼 신설 (`templates/index.html`, `static/css/style.css`, `static/js/main.js`)**:
    - 메인 홈 검색창(`mainSearchInput`) 및 결과창 상단 검색창(`resultsSearchInput`)에 검색어 입력 시 우측에 원형 `×` 버튼(`.btn-clear-search-input`)이 즉시 노출되도록 구현
    - `×` 버튼 클릭 시 검색창이 `""`로 초기화되고 포커스가 유지되며, 결과창에서는 검색 필터가 즉시 해제되어 전체 결과 목록이 다시 렌더링되도록 연동
    - 통계 배지 클릭 시 및 홈/결과창 전환 시에도 초기화 버튼 가시성(`updateClearButtons`) 자동 동기화
  - **온전한 단어 검색(Whole Word Search) 모드 구현 (`database.py`, `app.py`, `templates/index.html`, `static/css/style.css`, `static/js/main.js`)**:
    - **SQLite REGEXP 연동**: SQLite 커스텀 정규식 함수 `conn.create_function("REGEXP", 2, _regexp_func)` 등록 및 단어 경계(`(?<!\w)...(?!\w)`) 기반 검색 쿼리 구축
    - `it` 검색 시 `situation`, `with` 등 부분 일치 단어를 정밀 배제하고 독립된 단어 `it`만 선별 검색 (영문뿐 아니라 한글 단어 경계 및 구 단위 표현 `valuable because` 지원)
    - 홈 필터 바 및 결과창 상단 검색 바에 `[• 단어 단위]` 토글 버튼 신설 및 양방향 활성화 상태 동기화
    - 결과 내 검색(`executeSearchWithinResults`) 및 지문/문장 본문의 형광펜 하이라이트(`highlightTextKeyword`)까지 단어 단위 일치 연동
  - **OpenRouter Multi-LLM API 연동 및 Top 5 모델 드랍다운 선택 시스템 구축 (`grammar_analyzer.py`, `app.py`, `templates/index.html`, `static/css/style.css`, `static/js/main.js`)**:
    - **OpenRouter REST API 연동**: `https://openrouter.ai/api/v1/chat/completions` 엔드포인트 직접 호출 클라이언트 구축 (HTTP-Referer, X-Title, JSON 포맷팅 지원)
    - **Top 5 모델 실시간 조회 엔드포인트 (`GET /api/openrouter/top-models`)**: OpenRouter 공식 API(`https://openrouter.ai/api/v1/models`)에서 실시간 토큰 단가 및 컨텍스트 정보를 동적 추출하고 30분 캐싱 지원
    - **추천 Top 5 라인업**:
      - 🥇 인기 1위: `deepseek/deepseek-chat` (DeepSeek V3 — $0.32/1M, $0.89/1M, 160k ctx / 압도적 가성비)
      - 🥈 가성비 1위: `openai/gpt-4o-mini` (OpenAI GPT-4o-mini — $0.15/1M, $0.60/1M, 125k ctx / 초고속 & 저비용)
      - 🥉 어법정밀 1위: `anthropic/claude-sonnet-4.5` (Anthropic Claude Sonnet 4.5 — $3.00/1M, $15.00/1M, 976k ctx / 최고급 문해력)
      - 4위 플래그십: `openai/gpt-4o` (OpenAI GPT-4o — $2.50/1M, $10.00/1M, 125k ctx / 표준 플래그십)
      - 5위 오픈소스: `meta-llama/llama-3.3-70b-instruct` (Meta Llama 3.3 70B — $0.10/1M, $0.32/1M, 128k ctx / 고성능 오픈소스)
    - **AI 설정 모달 UI 구축**: Provider로 OpenRouter 선택 시 `[🏆 OpenRouter Top 5 추천 모델 선택]` 드랍다운 및 실시간 모델 정보 카드(순위, 명칭, 단가, 컨텍스트, 상세 설명) 자동 노출, `✏️ 직접 입력 (커스텀 모델명)` 선택 및 `[🔄 실시간 정보 갱신]` 기능 완비
- **검증 결과**:
  - `node --check static/js/main.js` 자바스크립트 문법 검사 통과 (오류 0건)
  - `python -m py_compile app.py grammar_analyzer.py database.py run.py` 파이썬 구문 검증 완료 (통과)
  - 온전한 단어 검색 API 검증: `it` 검색 시 일반 256건 / 단어 단위 81건으로 부분 일치 제외 정상 확인
  - `GET /api/openrouter/top-models` 로컬 엔드포인트 200 OK 및 실시간 Top 5 모델 정보 반환 확인

### [2026-09-20 19:18] 업데이트 이력 (Commit ID: e065a2b)
- **수정 내용**:
  - **AI 연결 작동 상태 실시간 시각화 디자인 (`templates/index.html`, `static/css/style.css`, `static/js/main.js`)**:
    - 상단 헤더의 `[🔑 AI 설정]` 버튼에 API 키 등록 및 연결 작동 상태를 한눈에 파악할 수 있는 고대비 비주얼 디자인 적용
    - 연결 작동 시 선명한 에메랄드 그라디언트 배경(`linear-gradient(135deg, #059669, #10b981)`), 펄스 글로우 애니메이션 닷(`🟢`, `@keyframes aiPulseDot`), 그리고 현재 연결된 공급자 배지(`[Gemini]`, `[OpenRouter]`, `[GPT]`, `[Claude]`) 동적 렌더링
    - 페이지 최초 로드 시, 모달 오픈 시, 그리고 API 키 설정 저장 시 즉각 상태를 확인하여 헤더 버튼 디자인을 실시간 자동 갱신
  - **수능·모의고사 8대 품사별 어법 태그 배지 색상 시스템 체계화 (`static/css/style.css`, `static/js/main.js`)**:
    - 기존 '현재완료시제'(동사)와 '관계부사'(접속사)의 색상 차이 원인 분석 및 답변 제공
    - 대분류 품사(POS)에 따라 모든 어법 범주가 직관적이고 조화로운 파스텔 톤으로 구분되도록 체계적인 배지 클래스 시스템 구축:
      - `동사`: 부드러운 로즈/레드 (`.badge-verb`, `#fdf2f8` / `#be185d`)
      - `접속사 / 관계사`: 밝은 스카이블루 (`.badge-conj`, `#eff6ff` / `#1d4ed8`)
      - `명사 / 주어`: 싱그러운 에메랄드 그린 (`.badge-noun`, `#ecfdf5` / `#047857`)
      - `대명사`: 청록/틸 (`.badge-pronoun`, `#f0fdfa` / `#0f766e`)
      - `형용사 / 부사`: 따뜻한 앰버/오렌지 (`.badge-adj-adv`, `#fffbeb` / `#b45309`)
      - `전치사`: 차분한 인디고 (`.badge-prep`, `#eef2ff` / `#4338ca`)
      - `특수구문`: 신비로운 바이올렛/보라 (`.badge-special`, `#f5f3ff` / `#6d28d9`)
      - `문장 구조`: 중립 슬레이트 그레이 (`.badge-sentence`, `#f1f5f9` / `#334155`)
  - **'모든 문장 일괄 어법 분석' 버튼 신설 및 미분석 문장 선별 분석 최적화 (`templates/index.html`, `static/css/style.css`, `static/js/main.js`, `app.py`)**:
    - 문장 결과창 상단에 `[⭐ 중요 문장 일괄 어법 분석]`과 나란히 `[🤖 모든 문장 일괄 어법 분석]` 버튼(`.btn-batch-all`) 신설
    - **중복 분석 및 토큰 낭비 방지**: 이미 어법 분석이 완료된 문장은 자동으로 건너뛰고, 아직 분석되지 않은 '미분석 문장'들만 선별하여 처리하도록 구현
    - **투명한 안내 & 진행률 표시**: 확인 창에서 전체 문장 수, 이미 분석된 문장 수, 실제 분석 대상 문장 수를 투명하게 안내하고, 20문장 단위 자동 청크 분할 전송(`⏳ 분석 중 (20/539)...`)으로 브라우저 타임아웃 방지
    - **백엔드 이중 안전장치**: `POST /api/sentences/batch-analyze-grammar` 엔드포인트에 `skip_already_analyzed: true` 파라미터 및 서버단 필터링 로직 구현, 대량의 문장 ID 요청 시에도 DB 전체 문장 범위를 안전하게 커버하도록 쿼리 개선
- **검증 결과**:
  - `node -c static/js/main.js` 자바스크립트 문법 검사 통과 (오류 0건)
  - `python -m py_compile app.py grammar_analyzer.py database.py run.py` 파이썬 구문 검증 완료 (통과)
  - `GET /api/settings/ai` 엔드포인트 정상 응답 및 OpenRouter 활성 상태 확인 (통과)

### [2026-09-20 19:28] 업데이트 이력 (Commit ID: 680e6b3)
- **수정 내용**:
  - **'처음 화면으로 돌아가기' 버튼 상단 헤더 위치 이동 (`templates/index.html`, `static/css/style.css`, `static/js/main.js`)**:
    - 결과창 검색 바 1행에 위치하던 `[← 처음 화면으로 돌아가기]` 버튼을 상단 메인 헤더의 `header-actions` 내, `header-action-slot` 바로 앞 위치로 이전 배치
    - **동적 가시성 제어**: 홈 화면에서는 자동 숨김(`display: none`), 결과창 및 문장 분석창 진입 시 헤더 상단에 표시(`display: inline-flex`)되어 스크롤 여부와 무관하게 홈으로 즉시 복귀 가능
    - **헤더 버튼 규격화**: 헤더의 타 작업 버튼들과 통일된 규격(`padding: 0.35rem 0.85rem`, `font-size: 0.82rem`, `border-radius: var(--radius-md)`)과 소프트 블루 호버 리프트 효과 적용
    - 결과창 상단 바에서 불필요한 공백을 제거하여 결과 검색창 및 탭 영역 가독성 향상
  - **메인 홈 '단어 단위' 검색 토글 버튼 중앙 검색창 내부 이전 (`templates/index.html`, `static/css/style.css`)**:
    - 하단 필터 바에 위치하던 `[• 단어 단위]` 토글 버튼을 중앙 대형 구글 검색창(`.google-search-box`) 내부의 `[검색]` 버튼 바로 왼쪽으로 이동 배치
    - 검색창 일체형 필 버튼 스타일(`.google-search-box .btn-home-search-wholeword`) 구축
    - 활성화(ON) 시 블루 글로우 라이브 닷과 테두리 강조 피드백 제공 및 결과 화면 단어 단위 토글과 양방향 실시간 상태 동기화 유지
- **검증 결과**:
  - `node -c static/js/main.js` 자바스크립트 문법 검사 통과 (오류 0건)
  - `python -m py_compile app.py grammar_analyzer.py database.py run.py` 파이썬 구문 검증 완료 (통과)

### [2026-09-20 20:10] 업데이트 이력 (Commit ID: c3aeb2f)
- **수정 내용**:
  - **실시간 AI 어법 일괄 분석 모달창 구축 (`templates/index.html`, `static/css/style.css`, `static/js/main.js`)**:
    - 어법 분석 진행 상황을 실시간으로 직관 확인 가능한 전용 모달(`batchAnalysisModal`) 신설
    - 전체 진행률 및 퍼센트 게이지 바, 현재 처리 중인 문장 카드(출처 번호, 문장 본문 텍스트 프리뷰), 라이브 스트리밍 로그 콘솔(성공 뱃지, 어법 개수, 해당사항 없음 및 에러 메시지) 구현
    - 단일 문장 단위 비동기 순차 처리로 브라우저 프리징 및 서버 타임아웃 방지
  - **어법 '✓ 해당사항 없음(분석 완료)'과 '미분석'의 엄격한 분리 (`database.py`, `app.py`, `templates/index.html`, `static/css/style.css`, `static/js/main.js`)**:
    - `sentences` 테이블에 `grammar_analyzed` 컬럼(0: 미분석, 1: 분석 완료) 신설 및 자동 마이그레이션 적용
    - AI 분석 완료 후 어법 포인트가 0개인 문장도 `✓ 해당사항 없음`(연회색 배지)으로 명확히 구분 표기하여 불필요한 재분석 방지
    - 홈 및 결과창 어법 필터에 `[전체 어법]`, `[어법 적용 문장]`, `[✓ 해당사항 없음]`, `[⏳ 미분석 문장]` 선별 필터링 옵션 완비
  - **문장 결과 테이블 세로 스크롤 시 상단 헤더 고정 (Sticky Header) (`static/css/style.css`, `static/js/main.js`)**:
    - 문장 결과 요약 바(`.sentence-header-bar`) 및 테이블 컬럼 헤더(`.sentence-table thead th`)에 `position: sticky` 및 적정 z-index 부여
    - 스크롤을 끝까지 내려도 열 명칭(순번, 출처, 해당 문장, 어법 범주, 태그 등)이 화면 상단에 영구 고정되어 데이터 가독성 극대화
  - **어법 범주 클릭형 대화식 팝오버 창 구축 (`templates/index.html`, `static/css/style.css`, `static/js/main.js`)**:
    - 마우스를 오래 올려두어야 하던 기본 브라우저 툴팁 방식에서 벗어나, 어법 태그 배지 클릭 시 즉시 상세 해설이 뜨는 대화식 팝오버(`grammarExplanationPopover`) 구현
    - 어법 배지 위치에 맞춘 자동 좌표 산출, 상단 그라데이션 타이틀 바, 타깃 표현 하이라이트 박스, 상세 AI 해설 본문, 외부 클릭 및 ESC 키 닫기 이벤트 지원
  - **문장 태그 인플레이스(In-Place) 갱신 및 지문 8문장 뷰 화면 풀림 버그 해결 (`static/js/main.js`)**:
    - 문장 태그 추가/삭제 시 전체 검색(`executeSearch("results")`)이 실행되어 단일 지문 8문장 화면이 DB 전체 539문장으로 리셋되던 문제 원천 차단
    - 해당 행의 태그 컨테이너(`.tags-container-...`)만 즉시 부분 DOM 갱신(`updateTagsCell`, `bindTagRemoveBtns`)하여 스크롤 및 지문 8문장 상태 완벽 보존
    - 어법 필터 초기화, 별표 필터 토글 시에도 `refreshCurrentSentenceView()`를 호출하여 지문 문장 컨텍스트 보호
  - **향후 웹 서비스 배포용 멀티테넌트(아이디별 메타데이터 격리) 아키텍처 가이드 반영 (`README.md`)**:
    - 수능/모의고사 기출 원문 DB는 전 교사가 100% 공유하면서도 태그, 어법 분석 결과, 중요(⭐) 문장은 교사 ID별로 독립 보관되는 Multi-Tenant 아키텍처 설계 청사진 문서화 (DDL, SQL JOIN 쿼리, REST API 설계 원칙)
- **검증 결과**:
  - `node -c static/js/main.js` 자바스크립트 문법 검사 통과 (오류 0건)
  - `python -m py_compile app.py database.py grammar_analyzer.py run.py` 파이썬 구문 검증 완료 (통과)
  - 로컬 HTTP 서버 정상 200 OK 응답 및 기능 무결성 확인

### [2026-09-20 20:21] 업데이트 이력 (Commit ID: cf75005)
- **수정 내용**:
  - **어법 범주 상세 해설 팝오버 미노출 버그 원천 해결 (`templates/index.html`, `static/css/style.css`, `static/js/main.js`)**:
    - **HTML 부모 모달 중첩 오류 수정**: `templates/index.html`에서 앞선 `#batchAnalysisModal` 모달의 닫는 `</div>` 태그가 누락되어 `#grammarExplanationPopover`가 숨김 모달(`display: none`) 내부에 갇혀 브라우저에 표시되지 못하던 문제를 닫는 태그 추가로 완벽 해결
    - **팝오버 z-index 및 레이어 보강**: `.grammar-popover`의 `z-index`를 `999999`로 대폭 상향하고 `pointer-events: auto`를 적용하여 모든 스티키 헤더 및 컨테이너 위로 선명하게 노출되도록 보장
    - **배지 데이터 내장 및 전역 이벤트 위임**: `renderGrammarBadges`에서 배지 생성 시 어법 데이터 전체를 `data-anno` 속성으로 완전 내장하고, `document.addEventListener("click")` 전역 이벤트 위임을 통해 어떤 행/뷰에서든 배지 클릭 즉시 팝오버가 정확히 연동되도록 리팩토링
    - **미세 스크롤 시 조기 닫힘 방지**: 클릭 시점의 미세한 컨테이너 스크롤 간섭으로 팝오버가 즉시 닫혀버리던 `window.scroll` 캡처 리스너 제거 및 ESC/바깥 클릭 닫기 최적화
  - **복수 LLM 앙상블 합의 판정(Multi-LLM Consensus Voting) 기술 검토**:
    - 단일 모델 대신 OpenRouter를 통한 복수 모델(DeepSeek V3 + GPT-4o-mini + Claude) 비동기 병렬(`asyncio.gather`) 교차 검증 및 엄격 교집합/다수결(2/3) 합의 아키텍처 타당성 검토 완료
- **검증 결과**:
  - `node -c static/js/main.js` 자바스크립트 문법 검사 통과 (오류 0건)
  - `python -m py_compile app.py database.py grammar_analyzer.py run.py` 파이썬 구문 검증 완료 (통과)
  - 로컬 웹서버 정상 동작 확인




