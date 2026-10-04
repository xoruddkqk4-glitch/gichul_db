---
name: apply
description: Triggered by '/apply', '/action apply', or explicit requests to apply/execute the implementation plan created by the '/ask' skill. Reads the latest implementation plan and executes the planned code changes directly without needing phrases like '반영해줘'.
---

# 계획서 즉시 적용 스킬 (`apply`)

> [!IMPORTANT]
> **실행 목적 및 트리거 조건**
> 이 스킬은 `/ask` 스킬 등을 통해 `docs/plans/`에 작성된 계획서가 있을 때, **사용자가 번거롭게 '반영해줘', '코드 적용해줘'를 쓰지 않고 `/apply` 명령어 하나로 계획서를 즉시 코드에 반영**하기 위한 실행 스킬입니다.

## 📌 주요 원칙 (Core Rules)

1. **계획서 기반 정확한 구현 (Plan-Driven Execution)**:
   - 대상 계획서를 정확히 확인하고 순서대로 소스 코드를 수정합니다. 대상 결정 순서:
     1. 사용자가 파일명이나 단계(예: `/apply 1단계`, `/apply 3-A`)를 지정하면 그 계획서의 해당 부분만 적용
     2. 지정이 없으면 `docs/README.md`에서 🔄 진행 중 또는 ⬜ 대기 상태인 가장 최근 `docs/plans/` 계획서
     3. 대상이 모호하면 적용하지 말고 사용자에게 확인
2. **터미널 고속 검증 준수 (Rule 2)**:
   - 코드 변경 후 브라우저나 스크린샷 검증을 띄우지 않고, 터미널 기반 정적 검증(`python -m py_compile`, `node -c` 등)을 즉시 수행합니다.
3. **자동 커밋 금지 준수 (Rule 3 & 4)**:
   - 코드 적용과 터미널 검증까지만 완료하고 대기합니다. Git 커밋 및 푸시는 사용자가 명시적으로 `/git-commit` 명령어를 입력할 때까지 실행하지 않습니다.

---

## 📋 수행 절차 (Workflow)

1. **최신 계획서 확인**:
   - 위 순서로 `docs/plans/`의 대상 계획서를 로드하여 변경 대상 파일 및 수정 항목을 파악합니다.
2. **코드 변경 단계별 적용**:
   - `replace_file_content`, `multi_replace_file_content`, `write_to_file` 등의 도구를 사용하여 계획서에 명시된 파일들을 차례대로 정확하게 수정합니다.
3. **터미널 정적 오류 검증**:
   - 수정된 언어에 맞추어 빠른 정적 검증을 실행합니다:
     - Python: `python -m py_compile <수정된 파일>`
     - JavaScript: `node -c <수정된 파일>`
4. **결과 보고**:
   - 반영된 파일 목록, 주요 변경 내용, 정적 검증 통과 결과를 사용자에게 명확하고 간결하게 보고합니다.
5. **진행 상태 갱신**:
   - 계획서의 "진행 현황" 표와 `docs/README.md`의 상태를 갱신합니다 (⬜ 대기 → 🔄 진행 중 → ✅ 완료).
