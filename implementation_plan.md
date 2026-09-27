# Implementation Plan - 일괄 업로드 진행 상태 시각화 및 완료 버튼 전환 UX 개선

## 1. 개요 및 배경
- **문제점**:
  정답률 CSV 등 일괄 업로드가 진행되는 도중 및 10개 세트 처리가 완료된 시점(`🎉 일괄 처리 완료! 10 / 10`)에도,
  하단 우측 실행 버튼이 `📊 정답률 CSV 10개 세트 일괄 반영 시작` 문구 그대로 비활성화되어 멈춰 있거나,
  데이터 처리 중임을 알려주는 동적 아이콘(스피너)이 버튼 자체에 표시되지 않아 사용자가 멈춤/오류로 오인하는 문제 발생.
- **원인 분석**:
  1. **버튼 텍스트/스피너 미반영**:
     - `upload.js`에서 업로드 시작 시 `btnStartBatchUpload.disabled = true;`만 호출하고, 버튼 라벨을 변경하거나 동적 회전 아이콘(스피너)을 넣지 않아 버튼 모양이 시작 전과 동일하게 유지됨.
  2. **후속 동기화 중 블로킹 및 텍스트 전환 지연**:
     - 10개 세트 업로드 루프가 끝난 뒤 `loadStats()`, `await fetchRegisteredExamsSet()`, `await loadFilesStatusList()`, `await loadExamsManagerList()`, `executeSearch("results")` 등 여러 비동기 후속 처리가 실행됨.
     - 이 과정에서 상단 프로그레스 바는 이미 `100% (10/10 완료)`를 가리키는데, 하단 버튼은 여전히 `반영 시작` 문구 그대로 비활성화되어 대기함.
  3. **예외 처리 부재(Uncaught Exception)**:
     - 만약 후속 비동기 함수 중 하나라도 네트워크 오류나 DOM 예외가 발생하면, 하단 `btnStartBatchUpload.textContent = "✔ 처리 완료 (닫기)"` 코드가 실행되지 않고 영구히 시작 버튼 모양으로 멈춤.

---

## 2. 변경 대상 파일
- `static/js/upload.js`:
  - `btnStartBatchUpload` 클릭 이벤트 핸들러 내부의 상태 전환 및 텍스트 렌더링 로직 개선

---

## 3. 세부 설계 및 개선 내용

### 3.1 처리 진행 중 버튼 자체의 동적 스피너 및 진행률 표시
- 일괄 업로드가 시작되면:
  - `btnStartBatchUpload.disabled = true;`
  - `btnStartBatchUpload.innerHTML = '<span style="display:inline-block; animation:spin 1s linear infinite; margin-right:6px;">⏳</span> 데이터 처리 중... (0/${sets.length})';`
- 각 세트 처리 중:
  - `btnStartBatchUpload.innerHTML = '<span style="display:inline-block; animation:spin 1s linear infinite; margin-right:6px;">⏳</span> 데이터 반영 중... (${i + 1}/${sets.length})';`

### 3.2 후속 데이터 동기화 단계 안내
- 모든 세트 업로드 루프 직후 후속 동기화 작업(`loadStats`, `loadFilesStatusList` 등)을 수행할 때:
  - `btnStartBatchUpload.innerHTML = '<span style="display:inline-block; animation:spin 1s linear infinite; margin-right:6px;">⏳</span> 최종 데이터 동기화 중...';`
  - 사용자에게 현재 시스템이 멈춘 것이 아니라 최종 데이터를 갱신 중임을 시각적으로 명확히 전달.

### 3.3 Try-Finally 블록을 통한 완료 버튼(`✔ 처리 완료 (닫기)`) 전환 100% 보장
- 후속 동기화 작업에 `try-catch-finally`를 적용하여, 만에 하나 백그라운드 갱신 중 예외가 발생하더라도:
  ```javascript
  finally {
    if (btnCancelBatchModal) {
      btnCancelBatchModal.disabled = false;
      btnCancelBatchModal.textContent = "닫기";
    }
    btnStartBatchUpload.disabled = false;
    btnStartBatchUpload.dataset.state = "finished";
    btnStartBatchUpload.innerHTML = "✔ 처리 완료 (닫기)";
    btnStartBatchUpload.style.background = "#059669";
    btnStartBatchUpload.style.borderColor = "#059669";
  }
  ```
  - 반드시 '처리 완료 (닫기)' 버튼으로 전환되도록 보장.

---

## 4. 검증 계획
1. **정적 문법 검사**: `node --check static/js/upload.js`
2. **상태 전환 시뮬레이션**:
   - `클릭 직후` -> ⏳ 동적 스피너 및 `데이터 처리 중... (0/N)`
   - `세트 진행 중` -> ⏳ `데이터 반영 중... (K/N)` 실시간 갱신
   - `루프 완료 후` -> ⏳ `최종 데이터 동기화 중...`
   - `최종 완료` -> 초록색 `✔ 처리 완료 (닫기)` 버튼 활성화

---

## 5. 실행 정책 안내
- 본 문서는 `/ask` 모드에 따라 작성된 구현 계획서입니다.
- 사용자의 명시적인 승인 또는 실행 요청(예: "반영해줘", "진행해줘")이 전달되기 전까지 소스코드는 일체 수정하지 않습니다.
