# 교사용 유인물 제작소 3대 영역 1차 분리 및 듣기 유인물(B4 세로 2x3 템플릿 기반 · 통합 MP3) 구축 계획서

## 1. 개요 및 배경

- **작성일자**: 2026-10-09 (2차 개정: 2026-10-09 19:30)
- **관련 사용자 요청**:
  - "계획서에서 페이지 당 3x3 테이블을 2x3으로 변경할께."
  - "/static/templates(static/data/templates)에서 듣기 문제 유인물과 해설 유인물의 template을 확인하고 이를 계획서에 반영해줘."
- **목적**:
  - 교사용 유인물 제작소를 3대 핵심 영역(**[독해 유인물]**, **[문장 유인물]**, **[듣기 유인물]**)의 **1개 층(1-Tier) 직관적 탭 체계**로 세분화.
  - 실제 제공된 **듣기 전용 템플릿 2종(`listening_b4_question.hwpx`, `listening_b4_explanation.hwpx`)의 정밀 스키마(B4 세로 2x3 레이아웃)**를 100% 충실하게 반영하여 고품질 문제지/해설지 HWPX 생성 파이프라인 구축.
  - 유인물에 담긴 문항들의 순서에 맞춘 **단일 통합 MP3 오디오 결합 다운로드** 시스템 완비.

---

## 2. 템플릿 정밀 실사 분석 결과 (`static/data/templates/`)

제공된 듣기 템플릿 2종의 XML 구조(`Contents/section0.xml`)를 역공학 정밀 분석한 결과입니다:

### ① 공통 용지 규격 (Page Setup)
- **용지 종류**: **B4 Portrait (세로)** (`width: 72852`, `height: 103180`, `landscape: NARROWLY`) (257mm x 364mm)
- **공통 머리말 테이블 (Table 0, 1행 3열)**:
  - C0: `[왼쪽 상단]` 누름틀 (과목명)
  - C1: `[가운데 상단]` 누름틀 (학교/학원명)
  - C2: `[오른쪽 상단]` 누름틀 (학년 / 반 / 번호 / 이름)

---

### ② [듣기 문제 유인물] 템플릿 스펙 (`listening_b4_question.hwpx`)
- **페이지 구성**: **1페이지당 2문항** (1문항당 7행 복합 테이블 블록 x 2개 = 총 14행)
- **1번째 문항 블록 (Row 0 ~ 6)**:
  - **1열 (Col 0, `rowSpan=7`)**: `[듣기 문항 텍스트]` 누름틀
    - 문항 번호, 발문, 선택지 ①~⑤ (또는 그림/도표 문항 안내)
  - **2열 (Col 1, `rowSpan=7`)**: `[듣기 문항 약형드랩 텍스트]` 누름틀
    - FELS 7대 기능어가 빈칸(`[        ]`) 처리된 학생용 딕테이션 훈련 텍스트
  - **3열 (Col 2~3, `[표현 정리]` 필기 테이블)**:
    - Row 0: `[표현 정리]` 헤더 셀 (`colSpan=2`)
    - Row 1: `우리말` | `영어` 서브 라벨 헤더
    - Row 2~6: 학생 자율 필기용 5개 빈 줄 (칸을 채우지 않는 5행 2열 격자선 보존)
- **2번째 문항 블록 (Row 7 ~ 13)**:
  - 위 1번째 문항과 완전히 동일한 규격 (1열: 문항 텍스트 | 2열: 약형드랩 텍스트 | 3열: `[표현 정리]` 빈칸 표)

---

### ③ [듣기 해설 유인물] 템플릿 스펙 (`listening_b4_explanation.hwpx`)
- **페이지 구성**: **1페이지당 2문항** (Table 1: `rowCnt=2, colCnt=3`)
- **Row 0 (1번째 문항)**:
  - **1열 (Col 0)**: `[듣기 문항 텍스트]` 누름틀 (문항 번호, 발문, 선택지, `[정답] {ans}` 강조)
  - **2열 (Col 1)**: `[듣기 문항 해석 텍스트]` 누름틀 (대본 우리말 해석 전문)
  - **3열 (Col 2)**: `[듣기 문항 script 텍스트]` 누름틀 (영문 순수 대본 텍스트)
- **Row 1 (2번째 문항)**:
  - **1열 (Col 0)**: `[듣기 문항 텍스트]` 누름틀 (문항 번호, 발문, 선택지, `[정답] {ans}` 강조)
  - **2열 (Col 1)**: `[듣기 문항 해석 텍스트]` 누름틀 (대본 우리말 해석 전문)
  - **3열 (Col 2)**: `[듣기 문항 script 텍스트]` 누름틀 (영문 순수 대본 텍스트)

---

## 3. 시스템 아키텍처 및 3대 영역 비교

```
[교사용 유인물 제작소]
  │
  ├── 1. [📄 독해 유인물] (기존 '지문 유인물' 승계)
  │      └── B4 가로 2문항 (문제지 · 해설지 HWPX, 독해 프로젝트)
  │
  ├── 2. [📝 문장 유인물] (기존 '문장 유인물' 현행 유지)
  │      └── A4 세로 단면 구문 분석 훈련 (해설 불필요 단일 문제지 HWPX, 문장 프로젝트)
  │
  └── 3. [🎧 듣기 유인물] (신규 구축)
         ├── B4 세로 2x3 템플릿 기반 문제 유인물 (문항 | FELS 약형드랩 | 표현 정리 5행 표)
         ├── B4 세로 2x3 템플릿 기반 해설 유인물 (문항 | 우리말 해석 | script 전문)
         └── 유인물 문항 순서 결합 단일 통합 MP3 오디오 스트리밍 다운로드
```

| 구분 | [📄 독해 유인물] | [📝 문장 유인물] | [🎧 듣기 유인물] (신규) |
|---|---|---|---|
| **대상 데이터** | 독해 문항 (18~45번) | 개별 문장 (`sentences`) | 듣기 문항 (1~17번) |
| **용지 규격** | B4 Landscape (가로) | A4 Portrait (세로) | **B4 Portrait (세로)** (`257mm x 364mm`) |
| **페이지당 수량** | 2문항 / 페이지 | 6 또는 10문장 / 페이지 | **2문항 / 페이지** (2문항 블록) |
| **기본 템플릿** | `default_b4_question.hwpx`<br>`default_b4_explanation.hwpx` | `default_a4_sentence.hwpx` | **`listening_b4_question.hwpx`**<br>**`listening_b4_explanation.hwpx`** |
| **문제지 레이아웃** | 발문 + 본문 + 선지 | 문장 번호 + 영문 문장 + 필기칸 | **1열: 문항 텍스트**<br>**2열: FELS 약형드랩**<br>**3열: [표현 정리] 5행 필기 표** |
| **해설지 레이아웃** | 출처표 + 본문 + 해설 | (해설지 없음) | **1열: 문항 텍스트(정답)**<br>**2열: 우리말 해석 텍스트**<br>**3열: script 텍스트** |
| **오디오 지원** | 해당 없음 | 해당 없음 | **유인물 순서 맞춤 결합 단일 MP3 다운로드** |
| **프로젝트 키** | `gichul_handout_passage_projects` | `gichul_handout_sentence_projects` | `gichul_handout_listening_projects` |

---

## 4. 단계별 상세 구현 로드맵

### 1단계: 상단 3대 모드 선택기 UI 개편 (`templates/index.html`, `static/css/handouts.css`)
- **1계층 모드 선택기 3분할 탭 바 구축**:
  - `tabHandoutReading` (`📄 독해 유인물`)
  - `tabHandoutSentence` (`📝 문장 유인물`)
  - `tabHandoutListening` (`🎧 듣기 유인물` 신설)
- **컨테이너 분리**:
  - `#handoutReadingArea`: 기존 독해 유인물 화면 요소
  - `#handoutSentenceArea`: 기존 문장 유인물 화면 요소
  - `#handoutListeningArea`: 신규 듣기 유인물 화면 요소 (프로젝트 바, 툴바, 2문항/페이지 미리보기, 다운로드 액션 바)
- **듣기 유인물 전용 액션 툴바**:
  - `[📄 문제 유인물 다운로드 (B4)]`
  - `[📘 해설 유인물 다운로드 (B4)]`
  - `[🎵 전체 통합 MP3 다운로드]` (유인물 순서 결합 단일 오디오)
  - `[📦 일괄 ZIP 다운로드]` (문제지 + 해설지 + 통합 MP3 + 개별 MP3 일괄 압축)

---

### 2단계: 장바구니 및 프로젝트 상태 분리 (`static/js/handout-cart.js`)
- **듣기 프로젝트 독립 스토리지 키 관리**:
  - `KEY_LISTENING_PROJECTS = "gichul_handout_listening_projects"`
  - `KEY_CURRENT_LISTENING_PROJECT_ID = "gichul_handout_cur_listening_proj_id"`
- **듣기 프로젝트 전용 CRUD 함수 추가**:
  - `getListeningProjects()`, `getCurrentListeningProject()`, `createListeningProject()`, `renameListeningProject()`, `deleteListeningProject()`, `switchListeningProject()`
  - `getListeningCartItems()`, `addToListeningCart()`, `removeFromListeningCart()`, `reorderListeningCart()`, `renumberListeningCart()`
- **지문 뷰어 스마트 '유인물 담기' 라우팅**:
  - 현재 문항이 `area === 'listening'`인 경우 ➔ **듣기 유인물 프로젝트**로 자동 분류 저장.
  - 현재 문항이 `area === 'reading'` (또는 일반 독해)인 경우 ➔ **독해 유인물 프로젝트**로 저장.
- **하단 플로팅 장바구니 바 동기화**:
  - 독해 모드 시: `[독해 N문항] [📄 독해 유인물 N ➔]`
  - 문장 모드 시: `[문장 M개] [📝 문장 유인물 M ➔]`
  - 듣기 모드 시: `[듣기 K문항] [🎧 듣기 유인물 K ➔]`

---

### 3단계: 듣기 유인물 프론트엔드 모듈 구현 (`static/js/handout-listening.js`, `static/js/navigation.js`)
- **문항 목록 2문항 페이지 그룹화 렌더링**:
  - 2개 문항씩 1페이지 단위로 묶어서 B4 세로 2x3 레이아웃(문항 텍스트 / FELS 약형드랩 / 표현 정리 표)을 화면에서 직관적으로 미리보기 제공.
  - 문항 번호 수정(`custom_q_num`), 순서 변경(위/아래), 개별 음성 미리듣기 버튼, 문항 삭제.
- **우리말 해석 텍스트 자동 로드/추출**:
  - 해설지 텍스트에서 `[해석]` 섹션을 정밀 분리하여 2열 우리말 해석 데이터 준비.
- **통합 MP3 다운로드 인터랙션**:
  - 버튼 클릭 시 현재 유인물에 담긴 문항들의 ID 목록을 전송하여 백엔드에서 생성된 병합 MP3를 즉시 스트리밍 다운로드.

---

### 4단계: B4 세로 2x3 HWPX 생성 백엔드 엔진 개발 (`gichul/services/hwpx_generator.py`, `gichul/routers/handouts.py`)
- **기존 템플릿 연동**:
  - 문제 템플릿: `static/data/templates/listening_b4_question.hwpx`
  - 해설 템플릿: `static/data/templates/listening_b4_explanation.hwpx`
- **2문항 단위 페이지 복제(Pagination) 알고리즘 (`generate_listening_handout_hwpx`)**:
  - 문항 목록을 2개씩 페어로 분할하여 페이지 복제 및 테이블 주입.
  - **문제 유인물 (Question)**:
    - 1번째 문항: Row 0 / Col 0 (문항 텍스트), Row 0 / Col 1 (FELS 빈칸 드랩), Row 0~6 / Col 2 (`[표현 정리]` 표 원형 유지).
    - 2번째 문항: Row 7 / Col 0 (문항 텍스트), Row 7 / Col 1 (FELS 빈칸 드랩), Row 7~13 / Col 2 (`[표현 정리]` 표 원형 유지).
  - **해설 유인물 (Explanation)**:
    - 1번째 문항: Row 0 / Col 0 (문항 텍스트 + `[정답]`), Row 0 / Col 1 (우리말 해석), Row 0 / Col 2 (script 영문 전문).
    - 2번째 문항: Row 1 / Col 0 (문항 텍스트 + `[정답]`), Row 1 / Col 1 (우리말 해석), Row 1 / Col 2 (script 영문 전문).
  - 머리말 치환: 과목명(`left`), 학교/학원명(`center`), 학생 정보(`right`).
- **다운로드 API 엔드포인트 신설**:
  - `POST /api/handouts/listening/download`: `type` ("question" | "explanation" | "zip") 스트리밍.

---

### 5단계: 듣기 유인물 순서 맞춤 결합 MP3 생성 엔진 (`gichul/tts_service.py`, `gichul/routers/handouts.py`)
- **오디오 PCM 병합 파이프라인 (`merge_audio_pcm_streams`)**:
  - 유인물 문항 순서(`custom_q_num` 순)대로 각 문항의 MP3를 `mp3_to_pcm`으로 디코딩.
  - 이미 적용된 표준 규격(앞뒤 차임벨, 마지막 8초 무음, 1지문 2문항 8초 무음 2회 재생)을 그대로 유지한 채 PCM 버퍼 순차 연결(Concatenation).
  - 단일 고품질 MP3로 인코딩(`encode_pcm_to_mp3`)하여 반환.
  - 미생성 음성이 있을 경우 즉석 합성 후 결합.
- **통합 MP3 다운로드 엔드포인트**:
  - `POST /api/handouts/listening/download-audio`: 병합된 `[유인물명]_전체통합듣기.mp3` 파일 스트리밍 반환.

---

### 6단계: 검증 및 회귀 테스트
- **단위 테스트**:
  - `listening_b4_question.hwpx` 기반 문제지 2문항/페이지 생성 및 OWPML 스키마 검증.
  - `listening_b4_explanation.hwpx` 기반 해설지 2문항/페이지 생성 및 정답/해석/스크립트 3열 정합성 검증.
  - 다중 문항 MP3 PCM 병합 및 오디오 헤더 무결성 검증.
- **통합 회귀 테스트**:
  - 기존 [독해 유인물] B4 2문항 HWPX 생성 100% 정상 작동 확인.
  - 기존 [문장 유인물] A4 단면 구문 분석 100% 정상 작동 확인.
  - 전체 pytest 226개 회귀 테스트 100% 통과 유지.

---

## 5. 진행 현황 (Progress Status)

| 단계 | 작업 항목 | 상태 | 비고 |
|---|---|---|---|
| 1단계 | 상단 3대 모드 탭(독해·문장·듣기) 1계층 UI 개편 | ✅ 완료 | `index.html`, `handouts.css` 3분할 탭 및 레이아웃 완비 |
| 2단계 | 장바구니/프로젝트 분리 (듣기 프로젝트 독립 스토리지) | ✅ 완료 | `handout-cart.js` CRUD, 1~17번 스마트 라우팅 완비 |
| 3단계 | 듣기 유인물 프론트엔드 모듈 (`handout-listening.js`) | ✅ 완료 | 2문항/페이지 그룹화, 3열 미리보기, 순서 변경, 번호 관리 |
| 4단계 | B4 세로 2x3 템플릿 기반 HWPX 문제지/해설지 생성 엔진 | ✅ 완료 | `hwpx_generator.py`, `routers/handouts.py` 실물 템플릿 연동 |
| 5단계 | 유인물 문항 순서 맞춤 결합 단일 통합 MP3 다운로드 파이프라인 | ✅ 완료 | `tts_service.py` 2.0s 무음 결합 MP3 스트리밍 완비 |
| 6단계 | B4 스키마, 오디오 병합 무결성 및 전체 회귀 테스트 | ✅ 완료 | pytest 231개 전체 테스트 100% 통과 (5개 신규 테스트 추가) |
