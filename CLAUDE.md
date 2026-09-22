# CLAUDE.md — 05-gichul_db

에이전트 실행 규칙: 터미널 전용 고속 검증 (`.agents/rules/rules.md` 이식)

## 1. 브라우저 / 시각 검증 정책
- **엄격 금지:** 일반적인 코드 수정 작업 중에 브라우저(Chrome, Playwright, Scratchpad 등)를 구동하거나 시각 검증을 수행하지 않습니다.
- **자동 스크린샷 금지:** 코드 수정 후 스크린샷 촬영이나 시각적 확인을 절대 자동으로 수행하지 않습니다.
- UI 갱신은 브라우저의 Hot Module Replacement (HMR) 기능을 신뢰합니다.
- **예외:** 사용자가 `/scratchpad`, `/action scratchpad` 명령어를 입력하거나 "scratchpad로 검증해줘"처럼 명시적으로 요청한 경우에만 예외를 적용합니다.

## 2. 터미널 기반 오류 검증
- 코드 변경 후에는 브라우저 확인 대신 터미널 명령으로 빠른 정적 검증만 수행합니다.
- 프로젝트 성격에 맞춘 빠른 타입 검사/린트/구문 검사 수행:
  - TypeScript: `npx tsc --noEmit` (또는 `npm run type-check`)
  - Next.js / React: `npm run lint`
  - Vanilla JS / Node.js: `node -c app.js` (또는 `node --check <file>.js`)
- 경미한 경고는 끝없이 고치려 하지 말고 간단히 보고한 뒤 작업을 마칩니다.
- 무거운 데브 서버, 빌드 명령어(`npm run build`), 장시간 테스트를 임의로 실행하지 않습니다.

## 3. 작업 흐름 최적화 (일반 수정 모드)
- 일반적인 코드 수정이나 오류 복구 작업 시:
  - 코드 변경을 적용하고 빠른 터미널 검증 후 즉시 작업을 마칩니다.
  - **절대로 커밋(`git commit`)이나 푸시(`git push`)를 자동으로 하지 않습니다.**
- 사용자가 명시적으로 `/git-commit` 명령어를 입력할 때까지 대기합니다.

## 4. Git 커밋 및 푸시 정책 (오직 `/git-commit` 수신 시 실행)
- **엄격 조건:** 오직 `/git-commit`, `/action git-commit` 또는 "README 업데이트 후 커밋/푸시" 요청 시에만 실행합니다.
- 일반적인 코드 수정 후에는 절대로 커밋/푸시를 자동으로 하지 않습니다.
- **수행 절차:**
  1. `README.md` 하단에 작업 내용과 검증 결과를 누적 기록합니다.
  2. 상세 커밋 메시지를 작성하고 `git add .` 및 `git commit`을 진행합니다.
  3. GitHub 원격 저장소(`main` 브랜치)로 `git push`합니다.
- **README.md 누적 기록 규칙:**
  - `README.md` **맨 하단**에 **서울 기준 시각(KST, `YYYY-MM-DD HH:mm`)** 으로 누적 기록합니다.
  - 각 항목에 **날짜 및 시간(KST)**, **커밋 ID(Commit Hash)**, **수정 내용**이 반드시 포함되어야 합니다.
- 커밋 메시지는 한국어로 작성하며 제목은 `docs: update README.md and detailed commit results` 포맷을 따릅니다.

## 5. `/ask` 질의응답 및 계획 전용 모드
- `/ask` 질의를 받으면 프로젝트 소스 코드를 절대로 수정하지 않습니다.
- 단순 질문은 대화 답변으로 완결하고, 기술적/복잡한 변경 요청은 `implementation_plan.md` 계획서 작성까지만 진행합니다.
- **계획서 자동 실행 금지:** `/ask` 모드로 작성된 계획서는 자동 승인이 전달되더라도 절대로 자동으로 코드를 변경하지 않으며, 사용자의 명시적 추가 지시("실행해줘" 등)가 있을 때까지 대기합니다.
- 상세는 `.agents/skills/ask/SKILL.md` 참조.

## 6. `/scratchpad` 브라우저 검증 전용 모드
- 사용자가 `/scratchpad`, `/action scratchpad`, 또는 "scratchpad로 검증해줘"라고 명시적으로 요청한 경우에 한해 브라우저 검증을 수행합니다.
- 상세는 `.agents/skills/scratchpad/SKILL.md` 참조.

## 7. 원본 규칙 파일
이 문서는 `.agents/rules/rules.md`를 기반으로 구성되었습니다. 규칙을 변경할 때는 함께 갱신하세요.
- 스킬 정의 원본은 `.agents/skills/*/SKILL.md`이며, Claude Code 슬래시 명령(`/git-commit`, `/ask`, `/scratchpad`)용으로 `.claude/skills/*/SKILL.md`에 미러링되어 있습니다. 스킬을 수정할 때는 두 위치를 함께 갱신하세요.
