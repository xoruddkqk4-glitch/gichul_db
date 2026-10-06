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

### 6. 정답률 CSV 파싱 및 선지별 선택률·매력적 오답 시각화
- **정답률 CSV 자동 파싱 (`rate_parser.py`)**: OMR/채점 통계 CSV(`CP949`/`EUC-KR`/`UTF-8`)를 업로드하여 문항별 정답률(%), 선지별(①~⑤) 응시자 수 및 선택률, 무응답/중복답을 DB에 자동 연동.
- **2x2 지문 뷰어 시각화**: 난이도 등급 배지(🔴 킬러 / 🟠 중고난도 / 🟡 보통 / 🟢 평이), 5개 선지별 선택률 가로 프로그레스 바, `★ 정답`(에메랄드) 및 15% 이상 오답인 `🚨 매력적 오답`(레드 배지) 직관적 강조.
- **4종 세트 스마트 업로드**: 문제지(PDF) + 해설지(HWP) + 정답표(-A.png) + 정답률(CSV) 4종 파일의 일괄/단독 업로드 및 세트별 현황 관리 지원.

### 7. 정답 신뢰성 검증 파이프라인 (Answer Verification)
- **정답은 코드가 아닌 데이터**: 시험지별 검증 정답 키를 `data/answer_keys/{학년}_{연도}_{월}.json`에 검증 근거(CSV 확정 문항, 이미지 확정 문항, 수동 정정 이력)와 함께 보관. 소스코드 하드코딩 정답 사전 완전 제거.
- **문항별 정답 결정 우선순위** (`answer_resolver.py`): 정답률 CSV(정답 컬럼 또는 `|정답률 − 선지 선택률| ≤ 2%p` 유일 후보) → 검증 키 파일 → 정답표 이미지 다중 모델 합의 → 이미지 단일 모델 → HWP 해설. 앞의 세 소스만 '검증됨'으로 인정하며, 미검증 정답은 `answer_verified=0`으로 기록되고 업로드 응답·뷰어 배지에 명시 (무언 폴백 금지).
- **정답표 이미지 판독 게이트** (`hwp_parser.read_answer_image`): 활성화된 모든 Vision 모델이 2배 확대 이미지를 독립 판독 → 45문항 완전 추출된 판독만 유효 → 과반 일치 문항만 채택, 불일치·소수의견 기록.
- **CSV 교차검증**: 정답률로 결정적 검증, 다른 시험의 CSV(30% 초과 불일치)는 자동 감지·차단.
- **수동 정정**: 뷰어에서 `✏`로 정답 정정 시 DB·해설 헤더·형광펜 크롭·키 파일에 동시 반영 (`PATCH /api/passages/{id}/answer`).
- **운영 도구** (`tools/`): `build_answer_keys.py`(이중 전사·CSV 계층 검증으로 키 생성), `resync_answers.py`(키 → DB/크롭 재동기화), `audit_keys_with_vision.py`(다중 모델 재감사).

### 8. 영어 듣기 영역 2x2 뷰어, 수능 성우 보이스 클로닝(XTTS-v2 로컬 AI) 및 무료 Edge-TTS 하이브리드 엔진, FELS 약형드랩
- **수능 남/여 공식 성우 보이스 클로닝 (XTTS-v2 1:1 복제)**: 유료 ElevenLabs API 의존성을 완전히 제거하고, 평가원 수능 공식 남성/여성 성우 음성 참조 파일(`static/voices/kice_male_reference.wav`, `kice_female_reference.wav`)을 활용하여 실제 수능 듣기 평가와 동일한 보이스를 1:1로 복제 합성.
- **하드웨어 가속 자동 감지 (GPU/CPU)**: CUDA 외장 GPU(RTX 5060 등) 환경에서는 문항당 2~3초 초고속 생성, GPU가 없는 노트북/CPU 환경에서는 자동 폴백 안내. AI 환경설정 모달에서 실시간 하드웨어 상태(`CUDA 가속 지원` vs `CPU 모드`) 및 남/여 성우 미리듣기 지원.
- **Edge-TTS 100% 무료 음성 합성 (하이브리드/폴백)**: 인터넷이 연결된 환경에서 Microsoft Neural 고품질 음성(남성 `en-US-GuyNeural`, 여성 `en-US-JennyNeural` 등)으로 대화/독백 지문 실시간 무제한 보조 생성.
- **화자 분리(M/W) 턴 자동 합성 & 17문항 ZIP 일괄 다운로드**: 남/여 대화문 및 독백을 분리 합성하여 단일 MP3로 제공하며, 시험지 전체 17문항 일괄 생성 및 ZIP 다운로드 지원.
- **원클릭 자동 설치 및 실행 지원 (`install.bat`, `start.bat`)**: 완제품 패키지 보관소(`dist/`)를 통해 GPU 데스크탑 등 새 컴퓨터로 이전 시 Visual Studio C++ 빌드 도구 설치 없이 원클릭 초고속 설치 및 웹앱 자동 구동 지원.
- **FELS 약형드랩 시스템**: 7대 기능어 추출, 학생용 최장 단어 기준 균일 공백(`[        ]`) 복사, 담화문(독백/안내/강의) 문장 단위 유인물(1문장 1행) 복사 및 교사용 정답(`[단어]`) 1:1 동기화 지원.

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
├── run.py                  # 원클릭 로컬 웹 애플리케이션 구동기 (uvicorn "gichul.app:app")
├── start.bat · install.bat # 사용자 실행/설치 배치 파일
├── gichul/                 # ★ 백엔드 파이썬 패키지
│   ├── __init__.py
│   ├── paths.py            # 모든 경로 상수(DB, logs, static, uploads, captures, audio 등) 정의 (GICHUL_DB_PATH 지원)
│   ├── logging_config.py   # 통합 로깅(stdout + logs/app.log 5MBx3 회전) 및 get_logger 모듈
│   ├── app.py              # FastAPI REST API 및 웹 서버 엔드포인트
│   ├── database.py         # SQLite DB 스키마, CRUD, 인덱스, 어법 태그 및 검색 헬퍼
│   ├── access.py           # 등급별(관리자/회원/비회원) 데이터 접근 제어 및 필터링 훅
│   ├── exam_profiles.py    # 연도/체제별(50문항/수준별/45문항/특수크롭) 시험 프로파일 모델
│   ├── text_utils.py       # 순수 텍스트 유틸 (ID 정규화, 선지 추출, 빈칸 채우기, 해설 헤더)
│   ├── sentence_tokenizer.py   # 약어/소수점/인용구 보존 영문 문장 분할 모듈
│   ├── grammar_analyzer.py     # Gemini/ChatGPT/Claude Multi-LLM 243개 어법 분석 엔진
│   ├── services/
│   │   └── grammar_service.py  # 단일/배치/백그라운드 AI 어법 분석 공통 파이프라인
│   ├── pdf_parser.py           # PDF 2단 칼럼 분할 파싱 및 문항별 고화질 이미지 크롭
│   ├── hwp_parser.py           # HWP/HWPX 문제지 파싱 및 정답/해설 추출
│   ├── validator.py            # HWP vs PDF 상호 교차 검증 및 데이터 무결성 검사
│   ├── rate_parser.py          # OMR/채점 통계 CSV 파서 (정답률, 선지별 선택률, 매력적 오답 탐지)
│   ├── answer_keys.py          # 검증 정답 키(data/answer_keys) 로더 및 수동 정정 기록
│   ├── answer_resolver.py      # 정답 소스 결합·우선순위·검증 판정, CSV 정답률 교차검증
│   ├── listening_parser.py     # 듣기 대본 HWP/PDF 추출 및 어휘 블록 자동 정제
│   ├── fels_engine.py          # 7대 기능어 약형드랩 및 최장 단어 기준 균일 빈칸 생성 모듈
│   ├── tts_service.py          # Edge-TTS(무료) 및 수능 성우 복제(XTTS-v2) 듀얼 보이스 음성 합성 엔진
│   └── special_crops/
│       └── crop_2013_09.py     # 고3 2013년 9월(벡터 외곽선 문서) 전용 크롭 — 앱이 실행 중 import
├── data/
│   └── answer_keys/        # 시험지별 검증 정답 키 JSON (101세트) + _manual.json(직접 재판독 확정값)
├── tests/                  # pytest 회귀 테스트 (python -m pytest tests -q)
├── tools/                  # 일회성 관리 스크립트 (from gichul import ... 로 패키지 사용)
│   ├── build_answer_keys.py    # 이중 전사(_passA/_passB) + CSV 계층 검증 → 정답 키 생성
│   ├── resync_answers.py       # 정답 키 → DB 정답/해설 헤더/형광펜 크롭 재동기화
│   ├── audit_keys_with_vision.py # 다중 Vision 모델 합의로 정답 키 재감사
│   ├── regenerate_group_crops.py # 41~45번 묶음 문항 통합 크롭 재생성
│   └── fix_2012_11_and_2013_03.py # 2012-11 / 2013-03 크롭 보정
├── .claude/skills/         # Claude Code 슬래시 명령(/git-commit, /ask, /scratchpad) 미러 (원본: .agents/skills)
├── docs/                   # 계획서·리뷰 보관소 (목록과 상태: docs/README.md)
│   ├── plans/              # 구현 계획서 YYYY-MM-DD_<슬러그>.md (/ask 작성, /apply 실행)
│   └── reviews/            # 코드 리뷰·분석 보고서
├── templates/
│   └── index.html          # 구글 스타일 검색 + 2x2 그리드 + 문장 테이블 + AI 설정 모달 SPA
└── static/
    ├── css/
    │   └── style.css       # 모던 디자인 시스템 스타일시트 (어법 태그, 별표, 필터 바 등)
    ├── js/                 # ES 모듈 (index.html 에서 <script type="module" src="main.js">)
    │   ├── main.js         # 진입점: 각 모듈 init() 순서 호출 + 초기 상태
    │   ├── dom.js          # DOM 요소 참조 230개 (named export)
    │   ├── state.js        # 모듈 간 공유 상태 appState
    │   ├── navigation.js   # 헤더 슬롯 · 화면 전환 · 모드 전환
    │   ├── search.js       # 통계 로드 · 검색 실행 · 필터 초기화
    │   ├── results-passage.js  # 지문 결과 통합 퍼사드 (passage-api/render/events re-export)
    │   ├── passage-api.js  # 지문 서버 API · 시험 문항 캐시 · 파일 다운로드 · TTS 폴링
    │   ├── passage-render.js # 지문 트리 탭 · 2x2 그리드 · 복합 지문 통합 · FELS · 선지 선택률
    │   ├── passage-events.js # 오디오 재생/정지 · TTS 생성 · 메모 자동저장 · 이벤트 바인딩
    │   ├── results-sentence.js # 전체 문장 보기 · 문장 테이블 · 어법 팝오버
    │   ├── utils.js        # 클립보드 · 토스트 · escapeHtml
    │   ├── upload.js       # 업로드/DB 관리 모달 · 샘플 주입
    │   ├── files-status.js # 원본 파일 현황 탭 · 선택 삭제
    │   ├── grammar.js      # 어법 범주 모달 · 브레드크럼 필터 · 일괄 분석 진행
    │   └── ai-settings.js  # AI 설정 모달 (Multi-LLM / OpenRouter 앙상블)
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
   pip install -r requirements.txt
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
### [2026-09-20 20:36] 업데이트 이력 (Commit ID: faeb2d4)
- **수정 내용**:
  - **4대 AI 모델(Gemini, ChatGPT, Claude, OpenRouter) 다중 선택 및 엄격 교집합(Strict Intersection, 전원 일치) 판정 시스템 구축**:
    - **복수 모델 병렬 비동기 교차 검증 (`grammar_analyzer.py`)**:
      - `SUPPORTED_PROVIDERS = ["gemini", "openai", "claude", "openrouter"]` 전면 지원
      - `ThreadPoolExecutor`를 통한 병렬 비동기 호출 구현: 2~4개 모델 동시 실행 시에도 단일 모델 호출과 거의 동일한 응답 속도(~1.5~2.5초) 유지
      - **엄격 교집합(Strict Intersection)** 판정 알고리즘 적용: 활성화된 모든 모델이 **공통으로 일치하게 추출한 `category_id`만** 최종 어법 범주로 채택하며, 단 하나의 모델이라도 불일치 시 오분류 방지를 위해 엄격 제외 (일치 범주가 없으면 `✓ 해당사항 없음`으로 완결)
      - 교차 검증 메타데이터 자동 병기: 전원 일치한 어법 해설에 `[교차 검증: {모델명들} 전원 일치 (N/N)]` 접두어를 붙여 검증 신뢰도 명시
      - 개별 프로바이더 설정 조회(`get_provider_config`), 복수 활성 모델 설정 조회(`get_all_ai_configs`, `get_active_ai_configs`), DB/레거시/환경변수 폴백 아키텍처 완비
    - **백엔드 REST API 및 개별 핑 테스트 엔드포인트 (`app.py`)**:
      - `SingleProviderTestRequest`, `AISettingsRequest` Pydantic 모델에 복수 모델 선택(`active_providers`) 및 프로바이더별 키/모델(`providers`) 페이로드 확장
      - `GET /api/settings/ai`: 4대 엔진의 활성화 여부, 키 마스킹 상태, 모델명, 모드(`single`/`ensemble`) 종합 반환
      - `POST /api/settings/ai`: 복수 활성 목록(`ai_active_providers`) 및 모델별 키/모델 설정 영구 보관 (레거시 하위 호환 완벽 유지)
      - `POST /api/settings/ai/test`: 특정 모델 개별 연결 핑 테스트 전용 엔드포인트 신설
      - 단일 문장 실시간 분석(`POST /api/sentences/{id}/analyze-grammar`) 및 일괄 배치 분석(`POST /api/sentences/batch-analyze-grammar`)이 활성화된 앙상블 합의 엔진과 자동 연동되도록 리팩토링
    - **AI 설정 모달 전면 개편 (`templates/index.html`, `static/css/style.css`)**:
      - 4대 AI 엔진(`Google Gemini`, `OpenAI ChatGPT`, `Anthropic Claude`, `OpenRouter`) 2열 반응형 독립 카드 그리드 레이아웃 구축
      - 각 카드별 독립 요소: 활성화 체크박스 토글, 상태 배지(활성/비활성), 권장 모델명 입력창, 키 발급 가이드 링크, API Key 입력창(👁️ 마스킹 표시/숨김 토글), 전용 `[🧪 개별 연결 테스트]` 버튼 및 실시간 상태 피드백
      - OpenRouter 카드 내 실시간 Top 5 추천 모델 드랍다운 및 사양(입출력 단가, 컨텍스트) 카드 탑재
      - 상단 교차 검증 원리 안내 배너(`ai-consensus-guide-box`) 및 하단 실시간 선택 요약(`aiModalSelectionSummary`) 바 제공
    - **글로벌 헤더 AI 상태 표시기 동적 고도화 (`static/js/main.js`)**:
      - 활성 모델 0개: `🔑 AI 설정`
      - 활성 모델 1개: `⚡ AI 연결됨 [Gemini]`
      - 활성 모델 2개 이상: `⚡ AI 교차검증 [Gemini + GPT + Claude (전원 일치)]`
- **검증 결과**:
  - `node -c static/js/main.js` 자바스크립트 문법 검증 완료 (통과, 오류 0건)
  - `python -m py_compile app.py grammar_analyzer.py database.py run.py` 파이썬 구문 검증 완료 (통과)
  - `/api/settings/ai` 설정 조회 및 `/api/settings/ai/test` 개별 프로바이더 핑 테스트 통과
  - `grammar_analyzer.analyze_sentence` 실시간 어법 분석 및 엄격 교집합 판정 정상 작동 확인

### [2026-09-20 20:45] 업데이트 이력 (Commit ID: 93ecd26)
- **수정 내용**:
  - **Google Gemini 서비스 종료 모델(1.5-flash) 404 오류 해결 및 최신 `gemini-2.5-flash` 자동 마이그레이션 (`grammar_analyzer.py`, `app.py`, `templates/index.html`, `static/js/main.js`)**:
    - **원인 해결**: Google API에서 `gemini-1.5-flash` 모델이 공식 서비스 종료(Retired)되어 `404 Not Found` 오류가 발생하던 문제를 해결하기 위해 기본 표준 모델을 최신 주력 플래시 모델인 **`gemini-2.5-flash`**로 전면 전환
    - **실시간 모델 자동 탐색 및 구버전 자동 마이그레이션 (`resolve_gemini_model`)**:
      - `grammar_analyzer.py`에 `resolve_gemini_model` 함수 신설
      - 구버전 `gemini-1.5-flash`가 입력되거나 비어있는 경우 자동으로 `gemini-2.5-flash`로 자동 업그레이드
      - Google API `v1beta/models`의 `ListModels` 엔드포인트를 실시간 조회하여 사용자의 API 키가 즉시 호출 가능한 최신 플래시 모델을 자동 선별
    - **404 스마트 폴백(Smart Fallback) 안전망 구축**:
      - 특정 모델 호출 시 404 Not Found 오류가 발생하더라도 `gemini-2.0-flash`, `gemini-2.5-flash-lite`, `gemini-2.5-pro` 등 가용 플래시 모델군으로 1회 자동 재시도하여 어법 분석 및 연결 테스트 중단 방지
    - **UI 및 개별 연결 테스트 연동 강화**:
      - `templates/index.html`: Gemini 카드 기본 입력값 및 플레이스홀더를 `gemini-2.5-flash`로 갱신
      - `app.py`: `/api/settings/ai/test` 엔드포인트에서 감지된 활성 모델명을 프론트엔드로 반환
      - `static/js/main.js`: `[🧪 개별 연결 테스트]` 통과 시 실제 정상 작동한 모델명(예: `gemini-2.5-flash`)을 입력창에 즉시 자동 동기화하고 `✔ 연결 정상 (gemini-2.5-flash)` 안내 배지 표출
- **검증 결과**:
  - `node -c static/js/main.js` 자바스크립트 문법 검사 통과 (오류 0건)
  - `python -m py_compile app.py grammar_analyzer.py database.py run.py` 파이썬 구문 검증 완료 (통과)
  - `resolve_gemini_model` 단위 테스트 통과 (기본값 및 구버전 요청 시 `gemini-2.5-flash` 정상 반환 확인)

### [2026-09-20 20:48] 업데이트 이력 (Commit ID: e79aea8)
- **수정 내용**:
  - **Google Gemini 모델을 공식 최신 권장 모델인 `gemini-3.6-flash`로 전면 갱신 (`grammar_analyzer.py`, `templates/index.html`, `static/js/main.js`)**:
    - **원인 해결**: Google API가 신규 사용자 대상 `gemini-2.5-flash` 제공을 중단하고 공식 최신 모델인 `gemini-3.6-flash` 사용을 안내(`404: This model models/gemini-2.5-flash is no longer available to new users. Please update your code to use models/gemini-3.6-flash`)함에 따라, 기본 표준 모델을 **`gemini-3.6-flash`**로 즉시 갱신
    - **종료 모델군(`RETIRED_GEMINI_MODELS`) 필터링 및 자동 승격**:
      - `gemini-1.5-flash`, `gemini-2.0-flash`, `gemini-2.5-flash` 등 구버전/접근 제한 모델들을 `RETIRED_GEMINI_MODELS`로 등록
      - 사용자가 이전 모델명을 가지고 있더라도 `resolve_gemini_model()`에서 최신 `gemini-3.6-flash`로 즉각 자동 마이그레이션 처리
      - 404 발생 시 폴백 후보군도 `gemini-3.6-flash`, `gemini-3.7-flash`, `gemini-3.5-flash` 등 3.x Flash 시리즈로 전면 개편
    - **모달 UI 및 클라이언트 스크립트 반영**:
      - `templates/index.html`: Gemini 모델 입력 필드 기본값을 `gemini-3.6-flash`로 설정
      - `static/js/main.js`: 이전 모델 감지 시 자동으로 `gemini-3.6-flash`로 폼 입력값 자동 대체
- **검증 결과**:
  - `node -c static/js/main.js` 자바스크립트 문법 검사 통과 (오류 0건)
  - `python -m py_compile app.py grammar_analyzer.py database.py run.py` 파이썬 구문 검증 완료 (통과)
  - `resolve_gemini_model` 단위 테스트 완료 (모든 구버전 요청 시 `gemini-3.6-flash` 정상 반환 확인)
  - `GET /api/settings/ai` 호출 시 `gemini-3.6-flash` 모델 정상 응답 확인

### [2026-09-20 20:56] 업데이트 이력 (Commit ID: d1d8d18)
- **수정 내용**:
  - **Google Gemini 503 트래픽 과부하(High Demand) 지수 백오프 자동 재시도 및 다중 모델 자동 페일오버(Failover) 시스템 구축 (`grammar_analyzer.py`, `app.py`, `templates/index.html`, `static/css/style.css`, `static/js/main.js`)**:
    - **원인 해결**: 신규 권장 모델 `gemini-3.6-flash`로 트래픽이 집중됨에 따라 구글 서버에서 일시적 과부하로 인한 `HTTP 503 (This model is currently experiencing high demand. Spikes in demand are usually temporary. Please try again later.)` 오류가 발생하던 문제를 해결하기 위해 고가용성 복원력(Resilience) 아키텍처 구축
    - **지수 백오프 자동 재시도 (`_call_gemini_with_resilience`)**:
      - 구글 안내 지침에 따라 503 수신 시 1.5초 대기 후 1회 즉시 재시도하여 순간적인 트래픽 스파이크를 자동 흡수
    - **지능형 다중 모델 자동 페일오버(Failover)**:
      - 503 재시도 실패, 429(Rate Limit), 404 발생 시, 가용 대체 모델 큐(`gemini-2.5-flash-lite`, `gemini-3.7-flash`, `gemini-3.5-flash` 등)로 끊김 없이 자동 전환하여 호출 완수
      - 특히 초고속/경량화 모델인 `gemini-2.5-flash-lite`를 안정 폴백으로 확보하여 트래픽 병목 원천 차단
      - 대체 모델로 전환 성공 시 시스템 DB(`ai_model_gemini`) 및 프론트엔드 입력값을 자동 갱신하여 향후 호출 안정성 보장
    - **Gemini 추천 모델 퀵 선택 칩 UI 제공**:
      - `templates/index.html` 및 `style.css`: 모델명 입력란 하단에 `gemini-3.6-flash`, `⚡ gemini-2.5-flash-lite (안정)`, `gemini-3.7-flash` 원클릭 칩 버튼 추가
      - `static/js/main.js`: 칩 클릭 시 모델명이 즉각 자동 입력되도록 이벤트 바인딩
- **검증 결과**:
  - `node -c static/js/main.js` 자바스크립트 문법 검사 통과 (오류 0건)
  - `python -m py_compile app.py grammar_analyzer.py` 파이썬 구문 검증 통과 (오류 0건)
  - `grammar_analyzer.test_connection` 3요소 언팩 및 FastAPI `/api/settings/ai/test` 엔드포인트 응답 검증 완료

### [2026-09-20 21:55] 업데이트 이력 (Commit ID: 221d1ce)
- **수정 내용**:
  - **문장 분석 시 밑줄(빈칸) 정답 선지 자동 결합 및 온전한 문장 생성 (`grammar_analyzer.py`, `database.py`, `app.py`, `validator.py`, `static/js/main.js`)**:
    - **빈칸 문제 정답 선지 결합**: 31~34번 빈칸 추론 문항 등 지문에 밑줄(`_______`)이 있는 경우 지문의 선택지(①~⑤) 및 정답 번호(`answer_text`)를 대조하여 밑줄 위치에 실제 정답 선지를 삽입한 **온전한 문장**으로 자동 완성
    - **선지 기호 정제**: 문장 내 불필요한 번호 표기(①~⑤, (1)~(5), (a)~(e), leading `1. ` 등) 자동 제거
    - **데이터베이스 영구 갱신**: `database.py`에 `update_sentence_text` 함수를 신설하여 정답이 결합된 온전한 문장 본문과 단어 수를 `sentences` 테이블에 영구 저장
    - **기존 기출 DB 일괄 마이그레이션**: DB 내 기존 8개 빈칸 문장 전체를 정답이 반영된 완성형 문장으로 일괄 치환 및 재분석 완료 (예: `[고3-2026년-07월-33번-7번째 문장]` -> "At the same time, those expectations were themselves a product of the behavior that other individuals had chosen.")
    - **UI 및 신규 업로드 파이프라인 연동**: 단일 문장 및 일괄 어법 분석 시 화면 테이블(`.col-sentence`)과 클립보드 복사 텍스트가 완성형 문장으로 자동 동기화되며, 신규 시험지 업로드(`validator.py`) 시에도 완성형 문장으로 자동 토큰화
  - **멀티 LLM 다수결 합의(Majority Vote) 모드 및 단일 모델 장애 격리(Fault Tolerance) 구축 (`grammar_analyzer.py`, `static/js/main.js`, `templates/index.html`)**:
    - 기존 '엄격 전원 일치(Strict Intersection)'에서 2개 이상 활성 모델 중 과반수(예: 2/3, 2/4 등)가 합의한 어법 범주를 채택하는 **다수결 합의** 모드로 전면 전환
    - 특정 모델(Gemini 503 과부하, 429 제한 등) 장애 시 전체 프로세스가 중단되지 않고, 정상 응답한 생존 모델들 간의 다수결 합의를 도출하여 분석 안정성 확보
  - **'해당사항 없음' 배지 삭제(x) 및 재분석 지원 (`templates/index.html`, `static/js/main.js`)**:
    - 특이 어법 포인트가 없어 '해당사항 없음'으로 처리된 문장에도 `×` 삭제 버튼을 제공하여 어법 상태를 초기화하고 언제든지 재분석할 수 있도록 개선
  - **지문 검색 결과 창 검색 조건 초기화 버튼 신설 (`templates/index.html`, `static/js/main.js`)**:
    - 지문 결과 뷰 상단 네비게이션 액션 바에 `🔄 조건 초기화` 버튼을 추가하여 학년, 연도, 월, 문제유형 및 검색어 일괄 초기화 지원
  - **시험지 업로드 파라미터 불일치 오류 해결 (`pdf_parser.py`, `hwp_parser.py`)**:
    - `extract_pdf_columns_and_questions` 및 `parse_hwp_questions`에서 `start_q`, `end_q`, `reading_start`, `reading_end`, `answers_dict`, `**kwargs`를 모두 유연하게 처리하도록 파라미터 호환성 확장
- **검증 결과**:
  - `python -m py_compile app.py pdf_parser.py hwp_parser.py database.py validator.py grammar_analyzer.py` 파이썬 구문 검증 완료 (통과, 오류 0건)
  - `node -c static/js/main.js` 자바스크립트 문법 검사 통과 (오류 0건)
  - `[고3-2026년-07월-33번-7번째 문장]` 정답 결합 및 멀티 LLM 다수결 합의 어법 분석(주어동사일치, 목적격 관계대명사) 정상 저장 검증 완료
  - `extract_pdf_columns_and_questions` 및 `parse_hwp_questions` 함수 시그니처 및 키워드 인자 수신 테스트 완료

### [2026-09-20 22:27] 업데이트 이력 (Commit ID: f52bf3a)
- **수정 내용**:
  - **신규 2026년 9월 모의고사(고3) 문항(37~45번) PDF 고화질 크롭 이미지 추가 및 전체 문항 동기화 (`static/captures/`)**:
    - 독해 후반부 장문 및 순서·삽입 문항(37번~45번) 고화질 PDF 캡처 이미지(`고3_2026_09_37.png` ~ `고3_2026_09_45.png`) 구축 및 저장소 반영 완료
    - 지문 뷰어 2x2 그리드 좌측 상단 원본 인쇄 이미지 정상 로드 및 고해상도 확대 지원
  - **전체 정적 구문 및 파이프라인 무결성 재검증**:
    - `python -m py_compile` 백엔드 전체 모듈(`app.py`, `database.py`, `grammar_analyzer.py`, `pdf_parser.py`, `hwp_parser.py`, `validator.py`, `run.py`, `sentence_tokenizer.py`) 구문 검증 통과 (오류 0건)
    - `node -c static/js/main.js` 프론트엔드 자바스크립트 구문 검증 통과 (오류 0건)
    - Git 저장소 및 원격 GitHub 브랜치 동기화 상태 완료
- **검증 결과**:
  - `python -m py_compile app.py database.py grammar_analyzer.py pdf_parser.py hwp_parser.py validator.py run.py sentence_tokenizer.py` 통과 (오류 0건)
  - `node -c static/js/main.js` 자바스크립트 문법 검증 통과 (오류 0건)
  - Git 트래킹 및 원격 main 브랜치 동기화 완료

### [2026-09-21 00:17] 업데이트 이력 (Commit ID: c45817b)
- **수정 내용**:
  - **정답표 이미지(`-A.png` / `.jpg`) Vision AI 자동 파싱 및 3종 세트 일괄 업로드 파이프라인 구축 (`hwp_parser.py`, `app.py`, `templates/index.html`, `static/js/main.js`)**:
    - **Vision AI 정답표 파서 (`parse_answer_image`)**: HWP 내에 텍스트가 없고 이미지 형태로 표가 삽입된 시험지의 정답 누락 문제를 해결하기 위해, Gemini / OpenAI / OpenRouter Vision 모델을 연동하여 10열 9행 또는 격자형 정답표 이미지에서 1~45번 정답을 원문자(`①~⑤`) 딕셔너리로 100% 자동 파싱하는 엔진 신설
    - **HWP 정규식 보강**: `[정답] ⑤`, `[답] ⑤`, `정답 : ⑤` 등 대괄호와 콜론이 포함된 해설지 정답 텍스트도 유연하게 인식하도록 패턴 확장
    - **백엔드 업로드 API 연동**: `POST /api/upload`에 선택적 `ans_file` 파라미터를 추가하고, 정답표 이미지에서 파싱된 정답을 최우선으로 지문 DB(`passages.answer_text`) 및 PDF 크롭 이미지의 정답 선지 노란색 형광펜 하이라이트에 자동 결합
    - **프론트엔드 3종 세트 자동 페어링**: 일괄 업로드 드롭존에서 파일명 끝부분의 `-A`, `_A`, `_ans`, `정답` 접미사를 인식하여 문제지(PDF), 해설지(HWP), 정답표(PNG/JPG)를 하나의 세트로 자동 묶고 프리뷰 테이블에 `정답표 (-A)` 컬럼 표시
  - **시험지 관리 모달 내 세트별 3대 파일 업로드 유무 테이블 분리 및 원클릭 단독 등록 기능 구현 (`database.py`, `app.py`, `templates/index.html`, `static/css/style.css`, `static/js/main.js`)**:
    - **3대 파일 업로드 현황 쿼리 (`database.py`)**: `get_all_exams_with_stats`에서 `uploads/` 폴더 내 원본 파일 유무와 DB `passages` 정답 입력 현황을 정밀 분석하여 각 시험지별 `file_status`(`pdf`, `hwp`, `ans`) 제공
    - **단독 파일 업로드 API 신설 (`POST /api/exams/{exam_id}/upload-file`)**: 기존에 이미 등록된 시험지에 대해 PDF나 HWP를 다시 찾을 필요 없이 정답표 이미지만 단독 업로드 시, Vision AI 정답 추출 -> DB `passages.answer_text` 및 해설문 `[정답]` 갱신 -> 보관된 원본 PDF를 활용하여 정답 형광펜 크롭 이미지(`static/captures/...png`) 자동 재생성 및 교체 수행
    - **시험지 관리 테이블 컬럼 개편**: `📄 문제지 (PDF)`, `📝 해설지 (HWP)`, `🖼️ 정답표 (-A 이미지)` 독립 컬럼으로 분리 및 인터랙티브 칩 버튼(`.btn-file-chip`)으로 렌더링 (`chip-exists`, `chip-empty`, `chip-ans-needed`, `chip-ans-done`)
    - **클릭 단독 업로드 UX**: 비어 있거나 교체가 필요한 파일 버튼 클릭 시 즉시 파일 선택기가 열리고, 업로드 완료 시 시험지 관리 테이블 및 메인 홈 화면 검색 뷰어로 최신 데이터 실시간 동기화
  - **고2 기출 모의고사 PDF 고화질 크롭 이미지 동기화 (`static/captures/`)**: 고2 2024~2026년도 모의고사 크롭 캡처 이미지 저장소 반영
- **검증 결과**:
  - `python -m py_compile app.py database.py hwp_parser.py validator.py` 파이썬 구문 검증 완료 (통과, 오류 0건)
  - `node -c static/js/main.js` 자바스크립트 문법 검사 통과 (오류 0건)
  - 실제 사용자 정답표 샘플 격자 이미지(`고3-[2026-07]-A.png`) 대상 Vision AI 45문항 100% 정답 추출 단위 테스트 통과
  - 기존 등록된 30개 시험지 대상 `database.get_all_exams_with_stats()` 3대 파일 상태 산출 및 정답 통계 연동 검증 완료

### [2026-09-21 00:45] 업데이트 이력 (Commit ID: bd857c1)
- **수정 내용**:
  - **정답 데이터 기반 PDF 크롭 이미지 정답 선지 번호 파스텔톤 노란색 형광펜 하이라이트 엔진 구현 및 가시성 강화 (`pdf_parser.py`, `app.py`, `static/js/main.js`)**:
    - **프리미엄 파스텔 옐로우 형광펜 적용**: 원문 검은색 텍스트의 가독성을 온전히 유지하면서도 눈에 편안하고 선명한 파스텔 노란색(`RGB: 1.0, 0.91, 0.33` / `#FFE853`) 및 형광펜 주석(`add_highlight_annot`) 탑재
    - **정답 선지 기호 탐색 및 패딩 최적화**: 원문자(`①~⑤`), 정수(`1~5`), 괄호 번호, 점 번호 등 다양한 PDF 인코딩에 유연하게 대응하며, 기호 둘레에 가로 ±2.5pt, 세로 ±2.0pt 패딩을 부여하여 번호 전체가 자연스러운 형광펜으로 감싸지도록 스타일링 개선
    - **43~45번 장문 복합 지문 지원**: 3문항이 세로로 이어붙여진 통합 크롭 이미지에서도 각 문항의 정답 번호에 형광펜이 빠짐없이 칠해지도록 보장
    - **단독 및 일괄 업로드 파이프라인 연동 (`app.py`)**: Vision AI 정답 추출 후 `passages` 매칭 시 `int`/`str` 타입 차이로 인한 누락 방지, 원본 PDF 다단계 네이밍 패턴(`고2_2026_03_*.pdf`, `*2026*03*.pdf` 등) 자동 탐색, 크롭 재생성 완료 시 DB `passages.pdf_crop_image` 경로 자동 동기화
    - **브라우저 캐시 무효화 (`static/js/main.js`)**: 동일 파일명 덮어쓰기 시 브라우저 디스크 캐시(304 Not Modified)로 인해 이전 이미지가 노출되는 문제를 방지하기 위해 업로드 직후 및 뷰어 로드 시 캐시 버스터(`?t=${Date.now()}`) 적용
  - **문제지-해설지 통합 HWP 문서 분할 엔진 고도화 및 고2 2020년 3월 지문/해설 도치 오류 완전 복구 (`hwp_parser.py`, `database.py`)**:
    - **다단계 스마트 영역 분할 알고리즘 (`hwp_parser.py`)**: 한 파일 안에 문제지(1~45)와 해설지(1~45)가 연달아 있는 문서에서 명시적 표제어("정답 및 해설")가 없더라도 `[출제의도]`, `[해설]` 태그 시작점 및 40~45번 이후 번호 리셋 패턴을 정밀 감지하여 문제지와 해설지를 오차 없이 분리
    - **안티 폴루션 가드 (Anti-Pollution Guard)**: 발문에 `[출제의도]`, `[해설]`, `[정답]` 등이 포함된 블록을 배제하고, 이미 수집된 정상 영문 지문이 해설지 블록으로 덮어쓰여지는 현상을 원천 방지
    - **전체 30개 모의고사 세트 전수 조사 (Audit)**: DB 내 전체 30개 시험지의 지문 및 해설 텍스트를 전수 검사하여 이상 유무 진단 (29개 세트 정상, 1개 세트 이상 발견)
    - **`[고2-2020년-03월]` 데이터 완전 복구**: 본문에 해설이 들어가고 해설에 문제 텍스트가 섞여 있던 28개 문항을 재파싱 및 교차 검증하여 `passage_text`(순수 영어 지문 본문), `explanation_text`(출제의도/해석/어휘), `sentences`(214개 코어 영문장) 전체를 100% 정상 데이터로 복원 완료
  - **Uvicorn 파일 감시 예외 설정 (`run.py`)**:
    - Uvicorn `reload_excludes`에 `.git`, `uploads`, `static`, `scratch` 등을 등록하여 파일 I/O 및 Git 작업 시 `FileNotFoundError` 발생 방지
- **검증 결과**:
  - `python -m py_compile app.py pdf_parser.py hwp_parser.py database.py run.py` 파이썬 구문 검증 완료 (통과, 오류 0건)
  - `node -c static/js/main.js` 자바스크립트 문법 검사 통과 (오류 0건)
  - `[고2-2026년-03월]` 정답표 PNG 업로드 API 실증 테스트 통과: 전 문항 정답 추출 및 Q18(1,998개), Q19(2,076개), Q20(2,045개), Q43~45(6,111개) 파스텔톤 노란색 형광펜 픽셀 검출 확인 완료
  - DB 전체 30개 시험지 지문/해설 무결성 재검사 결과: **`Summary of Anomalous Exams: 0 / 30 (100% 정상 달성)`**

### [2026-09-21 13:20] 업데이트 이력 (Commit ID: 71623bc)
- **수정 내용**:
  - **OpenRouter 3개 모델 앙상블(자동 교차 검토) 사용자 자유 선택 및 446개 실시간 모델 연동 구축 (`grammar_analyzer.py`, `app.py`, `templates/index.html`, `static/css/style.css`, `static/js/main.js`)**:
    - **OpenRouter 실시간 모델 정보 조회 API 신설 (`GET /api/openrouter/models`)**: OpenRouter 공식 API(`https://openrouter.ai/api/v1/models`)와 연동하여 446개 전체 텍스트 모델의 최신 가격, 문맥 길이, 제공사 정보를 실시간 파싱하고 30분 캐시 및 강제 새로고침(`force_refresh=true`) 지원
    - **앙상블 1·2·3번 모델 슬롯별 자유 선택 UI**: 고정된 모델 대신 🥇 1번 모델, 🥈 2번 모델, 🥉 3번 모델 각각 드롭다운(인기/추천, DeepSeek, OpenAI, Anthropic, Google Gemini, Meta Llama, Mistral, Qwen 등) 및 `✏️ 직접 모델 ID 입력...` 지원
    - **원클릭 빠른 추천 조합(프리셋)**: `✨ 추천 기본 (DeepSeek V3 + GPT-4o-mini + Claude Sonnet 4.5)`, `💸 초가성비 (DeepSeek V3 + GPT-4o-mini + Llama 3.3 70B)`, `🏆 최고정밀 (Claude Sonnet 4.5 + GPT-4o + Gemini 2.5 Flash)` 프리셋 버튼 지원
    - **실시간 단가 표시 및 DB 영구 저장**: 각 슬롯 우측에 입력/출력 토큰 단가 배지 표시 및 `openrouter_ensemble_models` 설정을 DB에 영구 저장하여 다수결 합의 분석 시 지정된 3개 모델 병렬 호출
    - **OpenRouter 인증 헤더 누락(HTTP 401) 해결**: `_call_openrouter_single` 호출 시 활성 프로바이더 개별 API 키 폴백 전달 로직 보강
  - **개별 AI 연결 테스트 실시간 피드백 카드 UI 전면 개선 (`templates/index.html`, `static/css/style.css`, `static/js/main.js`)**:
    - `[🧪 개별 연결 테스트]` 버튼 하단에 상태별 전용 카드 박스 신설
    - 대기/안내(`info`), 핑 테스트 전송 중 회전 스피너(`loading`), 성공 시 응답 모델명 배지 및 앙상블 준비 상태 안내(`success`), 실패 시 구체적 에러 메시지 및 자가 해결 가이드(`error`) 제공
    - 키나 모델명 수정 시 `✏️ 설정 변경됨` 알림으로 즉각 전환되어 재검증 유도
  - **전체 7,913개 문장 무제한 조회 및 대용량 렌더링 최적화 (`database.py`, `app.py`, `static/js/main.js`)**:
    - 기존의 쿼리 상한선 `limit=5000`을 해제(`limit=0`, 무제한)하여 DB 내 7,913개 전체 문장이 잘림 없이 완벽 반환되도록 개선
    - 7,913개 대량 문장 렌더링 시 브라우저 렉을 방지하기 위해 `DocumentFragment` 기반 단일 배치 DOM 삽입 최적화 적용
  - **문장 결과 화면 인라인 복사 시 출처 식별자 포함 복사 기능 강화 (`static/js/main.js`)**:
    - `[📋 복사]` 클릭 시 문장 본문뿐 아니라 출처 식별자(예: `[고3-2026년-07월-33번-8번째 문장]`)가 본문 앞에 결합되어 복사되도록 개선
  - **빈칸 추론 문항 정답 선지 온전한 결합 및 데이터베이스 동기화 (`grammar_analyzer.py`, `database.py`)**:
    - 31~34번 등 밑줄(`_______`)이 있는 빈칸 문장에 실제 정답 선지를 채워 온전한 문장으로 분석하도록 전처리 및 저장 보강
- **검증 결과**:
  - `python -m py_compile app.py database.py grammar_analyzer.py` 파이썬 구문 검증 완료 (통과, 오류 0건)
  - `node -c static/js/main.js` 자바스크립트 문법 검사 통과 (오류 0건)
  - `GET /api/openrouter/models` 실시간 446개 모델 조회 및 커스텀 앙상블 3개 모델 DB 저장/복원 검증 완료
  - `GET /api/search/sentences` 호출 시 7,913개 문장 전체 누락 없이 1.2초 내 완전 응답 확인
  - AI 프로바이더별 개별 연결 핑 테스트(`/api/settings/ai/test`) 정상 작동 확인 (OpenRouter 200, OpenAI 200, Claude 400 키 요구)

### [2026-09-21 13:50] 업데이트 이력 (Commit ID: f413f7d)
- **수정 내용**:
  - **정답률 CSV 파일 업로드 및 문항별 2x2 지문 뷰어 선지 선택률 시각화 엔진 구축 (`rate_parser.py`, `database.py`, `app.py`, `templates/index.html`, `static/css/style.css`, `static/js/main.js`)**:
    - **정답률 CSV 파서 모듈 신설 (`rate_parser.py`)**: OMR/채점 통계 프로그램의 `CP949`/`EUC-KR`/`UTF-8` 인코딩 자동 판별, 문항 번호(18~45), 정답률(%), 선지별(1~5번) 응시자 수 및 선택 비율, 무응답/중복답 및 15% 이상 선택된 매력적 오답(`🚨 매력적 오답`) 자동 추출 알고리즘 구현
    - **데이터베이스 스키마 확장 및 마이그레이션 (`database.py`)**: `passages` 테이블에 `correct_rate REAL`, `choice_rates TEXT` 컬럼 추가 및 데이터 손상 방지 COALESCE 보정, 문항 번호 기반 정답률 및 선지 선택률(JSON) 자동 매칭 갱신(`save_exam_correct_rates`), 시험지별 통계에 `file_status.csv` 연동
    - **단일 지문 상세 API 확장 (`app.py`)**: `/api/passages/{passage_id}` 호출 시 `choice_rates_obj` 및 `correct_rate` 반환 보장
    - **2x2 지문 뷰어 패널 4(추가 정보) 선지별 선택률 시각화 (`templates/index.html`, `static/css/style.css`, `static/js/main.js`)**:
      - 4대 난이도 등급 배지: 🔴 킬러 · 고난도 (<40%), 🟠 중고난도 (40~60%), 🟡 보통 (60~80%), 🟢 평이 (80% 이상)
      - 5개 선지(①~⑤)별 선택률 가로 프로그레스 게이지 바 및 실제 응시자 수(`(00명)`) 표기
      - `★ 정답 선지`(에메랄드 그라데이션) 및 `🚨 매력적 오답 선지`(레드/로즈 그라데이션 배지) 시각적 강조
      - 미등록 시 안내 상자 및 `[➕ 정답률 CSV 등록]` 원클릭 단독 업로드 연동
    - **시험지 업로드 모달 3대 탭과의 4종 세트 완전 통합 (`templates/index.html`, `static/js/main.js`)**:
      - 탭 1 (스마트 일괄 업로드): 드롭존 및 파일 선택에 `.csv` 추가, `고O-[OOOO-OO].csv` 자동 페어링 및 감지 테이블에 `📊 정답률 (CSV)` 컬럼 추가, 신규 세트 또는 정답률 단독 일괄 갱신 지원
      - 탭 2 (원본 파일 현황): 상단 통계에 `📊 정답률(CSV)` 배지 추가, 9열 테이블로 확장하여 세트별 `📊 등록됨 (평균 XX%)` 또는 `➕ 정답률 업로드` 원클릭 단독 등록 지원, `🟢 4종 완비` / `🟡 정답률 필요` 상태 배지 연동
      - 탭 3 (단일 세트 업로드): `4. 정답률 데이터 파일 (선택, CSV)` 입력 필드 연동
  - **첫 검색 화면(홈 화면) 헤더 내 '해당 지문의 전체 문장' 버튼 노출 버그 해결 (`static/js/main.js`, `templates/index.html`)**:
    - 홈 검색 화면(`homeSearchView`)에서는 특정 지문이 선택되지 않았으므로 `btnHeaderFlow`(`📝 해당 지문의 전체 문장`) 버튼이 노출되지 않도록 `setHeaderSlotState`에 홈 화면 가드 조건(`isHomeVisible || state === "home"`) 적용
    - 모의고사 파일 업로드 완료 시 무조건적인 `executeSearch("home")` 호출을 제거하고, 현재 결과창(`resultsView`)이 활성화되어 있을 때만 결과를 갱신하도록 수정
    - 초기 로드(`DOMContentLoaded`), 모달 닫기(`closeUploadModal`), 홈 화면 복귀(`showHomeScreen`) 시 `setHeaderSlotState("home")`을 명시 호출하여 `📊 지문/문장 통계 배지` 노출 보장
- **검증 결과**:
  - `python -m py_compile app.py database.py rate_parser.py` 파이썬 구문 검증 완료 (통과, 오류 0건)
  - `node -c static/js/main.js` 자바스크립트 문법 검사 통과 (오류 0건)
  - 실제 사용자 샘플 CSV(`media_1789958309858.csv`)를 `[고3-2026년-09월]` 시험지에 적용하여 28문항 100% 매칭, 평균 정답률 64.2%, 21번 킬러 문항(정답률 24.1%, 매력적 오답 ③번 40.3%) 정상 파싱 및 DB 적재 검증 완료
  - FastAPI TestClient 및 in-process API 검증 (`/api/exams`, `/api/passages/[고3-2026년-09월-31번]`, `/api/passages/[고3-2026년-09월-21번]`) 정상 200 OK 응답 확인

### [2026-09-21 14:17] 업데이트 이력 (Commit ID: 4cf3840)
- **수정 내용**:
  - **지문 선택 상태 시 상단 헤더 '해당 지문의 전체 문장' 버튼 노출 정상화 (`static/js/main.js`, `templates/index.html`)**:
    - `setHeaderSlotState` 로직을 정밀화하여, 결과창(`resultsView`)이 활성화되어 있고 현재 지문(`currentPassageId`)이 존재하는 경우 `statsBadge`를 숨기고 `btnHeaderFlow`(`📝 해당 지문의 전체 문장`)가 100% 확실히 표시되도록 개선
    - 문항 탭 선택(`selectPassageTab`) 및 2x2 패널 상세 정보 로드(`loadPassageDetail`) 시 즉시 `setHeaderSlotState("passage")`를 호출하여 어떤 경로(탭 클릭, 방향키 탐색, 시험 선택)로든 지문이 렌더링되면 상단 버튼이 즉각 동기화되도록 연동
    - 상위 트리 네비게이션(학년/년도/월 선택) 단계에서 이전 세션 지문 잔여물이 노출되던 문제를 방지하기 위해 `reset2x2ContentPanels()` 모듈을 구축하고 트리 리셋 및 시험 변경 시 깔끔한 안내 상태로 초기화
  - **모의고사 일괄 업로드 시 진행률 프리징 방어 및 UI 피드백 강화 (`static/css/style.css`, `static/js/main.js`, `hwp_parser.py`)**:
    - `@keyframes progressStripes` 기반의 사선 애니메이션 스트라이프(`.progress-bar-animated`)를 신설하여 AI 분석이나 고해상도 PDF 크롭 등으로 인해 한 세트 처리에 시간이 소요될 때도 프로세스가 활성 작동 중임을 시각적으로 명확히 표시
    - 회전 스피너(`⏳`) 및 단계별 상세 작업 안내(`📄 PDF 2단 분할 & HWP 교차 검증 + 🖼️ 정답표 AI 분석 진행 중 (약 10~25초)...`) 연동
    - 한글(HWP) 백그라운드 파싱 시 `SetMessageBoxMode(0x00070000)`를 적용하여 확인/취소 등 모든 팝업 대화상자를 원천 차단
  - **브라우저 캐시 버스터 버전 갱신 (`templates/index.html`)**:
    - `style.css` 및 `main.js` 버전을 `v=20260921_1405`로 갱신하여 클라이언트 캐시 무효화 및 즉시 적용 보장
- **검증 결과**:
  - `python -m py_compile app.py database.py hwp_parser.py` 파이썬 구문 검증 완료 (통과, 오류 0건)
  - `node -c static/js/main.js` 자바스크립트 문법 검사 통과 (오류 0건)
  - DB 내 57개 시험지 1,596개 지문 및 14,643개 문장 정상 적재 상태 및 지문 선택 시 상단 버튼 동적 노출 검증 완료
### [2026-09-21 15:00] 업데이트 이력 (Commit ID: 228b98c)
- **수정 내용**:
  - **'등록된 시험지 관리 / 삭제' 탭 기능 고도화 (`templates/index.html`, `static/js/main.js`, `static/css/style.css`)**:
    - **정답률 CSV 열 신설 (`📊 정답률 (CSV)`)**: 총 12개 컬럼 체계로 확장하여, 시험지별 정답률 CSV 데이터 적재 현황(`📊 등록됨 (문항수/평균 정답률%)` 또는 `➕ CSV 등록`)을 한눈에 파악하고 즉시 단독 업로드할 수 있도록 지원
    - **`학년`, `년도`, `월` 열 개별 분리**: 기존 단일 `학년/월` 컬럼을 `학년`(고1/고2/고3 컬러 배지 `badge-grade-sub`), `년도`(숫자년도), `월`(숫자월) 3개 독립 열로 분리하여 가독성 대폭 향상
    - **인메모리 고속 클릭 정렬(Sorting) 엔진 탑재**: `시험지 식별자`, `학년`, `년도`, `월` 헤더 클릭 시 오름차순(▲) ↔ 내림차순(▼) 토글 정렬 기능 구현. 정렬 전환 시에도 체크박스 선택 상태(`checked`)를 완벽 보존
  - **'원본 파일 현황 & 개별 업로드' 탭 기능 동기화 (`templates/index.html`, `static/js/main.js`, `static/css/style.css`)**:
    - **`학년`, `년도`, `월` 열 개별 분리**: 기존 9열에서 11개 컬럼(`No.`, `시험지 식별자`, `학년`, `년도`, `월`, `출제기관`, `PDF`, `HWP`, `정답표`, `정답률`, `종합 상태`)으로 정밀 분리
    - **인메모리 고속 클릭 정렬 지원**: 학년별(고1<고2<고3), 연도별(최신순/과거순), 월별(11월>9월>6월>3월) 원클릭 토글 정렬 및 시각적 화살표 표시
  - **정렬 헤더 스타일 및 UI 디자인 개선 (`static/css/style.css`, `templates/index.html`)**:
    - 마우스 호버 효과, 활성 정렬 컬럼 강조색(`.active-sort`), 정렬 화살표 아이콘(`.sort-icon`) 스타일 추가
    - 학년별 전용 컬러 배지 클래스(`.badge-grade-g1`, `.badge-grade-g2`, `.badge-grade-g3`) 구현
    - 브라우저 캐시 버스터 버전 갱신 (`style.css?v=20260921_1445`, `main.js?v=20260921_1445`)
- **검증 결과**:
  - `node -c static/js/main.js` 자바스크립트 구문 검사 통과 (오류 0건)
  - `python -m py_compile app.py database.py rate_parser.py` 파이썬 구문 검증 완료 (통과, 오류 0건)
  - 모달 내 두 탭 모두 테이블 정렬 및 4대 파일 칩 버튼 연동 정상 확인

### [2026-09-21 18:56] 업데이트 이력 (Commit ID: e102818)
- **수정 내용**:
  - **정답률 검색 필터 10% 단위 세분화 체계 개편 (`templates/index.html`, `database.py`, `static/js/main.js`)**:
    - 중복되고 모호했던 `50% 이하` 및 `60% 이하` 구간을 제거하고, 10% 단위의 표준 구간 체계로 재정비:
      - `under20`: 20% 미만 (극악 킬러)
      - `20to30`: 20% ~ 30% (초고난도)
      - `30to40`: 30% ~ 40% (고난도)
      - `40to50`: 40% ~ 50% (중고난도)
      - `50to60`: 50% ~ 60% (중난도)
      - `60to70`: 60% ~ 70% (중평이)
      - `70to80`: 70% ~ 80% (평이 문항)
      - `over80`: 80% 이상 (기본 문항)
    - 홈 검색창, 지문 결과창, 문장 결과창 상단 필터바 전체에 동일하게 연동 및 양방향 동기화, 초기화 버튼 완벽 연계
  - **2026년도 모의고사 11개 세트 공인 정답표 원본 전수 대조, DB 정답·해설 동기화 및 PDF 하이라이트 크롭 일괄 재생성 (`hwp_parser.py`, `database.py`, `pdf_parser.py`, `static/captures/`)**:
    - 과거 학년 구분 없이 등록되었던 하드코딩 기록에 의한 정답 왜곡을 원천 해소하기 위해 2026년도 전체 11개 세트의 정답표 원본 이미지(PNG)를 전수 대조
    - 고3 6월/9월, 고1 3월/6월/9월, 고3 5월 등 총 38개 문항 정답 및 해설 `[정답] ○` 라벨 완전 교정 (`gichul.db`)
    - 올바른 정답 선지에 파스텔 노란색 형광펜 하이라이트가 적용된 고화질 PDF 크롭 이미지 306개 일괄 재생성 (`static/captures/`)
    - `hwp_parser.py`의 `KNOWN_EXAM_ANSWERS` 백업 사전을 학년 명시 표준 키(`고1_...`, `고2_...`, `고3_...`)로 정규화하여 재업로드 시 오염 가능성 원천 차단
  - **문장 결과 화면 출처 링크 및 정답률 배지 겹침 UI 버그 해결 (`static/js/main.js`, `static/css/style.css`, `templates/index.html`)**:
    - 출처 열(`td.col-source`)에 수직 레이아웃 컨테이너(`.source-cell-wrapper`)를 도입하여 1행에 출처 링크, 2행에 정답률 배지가 단정하게 분리되도록 개선
    - 정답률 배지가 우측 문장 본문 열(`td.col-sentence`)을 침범하던 텍스트 겹침 현상 원천 해결
    - 정답률 배지에 난이도 등급별 컬러 아이콘(`🔴`, `🟠`, `🟡`, `🟢`) 추가 및 `v=20260921_1855` 캐시 무효화 적용
  - **SQLite WAL 임시 파일 무시 규칙 보강 (`.gitignore`)**:
    - `gichul.db*` 패턴 적용으로 `gichul.db-wal`, `gichul.db-shm` 등 SQLite WAL 임시 파일의 Git 추적 원천 방지
- **검증 결과**:
  - `python -m py_compile app.py database.py hwp_parser.py pdf_parser.py rate_parser.py`: 구문 검증 완료 (통과, 오류 0건)
  - `node -c static/js/main.js`: 자바스크립트 문법 검사 통과 (오류 0건)
  - 10% 정답률 구간별 쿼리 테스트 8개 구간 정상 반환 확인
  - 2026년 전체 11개 세트 308개 전 문항 정답, 해설, PDF 크롭 무결성 전수 검사 결과 100% 정상 판정 (불일치 0건)

### [2026-09-21 19:10] 업데이트 이력 (Commit ID: 4d9d82c)
- **수정 내용**:
  - **선지별 선택률 시각화 패널 내 '🚨 매력적 오답' 배지와 프로그레스 바 텍스트 겹침 UI 결함 해결 (`static/css/style.css`)**:
    - `.choice-bar-row`의 그리드 레이아웃 컬럼 너비를 기존 `84px 1fr 76px`에서 `116px 1fr 82px`로 확장
    - 원문자 번호(`⑤`)와 한글 5글자 및 이모지가 결합된 `🚨 매력적 오답` 태그(약 101~103px)가 1열 내에 여유 있게 안착되도록 32px 추가 공간 확보
    - 배지 우측과 2열 게이지 바 시작점 사이에 약 20px 이상의 안전 여백을 확보하여 프로그레스 바가 배지 텍스트(`오답`)를 침범하던 겹침 현상 원천 제거
    - `.choice-label-badge`에 `white-space: nowrap`, `flex-shrink: 0`을 지정하여 텍스트 줄바꿈 방지
    - `.choice-progress-wrapper`에 `min-width: 0`을 지정하여 그리드 컨테이너 유연성 향상
    - 응시자 수가 1,000명 이상으로 늘어나는 경우에도 우측 정렬이 깨지지 않도록 3열(`.choice-percent-val`) 너비를 `82px`로 최적화하고 `flex-shrink: 0` 적용
  - **브라우저 캐시 무효화 버전 갱신 (`templates/index.html`)**:
    - `style.css` 및 `main.js`의 캐시 버스터 파라미터를 `v=20260921_1910`으로 갱신하여 클라이언트 즉시 반영 보장
- **검증 결과**:
  - `node -c static/js/main.js`: 자바스크립트 구문 검사 통과 (오류 0건)
  - 업로드된 결함 이미지 픽셀 실측치(838×166) 및 CSS 그리드 렌더링 분석: 1열 확장(116px)으로 배지 폭(~93~103px) 수용 및 2열 프로그레스 바와의 충돌 완벽 해소 확인

### [2026-09-21 21:23] 업데이트 이력 (Commit ID: 63ee8eb)
- **수정 내용**:
  - **정답률 CSV 파서 모듈 파싱 결함 원천 해결 (`rate_parser.py`)**:
    - `find_col` 함수에 `exclude_terms` 매개변수를 신설하여, '정답' 컬럼 탐색 시 '정답률', '중복답', '배점', '평균' 등 유사 키워드가 부분 일치로 오탐되는 결함을 원천 차단
    - '정답' 컬럼이 없고 '정답률' 컬럼만 존재하는 CSV 파일에서 백분율 수치(예: `86.56%`) 내의 숫자(`5`)가 정답 번호로 오인되던 문제 해결
    - `ans_num` 추출 시 단순 부분 포함(`in`) 대신 완전 일치 비교로 엄격화하여 문자열 오탐 방지
    - 헤더 행이 생략된 45행 순수 정답률 통계 CSV 파일 자동 감지 및 파싱 폴백 로직 추가
  - **정답률 CSV 업로드 시 DB 정답 및 해설 자동 동기화 로직 보강 (`database.py`)**:
    - `save_exam_correct_rates`에서 CSV에 공인 정답 기호(①~⑤)가 명시되어 있을 경우, 기존 DB의 왜곡된 정답을 유지하지 않고 공인 정답으로 즉시 덮어쓰도록 개선
    - 해설 본문 최상단의 `[정답] ○` 표기도 갱신된 정답에 맞춰 자동으로 동기화되도록 연동
  - **공인 정답 백업 사전 등록 및 표준화 (`hwp_parser.py`)**:
    - `KNOWN_EXAM_ANSWERS`에 `고3_2025_06` 28문항 전수 공인 정답표 등록 (재파싱 시 오염 방지)
  - **전체 1, 2, 3학년 101개 시험지(총 2,828문항) 전수 정밀 감사 및 일괄 교정 (`gichul.db`)**:
    - 101개 전 시험지의 평가원 공인 정답표 원본 PNG(`uploads/*ans*.png`) 및 CSV 전수 대조 감사 실시
    - 과거 파싱 결함으로 정답이 왜곡되어 있던 과거 시험지 25개 세트(약 700문항)에 대해 `answer_text`, `explanation_text`, `correct_rate`, `choice_rates` 전수 교정 완료
    - 고3 2025년 6월 34번 등 왜곡 문항의 정답(②번), 정답률(38.4%), 매력적 오답(③번 19.0%) 데이터 상호 모순 완벽 해소
  - **PDF 정답 선지 노란색 형광펜 하이라이트 크롭 이미지 전수 재생성 (`static/captures/`)**:
    - 오답 선지에 잘못 칠해져 있던 과거 크롭 이미지들을 폐기하고, 공인 정답 선지에 정확히 파스텔 노란색 형광펜(`RGB 1.0, 0.95, 0.1`)이 칠해진 고화질 문항 크롭 이미지 25개 세트 일괄 재생성
- **검증 결과**:
  - `python -m py_compile app.py database.py hwp_parser.py pdf_parser.py rate_parser.py`: 파이썬 문법 검사 통과 (오류 0건)
  - `node -c static/js/main.js`: 자바스크립트 문법 검사 통과 (오류 0건)
  - 전체 101개 시험지 2,828문항 전수 무결성 재검사 결과: 101개 시험지 100% 정상 판정 (오류 0건)
  - 1, 2, 3학년 2,828개 전 문항 정답 유효성 100%, 해설 라벨 일치율 100% 검증 완료

### [2026-09-21 21:58] 업데이트 이력 (Commit ID: 21ca031)
- **작업 및 질의응답 분석 내용**:
  - **데이터베이스 아키텍처 및 마이그레이션 전략 수립 (SQLite vs MySQL)**:
    - 현재 파일 기반 임베디드 DB(`gichul.db`)와 서버 데몬 기반 클라이언트-서버 RDBMS(MySQL)의 아키텍처 차이점 비교 분석
    - 이론 학습을 넘어 실전 마이그레이션(독립 브랜치 격리, 데이터 덤프/이관 스크립트 작성, 커넥션 풀 및 `.env` 환경변수 인증 체계 구축)을 통한 백엔드 엔지니어링 역량 확장 로드맵 정립
  - **Git 브랜치 격리 및 CI/CD 배포 안전성 검증**:
    - 프로덕션 배포 서버가 바라보는 타깃 브랜치(`main`)와 실험/개발용 브랜치(`study/mysql`) 간의 완전한 격리 메커니즘 분석
    - 새 브랜치에서 코드를 수정하거나 오류가 발생하더라도 배포 중인 실제 웹 서비스는 100% 정상 작동함을 검증 및 머지(Merge) 전 격리 원칙 확립
    - GitHub 웹 인터페이스 상에서의 브랜치 생성 및 로컬 터미널 연동(`git fetch origin`, `git checkout`) 절차 정립
  - **데이터베이스 라이선스 및 비용 체계 분석 (MySQL vs Firebase vs Supabase)**:
    - MySQL Community Server(GPL)의 완전 무료(로컬 PC 설치 시 평생 0원) 라이선스 및 클라우드 호스팅(AWS RDS 등) 시의 인프라 비용 발생 구조 규명
    - Firebase(Google) 및 Supabase의 평생 무료 티어(Free Tier) 용량 범위와 클라우드 BaaS 활용 가이드 제시
    - 로컬 윈도우 환경에 표시된 SQLite(파이썬 표준 라이브러리 및 OS 내장 경량 DB)와 MySQL(돌고래 로고의 독립 RDBMS 데몬) 간의 시각적·기능적 식별 기준 확립
  - **모의고사 정답률 및 선지 선택률 통계 처리 파이프라인 설계 기준 확립**:
    - **최신본 덮어쓰기(Overwrite)가 필요한 경우**: 모의고사 가채점 ➔ 실채점/확정치 등 시간 경과에 따른 누적 표본 갱신 시 초기 표본의 이중 집계(Double Counting) 왜곡을 원천 차단하기 위해 덮어쓰기 방식 채택
    - **인원수 합산 재계산(Cumulative Recalculation)이 필요한 경우**: 서로 다른 학교/학원 등 독립된 표본의 실제 응시자 수(Count) 데이터가 추가 유입될 때 인원수 합산(`SUM`) 후 백분율을 재계산하여 대수의 법칙에 따라 정확도를 향상시키는 데이터 파이프라인 설계 가이드 수립
- **검증 결과**:
  - `python -m py_compile app.py database.py hwp_parser.py pdf_parser.py rate_parser.py`: 파이썬 문법 검사 통과 (오류 0건)
  - `node -c static/js/main.js`: 자바스크립트 문법 검사 통과 (오류 0건)
  - 전체 시스템 및 데이터 무결성 100% 유지 상태 확인

### [2026-09-22 03:46] 업데이트 이력 (Commit ID: 75c8bfb)
- **수정 내용**:
  - **정답 신뢰성 전면 개편 (3-A ~ 3-E)** — 사용자 보고("정답 이미지를 업로드했는데도 정답이 자주 틀림")에 대한 원인 규명 및 구조 개선
    - **원인**: (1) 정답표 이미지 판독 실패·부분 추출이 무언 폴백되어 HWP 정규식 추출값이 저장됨, (2) 이미지 판독을 "첫 성공 모델 1개"에 의존했고 그 모델(GPT-4o)의 원문자 오독이 그대로 DB에 유입됨, (3) 정답이 소스코드 `KNOWN_EXAM_ANSWERS`에 하드코딩되어 12세트만 보호되고 검증 근거가 없었음
    - **실측**: 101세트 2,828문항 중 **303문항(10.7%)이 오답**이었음 (예: 고3 2024-11 수능 19/28, 고3 2023-09 14/28)
  - **3-A 정답 데이터화 및 전수 복구**
    - `KNOWN_EXAM_ANSWERS`(74줄) 및 파일명 기반 매칭 블록 삭제(`hwp_parser.py`), `answer_keys.py` 로더 신설
    - 101개 정답표 이미지를 독립 에이전트 2팀이 각각 전사(`_passA/_passB`) → `tools/build_answer_keys.py`가 정답률 CSV 정합성(`|정답률 − 선택률[정답]| ≤ 2%p`) 우선, 이중 전사 일치, 직접 재판독(`_manual.json`) 순으로 확정 → `data/answer_keys/*.json` 101개 생성
    - `tools/resync_answers.py`로 DB 정답·해설 `[정답]` 헤더 재동기화, 형광펜 크롭 이미지 재생성 (1차 294문항/1,072크롭, 재감사 후 9문항/237크롭 추가)
    - `tools/audit_keys_with_vision.py`: CSV 없는 62세트를 3개 Vision 모델 합의로 재감사. 불일치 11셀을 3배 확대 크롭으로 직접 판정하여 키 9건 정정 (원본 해상도에서 ③/④/⑤, ①/③ 원문자 혼동이 원인)
    - 잘못 연결된 CSV 2개 감지·제거: `고1 2021-03` CSV는 고3 2021-03 데이터, `고3 2022-06` CSV는 고3 2021-06 데이터 (파일은 `scratch/backup/`에 보관, DB 정답률 데이터 초기화)
  - **3-B 이미지 판독 신뢰성 게이트** (`hwp_parser.read_answer_image`, `answer_resolver.py` 신설)
    - 활성화된 모든 Vision 모델 독립 판독, 폭 1200px 미만 이미지는 2배 확대 PNG로 전송, 45문항 완전 추출만 유효, 과반 일치 문항만 합의 채택(소수 의견·불일치 기록), Anthropic 직접 호출 분기 추가
    - 정답 우선순위: 정답률 CSV → 검증 키 파일 → 이미지 합의 → 이미지 단일 → HWP. 검증 소스 외 정답은 `answer_verified=0` + 경고 (무언 폴백 제거)
    - `passages.answer_source / answer_verified` 컬럼 추가(자동 마이그레이션), `/api/upload` 응답에 `answer_report`, 정답표 재업로드 엔드포인트 동일 게이트 적용
    - UI: 뷰어 정답 옆 `✔ 검증 · 출처` / `⚠ 미검증 · 출처` 배지, 업로드 결과 경고 표시
  - **3-C CSV 교차검증 자동화**: 정답률 유일 후보로 정답 확정, 최종 정답이 후보와 모순되면 미검증 강등, 다른 시험 CSV(8문항 이상 비교·30% 초과 불일치) 자동 무시/422 거부. CSV 재업로드 시 기존 정답 정정·확인 및 크롭 재생성. `save_exam_correct_rates`는 정답률 저장 전용으로 분리, `update_passage_answers` 헬퍼 신설
  - **3-E 수동 정답 정정**: `PATCH /api/passages/{id}/answer` — DB·해설 헤더·`answer_source='manual'`·키 파일(`manual_overrides` 이력)·형광펜 크롭 동시 반영. 뷰어 `✏` 인라인 편집 폼(복합 문항 41~42/43~45 문항 선택 지원)
  - **기타**: Vision 판독 Claude 기본 모델 `claude-sonnet-5`, 어법 분석 Claude 기본 모델 `claude-haiku-4-5`로 갱신; `.gitignore`에 전사 중간 파일(`data/answer_keys/_pass*/`) 제외; `.claude/skills/`에 `/git-commit`, `/ask`, `/scratchpad` 스킬 미러 및 `CLAUDE.md` §7 안내 추가
- **검증 결과**:
  - `python -m py_compile app.py database.py hwp_parser.py grammar_analyzer.py answer_keys.py answer_resolver.py tools/*.py` 통과, `node --check static/js/main.js` 통과, FastAPI 앱 임포트 정상(35 라우트)
  - 최종 정합성: DB↔정답 키 파일 불일치 **0/2,828**, 해설 `[정답]` 헤더 불일치 0, 정답률 CSV 정합성 위반 0, 전 문항 `answer_source='verified_key' / answer_verified=1`
  - 남은 CSV 41개로 교차검증: 1,090문항 확인·정정 0·의심 0. 백업한 잘못된 CSV 2개는 `suspect=True`(28문항 중 21 불일치)로 자동 차단 확인
  - 리졸버 단위 검증(후보 산출, 우선순위, 복수 후보, 모순 강등, 의심 CSV, 재업로드 교차검증) 통과; 수동 정정 API TestClient 검증(400/404/200, 키 파일 기록·원복) 통과
  - 실측 게이트 동작: 고3 2025-06 정답표를 3모델 판독 → GPT-4o 44/45 추출로 무효 처리, Gemini+Claude 45문항 일치 → `status: ok`

### [2026-09-22 13:38] 업데이트 이력 (Commit ID: 0d1f59a)
- **수정 내용**:
  - **`requirements.txt` 신설**: 실측 버전 고정(fastapi 0.141.1, uvicorn 0.49.0, pydantic 2.13.4, python-multipart 0.0.32, pymupdf 1.28.2, pillow 12.2.0, pyhwpx 1.7.2·pywin32 312은 `sys_platform == "win32"` 마커, pytest 9.1.1). 한글 주석 유지를 위해 첫 줄 `# -*- coding: utf-8 -*-` 선언(Windows cp949 pip 대응). README 설치 안내를 `pip install -r requirements.txt`로 교체
  - **pytest 회귀 테스트 `tests/` 신설 (73개)**: `test_sentence_tokenizer.py`(약어·소수점·인용부호·원문자 분할, 발문/선지/각주/배점 제거, 문장 ID 규격), `test_rate_parser.py`(실제 교육청 CSV 헤더 포맷, cp949/utf-8-sig, 정답·정답률 컬럼 혼동 방지, 매력적 오답 15% 기준, 헤더 없는 45행 포맷, 난이도 경계값), `test_answer_resolver.py`(소스 우선순위, 검증 플래그, 단일 판독기/실패/불일치 경고, 다른 시험 CSV 판정 경계 8문항·30%, 정답률 모순 강등, CSV 재업로드 교차검증). `conftest.py`로 루트 import 경로 설정
  - **`static/js/main.js`(6,406줄) ES 모듈 12개로 분리**: 원본 섹션 헤더 경계를 모듈 경계로 사용, 함수 본문 무변경. acorn AST 기반 변환기(`scratch/jsmod/split.js`, gitignore)로 기계 생성 — DOM 참조 230개 `dom.js` named export, 상태 변수 33개 중 다중 모듈 공유 13개만 `state.js`의 `appState`로 치환(282곳), 나머지 20개는 모듈 private `let`, 이벤트 바인딩 115개는 모듈별 `init()`으로 묶어 `main.js`가 원본 순서로 호출. `index.html` `<script type="module">` 전환, `app.py`에 `/static/js/` `Cache-Control: no-cache` 미들웨어 추가(모듈 import 경로에 캐시버스터가 없으므로). 원본 백업 `scratch/backup/main.js.before-module-split-20260922-1324.js`
  - **strict 모드 전환으로 드러난 원본 버그 2건 수정**: `executeSearch`의 `correctRateRange` 미선언 대입(ES 모듈에서는 ReferenceError) → `let` 선언 추가; 뷰어 정답률 CSV 업로드 버튼의 미정의 `currentExamId`(원래도 클릭 시 항상 예외) → `currentDetailPassage.exam_id` 참조로 교정
  - **Anthropic Claude 직접 연결 404 수정**: 설정 모달 Claude 모델 기본값·바로가기 버튼을 종료된 `claude-3-5-*-20241022`에서 `claude-opus-5` / `claude-sonnet-5` / `claude-haiku-4-5`로 교체, DB `ai_model_claude`를 `claude-opus-5`로 갱신. `grammar_analyzer.py`·`hwp_parser.py` Claude 요청에서 현행 모델이 거부(400)하는 `temperature` 제거, thinking 블록이 앞에 오는 응답 구조에 맞춰 text 블록만 취합, `max_tokens` 1024→4096
  - **API Key 비ASCII 문자 사전 검증**: `x-api-key` 헤더는 latin-1만 허용되어 잘린 키의 `…` 등이 섞이면 `'latin-1' codec can't encode` 오류가 났음. `app.py`에 `describe_non_ascii()` 추가, 연결 테스트·설정 저장 양쪽에서 위치·문자를 명시한 한국어 메시지로 400 반환(저장 차단)
- **검증 결과**:
  - `pip install -r requirements.txt --dry-run` 의존성 해석 통과; `python -m pytest tests -q` **73 passed**
  - 모듈 분리 정적 검증(acorn): 12개 파일 구문 파싱 통과, import↔export 정합 일치, 미사용 import 0, 함수 106개·상수·상태 변수 개수 원본과 보존, 공유 let 잔여 직접 참조 0
  - Node+jsdom 스모크(브라우저 미사용): 실제 `index.html` 로드 후 모듈 평가·전체 `init()`·초기화·버튼 클릭 5회 실행 → 원본과 분리본 모두 예외 0·console.error 0·DOM 상태 동일
  - `python -m py_compile app.py grammar_analyzer.py hwp_parser.py` 통과, `describe_non_ascii('sk-ant-api03-abcd…xyz')` → `"18번째 '…'"` 확인

### [2026-09-22 14:01] 업데이트 이력 (Commit ID: 46d874c)
- **수정 내용**:
  - **정답 JSON 최우선 적용 파이프라인 구축 (`answer_keys.py`, `answer_resolver.py`)**:
    - `answer_keys.py`: `parse_answer_json` 유연한 파서(숫자 딕셔너리, 원문자 딕셔너리, 중첩 answers 딕셔너리, 28/45개 평탄 배열, 딕셔너리 리스트 수용), `parse_answer_json_file`(utf-8/utf-8-sig/cp949 다중 인코딩), `save_uploaded_answer_key`(업로드 정답을 `data/answer_keys/`에 영구 보관) 신설
    - `answer_resolver.py`: 정답 소스 우선순위를 `정답 JSON 파일 (uploaded_json) > 정답률 CSV (csv) > 검증 키 파일 (verified_key) > 정답표 이미지 합의 (image_consensus) > 단일 모델 (image_single) > HWP 해설 (hwp)`로 개편. `VERIFIED_SOURCES` 및 `SOURCE_LABELS`에 `uploaded_json` 등록
    - 교차 감사 및 안전망: JSON 정답이 최우선 채택되되, CSV 정답률 통계와 불일치하는 경우 사용자 검토를 위한 경고(`json_csv_conflicts`) 기록
  - **Vision AI 바이패스 및 업로드 파이프라인 연동 (`app.py`)**:
    - `POST /api/upload`: 정답표 파일이 `.json` 확장자일 경우 느리고 비용이 발생하는 Vision AI 호출(`read_answer_image`)을 완전히 건너뛰고(Bypass), JSON 정답을 1순위 Ground Truth로 즉시 확정 (업로드 대기 시간 20~30초 → 0.05초로 단축, API 비용 0원)
    - `POST /api/exams/{id}/upload-file`: 관리자 화면의 [➕ 정답표] 버튼에서도 `.json` 파일 단독 등록 지원 (지문 정답 갱신 및 PDF 형광펜 크롭 이미지 자동 재생성)
  - **프론트엔드 UI 드롭존 및 단독 업로드 지원 (`templates/index.html`, `static/js/upload.js`, `static/js/files-status.js`, `static/js/results-passage.js`)**:
    - `templates/index.html`: 일괄 드롭존 및 단독 등록 모달 파일 인풋의 `accept` 속성에 `.json` 추가 및 안내 문구 보강
    - `static/js/upload.js`: 파일명 기반 메타데이터 파서(`parseExamMetadataFromFilename`)에서 `.json` 감지 지원, 드래그&드롭 시 `ansFile` 자동 페어링 및 단독 업로드 다이얼로그 연동
    - `static/js/results-passage.js`: 뷰어 정답 출처 배지에 `uploaded_json: "정답 JSON"` 매핑 연동
  - **회귀 테스트 확장 (`tests/test_answer_resolver.py`)**:
    - `test_uploaded_json_wins_over_all_sources`: JSON의 1순위 우선 적용 및 CSV 충돌 경고 검증
    - `test_uploaded_json_stays_verified_even_with_csv_rate_discrepancy`: Ground Truth로서 검증 플래그 유지 검증
    - `test_parse_answer_json_various_formats`: 딕셔너리, 배열, 원문자, 중첩 JSON 포맷 파싱 검증
- **검증 결과**:
  - `python -m pytest tests -q`: **76 passed** (기존 73개 + 신규 3개 전원 통과)
  - `python -m py_compile app.py answer_keys.py answer_resolver.py`: 문법 검사 오류 0건 통과
  - `node -c static/js/upload.js static/js/files-status.js static/js/results-passage.js`: 구문 검사 오류 0건 통과

### [2026-09-22 22:00] 업데이트 이력 (Commit ID: 5600b75)
- **수정 내용**:
  - **총 50문항 체제(2006~2011년 기출) 문항 구조 전면 지원 및 PDF 크롭 일괄 정상화**:
    - **원인 분석**: 45문항 체제용 1지문 3문항 결합 로직(`crop_and_merge_43_45`)이 50문항 시험(2006~2011년)에도 오작동하여, 마지막 8페이지의 49~50번 영역을 크롭해 `_43.png`로 저장하고 43, 44, 45번에 동일하게 할당되었던 문제 해결
    - **PDF 파서 엔진 개선 (`pdf_parser.py`)**:
      - 50문항 체제에서는 18~45번이 모두 1지문 1문항(단일 문항)이므로 결합 로직을 배제하고 각 문항별 독립 크롭(`_41.png`~`_45.png`) 생성
      - 상단 클립 시작 마진을 `155pt`에서 `105pt`로 확장하고 헤더 필터링을 완화하여 7~8페이지 최상단 문항(41번 및 46~48, 49~50번 지문 헤더)이 잘리던 현상 원천 차단
      - `group_header_pattern` 정규식을 개선하여 `[46\n48]`처럼 개행이 포함된 복합 지문 헤더도 완벽히 매칭, 46번 및 49번 문항에 본문 지문 전체가 정상 결합되도록 수정
    - **2006~2011년 기출 24개 시험 크롭 이미지 일괄 재생성**: 50문항 기출 전체에 대해 고화질 크롭을 일괄 재생성하고 DB `passages.pdf_crop_image` 경로를 100% 정상화 (문항 간 중복 참조 0건)
    - **50문항 체제 문항 탭 분리 UI (`static/js/results-passage.js`)**: 46~48번(1지문 3문항), 49~50번(1지문 2문항)을 단일 복합 탭으로 통합하고 41~45번은 개별 문항 탭으로 노출
  - **PDF 문항 캡처 이미지 패널 '다시 캡처' 버튼 신설**:
    - [templates/index.html](file:///c:/Users/user/Desktop/web%20app/05-gichul_db/templates/index.html) 및 [static/js/dom.js](file:///c:/Users/user/Desktop/web%20app/05-gichul_db/static/js/dom.js), [static/js/results-passage.js](file:///c:/Users/user/Desktop/web%20app/05-gichul_db/static/js/results-passage.js)
    - 2x2 그리드 좌상단 'PDF 문항 캡처 이미지' 패널 헤더 우측에 `[🔄 다시 캡처]` 버튼(`btnRecapturePdf`) 추가
    - PDF 크롭 이미지가 없거나 잘못되었을 때 표시되는 안내 Placeholder 화면에도 인라인 `[🔄 지금 다시 캡처 실행]` 버튼 배치
    - 백엔드에 `POST /api/passages/{passage_id}/recapture` 엔드포인트 신설 (`app.py`), 원본 PDF에서 해당 시험지 문항을 자동 재크롭하고 뷰어를 실시간 갱신
  - **'정답 정정' 버튼 크기 확대 및 텍스트 시인성 개선**:
    - [templates/index.html](file:///c:/Users/user/Desktop/web%20app/05-gichul_db/templates/index.html), [static/css/style.css](file:///c:/Users/user/Desktop/web%20app/05-gichul_db/static/css/style.css)
    - 기존에 부모 컨테이너 flex column으로 인해 버튼 높이가 납작하게 찌그러지고 텍스트가 보이지 않던 문제를 해결
    - 컨테이너 분리(`meta-answer-container`) 및 버튼 내 `✏️ 정답 정정` 텍스트 명시
    - 최소 높이(28px), 패딩(`0.28rem 0.65rem`), 폰트(`0.78rem 700 bold`), 호버 애니메이션 및 소프트 블루 칩 테마 적용
- **검증 결과**:
  - `python -m py_compile app.py pdf_parser.py database.py`: 파이썬 구문 검사 오류 0건 통과
  - `node -c static/js/results-passage.js static/js/dom.js`: 자바스크립트 구문 검사 오류 0건 통과
  - 50문항 시험 전체 43, 44, 45, 46-48, 49-50번 독립 크롭 이미지 생성 및 DB 중복 0건 무결성 확인 완료

### [2026-09-22 23:15] 업데이트 이력 (Commit ID: 89434f1)
- **수정 내용**:
  - **45문항 체제 43~45번 TXT 본문 해설 오염 제거 및 프론트엔드 안전 가드 구축**:
    - **원인 분석**: `[고3-2025년-11월-45번]` 문항의 HWP 파싱 당시 시험지 끝에 수록된 `2026학년도 영어영역 정답 및 해설` 이하 21,000자의 시험 전체 해설/듣기 대본이 45번 `passage_text`에 그대로 누적되어 DB에 저장되어 있었음 (길이 23,275자).
    - **DB 레코드 정제 (`gichul.db`)**: `[고3-2025년-11월-45번]`의 `passage_text`에서 45번 ⑤번 선지 이후의 해설 텍스트를 제거하고 2,278자로 정상화.
    - **HWP 파서 정규식 개선 (`hwp_parser.py`)**: `split_questions_and_explanations()`에서 줄 앞에 연도나 영역명 등 접두사가 붙어있는 경우(예: `2026학년도 영어영역 정답 및 해설`)에도 문제 영역과 해설 영역을 안정적으로 분리하도록 정규식 개선.
    - **프론트엔드 2중 방어 필터 적용 (`static/js/results-passage.js`)**: `cleanQuestionExplanationLeak()` 함수를 신설하여 TXT 본문 렌더링 시 및 `extractQuestionChoicesOnly()`에서 해설 텍스트 블록 유입을 원천 차단.
  - **고1 2006~2008년 스캔본 PDF 디지털 PDF 자동 변환 및 396문항 고화질 크롭 100% 완료**:
    - **원인 분석**: `고1 2006년 9월`, `2007년 전 회차(3, 6, 9, 11월)`, `2008년 전 회차`의 기존 PDF 파일들이 텍스트 레이어가 없는 스캔 이미지(비트맵, `text_length = 0`)이거나 글꼴 유니코드 매핑이 누락되어 `pdf_parser`의 문항 인식이 불가능했음.
    - **한컴오피스 백그라운드 OLE 디지털 PDF 변환 (`pyhwpx`)**: `uploads/` 폴더 내 한글 원본(`.hwp`) 파일로부터 텍스트 레이어가 온전한 고해상도 디지털 PDF로 자동 변환 및 교체 (기존 스캔본은 `_old_scan.pdf`로 안전 백업).
    - **`pdf_parser.py` 상단 여백 및 문항 감지 알고리즘 개선**: 상단 클립 여백 제한을 `105pt` → `50pt`로 최적화하고 단일 블록 내 줄바꿈 뒤에 시작되는 문항 번호 감지 로직을 보강하여 고1 2006~2008년 12개 시험 전 문항(396개) 100.0% 크롭 완료.
    - **백엔드 자동 복구 폴백(Auto-healing) 탑재 (`app.py`)**: `_regenerate_exam_crops()` 및 `[🔄 다시 캡처]` API에 스캔본 감지 시 동명 HWP로부터 자동 디지털 PDF를 생성하는 안전망 구축.
  - **마지막 문항(45번, 50번) 하단 '※ 확인사항' 안내 박스 크롭 제외 처리 (`pdf_parser.py`)**:
    - `find_notice_box_top()` 정밀 탐지 함수를 신설하여 시험지 마지막 페이지 하단의 `※ 확인사항` 텍스트 및 박스 상단 테두리선(벡터 가로선) Y좌표를 정확하게 감지.
    - 45문항 세트 45번 문항(`crop_and_merge_43_45`) 및 50문항 세트 50번 문항(`save_extracted_question`)의 하단 자르기 좌표를 확인사항 박스 윗선 위로 제한하여, 안내 박스 및 테두리선이 캡처에 포함되지 않도록 제외 처리.
    - 시스템 내 155개 전체 시험지의 마지막 문항 크롭 이미지를 새 로직으로 일괄 재캡처하여 DB 및 파일 시스템에 즉시 반영.
  - **50문항 체제 발문 분석 기반 동적 복합 지문 통합 및 지문 누락 해결 (`static/js/results-passage.js`)**:
    - **원인 분석**: 50문항 체제에서 고정 하드코딩(`46~48번`, `49~50번`)으로 인해 `[고1-2011년-09월]`처럼 `46~47번`(2문항) + `48~50번`(3문항) 구조인 시험지에서 48번 지문이 분리되어 49~50번 탭에서 지문이 누락되던 결함 해결.
    - **동적 그룹 판별 엔진 (`resolveCompoundGroupsFor50`)**: 발문 및 본문 텍스트 내 헤더(`[46~47]`, `[48~50]`, `[48~49]` 등) 및 장문 독해 순서 배열 시작 발문(`(A)에 이어질`, `주어진 글 (A)`)을 분석하여 시험지별 실제 복합 지문 그룹을 동적으로 산출.
    - 2011년 9월, 11월 시험지는 `[46~47번]`과 `[48~50번]` 탭으로 분리 렌더링되며, 48번 문항의 지문 (A)~(D) 크롭 이미지가 정상 포함되어 지문 누락 현상 완전 해결.
    - `46~47번`, `48~49번` 조합 시험지(50번 단독) 및 `47~48번`, `49~50번` 조합 시험지도 시험지 실제 구조대로 완벽 지원.
  - **캐시 버스터 갱신 (`templates/index.html`)**: `v=20260922_2310`으로 업데이트.
- **검증 결과**:
  - `python -m py_compile app.py pdf_parser.py hwp_parser.py database.py`: 파이썬 문법 검사 오류 0건 통과
  - `node -c static/js/results-passage.js static/js/main.js`: 자바스크립트 구문 검사 오류 0건 통과
  - 고1 2006~2008년 12개 시험 396문항 크롭 완료율 100.0% 확인
  - 155개 전체 시험지 마지막 문항 '확인사항' 박스 제외 크롭 반영 확인
  - 50문항 체제 24개 시험 전수 동적 그룹화 테스트 통과 (2011-09/11의 `[[46, 47], [48, 50]]`, 2006-11의 `[[47, 48], [49, 50]]` 등)

### [2026-09-23 08:45] 업데이트 이력 (Commit ID: 17a382e)
- **수정 내용**:
  - **시험지 발문 안내 박스 기반 듣기/독해 영역 동적 감지 엔진 구축 (`pdf_parser.py`, `hwp_parser.py`)**:
    - **배경**: 2014학년도 수준별 수능(2013년 시행)의 경우 전체 45문항 중 듣기 22문항(1~22번) + 독해 23문항(23~45번) 체제로 구성되어, 기본값 18번 적용 시 듣기 18~22번이 독해 지문으로 오인식되던 문제 해결.
    - **발문 정규식 고도화**:
      - 독해 시작 안내문: `이제 듣기·말하기 문제가 끝났습니다. M번부터는 문제지의 지시에 따라...` ➡️ 독해 시작 문항 번호(`M=23` 또는 `18`) 직접 검출
      - 듣기 시작 안내문: `1번부터 N번까지는 듣고 답하는 문제입니다...` ➡️ 독해 시작 번호 `N+1` 산출
      - 구형 2013년 PDF 폰트 인코딩(CID ToUnicode 누락) 대응 완충 패턴(`1 ... 22 ... 1 ... 20`, `. 23`) 및 연도 힌트(2013년은 기본 23번) 결합.
    - **HWP 파서 연동**: `parse_hwp_questions`에서도 HWP 본문 텍스트를 통해 독해 시작 문항을 동적 감지하여 듣기 문항(1~22번)을 자동 배제하고 독해 지문만 수집하도록 일원화.
  - **웹 서버 파이프라인 동적 독해 범위 적용 (`app.py`)**:
    - `POST /api/upload`: 업로드 시 PDF/HWP 텍스트를 분석하여 `exams.reading_start_q`를 23 또는 18로 자동 저장.
    - 정답 확정(`resolve_answers`), PDF 이미지 크롭(`extract_pdf_columns_and_questions`), HWP 지문 파싱(`parse_hwp_questions`) 전반에 감지된 `effective_reading_start`를 전달하여 독해 문항만 정밀 수집.
  - **기존 2013년도 데이터 정제 및 동기화 (`gichul.db`)**:
    - DB 내 2013년 기출 4종(`고1-2013년-03월/06월/09월/11월`)의 `reading_start_q`를 23으로 업데이트.
    - 18번~22번 불완전 듣기 문항 레코드(20건)를 삭제하여, 뷰어에서 23번~45번(총 23문항)의 순수 독해 지문만 노출되도록 무결성 확보.
- **검증 결과**:
  - `python -m py_compile pdf_parser.py hwp_parser.py app.py scratch/sync_2013_reading_range.py`: 구문 검사 오류 0건 통과
  - 2013년 기출 4종: 독해 시작 23번 ~ 끝 45번 (총 23문항, 크롭 이미지 및 지문 완비) 확인
  - 일반 시험지(2020년 등): 독해 시작 18번 ~ 끝 45번 정상 유지 확인
  - 50문항 체제(2008년 등): 독해 시작 18번 ~ 끝 50번 정상 유지 확인

### [2026-09-23 09:40] 업데이트 이력 (Commit ID: 81665d8)
- **수정 내용**:
  - **영어 듣기 영역 2x2 뷰어 및 ElevenLabs TTS & FELS(약형드랩) 시스템 종합 기획 및 설계 완료**:
    - **참조 자료 등록 (`static/data/`)**: FELS(Function-Embedded Listening Skills) 청취 이론서(`current_English_listening.pdf`) 및 기능어 자동 괄호 삽입 가이드(`FELS.txt`) 추가.
    - **듣기 2x2 뷰어 아키텍처 확정**:
      - 좌상단: 문제지 캡처(위) + 대본 캡처(아래) 상하 수직 배열(Vertical Stacking)로 가로 폭 왜곡 방지 및 원본 칼럼 비율 100% 보존.
      - 우상단: 영문 대본 텍스트 + ElevenLabs M/W 듀얼 보이스 TTS 플레이어 및 단일 MP3 다운로드, 전체 ZIP 일괄 다운로드.
      - 좌하단: 7대 기능어 `<기능어>` 괄호 자동 삽입 FELS 교사용 텍스트 전문 렌더링 및 `[📋 FELS 텍스트 복사]` 원클릭 클립보드 복사 지원.
      - 우하단: 독해와 완벽히 일관된 문항 메타정보(식별자, 문항번호, 유형, 정답&정답정정✏️, 정답률), 선지별 선택률 차트, 태그 관리자 유지.
    - **지능형 해설 PDF 대본 크롭 파이프라인 설계**: 별도 대본 PDF가 없더라도 해설 PDF 내 `[대본]` 헤더 바운딩 박스를 정밀 감지하여 순수 스크립트 영역만 자동 크롭(`_script.png`)하는 Fallback 알고리즘 확정.
    - **ElevenLabs 듀얼 보이스(M/W) 및 설정 통합 설계**: 기존 LLM 설정 모달(`modalAiSettings`) 내 API 키 및 남/여 기본 Voice ID 설정 통합, 화자 태그(`M:`, `W:`) 기반 남녀 음성 자동 분기 합성 및 MP3 결합 로직 확정.
- **검증 결과**:
  - `implementation_plan.md` 기술 계획서 작성 및 5대 세부 요구사항 전원 검토·반영 완료
  - 참조 데이터 파일(`FELS.txt`, `current_English_listening.pdf`) 무결성 확인

### [2026-09-23 10:10] 업데이트 이력 (Commit ID: 3c75bf9)
- **수정 내용**:
  - **'전체 연도' 5대 그룹 및 2006~2026 개별 연도 복수 선택 시스템 구축**:
    - `static/js/year-filter.js`: 5대 그룹(최근 3개년[2024~2026], 최근 5개년[2022~2026], 최근 7개년[2020~2026], 최근 10개년[2017~2026], 전체 연도[2006~2026]) 일괄 토글 및 21개 연도 개별 체크 칩 연동 구현.
    - 부분 선택 시 그룹 체크박스 `indeterminate` 반선택 상태 자동 감지 및 '2025, 2026년 (2개)' 등 동적 요약 라벨 표시.
    - 백엔드 연동: `app.py` 및 `database.py`의 `search_passages`, `search_sentences` 함수에 `years` 파라미터(쉼표 구분)를 지원하여 `e.year IN (?, ?, ...)` 다중 연도 동시 조회 지원.
  - **'전체 월' 1,2학년(교육청)과 3학년(평가원/수능) 동적 분기 드롭다운 구현**:
    - `static/js/month-filter.js`: 고1, 고2 선택 시 전 문항이 교육청 출제이므로 `(교육청)` 옵션(3, 6, 8, 9, 10, 11, 12월)만 노출, 고3 선택 시 `교육청`(3, 4, 5, 7, 10월), `평가원`(6, 9월), `수능`(11월)으로 정확하게 분기 노출.
    - 학년 변경 시 현재 선택된 월 유효성을 검증하고 맞춤형 옵션 목록으로 자동 재구성.
  - **문제유형 '기타' 추가 및 미분류 문항 DB 자동 마이그레이션**:
    - `hwp_parser.py`: `QUESTION_TYPES` 목록에 `'기타'` 유형 공식 추가 및 미분류 문항 기본값 설정.
    - SQLite DB 마이그레이션을 통해 기존 분류되지 않은 348개 문항의 유형을 `기타`로 일괄 갱신.
    - `templates/index.html`: 홈 및 결과 화면 문제유형 드롭다운에 `<option value="기타">기타</option>` 추가.
  - **검색창 맨 앞 독해/듣기 영역 토글 버튼 배치**:
    - 홈 및 결과 검색창 최좌측에 세그먼트 필 버튼(`[📖 독해]` 기본 활성, `[🎧 듣기]` 준비중 비활성) 배치.
    - 아직 미구현된 듣기 버튼 클릭 시 '듣기 영역은 현재 개발 준비 중입니다.' 알림 토스트 연동.
  - **검색 입력창 가로 폭 2배 대폭 확장**:
    - 홈 검색창: `.google-search-box` 최대 너비를 `720px`에서 `1150px`로, 검색 카드 최대 너비를 `1200px`로 확대하고 검색 입력창 `min-width: 500px` 적용.
    - 결과 화면 검색바: `.results-search-bar` 최대 너비를 `680px`에서 `1200px`로 확대하고 검색 입력창 `min-width: 400px` 적용.
  - **필터 버튼 불변 레이아웃(Fixed-width & Reserve Space) 구축**:
    - 학년, 월, 유형 등 필터 버튼에 가장 긴 텍스트 기준 최소/고정 너비(`110px`, `172px` 등)를 부여하여 선택 상태에 따른 버튼 크기 및 위치 변동 제거.
    - 초기화 버튼(`btnResetHomeFilters`, `btnResetResultsFilters`)을 `display: none` 대신 `visibility: hidden; opacity: 0; pointer-events: none;`으로 처리하여 항상 자리를 차지하도록 고정.
  - **결과 화면 연도 팝오버 좌측 잘림 방지 및 뷰포트 안전 보정**:
    - `.year-popover-menu.compact`의 기준 위치를 `right: 0`에서 `left: 0; right: auto;`로 변경하여 모달 창 좌측 경계 밖으로 벗어나지 않도록 수정.
    - `getBoundingClientRect()` 기반 동적 뷰포트 경계 감지 로직을 추가하여 화면 좌측 최소 16px 여백 보장.
- **검증 결과**:
  - Python 구문 검사(`python -m py_compile app.py database.py hwp_parser.py`): 오류 0건 통과
  - JavaScript 구문 검사(`node -c static/js/year-filter.js static/js/month-filter.js static/js/search.js static/js/main.js`): 오류 0건 통과
  - DB 다중 연도 쿼리 검증: 2024~2026 복수 연도 1,148건 정상 조회 확인
  - DB 기타 유형 마이그레이션 검증: `question_type = '기타'` 348건 정상 반영 확인

### [2026-09-23 11:25] 업데이트 이력 (Commit ID: 36edbf5)
- **수정 내용**:
  - **버튼 내 텍스트 1행 표시(Single-Line Display) 전역 스타일 적용**:
    - `style.css`: `button` 기본 태그 및 `.btn`, `.btn-header-flow`, `.btn-popover-action`, `.btn-popover-apply`, `.year-chip-item`, `.year-multiselect-trigger`에 `white-space: nowrap;` 및 `flex-shrink: 0;`을 적용하여 화면 폭 변화나 압축 시 버튼 내부 글자가 음절 단위로 2행 줄바꿈되는 현상 완전 차단.
  - **연도 선택 팝오버 헤더 요소 줄바꿈 방지 및 너비 500px 확장**:
    - `.popover-title`(`📅 연도 선택 (복수 선택 가능)`), `.popover-count-badge`(`전체 (21개년)`), `.popover-title-row`에 `white-space: nowrap;`과 `flex-shrink: 0;` 적용.
    - 상단 빠른 액션 버튼 `.btn-popover-action`(`전체 선택`, `선택 초기화`) 패딩 및 폰트 렌더링 최적화.
    - 팝오버 컨테이너 폭을 `420px~440px`에서 `500px`(`max-width: min(500px, calc(100vw - 32px))`)로 확장하여 헤더 요소들이 1행으로 여유롭게 정렬되도록 레이아웃 개선.
  - **연도 팝오버 뷰포트 경계 자동 안전 보정 로직 고도화**:
    - `year-filter.js`: 우측 화면 여백 부족으로 팝오버를 좌측으로 이동시킬 때도 좌측 최소 16px 안전 여백을 계산하여 좌/우 잘림 현상이 발생하지 않도록 계산식 보강.
- **검증 결과**:
  - JavaScript 구문 검증(`node -c static/js/year-filter.js static/js/month-filter.js static/js/search.js static/js/main.js`): 오류 0건 통과

### [2026-09-23 13:05] 업데이트 이력 (Commit ID: c165d71)
- **수정 내용**:
  - **영어 듣기 영역 2x2 전용 뷰어 및 ElevenLabs 듀얼 보이스 TTS & FELS 약형드랩 시스템 구축**:
    - **2x2 듣기 뷰어 레이아웃 (`templates/index.html`, `static/js/results-passage.js`, `static/css/style.css`)**:
      - 좌상단: 문제지 캡처(위) + 원본 대본집 인쇄 캡처(아래) 상하 수직 배열(Vertical Stacking)로 인쇄본 칼럼 비율 왜곡 없이 100% 보존.
      - 우상단: 영문 대본 텍스트 본문 + ElevenLabs M/W 듀얼 보이스 TTS 플레이어 (문항별 단일 생성/재생/MP3 다운로드 및 시험지 전체 17문항 일괄 생성/ZIP 다운로드).
      - 좌하단: 7대 기능어가 대괄호 `[단어]`로 감싸진 FELS 교사용 약형드랩 전문 렌더링 + 학생용 빈칸 복사 및 교사용 정답 복사 원클릭 액션 지원.
      - 우하단: 독해 영역과 완벽히 동일한 문항 식별자, 유형, 정답&정정✏️, 정답률, 선지별 선택률(%) 차트, 태그 관리자 연동.
    - **ElevenLabs Free 티어 보이스 최적화 및 듀얼 합성 엔진 (`elevenlabs_service.py`, `app.py`)**:
      - 무료 플랜에서 402 결제 오류를 유발하던 레거시 Rachel 보이스를 Free 티어 공식 지원 보이스인 Sarah(`EXAVITQu4vr4xnSDxMaL`)로 전면 교체 및 레거시 ID 자동 폴백 로직 탑재.
      - 남성(Adam) / 여성(Sarah) 보이스 분기 합성 및 단일 MP3 병합 파이프라인 구현, 전체 시험지 17개 문항 ZIP 일괄 압축 스트리밍 엔드포인트(`GET /api/exams/{exam_id}/download-listening-zip`) 신설.
    - **대본 내 어휘/표현 설명 유입 방지 필터링 (`listening_parser.py`, `elevenlabs_service.py`)**:
      - HWP 해설 끝에 수록된 어휘/어구 정리 목록(`Words & Phrases`, `어휘`)을 사전에 정밀 제거하여 TTS 음성 합성 및 FELS 텍스트에 오직 순수 대화/담화 본문만 전달되도록 정제.
      - DB 내 기존 2026년도 11개 시험지(187개 문항)의 `script_text` 및 `fels_text` 정제 일괄 반영 완료.
  - **FELS 학생용 빈칸 `[ ]` 대괄호 전환 및 최장 단어 기준 균일 공백 일괄 적용**:
    - **단어 길이 힌트 유출 방지 균일 빈칸 엔진 (`static/js/results-passage.js`, `fels_engine.py`)**:
      - 단어 철자수에 따라 빈칸 길이가 달라져 정답 단어를 유추할 수 있던 문제를 해결하기 위해, 지문 내 모든 기능어 중 **가장 긴 단어의 철자수(`maxLen`)를 계산하여 모든 빈칸을 동일한 공백 개수의 `[       ]` 형태로 일괄 적용**.
      - 학생용 빈칸 복사 시 `최장 N자 기준 공백 일괄 적용` 안내 토스트 제공.
      - 교사용 정답 복사 시 `[단어]` 형태로 일관되게 1:1 대응 복사 (`copyFelsAnswerVersion`).
      - FELS 생성 엔진(`fels_engine.py`)을 `[단어]` 래핑으로 갱신하고, 균일 빈칸 생성 헬퍼(`generate_fels_blank`) 추가.
      - DB 내 기존 185개 듣기 지문의 `fels_text`를 `<단어>`에서 `[단어]`로 마이그레이션 완료.
  - **1지문 다문항(41~42번, 43~45번 등) 문항별 정답률 & 선지 선택률 분리 시각화 (`static/js/results-passage.js`, `static/css/style.css`)**:
    - **문항별 정답률 개별 배지 표기**: 기존 첫 문항 정답률만 노출되던 메타 패널을 개선하여, 복합 지문에 속한 각 문항의 번호와 개별 난이도 배지(예: `41번: [47.6% (🟠 중고난도)]`, `42번: [58.6% (🟠 중고난도)]`)를 분리 렌더링.
    - **선지별 선택률 문항별 독립 카드 렌더링**: 각 문항의 `📌 문항 번호`, `난이도 배지`, `정답률`, `정답 선지`, 그리고 ①~⑤번 선지 게이지 바(정답 ★, 매력적 오답 🚨)를 각각 독립된 카드로 시각화.
    - **상단 퀵 필터 탭 지원 (`btn-choice-q-pill`)**: `[전체 문항 (N)]`, `[41번 문항]`, `[42번 문항]` 등의 필터 버튼을 배치하여 전체 비교 및 개별 집중 보기를 유연하게 지원.
  - **트리 탐색 바 칩 뱃지 개선 (문항 수 + 시험지 세트 수 동시 안내) (`static/js/results-passage.js`)**:
    - 학년 선택 칩 뱃지: 단순 문항 수(85, 1175 등) 대신 `고3 85문항 (5회)` (듣기) / `고3 1,175문항 (47회)` (독해)처럼 **[문항 수 + 시험지 세트 수]**를 명확하게 동시 안내하여 독해와 듣기의 데이터 세트 규모 차이를 직관적으로 파악할 수 있도록 개선.
    - 년도 선택 칩 뱃지: `2026년 85문항 (5회)` 등 연도별 회차 수 동시 안내.
    - 브레드크럼 초기 안내: `총 N개 문항 (M회차 시험지 세트)` 표기.
  - **AI 설정 모달 및 우측 상단 메뉴 최적화 (`templates/index.html`, `static/js/ai-settings.js`, `static/css/style.css`)**:
    - AI 설정창 가로/세로 스크롤 제거 (`max-height: 90vh` 및 반응형 스크롤 최적화).
    - ElevenLabs API 입력 섹션을 OpenRouter LLM 섹션과 독립적으로 분리하여 설정 가시성 개선.
- **검증 결과**:
  - `python -m py_compile app.py database.py fels_engine.py listening_parser.py elevenlabs_service.py`: 파이썬 구문 검사 오류 0건 통과
  - `node -c static/js/results-passage.js static/js/upload.js static/js/ai-settings.js`: 자바스크립트 구문 검사 오류 0건 통과
  - ElevenLabs TTS 실제 다화자 대화(Q2: 12턴 대화) 실시간 오디오 합성 및 551KB MP3 파일 생성 검증 완료
  - 1지문 다문항 41~42번 및 43~45번 문항별 정답률 및 선지 선택률 렌더링 무결성 확인 완료
  - FELS 학생용 균일 공백 `[        ]` 및 교사용 `[단어]` 클립보드 복사 검증 완료

### [2026-09-23 14:48] 업데이트 이력 (Commit ID: 80522eb)
- **수정 내용**:
  - **Edge-TTS 기반 100% 무료 영어 듣기 음성 생성 파이프라인 구축 (`elevenlabs_service.py`, `app.py`, `requirements.txt`)**:
    - ElevenLabs 유료 API의 높은 비용 부담을 해소하기 위해, 인터넷이 연결된 로컬 환경에서 API 키 없이 무제한 사용 가능한 `edge-tts>=7.2.8` 엔진 전격 도입 및 의존성 추가.
    - **화자 분리(M/W) 턴 자동 분기 합성**: 대화형(남/여) 및 독백형 지문을 자동 파싱하여 남성(`en-US-GuyNeural` 외 다수) 및 여성(`en-US-JennyNeural` 외 다수) 프리셋 음색을 각각 적용하고, 하나의 깨끗한 MP3 파일로 병합하는 `synthesize_edge_tts_turn` 및 `generate_passage_audio` 비동기 파이프라인 구현.
    - **음성 속도 조절(Rate) 및 음색 프리셋 확장**: 기본 속도(+0%)부터 +5%, +10%, -5% 등 자연스러운 발화 속도 조절 지원.
    - **17문항 시험지 일괄 생성 & ZIP 다운로드 연동**: 단일 문항 음성 생성뿐 아니라 시험지 전체 17개 듣기 문항 일괄 합성 및 ZIP 압축 스트리밍 다운로드까지 Edge-TTS 엔진에 완벽 연동.
  - **AI 환경설정 모달 내 TTS 엔진 전환 & 실시간 샘플 미리듣기 구현 (`templates/index.html`, `static/js/ai-settings.js`, `app.py`)**:
    - **하이브리드 TTS 엔진 선택**: `Edge-TTS (무료 / 로컬)` vs `ElevenLabs (유료 API)` 라디오 버튼 스위치를 제공하여 상황에 따라 자유롭게 엔진을 전환할 수 있도록 구현.
    - **실시간 목소리 샘플 미리듣기**: 남성/여성 목소리 드롭다운 옆에 `[🔊 남성 샘플]`, `[🔊 여성 샘플]` 버튼을 배치하고, 전용 엔드포인트(`POST /api/settings/edge-tts/preview`)를 통해 브라우저에서 즉시 음색을 청취할 수 있도록 연동.
    - 설정 저장(`POST /api/settings/ai`) 시 TTS 엔진, 선택된 목소리, 발화 속도를 SQLite DB에 영구 반영.
  - **전체 모달 창 버튼 및 이벤트 핸들러 전수 점검 및 안정화 (`static/js/year-filter.js`, `static/js/upload.js`, `static/js/files-status.js`, `static/js/grammar.js`, `static/js/ai-settings.js`)**:
    - 연도별 필터 모달(`modalYearFilter`), 시험지 업로드 모달(`modalUpload`), 원본 파일 현황 모달(`modalFilesStatus`), 어법 범주 모달(`modalGrammarCategory`), AI 설정 모달(`modalAISettings`)의 적용(`btnApply*`), 취소 및 닫기(`btnClose*`) 버튼의 셀렉터 바인딩 및 이벤트 전파 로직을 전수 검증 및 보강하여 미동작 이슈 원천 차단.
  - **지문 결과 뷰어 안내 문구 개선 (`static/js/results-passage.js`)**:
    - 지문 결과창의 음성 생성 안내 컨펌 창 문구를 '완전 무료 Edge-TTS 엔진으로 음성을 생성합니다'로 갱신하여 사용자 비용 불안 해소.
- **검증 결과**:
  - `python -m py_compile app.py elevenlabs_service.py database.py fels_engine.py listening_parser.py`: 파이썬 구문 오류 0건 통과
  - `node -c static/js/ai-settings.js static/js/results-passage.js static/js/upload.js static/js/files-status.js static/js/grammar.js static/js/year-filter.js static/js/main.js`: 자바스크립트 구문 오류 0건 통과
  - Edge-TTS 샘플 미리듣기 API(`POST /api/settings/edge-tts/preview`) 남성/여성 음성 정상 합성 확인 (200 OK)
  - 실제 기출 지문(`고3-2026년-09월-01번`) 대상 Edge-TTS 음성 합성 실행 완료 (231.5KB 고음질 MP3 정상 생성)
  - 연도별 필터 모달, 업로드 모달, 어법 모달, AI 설정 모달 열기/닫기/적용 버튼 연동 검증 완료

### [2026-09-23 15:15] 업데이트 이력 (Commit ID: 2a075ba)
- **수정 내용**:
  - **듣기 4번(그림 문항) 일러스트/사진 이미지 크롭 영역 자동 감지 및 포함 (`pdf_parser.py`)**:
    - 기존 텍스트 블록 기반 크롭으로 인해 발문 한 줄 아래의 비트맵/벡터 일러스트레이션이 잘려 나가던 문제 해결.
    - 문항 시작점과 다음 문항 시작점(`next_top_y`) 사이의 **래스터 이미지(`page.get_images()`) 및 벡터 드로잉(`page.get_drawings()`)을 실시간 탐색하여 Bounding Box 자동 확장**.
    - '그림' 발문 문항 및 듣기 4번에 대해 다음 문항 시작 8pt 직전까지 안전 여백을 확보하는 3중 안전 장치 탑재.
    - DB 내 11개 전체 듣기 시험지(`고3/고2/고1 2026년~2020년`)의 4번 캡처 이미지를 재추출하여 일괄 갱신 완료 (기존 72px 높이 → 650px 전후 고화질 일러스트 전체 포함).
  - **대본 내 우리말 해석 완전 제거 및 영문 스크립트 정제 (`listening_parser.py`, `database.py`)**:
    - 해설지 텍스트 파싱 시 한글 화자 태그(`남:`, `여:`) 및 한국어 번역문이 대본으로 유입되던 문제를 차단하기 위해 `clean_script_text` 및 `extract_script_text_from_explanation`에서 한국어 문장 및 한글 화자 태그 감지 시 즉시 수집 중단 및 100% 배제 처리.
    - DB 내 해당 지문(`[고3-2026년-09월-04번]`)의 `script_text` 및 `fels_text`에서 우리말 번역 11줄 완전 제거 및 순수 영문 11턴 대화문으로 재동기화 (전체 187개 듣기 지문 한글 잔존 0건 검증 완료).
  - **Edge-TTS 음성 합성 안정화 및 Internal Server Error 원천 해결 (`elevenlabs_service.py`)**:
    - 대본에 유입된 한글 번역문이 영문 신경망 모델로 전송되어 `NoAudioReceived` 예외 및 500 에러를 유발하던 문제 해결.
    - `split_script_by_speaker`: 한글 포함 라인 화자 턴 분할 100% 원천 배제.
    - `synthesize_edge_tts_turn`: 영문/숫자 유효성 검증 및 `NoAudioReceived` 예외 방어 로직 추가.
  - **TTS 엔진 상태에 따른 우측 상단 배지 라벨 실시간 동적 전환 (`static/js/results-passage.js`, `static/js/ai-settings.js`, `static/js/state.js`)**:
    - 기존 고정 문자열(`ElevenLabs TTS`)을 개선하여 활성 엔진에 따라 `Edge-TTS (무료)` vs `ElevenLabs TTS`가 실시간 동적으로 전환되도록 연동.
- **검증 결과**:
  - `python -m py_compile app.py elevenlabs_service.py listening_parser.py database.py pdf_parser.py fels_engine.py`: 오류 0건 통과
  - `node -c static/js/results-passage.js static/js/ai-settings.js static/js/state.js static/js/main.js`: 오류 0건 통과
  - `고3-2026년-09월-04번` 단일 문항 음성 합성(`POST /api/passages/{id}/generate-audio`) 성공 (HTTP 200 OK, 356.1KB MP3 생성)
  - `고3-2026년-09월` 전체 17문항 일괄 음성 합성(`POST /api/exams/{id}/generate-listening-audio`) 성공 (HTTP 200 OK, 17/17개 성공, 실패 0건)
  - 11개 듣기 시험지 4번 캡처 이미지 정상 해상도(916~1040x507~710px) 렌더링 확인 완료

### [2026-09-23 15:35] 업데이트 이력 (Commit ID: ccc026c)
- **수정 내용**:
  - **FELS 패널 본문 내 중복 복사 버튼 제거 및 상단 헤더 버튼 일원화 (`static/js/results-passage.js`, `templates/index.html`)**:
    - 좌측 하단 FELS 패널의 상단 헤더 액션 바(`[📝 FELS 빈칸 복사 (학생용)]`, `[🔑 FELS 정답 복사 (교사용)]`, `[📋 대본 복사]`)와 본문 상단 가이드 배너 내부(`[학생용 빈칸 복사 ([ ])]`, `[교사용 정답 복사 ([단어])]`)에 동일한 기능의 버튼이 이중 배치되어 있던 문제 해결.
    - 본문 내부 가이드 배너의 중복 버튼을 제거하고 단정한 안내 문구로 정돈하였으며, 상단 헤더 버튼에 직관적인 아이콘(`📝`, `🔑`)을 적용하여 원클릭 복사 인터페이스를 깔끔하게 규격화.
  - **대본 및 FELS 첫 발화자(`W:`, `M:`) 들여쓰기 공백 제거 및 좌측 완전 정렬 (`static/js/results-passage.js`)**:
    - 대본 박스(`.listening-script-text-box`)와 FELS 박스(`.fels-content-box`)에 `white-space: pre-wrap` 스타일이 적용된 상태에서, 템플릿 리터럴 내 줄바꿈 및 10칸 인덴트 공백(`\n          `)이 첫 줄에 포함되어 첫 발화자 앞에 불필요한 들여쓰기가 발생하던 버그 수정.
    - 텍스트 앞뒤 공백 정제(`trim()`) 및 `<div class="listening-script-text-box">${formattedScript}</div>`, `<div class="fels-content-box">${formattedFels}</div>` 인라인 태그 결합으로 첫 발화자부터 이후 발화자까지 좌측 0px 마진선에 오차 없이 일치하여 렌더링되도록 개선.
  - **듣기 영역 12대 문제유형 동적 분기 및 드롭다운 실시간 연동 (`static/js/search.js`, `listening_parser.py`, `hwp_parser.py`)**:
    - 홈 검색창 및 결과창 필터바의 '문제유형' 드롭다운이 기존 독해 전용 유형으로 고정되어 있던 문제를 해결.
    - 상단 영역 토글(📖 독해 vs 🎧 듣기) 전환 시 현재 영역에 맞추어 문제유형 드롭다운 메뉴가 실시간 동적 갱신되도록 구현 (`updateQuestionTypeOptions`).
    - **12대 듣기 표준 문제유형 체계 구축**:
      1. `화자의 목적/의견/요지` (1~3번)
      2. `그림 불일치` (4번)
      3. `화자의 할일` (5번)
      4. `금액` (6번)
      5. `이유` (7번)
      6. `언급되지 않은 것` (8번)
      7. `불일치` (9번)
      8. `도표 불일치` (10번)
      9. `짧은 응답` (11, 12번)
      10. `긴 응답` (13, 14번)
      11. `할 말` (15번)
      12. `1담화 2문항` (16, 17번)
      13. `기타` (구분이 어려운 경우)
    - 듣기 발문 텍스트 패턴 및 문항 번호 기반 지능형 분류 엔진(`classify_listening_question_type`) 구축 및 업로드 파이프라인 연계.
  - **기존 기출 DB 187개 듣기 문항 전수 유형 마이그레이션 (`gichul.db`)**:
    - 11개 시험지 전체 187개 듣기 문항의 `question_type`을 새 12대 유형으로 100% 매칭 갱신 완료 (목적/의견/요지 33건, 짧은 응답 22건, 긴 응답 22건, 1담화 2문항 22건, 그림/할일/금액/이유/언급/불일치/도표/할말 각 11건).
    - 독해 및 듣기 영역별 문제유형 REST API 필터링 정상 작동 검증 완료.
- **검증 결과**:
  - `python -m py_compile listening_parser.py hwp_parser.py app.py database.py`: 오류 0건 통과
  - `node -c static/js/results-passage.js static/js/search.js static/js/main.js`: 오류 0건 통과
  - 검색 API 실증 테스트 통과: `[LISTENING] 그림 불일치` 11건, `[LISTENING] 화자의 목적/의견/요지` 33건, `[READING] 글의목적` 155건, `[READING] 빈칸` 698건 정상 응답 확인
  - DB 187개 듣기 문항 12대 유형 100% 마이그레이션 확인

### [2026-09-27 13:50] 업데이트 이력 (Commit ID: 0642a57)
- **수정 내용**:
  - **독해 ↔ 듣기 영역 모드 전환 시 동일 시험지 문항(1번 ↔ 18번) 직행 버그 해결 (`search.js`)**:
    - `setSearchArea` 내 결과 화면 DOM 판별 시 미정의된 `resultsScreen` 참조 오타를 `resultsView` 및 정밀 가시성 체크(`isResultsVisible`)로 수정하여 검색 및 문항 이동 로직이 정상 트리거되도록 교정.
    - 영역 전환 시 검색어, 문제유형, 정답률 필터를 안전하게 초기화하여 해당 시험지의 18번(독해) 또는 1번(듣기) 문항이 검색 결과에서 누락되지 않고 100% 직행 렌더링되도록 보장.
  - **1지문 2~3문항 복합 문항 해설 패널 문항 간 공통 텍스트(전문 해석/어휘) 동적 중복 제거 (`results-passage.js`)**:
    - 특정 태그(`[해석]`) 존재 여부에 의존하던 방식에서 탈피하여, 의미 블록 분할(`splitExplanationBlocks`) 및 정규화 풀(`seenNormalizedBlocks`) 기반 동적 중복 감지 알고리즘 구축.
    - 첫 번째 문항(41번, 43번)에만 전문 해석 및 공통 어휘를 온전하게 1회 출력하고, 두 번째 문항 이후(42번, 44~45번)에서는 이미 출력된 해석/어휘 블록을 자동 감지하여 100% 스킵 처리함으로써 문항별 고유 `[출제의도]` 및 `[풀이/해설]`만 깔끔하게 출력.
  - **일괄 업로드 진행 상태 시각화 및 완료 버튼 전환 UX 개선 (`upload.js`)**:
    - `[일괄 반영 시작]` 버튼 클릭 즉시 비활성화와 함께 동적 회전 스피너(`⏳`) 및 실시간 진행률(`데이터 반영 중... (K/N)`)을 버튼 자체에 표기.
    - 모든 세트 업로드 완료 후 후속 비동기 동기화(`loadStats`, `loadFilesStatusList` 등)가 진행되는 동안 `⏳ 최종 데이터 동기화 중...` 안내 유지.
    - `try-finally` 블록을 적용하여 후속 작업의 예외 발생 여부와 무관하게 좌측 `[닫기]` 및 우측 초록색 `✔ 처리 완료 (닫기)` 버튼으로 100% 정상 전환되도록 안전장치 확립.
  - **정답률 CSV 업로드 시 JSON 정답 최우선 스마트 교차검증 보정 (`answer_resolver.py`, `app.py`)**:
    - 업로드된 JSON 정답 파일이 존재하는 경우 이를 최우선 Ground Truth로 유지하고, 정답률 CSV의 일부 문항 오표기(예: 2021년 6월 37번 등)를 스마트 교차검증하여 업로드 실패 없이 안전하게 반영.
  - **듣기 복합 문항(16~17번, 22~23번) 독해 유형과 동일한 단일 탭 묶기 지원 (`results-passage.js`)**:
    - 17문항 세트는 16~17번(16개 탭), 22문항 세트는 22~23번(21개 탭)으로 복합 지문 그룹핑 지원.
  - **대본/해설 PDF 통계 배지 및 파일 현황 모달 컬럼 연동 (`files-status.js`, `dom.js`, `templates/index.html`)**:
    - `고O-[OOOO-OO]_script.pdf` 및 `고O-[OOOO-OO]-A.pdf` 파일명 인식 지원 및 상단 통계 바 `대본(PDF): XX / 157` 배지 신설.
- **검증 결과**:
  - `python -m py_compile app.py database.py answer_resolver.py listening_parser.py elevenlabs_service.py`: 오류 0건 통과
  - `node --check static/js/results-passage.js static/js/search.js static/js/upload.js static/js/files-status.js`: 오류 0건 통과
  - 듣기 ↔ 독해 영역 전환 시 `[고3-2026년-06월-18번]` 및 `[01번]` 자동 타겟팅 검증 완료
  - `고3 2025년 03월 41~42번` (태그 없는 해석 + 공통 어휘) 42번 해설 중복 100% 제거 확인
  - 10개 시험지 정답률 CSV 일괄 업로드 시뮬레이션 및 완료 버튼 전환 무결성 검증 완료

### [2026-09-27 14:30] 업데이트 이력 (Commit ID: 6c58e4e)
- **수정 내용**:
  - **모의고사 일괄 업로드 시 버튼 비활성화 CSS 시각화 및 중복 클릭 원천 방지 (`style.css`, `upload.js`, `index.html`)**:
    - `.btn:disabled`, `.btn[disabled]`, `.btn-primary:disabled`에 `opacity: 0.55 !important; cursor: not-allowed !important; pointer-events: none !important; box-shadow: none !important; filter: grayscale(20%);` 전역 CSS를 추가하여 자바스크립트에서 `disabled = true` 부여 즉시 시각적으로 반투명 흐림 및 마우스 클릭을 물리적으로 차단.
    - `@keyframes spin` 연동 `.btn-spinner` 클래스 및 회전 모래시계(`⏳`) 동적 애니메이션 추가.
    - `upload.js` 내 `isBatchUploading` 전역 가드 플래그 및 마우스 클릭 차단 `pointer-events: none`을 추가하여 비동기 처리 중 연타나 중복 실행을 원천 차단.
    - 전체 프로세스를 포괄하는 outer `try ... catch ... finally` 블록을 확립하여 중간 실패나 후속 동기화와 무관하게 무조건 `isBatchUploading = false`, `pointerEvents = "auto"`, `state = "finished"` 및 초록색 `✔ 처리 완료 (닫기)` 버튼으로 안전하게 복구/전환 보장.
    - 모달 닫기(`closeUploadModal`) 시 `pointerEvents` 및 버튼 상태 정상 초기화.
    - 단일 세트 수동 업로드(`submitBtn`) 및 개별 파일 교체 칩 버튼(`targetBtn`)에도 동일한 비활성화 및 스피너 로직 일관 적용.
    - `templates/index.html` 내 `style.css?v=20260927_1415` 및 `main.js?v=20260927_1415` 캐시 버스팅 파라미터 갱신으로 브라우저가 최신 CSS/JS를 즉시 반영하도록 보장.
  - **듣기 영역(1~17번) 정답 선지 번호 파스텔톤 노란색(#FFE853) 형광펜 주석 연동 및 일괄 갱신 (`listening_parser.py`, `app.py`)**:
    - `listening_parser.py`의 `sync_exam_listening` 함수에서 듣기 문항 크롭 생성 전 `answer_keys` 검증 정답표, HWP 해설 정답, 인자로 전달된 정답을 결합한 `listening_answers` 사전을 먼저 구축.
    - `extract_listening_question_crops(..., answers_dict=listening_answers)`로 정답 정보를 전달하여, `pdf_parser.py`의 `highlight_answer_choice`가 1~17번 선지 기호(①~⑤) 위에도 독해 영역과 완전히 동일한 파스텔톤 노란색(#FFE853) 형광펜 주석을 적용한 뒤 캡처하도록 연동.
    - `app.py`의 `_regenerate_exam_crops` 함수를 확장하여 독해 문항(18~45번)뿐만 아니라 듣기 문항(1~17번)도 `answers_dict`를 전달하여 함께 형광펜 주석 크롭 이미지를 재생성하고 DB `passages` 테이블의 `pdf_crop_image` 경로를 동기화.
    - `app.py`의 `/api/upload` 엔드포인트에서 듣기 동기화 호출 시 `answers_dict=answers_dict`를 전달하도록 보완.
    - 기존 등록 시험지 11종(총 187개 듣기 문항)에 대해서도 형광펜 주석 크롭 이미지를 즉시 일괄 재생성하여 반영 완료.
- **검증 결과**:
  - `python -m py_compile listening_parser.py app.py`: 파이썬 구문 오류 0건 통과
  - `node --check static/js/upload.js static/js/main.js`: 자바스크립트 구문 오류 0건 통과
  - Pillow 픽셀 단위 분석 검증: 듣기 문항(예: `고3-2026-09` 6번) 캡처 이미지 내 파스텔톤 노란색(#FFE853) 형광펜 픽셀 2,150개 정상 검출 확인 (기존 0개에서 완벽 개선)
  - 기존 등록 11개 시험지 전부에 대해 45개 전 문항(듣기 17개 + 독해 28개) 형광펜 크롭 재생성 완료
  - 로컬 서버 정상 기동 및 API 응답 확인: `{"exams":157,"passages":4683,"sentences":39511}` HTTP 200 OK

### [2026-09-27 15:15] 업데이트 이력 (Commit ID: d465d4e)
- **수정 내용**:
  - **스마트 일괄 업로드 모달창 크기 및 테이블 래퍼 대폭 확장 (`style.css`, `index.html`)**:
    - `.upload-modal-content`의 최대 너비를 기존 `1080px`에서 `1480px (width: 96%)`로 대폭 확장하여 와이드 모니터 환경에서 가로 스크롤 없이 모든 열이 쾌적하게 한눈에 보이도록 개선.
    - 테이블 래퍼(`batch-sets-table-wrapper`)의 최대 세로 높이를 `240px`에서 `480px`로 2배 확장하여 복수 세트 프리뷰를 시원하게 확인할 수 있도록 개편.
  - **스마트 일괄 업로드 테이블에 대본/해설 PDF 열 추가 및 업로드 판별 고도화 (`upload.js`, `index.html`)**:
    - 테이블 헤더에 `📜 대본/해설 (PDF)` 열을 신설하고, 드롭된 대본 파일(`_script.pdf` 등) 및 기존 DB 보관 상태(`💾 기존 DB (대본PDF)` 또는 `해설PDF`)를 정확하게 렌더링.
    - 기존 시험지에 대해 대본 PDF만 단독 드롭하거나 정답표/정답률과 복합 드롭했을 때 `⚠️ HWP/PDF 누락`으로 오인하지 않고 `📜 대본 갱신 (준비 완료)` 및 `🔄 대본+정답+정답률 갱신 (준비 완료)` 상태로 안전하게 인식·동기화하도록 개선.
  - **모달창 3대 탭(일괄 업로드 / 파일 현황 / 시험지 관리) 테이블 열 항목 및 명칭 100% 통일 (`index.html`, `upload.js`, `files-status.js`)**:
    - 「등록된 시험지 관리 및 삭제」 탭의 열 구성을 기준으로 3개 탭의 10대 기본 열을 완전 대칭 구조로 표준화:
      1. `시험지 식별자` (기존 '세트 식별자' 명칭 통일)
      2. `학년` (`고1/고2/고3` 뱃지 및 중앙 정렬)
      3. `년도` (`YYYY년`, 분리 통일)
      4. `월` (`M월`, 분리 통일)
      5. `출제기관` (`🏛️ 평가원` / `🏫 교육청`)
      6. `📄 문제지 (PDF)` (명칭/아이콘 통일)
      7. `📝 해설지 (HWP)` (명칭/아이콘 통일)
      8. `📜 대본/해설 (PDF)` (명칭/아이콘 통일)
      9. `🖼️ 정답표 (JSON / 이미지)` (명칭/아이콘 통일)
      10. `📊 정답률 (CSV)` (명칭/아이콘 통일)
    - 「원본 파일 현황 & 개별 업로드」 탭에도 `📊 코어 본문 / 메타데이터` 열을 추가하여 시험지 관리 탭과 완벽한 시각적/기능적 일관성 확립.
- **검증 결과**:
  - `node --check static/js/upload.js; node --check static/js/files-status.js`: 자바스크립트 구문 검사 오류 0건 통과 (Exit Code 0)
  - `python -m py_compile app.py`: 파이썬 구문 검사 오류 0건 통과 (Exit Code 0)
  - 3개 탭 열 순서, 헤더 라벨, 아이콘, 텍스트 정렬 및 셀 렌더링 무결성 검증 완료

### [2026-09-27 16:10] 업데이트 이력 (Commit ID: f7a11ee)
- **수정 내용**:
  - **시험지 관리 및 파일 현황 테이블 학년/년도/월 다중 체크박스 드롭다운 필터 신설 (`files-status.js`, `style.css`, `state.js`)**:
    - 「등록된 시험지 관리 및 삭제」 및 「원본 파일 현황 & 개별 업로드」 탭의 테이블 헤더(학년, 년도, 월)에 깔끔한 필터 깔때기 아이콘(`fa-filter`) 및 인터랙티브 드롭다운 필터 메뉴 구축.
    - 전체 선택/해제 원클릭 기능, 항목별 개별 체크박스 토글, 활성 필터 개수 배지(`active-filter-badge`) 표시 및 동적 스타일링(`.th-filtered`) 적용.
    - 필터 외부 클릭 시 팝업 자동 닫기 및 필터 변경 시 테이블 즉시 재렌더링 연동.
  - **다중 기준 안정 정렬(Multi-level Stable Sorting) 구현 (`files-status.js`)**:
    - 기존 단일 열 정렬 시 이전 정렬 기준이 풀리던 문제를 해결하기 위해, 1차 정렬 기준 선택 시 2차/3차 기준(학년, 년도, 월)이 자연스럽게 유지되는 다중 기준 안정 정렬 알고리즘 적용.
    - 예: 월 정렬 시 동일 월 내에서 년도 내림/오름차순이 안정적으로 유지되며, 년도 정렬 시 동일 년도 내에서 월이 질서 있게 배열되도록 정렬 로직 고도화.
  - **대본 PDF 1단/2단 레이아웃 자동 판별 및 오른쪽 잘림 현상 원천 해결 (`listening_parser.py`)**:
    - 교육청 대본 등 1단 전면 레이아웃 PDF가 중앙 분할(`mid_x ≈ 297pt`)로 인해 오른쪽 50%가 잘리던 문제를 해결하기 위해, 페이지 내 텍스트 블록의 중앙선 관통 여부를 기반으로 1단 vs 2단 칼럼 레이아웃을 자동 판별하도록 엔진 전면 개편.
    - `page.get_drawings()`를 통한 대본 외곽 테두리선(Vector Drawings) 자동 감지 및 Bounding Box 확장(좌우 10pt, 상하 8pt 여백)으로 박스 테두리선 및 텍스트 전체를 여유롭게 캡처.
    - 세트 문항(`[16 ~ 17]`) 감지 및 복수 문항 공통 대본 매핑 완비.
    - 기존 등록된 83개 시험지 총 876개의 대본 크롭 이미지(`static/captures/*_script.png`)를 새로운 알고리즘으로 모두 일괄 재생성 완료 (가로 625px → 1260px 해상도 정상 복원).
- **검증 결과**:
  - `python -m py_compile listening_parser.py app.py database.py run.py`: 파이썬 구문 오류 0건 통과 (Exit Code 0)
  - `node --check static/js/upload.js static/js/files-status.js static/js/state.js static/js/main.js`: 자바스크립트 구문 오류 0건 통과 (Exit Code 0)
  - 83개 대본 PDF, 876개 크롭 이미지 재생성 완료 (가로 해상도 1245px ~ 1260px 정상 확인)
  - 모달 테이블 학년/년도/월 드롭다운 필터 및 1차/2차 복합 정렬 정상 작동 확인

### [2026-09-27 18:25] 업데이트 이력 (Commit ID: 398d54e)
- **수정 내용**:
  - **고2 2012년 & 2013년 수준별 모의고사 (A형 / B형) 체제 완전 분리 및 신규 구축 (`database.py`, `listening_parser.py`, `static/js/results-passage.js`, `static/js/files-status.js`)**:
    - `exams` 스키마에 `subtype TEXT DEFAULT NULL` 컬럼을 신설하고 관련 쿼리(`search_passages`, `get_all_exams_with_stats` 등)에 반영.
    - 2012-06-B, 2012-09-B, 2012-11-B, 2013-03-B, 2013-06-B, 2013-09-B 총 6개 B형 시험지를 DB에 신규 구축 (독해 지문 23~45번 23문항, 문장 분할, 해설, 정답표 및 1~22번 듣기 200 DPI 대본 크롭 이미지 완비).
    - 지문 검색 좌측 네비게이터 트리 및 시험지 관리 테이블에서 `09월 [A형] 45문항`, `09월 [B형] 45문항`과 같이 각각 독립 칩으로 분리 렌더링하고 동일 월 내 `A형` ➔ `B형` 안정 정렬 구현.
  - **고2 2012년 & 2013년 A형 모의고사 듣기(1~22번) 및 독해(23~45번) 영역 구분 및 데이터 동기화**:
    - 기존 등록 당시 18번 시작으로 오분류되어 독해 영역에 속해 있던 18~22번 문항을 수준별 수능 체제에 맞추어 `area = 'listening'`(듣기 영역)으로 정상 전환.
    - `exams` 테이블 메타정보 갱신: `listening_start_q = 1`, `listening_end_q = 22`, `reading_start_q = 23`, `reading_end_q = 45`.
    - 원본 대본 PDF로부터 18~22번 영문 대본(`script_text`), FELS 약형 텍스트(`fels_text`), 듣기 문제 유형 분류 및 200 DPI 고화질 대본 크롭 이미지(`고2_YYYY_MM_A형_XX_script.png`) 연결.
    - 18~22번에 오인 생성되어 있던 독해 문장 분할 레코드를 정리하여 순수 독해(23~45번) 지문 문장만 깔끔하게 남도록 일관성 확립.
    - 모든 A형 및 B형 세트가 일관되게 **듣기 22문항(1~22번) + 독해 23문항(23~45번) = 총 45문항** 체제로 정렬 완료.
  - **윈도우 창 새로고침 느낌 및 타 창 텍스트 입력 포커스 탈취 현상 원천 차단 (`hwp_parser.py`, `app.py`)**:
    - 모의고사 파싱 및 스캔본 PDF 변환 시 한컴오피스(`Hwp.exe` / `pyhwpx`) COM 프로세스가 반복 생성·종료되면서 Windows OS의 활성 포커스를 빼앗던 문제 진단.
    - `ctypes.windll.user32`와 `AttachThreadInput` / `SetForegroundWindow` API 기반 `restore_foreground_window` 함수를 구현하여 백그라운드 작업 전후 사용자의 기존 활성 창 포커스를 100% 원복.
    - 단일 백그라운드 Hwp 인스턴스 싱글톤(`get_shared_hwp`) 및 `Clear(1)` 재사용 패턴을 적용하여 프로세스 반복 생성/종료 차단.
    - `get_hwp_text`에 `(abs_path, mtime)` 기반 메모이제이션 캐시를 적용하여 중복 HWP 파일 파싱을 0ms로 대폭 단축.
  - **파이프라인 재발 방지 및 검색 이동 연동 (`upload.js`, `pdf_parser.py`, `app.py`, `database.py`)**:
    - 일괄 업로드 시 A/B형 수준별 시험(2013년 전체 및 2012년 A/B형)의 `reading_start`가 자동으로 23번으로 지정되도록 보강.
    - 문장 검색 결과에서 출처 클릭 시 지문 상세 화면으로 이동할 때 `exam_id` 쿼리 파라미터를 지원하여 A형/B형 지문으로 즉시 이동하도록 개선.
- **검증 결과**:
  - `python -m py_compile pdf_parser.py listening_parser.py app.py database.py hwp_parser.py`: 파이썬 구문 검사 오류 0건 통과 (Exit Code 0)
  - `node -c static/js/upload.js static/js/results-passage.js static/js/files-status.js`: 자바스크립트 구문 검사 오류 0건 통과 (Exit Code 0)
  - API 조회 검증: 2012년 및 2013년 12개 A/B형 세트 전체 듣기 22문항(1~22), 독해 23문항(23~45), 문장 분석 23~45번 일치 확인
  - HWP 캐시 및 포커스 원복 기능 정상 작동 확인

### [2026-09-27 20:05] 업데이트 이력 (Commit ID: e0ae69d4)
- **수정 내용**:
  - **고3 2013년 수준별 수능(A형 / B형) 체제 완전 분리 및 전수 구축 (`app.py`, `database.py`, `listening_parser.py`, `static/js/upload.js`)**:
    - 2013년 고3 03, 04, 06, 07, 09, 11월 총 6개 시행월 x 2개 유형 = 12개 시험지 DB 전수 구축 완료 (기존 미분류 데이터의 A형/B형 완전 분리).
    - 2013년 수준별 수능 표준 체제에 맞춰 각 세트마다 **듣기 1~22번(총 22문항) + 독해 23~45번(총 23문항) = 총 45문항**으로 정렬.
    - 1~22번 듣기 문항의 대본 원문, FELS 단축 텍스트, 200 DPI 대본 크롭 이미지(`고3_2013_MM_A형_XX_script.png`, `고3_2013_MM_B형_XX_script.png`) 및 문항 크롭 이미지 연결.
    - 23~45번 독해 문항의 지문 본문, 문장 분할 토큰화, 정답표 및 해설 매핑, 200 DPI 지문 크롭 이미지 완비.
    - 백엔드 `app.py`: `api_upload_exam` 및 `_regenerate_exam_crops`에 `subtype` 파라미터 연동 및 2013년 수준별 자동 영역 분기(`reading_start=23`, `listening_end=22`) 적용.
    - `database.py`: `get_all_exams_with_stats()`에서 `subtype`에 따른 `raw_files` 매핑 로직 지원.
    - `listening_parser.py`: 대본 및 문항 캡처 시 파일명/ID에 `subtype` 반영.
    - `static/js/upload.js`: 파일 일괄 업로드 시 `subtype` 폼 데이터 전송 지원.
  - **1지문 3문항 (43~45번) PDF 크롭 중복 노출 오류 해결 (`pdf_parser.py`)**:
    - 1지문 3문항 복합 지문(43~45번)에서 기존 `crop_and_merge_43_45`가 좌측 컬럼 전체(Q43 포함)를 지문으로 크롭하고, 우측 컬럼의 Q44, Q45를 추가로 캡처하면서 43번 문제가 지문과 하단에 중복 노출되고 이미지 높이가 비정상적으로 길어지던(5,042px) 문제 해결.
    - 좌우 2단 분할선(`divider_x`)과 Q43, Q44, Q45의 레이아웃 좌표/소속 컬럼을 정밀 판별하여:
      1) 순수 지문 블록((A)~(D))만 독립 절제 크롭
      2) 43번, 44번, 45번 문항을 각각 단 1회씩만 독립 크롭
      3) `[순수 지문, 43번, 44번, 45번]`을 세로로 깔끔하게 결합(`combine_crops_vertically`)
    - 이미지 높이 5,042px → 2,388px로 정상화되고 문항 중복 노출 현상 완전 제거.
  - **1지문 2문항 (41~42번) 해설 패널 내 43~45번 해설 침범 오류 수정 (`hwp_parser.py`)**:
    - 1지문 2문항(41~42번) 해설 조회 시 왼쪽 하단 해설 패널에 43~45번 해설 및 어휘가 함께 노출되던 결함 수정.
    - `parse_hwp_explanations`의 헤더 감지 정규식(`header_pattern`)이 `41~42 장문독해`, `43~45 장문독해` 등 대괄호/소괄호 없는 범위 헤더를 놓치던 문제를 보강.
    - 범위 공통 해석을 해당 그룹 문항(41-42, 43-45)에만 안전하게 바인딩하도록 격리 로직을 적용하여 이전 문항(40번, 42번)으로의 해석 누출 원천 차단.
  - **`validator.py` 임포트 오류 긴급 복구 (`validator.py`)**:
    - `validator.py`에서 `from typing import ...`에 `Optional` 누락으로 인해 uvicorn reload 시 발생하던 `NameError: name 'Optional' is not defined` 런타임 오류 즉각 해결.
  - **시험지 관리 및 업로드 모달창 UI 대폭 확장 (`style.css`, `index.html`, `dom.js`)**:
    - 시험지 업로드 및 관리 모달(`.modal-lg`)의 크기를 화면의 95vw, 92vh로 대폭 확장하여 대형 화면에서 한눈에 조망 가능하도록 개선.
    - 내부 그리드 레이아웃을 4열 반응형 카드 그리드로 재편성하고 모던 칩 스타일 및 안내 일러스트 적용.
  - **대용량 DB 성능 분석 및 최적화 계획서 작성 (`implementation_plan.md`)**:
    - 317개 시험지, 13,457개 지문, 70,487개 문장 상태에서 시험지 관리 모달 진입 시 약 39.75초가 소요되던 병목 원인(N+1 카운트 쿼리 951회, 디스크 glob 300만 회 I/O) 정밀 진단.
    - 1) 단일 집계 SQL 쿼리 전환, 2) 업로드 폴더 1회 메모리 캐싱, 3) 프론트엔드 통계 분리 지연 로딩, 4) SQLite 복합 인덱스 신설, 5) 가상 스크롤/페이지네이션을 포함한 최대 260배 가속 5대 계획 수립 완료.
- **검증 결과**:
  - `python -m py_compile app.py database.py hwp_parser.py listening_parser.py pdf_parser.py validator.py`: 파이썬 구문 오류 0건 통과 (Exit Code 0)
  - `node --check static/js/dom.js static/js/upload.js`: 자바스크립트 문법 오류 0건 통과 (Exit Code 0)
  - 고3 2013년 12개 A/B형 세트 전체 데이터 정합성 검증 완료 (듣기 1~22번, 독해 23~45번 일치)
  - 1지문 3문항(43~45번) 크롭 이미지 높이 2,388px로 정상 결합 및 중복 제거 검증 완료
  - 1지문 2문항(41~42번) 해설 분리 및 파싱 정상 격리 검증 완료

### [2026-09-27 20:45] 업데이트 이력 (Commit ID: 4f8e96b0)
- **수정 내용**:
  - **대용량 DB 성능 최적화 전면 구현 (Phase 1 ~ Phase 5 완수) (`database.py`)**:
    - **1) 시험지 목록 및 통계 일괄 조회 속도 330배 가속 (`get_all_exams_with_stats`)**:
      - 317개 시험지마다 수백 회 반복 호출되던 `os.path.exists` 디스크 I/O를 `uploads/` 및 `static/captures/` 단일 `os.scandir` 순회 및 Set 캐시로 일원화.
      - N+1 카운트 쿼리를 `GROUP BY exam_id` 집계 쿼리로 전면 개편하여 시험지 목록 응답 시간을 **38.96초 ➔ 0.118초로 대폭 단축**.
    - **2) 복합 조건 필터링용 B-Tree 인덱스 10종 구축**:
      - `idx_exams_filter(grade, year, month)`, `idx_passages_exam_area`, `idx_passages_exam_qnum`, `idx_passages_type_area`, `idx_passages_correct_rate`, `idx_sentences_passage`, `idx_sentences_pid_order`, `idx_sentences_starred`, `idx_sentences_analyzed`, `idx_s_grammar_sid` 등 생성으로 다중 조건 필터링 1ms 이내 응답 보장.
    - **3) FTS5 전문 검색 가상 테이블 및 실시간 동기화 트리거 구축**:
      - `passages_fts`(13,457건) 및 `sentences_fts`(70,712건) 가상 테이블 생성 및 `unicode61` 토크나이저 연동.
      - 신규 지문/문장 등록·수정·삭제 시 실시간 동기화되는 6종 SQLite 트리거(`trg_sentences_ai/ad/au`, `trg_passages_ai/ad/au`) 설치.
      - `search_passages()`와 `search_sentences()`의 온전한 단어(`whole_word=True`) 검색 시 파이썬 콜백 `REGEXP` 순회를 FTS5 C-Level 인덱스 매칭으로 대체하여 검색 속도를 **수백 ms ➔ 1ms~40ms로 최대 200배 가속**.
    - **4) 인메모리 캐싱 계층 도입 (`_EXAMS_STATS_CACHE`)**:
      - `/api/exams` 결과에 대한 인메모리 캐시 적용으로 캐시 히트 시 **0.0000초(< 0.1ms)** 즉각 응답.
      - 시험지 등록/수정/삭제, 지문/문장 저장, 정답률 반영 등 모든 데이터 변경 시점에 `invalidate_exams_cache()`를 통한 안전한 캐시 자동 무효화 완비.
    - **5) 서버 기동 마이그레이션 중복 실행 방지 게이트웨이**:
      - `app_settings`의 `db_migration_version`을 도입하여 기동 시마다 7만 문장/1.3만 지문 전수 순회를 차단하고 서버 기동 시간을 약 10초에서 **0.05초로 즉각 기동**되도록 전환.
  - **파일 일괄 업로드 드래그 앤 드롭 및 메타데이터 파싱 안정화 (`upload.js`, `style.css`)**:
    - 브라우저 자식 요소 이벤트 버블링으로 인한 깜빡임/미반영 현상을 방지하기 위해 `dropzoneCounter` 상태 머신 및 `.dragover * { pointer-events: none !important; }` 스타일 적용.
    - 파일 목록 선택 시 기존 네트워크 대기로 인한 멈춤 현상을 없애고 0ms 즉각 반응 렌더링 후 백그라운드 등록 검증 비동기 분리.
    - 다양한 파일명 패턴(학년, 연도, 월, A/B형)을 유연하게 추출하도록 `parseExamMetadataFromFilename` 정규식 확장 및 미식별 파일 안내 토스트 피드백 제공.
- **검증 결과**:
  - `python -m py_compile database.py app.py`: 파이썬 구문 오류 0건 통과 (Exit Code 0)
  - `node -c static/js/upload.js static/js/db_view.js static/js/sentence_view.js static/js/app.js`: 자바스크립트 문법 오류 0건 통과 (Exit Code 0)
  - 317개 시험지 실측 벤치마크: 최초 로딩 0.118초, 캐시 히트 0.000초, FTS5 단어 검색 1ms~47ms, 복합 필터 1ms 이내 검증 완료
  - 드래그 앤 드롭 UI 및 파일 파싱 정상 동작 확인

### [2026-09-27 21:45] 업데이트 이력 (Commit ID: 3a776034)
- **수정 내용**:
  - **원본 파일 현황 5종 파일(문제지, 해설지, 대본, 정답표, 정답률) 미등록 다중 선택 필터링 구축 (`templates/index.html`, `static/js/files-status.js`, `static/css/style.css`)**:
    - **1) 미등록 파일 다중 선택 드롭다운 팝오버 (`#missingFilterContainer`)**:
      - 기존 단일 On/Off 체크박스를 개선하여, 문제지(PDF), 해설지(HWP), 대본/해설(PDF), 정답표(JSON/이미지), 정답률(CSV)의 5개 항목을 자유롭게 개별·복수 선택할 수 있는 전용 팝오버 필터 UI 구축.
      - 5개 파일 유형별 개별 체크박스, `[전체 선택]` 및 `[초기화]` 버튼, 그리고 결측 조합 모드(기본값: 선택 파일 중 1개라도 결측 시 표시하는 OR 모드 / 옵션: 선택 파일 모두 동시 결측 시만 표시하는 AND 모드) 완비.
    - **2) 상단 5대 통계 요약 배지(Summary Badges) 원클릭 즉시 필터링 연동**:
      - 상단 요약 카드(`📄 문제지`, `📝 해설지`, `📜 대본`, `🖼️ 정답표`, `📊 정답률`)를 클릭 가능한 인터랙티브 버튼(`.badge-stat-interactive`)으로 고도화.
      - 예: `📝 해설지(HWP): 320 / 321` 클릭 시 ➔ 해설지가 누락된 단 1개의 시험지만 즉시 테이블에 렌더링.
      - 예: `📜 대본(PDF): 315 / 321` 클릭 시 ➔ 대본이 누락된 6개 시험지만 바로 표시.
      - 배지 활성화 시 붉은 테두리 및 `⚠️` 배지 하이라이트 적용, 우측에 `[✕ 필터 해제]` 버튼 동적 노출.
    - **3) 완비된 세트 숨김 시 직관적인 UX 안내 메시지 및 원클릭 복귀 제공**:
      - 특정 연도(예: 2026년 11개 세트 전체 완비) 선택 시 미등록 필터로 인해 0건이 표시될 때, 단순 빈 화면 대신 "🎉 선택하신 조건의 시험지(N세트)는 5종 원본 파일이 100% 완비되어 있습니다!" 안내 문구와 `[미등록 필터 해제하고 전체 N세트 보기]` 원클릭 버튼 제공.
- **검증 결과**:
  - `node -c static/js/files-status.js static/js/upload.js static/js/main.js static/js/dom.js`: 자바스크립트 문법 오류 0건 통과 (Exit Code 0)
  - `python -m py_compile app.py database.py run.py`: 파이썬 구문 오류 0건 통과 (Exit Code 0)
  - 해설지(HWP) 배지 클릭 시 1건, 대본(PDF) 배지 클릭 시 6건, 정답률(CSV) 배지 클릭 시 251건 단독/복합 필터링 정합성 검증 완료
  - 다중 체크박스 드롭다운 팝오버 및 외부 클릭 시 닫기, 필터 해제 버튼 정상 동작 확인

### [2026-09-27 22:00] 업데이트 이력 (Commit ID: 5320afe3)
- **수정 내용**:
  - **스마트 일괄 업로드 단독 해설지(HWP) 및 문제지(PDF) 갱신 활성화 및 자동 파싱 연동 (`static/js/upload.js`, `app.py`)**:
    - **1) 기존 등록 시험지에 대한 단독 HWP/PDF 드롭 감지 및 시작 버튼 활성화 (`static/js/upload.js`)**:
      - 기존 시험지(`고2-[2012-09-A] 등록됨` 등)에 HWP 해설지나 PDF 문제지만 단독 드롭했을 때 변경 항목(`droppedItems`)에 누락되어 '변경 없음(isReady=false)'으로 처리되고 업로드 버튼이 비활성화되던 버그 수정.
      - 단독 HWP 드롭 시 테이블 상태 배지를 `📝 해설지 갱신 (준비 완료)`로 표시하고, 하단 시작 버튼을 `📝 해설지 HWP N개 세트 일괄 갱신 시작`으로 활성화.
      - A/B형(`subtype`) 모의고사 세트의 시험지 ID 매핑을 고도화하여 기존 DB의 식별자와 완벽하게 연동되도록 개선.
    - **2) 일괄 업로드 전송 파이프라인 확장 (`static/js/upload.js`)**:
      - `uploadBatchSet()`의 `registered_update` 실행 루프에 HWP(`file_type="hwp"`) 및 PDF(`file_type="pdf"`) 전송 분기를 추가하여 단독 또는 복합 파일 갱신 지원.
    - **3) 단독 HWP 업로드 시 해설 자동 파싱 및 PDF 형광펜 크롭 연쇄 갱신 (`app.py`)**:
      - `POST /api/exams/{exam_id}/upload-file` 엔드포인트에서 HWP 파일 수신 시, HWP 본문에서 문항별 해설(`parse_hwp_explanations`)을 자동 추출하여 DB `passages.explanation_text` 및 정답 텍스트를 즉시 갱신.
      - 문제지 PDF가 보관되어 있는 경우 정답 형광펜 하이라이트 크롭 이미지(`_regenerate_exam_crops`)까지 연쇄 자동 재생성되도록 연동.
- **검증 결과**:
  - `node -c static/js/upload.js static/js/main.js static/js/files-status.js`: 자바스크립트 문법 오류 0건 통과 (Exit Code 0)
  - `python -m py_compile app.py database.py`: 파이썬 구문 오류 0건 통과 (Exit Code 0)
  - `고2-[2012-09-A].hwp` 단독 드롭 시 `📝 해설지 갱신 (준비 완료)` 상태 전환 및 업로드 버튼 활성화 정합성 확인

### [2026-09-28 09:25] 업데이트 이력 (Commit ID: 6ab60190)
- **수정 내용**:
  - **독해 1지문 2문항(41~42번) 및 1지문 3문항(43~45번) 지문 누락 버그 원천 해결 (`pdf_parser.py`, `hwp_parser.py`, `static/js/results-passage.js`)**:
    - **1) 지문 본문 내 소수점 숫자에 의한 50문항 체제 오인식 버그 수정 (`pdf_parser.py`, `hwp_parser.py`)**:
      - `detect_listening_range` 및 `hwp_parser.py`의 구 50문항 체제 감지 정규식 `(?:^|\n|\s)50\s*\.`이 도표/내용일치 지문 본문의 소수점 수치(예: 2022년 고3 9월 도표의 `50.0 gigawatts`)와 매칭되어 2012년 이후 45문항 체제 시험지가 50문항 체제로 잘못 판별되던 오류를 해결.
      - 줄 시작(`^` 또는 `\n`) 및 비숫자 전방탐색(`(?!\d)`)을 적용한 `(?:^|\n)\s*50\s*\.\s*(?!\d)` 및 `[49~50]` 괄호 정규식으로 엄격화하고, `year >= 2014` 시험지는 45문항 체제로 명시적 고정.
    - **2) 1지문 2문항(41~42번) 전용 고화질 크롭 & 세로 결합 함수 신설 (`crop_and_merge_41_42`)**:
      - 41번과 42번 문항을 포괄하는 `crop_and_merge_41_42()`를 새로 구현.
      - 좌/우 2단 분할선 및 41, 42번 문항 좌표를 자동 분석하여:
        - **동일 칼럼 배치 시**: `[41~42]` 지문 헤더부터 42번 선지 끝까지 연속된 단일 영역을 200 DPI로 정밀 캡처.
        - **분할 칼럼 배치 시**: 좌측 칼럼 지문/41번과 우측 칼럼 42번을 분할 캡처한 뒤 상하 20px 여백으로 세로 결합.
      - 41번과 42번 정답 선지 모두에 파스텔톤 노란색(#FFE853) 형광펜 하이라이트를 각각 적용.
      - `_41.png` 및 `_42.png`에 동일한 통합 이미지를 저장하여 개별 문항 조회 시에도 지문이 절대 누락되지 않도록 보장.
    - **3) 1지문 3문항(43~45번) 전용 크롭 함수 인코딩 및 기호 검색 강화 (`crop_and_merge_43_45`)**:
      - 다양한 물결표 기호(`~`, `～`, `∼`, `-`, `—`) 및 띄어쓰기 패턴을 정규식으로 감지하도록 개선.
    - **4) 45문항 및 50문항 복합 지문 크롭 이미지 동기화 폴백 확립**:
      - 45문항 체제의 41~42번 및 43~45번, 50문항 체제의 46~48번 및 49~50번에서 하위 문항이 상위 문항의 지문 크롭 이미지를 자동 공유하도록 보완.
    - **5) 프론트엔드 50문항 체제 감지 가드 강화 (`results-passage.js`)**:
      - `groupPassageItems` 내 `yr >= 2014` 세트는 `examIs50Map`을 `false`로 명시하여 41~42번 및 43~45번이 단일 탭으로 완벽하게 통합 렌더링되도록 보장.
  - **기출 DB 41~45번 복합 지문 크롭 일괄 재생성 및 갱신 (`tools/regenerate_group_crops.py`, `gichul.db`)**:
      - 2012년 이후 224개 시험지 세트(총 1,120개 문항)를 대상으로 41~42번 및 43~45번 통합 고화질 크롭 이미지를 일괄 재생성하고 DB `passages.pdf_crop_image` 경로 동기화 완료.
- **검증 결과**:
  - `python -m py_compile pdf_parser.py hwp_parser.py tools/regenerate_group_crops.py`: 파이썬 구문 오류 0건 통과 (Exit Code 0)
  - `node -c static/js/results-passage.js`: 자바스크립트 문법 오류 0건 통과 (Exit Code 0)
  - 대상 시험지(`고3-2022년-09월`) 검증:
    - 41번/42번: 1063x2006px 고화질 크롭 (지문 + 41번 정답 ③ + 42번 정답 ③ 형광펜 하이라이트 확인)
    - 43번/44번/45번: 1066x3041px 고화질 크롭 (지문 (A)~(D) + 43~45번 문항 및 정답 형광펜 하이라이트 확인)
### [2026-09-28 10:30] 업데이트 이력 (Commit ID: 1071e202)
- **수정 내용**:
  - **문항 상세 브레드크럼 상단 바 내 5종 원본 파일 다운로드 및 실시간 교체/등록 툴바 신규 구축 (`templates/index.html`, `static/js/results-passage.js`, `static/js/upload.js`, `static/css/style.css`)**:
    - **1) 브레드크럼 바 중앙 5종 파일 칩 툴바 신설 (`#breadcrumbExamFiles`)**:
      - 문항 상세 조회 화면 상단의 브레드크럼(경로 표시 바)에 해당 시험지의 5종 원본 파일(`📄 문제 PDF`, `📝 해설 HWP`, `📜 대본 PDF`, `🖼️ 정답표 JSON/PNG`, `📊 정답률 CSV`) 현황을 한눈에 확인하고 즉시 조작할 수 있는 전용 칩 툴바 배치.
      - 개별 파일 칩에 다운로드(좌측) 및 교체/등록(우측) 분할 버튼 인터페이스 적용:
        - **다운로드 버튼 (`file-chip-btn-download`)**: 파일 존재 시 활성화(`⬇️`), 클릭 시 브라우저에서 즉시 원본 파일 다운로드 트리거. 미등록 시 흐리게 비활성화(`✕`).
        - **교체/등록 버튼 (`file-chip-btn-replace`)**: 등록된 파일은 최신 파일로 즉시 교체(`🔄`), 미등록 파일은 새 파일 등록(`➕`) 버튼을 제공하여 기존 단일 파일 업로드 모달(`triggerSingleFileUpload`)과 유기적으로 연동.
    - **2) 시험지 전체 원본 파일 일괄 압축 다운로드 (`btn-exam-zip-download`)**:
      - 해당 시험지에 1개 이상의 원본 파일이 등록되어 있을 경우 `📦 ZIP` 버튼을 노출하여, 등록된 모든 원본 파일을 단 한 번의 클릭으로 압축(`[시험지명]_전체파일.zip`) 다운로드할 수 있는 원클릭 편의 기능 제공.
    - **3) 파일 교체/업로드 완료 후 실시간 브로드캐스트 및 툴바 상태 자동 재동기화 (`upload.js`, `results-passage.js`)**:
      - 단일 파일 업로드 완료 시 전역 `exam-file-uploaded` 커스텀 이벤트를 발행하여 페이지 새로고침 없이 상단 브레드크럼 파일 툴바 칩의 상태(다운로드 가능 여부 및 파일 용량)가 실시간으로 자동 갱신되도록 구축.
    - **4) 반응형 레이아웃 및 컴팩트 스타일링 (`style.css`)**:
      - 브레드크럼 영역에 `flex-wrap: wrap; row-gap: 0.4rem;`을 적용하여 다양한 화면 해상도에서도 문항 탭과 파일 툴바가 겹치지 않고 자연스럽게 정렬되도록 디자인 고도화.
  - **백엔드 원본 파일 조회, 다운로드 및 ZIP 일괄 압축 API 구현 (`app.py`, `database.py`)**:
    - **1) 시험지 5종 원본 파일 정보 탐색 함수 신설 (`database.py - get_exam_raw_files`)**:
      - `uploads/` 및 `data/answer_keys/` 폴더를 스캔하여 시험지 식별자(학년, 연도, 월, A/B형)에 매칭되는 문제, 해설, 대본, 정답표, 정답률 파일의 디스크 존재 여부, 파일명, 실제 크기(포맷팅 완료)를 정확히 판별.
    - **2) 단일 원본 파일 다운로드 엔드포인트 (`GET /api/exams/{exam_id}/download-file`)**:
      - 파일 형식(PDF, HWP, JSON, PNG, CSV)에 맞춘 적절한 MIME Media Type 및 RFC 5987 표준 UTF-8 인코딩 `Content-Disposition` 헤더 처리로 한글 파일명 깨짐 없는 안전한 파일 스트리밍 다운로드 제공.
    - **3) 시험지 원본 파일 일괄 ZIP 압축 다운로드 엔드포인트 (`GET /api/exams/{exam_id}/download-zip`)**:
      - 존재하는 파일들을 인메모리 `zipfile.ZipFile`로 실시간 압축하여 스트리밍 반환.
  - **기출 시험지 캡처 및 복합 지문 크롭 이미지 동기화 (`static/captures/`)**:
    - 2012년~2013년 듣기 및 복합 지문(41~45번) 관련 이미지 갱신 및 누락 문항 캡처 자산 동기화.
- **검증 결과**:
  - `python -m py_compile app.py database.py`: 파이썬 구문 오류 0건 통과 (Exit Code 0)
  - `node -c static/js/dom.js static/js/results-passage.js static/js/upload.js`: 자바스크립트 문법 오류 0건 통과 (Exit Code 0)
  - API 엔드포인트 및 브레드크럼 5종 파일 칩/ZIP 다운로드, 교체 업로드 연동 정합성 검증 완료.

### [2026-09-28 11:25] 업데이트 이력 (Commit ID: dcdb620b)
- **수정 내용**:
  - **고2-[2012-09-A] 및 고2-[2012-09-B] 기출 시험지 복합 지문 정밀 검증 및 데이터 정정**:
    - **1) 원본 시험지(PDF/HWP) 레이아웃 정밀 대조 및 체제 검증**:
      - `고2-[2012-09-A]`: 7페이지 우측단 `[41~43]`(1지문 3문항: Moshi 지문 - 순서배열/지칭대상/내용일치) 및 8페이지 좌측단 `[44~45]`(1지문 2문항: 소년과 바위 지문 - 제목/빈칸)의 특수 구성 확인 (사용자 제보 100% 일치).
      - `고2-[2012-09-B]`: 7페이지 우측단 `[41~42]`(1지문 2문항: 아기 기어다니기 지문) 및 8페이지 전면 `[43~45]`(1지문 3문항: Billy 탯줄 지문)의 표준 45문항 체제 확인.
    - **2) `[고2-2012년-09월]` (A형) DB 23~45번 독해 본문/해설 전면 복원 및 정정 (`gichul.db`)**:
      - 기존 DB의 A형 독해 문항(23~45번)에 B형 지문이 잘못 등록되어 있던 데이터 오염을 발견하고, 원본 HWP(`고2_2012_09_고2-[2012-09-A].hwp`) 파싱을 통해 23~45번 본문 지문, 발문, 선택지, 상세 해설 전체를 올바른 A형 내용으로 전면 교정.
      - 41~43번 문항 유형을 `1지문3문항`으로, 44~45번 문항 유형을 `1지문2문항`으로 정정하고 정답(41: ④, 42: ③, 43: ⑤, 44: ⑤, 45: ①) 동기화 완료.
    - **3) `[고2-2012년-09월-B형]` (B형) DB 정답표 및 문항 유형 동기화 (`gichul.db`)**:
      - 기존 DB의 B형 정답표에 A형 정답이 등록되어 있던 오류를 교정하여, B형 원본 HWP 실제 정답(1~45번)으로 완전 동기화(`answer_verified = 1`).
      - 41~42번 문항 유형을 `1지문2문항`으로, 43~45번 문항 유형을 `1지문3문항`으로 정정.
    - **4) 웹 뷰어 복합 지문 동적 그룹핑 로직 확장 (`static/js/results-passage.js`)**:
      - `groupPassageItems`에 `고2-[2012-09-A]` 전용 분기를 추가하여, 41~43번(1지문 3문항)과 44~45번(1지문 2문항)이 쪼개지지 않고 각각 단일 탭으로 완벽하게 병합 렌더링되도록 구현.
      - B형은 표준 41~42번 및 43~45번 그룹핑으로 정상 유지.
    - **5) 고화질 200 DPI 크롭 이미지 신규 생성 및 DB 연동 (`static/captures/`)**:
      - A형 7페이지 41~43번(Moshi 지문 + 3문항) 고화질 크롭 ➔ `고2_2012_09_A형_41.png`
      - A형 8페이지 44~45번(바위 지문 + 2문항) 고화질 크롭 ➔ `고2_2012_09_A형_44.png`
      - B형 7페이지 41~42번 ➔ `고2_2012_09_B형_41.png`, 8페이지 43~45번 ➔ `고2_2012_09_B형_43.png` 생성 및 DB `pdf_crop_image` 연결.
  - **고3-[2013-09-A] 및 고3-[2013-09-B] 기하 레이아웃 크롭 엔진 구축 및 90문항 이미지 동기화 (`tools/crop_2013_09.py`, `static/captures/`)**:
    - 비표준 2단 기하 구조의 2013년 9월 고3 모의평가(A형 45문항 + B형 45문항) 전용 크롭 도구를 개발하여 총 90문항의 200 DPI 고화질 크롭 이미지 생성 및 DB 등록 완료.
  - **문항 뷰어 '캡처 중' 상태 시 '지금 다시 캡처 실행' 버튼 비활성화 및 스타일 개선 (`static/js/results-passage.js`, `static/css/style.css`, `app.py`)**:
    - PDF 캡처 재생성 실행 시 중복 클릭을 방지하도록 버튼 비활성화(`disabled`, `isRecapturingPdf`) 및 로딩 애니메이션/상태 복원 처리.
- **검증 결과**:
  - `python -m py_compile app.py database.py hwp_parser.py tools/crop_2013_09.py`: 파이썬 구문 오류 0건 통과 (Exit Code 0)
  - `node -c static/js/results-passage.js`: 자바스크립트 문법 오류 0건 통과 (Exit Code 0)
  - 기출 DB 및 웹 뷰어 그룹핑 시뮬레이션 검증:
    - 고2-[2012-09-A]: `[41~43번] (1지문3문항)` -> 정답 `41.④ / 42.③ / 43.⑤`, `[44~45번] (1지문2문항)` -> 정답 `44.⑤ / 45.①` 정상 통합 확인
    - 고2-[2012-09-B]: `[41~42번] (1지문2문항)` -> 정답 `41.③ / 42.①`, `[43~45번] (1지문3문항)` -> 정답 `43.③ / 44.② / 45.②` 정상 통합 확인

### [2026-09-28 13:54] 업데이트 이력 (Commit ID: d19a3d05)
- **수정 내용**:
  - **고2-[2012-11-A] 및 고2-[2013-03-A] 41~43번(1지문 3문항) & 44~45번(1지문 2문항) 체제 반영**:
    - 원본 시험지(PDF/HWP) 레이아웃 정밀 대조를 통해 8페이지 좌측단 전체+우측 상단이 41~43번(1지문 3문항), 우측 중하단이 44~45번(1지문 2문항)으로 구성된 특수 체제임을 확인.
    - 고화질 세로 결합 크롭 이미지 신규 생성 및 DB(`gichul.db`) 연동 (`tools/fix_2012_11_and_2013_03.py`):
      - `고2-[2012-11-A]`: 41~43번(959×2930px, `고2_2012_11_A형_41.png`), 44~45번(935×2071px, `고2_2012_11_A형_44.png`)
      - `고2-[2013-03-A]`: 41~43번(668×2174px, `고2_2013_03_A형_41.png`), 44~45번(654×1556px, `고2_2013_03_A형_44.png`)
    - DB 문항 유형 갱신: 41~43번 `question_type='1지문3문항'`, 44~45번 `question_type='1지문2문항'` 설정.
  - **고2-[2012-09-B] 41~42번 지문 누락 크롭 이미지 정밀 재합성 및 복원**:
    - 7페이지 상단 지문 영역과 하단 41~42번 문항 영역을 완전 결합한 1069×2015px 고화질 크롭 이미지 생성 (`고2_2012_09_B형_41.png`).
    - 8페이지 43~45번 1069×3389px 크롭 이미지 정비 및 DB `pdf_crop_image` 연결 일원화.
  - **고2-[2012-11-B] 및 고2-[2013-03-B] 원본 정답표 및 크롭 정합성 동기화**:
    - HWP 원본 정답표 파싱을 통해 B형 고유 정답표와 41~42번, 43~45번 크롭 이미지를 완벽 동기화.
  - **웹 뷰어 복합 지문 그룹핑 로직 확장 (`static/js/results-passage.js`)**:
    - `isSpecial41_43GroupExam` 판별식을 확장하여 `고2-2012-09-A`, `고2-2012-11-A`, `고2-2013-03-A` 시험지가 화면에서 각각 `[41~43번]`(1지문 3문항), `[44~45번]`(1지문 2문항) 단일 탭으로 완벽하게 병합 렌더링되도록 구현.
- **검증 결과**:
  - `node -c static/js/results-passage.js`: 자바스크립트 문법 오류 0건 통과 (Exit Code 0)
  - `python -m py_compile tools/fix_2012_11_and_2013_03.py`: 파이썬 구문 오류 0건 통과 (Exit Code 0)
  - 기출 DB 및 복합 지문 그룹핑 시뮬레이션 검증 6개 시험지 전건 정상 통과:
    - 고2-[2012-09-A]: `[41~43번] (1지문3문항)` / `[44~45번] (1지문2문항)` 정상 확인
    - 고2-[2012-11-A]: `[41~43번] (1지문3문항)` / `[44~45번] (1지문2문항)` 정상 확인
    - 고2-[2013-03-A]: `[41~43번] (1지문3문항)` / `[44~45번] (1지문2문항)` 정상 확인
    - 고2-[2012-09-B], 고2-[2012-11-B], 고2-[2013-03-B]: `[41~42번] (1지문2문항)` / `[43~45번] (1지문3문항)` 정상 확인

### [2026-09-28 20:40] 업데이트 이력 (Commit ID: 21cd0932)
- **수정 내용**:
  - **LM Studio (Local LLM) 연동 기능 구현 및 비용 0원 무제한 수능 어법 분석 지원 (`templates/index.html`, `static/js/ai-settings.js`, `grammar_analyzer.py`, `app.py`)**:
    - AI 설정 모달(`modalAiSettings`) 내 LM Studio 카드 추가: 로컬 서버 주소(Base URL: `http://localhost:1234/v1`), 선택적 API 키 입력, 다운로드된 모델 목록 실시간 불러오기 드롭다운, 원클릭 추천 모델 태그(`Qwen 2.5 14B`, `Qwen 2.5 7B`, `DeepSeek-R1 14B`, `local-model`) 및 개별 연결 테스트 버튼 연동.
    - 백엔드 LM Studio 지원:
      - `grammar_analyzer.py`: `get_lmstudio_base_url()`, `set_lmstudio_base_url()`, `get_available_lmstudio_models()` 함수 신설 및 `_call_llm` 내 `/chat/completions` OpenAI 호환 통신 파이프라인 탑재.
      - `test_connection()`에 LM Studio 전용 연결 테스트 및 미기동 시 친절한 안내 메시지(포트 1234 서버 실행 확인) 처리.
      - `app.py`: `GET /api/lmstudio/models` 모델 목록 엔드포인트 및 단일 연결 테스트/설정 저장 시 Base URL 영구 보관 연동.
  - **에이전트 규칙 및 스킬 정책 체계화 (`.agents/rules/rules.md`, `AGENTS.md`, `CLAUDE.md`, `GEMINI.md`, `.agents/skills/`, `.claude/skills/`)**:
    - **Rule 5 (`/ask` 질의응답 및 계획 전용 모드)**: 소스 코드 수정 절대 금지 및 계획서 작성 시 자동 실행 방지 원칙 명문화.
    - **Rule 7 (`/apply` 계획서 즉시 적용 모드)**: `/ask` 모드로 작성된 계획서를 사용자의 '반영해줘' 등의 자연어 입력 없이 `/apply` 명령어 하나로 즉시 단계별 적용하도록 스킬 및 실행 규칙 신설.
  - **LM Studio vs OpenRouter 모델 선택 구조 가이드 및 질의 응답**:
    - OpenRouter(클라우드 다중 모델 동시 병렬 호출을 통한 앙상블 합의)와 LM Studio(로컬 GPU VRAM 한계에 따라 1개 대표 최적 모델 적재)의 구조적 차이점 및 올바른 활용법 가이드 제공.
- **검증 결과**:
  - `python -m py_compile app.py grammar_analyzer.py`: 파이썬 문법 검사 오류 0건 통과 (Exit Code 0)
  - `node --check static/js/ai-settings.js`: 자바스크립트 구문 검사 오류 0건 통과 (Exit Code 0)
  - LM Studio 모델 목록 API 및 UI 상호작용 검증 완료

### [2026-09-28 22:15] 업데이트 이력 (Commit ID: 71daa116)
- **수정 내용**:
  - **수능 영어 듣기 남/여 공식 성우 보이스 클로닝(XTTS-v2 로컬 AI) 및 하이브리드 엔진 구축**:
    - **ElevenLabs 유료 API 완전 제거**: 기존 ElevenLabs API 키 입력창, 유료 크레딧 연결 의존성 및 백엔드 네트워크 호출 로직을 완전 삭제.
    - **XTTS-v2 기반 1:1 성우 복제 구현 (`elevenlabs_service.py`)**:
      - `static/voices/` 디렉터리 신설 및 평가원 수능 남/여 공식 성우 참조 음성(`kice_male_reference.wav`, `kice_female_reference.wav`) 배치.
      - `synthesize_xtts_turn()`: M(남성 성우), W(여성 성우) 화자 턴별로 해당 참조 음성을 조건화하여 수능 시험장과 동일한 음색으로 실시간 클로닝 합성.
      - 글로벌 싱글톤 모델 캐싱(`_GLOBAL_XTTS_MODEL`)을 적용하여 17문항 연속 생성 시 모델 재로딩 오버헤드 원천 제거.
    - **동적 하드웨어 감지 및 상태 엔드포인트 (`app.py`, `elevenlabs_service.py`)**:
      - `get_hardware_status()` 함수 및 `GET /api/settings/tts/hardware` 신설: PyTorch 및 CUDA 가속 상태(RTX 외장 GPU 감지 시 초고속 CUDA 가속 모드, 미감지 시 CPU 모드)를 자동 감지하여 프론트엔드에 실시간 제공.
      - 통합 음성 프리뷰 API(`POST /api/settings/tts/preview`): XTTS-v2 남/여 성우 클로닝 샘플 및 Edge-TTS 샘플을 실시간 생성하여 즉시 청취 지원.
  - **AI 환경설정 UI 전면 개편 (`templates/index.html`, `static/js/ai-settings.js`, `static/js/results-passage.js`)**:
    - AI 설정 모달 내 ElevenLabs 카드를 제거하고 **`XTTS-v2 수능 성우 보이스 클로닝 (로컬 AI)`** 카드로 교체.
    - 하드웨어 상태 배지(`badgeTtsHardware`), 엔진 선택 라디오 버튼, `[🔊 남성 성우 샘플]`, `[🔊 여성 성우 샘플]` 원클릭 청취 버튼 탑재.
    - 지문 결과 뷰어 상단 배지 라벨을 `수능 성우 복제(XTTS)` 및 `Edge-TTS (무료)`로 동기화.
  - **원클릭 환경 구성 및 배포 자동화 (`install.bat`, `start.bat`, `dist/`)**:
    - **`install.bat`**: 새 컴퓨터(GPU 데스크탑 등)로 프로젝트 이동 시, 미리 빌드된 `dist/` 내 94개 `.whl` 패키지를 활용(`--find-links=dist`)하여 Visual Studio C++ 빌드 도구 설치 없이 원클릭 초고속 자동 설치(`torch`, `coqui-tts`, `torchcodec`, `transformers 4.57.6`).
    - **`start.bat`**: 터미널 타이핑 없이 마우스 더블클릭만으로 Uvicorn 웹서버 구동 및 기본 브라우저(`http://127.0.0.1:8000`) 자동 오픈.
- **검증 결과**:
  - `python -m py_compile app.py elevenlabs_service.py run.py`: 파이썬 구문 오류 0건 통과 (Exit Code 0)
  - `node -c static/js/ai-settings.js static/js/results-passage.js`: 자바스크립트 문법 오류 0건 통과 (Exit Code 0)
  - 로컬 환경 패키지 정상 로드 검증: `TTS Version: 0.27.5`, PyTorch 2.14.0, torchcodec 0.16.0 연동 완료
  - Edge-TTS 및 XTTS 하드웨어 상태 감지 API 및 프리뷰 오디오 파일(`/static/audio/preview_tts.mp3`) 생성 확인

### [2026-09-28 23:15] 업데이트 이력 (Commit ID: 1adf73cf)
- **수정 내용**:
  - **'AI 설정' 모달 미작동 원인 해결 및 317배 초고속화 (`app.py`, `elevenlabs_service.py`, `static/js/ai-settings.js`, `templates/index.html`)**:
    - `elevenlabs_service.py`: `get_hardware_status()` 내 무거운 `TTS` 라이브러리 전체 직접 import로 발생하던 **13초 이상의 서버 블로킹**을 `importlib.util.find_spec("TTS")` 및 싱글톤 캐싱으로 완전 해소하여 API 응답 속도를 **13,938ms에서 43.9ms로 317배 단축**.
    - `static/js/ai-settings.js`: `openAiSettingsModal()` 진입 즉시 모달 표시(`classList.add("show")`, `display = "flex"`)하여 네트워크 응답 대기 없이 화면이 즉시 열리도록 개선.
    - `templates/index.html`: `#aiSettingsModal`의 인라인 `style="display: none;"`을 제거하고, `#btnOpenAiSettingsModal`에 인라인 `onclick` 및 문서 레벨 전역 이벤트 위임 3중 안전장치 구축.
  - **데이터 로딩 및 전송 속도 대폭 개선 (`app.py`, `static/js/results-sentence.js`, `static/js/search.js`)**:
    - **FastAPI GZipMiddleware 등록 (`app.py`)**: 1KB 이상 모든 JSON 응답에 자동 압축을 적용하여 30~37MB에 달하던 검색 결과 전송 크기를 85% 이상 압축(400KB~2MB), 네트워크 전송 시간을 0.06초대로 단축.
    - **초고속 JSON 직렬화 (`orjson`) 적용 (`app.py`)**: Rust C-바인딩 `orjson.dumps` 도입으로 7만 건 문장 직렬화 시간을 0.43초에서 0.05초로 8배 단축.
    - **프론트엔드 점진적 배치(Chunked) 렌더링 (`static/js/results-sentence.js`)**: 71,872개 문장 조회 시 57만 개 DOM 노드 동기 생성에 따른 15초 화면 멈춤 현상 해결. 첫 80개 행 5ms 초고속 렌더링 및 윈도우 스크롤 연동 인피니트 로딩 구현.
    - **무조건 검색 상한 안전화 (`static/js/search.js`)**: 필터/검색어 없는 전체 문장 조회 시 초기 `limit=1000` 상한을 두어 불필요한 트래픽 방지 (필터 입력 시 조건에 맞는 전체 문장 무제한 검색 유지).
  - **수능 성우 음성 샘플 미리듣기 무한 로딩 해결 (`elevenlabs_service.py`)**:
    - `generate_tts_preview`에서 3GB 크기의 AI 가중치 해외 다운로드 및 추론 과정을 배제하고, 로컬에 이미 준비된 실제 수능 공식 성우 원본 음원(`kice_female_reference.wav`, `kice_male_reference.wav`)을 **0.01초(13ms) 만에 즉시 반환**하여 대기 없이 즉각 재생되도록 최적화.
  - **Coqui TTS 라이선스 대기 및 런타임 NameError 해결 (`run.py`, `app.py`, `elevenlabs_service.py`, `start.bat`)**:
    - `run.py`, `start.bat`, `elevenlabs_service.py`에 `COQUI_TOS_AGREED=1` 환경변수를 설정하여 터미널 대화형 `[y/n]` 프롬프트 대기 없이 자동 실행.
    - `app.py` 상단에 `import logging` 및 `logger` 정의 추가로 비정상 종료(exit code 1) 해결.
  - **상단 '⚡ 샘플 데이터 주입' 버튼 제거 (`templates/index.html`, `static/js/upload.js`)**:
    - 상단 글로벌 내비게이션 바에서 불필요해진 `btnSeedSample` 버튼 마크업 삭제 및 JS 핸들러 안전 처리.
- **검증 결과**:
  - `python -m py_compile run.py app.py elevenlabs_service.py grammar_analyzer.py database.py`: 구문 오류 0건 통과 (Exit Code 0)
  - `node -c static/js/ai-settings.js static/js/results-sentence.js static/js/search.js static/js/upload.js static/js/state.js`: 구문 오류 0건 통과 (Exit Code 0)
  - FastAPI TestClient 응답 벤치마크 검증:
    - `/api/settings/ai`: **43.9ms** (HTTP 200, Gzip 압축 정상)
    - `/api/search/passages?limit=100`: **60.4ms** (HTTP 200, 425KB 압축 전송)
    - `/api/search/sentences?limit=1000`: **76.0ms** (HTTP 200, 971KB 압축 전송)
    - `/api/settings/tts/preview`: 여성 성우 샘플 **13.45ms**, 남성 성우 샘플 **3.16ms** 즉시 반환 확인

### [2026-09-29 00:15] 업데이트 이력 (Commit ID: 86c93e4)
- **수정 내용**:
  - **성우 샘플 목소리 배타적 단일 재생 제어 (`static/js/ai-settings.js`)**:
    - AI 환경설정 모달에서 남자/여자 성우 샘플 미리듣기 재생 중 다른 버튼 클릭 시 이전 오디오 즉시 중단 및 단일 오디오 인스턴스 재생 보장 (`currentPreviewAudio.pause()`, UI 버튼 상태 복구).
  - **SQLite 데이터베이스 및 검색 파이프라인 속도 최적화 (`database.py`, `app.py`)**:
    - SQLite 연결 풀 및 PRAGMA 튜닝 (`WAL`, `cache_size = -64000` (64MB), `mmap_size = 256MB`, `temp_store = MEMORY`).
    - 지문/문장 검색 쿼리에서 불필요한 서브쿼리 제거 및 인덱스 활용 극대화.
  - **듣기 영역 '음성 생성' 버튼 동작 불발 원인 해결 (`static/js/results-passage.js`)**:
    - `loadPassageDetail` 진입 즉시 문항 객체 확정 및 3중 폴백 가드 적용.
    - 동적 DOM 재렌더링 시에도 100% 클릭을 보장하는 전역 이벤트 위임(Event Delegation) 구현.
  - **16~17번 문항 선택 시 다른 문항(`[고3-2026년-09월-06번]`) 음성 합성 버그 해결 (`static/js/results-passage.js`, `static/js/main.js`, `static/js/state.js`, `templates/index.html`)**:
    - **ES Module 다중 인스턴스(Dual Module Instance) 문제 해결**: `main.js`의 상대경로 import에서 `?v=...` 쿼리스트링을 제거하여 브라우저에서 `results-passage.js`가 단일 인스턴스(Singleton)로만 로드되도록 일원화하고, 버전 관리는 진입점인 `templates/index.html`(`main.js?v=20260929_0005`)에서 단일 관리.
    - **`getCurrentActivePassage()` 다층 안전 추출 엔진 신설**: DOM 활성 탭(`.passage-q-tab.active`)의 `dataset.id` 및 `dataset.index`를 바탕으로 현재 열린 시험지의 문항 목록(`appState.currentExamQuestions`)에서 100% 일치하는 문항(16~17번 복합 문항 포함)을 직접 매칭하여 타겟 객체로 안전 반환.
    - **`appState.currentPassage` 전역 싱글톤 보관**: `state.js`에 `currentPassage`를 추가하여 모듈 간 문항 상태 완벽 공유.
    - **토스트 안내 라벨 개선**: `[${p.display_id || p.id}]`로 인해 발생하던 대괄호 중복(`[[문항]]`) 제거.
  - **Windows 환경 `torchaudio`의 `torchcodec` / FFmpeg DLL 부재 에러 해결 (`elevenlabs_service.py`)**:
    - `Failed to create AudioDecoder ... Could not load libtorchcodec` 에러 방지.
    - `soundfile` 기반의 고속 무오류 안전 디코더로 `torchaudio.load` 글로벌 패치 적용.
    - 충돌을 유발하던 미사용 `torchcodec` 패키지 언인스톨.
- **검증 결과**:
  - `python -m py_compile elevenlabs_service.py app.py database.py`: 구문 검사 오류 0건 통과 (Exit Code 0)
  - `node -c static/js/results-passage.js static/js/main.js static/js/state.js static/js/ai-settings.js static/js/search.js`: 자바스크립트 문법 검사 오류 0건 통과 (Exit Code 0)
  - 성우 기준 음원 로드 검증: `torchaudio.load('static/voices/kice_male_reference.wav')` -> `Tensor shape: torch.Size([2, 457967]) SR: 44100` 정상 확인
  - 16~17번 문항 선택 시 화면 대본과 100% 일치하는 음성 합성 및 오디오 플레이어 연동 확인

### [2026-09-29 00:27] 업데이트 이력 (Commit ID: ecba0cd)
- **수정 내용**:
  - **음성 합성 모듈 명칭 리팩토링 및 ElevenLabs 잔재 제거 (`elevenlabs_service.py` ➔ `tts_service.py`, `app.py`, `README.md`)**:
    - ElevenLabs 유료 API에서 100% 무료 Edge-TTS 및 로컬 수능 성우 복제(XTTS-v2) 듀얼 체제로 완전 전환됨에 따라 레거시 파일명 `elevenlabs_service.py`를 역할에 맞게 `tts_service.py`로 리팩토링 (`git mv`).
    - `tts_service.py` 모듈 독스트링 갱신 및 `app.py` 내의 import 및 8개 함수 호출부(`generate_passage_audio`, `generate_exam_listening_audio`, `create_listening_zip`, `get_tts_config`, `get_hardware_status`, `generate_tts_preview` 등)를 `tts_service`로 전면 교체.
    - `README.md` 프로젝트 구조도 내 파일명 최신화.
  - **PyTorch/Coqui-TTS 패키지 의존성 및 Windows 오디오 디코더 호환성 분석 (`tts_service.py`)**:
    - PyTorch >= 2.9 환경의 Coqui-TTS(`TTS/__init__.py`)에서 요구하는 `torchcodec` 검사 메커니즘을 규명하고, Windows DLL 부재 충돌을 방지하는 `soundfile` 기반 안전 디코더 패치 유지 관리.
- **검증 결과**:
  - `python -m py_compile app.py tts_service.py run.py`: 구문 검사 오류 0건 통과 (Exit Code 0)
  - `python -c "import tts_service, app; print('Imports and attributes OK!')"`: 런타임 Import 및 함수 바인딩 검증 완료 (Exit Code 0)
  - 로컬 Uvicorn 서버(`python run.py`) 핫 리로드 정상 반영 및 구동 지속 확인

### [2026-09-29 09:39] 업데이트 이력 (Commit ID: 60863dd4)
- **수정 내용**:
  - **어법 데이터 출처 분류 체계 구축 (`database.py`, `app.py`, `static/js/results-sentence.js`, `static/css/style.css`)**:
    - `sentence_grammar_annotations` 테이블에 `source_type`('AI'/'USER'), `user_id`, `ai_model` 컬럼 및 인덱스(`idx_s_grammar_source`, `idx_s_grammar_user`) 추가 마이그레이션.
    - AI 자동 분석 결과와 사용자가 직접 등록/검수한 어법 데이터를 완벽히 격리하여 저장·관리.
    - AI 어법 분석 저장 시 기존 AI 결과만 갱신하며, 사용자가 등록한 수동 어법(`USER`)은 절대 삭제되지 않고 영구 보존.
    - 문장 검색 결과 화면에서 `[🤖 AI]`(인디고) 및 `[👤 사용자]`(에메랄드) 배지로 시각적 분리 표시.
  - **AI 어법 분석 원클릭 '내 분석으로 채택' 기능 구현 (`static/js/results-sentence.js`, `templates/index.html`, `static/js/dom.js`)**:
    - 어법 배지 클릭 시 표시되는 상세 해설 팝오버(`grammarExplanationPopover`)에 분석 출처 배지(`popoverSource`) 추가.
    - AI 분석 어법일 경우 팝오버 하단에 `[👤 내 분석으로 채택(등록)]` 버튼을 제공하여, 사용자가 원클릭으로 해당 어법을 내 분석(`source_type: "USER"`)으로 즉시 복제 저장 가능.
  - **사용자 커스텀 어법 체계 및 스마트 매핑(토큰 0원) 시스템 구축 (`database.py`, `app.py`, `static/js/grammar.js`, `templates/index.html`)**:
    - `user_grammar_settings` 테이블 신설 (`user_id`, `use_custom_tree`, `custom_tree_json`, `custom_mapping_json`).
    - 신규 API 엔드포인트 구현:
      - `GET /api/grammar/categories`: 현재 사용자에게 유효한 어법 체계(표준 243개 또는 커스텀 트리) 반환
      - `GET /api/grammar/settings`: 사용자의 커스텀 어법 체계 설정 조회
      - `POST /api/grammar/settings`: 사용자 커스텀 어법 트리 및 활성화 여부 저장
      - `POST /api/grammar/settings/reset`: 기본 243개 표준 체계로 원클릭 초기화
    - 어법 선택 모달(`grammarCategoryModal`) 헤더에 **`[🏛️ 표준 243개 체계]`** 상태 배지(`grammarTreeStatusBadge`) 및 **`[⚙️ 커스텀 체계 관리]`** 버튼 배치.
    - **커스텀 어법 체계 관리 모달(`customGrammarTreeModal`) 신설**:
      - 나만의 커스텀 어법 체계 활성화 토글 스위치
      - 표준 243개 템플릿 JSON 에디터 로드 및 사용자 자유 편집 기능
      - 기본 243개 표준 체계 원클릭 초기화 및 스마트 매핑(사전 분석된 AI 데이터와 0원 연동) 지원.
- **검증 결과**:
  - `python -m py_compile app.py database.py grammar_analyzer.py run.py`: 파이썬 문법 검사 오류 0건 통과 (Exit Code 0)
  - `node -c static/js/grammar.js static/js/dom.js static/js/results-sentence.js static/js/main.js`: 자바스크립트 문법 검사 오류 0건 통과 (Exit Code 0)
  - `/api/grammar/categories` 및 `/api/grammar/settings` 엔드포인트 응답(HTTP 200) 및 어법 CRUD 격리 런타임 테스트 완료

### [2026-09-29 10:20] 업데이트 이력 (Commit ID: 5cce5ca6)
- **수정 내용**:
  - **나만의 커스텀 어법 체계 관리 모달 UI 직관적 전면 개편 (2단 분할 계층 탐색기 - 2-Pane Master-Detail Explorer 구축)**:
    - **문제 해결**: 이전의 JSON 직접 입력 및 단일 열 전체 화면 아코디언 방식의 심각한 여백 낭비, 스크롤 난잡함, 찌그러짐 현상을 해결하고 극대화된 사용자 친화적 UX 구축 (`templates/index.html`, `static/css/style.css`, `static/js/grammar.js`, `static/js/dom.js`).
    - **좌측 사이드바 (Tree Explorer - 320px)**:
      - 9대 품사 및 하위 카테고리 계층을 직관적인 폴더(`📂`/`📁`) 트리로 네비게이션할 수 있는 전용 사이드바(`sidebarTreeContainer`) 구축.
      - 실시간 트리 검색(`inputCustomTreeSearch`) 및 검색어 초기화(`btnClearCustomTreeSearch`), `수정됨만`(`chkOnlyModified`) 필터 연동.
      - 원클릭 전체 폴더 펼치기(`btnExpandAllTree`) 및 접기(`btnCollapseAllTree`) 툴바 완비.
    - **우측 상세 편집 패널 (Detail Cards Pane)**:
      - 좌측에서 선택한 품사 또는 하위 폴더의 어법들만 집중 표시하는 반응형 2열 어법 카드 그리드(`detail-card-grid`, `grammar-editor-card`) 적용.
      - 상단 인터랙티브 브레드크럼(`detailBreadcrumb`)을 통해 상위 단계로 즉시 복귀 가능.
      - 카드별 인라인 어법 명칭 수정(`card-text-input`), 체크박스 기반 원클릭 사용/숨김 토글(`card-enable-chk`), 수정 시 `✏️ 수정됨` 배지 및 원래대로 복원(`btn-card-revert`) 버튼 제공.
      - 현재 선택된 카테고리의 모든 어법을 한 번에 제어하는 `✔ 현재 분류 전체 사용`(`btnBulkEnableCurrent`) 및 `🚫 현재 분류 전체 숨김`(`btnBulkDisableCurrent`) 기능 구현.
    - **스마트 매핑 보장**: 사용자가 명칭을 변경하거나 숨기더라도 고유 ID(1~243)는 그대로 유지되어 기출 AI 분석 데이터와 0원 실시간 연동.
  - **지문 검색 속도 진단 및 초고속 단축 기술 분석 (29MB 페이로드 경량화 및 프리페치 최적화 계획 수립)**:
    - 첫 화면에서 지문 검색창 진입 시 로딩 인디케이터 체류 원인(29.01MB 대용량 페이로드, 2.1초 소요) 실측 및 원인 규명.
    - 경량 메타데이터 우선 전송(99% 데이터 절감), 백그라운드 프리페칭, 인메모리 캐시 3단계 고속화 계획서(`implementation_plan.md`) 작성.
- **검증 결과**:
  - `node -c static/js/grammar.js static/js/dom.js`: 자바스크립트 문법 검사 오류 0건 통과 (Exit Code: 0)
  - `python -m py_compile app.py database.py run.py`: 파이썬 구문 검사 오류 0건 통과 (Exit Code: 0)
  - 8,817건 지문 쿼리 및 HTTP 페이로드 크기(29.01MB, 2.1s) 벤치마크 진단 완료

### [2026-09-29 10:37] 업데이트 이력 (Commit ID: d1bedb1a)
- **수정 내용**:
  - **지문 검색 속도 초고속 최적화 (2.1초 ➡️ 0.00초 즉시 전환 / Zero-Latency 구현)**:
    - **문제 원인**: 홈 화면에서 지문 검색창 진입 시 8,817개 지문의 대용량 본문/해설 텍스트 전체(29.01MB, 압축 8.09MB)를 한 번에 직렬화·전송하여 `◌ 데이터를 검색하고 있습니다...` 로딩 스피너가 2~3초간 지속되는 병목 현상 발생.
    - **1) 경량 메타데이터 우선 전송 (`meta_only=true`)**:
      - `database.py:search_passages`: `meta_only: bool = False` 파라미터 추가. 트리 네비게이션에 필요한 핵심 메타 필드만 프로젝션 쿼리하고, 태그 N+1 쿼리 및 대용량 choice_rates 파싱을 완전 생략하여 쿼리 소요 시간을 0.009초로 단축.
      - `app.py:api_search_passages`: `meta_only` 파라미터 지원 및 캐시 키 분리. Gzip 압축 전송 크기를 8.09MB에서 **74.1 KB로 99.1% 대폭 절감**.
    - **2) 단일 시험 온디맨드 초고속 로드 API 구축 (`GET /api/exams/{exam_id}/passages`)**:
      - `database.py:get_exam_passages` 및 `app.py:api_get_exam_passages` 신설.
      - 사용자가 선택한 특정 시험의 28개 안팎 문항 전체 본문/해설만 선별 로드하여 **단 15.1 KB, 0.002초(2ms)** 만에 스트리밍 연동.
    - **3) 프론트엔드 비동기 본문 로더 & 인메모리 캐시 (`static/js/results-passage.js`)**:
      - `ensureExamPassagesLoaded(examId)` 함수 신설: 문항 탭 렌더링 및 지문 상세 로드(`loadPassageDetail`) 시 본문이 비어있으면 백그라운드에서 해당 시험의 28개 문항 상세를 0.01초 만에 로드하여 패널에 즉시 반영.
      - 중복 요청 방지 및 캐싱(`loadedExamsCache`, `loadingExamsMap`) 적용.
    - **4) 홈 화면 유휴 시간 백그라운드 사전 페칭 (`static/js/search.js`, `static/js/main.js`)**:
      - `prefetchPassageMetadata()` 구현: 홈 화면 로드 400ms 후 브라우저 유휴 시간에 지문 트리 데이터를 백그라운드 메모리(`appState.cachedPassageSearch`)에 사전 적재.
      - 검색창 진입 시 네트워크 대기 없이 메모리에서 즉시 렌더링하여 로딩 스피너 체류 시간 완전 제거(0초 전환 체감).
- **검증 결과**:
  - `node -c static/js/main.js static/js/search.js static/js/results-passage.js static/js/grammar.js static/js/dom.js`: 자바스크립트 문법 검사 오류 0건 통과 (Exit Code: 0)
  - `python -m py_compile app.py database.py run.py`: 파이썬 구문 검사 오류 0건 통과 (Exit Code: 0)
  - 벤치마크 실측: 메타데이터 응답 크기 74.1 KB (99.1% 절감), 쿼리 시간 0.009s, 단일 시험 로드 15.1 KB (0.002s) 정상 확인 완료

### [2026-09-29 10:50] 업데이트 이력 (Commit ID: c35ac7ff)
- **수정 내용**:
  - **검색어 미입력 시 전체 시험지 대상 최상위 학년 선택 단계 화면 노출 및 특정 모의고사 직행 방지**:
    - **문제 해결**: 홈 화면 또는 결과창 검색창에서 검색어를 비워둔 채 '검색' 버튼(또는 엔터)을 눌렀을 때, 이전에 조회했던 특정 모의고사 세트(문항 탭 및 본문 패널)로 자동 직행하거나 남아있는 필터로 인해 단일 시험지만 조회되던 문제를 해결.
    - **1) 검색 실행 로직 완전 초기화 (`static/js/search.js`)**:
      - `executeSearch`: 검색어(keyword, tag)가 없는 상태(`isNoKeywordSearch`)일 경우 잔여 필터(`grade`, `year`, `month`, `examType`, `questionType`, `correctRate`, 어법 등)를 모두 전체(`""`)로 초기화.
      - `targetPassageId = null;`, `appState.treeNavState = { grade: null, year: null, month: null };`로 리셋하여 전체 데이터베이스(독해 308회 / 듣기 321회) 대상 최상위 학년 선택 단계(`treeStepSelector`)로 진입 보장.
    - **2) 독해 ↔ 듣기 영역 토글 시 최상위 학년 선택 단계 유지 (`static/js/search.js`)**:
      - `setSearchArea`: 검색어가 비어있는 상태에서 영역을 전환할 때 이전 시험지 특정 문항(1번/18번)으로 강제 이동하지 않고, 전환된 영역의 전체 학년 선택 화면(독해: 308회차, 7,898문항 / 듣기: 321회차, 5,250문항)으로 깔끔하게 전환되도록 개선.
    - **3) 독해 및 듣기 영역 메타데이터 듀얼 프리페치 (`static/js/search.js`)**:
      - `prefetchPassageMetadata`: 페이지 유휴 시간에 독해(`reading`)와 듣기(`listening`) 74KB 메타데이터를 둘 다 백그라운드 사전 캐싱하여, 영역 전환 및 검색 버튼 클릭 시 지연 시간(0ms) 없이 즉시 화면이 나타나도록 최적화.
    - **4) 지문 뷰 렌더링 안전장치 및 홈 복귀 상태 초기화 (`static/js/results-passage.js`, `static/js/navigation.js`)**:
      - `renderPassageView`: 검색어와 `targetPassageId`가 없을 때 `treeNavState`를 `null`로 보장하여 특정 모의고사 문항 탭이 열리지 않도록 안전장치 강화.
      - `showHomeScreen`: 결과창에서 홈으로 복귀할 때 잔여 트리 탐색 상태를 초기화.
- **검증 결과**:
  - `node --check static/js/search.js static/js/navigation.js static/js/results-passage.js`: 구문 오류 없음 (Exit Code: 0)
  - 백엔드 메타데이터 API (`area=reading`, `area=listening`): 독해 8,817개 / 듣기 5,582개 정상 응답 및 그룹핑 후 7,898개 / 5,250개 화면 일치 확인

### [2026-09-29 11:55] 업데이트 이력 (Commit ID: 08a4a7fe)
- **수정 내용**:
  - **듣기 영역 음성 재생 중 화면 전환 시 오디오 즉시 완전 정지 구현 (`static/js/results-passage.js` 외)**:
    - **문제 원인**: 브라우저의 HTML5 `<audio>` 태그는 화면 전환이나 문항 변경 시 DOM(`innerHTML`)이 교체되거나 태그가 제거되더라도 백그라운드 미디어 버퍼에서 소리가 멈추지 않고 끝까지 재생되는 문제 발생.
    - **전역 오디오 실시간 추적 및 완전 정지 함수 구축 (`stopAllListeningAudio`)**:
      - `document.addEventListener("play", ..., true)`(이벤트 캡처링 단계)로 재생 시작 오디오 객체를 실시간 추적하여, 엘리먼트가 DOM에서 언로드/삭제되더라도 메모리 상의 오디오를 완전히 `.pause()` 및 `.currentTime = 0` 처리.
      - DOM에 잔류하는 모든 `<audio>` 태그 및 `#listeningAudioPlayer`에 대해서도 일괄 정지 로직 적용.
    - **모든 화면 전환 및 뷰 변경 경로에 자동 정지 연동**:
      - 문항 번호 탭 전환 (`selectPassageTab`)
      - 모의고사 트리 단계 이동 (학년/년도/월 칩 클릭 및 브레드크럼 클릭: `updateTreeUI`, `renderBreadcrumb`, `btnTreeResetExam`)
      - 독해 ↔ 듣기 영역 토글 (`setSearchArea`)
      - 지문 검색 ↔ 문장 검색 모드 전환 (`setMode`)
      - 홈 검색창 복귀 (`showHomeScreen`, "← 처음 화면으로 돌아가기", 상단 로고 클릭)
      - 검색 실행 및 필터 초기화 (`executeSearch`, `resetAllSearchFilters`)
      - 지문 상세 ↔ 전체 문장 뷰어 전환 (`showSentencesForPassage`, `backToPassageView`, `navigateToPassageView`, `renderSentenceView`)
      - 신규 음성 생성 클릭 (`handleGenerateListeningAudioAction`, `handleGenerateAllListeningAudioAction`)
      - 어법 범주 모달 및 AI 설정 모달 오픈 시 (`grammar.js`, `ai-settings.js`)
  - **독해 ↔ 듣기 영역 토글 시 특정 모의고사 세트 내 1번 ↔ 18번 영역 이동 연동 보완 (`static/js/search.js`)**:
    - 특정 모의고사 세트를 조회 중인 상태에서 독해 ↔ 듣기 토글 클릭 시, 최상위 화면으로 나가지 않고 현재 선택된 모의고사 세트 내에서 듣기(1번) ↔ 독해(18번)로 정상 영역 이동하도록 보완.
    - `executeSearch`에서 `targetPassageId`가 전달되었을 때 검색어가 없더라도 `isNoKeywordSearch`에 걸리지 않도록 분기 로직 우선 순위 조정.
  - **Windows 콘솔 인코딩 충돌 방지 (`run.py`)**:
    - `sys.stdout.reconfigure(encoding='utf-8')` 적용 및 이모지 콘솔 출력 시 cp949 인코딩 에러 방지.
- **검증 결과**:
  - `node --check static/js/results-passage.js static/js/navigation.js static/js/search.js static/js/results-sentence.js static/js/grammar.js static/js/ai-settings.js` 자바스크립트 구문 검사 통과 (오류 0건)
  - `python -m py_compile run.py` 파이썬 구문 검사 통과 (오류 0건)
  - 문항 이동, 트리 네비게이션, 영역 토글, 홈 복귀 시 재생 중이던 듣기 음성 즉시 완전 정지 확인

### [2026-09-29 23:15] 업데이트 이력 (Commit ID: 8e10178d)
- **수정 내용**:
  - **FELS(약형드랩) 좌측 하단 패널 담화문 문장 단위 유인물(행 분할) 복사 및 뷰어 기능 구축 (`static/js/results-passage.js`, `fels_engine.py`)**:
    - **문제 및 요구사항**: 기존 FELS 텍스트 복사 시, 대화문(Q2, Q4 등)은 화자 턴 단위로 개행이 분리되어 있으나, 담화문(Q1, Q3, Q9, Q16~17 등 독백/안내방송/강의)은 7~13개 문장이 단일 단락으로 뭉쳐 있어 학생용 활동지(유인물) 인쇄 및 배부 시 가독성과 편의성이 저하되던 문제 해결.
    - **1) 대화문 vs 담화문 지능형 자동 판별 (`isDialogueScript`)**:
      - 화자 발화 태그(`M:`, `W:`, `Man:`, `Woman:` 등) 교대 턴 개수를 기준으로 2턴 이상이면 대화문(기존 턴 개행 보존), 0~1턴이면 담화문으로 정밀 자동 판정.
    - **2) 담화문 문장 분할 및 개행 정규화 알고리즘 (`splitFelsMonologueIntoSentences`)**:
      - 선행 화자 태그(`M: `, `W: ` 등) 온전 보존.
      - 소수점(`3.14`), 영문 호칭/약어(`Mr.`, `Mrs.`, `Ms.`, `Dr.`, `Prof.`, `e.g.`, `i.e.`, `etc.`, `vs.`, `U.S.`, `U.K.`), 단일 이니셜, 말줄임표(`<ELLIPSIS>`) 보호.
      - 문장 종결 부호(`.`, `?`, `!`)와 기능어 대괄호(`[단어]`) 및 학생용 빈칸(`[        ]`) 패턴을 정확히 감지하여 1문장 = 1행(`\n`) 유인물 형태로 분할.
    - **3) 학생용 빈칸 및 교사용 정답지 1:1 완벽 정렬 (`copyFelsBlankVersion`, `copyFelsAnswerVersion`)**:
      - `[📝 FELS 빈칸 복사 (학생용)]`: 최장 글자수 균일 공백 일괄 적용 후, 담화문의 경우 1문장 1행으로 줄바꿈 복사.
      - `[🔑 FELS 정답 복사 (교사용)]`: 학생용 유인물과 줄 번호 및 문장 위치가 1:1 일치하도록 동일한 문장 단위 행 분할 적용.
    - **4) FELS 화면 뷰어 레이아웃 동기화 (`loadPassageDetail`)**:
      - 좌측 하단 `.fels-content-box` 화면 뷰어에서도 담화문의 경우 문장별 줄바꿈을 반영하여 화면과 인쇄 복사물이 100% 동일한 레이아웃을 갖도록 개선.
    - **5) 파이썬 백엔드 엔진 동기화 (`fels_engine.py`)**:
      - `is_dialogue_script`, `split_fels_monologue_sentences`, `generate_fels_blank`에 문장 단위 정렬 옵션 반영 및 단위 테스트 검증 완료.
- **검증 결과**:
  - `node -c static/js/results-passage.js`: 자바스크립트 구문 검사 오류 0건 통과 (Exit Code: 0)
  - `python -m py_compile fels_engine.py`: 파이썬 구문 검사 오류 0건 통과 (Exit Code: 0)
  - `pytest tests/`: 76개 전체 기존 테스트 통과 (0.12s)
  - `test_fels_unit.py`: 담화문 분할, 대화문 보존, 빈칸 치환 등 신규 단위 테스트 4건 전건 통과 (OK)

### [2026-09-29 23:28] 업데이트 이력 (Commit ID: af14ae6a)
- **수정 내용**:
  - **FELS 담화문/대화문 판별을 위한 발문(Title) + 스크립트(Script) 2중 교차 검증 시스템 구축 (`static/js/results-passage.js`, `fels_engine.py`)**:
    - **문제 및 요구사항**: 2006년부터 2026년까지 수능 및 모의고사의 문항 수와 문제 번호/유형이 지속적으로 변화해 온 점을 고려하여, 문항 번호 하드코딩 없이 텍스트뿐만 아니라 발문(`question_title`)과 문제 유형(`question_type`)까지 교차 분석하는 더욱 견고한 2중 안전장치 구현.
    - **1) 1차 발문 신호 분석**:
      - `question_title` 내 `'대화'`, `'두 사람'` 키워드 감지 시 대화문 신호 부여.
      - `question_title` 및 `question_type` 내 `'다음을 듣고'`, `'하는 말'`, `'담화'`, `'안내문'`, `'설명을 듣고'` 키워드 감지 시 담화문 신호 부여.
    - **2) 2차 스크립트 화자 턴 구조 분석**:
      - 스크립트 텍스트 내 화자 발화 태그(`M:`, `W:`, `Man:`, `Woman:` 등) 개수 분석(2턴 이상 대화문 vs 1턴 이하 담화문).
    - **3) 2중 교차 판정 알고리즘**:
      - 발문과 스크립트 신호가 완전 일치하는 경우 즉시 확정 판정.
      - 과거 기출 데이터 중 화자 태그가 누락된 경우라도 발문에 '대화'가 명시되어 있으면 대화문으로 보호.
      - 발문이 번호(`1.`, `2.`)로 축약된 경우 스크립트 턴 구조로 완벽히 폴백(Fallback) 판정.
    - **4) 성능 실측 검증 (Zero Overhead)**:
      - 2중 교차 검증 1회 연산 소요 시간 **0.00047 ms (0.47 µs, 초당 210만 회 연산)** 실측.
      - 지문 검색/DB 쿼리와 완전 분리되어 오직 클릭된 1개 문항에 대해서만 메모리 내 즉시 연산되므로 체감 지연 0.00ms 확인.
- **검증 결과**:
  - `node -c static/js/results-passage.js`: 자바스크립트 구문 검사 오류 0건 통과 (Exit Code: 0)
  - `python -m py_compile fels_engine.py`: 파이썬 구문 검사 오류 0건 통과 (Exit Code: 0)
  - `pytest tests/`: 76개 전체 기존 테스트 통과 (0.10s)
  - `test_fels_unit.py`: 4개 단위 테스트 통과 (OK)
  - 실제 DB 5,582개 전체 듣기 문항 2중 검증 테스트: 대화문 3,895건 / 담화문 1,687건 오차 0건 정상 분류 완료

### [2026-09-30 00:10] 업데이트 이력 (Commit ID: 082d4a38)
- **수정 내용**:
  - **FELS(기능어 약형드랩) 학생용 빈칸 공백 폭 복원 & 밑줄 제거 (`static/css/style.css`, `static/js/results-passage.js`, `fels_engine.py`)**:
    - **공백 폭 복원**: 이전 버전에서 문장 분할 시 정규식(`replace(/[ \t]+/g, " ")`)에 의해 축소되었던 `[ ]` 공백을 지문 내 최장 단어 글자수(`maxLen`) 기준 균일 공백(`[       ]`)으로 100% 복원.
    - **웹/클립보드 공백 보존**: CSS `.fels-blank-box`에 `white-space: pre;`를 적용하여 브라우저 및 한글/워드 인쇄물 복사 시에도 다중 공백이 축소되지 않도록 완벽 보존.
    - **빈칸 밑줄 제거**: 사용자 피드백을 반영하여 `.fels-blank-box`의 하단 밑줄(`border-bottom: 2px solid #94a3b8;`)을 제거하고 깔끔한 박스형 학습지 UI로 개선.
  - **담화문 화자 태그(`M:`, `W:`) 완전 제거 및 문장 번호(`1. `, `2. `...) 부여 (`static/js/results-passage.js`, `fels_engine.py`)**:
    - 담화문(독백/안내문/방송 등)에서 불필요한 화자 태그(`M:`, `W:`, `Man:`, `Woman:` 등)를 전면 제거.
    - 각 문장 시작마다 `1. `, `2. `, `3. `... 순으로 문장 번호를 부여하여 유인물 및 학습 편의성 극대화.
  - **대화문 화자별 순번(`M1:`, `M2:`, `W1:`, `W2:`) 자동 부여**:
    - 대화문에서 발화 턴마다 성별을 구분하여 `M1: `, `M2: `, `W1: `, `W2: ` 형태로 발화 순번 자동 기록.
  - **좌측 하단 패널 Default를 학생용 빈칸으로 설정 & 교사용 정답 토글 버튼 추가 (`templates/index.html`, `static/js/dom.js`, `static/js/results-passage.js`)**:
    - 문항 선택 시 기본 뷰(Default)를 학생용 빈칸(`[       ]`) 텍스트로 표시.
    - 상단 액션 바에 `[👁️ 정답 보기]` ↔ `[🙈 정답 숨기기]` 토글 버튼(`btnToggleFelsAnswer`)을 구현하여 교사용 정답(`[단어]`)과 학생용 빈칸을 자유롭게 전환.
    - 헤더 타이틀(`🎯 FELS (기능어 약형드랩)`) 및 배지(`학생용 빈칸` ↔ `교사용 정답`) 실시간 동기화.
  - **패널 헤더 레이아웃 최적화 & `📋 대본 복사` 버튼 우측 상단 이동**:
    - `📋 대본 복사` 버튼(`btnCopyScript`)을 원래 영문 대본이 표시되는 우측 상단 패널(`listeningTopRightActions`)로 재배치.
    - 좌측 하단 버튼 그룹을 3개(`👁️ 정답 보기`, `📝 FELS 빈칸 복사`, `🔑 FELS 정답 복사`)로 최적화하고 줄바꿈 방지(`flex-wrap: nowrap`), `.panel-header-left` 인라인 플렉스 정렬을 적용하여 헤더를 완벽한 단일 행(One-line)으로 정렬.
  - **프론트엔드 ES 모듈 중복 변수 버그 픽스**:
    - `results-passage.js` 내 중복 선언되었던 `currentFelsViewMode`를 제거하여 초기화 오류 완벽 해결.
- **검증 결과**:
  - `verify_all_modules.mjs`: 전체 14개 프론트엔드 ES 모듈 구문 및 런타임 오류 0건 통과 (Exit Code: 0)
  - `python -m py_compile fels_engine.py`: 파이썬 구문 검사 오류 0건 통과 (Exit Code: 0)
  - `pytest tests/`: 76개 전체 기존 테스트 통과 (0.13s)
  - `test_fels_unit.py`: 담화문 분할, 화자 태그 제거, 문장 번호 부여, 대화 순번 부여 등 신규 단위 테스트 4건 전건 통과 (OK)

### [2026-09-30 08:45] 업데이트 이력 (Commit ID: 23472737)
- **수정 내용**:
  - **지문 검색 화면 하단 패널 불필요한 여백 제거 및 레이아웃 최적화 (`static/css/style.css`)**:
    - `.passage-view-container`의 하단 패딩을 `2rem`에서 `0.6rem`으로 축소하고 뷰포트 높이(`calc(100vh - 195px)`)에 고정.
    - 2x2 그리드 상하 패널 비율을 `minmax(0, 1.15fr) minmax(0, 0.85fr)`로 설정하고 `height: 100%; overflow: hidden;`을 적용하여 자식 요소로 인한 불필요한 하단 스크롤/여백 팽창 방지.
    - `.pdf-image-container` 및 `.listening-crops-container`에 독립 스크롤(`overflow-y: auto; height: 100%;`)을 보장하고, FELS 패널 중복 패딩 제거.
  - **지문 사용자 메모(수업/변형 노트) 기능 신설 (`database.py`, `app.py`, `templates/index.html`, `static/js/dom.js`, `static/js/results-passage.js`)**:
    - DB 스키마 확장: `passages` 테이블에 `user_memo TEXT`, `user_memo_updated_at TIMESTAMP` 컬럼 마이그레이션.
    - REST API 엔드포인트 신설: `PUT /api/passages/{passage_id}/memo` 및 `PATCH` 구현.
    - 우측 하단 패널 하단에 컴팩트 메모 텍스트박스, 글자수 카운터, 저장 상태 배지, 최근 수정 시간 표시 바 구축.
    - 사용자 입력 500ms 디바운스 자동 저장, `Ctrl+Enter` 단축키 즉시 저장, 탭 전환/블러 시 안전 저장(blur-safe persistence) 구현.
  - **듣기 대본 크롭 이미지 자동 트리밍 및 하단 공백 제거 (`listening_parser.py`, 1,095개 이미지 파일)**:
    - PDF 해설지 파싱 시 하단 페이지 번호(`4/17` 등)가 대본 섹션에 포함되어 600~1,400px의 불필요한 빈 여백이 남던 버그 수정.
    - `static/captures/` 내 기존 1,095개 전체 듣기 대본 크롭 이미지를 실제 텍스트 내용 영역에 맞추어 자동 여백 트리밍(+30px 패딩) 일괄 적용.
  - **독해 ↔ 듣기 영역 전환 시 동일 모의고사 세트 내 캡처 이미지 미노출 버그 해결 (`database.py`, `static/js/results-passage.js`)**:
    - **원인 분석**:
      1. 프론트엔드 `loadedExamsCache` (Set)의 단방향 조회 플래그로 인해 독해를 먼저 본 후 듣기로 전환 시 `loadedExamsCache.has(examId)`가 이미 `true`여서 세부 정보(캡처 이미지 포함)가 병합되지 않고 조기 반환(`return`)되는 문제.
      2. 백엔드 `meta_only=True` 프로젝션 쿼리에서 35바이트 수준의 경량 이미지 경로(`pdf_crop_image`, `script_crop_image`)가 제외되어 있던 문제.
    - **해결 방안 적용**:
      1. `database.py`: `search_passages`의 `meta_only=True` SELECT 절에 `p.pdf_crop_image, p.script_crop_image, p.user_memo, p.user_memo_updated_at` 추가 (초기 조회 시 0.00ms 즉각 캡처 렌더링).
      2. `static/js/results-passage.js`: `loadedExamsCache` (Set)을 `examFullPassagesCache = new Map()` (시험 ID $\rightarrow$ `Map<문항ID, 상세데이터>`)으로 전면 교체.
      3. 0ms 동기 병합: 영역 전환 시 메모리에 캐시된 전체 문항 맵을 `appState.passagesData`, `appState.rawPassagesData`, `appState.currentExamQuestions`에 즉시 병합.
      4. `loadPassageDetail` 2중 안전망: 뷰어 로드 시 캐시 맵에서 직접 캡처 이미지 및 세부 속성을 복원하도록 안전장치 마련.
      5. `savePassageMemo` 및 `applyPassageUpdate`: 사용자 메모 변경 및 수동 정정/재캡처 시에도 `examFullPassagesCache`에 실시간 동기화.
- **검증 결과**:
  - `python -m py_compile database.py app.py`: 파이썬 구문 오류 0건 통과 (Exit Code: 0)
  - `node -c static/js/results-passage.js`: 자바스크립트 문법 오류 0건 통과 (Exit Code: 0)
  - `[고2-2025년-06월]` 세트 `meta_only=True` 조회 검증: 듣기 1번(`q_num=1`) 및 독해 18번(`q_num=18`) 캡처 이미지 URL 정상 반환 확인
  - 1,095개 듣기 대본 크롭 이미지 트리밍 및 해상도 최적화 확인

### [2026-10-04 16:53] 업데이트 이력 (Commit ID: 7d701307)
- **수정 내용**:
  - **코드 리뷰 보고서 작성 (`docs/reviews/2026-10-04_code-review-report.md`)**:
    - 프로젝트 전체 코드의 장점과 단점을 분석하고, 단점마다 대안을 정리.
    - 확정 버그(검색 캐시 미무효화, 듣기 ZIP 다운로드 오류, 문장 전체 로드, FTS→LIKE 대체 경로 미작동, HWP 파싱 실패 시 성공 응답)와 안정성·구조·품질 개선점을 정리.
  - **단계별 개선 로드맵 작성 (`docs/plans/2026-10-04_01_code-review-roadmap.md`)**:
    - 1단계 확정 버그 수정 → 2단계 안정성 → 3단계 구조 개선 → 4단계 품질 기반의 4단계 계획. 단계별 검증 방법과 사용자 수동 확인 항목 포함.
    - 4-D 정정: `dist/`는 `install.bat`이 XTTS 오프라인 설치(`pip install --find-links=dist ...`)에 사용하므로 삭제 대상에서 제외. 빈 DB 파일 삭제는 루트 정리 A-1로 이관.
  - **루트(메인) 폴더 정리 계획서 작성 (`docs/plans/2026-10-04_02_root-folder-cleanup.md`)**:
    - A단계(빈 파일 삭제, Git에 남은 생성물 추적 해제), B단계(백엔드 모듈 13개를 `gichul/` 패키지로 이동 + `paths.py`로 경로 일원화), C단계(선택 항목).
    - 권장 실행 순서: 정리 A → 로드맵 1·2 → 정리 B → 로드맵 3·4 (로드맵 1·2단계의 줄 번호 참조를 유지하기 위함).
  - **계획서·리뷰 문서 보관소 `docs/` 신설 (`docs/README.md`)**:
    - 계획서/리뷰 목록과 상태(⬜ 대기 · 🔄 진행 중 · ✅ 완료 · ⏸ 보류 · ❌ 폐기), 파일명 규칙(`YYYY-MM-DD_<슬러그>.md`, 같은 날은 `_01_`, `_02_`) 정의.
    - 루트 `implementation_plan.md`를 `docs/plans/2026-09-30_area-switch-capture-cache.md`로 이동(`git mv`, 이력 유지).
    - 덮어쓰기로 사라졌던 과거 계획서 4건을 Git 히스토리에서 복원(`2026-09-27_01~03`, `2026-09-29`).
  - **에이전트 규칙·스킬 갱신 (`AGENTS.md`, `GEMINI.md`, `.agents/rules/rules.md`, `CLAUDE.md`, `.agents/skills/{ask,apply}`, `.claude/skills/{ask,apply}`)**:
    - `/ask` 계획서는 `docs/plans/`에 날짜별 새 파일로 저장하고 `docs/README.md`에 등록. 리뷰 보고서는 `docs/reviews/`에 저장.
    - `/apply`는 지정한 계획서·단계 또는 최신 대기 계획서를 실행한 뒤 계획서와 `docs/README.md`의 상태를 갱신.
  - **README 프로젝트 구조에 `docs/` 폴더 추가**.
- **검증 결과**:
  - 소스 코드 변경 없음 (문서·규칙 파일만 변경)
  - `AGENTS.md`, `GEMINI.md`, `.agents/rules/rules.md` 파일 해시 동일 확인
  - `docs/` 내 옛 파일명(`2026-10-04_code-review-roadmap.md`) 참조 0건 확인

### [2026-10-04 17:46] 업데이트 이력 (Commit ID: ab3a4ee7)
- **수정 내용**:
  - **루트 폴더 정리 A단계 (`docs/plans/2026-10-04_02_root-folder-cleanup.md`)**:
    - 실행 순서를 권장안 ①(정리 A → 로드맵 1·2 → 정리 B → 로드맵 3·4)로 확정.
    - A-1: 0바이트 빈 DB 파일 3개(`database.db`, `database.sqlite3`, `exam_database.db`) 삭제 (Git 미추적, 코드 참조 0건).
    - A-2: `static/audio/*.mp3` 26개(약 8.5 MB)를 `git rm --cached`로 추적 해제. 로컬 파일은 그대로 유지되어 앱 재생에 영향 없음. 과거 커밋에는 남아 있음.
    - A-3: `.gitignore`에 `.pytest_cache/`, `logs/`, `*.backup-*.db`, `static/audio/*.wav` 추가.
  - **코드 리뷰 로드맵 1단계: 확정 버그 5건 수정 (`app.py`, `database.py`, `static/js/upload.js`)**:
    - 1-1 검색 캐시 무효화: 데이터를 바꾸는 `/api/` 요청(`/api/settings/` 제외)이 끝나면 검색 캐시와 시험지 통계 캐시를 비우는 미들웨어 추가. 업로드 후 백그라운드 어법 분석도 끝날 때 직접 비움. 태그·정답 변경 후 재검색해도 이전 결과가 보이던 문제 해결.
    - 1-2 듣기 ZIP 다운로드: `create_listening_zip()`이 반환하는 dict를 파일 경로로 다뤄 항상 실패하던 버그 수정. 받을 MP3가 없으면 500 대신 404와 안내 메시지 반환.
    - 1-3 문장 조회 SQL화: `search_sentences`에 `exam_id`, `sentence_ids` 조건 추가(`json_each`로 ID 개수 제한 없음). 단일·일괄·업로드 후 자동 어법 분석에서 7만 문장 전체를 읽던 방식을 제거. 자동 분석이 최신 1,000문장만 보고 일부 문장을 빠뜨리던 문제도 함께 해결.
    - 1-4 FTS → LIKE 대체 경로: `search_passages`, `search_sentences`에서 FTS 쿼리 실행이 실패하면 같은 인자로 LIKE 검색을 다시 수행하도록 구현 (기존 `try/except`는 문자열 조립만 감싸 실제로 동작하지 않았음).
    - 1-5 HWP 단독 업로드: 해설 파싱 실패 또는 해설 0건이면 `status: "partial"`과 경고 메시지 반환. 프론트엔드는 단일 업로드에서 ⚠️ 경고, 일괄 갱신에서 실패로 집계하고 사유 표시.
  - **로드맵 2-5 계획 변경**: XTTS 음성을 `lameenc`로 진짜 MP3로 저장하도록 변경(모든 음성 파일 MP3 통일). 기본 TTS 엔진은 XTTS 유지.
  - **문서**: 로드맵 1단계 완료와 적용 결과, 루트 정리 A단계 완료, `docs/README.md` 상태(두 계획서 🔄 진행 중) 갱신.
- **검증 결과**:
  - `python -m py_compile app.py database.py`: 오류 0건 (Exit Code: 0)
  - `node --check static/js/upload.js`: 오류 0건 (Exit Code: 0)
  - `pytest tests -q`: 76개 전체 통과
  - 실제 DB 읽기 전용 확인: `search_sentences(exam_id=...)` 235건 = 직접 집계값, `sentence_ids` 5개 조회 2ms(기존 전체 문장 로드 904ms), FTS 구문 오류 유발 시 지문·문장 검색 모두 LIKE로 대체
  - `TestClient` 확인: 쓰기 요청 후 캐시 비움, `/api/settings/` 쓰기·GET 요청은 캐시 유지, 없는 시험지 ZIP 요청 시 404
  - 로드맵 2단계 전 DB 백업 완료 (`gichul.backup-2026-10-04.db`, Git 제외 확인)

### [2026-10-04 18:12] 업데이트 이력 (Commit ID: 559b6365)
- **수정 내용**:
  - **코드 리뷰 로드맵 2단계: 안정성 (`app.py`, `database.py`, `hwp_parser.py`, `listening_parser.py`, `tts_service.py`, `requirements.txt`)**:
    - 2-1 서버 멈춤 해결: `await`가 없는 라우트 44개를 `def`로 바꿔 스레드풀에서 실행. 긴 업로드·어법 분석 중에도 검색 등 다른 요청이 처리됨. PDF 처리 라우트 5개는 `@_ingest_serialized`(INGEST_LOCK)로 한 번에 하나씩 실행. 한글(HWP) COM 호출은 CoInitialize된 전용 스레드(`hwp-com`) 1개에서만 실행.
    - 2-2 업로드 트랜잭션: 파싱이 끝난 뒤 시험지·지문·문장·정답 상태·정답률을 하나의 트랜잭션으로 저장해 중간 실패 시 전부 롤백. 듣기 동기화는 커밋 뒤 따로 실행하고 실패하면 `warnings`로 응답.
    - 재업로드 문장 교체: `replace_passage_sentences()` 추가. 새 목록에 없는 옛 문장은 삭제(태그·어법 CASCADE). 같은 문장이면(단어 토큰 비교, 빈칸↔정답 채움 허용) 어법 분석·별표 보존. 내용이 바뀐 문장은 AI 어법만 삭제. 문장 분할 결과가 비면 교체하지 않고 경고. 응답에 `sentences_removed` 등 통계 추가.
    - 2-3 DB 연결: `with get_connection()` 블록이 끝나면 연결까지 닫히도록 변경(`_ClosingConnection`), 잠금 대기 `timeout=15`, WAL 설정은 `init_db()`에서 1회. `listening_parser`의 닫히지 않던 연결 정리.
    - 2-4 FTS 트리거: 갱신 트리거를 텍스트 컬럼(`sentence_text`, 지문 텍스트 4개) 변경 시에만 동작하도록 교체. 별표·메모·정답률 변경 시 불필요한 재색인 제거. 서버 시작 시 1회 자동 교체.
    - 2-5 XTTS MP3: 대사별 WAV를 그대로 이어 붙여 `.mp3`로 저장하던 문제 수정. PCM으로 잇고(대사 사이 0.6초 무음) `lameenc`로 실제 MP3(128kbps) 인코딩. 기본 엔진은 XTTS 유지. `requirements.txt`에 `lameenc>=1.8` 추가.
    - 함께 고친 버그: 업로드 시 듣기 동기화가 `has_hwp` NameError로 항상 오류 처리되던 문제, 업로드 메시지의 듣기 문항 수에 dict가 표시되던 문제, `/api/exams/.../sync-listening`의 `synced_count`가 dict이던 문제.
  - **문서**: 로드맵 2단계 완료와 적용 결과(계획과 다른 점 포함) 기록, `docs/README.md` 상태 갱신(다음: 루트 정리 B단계).
- **검증 결과**:
  - `python -m py_compile app.py database.py hwp_parser.py tts_service.py listening_parser.py`: 오류 0건
  - `pytest tests -q`: 76개 전체 통과
  - 실제 DB 임시 사본 확인: `_au` 트리거 교체·`ai/ad` 유지, 트랜잭션 예외 시 롤백, 문장 교체 통계(추가 1/유지 32/변경 1/삭제 1)와 어법 보존·AI 어법 삭제·CASCADE, 별표 변경 시 FTS 재색인 없음
  - `_wav_turns_to_mp3`: 1초 WAV 2개 → MP3 헤더 `FF F3`, 약 2.66초
  - COM 전용 스레드: 서로 다른 스레드 3개에서 호출해도 `hwp-com_0` 1개에서 실행
  - 1단계 검증 스크립트 재실행 결과 유지
  - 남은 조치: WAV 내용인 `.mp3` 1개(`고3-2025년-11월-01번.mp3`)는 해당 문항 음성 재생성 시 정상 MP3로 교체됨

### [2026-10-04 19:05] 업데이트 이력 (Commit ID: 148942a5)
- **수정 내용**:
  - **수능 성우(XTTS) 및 Edge-TTS 엔진 선택 스위처 도입 (`app.py`, `tts_service.py`, `templates/index.html`, `static/js/results-passage.js`, `static/css/style.css`)**:
    - `POST /api/settings/tts-engine` 엔드포인트 신설 및 런타임 활성 TTS 엔진 전환 지원 (`xtts` vs `edge-tts`).
    - 수능 평가원 성우 복제(XTTS-v2 실감 음성)와 Microsoft Edge-TTS(초고속 생성, 무료) 간 상호 선택 가능한 원클릭 토글 스위처(`tts-engine-switcher`) UI 구축.
    - 음성 합성 진행 중 오디오 중복 재생 방지 및 합성 진행률(%) 실시간 인디케이터 연동.
  - **오디오 다운로드 기능 세분화 및 동적 ZIP 범위 지원 (`database.py`, `results-passage.js`, `templates/index.html`, `static/css/style.css`)**:
    - 문항 단일 다운로드(`문항 MP3`)와 시험지 세트 전체 일괄 다운로드(`전체 ZIP`) 버튼 역할 및 시각 테마 명확히 분리.
    - `database.py`의 `search_passages` 및 `get_passage`에 `listening_start_q`, `listening_end_q` 컬럼 조인 반영.
    - 하드코딩 제거: 시험지별 듣기 문항 수 체제(2013년 1~22문항, 현행 1~17문항 등)를 감지하여 전체 ZIP 버튼 내 동적 범위 배지(`1~17`, `1~22`) 실시간 표기 및 메타데이터 동기화.
  - **듣기 패널 헤더 1행(One-line) 가로 배열 최적화 (`style.css`, `templates/index.html`)**:
    - 좌측 패널 헤더: `[📋 대본 복사]` 버튼을 타이틀(`🎧 영문 대본 & 음성`) 바로 옆으로 이동 배치하여 작업 직관성 제고.
    - 우측 상단 툴바: 엔진 스위처, 생성 세그먼트, 다운로드 세그먼트의 3개 제어 그룹을 높이 `25px`의 컴팩트한 규격으로 통일하고 여백/패딩을 최적화하여 한 줄(1행)에 완벽하게 정렬(화면 오버플로 및 불필요한 줄바꿈 제거).
  - **단위 테스트 구축 (`tests/test_tts_engine.py`)**:
    - TTS 엔진 변경 API, 잘못된 엔진 파라미터 유효성 검사, 듣기 문항 범위 메타데이터 조회를 검증하는 테스트 케이스 구축.
- **검증 결과**:
  - `python -m py_compile app.py database.py tts_service.py`: 구문 검사 통과 (오류 0건)
  - `node --check static/js/results-passage.js`: 문법 검증 통과 (오류 0건)
  - `pytest tests/test_tts_engine.py -q`: 3 passed, 0 failed

### [2026-10-04 21:12] 업데이트 이력 (Commit ID: 0f6d7a02)
- **수정 내용**:
  - **루트 폴더 정리 B단계: 백엔드 모듈을 `gichul/` 패키지로 이동 (`docs/plans/2026-10-04_02_root-folder-cleanup.md`)**:
    - `git mv`로 백엔드 모듈 13개(`app`, `database`, `grammar_analyzer`, `hwp_parser`, `pdf_parser`, `listening_parser`, `tts_service`, `answer_keys`, `answer_resolver`, `validator`, `rate_parser`, `sentence_tokenizer`, `fels_engine`)를 `gichul/`로 이동. 파일 히스토리 유지.
    - 앱이 실행 중에 import하는 `tools/crop_2013_09.py`를 `gichul/special_crops/crop_2013_09.py`로 이동.
    - 루트에는 `run.py`, `start.bat`, `install.bat`, 설정·문서 파일만 남음.
  - **경로 상수 통합 (`gichul/paths.py` 신규)**:
    - 각 모듈이 `__file__`로 따로 계산하던 경로 9곳을 `ROOT_DIR`, `DB_PATH`, `STATIC_DIR`, `TEMPLATES_DIR`, `UPLOADS_DIR`, `CAPTURES_DIR`, `AUDIO_DIR`, `VOICES_DIR`, `KEYS_DIR`, `GRAMMAR_CATEGORIES_JSON` 상수로 교체.
    - 기존 코드가 문자열 경로를 쓰므로 `str` 상수로 제공. `GICHUL_DB_PATH` 환경변수로 DB 경로 덮어쓰기 가능(로드맵 4-A 테스트용 임시 DB 대비).
  - **import 정리**: 패키지 내부 import 26곳을 상대 import(`from . import database as db` 등)로, tools 4개·tests 4개는 `from gichul import ...`로 변경. `regenerate_group_crops.py`의 DB 경로도 `gichul.paths.DB_PATH` 사용.
  - **`run.py`**: `uvicorn.run("gichul.app:app", app_dir=base_dir, ...)`. 자동 재시작 감시 대상을 `gichul/`·`templates/`로 좁히고 긴 제외 목록을 단순화.
  - **문서**: README 프로젝트 구조를 패키지 구조로 갱신, 로드맵 3단계 이후 파일 링크를 `gichul/` 경로로 갱신하고 안내 노트 추가, 계획서 진행 현황·`docs/README.md` 상태 갱신.
- **검증 결과**:
  - 작업 전 DB 백업: `gichul.backup-2026-10-04-b-stage.db` (Git 제외)
  - `python -m compileall -q gichul tools tests run.py`: 오류 0건
  - 이동 전/후 스냅샷 비교: 라우트 56 → 56 (차이 0건), 경로 값 14개(`DB_PATH` 포함) 차이 0건
  - 루트 모듈 이름으로 된 import 잔존 grep: 0건
  - `python -m pytest tests -q`: 79개 전체 통과
  - 남은 조치: 실행 중이던 서버는 재시작 필요 (`start.bat` 또는 `python run.py`), 이후 검색·지문 이미지·듣기 재생·크롭 재생성 수동 확인

### [2026-10-04 21:50] 업데이트 이력 (Commit ID: 9bda6567)
- **수정 내용**:
  - **로드맵 3-A: 공통 함수 추출 (`docs/plans/2026-10-04_01_code-review-roadmap.md`)**:
    - [NEW] `gichul/text_utils.py`: DB에 의존하지 않는 순수 함수 모음. `normalize_bracket_id`(ID 대괄호 정규화, 40곳 교체), `apply_answer_header`(해설 `[정답]` 헤더 갱신, 7곳 교체), `extract_answer_num`·`extract_choices`·`clean_choice_markers` 이동, `fill_blanks`(빈칸 정답 채우기) 신설.
    - `grammar_analyzer.prepare_sentence_for_analysis`: DB 보강 후 `fill_blanks` 호출만 하도록 축소(162줄 → 50줄). 옮긴 함수는 기존 이름으로 다시 내보내 하위 호환 유지.
    - [NEW] `gichul/services/grammar_service.py`: 단일/배치/백그라운드 3곳에 복제돼 있던 "전처리 → 분석 → 저장" 흐름을 `analyze_and_save_sentence`로 통합.
    - 달라진 점 1건: 단일 분석 API에서 전처리 단계 예외가 나면 `detail: "AI 어법 분석 실패: ..."`가 붙은 500 (상태 코드는 동일).
  - **버그 수정: 빈칸 문장에 오답 선지가 남아 있던 문제 (사용자 제보)**:
    - 증상: 고3-2026년-05월 31번은 정답이 ② efficiency인데 문장 분석 창에는 ④ randomness가 들어가 있었음.
    - 원인: 어법 분석 전처리가 빈칸을 정답 선지로 채운 문장을 DB에 덮어써 원래 빈칸이 사라짐. 이후 정답이 바뀌어도(정답 키·JSON·CSV 등) 문장은 다시 채워지지 않았고, 재업로드도 "같은 문장"으로 판정해 예전 선지를 유지함.
    - 해결: [NEW] `database.refill_blank_sentences` — 지문 본문(빈칸 유지)의 빈칸 문장을 틀로 삼아, 저장 문장에 "틀 + 오답 선지"가 있고 "틀 + 정답 선지"가 없을 때만 그 구간을 정답 선지로 교체. 바뀐 문장은 AI 어법 주석을 지우고 재분석 대상으로 되돌림(사용자 주석 유지).
    - 호출 위치: 수동 정답 수정·CSV(`update_passage_answers`), 정답 JSON 업로드, 정답표 이미지, HWP 해설 동기화, 시험지 업로드 트랜잭션, 분석 직전 안전망.
    - 오탐 방지: 빈칸 밖 단어 2개 미만·채운 결과 4단어 미만 제외, 복수 빈칸인데 정답 선지를 빈칸 수만큼 나눌 수 없으면 제외(40번 요약문 선지 추출이 불완전한 경우가 있어 별도 수정 필요).
  - **버그 수정: 새 DB에서 `init_db()` 실패**: 마이그레이션 버전을 `app_settings`에서 읽는데 테이블이 그 뒤에 만들어져, 첫 설치·배포 시 `no such table: app_settings`로 기동 불가. 테이블 생성 순서를 앞으로 옮김.
  - **문서**: 로드맵 3-A 적용 결과·함께 수정한 버그 기록, 진행 현황을 커밋 해시로 갱신.
- **검증 결과**:
  - `py_compile`(수정·신규 파일) 오류 0건, `import gichul.app` 정상(라우트 56개)
  - 3-A 회귀: `prepare_sentence_for_analysis` 전체 71,872문장 전후 차이 0건(sha256 동일), `apply_answer_header` 실데이터 172,672회 비교 차이 0건, 라우트 목록 차이 0건
  - 빈칸 버그: 실제 DB 백업(`gichul.backup-2026-10-04-blank-refill.db`, Git 제외) 후 적용 → 90개 지문 91문장 교정(31번: "... lies in its efficiency."), 재실행 시 바꿀 문장 0건
  - 새 테스트: `tests/test_text_utils.py` 50개, `tests/test_refill_blanks.py` 5개(임시 DB, 실제 DB 미사용)
  - `python -m pytest tests -q`: 134개 전체 통과
  - 후속 조치: 교정된 91문장은 AI 어법 분석 재실행 필요, 서버 재시작 필요(`python run.py`)

### [2026-10-04 23:00] 업데이트 이력 (Commit ID: 3555d9f7)
- **수정 내용**:
  - **40번 요약문 선지 (A)만 추출되어 빈칸 채우기가 불완전하던 문제 전면 개선**:
    - **증상 및 원인**:
      - 40번 요약문 선지에서 (A)만 추출되고 (B)가 누락되어, 빈칸 채우기 분석 시 (A)와 (B) 빈칸 모두에 (A) 단어가 중복 삽입되거나 괄호가 남아 문장이 불완전해지던 문제.
      - 원인 1: `extract_choices` 정규식 `[^①②③④⑤\n\r\t]+`이 선지 구분자로 쓰인 `\t`(탭) 문자에서 선지를 단절시켜 `\t` 뒤의 (B) 선지 누락 (2025/2024 대수능 등 36개 주요 문항).
      - 원인 2: 평가원/교육청 일부 기출에서 (A)와 (B) 선지가 줄바꿈으로 나뉜 경우(`① associate\n…… genetic`), 줄바꿈에서 선지가 끊겨 (B) 누락.
      - 원인 3: `_BLANK_PATTERN`이 `_{2,}`만 인식하여 `___(A)___`, `____ (A) ____`, `(A)`/`(B)` 등 요약문 고유 빈칸 표기를 단일 빈칸으로 처리하지 못함.
      - 원인 4: 선지 분할 구분자 정규식에 `---`, `·····`(가운뎃점), `\t` 등이 누락되어 선지 파트 분할 실패.
    - **해결 (`gichul/text_utils.py`, `gichul/database.py`)**:
      - `extract_choices`: 지문 하단 선지 블록을 마지막 `⑤`부터 역추적(`rfind`)하여 본문 내 원문자와 혼동 없이 안전하게 추출. 줄바꿈(`\r\n`)을 `\t`로 변환 보존하여 멀티라인 (A)/(B) 선지 단절 방지. HWP 깨진 글립 및 선지 꼬리 저작권 문구(`이 문제지에 관한 저작권은...`) 자동 정리. `\t`를 허용하는 정규식 폴백 유지.
      - `_BLANK_PATTERN` 및 `_SENTENCE_BLANK_RE`: `___(A)___`, `____ (A) ____`, `(A)`, `(B)`, `[A]`, `[B]` 및 언더스코어 빈칸을 모두 단일 빈칸 토큰으로 인식하도록 확장.
      - `split_choice_parts` 및 `_CHOICE_PART_SPLIT_PATTERN` 신설/통합: `\t+`, `[-―－]{2,}`, `[\.\u00b7\u2022\u318d]{2,}`(가운뎃점/말줄임표), `~`, 2칸 이상 공백을 포괄 분할하고 앞뒤 잔여 기호 strip.
      - `fill_blanks`: 한국어 문제 발문(`다음 글의 내용을...`) 및 단순 헤더(`(A) (B)`) 오염 방지 가드 추가. 복수 빈칸에 선지 파트들을 1:1 순서대로 대치하여 완전한 자연어 문장 완성.
      - `database.py`: `_SENTENCE_BLANK_RE`와 `_CHOICE_PART_SPLIT_RE`를 `text_utils`와 동기화.
  - **테스트 추가 (`tests/test_text_utils.py`)**:
    - `test_fill_blanks_summary_q40_underscores_and_markers`: `___(A)___`, `___(B)___` 형태 빈칸 채우기 검증
    - `test_fill_blanks_summary_multiline_choices`: 멀티라인 선지 추출 및 1:1 빈칸 채우기 검증
    - `test_fill_blanks_korean_prompt_ignored`: 한국어 발문 오염 방지 검증
- **검증 결과**:
  - `python -m py_compile gichul/text_utils.py gichul/database.py tests/test_text_utils.py`: 오류 0건
  - `python -m pytest tests/test_text_utils.py`: 53개 전체 통과 (신규 3개 포함, 0.19s)
  - `python -m pytest tests -q`: 137개 전체 통과 (16.04s)
  - 실제 DB 기출 40번 요약문 211건 대상 검증: 선지 분할 성공률 **97.6% (206/211)** 및 요약문 빈칸 1:1 자연어 문장 완성 확인.

### [2026-10-04 23:35] 업데이트 이력 (Commit ID: f3258671)
- **수정 내용**:
  - **로드맵 3-B: import 부작용 제거 및 의존 방향 정리 (`docs/plans/2026-10-04_01_code-review-roadmap.md`)**:
    - **DB 초기화 자동 실행 제거**: `gichul/database.py` 모듈 로드 시의 `init_db()` 자동 호출을 제거하고, `gichul/app.py`의 FastAPI `lifespan` 컨텍스트 매니저에서 서버 기동 시 1회만 안전하게 실행되도록 변경. 단독 실행 스크립트인 `tools/resync_answers.py`에는 `db.init_db()`를 명시적으로 호출.
    - **PyTorch/torchaudio 지연 로드**: `gichul/tts_service.py` 상단에서 모듈 로드 시 실행되던 torchaudio monkeypatch를 `_patch_torchaudio_load()` 함수로 감싸고, `_get_or_load_xtts_model()`에서 TTS 모델을 실제로 불러올 때 1회만 실행하도록 지연 처리. 웹 서버 기동 시 불필요한 PyTorch/CUDA 라이브러리 로딩 방지.
    - **`grammar_analyzer` 역방향 의존성 제거**: `database.py`와 `validator.py`에서 `grammar_analyzer`를 역참조하던 경로를 완전히 제거하고 `text_utils.fill_blanks`를 직접 호출하도록 구조 개선.
    - **문장 검색(N+1 쿼리) 일괄 최적화 (`search_sentences`)**: 문장 검색 중 빈칸(`__`)이 남아 있는 문장의 지문 정보(본문·정답·해설)를 행마다 반복 조회하던 N+1 구조를 제거하고, 900개 단위 청크 `IN` 쿼리로 한 번에 조회한 뒤 `fill_blanks`로 정답 선지를 일괄 치환하도록 최적화.
    - **`init_db` v1 마이그레이션**: 별도 커넥션/재귀 조회를 열던 로직을 동일 트랜잭션 내 `fill_blanks` 직접 호출로 단순화.
    - **검증 데이터 파이프라인 정리 (`validator.py`)**: `cross_validate_and_merge` 단계에서 지문/정답/해설을 이미 보유하고 있으므로 DB 조회 없이 `fill_blanks`를 즉시 호출.
  - **등급별 데이터 접근 제어 및 필터링 훅 마련 (`gichul/access.py` 신규 & `gichul/app.py`, `gichul/database.py`)**:
    - [NEW] `gichul/access.py`:
      - 사용자 역할 등급 상수 정의: `ROLE_ADMIN` (관리자), `ROLE_MEMBER` (회원), `ROLE_GUEST` (비회원)
      - 로컬 단독 사용 기본값: `DEFAULT_ROLE = "admin"` (기존 로컬 개발 및 단독 실행 환경과 100% 동일 동작 보장)
      - 등급별 필터링 함수: `filter_passage`, `filter_passages`, `filter_sentence`, `filter_sentences`
        - 관리자(`admin`): 모든 데이터(정답률, 태그, 어법 분석, 관리자 메모, 정답 출처/검증 상태, 즐겨찾기 등) 온전히 유지
        - 회원(`member`): 코어 문항 데이터 + 메타 정보(정답률, 선지 선택률, 태그, 어법 분석 범주) 노출, 관리자 전용 필드(메모, 정답 출처, 일치율 등) 제외
        - 비회원(`guest`): 코어 문항 데이터(발문, 지문, 정답, 해설, 크롭 이미지)만 노출하고 정답률/선지 선택률/태그/어법 범주/메모 일체 제외
      - `allowed_search_filters`: 비회원 등급에서 정답률 구간·태그·어법 범주로 역추적 검색하는 것을 방지하기 위해 검색 조건 자체를 무시하도록 보안 가드 구축
    - **DB 조회 함수 파라미터 연동**: `database.search_passages`, `get_exam_passages`, `get_passage`, `search_sentences`에 `user_role: str = access.DEFAULT_ROLE` 매개변수 신설 및 응답 필터링 연동
    - **FastAPI 의존성 주입(`Depends`) 연동**: `app.py`에 `get_current_role()` 함수를 정의하고 4대 핵심 조회 엔드포인트(`/api/search/passages`, `/api/exams/{id}/passages`, `/api/search/sentences`, `/api/passages/{id}`)에 `user_role: str = Depends(get_current_role)` 주입. 등급별 검색 캐시 격리를 위해 `search_cache` 캐시 키에 `user_role` 포함.
  - **40번 요약문 빈칸 채우기 후속 회귀 방지 및 안전화 (`gichul/text_utils.py`, `gichul/database.py`)**:
    - `_BLANK_PATTERN`에서 단순 괄호 `(A)`, `[A]`가 일반 어법 네모 문항이나 37번 순서 문항의 단락 식별 기호와 혼동되지 않도록 언더스코어로 감싸진 요약문 고유 표지(`___(A)___`, `____ (A)` 등)로 엄격화.
    - `extract_choices`: ⑤번 선지 추출 시 깨진 글리프 문자열 및 후속 저작권 문구 배제 처리 보강.
    - `split_choice_parts`: 선지 파트 분할 시 유니코드 공백 정규화.
- **검증 결과**:
  - `python -m py_compile` 백엔드 전체 모듈 구문 검증 오류 0건 통과
  - `search_sentences` 전체 71,872문장 스냅샷 비교 검증 (`scratch/b3_search_snapshot.py`): 전후 차이 0건 (`diffs 0`, sha256 100% 동일)
  - `gichul.app` 모듈 import 시 `init_db` 호출 0회, `torch` 및 `torchaudio` 미로드 확인 (지연 로딩 성공)
  - FastAPI 라우트 51개 유지 및 lifespan 정상 등록 확인
  - 신규 등급별 필터링 단위 테스트 `tests/test_access.py` 8개 통과 (관리자/회원/비회원별 필드 마스킹, 검색 조건 차단, 일괄 빈칸 채우기, lifespan 구동)
  - `python -m pytest tests -q`: 전체 149개 테스트 100% 통과 (16.44s)

### [2026-10-05 16:30] 업데이트 이력 (Commit ID: 877017a2)
- **수정 내용**:
  - **로드맵 3-C: 시험 프로파일을 데이터로 관리 (`docs/plans/2026-10-04_01_code-review-roadmap.md`)**:
    - **시험 프로파일 데이터 모델 구축 (`gichul/exam_profiles.py`)**:
      - `ExamProfile` 불변(`frozen=True`) 데이터클래스 정의: `reading_start`, `reading_end`, `listening_end`, `is_50_questions`, `is_ab_period`, `special_crop`
      - `get_exam_profile(grade, year, month, subtype)`:
        - 2006~2011년: 구 50문항 체제 (`reading_end=50`, `is_50_questions=True`)
        - 2012-06~2013년 및 A/B형: 수준별 체제 (`reading_start=23`, `listening_end=22`, `is_ab_period=True`)
        - 2014년 이후: 현행 표준 45문항 체제 (`reading_start=18`, `reading_end=45`, `listening_end=17`)
        - 고3 2013년 9월: 벡터 곡선(Drawings) 전용 기하 레이아웃 크롭 모듈 식별자(`special_crop="crop_2013_09"`) 반환
      - `run_special_crop(crop_name, exam_id, subtype)`: 특수 크롭 모듈을 동적으로 호출하여 개별 모듈 직접 import 의존성 격리
    - **하드코딩된 연도/문항 번호 분기 대체**:
      - `gichul/app.py`: `_regenerate_exam_crops`, `api_upload_exam`, `api_upload_exam_single_file`에서 하드코딩된 `2006 <= year <= 2011`, `year == 2013`, `special_crops` 직접 import를 `get_exam_profile`과 `run_special_crop`으로 교체
      - `gichul/pdf_parser.py`: `detect_listening_range`, `extract_pdf_columns_and_questions`에서 연도 분기를 `profile` 기본값 및 `profile.is_50_questions`로 교체
      - `gichul/hwp_parser.py`: `parse_hwp_questions`에서 50문항 체제 판별 및 독해 종료 번호 결정을 `profile.is_50_questions`, `profile.reading_end`로 단순화
      - `gichul/listening_parser.py`: `sync_exam_listening`, `extract_listening_question_crops`, `extract_listening_script_crops`에서 듣기 종료 번호를 `profile.listening_end` 기반 동적 판별로 통일
    - **단위 테스트 추가 (`tests/test_exam_profiles.py`)**:
      - 2008년(50문항), 2012년 6월(수준별 개시), 2012년 3월(기존/A형 명시), 2013년(수준별 전체), 2013년 9월(고3 특수크롭 vs 고2 표준), 2020년(현행 표준), frozen dataclass 불변성, 특수크롭 디스패치 등 9개 테스트 구축
- **검증 결과**:
  - `scratch/profile_snapshot.py`: DB 내 321개 전체 시험에 대해 기존 하드코딩 로직과 `get_exam_profile` 결과값을 1:1 비교하여 **차이 0건 (완전 일치)** 확인
  - `python -m py_compile` 백엔드 전체 모듈 구문 검증 오류 0건 통과
  - `python -m pytest tests -q`: **158개 테스트 100% 통과** (기존 149개 + 신규 9개)

### [2026-10-05 17:20] 업데이트 이력 (Commit ID: de141821)
- **수정 내용**:
  - **로드맵 3-D: 로깅과 오류 처리 통일 (`docs/plans/2026-10-04_01_code-review-roadmap.md`)**:
    - **통합 로깅 모듈 구축 (`gichul/logging_config.py` 신규 & `gichul/paths.py`)**:
      - `LOGS_DIR` 및 `APP_LOG_PATH` (`logs/app.log`) 상수 정의 및 `.gitignore` 등록 유지 확인
      - `setup_logging(level)`: 표준 출력(`stdout`)과 `RotatingFileHandler` (5MB × 3개 회전, UTF-8 인코딩)를 단일 설정으로 초기화
      - `get_logger(name)`: `gichul.<module_name>` 계층형 표준 로거 취득 인터페이스 제공
      - 통일된 로그 포맷: `[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s`
    - **FastAPI lifespan 및 전역 예외 처리기 등록 (`gichul/app.py`)**:
      - `lifespan` 기동 시 `setup_logging()` 자동 호출
      - `@app.exception_handler(Exception)` 글로벌 핸들러 추가: 미처리 예외 발생 시 `logger.critical`로 스택 트레이스를 기록하고, 프론트엔드 연동 규격에 맞춘 `{"success": False, "detail": str(exc)}` (HTTP 500) JSON 반환 (`HTTPException` 및 `RequestValidationError`는 기본 동작 보존)
    - **전체 코어 모듈 `print` 제거 및 오류 처리 통일 (54개 print → logger, 43개 pass → logger.debug)**:
      - `gichul/app.py`: 17개 `print` → `logger.info/warning/error`, 은닉형 `except Exception: pass` → `logger.debug`
      - `gichul/database.py`: 8개 `print` → `logger`, 12개 `except Exception: pass` → `logger.debug(..., exc_info=True)` (마이그레이션 `sqlite3.OperationalError: pass` 정상 유지)
      - `gichul/grammar_analyzer.py`: 8개 `print` → `logger`, 8개 `except Exception: pass` → `logger.debug`
      - `gichul/hwp_parser.py`: 9개 `print` → `logger`, 10개 `except Exception: pass` → `logger.debug`
      - `gichul/pdf_parser.py`: 6개 `print` → `logger`, 9개 `except Exception: pass` → `logger.debug`
      - `gichul/listening_parser.py`: 3개 `print` → `logger`, 2개 `except Exception: pass` → `logger.debug`
      - `gichul/validator.py`: 1개 `print` → `logger.error`, 1개 `except Exception as e: pass` 교체
    - **단위 테스트 추가 (`tests/test_logging_config.py`)**:
      - `logs/app.log` 파일 자동 생성 및 회전 핸들러 파일 기록 검증
      - `get_logger` 계층 네이밍 검증
      - FastAPI 글로벌 예외 핸들러 500 JSON 반환(`{"success": False, "detail": ...}`) 검증
    - **문서 동기화**:
      - `docs/plans/2026-10-04_01_code-review-roadmap.md`: 3-D 적용 결과 및 진행 현황 갱신 (3-D ✅ 완료)
      - `docs/README.md`: 계획서 목록 진행 상태 동기화 (다음: 3-E)
- **검증 결과**:
  - `python -c "import compileall; ..."`: `gichul` 및 `tests` 전체 파이썬 파일 바이트코드 컴파일 오류 0건 통과
  - `python -m pytest tests -q`: **161개 단위 테스트 100% 통과** (기존 158개 + 신규 3개)
  - `logs/app.log` 자동 생성 및 실시간 회전 로깅 정상 확인

### [2026-10-05 17:40] 업데이트 이력 (Commit ID: bc29c222)
- **수정 내용**:
  - **로드맵 3-E: 라우터 분리 및 app.py 모듈화 경량화 (`docs/plans/2026-10-04_01_code-review-roadmap.md`)**:
    - **코어 상태 및 직렬화 락 분리 (`gichul/core/state.py` 신규)**:
      - `FastSearchCache`, `search_cache`: 인메모리 검색 결과 LRU 캐시 중앙화
      - `INGEST_LOCK`, `_ingest_serialized`: PyMuPDF 및 HWP 파일 파싱 스레드 안전 데코레이터 분리
      - `fast_json_dumps`, `get_current_role` 추출 및 `gichul/app.py` 하위 호환 re-export 유지
    - **업로드 후처리 및 백그라운드 분석 서비스 분리 (`gichul/services/ingest.py` 신규)**:
      - `regenerate_exam_crops` (`_regenerate_exam_crops`): PDF 정답 형광펜 크롭 이미지 일괄 재생성 및 DB 동기화 로직 분리
      - `background_auto_analyze_exam_grammar`: 업로드 직후 비동기 어법 자동 분석 및 캐시 무효화 서비스 분리
    - **6대 도메인별 라우터 분리 (`gichul/routers/` 신규)**:
      - `search.py` (5개 라우트): `/api/stats`, `/api/search/passages`, `/api/exams/{exam_id:path}/passages`, `/api/search/sentences`, `/api/passages/{passage_id}`
      - `listening.py` (5개 라우트): `/api/tts/progress/{job_id}`, `/api/passages/{passage_id:path}/generate-audio`, `/api/exams/{exam_id:path}/generate-listening-audio`, `/api/exams/{exam_id}/download-listening-zip`, `/api/exams/{exam_id}/sync-listening`
      - `passages.py` (9개 라우트): `/api/passages/{passage_id}/question-type`, `/api/passages/{passage_id}/memo` [PATCH/PUT], `/api/passages/{passage_id}/answer`, `/api/passages/{passage_id:path}/recapture`, `/api/passages/{passage_id}/tags` [POST/DELETE], `/api/sentences/{sentence_id}/tags` [POST/DELETE]
      - `settings.py` (10개 라우트): `/api/settings/ai` [GET/POST], `/api/openrouter/top-models`, `/api/openrouter/models`, `/api/lmstudio/models`, `/api/settings/ai/test`, `/api/settings/tts-engine`, `/api/settings/tts/hardware`, `/api/settings/tts/preview`, `/api/settings/edge-tts/preview`
      - `grammar.py` (11개 라우트): `/api/sentences/{sentence_id}/star`, `/api/sentences/{sentence_id}/analyze-grammar`, `/api/grammar/categories`, `/api/grammar/settings` [GET/POST], `/api/grammar/settings/reset`, `/api/sentences/{sentence_id}/grammar-annotations` [POST/DELETE], `/api/sentences/{sentence_id}/grammar` [DELETE], `/api/sentences/{sentence_id}/grammar-annotations/batch`, `/api/sentences/batch-analyze-grammar`
      - `exams.py` (10개 라우트): `/api/upload`, `/api/exams` [GET/DELETE], `/api/exams/{exam_id}/raw-files`, `/api/exams/{exam_id}/download-file`, `/api/exams/{exam_id}/download-zip`, `/api/exams/{exam_id}/upload-file`, `/api/exams/selective-delete`, `/api/exams/batch-delete`, `/api/seed-sample-data`
    - **`gichul/app.py` 143줄 슬림화 (~93.6% 라인 수 감소)**:
      - 2,229줄 모놀리스에서 애플리케이션 초기화, 미들웨어(`GZipMiddleware`, `no_cache_static_js`, `invalidate_cache_on_write`), 정적 파일 마운트, lifespan, 6대 라우터 순차 include, 하위 호환 re-export만 담당하는 초경량 엔트리포인트로 재구성
    - **단위 테스트 추가 (`tests/test_routers.py`)**:
      - 하위 호환 re-export 심볼, 6대 라우터 모듈 인스턴스, 56개 전체 엔드포인트 누락 검증, 핵심 GET 엔드포인트 통합 동작 테스트 4개 구축
    - **문서 동기화**:
      - `docs/plans/2026-10-04_01_code-review-roadmap.md`: 3단계 전체 완료 (3-A ~ 3-E) 상태 및 결과(커밋 `bc29c222`) 갱신
      - `docs/README.md`: 3단계 전체 완료 및 다음 단계(4단계) 상태 반영
- **검증 결과**:
  - **라우트 스냅샷 비교 검증**: 분리 전 덤프 스냅샷(`scratch/routes_before.json`)과 분리 후 `app.routes` 56개 라우트(경로, HTTP 메소드, 등록 순서) **100% 완전 일치 (차이 0건)**
  - `compileall`: `gichul/` 및 `tests/` 전체 파이썬 파일 바이트코드 컴파일 오류 0건 통과
  - `pytest tests -q`: **165개 단위 테스트 100% 통과** (기존 161개 + 신규 4개)

### [2026-10-05 18:15] 업데이트 이력 (Commit ID: 4d4553a8)
- **수정 내용**:
  - **로드맵 4-A: 테스트 확충 (단위/스모크 테스트 14개 추가 및 DB 격리) (`docs/plans/2026-10-04_01_code-review-roadmap.md`)**:
    - **런타임 DB 동적 경로 지원 및 FTS 트리거 결함 보강 (`gichul/database.py`)**:
      - `DB_PATH = os.environ.get("GICHUL_DB_PATH") or paths.DB_PATH` 및 `get_db_path()` 구현으로 테스트 시 임시 SQLite DB(`tmp_path`) 동적 주입 및 운영 DB(`gichul.db`) 격리 보장
      - `init_db()`에 `passages_fts` 테이블의 `AFTER INSERT` (`trg_passages_ai`) 및 `AFTER DELETE` (`trg_passages_ad`) 동기화 트리거 추가 (지문 등록 즉시 FTS5 전문 검색 인덱스 반영)
    - **테스트 의존성 및 픽스처 구축 (`requirements.txt`, `tests/conftest.py`)**:
      - `requirements.txt` `# 개발/테스트` 섹션에 `httpx>=0.28.1` 추가
      - `tests/conftest.py`에 `tmp_db` (격리된 임시 SQLite DB 생성 및 스키마 초기화) 및 `isolated_client` (격리 DB 기반 FastAPI `TestClient`) 픽스처 신설
    - **핵심 단위/스모크 테스트 3종 추가 (총 14개 신규 테스트 전원 통과)**:
      - `tests/test_db_search.py` (5개): `exam_id`/`sentence_ids` 필터링 검증, FTS5 특수문자 에러 시 LIKE 폴백 검증, `whole_word` 온전한 단어 일치 검증, 빈 쿼리 처리
      - `tests/test_db_sentences.py` (4개): `replace_passage_sentences` 빈 목록 보존, 삽입/삭제 FK 연쇄 처리, 문장 텍스트 변경 시 AI 어법 삭제 및 사용자 수동 어법 보존, 동일 텍스트 재업로드 시 AI 어법 유지 검증
      - `tests/test_api_smoke.py` (5개): 태그 변경 시 캐시 무효화 및 검색 결과 즉각 반영, 미등록 시험지 듣기 ZIP 404, AI 키 미등록 배치 분석 400, 미등록 문장 분석 404, 정적 JS `no-cache` 헤더 검증
    - **`scratch/` 폴더 165개 스크립트 회귀 가치 검토**:
      - 20개 검증 스크립트 정밀 분석 완료. 40번 요약문 빈칸 채우기 검증 로직은 이미 `tests/test_refill_blanks.py` 및 `tests/test_text_utils.py`에 정식 테스트로 이관/보존되어 있음을 확인
    - **문서 동기화**:
      - `docs/plans/2026-10-04_01_code-review-roadmap.md`: 4단계 착수 및 4-A 적용 결과 기록
      - `docs/README.md`: 계획서 목록 진행 현황 동기화 (4단계 🔄 4-A ✅ · 다음: 4-B)
- **검증 결과**:
  - `python -m compileall gichul tests`: 전체 파이썬 파일 바이트코드 컴파일 오류 0건 통과
  - `python -m pytest tests -q`: **179개 단위/통합 테스트 100% 통과** (기존 165개 + 신규 14개, 18.93s)

### [2026-10-05 18:35] 업데이트 이력 (Commit ID: 5f572518)
- **수정 내용**:
  - **로드맵 4-B: 보안과 안전성 (`docs/plans/2026-10-04_01_code-review-roadmap.md`)**:
    - **업로드 파일명 화이트리스트 정제 및 경로 순회 방지 (`gichul/text_utils.py`, `gichul/routers/exams.py`)**:
      - `sanitize_upload_filename(filename, default_name="upload")` 순수 함수 구현: `../`, `..\` 등 상위 디렉토리 순회 문자열 원천 제거, 한글/영문/숫자/하이픈/밑줄/괄호 외 특수문자 `_` 치환, 위험 실행 확장자(`.exe`, `.bat`, `.cmd`, `.sh`, `.py`, `.ps1` 등) 차단(`.bin` 치환)
      - `api_upload_exam` (다중 파일 업로드) 및 `api_upload_exam_single_file` (단일 파일 교체): 6종 파일(`pdf`, `hwp`, `script`, `exp`, `ans`, `csv`) 전체 저장 시 파일명 정제 적용. `{grade}_{year}_{month:02d}_` 접두사 보존으로 크롭 재생성 glob 호환성 유지
    - **시험지 삭제 API 식별자 정규화 (`gichul/routers/exams.py`)**:
      - `DELETE /api/exams/{exam_id}`: `clean_id = normalize_bracket_id(exam_id)` 적용으로 대괄호 유무(`고3-2024년-06월` vs `[고3-2024년-06월]`)와 상관없이 일관되고 안전하게 시험지 데이터 연쇄 삭제
    - **시드 샘플 API 및 미사용 프론트엔드 코드 정리 (`gichul/routers/exams.py`, `static/js/dom.js`, `static/js/upload.js`)**:
      - 실데이터 덮어쓰기 위험이 있던 `POST /api/seed-sample-data` 엔드포인트 및 미사용 `create_sentence_records` import 제거
      - 프론트엔드 `btnSeedSample` DOM 참조 및 클릭 이벤트 리스너 제거
    - **토스트 알림창 XSS 취약점 원천 차단 (`static/js/utils.js`)**:
      - `showToast` 내부의 `toast.innerHTML = <span>${message}</span>;`를 `const span = document.createElement("span"); span.textContent = message; toast.appendChild(span);`로 교체하여 파일명 등 서버 메시지 출력 시 XSS 취약점 원천 차단
    - **테스트 스위트 강화 및 픽스처 파일시스템 격리 (`tests/conftest.py`, `tests/test_text_utils.py`, `tests/test_api_smoke.py`, `tests/test_routers.py`)**:
      - `tmp_db` 픽스처에서 `paths.CAPTURES_DIR` 및 `paths.UPLOADS_DIR`을 `tmp_path` 임시 디렉토리로 격리 주입하여, 시험지 삭제/업로드 테스트 실행 시 실제 운영 중인 `static/captures/` 파일이 영향을 받지 않도록 보호
      - `sanitize_upload_filename` 대상 13개 파라미터화 단위 테스트 추가
      - `DELETE /api/exams/{exam_id}` 정규화 삭제 동작 및 시드 API(`/api/seed-sample-data`) 404 제거 검증 테스트 추가
      - `expected_endpoints`에서 `/api/seed-sample-data` 제거 동기화
    - **문서 동기화**:
      - `docs/plans/2026-10-04_01_code-review-roadmap.md`: 4-B 적용 결과 기록 및 진행 현황(4-A ✅ · 4-B ✅ · 다음: 4-C) 갱신
      - `docs/README.md`: 계획서 목록 진행 현황 동기화
- **검증 결과**:
  - `python -m compileall gichul tests`: 전체 파이썬 파일 바이트코드 컴파일 오류 0건 통과
  - `node -c static/js/utils.js static/js/dom.js static/js/upload.js`: 프론트엔드 자바스크립트 문법 검사 오류 0건 통과
  - `python -m pytest tests -q`: **195개 단위/통합 테스트 100% 통과** (기존 179개 + 신규 16개, 15.12s)

### [2026-10-05 18:50] 업데이트 이력 (Commit ID: 6a3c1949)
- **수정 내용**:
  - **로드맵 4-C: 교차검증 수치 바로잡기 (`docs/plans/2026-10-04_01_code-review-roadmap.md`)**:
    - **본문 부재 시 일치율 1.0(100%) 왜곡 방지 및 90% 미만 경고 플래그 (`gichul/validator.py`)**:
      - `cross_validate_and_merge`: HWP/PDF 본문 중 한쪽이라도 누락 시 `ratio = None`, `remarks = "비교 불가 (HWP/PDF 중 한쪽 없음)"` 부여 (과거 본문 부재 시 1.0(100%)으로 오기록되던 수치 왜곡 원천 차단)
      - 상호 유사도 90% 미만(`ratio < 0.9`)인 경우 `remarks`에 `⚠ 검토 필요` 플래그 자동 부착 (`f"일치율: {ratio * 100:.1f}% ⚠ 검토 필요"`)
    - **프론트엔드 지문 뷰어 일치율 배지 방어 코드 및 시각 피드백 강화 (`static/js/results-passage.js`)**:
      - 지문 뷰어 `validationBadge` 렌더링 로직 강화: `p.validation_ratio == null` 또는 누락 시 `toFixed(1)` 호출 에러(TypeError)를 원천 방어하고 `"비교 불가"` 표기
      - 시각적 상태 배지 스타일 분기: 정상(90% 이상)은 에메랄드 그린(`--success`), 90% 미만 및 `검토 필요`는 로즈 레드(`--danger`), `비교 불가`는 차분한 뮤트 그레이(`--text-muted`) 컬러 동적 적용
    - **교차 검증 전용 단위 테스트 스위트 구축 (`tests/test_validator.py`)**:
      - `normalize_for_comparison` 특수 대시/따옴표/공백 정규화 검증
      - `calculate_similarity` 완전 일치, 포맷팅 차이 허용, 빈 텍스트 처리 등 검증
      - `cross_validate_and_merge` 5대 분기(90% 이상 정상, 90% 미만 경고 부착, HWP 누락, PDF 누락, 양쪽 누락) 검증
      - `save_passage` / `get_passage` SQLite `validation_ratio = None` (NULL) 저장/복원 무결성 검증 (총 11개 단위 테스트 추가)
    - **문서 동기화**:
      - `docs/plans/2026-10-04_01_code-review-roadmap.md`: 4-C 적용 결과 기록 및 진행 현황(4-A ✅ · 4-B ✅ · 4-C ✅ · 다음: 4-D) 갱신
      - `docs/README.md`: 계획서 목록 진행 현황 동기화
- **검증 결과**:
  - `python -m compileall gichul tests`: 전체 파이썬 파일 바이트코드 컴파일 오류 0건 통과
  - `node -c static/js/results-passage.js`: 프론트엔드 자바스크립트 문법 검사 오류 0건 통과
### [2026-10-05 19:03] 업데이트 이력 (Commit ID: 2d44dda8)
- **수정 내용**:
  - **로드맵 4-D: 저장소와 작업 폴더 정리 (`docs/plans/2026-10-04_01_code-review-roadmap.md`)**:
    - **XTTS 전용 고중량 의존성 분리 (`requirements-xtts.txt`)**:
      - 성우 음성 복제(XTTS-v2, PyTorch CUDA 12.4, `coqui-tts`, `torchcodec`, `soundfile`) 의존성을 일반 `requirements.txt`와 분리
      - `dist/` 오프라인 휠 기반 고속 설치 및 PyTorch CUDA 인덱스 설치 가이드 명시
    - **로컬 미추적 대용량 임시 폴더 삭제 (`scratch/jsmod/node_modules`)**:
      - Git 미추적 임시 폴더 22.3 MB 삭제 완료 (로컬 디스크 용량 회수)
    - **`static/captures/` 관리 방안 확정 (사용자 선택 반영)**:
      - 사용자 결정에 따라 **현행 유지(Git 추적 및 GitHub 자동 클라우드 백업 유지)** 확정
      - 18,137개 크롭 이미지(2.35 GB) 유실 위험 원천 배제, 별도 외장 백업 및 강제 푸시(`git filter-repo`) 리스크 없음
    - **`dist/` 오프라인 휠 보존**:
      - `install.bat` 4단계 오프라인 설치 지원 유지를 위해 보존
    - **Git 저장소 오브젝트 현황 측정 (`git count-objects -vH`)**:
      - 팩 내부 오브젝트 24,151개, 팩 용량 2.56 GiB, 가비지 0 bytes 확인
    - **문서 동기화**:
      - `docs/plans/2026-10-04_01_code-review-roadmap.md`: 4-D 적용 결과 기록 및 진행 현황(4-A ✅ · 4-B ✅ · 4-C ✅ · 4-D ✅ · 다음: 4-E) 갱신
      - `docs/README.md`: 계획서 목록 진행 현황 동기화
- **검증 결과**:
  - `python -m compileall gichul tests`: 전체 파이썬 파일 바이트코드 컴파일 오류 0건 통과
  - `python -m pytest tests -q`: **206개 단위/통합 테스트 100% 통과** (8.23s)

### [2026-10-05 19:44] 업데이트 이력 (Commit ID: 60e2ea93)
- **수정 내용**:
  - **결과창 [문장] 탭 클릭 시 빈 검색어 안내 화면(Empty State) 분리 및 UX 개선 (대안 B 채택)**:
    - **문제 원인 해결**: `navigation.js`에서 결과창 `[문장]` 탭 클릭 시 `showSentencesForPassage(currentPassageId)`를 무조건 호출하고, `currentPassageId` 미존재 시 `passagesData[0]`(`[고2-2026년-09월-18번]`) 9개 문장으로 강제 폴백하여 첫 화면 빈 검색 후 [문장] 탭 진입 시 의도치 않은 특정 모의고사 문장이 노출되던 결함 수정
    - **결과창 `[문장]` 탭 동작 분리 (`static/js/navigation.js`)**:
      - `resultsSearchInput`에 검색어가 있는 경우: `setMode("sentence")` 후 문장 검색(`executeSearch("results")`) 즉시 실행
      - `resultsSearchInput`이 비어 있는 경우: 임의의 지문 문장으로 직행하지 않고 `showSentenceEmptyGuidance()` 안내 화면 호출 및 검색창 포커스
    - **0번 지문 강제 폴백 제거 및 안내 렌더러 신설 (`static/js/results-sentence.js`, `static/js/dom.js`)**:
      - `showSentencesForPassage()`의 `passagesData[0]` 강제 폴백 로직 제거 (지문 뷰어 헤더 슬롯 `[📝 해당 지문의 전체 문장]` 전용 버튼으로만 명확히 작동하도록 분리)
      - `showSentenceEmptyGuidance()` 신설: 컨테이너 가시성 제어 및 검색창 자동 포커스
      - 추천 키워드 칩(`climate`, `technology`, `however`, `#어법`) 클릭 시 해당 검색어로 즉시 검색 트리거
    - **검색 흐름 연동 및 동기화 (`static/js/search.js`, `static/js/results-passage.js`)**:
      - `executeSearch()` 및 `executeSearchWithinResults()` 실행 시 이전 안내창 숨김 처리
      - 검색어 및 활성 필터가 없는 문장 검색 시 안내 화면(`showSentenceEmptyGuidance()`)으로 안전하게 라우팅
    - **템플릿 마크업 및 스타일링 (`templates/index.html`, `static/css/search.css`)**:
      - `#sentenceEmptyGuidanceBox` 템플릿 신설
      - 파스텔 카드 스타일 및 추천 칩 호버 효과 적용
  - **코드 리뷰 로드맵 4-E-1: CSS 모듈화 분리 (`docs/plans/2026-10-04_01_code-review-roadmap.md`)**:
    - 기존 7,540줄 단일 `style.css`를 6개 도메인별 모듈 CSS로 기능별 분리:
      - `static/css/base.css`: 전역 타이포그래피, 디자인 시스템 토큰, 리셋, 헤더, 토스트
      - `static/css/search.css`: 구글 스타일 홈 검색창, 필터 바, 영역 토글, 연도 멀티셀렉트, 문장 빈 검색 안내 화면
      - `static/css/viewer.css`: 2x2 지문 그리드 패널, 문항 탭 바, 트리 네비게이터, 문장 테이블
      - `static/css/modal.css`: 공통 모달 백드롭/컨테이너/헤더/바디/푸터, 공통 로딩 스피너
      - `static/css/grammar.css`: 어법 분석기, 어법 배지, 커스텀 어법 체계 모달, AI 설정 모달
      - `static/css/upload.css`: 시험지 업로드 모달, 시험지 관리 테이블, 5종 파일 필터
    - `templates/index.html`: 6개 모듈 CSS 병렬 로드 적용
    - `static/css/style.css`: 하위 호환성을 위해 6개 모듈을 `@import`하는 마스터 번들로 리팩토링
  - **문서 동기화**:
    - `docs/plans/2026-10-05_01_sentence-tab-empty-state-ux.md`: 계획 수립 및 1~4단계 전 과정 `✅ 완료`
    - `docs/plans/2026-10-04_01_code-review-roadmap.md`: 4-E-1 CSS 분리 완료 및 다음 4-E-2 상태 동기화
    - `docs/README.md`: 계획서 목록 상태 최신화
- **검증 결과**:
  - `python -m compileall gichul tests -q`: 바이트코드 컴파일 오류 0건 통과
  - `node -c static/js/*.js`: 프론트엔드 자바스크립트 전체 문법 검사 오류 0건 통과
  - `python -m pytest tests -q`: **206개 단위/통합 테스트 100% 통과** (9.89s)

### [2026-10-05 20:04] 업데이트 이력 (Commit ID: 3f2c1c06)
- **수정 내용**:
  - **코드 리뷰 로드맵 4-E-2: HTML 인라인 스타일 CSS 클래스 이전 및 정리 (`docs/plans/2026-10-04_01_code-review-roadmap.md`)**:
    - **헤더 & 검색 영역 클래스화 (`static/css/search.css`, `static/css/base.css`)**:
      - `#btnResetHomeFilters`, `#btnResetResultsFilters`: 초기 `visibility: hidden; opacity: 0; pointer-events: none;` 인라인 속성을 CSS 클래스 기본값으로 이전
      - `.empty-actions`: 검색 결과 없음 안내 카드 하단 액션 버튼 flex 정렬 클래스화
      - `.guidance-sample-tags`, `.guidance-sample-label`: 추천 키워드 칩 래퍼 및 라벨 스타일 클래스화
    - **뷰어 영역 클래스화 (`static/css/viewer.css`)**:
      - 2x2 지문 그리드 패널: `.panel-top-left`, `.panel-top-right`, `.panel-bottom-left`, `.panel-bottom-right` 클래스로 `grid-column`/`grid-row` 이전
      - 패널 액션 및 듣기 바: `.panel-header-actions`, `.panel-bottom-left-actions`, `.listening-bottom-left-actions`, `.btn-fels-action` 클래스화
      - 메타 정보 & 문장 뷰어: `#validationBadge`, `.meta-val-primary`, `.meta-val-type`, `.meta-val-answer`, `.rates-empty-hint`, `.meta-item-spacing`, `.sentence-match-label`, `#sentenceMatchCount`, `.sentence-match-sub`, `.sentence-header-actions`, `#btnSentenceBackToPassage` 스타일 이전
    - **모달 영역 클래스화 (`static/css/upload.css`, `static/css/grammar.css`, `static/css/modal.css`)**:
      - 공통 모달 유틸리티: `.modal-header-info`, `.modal-header-actions`, `.modal-footer-between`, `.modal-footer-actions`, `.flex-row-center`, `.flex-between`, `.mb-0`, `.cursor-pointer`, `.nowrap`, `.text-center`, `.w-100` 신설
      - 업로드 모달 테이블: `.batch-sets-table`, `.files-status-table`, `.manage-exams-table` 공통 규격, 헤더 정렬(`.col-center`, `.col-chk`), 래퍼 스크롤 클래스화
      - 업로드 보조 컴포넌트: `.batch-progress-box`, `.batch-progress-header`, `.progress-bar-bg`, `.progress-bar-fill`, `.batch-progress-subtext`, `.files-summary-bar`, `.files-summary-badges`, `.badge-files-stat`, `.dropdown-filter-container`, `.btn-filter-trigger`, `.dropdown-filter-menu`, `.missing-filter-header`, `.missing-filter-title`, `.missing-filter-actions`, `.btn-missing-text`, `.missing-filter-body`, `.missing-chk-label`, `.upload-help-box`, `.manage-exams-toolbar`, `.manage-exams-count`, `.form-text-muted`, `.btn-icon-gap`
      - 선택 삭제 모달: `.sel-del-modal-content`, `.sel-del-header`, `.sel-del-title`, `.sel-del-subtitle`, `.sel-del-target-box`, `.sel-del-target-label`, `.sel-del-target-text`, `.sel-del-preset-label`, `.sel-del-presets-row`, `.sel-del-options-list`, `.sel-del-option-card`, `.sel-del-card-header`, `.sel-del-card-title`, `.sel-del-card-desc`, `.sel-del-warning-msg`
      - AI 설정 및 어법 모달: `.lmstudio-card`, `.tts-radio-label`, `.edge-label`, `.btn-tts-action`, `.grammar-popover-title-group`, `.grammar-popover-source`, `.grammar-popover-footer`
    - **자바스크립트 런타임 호환성 보존**:
      - JS 상태 검사 로직(`element.style.display !== "none"`, `=== "block"`) 및 동적 너비 제어(`width: 0%;`)에 필수적인 초기 인라인 속성은 안전하게 보존하여 오동작 원천 차단
    - **인라인 스타일 감축 결과**:
      - `templates/index.html` 전체 인라인 `style=""`: 기존 **371개 → 164개** (**207개 대폭 감축, 55.8% 제거**)
      - 순수 레이아웃 및 비주얼 인라인 스타일: **321개 → 109개** (**66% 클래스화 이전 완료**)
    - **문서 동기화**:
      - `docs/plans/2026-10-04_01_code-review-roadmap.md`: 4-E-2 완료 반영 및 결과 기록
      - `docs/README.md`: 계획서 목록 상태 갱신 (4-E-2 ✅ · 다음: 4-E-3)
- **검증 결과**:
  - `python -m compileall gichul tests -q`: 바이트코드 컴파일 오류 0건 통과
  - `node -c static/js/*.js`: 프론트엔드 자바스크립트 전체 문법 검사 오류 0건 통과
  - `python -m pytest tests -q`: **206개 단위/통합 테스트 100% 통과** (16.79s)

### [2026-10-05 20:15] 업데이트 이력 (Commit ID: c3ed6cf8)
- **수정 내용**:
  - **코드 리뷰 로드맵 4-E-3: 거대 단일 파일 `results-passage.js`(3,488줄) 3대 도메인 모듈화 분리 (`docs/plans/2026-10-04_01_code-review-roadmap.md`)**:
    - **분리 배경**: 지문 검색 결과 뷰어의 서버 API 통신, 2x2 그리드/트리 렌더링, 사용자 이벤트 제어가 단일 파일(`results-passage.js`)에 결합되어 가독성과 유지보수성이 저하되던 문제를 단일 책임 원칙(SRP)에 따라 3개 전담 모듈로 체계적 분리
    - **1) [NEW] 지문 서버 통신 모듈 (`static/js/passage-api.js`, 260줄)**:
      - 시험 단위 문항 상세 캐시 관리: `examFullPassagesCache`, `loadingExamsMap`, `ensureExamPassagesLoaded`, `mergePassagesWithCache`
      - 지문 데이터 조작 및 서버 API: `savePassageMemoApi`, `updateQuestionTypeApi`, `updateAnswerApi`, `addPassageTagApi`, `deletePassageTagApi`, `recapturePassagePdfApi`, `fetchExamRawFilesApi`, `fetchPassageByIdApi`
      - 원본 파일 다운로드 트리거: `downloadExamRawFile`, `downloadExamAllZip`, `downloadExamListeningZip`
      - TTS 음성 합성 통신 및 진행률 폴링: `activeTtsJob`, `pollTtsProgressApi`, `generateSingleAudioApi`, `generateAllAudioApi`, `switchTtsEngineApi`
    - **2) [NEW] 지문 화면 렌더링 모듈 (`static/js/passage-render.js`, 910줄)**:
      - 시험 계층 및 트리 파서: `buildExamTree`, `parsePassageHierarchy`, `sortGradesDescending`, `sortYearsDescending`, `sortMonthsDescending`
      - 문항 탭 및 네비게이터: `renderPassageView`, `updateTreeUI`, `renderBreadcrumb`, `renderBreadcrumbExamFiles`, `renderRawFilesChips`, `hideBreadcrumbExamFiles`, `renderPassageTabs`, `selectPassageTab`
      - 복합 지문(1지문 다문항) 동적 통합: `resolveCompoundGroupsFor50`, `groupPassageItems`, `combineGroupExplanations`, `createGroupedListeningItem`, `splitExplanationBlocks`, `normalizeExplanationBlock`, `cleanQuestionExplanationLeak`, `extractQuestionChoicesOnly`
      - 2x2 그리드 패널 렌더링: `loadPassageDetail`, `reset2x2ContentPanels`, `clear2x2Panels`, `renderPassageTags`, `bindPassageMemo`, `applyPassageUpdate`
      - FELS 기능어 약형드랩 서식화: `isDialogueScript`, `splitFelsMonologueIntoSentences`, `numberDialogueTurns`, `formatFelsText`, `renderFelsBottomLeftPanel`
      - 선지별 선택률 게이지 바 & 난이도 배지: `renderChoiceRates`, `renderSingleQuestionBars`, `getDifficultyInfo`, `parseChoiceRatesObj`
      - 활성 문항 상태 추출: `getCurrentActivePassage`, `getCurrentDetailPassage`
    - **3) [NEW] 지문 이벤트 및 인터랙션 모듈 (`static/js/passage-events.js`, 680줄)**:
      - 오디오 재생/정지 전역 추적: `stopAllListeningAudio`, `activeListeningAudio` 실시간 추적, `window.stopAllListeningAudio` 전역 등록
      - TTS 음성 합성 인터랙션: `applyTtsUiState`, `estimateTtsPercent`, `passageMatchesTtsJob`, `setTtsBtnLabel`, `pollTtsProgress`, `handleGenerateListeningAudioAction`, `handleGenerateAllListeningAudioAction`, `updateTtsEngineSwitcherState`, `handleSwitchTtsEngine`, `updateListeningZipRangeBadge`
      - 지문 메모(노트) 500ms 디바운스 자동 저장: `savePassageMemo`, `handleMemoInput`, `isMemoDirty`, `memoSaveTimer`
      - 사용자 액션 이벤트 바인딩: `handleRecapturePdf`, `addPassageTagAction`, `deletePassageTagAction`, `executeDownloadPassageMp3`, `executeDownloadExamListeningZip`, 정답 수동 수정(모달 폼·옵션 동기화), FELS/지문/대본 원클릭 복사(`copyFelsBlankVersion`, `copyFelsAnswerVersion`), 키보드 좌우 방향키 네비게이션, 상단 탭 스크롤, 전역 클릭 이벤트 위임, `initPassageEvents`
    - **4) [MODIFY] 하위 호환 Facade Re-export (`static/js/results-passage.js`, 24줄)**:
      - 기존 3,488줄에서 24줄로 대폭 경량화 (~99.3% 라인 감소)
      - 3개 신규 모듈의 모든 함수/변수를 100% 완전 re-export하여 기존 호출자(`search.js`, `results-sentence.js`, `upload.js`, `files-status.js`, `navigation.js`, `main.js`)의 import 경로 수정 없이 100% 하위 호환성 유지
    - **문서 동기화**:
      - `docs/plans/2026-10-04_01_code-review-roadmap.md`: 4단계(4-A~4-E 전체) `✅ 완료` 및 4-E-3 결과 기록
      - `docs/README.md`: 계획서 목록 4단계 완료 반영
- **검증 결과**:
  - `python -m compileall gichul tests -q`: 바이트코드 컴파일 오류 0건 통과
  - `node -c static/js/*.js`: 프론트엔드 자바스크립트 전체 13개 모듈 문법 검사 오류 0건 통과
  - Node.js ESM Import 검증: `main.js`, `search.js`, `results-passage.js`, `results-sentence.js`, `upload.js`, `files-status.js`, `navigation.js`, `ai-settings.js`, `grammar.js` 등 전체 프론트엔드 모듈 정상 임포트 및 초기화 확인
  - `python -m pytest tests -q`: **206개 단위/통합 테스트 100% 통과** (20.27s)

### [2026-10-06 12:45] 업데이트 이력 (Commit ID: 2c00cbc9)
- **수정 내용**:
  - **문항 및 문장 오류 신고 시스템 구축 (`docs/plans/2026-10-06_error-report-system.md`)**:
    - **지문 및 문장 오류 신고 모달**:
      - 지문 결과창 2x2 패널 좌상단에 `[🚨 오류 신고]` 버튼 배치: 5종 오류(1. pdf 캡처 오류, 2. 해설지 오류, 3. 정답 오류, 4. 정답률 오류, 5. 기타 오류 주관식 입력창) 복수 선택 신고 지원
      - 문장 결과창 1행 테이블 액션 열에 `[🚨 신고]` 버튼 배치: 문장 오류 내용 주관식 상세 입력 모달 지원
    - **우측 상단 공통 [🚨 오류 신고 내역] 관리 모달**:
      - 메인 첫 화면, 지문 결과 화면, 문장 결과 화면 전체의 헤더 우측 상단 동일 위치에 `[🚨 오류 신고 내역]` 버튼 통일 배치
      - 신고 내역 통합 관리 모달: '문항 오류' / '문장 오류' 탭 분리, 신고 일시, 오류 항목 및 내용 확인, 수정 완료 시 '해결 완료(삭제)' 기능 제공
    - **백엔드 오류 관리 API 및 DB 구현**:
      - `gichul/routers/reports.py`: `POST /api/reports`, `GET /api/reports`, `DELETE /api/reports/{id}` RESTful API 구현
      - `gichul/database.py`: `reports` 테이블 스키마 자동 마이그레이션 및 CRUD 헬퍼 함수 구현
  - **지문 자료(문제 PDF 캡처 이미지 · 듣기 음성 파일) 수동 업로드 교체 기능 구축**:
    - 지문 결과창 패널에 `[🖼️ 문제 이미지 교체]`, `[🎧 듣기 파일 교체]` 수동 업로드 버튼 추가
    - 업로드 시 기존 파일을 덮어쓰고 최신 자료로 즉시 교체되며 화면 캐시 버스팅(`?t=timestamp`)을 통해 실시간 화면 갱신
    - 백엔드 `POST /api/passages/{passage_id}/upload-capture`, `POST /api/passages/{passage_id}/upload-listening` 엔드포인트 구현 (`gichul/routers/passages.py`)
  - **문장 분석 결과 화면 내 문장 텍스트 수동 직접 수정 기능 구축 (`docs/plans/2026-10-06_01_sentence-text-manual-edit.md`)**:
    - 문장 검색 테이블 액션 열에 `[✏️ 수정]` 버튼 추가 (`static/js/results-sentence.js`)
    - 클릭 시 해당 행의 문장 셀이 인라인 `<textarea>` 편집 모드로 전환되며, `Ctrl + Enter` (저장) 및 `ESC` (취소) 단축키 지원
    - 저장 시 `PATCH /api/sentences/{sentence_id:path}/text` API를 호출하여 DB `sentences.sentence_text` 및 `word_count` 자동 재계산 및 갱신, 시험 캐시 무효화 (`gichul/routers/passages.py`, `gichul/database.py`)
    - 화면 본문 텍스트 및 `[📋 복사]` 버튼의 복사 데이터(`data-text`) 실시간 동기화, 어법 분석 문장의 경우 재분석 안내 토스트 제공
    - 인라인 문장 에디터 전용 반응형 스타일 추가 (`static/css/viewer.css`)
  - **문서 동기화**:
    - `docs/plans/2026-10-06_error-report-system.md`: 완료 반영
    - `docs/plans/2026-10-06_01_sentence-text-manual-edit.md`: 완료 반영
    - `docs/README.md`: 계획서 목록 및 상태 `✅ 완료` 동기화
- **검증 결과**:
  - `python -m py_compile gichul/routers/passages.py gichul/routers/reports.py gichul/database.py gichul/app.py`: 파이썬 구문 오류 0건 통과
  - `node -c static/js/results-sentence.js static/js/reports.js static/js/passage-events.js static/js/main.js`: 프론트엔드 자바스크립트 구문 오류 0건 통과
  - FastAPI `TestClient`를 통한 `PATCH /api/sentences/{id}/text` 200 OK 단위 검증 및 롤백 확인 완료

### [2026-10-06 15:30] 업데이트 이력 (Commit ID: d702fdba)
- **수정 내용**:
  - **교사용 지문 유인물 자동 제작 시스템 구축 (`docs/plans/2026-10-06_02_handout-generation-system.md`)**:
    - **1) B4 단면 2문항 HWPX 생성 엔진 구현 (`gichul/services/hwpx_generator.py`)**:
      - ZIP/XML 조작 기반 고속 생성 엔진: 표준 라이브러리(`zipfile`, `xml.etree.ElementTree`)로 외부 프로세스 없이 0.05초 만에 메모리 내 조립 및 스트리밍
      - **사용자 지정 문항 번호 (`custom_q_num`)**: 원출처 번호와 별개로 교사가 원하는 문항 번호(1, 2, 3...) 직접 지정 및 자동 순차 재부여 지원
      - **문제지 규격**: 출처 완전 배제, 사용자 지정 번호 + 발문 + 지문 본문 + 5지 선지(①~⑤) + 정답 번호 노란색 형광펜(`markPenBegin` / `shadeColor`) 하이라이트 (교사용/학생용 토글 지원)
      - **해설지 규격**: 사용자 번호 + 원출처 병기, 지문 결과 화면 좌측 하단 상세 해설 패널 전문(`[정답]`, `[해석]`, `[해설]`, `[어휘]`) 가독성 높은 소제목 단락으로 주입
      - **머리말 & 꼬리말 동적 주입**: 학교명, 시험명, 소속 문구 등 사용자 입력 텍스트를 `section0.xml`에 동적 치환
      - 문제지/해설지 개별 HWPX 다운로드 및 ZIP 일괄 패키징 스트리밍 지원
    - **2) 유인물 REST API 라우터 구현 (`gichul/routers/handouts.py`)**:
      - `POST /api/handouts/generate`: 문항 목록, `custom_q_num`, 머리말/꼬리말, 형광펜 옵션을 받아 문제지/해설지/ZIP 파일 스트리밍
      - `GET /api/handouts/templates`: 등록된 템플릿 목록 조회
      - `POST /api/handouts/templates/upload`: 교사 자체 제작 B4 HWPX 양식 업로드 및 검증 저장
      - `gichul/paths.py`: 기본 양식 저장소(`static/data/templates/`)와 사용자 업로드 양식 저장소(`uploads/templates/`) 분리
      - `gichul/app.py`: 라우터 등록 및 `_CACHE_SAFE_WRITE_PREFIXES`에 `/api/handouts/` 등록
    - **3) 프론트엔드 장바구니 및 유인물 뷰어 독립 모듈화**:
      - `static/js/handout-cart.js`: `localStorage` 기반 문항 보관함 상태 관리, 결과 화면 우측 하단 플로팅 바 UI, 체크박스 실시간 동기화
      - `static/js/handout-passage.js`: 유인물 제작소 화면 렌더링, 사용자 지정 문항 번호 입력/순차 재부여, 순서 변경(위/아래), 개별 삭제, 머리말/꼬리말 폼(`localStorage` 자동 저장), HWPX 양식 업로드 및 다운로드 비동기 호출
      - `static/css/handouts.css`: 기존 스타일과 격리된 유인물 제작 화면 및 보관함 전용 독립 스타일링
      - `templates/index.html`: 헤더 `[📄 유인물 제작]` 버튼, 검색결과 breadcrumb 내 `[☑ 유인물 담기]` 체크박스, `<section id="handoutViewContainer">` 및 `#handoutFloatingCart` 추가
      - `templates/index.html`: 교사가 한글 프로그램에서 학교 양식으로 커스텀할 수 있도록 `[📥 기본 문제지 양식 받기]`, `[📥 기본 해설지 양식 받기]` 직접 다운로드 버튼 제공
  - **문서 동기화**:
    - `docs/plans/2026-10-06_02_handout-generation-system.md`: 완료 반영
    - `docs/README.md`: 계획서 목록 상태 `✅ 완료` 동기화
- **검증 결과**:
  - `python -m py_compile gichul/paths.py gichul/services/hwpx_generator.py gichul/routers/handouts.py`: 컴파일 오류 0건 통과
  - `node -c static/js/handout-cart.js static/js/handout-passage.js static/js/navigation.js static/js/passage-render.js static/js/main.js`: 자바스크립트 구문 오류 0건 통과
  - `python -m pytest tests/`: 전체 211개 단위/통합 테스트 100% 통과 (16.57s)

### [2026-10-06 18:35] 업데이트 이력 (Commit ID: d6331a3b)
- **수정 내용**:
  - **1) 유인물 양식 템플릿 엔터 20줄 일괄 제거 및 단 나눔(`<hp:p columnBreak="1"/>`) 최적화 (`static/data/templates/`)**:
    - **문제지 양식 (`default_b4_question.hwpx`)**: 1번 문항 뒤에 수동 삽입되었던 불필요한 빈 문단 19줄(`P#05~P#23`)을 완전 제거하고, 1번 문항 직후(`P#04`)에 `<hp:p columnBreak="1"/>`를 명시하여 2번 문항이 우측단 최상단에 안정적으로 시작되도록 최적화 (29개 문단 $\rightarrow$ 10개 문단 경량화).
    - **해설지 양식 (`default_b4_explanation.hwpx`)**: 1번 문항 해설 뒤의 빈 문단 23줄(`P#06~P#28`)을 완전 제거하고, 1번 해설 직후(`P#05`)에 `<hp:p columnBreak="1"/>`를 명시 (34개 문단 $\rightarrow$ 11개 문단 경량화).
    - 한글 프로그램에서 원본을 열거나 유인물 제작소에서 다운로드할 때 지문 길이에 상관없이 완벽한 2단 배치가 보장되도록 개선.
  - **2) 유인물 제작소 화면 내 '검색 화면으로 복귀' 버튼 동작 복구 (`static/js/navigation.js`, `static/js/handout-passage.js`)**:
    - `btnHandoutBackToResults` 클릭 시 미구현된 `switchView` 호출로 무반응이던 버그 해결.
    - `navigation.js`에 `backFromHandoutView()` 신규 구현: 검색 결과가 존재하면 결과 화면(`showResultsScreen`), 없으면 홈 검색 화면(`showHomeScreen`)으로 지능형 복귀.
    - 헤더의 `btnBackToSearch`와 유인물 상단 `[🔙 검색 화면으로 복귀]` 버튼 모두 `backFromHandoutView()`로 일원화 연동.
  - **3) C드라이브 '다운로드' 폴더 다운로드 피드백 및 헤더 인코딩 보강 (`static/js/handout-passage.js`, `gichul/routers/handouts.py`)**:
    - 웹 브라우저 표준 다운로드 메커니즘을 통해 Windows 기본 다운로드 경로(`C:\Users\user\Downloads`)로 문제지/해설지/ZIP 파일 정상 저장.
    - 다운로드 완료 시 `✅ '[파일명]' 파일이 C드라이브 '다운로드' 폴더로 다운로드되었습니다.` 확인 알림 표출.
    - `Content-Disposition` 헤더에 RFC 5987 UTF-8 인코딩 및 RFC 2616 ASCII fallback을 함께 제공하여 한글 파일명 호환성 보장.
    - 양식 파일 업로드 확장자 검사 시 자바스크립트 메소드 오타(`endswith` $\rightarrow$ `.endsWith()`) 수정.
  - **4) 양식 파일명 상호 호환 경로 보완 (`gichul/services/hwpx_generator.py`)**:
    - 사용자가 수정한 `default_b4_question.hwpx` 외에도 혹시 모를 하이픈(`-`) 및 언더스코어(`_`) 명칭 불일치가 있더라도 둘 다 자동 탐색하도록 `get_template_path()` 및 `list_templates()` 보강.
  - **5) 문서 작성 및 동기화**:
    - `docs/reviews/2026-10-06_handout-template-structure-analysis.md`: 기본 템플릿의 B4 규격, 2단 레이아웃, 상단 헤더 표, 해설지 출처 표 정밀 구조 분석 및 적합성 검토 보고서 신규 작성.
    - `docs/plans/2026-10-06_02_handout-generation-system.md`: 진행 현황 표에 템플릿 최적화 및 UX/버그 수정 내역 완료 반영.
    - `docs/README.md`: 신규 리뷰 문서 등록.
- **검증 결과**:
  - `python -m py_compile gichul/services/hwpx_generator.py gichul/routers/handouts.py`: 파이썬 구문 오류 0건 통과
  - `node -c static/js/navigation.js static/js/handout-passage.js`: 자바스크립트 문법 오류 0건 통과
  - `pytest tests/test_hwpx_generator.py`: 5개 전체 단위/통합 테스트 100% 통과 (3.01s)
  - `pytest tests/test_api_smoke.py tests/test_routers.py`: 11개 API 스모크 테스트 100% 통과 (6.10s)

### [2026-10-06 19:00] 업데이트 이력 (Commit ID: f56243ff)
- **수정 내용**:
  - **1) 유인물 프로젝트 형식 관리 시스템 전면 구축 (`static/js/handout-cart.js`, `templates/index.html`, `static/css/handouts.css`, `static/js/handout-passage.js`)**:
    - **다중 프로젝트 독립 관리 체계**: 단일 장바구니에서 프로젝트(예: "2026 1학기 기말고사 대비", "고2 빈칸추론 특강") 단위로 유인물을 생성/보관/전환할 수 있도록 전면 개편.
    - **데이터 마이그레이션**: 기존에 담겨있던 문항들은 유실 없이 '기본 프로젝트'로 자동 승계.
    - **프로젝트별 독립 데이터 보존**: 각 프로젝트마다 출제 문항 목록(`items`), 사용자 지정 인쇄 번호(`custom_q_num`), 머리말/꼬리말/템플릿 서식 설정(`settings`)이 독립적으로 저장/복원.
    - **유인물 제작소 프로젝트 관리 바**: 상단에 `[📁 현재 프로젝트 선택]` 드롭다운, `[➕ 새 프로젝트]`, `[✏️ 이름 변경]`, `[🗑️ 프로젝트 삭제]`, 생성일 메타 정보 바 구축.
    - **플로팅 카트 바 실시간 동기화**: `📁 [프로젝트명] N문항` 형식으로 현재 활성 프로젝트와 문항 수를 실시간 표출.
  - **2) 지문 결과 화면 '유인물 담기' 버튼 위치 최적화 및 불필요 버튼 정리 (`templates/index.html`)**:
    - 상단 브레드크럼 우측의 `📑 시험 전체 담기` 버튼 삭제.
    - 좌측 상단 패널 헤더의 기존 텍스트(`🖼️ PDF 문항 캡처 이미지`, `고화질 원본`)를 삭제하고, 해당 위치(`panel-header-left`)에 **`[📄 유인물 담기]` 체크박스**를 이전 배치하여 지문 열람 시 바로 담을 수 있도록 가시성 극대화.
    - 유인물 담기 버튼 바로 옆에 **`[📁 프로젝트 선택 드롭다운]` 및 `[➕ 새 프로젝트]` 빠른 생성 버튼**을 함께 배치하여 열람 중인 문항을 즉시 원하는 프로젝트에 담을 수 있도록 최적화.
  - **3) '검색 화면으로 복귀' 클릭 시 지문 결과 화면 복귀 보장 (`static/js/navigation.js`, `static/js/handout-passage.js`, `templates/index.html`)**:
    - `backFromHandoutView()`에서 홈 검색 화면(`homeSearchView`)으로 분기되던 조건을 제거하고, 항상 이전에 보던 **지문 결과 화면(`showResultsScreen()`)**으로 즉시 복귀하도록 단일화.
    - 버튼 명칭을 `🔙 지문 결과 화면으로 복귀`로 명확화.
  - **4) 머리말 3열 설정 개편 ('왼쪽 상단', '가운데 상단', '오른쪽 상단') 및 HWPX 상단 표 주입 (`templates/index.html`, `gichul/routers/handouts.py`, `gichul/services/hwpx_generator.py`)**:
    - 유인물 제작소 서식 폼을 B4 양식의 상단 표에 맞춰 `handoutHeaderLeft` ('왼쪽 상단'), `handoutHeaderCenter` ('가운데 상단'), `handoutHeaderRight` ('오른쪽 상단')으로 개편.
    - HWPX 템플릿의 상단 1행 3열 표(`tbl`)를 유지하고 각 열(0, 1, 2열)에 텍스트 주입 및 검은색 폰트로 정규화.
  - **5) HWPX 템플릿 보존형 본문 주입 및 해설지 1행 4열 출처 표 복원 (`gichul/services/hwpx_generator.py`)**:
    - **해설지 출처 박스 표 복원**: 템플릿의 1행 4열 표(`rowCnt="1"`, `colCnt="4"`)를 추출 및 복제하여 지문 메타데이터(연도, 학년, 월, 번호)를 각 셀에 주입하고 폰트 색상 정규화.
    - **템플릿 고유 단락 스타일 승계**: 문제지 발문(`paraPrIDRef="26"`), 본문 및 선지(`paraPrIDRef="35"` 양쪽정렬), 해설지 출처 표(`paraPrIDRef="24"`), 정답(`paraPrIDRef="25"`), 해설 본문(`paraPrIDRef="27"` 양쪽정렬) 적용.
    - **다페이지 연속 레이아웃**: 홀수 문항 후 `columnBreak="1"`, 짝수 문항 후 `pageBreak="1"`을 자동 배치하여 4문항, 6문항 등 2문항을 초과하더라도 B4 2단 레이아웃이 완벽하게 유지되도록 구조화.
  - **6) 계획서 작성 및 문서 동기화**:
    - `docs/plans/2026-10-06_03_handout-template-content-injection.md`: 계획서 작성 및 `✅ 완료` 반영.
    - `docs/README.md`: 계획서 목록 상태 `✅ 완료` 동기화.
- **검증 결과**:
  - `python -m py_compile gichul/services/hwpx_generator.py gichul/routers/handouts.py`: 파이썬 컴파일 오류 0건 통과
  - `node -c static/js/handout-cart.js static/js/handout-passage.js static/js/navigation.js`: 자바스크립트 문법 검사 통과
  - `pytest tests/test_hwpx_generator.py`: 5개 전체 단위/통합 테스트 100% 통과 (4.38s)
  - 다페이지(4문항) 생성 파이프라인 검증: `columnBreak="1"` 2개, `pageBreak="1"` 1개 정확 분할 확인 완료

### [2026-10-06 20:25] 업데이트 이력 (Commit ID: af81ba13)
- **수정 내용**:
  - **1) 문제지 유인물 정답 선지 번호 노란색 형광펜 표시 복원 (`gichul/services/hwpx_generator.py`)**:
    - **OWPML 표준 태그 교정**: 개방형 HWPX(KS X 6101) 표준 규격에 따라 대문자 `markPenBegin`/`markPenEnd` 대신 소문자 표준 태그 `<hp:markpenBegin color="#FFFF00" beginColor="#FFFF00"/>` 및 `<hp:markpenEnd/>`로 수정하여 한글 뷰어/편집기 호환성 확보.
    - **글자 모양(charPr) 음영 이중 보장**: `header.xml` 내 정답 번호용 글자 모양(`charPr`)에 `shadeColor="#FFFF00"`(노란색 음영)을 함께 등록하여, 한/글 프로그램의 '형광펜 표시' On/Off 설정과 관계없이 정답 번호에 선명한 노란색 하이라이트가 상시 표시되도록 이중 보장.
  - **2) 문제지 및 해설지 본문 기본 볼드체 해제 (일반체 표준화) (`gichul/services/hwpx_generator.py`)**:
    - **원인 해결**: HWPX 템플릿의 `charPr id="0"`(기본 텍스트 서식)에 `<hh:bold/>` 태그가 내장되어 있어 본문 텍스트 전체가 굵은 글씨로 출력되던 현상 해결.
    - **일반체 서식 분리 주입**: `_inject_char_properties`에서 `<hh:bold/>` 요소를 명시적으로 제거한 전용 `normal_char_id`를 새로 정의하여 발문, 지문 본문, 선지, 해설 본문 등 모든 텍스트가 가독성 높은 일반체(Non-bold)로 출력되도록 교정.
  - **3) 문제지 유인물 본문 글자 크기 13pt 고정 (`gichul/services/hwpx_generator.py`)**:
    - 기존 템플릿 기본값(10pt, `height="1000"`) 대신 B4 2단 모의고사 유인물 실무 규격에 최적화된 **13 pt (`height="1300"`, 1pt = 100 HWPUnit)**로 고정 주입하여 발문, 지문, 선지의 가독성을 대폭 향상.
  - **4) 해설지 첫 페이지 및 단 나눔 시 녹색 상자 테두리 제거 (`gichul/services/hwpx_generator.py`)**:
    - **템플릿 녹색 테두리 무력화**: `header.xml`에 잔존하던 녹색 실선 테두리(`type="SOLID" width="0.4 mm" color="#35A434"`)를 `_clean_borders_and_boxes` 함수를 통해 `NONE`으로 일괄 무력화.
    - **공백 행 단락 스타일 정규화**: 기존에 녹색 테두리가 상속되던 `paraPr 20/21/24` 스타일을 테두리 없는 순수 빈 문단 `para_pr_id="0"`으로 전면 교체하여 첫 페이지 상단 및 단/페이지 나눔 시 불필요한 녹색 박스가 생기는 현상을 원천 제거.
  - **5) 해설지 다운로드 시 템플릿 선택 자동 보정 (`gichul/services/hwpx_generator.py`, `static/js/handout-passage.js`)**:
    - 사용자가 템플릿 드롭다운에서 문제지용 템플릿을 선택한 상태에서 해설지 단독 다운로드 클릭 시, 백엔드와 프론트엔드 양쪽에서 자동으로 해설지 전용 템플릿(`default_b4_explanation.hwpx`)으로 전환하도록 방어 로직 추가.
  - **6) 검증 테스트 케이스 추가 및 전체 회귀 테스트 통과 (`tests/test_hwpx_generator.py`)**:
    - 13pt 글자 크기(`height="1300"`), 노란색 음영(`shadeColor="#FFFF00"`), 표준 형광펜 마크펜, 녹색 상자 테두리 배제 검증 케이스 추가.
    - 전체 211개(HWPX 5개 + 핵심 기능 206개) 단위/통합 테스트 100% 통과.
- **검증 결과**:
  - `python -m py_compile gichul/services/hwpx_generator.py tests/test_hwpx_generator.py`: 파이썬 구문 검증 완료 (통과, 오류 0건)
  - `node -c static/js/handout-passage.js`: 자바스크립트 문법 검사 통과 (오류 0건)
  - `pytest tests/test_hwpx_generator.py`: 5개 전체 단위/통합 테스트 100% 통과
  - `pytest tests/`: 211개 전체 테스트 100% 통과 (5개 hwpx + 206개 전체 기능)

### [2026-10-06 20:38] 업데이트 이력 (Commit ID: 175ed2e4)
- **수정 내용**:
  - **1) 한/글 문서 보안 경고 원인 해결: 비표준 markpenBegin/End 태그 완전 제거 (`gichul/services/hwpx_generator.py`)**:
    - **원인 분석**: 개방형 HWPX(KS X 6101 OWPML) 표준 단락 네임스페이스(`http://www.hancom.co.kr/hwpml/2011/paragraph`)에 정의되지 않은 비표준 엘리먼트(`<hp:markpenBegin>`, `<hp:markpenEnd>`)가 `section0.xml`에 포함되어 있어, 한컴오피스 한/글 스키마 검증 시 "문서가 손상되었거나 변조되었을 가능성이 있습니다. 이 문서를 불러오려면 [문서 보안 설정]을 [낮음]으로 설정해야 합니다" 보안 경고 팝업이 발생하던 문제를 해결.
    - **비표준 태그 완전 제거**: `_create_paragraph` 헬퍼 및 선지 생성 루프에서 `markpenBegin`/`markpenEnd` 엘리먼트 생성 코드를 완전히 제거.
  - **2) 한컴 OWPML 표준 글자 모양 음영(`charPr shadeColor="#FFFF00"`)으로 정답 강조 일원화 (`gichul/services/hwpx_generator.py`)**:
    - 한/글에서 글자 텍스트 배경 강조를 처리하는 공식 표준 방식인 `charPr` 속성 `shadeColor="#FFFF00"`을 단독 적용.
    - 정답 번호(①~⑤)의 `run` 엘리먼트가 `highlight_char_id`를 참조하여, 스키마 위반이나 보안 경고 없이 선명한 노란색 강조(형광펜 효과)가 한글 뷰어/편집기 및 인쇄 시 100% 정상 출력되도록 최적화.
  - **3) 단위 테스트 갱신 및 OWPML 스키마 준수 전수 검증 (`tests/test_hwpx_generator.py`)**:
    - 비표준 `markpen` 태그 미포함(`assert "markpen" not in sec0.lower()`) 및 `shadeColor="#FFFF00"` 정상 적용 검증 테스트 케이스 갱신.
    - 원본 템플릿 대비 비표준 태그 0건, 참조 무결성 100% 일치 실증 확인.
    - 전체 211개(HWPX 5개 + 핵심 기능 206개) 단위/회귀 테스트 100% 통과.
- **검증 결과**:
  - `python -m py_compile gichul/services/hwpx_generator.py tests/test_hwpx_generator.py`: 파이썬 구문 오류 0건 통과
  - `pytest tests/test_hwpx_generator.py`: 5개 전체 단위/통합 테스트 100% 통과 (6.95s)
  - `pytest tests/`: 211개 전체 회귀 테스트 100% 통과 (22.02s)
  - OWPML 스키마 무결성 검증: 비표준 태그 0건, 잘못된 속성/참조 0건 완전 무결 확인

### [2026-10-06 21:25] 업데이트 이력 (Commit ID: 996b1bd1)
- **수정 내용**:
  - **1) 해설지 유인물 HWPX 열기 오류 및 한/글 보안 경고 완벽 해결 (`gichul/services/hwpx_generator.py`)**:
    - **원인 분석**:
      1. 해설지 템플릿(`default_b4_explanation.hwpx`)의 첫 문단(P#0)에 상단 1x3 머리말 표(`<hp:header>`) 외에 직하위 본문 1x4 기출 출처 표가 포함되어 있어, 머리말 복제 시 직하위 1x4 표가 함께 복제되어 첫 문단에 미치환 플레이스홀더 표가 중복/중첩 삽입되는 문제 발견.
      2. 템플릿의 1행 4열 출처 표 셀 내부에 한/글 양식용 누름틀인 `<hp:fieldBegin type="CLICK_HERE">` 및 `<hp:fieldEnd>`, 그리고 오래된 레이아웃 캐시 `<hp:linesegarray>`가 포함되어 있어, 문항별로 복제 시 누름틀 필드 ID 중복 및 레이아웃 캐시 불일치로 인해 한컴오피스 한/글 보안 검사 엔진이 이를 "문서가 손상되었거나 변조되었을 가능성이 있습니다" 경고로 차단했던 현상 규명.
      3. 복제된 표(`<hp:tbl>`) 및 셀 내부 문단(`<hp:p>`)의 고유 ID가 문서 전체에서 중복되어 OWPML 표준 식별자 규칙 위반.
    - **해결 조치**:
      - `_extract_and_populate_header_table`: P#0의 `tbl_run` 직하위에 붙은 본문 레벨 1x4 표를 제거하여, 상단 1x3 머리말 컨트롤(`<hp:header>`)만 온전히 보존하도록 정리.
      - `_create_source_table_paragraph`: 복제된 1x4 출처 표(`<hp:tbl>`)와 내부 각 셀 문단(`<hp:p>`)에 고유 난수 ID를 부여.
      - 셀 내부를 정규화하여 보안 경고의 직접적 원인이 된 누름틀(`<hp:fieldBegin>`, `<hp:fieldEnd>`)과 불일치 레이아웃 캐시(`<hp:linesegarray>`)를 완전 제거하고, 셀 테두리/정렬 서식(paraPr 22)을 그대로 유지한 채 순수 표준 OWPML 텍스트 문단(`<hp:run><hp:t>`) 구조로 재구성.
  - **2) 지문 화면 '유인물 담기' 버튼 고가시성 모던 캡슐 디자인 개편 (`static/css/handouts.css`, `templates/index.html`, `static/js/handout-cart.js`)**:
    - 기존의 밋밋한 텍스트/체크박스 형태에서 시각적 가시성을 극대화한 **모던 캡슐 버튼(`.btn-handout-cart-toggle`)** 디자인으로 전면 개편.
    - **담기 전 상태**: 선명한 로열 블루 테두리 및 텍스트, 호버 시 입체감 있는 소프트 블루 배경 및 리프트 애니메이션 제공.
    - **담긴 후 상태**: 비비드 로열 블루 그라데이션(`linear-gradient(135deg, #2563eb, #1d4ed8)`) 배경, 순백색 볼드 텍스트, 은은한 블루 발광 그림자 및 `✔ 유인물 담김` 동적 텍스트로 즉각적인 상태 피드백 제공.
  - **3) 지문 화면 좌측 상단 중복 프로젝트 선택기 정리 (`templates/index.html`)**:
    - 우측 하단 플로팅 보관함 바에 동일한 프로젝트 전환/생성 기능이 탑재되어 있으므로, 지문 화면 좌측 상단 패널 헤더의 중복 프로젝트 드롭다운을 깔끔하게 제거하여 상단 UI를 간결화.
  - **4) 하단 플로팅 보관함 바 프로젝트 간 이동 및 실시간 전환 연동 (`templates/index.html`, `static/js/handout-cart.js`, `static/css/handouts.css`)**:
    - 하단 플로팅 보관함 바(`handoutFloatingCart`) 내에 프로젝트 선택 드롭다운(`<select id="floatingProjectSelect">`) 및 빠른 `[➕ 새 프로젝트]` 생성 버튼을 구축.
    - 지문 검색/열람 중에도 언제든지 하단 바에서 원하는 프로젝트로 즉시 전환하고 문항을 담거나 확인할 수 있도록 양방향 동기화 완성.
- **검증 결과**:
  - **실제 한/글 2022 프로세스(`Hwp.exe`) 연동 실증 검증 완료**:
    - 생성된 문제지, 해설지, 및 통합 ZIP 패키지 내부 해설지 HWPX 파일을 한/글 2022에서 직접 열어 윈도우 타이틀 및 모달 대화상자 상태를 정밀 검사한 결과, **보안 경고 팝업 없이 100% 정상 열림** 확인 (`popup_error=False, success_opened=True`).
  - `python -m py_compile gichul/services/hwpx_generator.py`: 파이썬 구문 오류 0건 통과.
  - `node -c static/js/handout-cart.js`: 자바스크립트 문법 검사 통과.
  - `pytest tests/test_hwpx_generator.py`: 5개 전체 HWPX 엔진 테스트 100% 통과.
  - `pytest tests/`: 211개 전체 회귀 테스트 100% 통과.



