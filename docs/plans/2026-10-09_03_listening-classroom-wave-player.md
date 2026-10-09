# 교사용 듣기 유인물 수업 진행 전용 전체화면 파형 뷰어 및 문장별 구간 반복 플레이어 구현 계획서

## 1. 개요 및 배경

본 계획서는 교사가 제작한 **듣기 문제 유인물(세트)**을 활용하여 교실(전자칠판, 빔프로젝터)에서 학생들과 효율적으로 인터랙티브 듣기 수업을 진행할 수 있도록, **'듣기 유인물 수업 모드' 전체화면 창**을 제공하고, 음성을 **문장 단위로 분할 재생**하며, 첨부 이미지 규격의 **고대비 오디오 Waveform 파형 뷰어**, **마우스 드래그 앤 드롭 구간 선택**, **선택 구간 N회 반복 재생** 기능을 구축하기 위한 기술 설계 및 구현 로드맵입니다.

---

## 2. 사용자 핵심 요구사항 및 기능 명세

1. **수업 진행 창 실행 버튼 (Entry Button)**:
   - **위치**: 듣기 유인물 우측 패널의 '📥 듣기 유인물 및 오디오 다운로드' 카드 바로 아래 배치.
   - **가시성**: 교사가 즉시 인지할 수 있는 대형 그라디언트 액센트 버튼 (`linear-gradient`, 섀도우 및 펄스 효과, `🎧 칠판형 듣기 수업 모드 시작`).
2. **수업 진행 창 (Classroom Fullscreen Window / Modal)**:
   - 빔프로젝터/전자칠판에 최적화된 고대비 칠판형 다크 테마 (`#081b2e` ~ `#0f172a`).
   - 우측 상단 `[⛶ 전체 화면]` 버튼 및 HTML5 Fullscreen API 연동 (단축키 `F` / `F11`).
3. **문장 단위 분할 및 수업 집중 디스플레이**:
   - 유인물 세트 내 문항 대본을 문장 단위로 분할하여 한 문장씩 선명하게 표시.
   - 화자 배지 (`[M:]`, `[W:]`), 대형 영문 문장 텍스트(24~32px).
   - `[FELS 빈칸 가리기/보기]` 토글 스위치 (학생 딕테이션 퀴즈용).
   - `[우리말 해석 보기]` 토글 스위치.
4. **오디오 Wave 파형 창 (첨부 이미지 규격 100% 재현)**:
   - 딥 블루 배경 (`#083358` ~ `#0b3b60`).
   - 상단 중앙 파일명 라벨: `${프로젝트명}_${문항번호}번_문장${idx}.mp3`.
   - Web Audio API 기반 오디오 버퍼 디코딩 및 정밀 Canvas 파형 렌더링.
   - 선명한 형광 민트/시안 파형 (`#00ffcc` / `#10b981`) 및 재생 진행 하이라이트.
   - 중앙 백색 재생 헤드(Playhead) 세로선 및 하단 중앙 타임코드 (`00:03.4 / 00:08.2`).
5. **마우스 드래그 앤 드롭 구간 선택 (Region Selection)**:
   - 파형 위에서 마우스 좌클릭 후 드래그 시 반투명 시안 하이라이트 구간 박스 생성.
   - 구간 좌우 조절 핸들 제공 및 시작/종료 시간 정밀 매핑.
   - 파형 빈 영역 클릭 시 구간 선택 해제.
6. **선택 구간 반복 재생 엔진 (A-B Looper)**:
   - 드래그 선택 구간을 원하는 횟수(1회, 2회, 3회, 5회, 무한 반복)만큼 정확히 루프 재생.
   - 현재 반복 진행 상태 실시간 표시 (예: `반복 2/3회`).
7. **교사용 편리한 문장 이동 & 단축키**:
   - `[⏮ 이전 문장]`, `[다음 문장 ⏭]` 원클릭 버튼 및 키보드 단축키 (`←`, `→`).
   - `Space`: 재생/일시정지, `R`: 선택 구간 반복, `Esc`: 닫기/전체화면 해제.

---

## 3. 세부 아키텍처 및 구현 설계

### 3.1. 프론트엔드 모달 및 버튼 구조 (`templates/index.html`, `static/css/handouts.css`)
- **버튼 추가 (`#btnOpenListeningClassroomModal`)**:
  - `handoutListeningLayout` 내 `handout-settings-panel`의 다운로드 카드 하단에 삽입.
  - 가로 폭 100%, 패딩 14px, 폰트 1.05rem, 볼드, 바이올렛/블루 네온 그라디언트.
- **모달 DOM (`#listeningClassroomModal`)**:
  - `modal-backdrop` 기반 전체 화면 오버레이.
  - 상단 툴바: 프로젝트명, 문항 네비게이션 드롭다운, 전체화면 토글, 닫기 버튼.
  - 중앙 상단: 문장 텍스트 칠판 영역 (대형 영문 텍스트, FELS 빈칸 토글, 해석 토글).
  - 중앙 중단: 오디오 Wave 캔버스 컨테이너 (`#listeningWaveContainer`, 캔버스 폭 100%, 높이 160px).
  - 중앙 하단: 타임코드 및 재생 프로그레스, 볼륨/배속 컨트롤러.
  - 하단 바: 이전/다음 문장 버튼, 재생/정지 버튼, 구간 반복 횟수 선택 드롭다운, 단축키 가이드.

### 3.2. 백엔드 REST API 설계 (`gichul/routers/handouts.py`, `gichul/tts_service.py`)
- **`POST /api/handouts/listening/classroom-data`**:
  - 입력: `{"passage_ids": ["..."], "project_title": "..."}`
  - 처리: 각 문항의 메타데이터, 문장 분할 목록(`sentences`: 순번, 화자, 영문, 우리말 해석, FELS 약형드랩), 문항 전체 오디오 경로 반환.
- **`GET /api/handouts/listening/sentence-audio`**:
  - 쿼리 파라미터: `passage_id`, `order_index`, `speaker`, `text`
  - 처리: 해당 문장의 개별 오디오가 존재하면 반환, 없으면 즉시 Edge-TTS(남/여 화자 분기)로 합성하여 스트리밍 반환 및 캐싱.

### 3.3. 파형 시각화 및 드래그 구간 반복 모듈 (`static/js/listening-classroom.js`)
- **Canvas 파형 디코더**:
  - `AudioContext.decodeAudioData(arrayBuffer)` -> 채널 데이터 다운샘플링 -> 피크(Peaks) 산출.
  - 첨부 이미지와 완벽히 일치하는 딥 블루 배경(`linear-gradient(#082846, #0b3b60)`) + 네온 민트(`rgb(0, 255, 204)`) 파형 렌더링.
- **드래그 인터랙션**:
  - `canvas.addEventListener("mousedown")`, `mousemove`, `mouseup` 이벤트를 통해 `regionStartRatio`, `regionEndRatio` 계산.
  - 실시간 오버레이 캔버스 또는 DOM 셀렉션 박스로 하이라이트.
- **루프 오디오 엔진**:
  - HTML5 `Audio` 객체의 `timeupdate` 이벤트 리스너를 통해 `audio.currentTime >= regionEndTime` 시 루프 카운트 검사 및 `audio.currentTime = regionStartTime` 재설정.

---

## 4. 단계별 구현 계획 (Phases)

### 1단계: 백엔드 수업 데이터 및 문장 오디오 API 구축
- `gichul/routers/handouts.py` 및 `gichul/tts_service.py`에 수업용 문장 데이터 조회 API(`POST /api/handouts/listening/classroom-data`) 및 단일 문장 고속 오디오 스트리밍 API(`GET /api/handouts/listening/sentence-audio`) 신설.

### 2단계: 프론트엔드 UI 배치 및 칠판형 전체화면 모달 마크업
- `templates/index.html`에 고가시성 수업 시작 버튼(`#btnOpenListeningClassroomModal`) 및 칠판형 수업 모달 DOM 추가.
- `static/css/handouts.css`에 다크 블루 네온 칠판 테마 및 반응형/전체화면 스타일 추가.

### 3단계: 오디오 Waveform 캔버스 렌더러 & 드래그 구간 선택 구현
- `static/js/listening-classroom.js` 신설: Web Audio API 기반 오디오 디코딩 및 첨부 이미지 스타일 Canvas 파형 드로잉.
- 마우스 드래그 앤 드롭 구간 선택(Region Selection) 핸들러 구현.

### 4단계: 구간 반복 재생 엔진 & 문장별 네비게이션/단축키 완성
- 선택 구간 N회 반복 재생 엔진(A-B Looper) 및 반복 카운터 구현.
- 이전/다음 문장 이동, FELS 빈칸/해석 토글, 전체화면 토글 및 키보드 단축키 바인딩.
- `static/js/handout-listening.js`와 메인 이벤트 연결.

### 5단계: 검증 및 테스트
- `python -m py_compile`, `node -c` 정적 검증.
- `pytest tests/` 전체 회귀 검증.

---

## 5. 진행 현황 (Progress Status)

| 단계 | 작업 내용 | 담당 파일 | 상태 |
|---|---|---|:---:|
| 1단계 | 수업용 문장 분할 데이터 & 문장 오디오 스트리밍 API 신설 | `gichul/routers/handouts.py`, `gichul/tts_service.py` | ✅ 완료 |
| 2단계 | 고가시성 수업 시작 버튼 & 칠판형 전체화면 모달 마크업/스타일 | `templates/index.html`, `static/css/handouts.css` | ✅ 완료 |
| 3단계 | 첨부 이미지 규격 Canvas 파형 렌더러 & 마우스 드래그 구간 선택 | `static/js/listening-classroom.js` | ✅ 완료 |
| 4단계 | 구간 N회 반복 재생 엔진 & 문장 이동/단축키/FELS 토글 연동 | `static/js/listening-classroom.js`, `static/js/handout-listening.js` | ✅ 완료 |
| 5단계 | 터미널 정적 검증 및 전체 회귀 테스트 통과 | 전체 파일 | ✅ 완료 |
