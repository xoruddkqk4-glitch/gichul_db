---
name: ask
description: Triggered by '/ask', '/action ask', or requests starting with '/ask'. Answers questions or creates an implementation plan WITHOUT modifying source code. Generated plans must NOT be automatically executed.
---

> 원본: `.agents/skills/ask/SKILL.md` (Claude Code 슬래시 명령용 미러. 규칙 변경 시 두 파일을 함께 갱신)

# 코드 수정 없는 질의응답 및 계획서 작성 전용 스킬 (`ask`)

`/ask`, `/action ask` 명령이나 질문/계획서 작성 전용 요청을 수신했을 때 실행되는 스킬입니다.

## 핵심 원칙 (Core Rules)

1. **코드 수정 절대 금지 (No Code Modification)**:
   - 워크스페이스 내 프로젝트 소스 코드(모든 소스 파일, 설정 파일, 스크립트 등)를 절대로 수정하거나 삭제하지 않습니다.
   - 조회/검색 도구(Read, Grep, Glob, 읽기 전용 셸 명령)만 활용하여 분석 및 답변합니다.
   - **유일한 예외:** `docs/plans/`, `docs/reviews/` 문서 작성과 `docs/README.md` 목록 갱신은 허용됩니다.

2. **답변 또는 계획서 작성까지만 수행 (Answer or Plan Only)**:
   - 단순 질문인 경우 대화창 답변으로 완결합니다.
   - 기술적 구현/복잡한 코드 변경 작업 요청인 경우 계획서 작성까지만 진행합니다.
   - **저장 규칙:**
     - 계획서: `docs/plans/YYYY-MM-DD_<영문-주제-슬러그>.md` (서울 기준 날짜, 같은 날 여러 개면 `YYYY-MM-DD_01_...`)
     - 리뷰·분석 보고서: `docs/reviews/YYYY-MM-DD_<영문-주제-슬러그>.md`
     - 기존 계획서를 **덮어쓰지 않고** 항상 새 파일로 만듭니다.
     - 작성 후 `docs/README.md` 목록에 날짜·제목·상태(⬜ 대기)를 추가합니다.
     - 계획서에는 `/apply`가 추적할 수 있도록 "진행 현황" 표를 넣습니다.

3. **계획서 자동 실행 절대 금지 (Never Auto-Execute Plan)**:
   - `/ask` 모드로 작성된 계획서는 시스템 정책 등에 의해 자동 승인(Auto-Approve/Proceed) 되더라도 **절대로 자동으로 코드를 수정/실행해서는 안 됩니다**.
   - 계획서 작성 후 반드시 사용자의 **명시적 추가 명령(`/apply`, "반영해줘" 등)**이 있을 때까지 대기합니다.

## 수행 절차 (Workflow)

1. **요청 분석 및 기존 코드 분석**: 사용자 질의를 확인하고 필요한 파일 및 구조를 조회하여 분석합니다.
2. **응답 구분**:
   - **단순 질의**: 코드 수정 없이 질문에 정확하고 명쾌하게 답변합니다.
   - **복잡한 작업/구현 요청**: `docs/plans/`에 새 계획서 파일을 만들어 분석 결과와 구현 계획을 작성하고 `docs/README.md`에 등록합니다.
3. **완료 및 사용자 승인 대기**: 답변 또는 계획서 경로를 사용자에게 제공하고, 사용자의 명시적인 추가 실행 요청(`/apply` 등) 전까지 작업을 정지하고 대기합니다.
