# 교사용 듣기 수업 파형 플레이어 반복 재생 단축키([, ], \) 및 드래그 연동 구현 계획서

## 1. 개요 및 배경

교사용 듣기 유인물 수업 진행 전용 전체화면 창(`listening-classroom.js`)에서 교사가 오디오를 청취하며 수업을 진행할 때, 보다 빠르고 직관적으로 특정 어휘나 연음 구간을 반복 청취할 수 있도록 **키보드 단축키(`[`, `]`, `\`)를 통한 구간 시작점/끝점 설정 및 해제 기능**을 도입합니다.  
기존의 마우스 드래그 앤 드롭 구간 선택 기능과 완벽히 융합되어, 마우스와 키보드 양쪽 모두에서 자연스럽게 구간을 지정하고 A-B Looper 엔진을 가동할 수 있도록 설계합니다.

---

## 2. 사용자 핵심 요구사항 및 기능 명세

1. **반복 재생 시작점 설정: `[` 키 (`BracketLeft`)**
   - 오디오 재생 도중 또는 일시정지 상태에서 `[` 키를 누르면, 현재 재생 위치(`currentTime`)가 반복 재생 시작점(`startTime`)으로 지정됩니다.
   - 이미 끝점(`endTime`)이 설정되어 있고 `startTime < endTime`인 경우 즉시 유효 구간으로 확정 및 오버레이 갱신.
   - 끝점이 아직 설정되지 않은 경우, 시작점 마커를 시각적으로 표시하고 끝점(`]`) 입력을 대기(또는 현재 위치부터 오디오 끝까지를 임시 구간으로 가시화).

2. **반복 재생 끝점 설정: `]` 키 (`BracketRight`)**
   - `]` 키를 누르면, 현재 재생 위치(`currentTime`)가 반복 재생 끝점(`endTime`)으로 지정됩니다.
   - 시작점(`startTime`)이 이미 설정되어 있는 경우: `startTime ~ endTime` 구간이 확정되며, 오버레이 박스가 갱신되고 즉시 A-B Looper 반복 재생이 시작(또는 준비 완료)됩니다.
   - 시작점이 아직 없는 상태에서 `]`를 누른 경우: `0초 ~ currentTime`을 반복 구간으로 자동 설정합니다.

3. **반복 재생 구간 해제: `\` 키 (`Backslash`)**
   - `\` 키를 누르면 설정된 반복 구간이 즉시 해제(`clearSelectedRegion()`)됩니다.
   - 파형 상의 반투명 시안 하이라이트 박스와 `✕ 구간 선택 해제` 버튼이 숨겨지고, 기본 문장 전체 재생 모드로 원복됩니다.

4. **마우스 드래그 앤 드롭 구간 설정 기능 유지 및 상호 연동**
   - 캔버스 파형 위에서 마우스 좌클릭 드래그로 구간을 설정하는 기존 인터랙션을 100% 보존합니다.
   - 마우스로 잡은 구간의 시작점/끝점을 키보드 `[`나 `]`로 미세 조정할 수 있으며, 마우스로 잡은 구간도 `\` 키로 원클릭 해제할 수 있도록 동일한 데이터 모델(`this.selectedRegion`)을 공유합니다.

5. **수업 창 하단 단축키 가이드 팁 갱신**
   - `templates/index.html` 하단 단축키 가이드 영역에 새로 추가된 단축키 `<kbd>[</kbd> 구간 시작`, `<kbd>]</kbd> 구간 끝`, `<kbd>\</kbd> 구간 해제`를 직관적으로 추가 표기합니다.

---

## 3. 세부 기술 설계 및 아키텍처

### 3.1. `ListeningClassroomController` 메서드 추가 (`static/js/listening-classroom.js`)

- **`setRegionStartFromCurrentTime()`**:
  ```javascript
  const curTime = this.audioElement.currentTime;
  const duration = this.audioDuration || 1;
  const curRatio = Math.max(0, Math.min(1, curTime / duration));

  let endRatio = this.selectedRegion ? this.selectedRegion.endRatio : 1.0;
  let endTime = this.selectedRegion ? this.selectedRegion.endTime : duration;

  // 시작점이 끝점보다 뒤에 있으면 끝점을 duration으로 확장
  if (curTime >= endTime) {
    endRatio = 1.0;
    endTime = duration;
  }

  this.selectedRegion = {
    startRatio: curRatio,
    endRatio: endRatio,
    startTime: curTime,
    endTime: endTime
  };

  this.updateRegionOverlay();
  if (this.dom.btnClearRegion) {
    this.dom.btnClearRegion.style.display = "inline-flex";
  }
  this.updatePlayButtonUi();
  ```

- **`setRegionEndFromCurrentTime()`**:
  ```javascript
  const curTime = this.audioElement.currentTime;
  const duration = this.audioDuration || 1;
  const curRatio = Math.max(0, Math.min(1, curTime / duration));

  let startRatio = this.selectedRegion ? this.selectedRegion.startRatio : 0.0;
  let startTime = this.selectedRegion ? this.selectedRegion.startTime : 0.0;

  // 끝점이 시작점보다 앞에 있으면 시작점을 0으로 설정
  if (curTime <= startTime) {
    startRatio = 0.0;
    startTime = 0.0;
  }

  this.selectedRegion = {
    startRatio: startRatio,
    endRatio: curRatio,
    startTime: startTime,
    endTime: curTime
  };

  this.updateRegionOverlay();
  if (this.dom.btnClearRegion) {
    this.dom.btnClearRegion.style.display = "inline-flex";
  }
  this.updatePlayButtonUi();

  // 끝점 지정 시 즉시 루프 반복 시작
  this.startRegionLoop();
  ```

### 3.2. 전역 키보드 이벤트 분기 처리 (`bindEvents`)

- 한글 입력기(IME) 상태에서도 오작동 없이 키 입력을 감지할 수 있도록 `e.code`를 기준으로 판별합니다.
  - `BracketLeft`: `[` 키 입력 감지 → `setRegionStartFromCurrentTime()`
  - `BracketRight`: `]` 키 입력 감지 → `setRegionEndFromCurrentTime()`
  - `Backslash`: `\` 키 입력 감지 → `clearSelectedRegion()`
- `input`, `select`, `textarea` 포커스 중에는 단축키가 실행되지 않도록 기존 가드 로직을 유지합니다.

### 3.3. 모달 하단 단축키 가이드 UI 수정 (`templates/index.html`)

- `classroom-shortcut-tips` 컨테이너에 신규 단축키 배지 추가:
  ```html
  <div class="classroom-shortcut-tips">
    <span>💡 단축키:</span>
    <kbd>Space</kbd> 재생/정지
    <kbd>[</kbd> 구간 시작
    <kbd>]</kbd> 구간 끝
    <kbd>\</kbd> 구간 해제
    <kbd>←</kbd> 이전 문장
    <kbd>→</kbd> 다음 문장
    <kbd>S</kbd> 약형/Script 전환
    <kbd>T</kbd> 해석 토글
    <kbd>R</kbd> 구간 반복
    <kbd>F</kbd> 전체화면
    <kbd>Esc</kbd> 닫기
  </div>
  ```

---

## 4. 단계별 구현 계획 (Phases)

### 1단계: 컨트롤러에 단축키용 시작점/끝점 설정 로직 구현
- `static/js/listening-classroom.js` 내에 `setRegionStartFromCurrentTime()` 및 `setRegionEndFromCurrentTime()` 메서드를 추가하고, 오버레이 업데이트 및 유효성 검사 로직을 구현합니다.

### 2단계: 키보드 이벤트 리스너 바인딩 및 마우스 드래그 연동
- `listening-classroom.js`의 `keydown` 이벤트 핸들러에 `BracketLeft`, `BracketRight`, `Backslash` 분기를 추가하고, 마우스 드래그 선택 상태와의 상호 전환을 검증합니다.

### 3단계: HTML 모달 하단 단축키 가이드 UI 업데이트
- `templates/index.html`의 칠판 모달 하단 안내 영역에 `[`, `]`, `\` 단축키 배지를 직관적으로 추가합니다.

### 4단계: 터미널 정적 검증 및 런타임 회귀 테스트
- `node -c static/js/listening-classroom.js` 구문 검사.
- `python -m py_compile` 백엔드 파일 검사 및 관련 테스트 수행.

---

## 5. 진행 현황 (Progress Status)

| 단계 | 작업 내용 | 담당 파일 | 상태 |
|---|---|---|:---:|
| 1단계 | 컨트롤러에 단축키용 시작점/끝점 설정 로직 구현 | `static/js/listening-classroom.js` | ✅ 완료 |
| 2단계 | 키보드 이벤트 리스너 바인딩 및 마우스 드래그 연동 | `static/js/listening-classroom.js` | ✅ 완료 |
| 3단계 | HTML 모달 하단 단축키 가이드 UI 업데이트 | `templates/index.html` | ✅ 완료 |
| 4단계 | 터미널 정적 검증 및 런타임 회귀 테스트 | `static/js/listening-classroom.js`, `templates/index.html` | ✅ 완료 |
