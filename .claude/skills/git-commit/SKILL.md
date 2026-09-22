---
name: git-commit
description: Triggered strictly by '/git-commit', '/action git-commit', or explicit requests to update README.md with detailed verification results and commit/push to GitHub. Never executed automatically during standard code editing tasks.
---

> 원본: `.agents/skills/git-commit/SKILL.md` (Claude Code 슬래시 명령용 미러. 규칙 변경 시 두 파일을 함께 갱신)

# README 자동 업데이트 & Git 커밋/푸시 스킬 (`git-commit`)

> [!IMPORTANT]
> **실행 조건 (Strict Trigger Policy)**
> 이 스킬은 **오직 사용자가 `/git-commit`, `/action git-commit` 명령어를 명시적으로 입력하거나 "README 업데이트 후 커밋/푸시해줘"라고 직접 요청했을 때만 실행**됩니다.
> 일반적인 코드 수정, 버그 수정, 리팩토링 요청 시에는 절대로 본 커밋/푸시 스킬을 자동 실행하지 않습니다.

## 주요 기능 및 수행 절차 (Workflow)

1. **사용자 요청 및 변경 사항 분석**:
   - 대화 내역의 사용자 요청 배경, 해결된 문제, 구현된 기능을 종합 정리합니다.
   - 실제 변경된 코드, 설정 파일 및 문서 내역을 검토합니다 (`git status`, `git diff`).

2. **README.md 문서 업데이트 및 누적 이력 기록**:
   - 변경 사항 및 새로 추가되거나 검증된 기능 내역을 대상 프로젝트 루트의 **`README.md`**에 체계적으로 반영합니다.
   - **`README.md` 맨 뒷부분 누적 기록 규칙**:
     - `README.md` 수정 시, 업데이트되는 내용을 파일의 맨 뒷부분(하단)에 **날짜 및 시간(서울 기준 시각 KST: YYYY-MM-DD HH:mm)** 기준으로 누적으로 기록합니다.
     - 누적 기록에는 **날짜 및 시간(KST)**, **커밋 ID(Commit Hash)**, **수정 내용(Modification Details)**, **검증 결과**가 반드시 포함되어야 합니다.
     - 양식:
       ```markdown
       ### [YYYY-MM-DD HH:mm] 업데이트 이력 (Commit ID: <커밋 ID>)
       - **수정 내용**: <수정 사항 및 작업 내용 요약>
       - **검증 결과**: <검증 결과>
       ```
     - 커밋 전에는 커밋 ID를 알 수 없으므로, 커밋 후 실제 해시를 README 항목에 반영하고 `docs: sync exact commit ID <hash> in README.md` 형식의 후속 커밋으로 동기화합니다.
     - `README.md` 기존 본문 내용 수정도 가능하며, 변경 내역은 파일 맨 하단에 날짜 및 시간별로 계속 누적 기록합니다.

3. **상세 Git 커밋 메시지 작성** (한국어):
   ```text
   docs: update README.md and detailed commit results

   [User Request]
   - 사용자의 질의 및 요청 사항 요약

   [Action & Verification Results]
   - 수정한 파일 및 구현/수정 내역 상세
   - 구문 검사, 실행 검증, 빌드/타입체크 결과

   [Summary]
   - 최종 작업 결과 및 동기화 상태
   ```

4. **Git Staging, Commit & Push**:
   - `git add .` (단, `.gitignore` 대상 및 비밀 정보가 포함되지 않았는지 `git status`로 확인)
   - 상세 메시지로 `git commit`
   - `git push origin main` (또는 현재 작업 브랜치)

5. **결과 보고**:
   - 최종 커밋 해시, README 반영 사항, 푸시 결과를 사용자에게 종합 보고합니다.
