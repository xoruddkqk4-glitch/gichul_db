# Implementation Plan — 루트(메인) 폴더 정리

> [!IMPORTANT]
> `/ask` 모드로 작성한 계획서입니다. **자동으로 실행하지 않습니다.**
> 진행 방법: `/apply A단계` → (확인) → `/apply B단계` … 순서로 요청해 주세요. 단계마다 정적 검증 후 커밋하지 않고 기다립니다.

- 계획서 목록과 상태: [docs/README.md](../README.md)
- 관련 계획서: [코드 리뷰 개선 로드맵](2026-10-04_01_code-review-roadmap.md) (B단계와 순서를 맞춰야 함 → [§4](#4-로드맵과의-실행-순서-권장))

## 진행 현황

| 단계 | 주제 | 위험도 | 상태 |
|---|---|---|---|
| A단계 | 안전 정리: 빈 파일 삭제, Git에 남은 생성물 추적 해제 | 낮음 | ⬜ 대기 |
| B단계 | 파이썬 모듈 13개를 `gichul/` 패키지로 이동 + 경로 상수 한곳으로 모으기 | 중간 | ⬜ 대기 |
| C단계 | (선택) 실행 중 생기는 데이터 폴더 분리, README 이력 분리, wheel 폴더 이름 변경 | 중간 | ⬜ 대기 |

---

## 1. 현재 루트 폴더 진단

### 1-1. 현재 구성 (2026-10-04 기준)

| 분류 | 항목 | Git 추적 | 판단 |
|---|---|---|---|
| **에이전트 규칙** | `AGENTS.md`, `GEMINI.md`, `CLAUDE.md` | ✅ | **루트 유지** (각 도구가 루트에서 찾음) |
| **문서** | `README.md` (1,808줄, 이 중 약 1,540줄이 변경 이력) | ✅ | 루트 유지, 이력 분리는 C단계 선택 |
| **실행 진입점** | `run.py`, `start.bat`, `install.bat` | ✅ | **루트 유지** (사용자가 더블클릭하는 파일) |
| **설정** | `requirements.txt`, `.gitignore`, `.gitattributes` | ✅ | 루트 유지 |
| **백엔드 모듈 (13개)** | `app.py`, `database.py`, `grammar_analyzer.py`, `hwp_parser.py`, `pdf_parser.py`, `listening_parser.py`, `tts_service.py`, `answer_keys.py`, `answer_resolver.py`, `validator.py`, `rate_parser.py`, `sentence_tokenizer.py`, `fels_engine.py` | ✅ | **B단계: `gichul/` 패키지로 이동** |
| **실데이터 DB** | `gichul.db` (186MB), `gichul.db-shm`, `gichul.db-wal` | ❌ (ignore) | 루트 유지 또는 C단계에서 이동 |
| **빈 파일** | `database.db`, `database.sqlite3`, `exam_database.db` (**모두 0바이트**, 코드에서 참조 0건) | ❌ | **A단계 삭제** |
| **로컬 전용 폴더** | `uploads/` (747MB), `dist/` (178MB, `install.bat`이 사용), `scratch/` (47MB) | ❌ (ignore) | 유지 (`dist/` 이름 변경은 C단계 선택) |
| **캐시** | `__pycache__/`, `.pytest_cache/` | ❌ | 그대로 (자동 생성, Git 제외) |

> [!NOTE]
> 코드 리뷰 보고서에서는 `dist/`를 "requirements에 없는 wheel 묶음"이라 정리 대상으로 봤습니다. 다시 확인해 보니 [install.bat](file:///c:/Users/user/Desktop/web%20app/05-gichul_db/install.bat)의 `[4/4]` 단계가 `pip install --find-links=dist coqui-tts torchcodec`로 **XTTS 오프라인 설치용으로 쓰고 있습니다**. 그래서 삭제 대상에서 뺐습니다.

### 1-2. 실제로 어수선한 지점
1. **백엔드 파이썬 파일 13개가 설정·문서·배치 파일과 루트에 섞여 있음** → 루트 파일 32개 중 절반 가까이를 차지합니다.
2. **경로 기준점이 9곳에 흩어져 있음** — 각 모듈이 `os.path.dirname(__file__)`로 각자 계산합니다. 그래서 파일을 옮기면 DB나 캡처 경로가 조용히 바뀔 위험이 있습니다.
   | 파일 | 위치 | 계산하는 경로 |
   |---|---|---|
   | app.py | [L50](file:///c:/Users/user/Desktop/web%20app/05-gichul_db/app.py#L50-L53) | BASE/static/templates/uploads |
   | database.py | [L16](file:///c:/Users/user/Desktop/web%20app/05-gichul_db/database.py#L16), [L428](file:///c:/Users/user/Desktop/web%20app/05-gichul_db/database.py#L428), [L643](file:///c:/Users/user/Desktop/web%20app/05-gichul_db/database.py#L643), [L752](file:///c:/Users/user/Desktop/web%20app/05-gichul_db/database.py#L752), [L1739](file:///c:/Users/user/Desktop/web%20app/05-gichul_db/database.py#L1739) | gichul.db, uploads, captures, grammar_categories.json |
   | answer_keys.py | [L13](file:///c:/Users/user/Desktop/web%20app/05-gichul_db/answer_keys.py#L13) | data/answer_keys |
   | grammar_analyzer.py | [L18](file:///c:/Users/user/Desktop/web%20app/05-gichul_db/grammar_analyzer.py#L18) | static/data/grammar_categories.json |
   | listening_parser.py | [L24](file:///c:/Users/user/Desktop/web%20app/05-gichul_db/listening_parser.py#L24) | BASE |
   | pdf_parser.py | [L16](file:///c:/Users/user/Desktop/web%20app/05-gichul_db/pdf_parser.py#L16) | static/captures |
   | tts_service.py | [L53](file:///c:/Users/user/Desktop/web%20app/05-gichul_db/tts_service.py#L53) | static/audio, static/voices |
3. **Git에 남아 있는 생성물**: `static/audio/*.mp3` 26개는 `.gitignore`에 규칙이 있는데도, 규칙을 추가하기 전에 커밋되어 계속 추적되고 있습니다.

---

## 2. A단계 — 안전 정리 (위험 낮음)

| # | 작업 | 명령/변경 | 비고 |
|---|---|---|---|
| A-1 | 빈 DB 파일 3개 삭제 | `Remove-Item database.db, database.sqlite3, exam_database.db` | 0바이트, 참조 0건 확인함 |
| A-2 | 생성된 음성 파일 추적 해제 | `git rm --cached static/audio/*.mp3` | **로컬 파일은 그대로 남음**. 이후 GitHub에는 MP3가 올라가지 않음 |
| A-3 | `.gitignore` 보강 | `.pytest_cache/`, `logs/`, `*.backup-*.db` 추가 | 로드맵 2·3단계에서 생길 파일 대비 |

- 검증: `git status --short`로 의도한 변경만 있는지 확인합니다.
- `static/captures/` 이미지 18,137개 추적 해제는 위험도가 높아서 **로드맵 4-D에서 별도로 결정**합니다 (이번 계획 범위 밖).

---

## 3. B단계 — `gichul/` 패키지로 이동

### 3-1. 목표 구조
```
05-gichul_db/
├── README.md · AGENTS.md · CLAUDE.md · GEMINI.md     # 루트 유지
├── requirements.txt · .gitignore · .gitattributes
├── run.py · start.bat · install.bat                  # 사용자 진입점 유지
├── gichul/                                           # ★ 백엔드 패키지 (신규)
│   ├── __init__.py
│   ├── paths.py            # ★ 모든 경로 상수를 여기서만 정의
│   ├── app.py
│   ├── database.py
│   ├── grammar_analyzer.py · tts_service.py · fels_engine.py
│   ├── pdf_parser.py · hwp_parser.py · listening_parser.py · rate_parser.py
│   ├── answer_keys.py · answer_resolver.py · validator.py · sentence_tokenizer.py
│   └── special_crops/crop_2013_09.py   # tools/에서 이동 (앱이 실행 중에 import하는 코드)
├── static/ · templates/ · data/                      # 위치 변경 없음
├── tests/ · tools/ · docs/
└── (로컬 전용·Git 제외) gichul.db* · uploads/ · dist/ · scratch/
```
- 하위 폴더를 처음부터 잘게 나누지 않고 **한 폴더(flat)** 로 옮깁니다. 로드맵 3단계에서 만들 `routers/`, `services/`, `core/` 등은 이 패키지 아래에 만들어집니다.

### 3-2. 작업 순서
1. **기준 스냅샷 (옮기기 전)**: `scratch/route_snapshot_before.json`에 `app.routes`의 (메서드, 경로) 목록을 저장하고, `scratch/paths_before.json`에 각 모듈이 계산한 경로 값을 저장합니다.
2. **`git mv`로 13개 모듈 이동** — 파일 히스토리가 유지됩니다.
3. **[NEW] `gichul/paths.py`**
   ```python
   ROOT_DIR = Path(__file__).resolve().parent.parent   # 프로젝트 루트
   DB_PATH = Path(os.environ.get("GICHUL_DB_PATH", ROOT_DIR / "gichul.db"))
   STATIC_DIR, TEMPLATES_DIR = ROOT_DIR / "static", ROOT_DIR / "templates"
   UPLOADS_DIR = ROOT_DIR / "uploads"
   CAPTURES_DIR, AUDIO_DIR, VOICES_DIR = STATIC_DIR / "captures", STATIC_DIR / "audio", STATIC_DIR / "voices"
   KEYS_DIR = ROOT_DIR / "data" / "answer_keys"
   GRAMMAR_CATEGORIES_JSON = STATIC_DIR / "data" / "grammar_categories.json"
   ```
   - §1-2 표의 경로 기준점 9곳을 모두 `paths`의 상수로 바꿉니다. 기존 문자열 경로를 쓰는 곳과 호환되도록 `str()`로 감싸거나 `os.fspath`를 씁니다.
   - `GICHUL_DB_PATH` 환경변수는 로드맵 4-A(테스트용 임시 DB)에서 쓸 것을 미리 넣어 두는 것입니다.
4. **내부 import를 패키지 상대 import로 변경** (총 26곳)
   | 파일 | 대상 |
   |---|---|
   | app.py | L36-L47 최상단 11개, L273 `tools.crop_2013_09` → `.special_crops.crop_2013_09`, L2044 `sentence_tokenizer` |
   | database.py | L174, L1926 (`grammar_analyzer`, 함수 안 지연 import) |
   | grammar_analyzer.py | L15 `database` |
   | hwp_parser.py | L416, L538, L916 (함수 안 지연 import) |
   | listening_parser.py | L18-L22 |
   | tts_service.py | L29 |
   | validator.py | L11, L103 |
   - 예: `import database as db` → `from . import database as db`, `from pdf_parser import X` → `from .pdf_parser import X`
5. **[MODIFY] [run.py](file:///c:/Users/user/Desktop/web%20app/05-gichul_db/run.py#L40-L56)**: `uvicorn.run("gichul.app:app", ...)`. `reload_dirs`를 `[base_dir/"gichul", base_dir/"templates"]`로 좁히면 감시 대상이 줄어들어 `reload_excludes` 목록도 단순해집니다.
6. **[MODIFY] tools/ 5개**: `sys.path.insert(0, ROOT)`는 유지하고 import만 바꿉니다 (`import pdf_parser` → `from gichul import pdf_parser`). [regenerate_group_crops.py:L16](file:///c:/Users/user/Desktop/web%20app/05-gichul_db/tools/regenerate_group_crops.py#L16)의 DB 경로 직접 계산은 `gichul.paths.DB_PATH`로 바꿉니다.
7. **[MODIFY] tests/**: `import answer_resolver as ar` → `from gichul import answer_resolver as ar` 등 4곳. `conftest.py`의 루트 sys.path 추가는 그대로 둡니다.
8. **[MODIFY] 문서**: `README.md`의 프로젝트 구조 설명, `docs/plans/2026-10-04_01_code-review-roadmap.md`의 파일 경로 표기(3단계 이후 항목)

### 3-3. B단계 검증
```powershell
python -m compileall -q gichul tools tests run.py
python -c "import gichul.app as m; print(len(m.app.routes))"   # import 성공 + 라우트 수
python -m pytest tests -q
```
- 스냅샷 비교: 라우트 목록 차이 0건, 경로 값 차이 0건 (특히 `DB_PATH`가 같은 `gichul.db`를 가리키는지)
- 루트 모듈 이름으로 된 import가 남았는지 확인하는 grep 결과 0건
- **사용자 수동 확인**: `start.bat`으로 실행 → 검색 / 지문 뷰어 이미지 / 듣기 오디오 재생 / 시험지 1개 크롭 재생성

> [!WARNING]
> `python -c "import gichul.app"`을 실행하면 현재 구조상 `init_db()`가 **실제 `gichul.db`에서 실행**됩니다. 이미 적용된 마이그레이션만 있으므로 데이터는 바뀌지 않습니다. 그래도 B단계 전에 DB 백업(`Copy-Item gichul.db gichul.backup-<날짜>.db`)을 권장합니다.

---

## 4. 로드맵과의 실행 순서 (권장)

B단계는 거의 모든 파이썬 파일의 경로와 import를 바꿉니다. 그래서 로드맵과 순서를 맞춰야 합니다.

```mermaid
flowchart LR
    A["정리 A단계"] --> R1["로드맵 1단계"] --> R2["로드맵 2단계"] --> B["정리 B단계 (패키지 이동)"] --> R3["로드맵 3단계"] --> R4["로드맵 4단계"]
```

| 선택지 | 장점 | 단점 |
|---|---|---|
| **① 권장: A → 로드맵 1·2 → B → 로드맵 3·4** | 1·2단계 계획서의 파일/줄 번호가 그대로 맞음. 3단계에서 새로 만드는 모듈(`text_utils`, `routers/` 등)이 처음부터 패키지 안에 생김 | 루트 정리가 끝나는 시점이 늦어짐 |
| ② A → B → 로드맵 1~4 | 루트가 즉시 깔끔해짐 | 로드맵 1·2단계의 파일 경로/줄 번호를 모두 다시 맞춰야 함 |
| ③ B를 로드맵 3단계에 합침 (3-0) | 구조 변경을 한 번에 끝냄 | 3단계 작업량이 커짐 |

---

## 5. C단계 — 선택 항목 (적용할 때 하나씩 결정)

| # | 작업 | 효과 | 주의 |
|---|---|---|---|
| C-1 | 실행 중 생기는 데이터를 `var/`로 이동: `gichul.db*`, `uploads/` → `var/gichul.db`, `var/uploads/` | 루트에서 대용량 로컬 데이터가 빠짐 | 서버를 끈 상태에서 `-wal`/`-shm`까지 함께 이동. B단계의 `paths.py` 한 곳만 수정. `.gitignore`·`run.py` 제외 규칙 갱신 |
| C-2 | `README.md`의 변경 이력(약 1,540줄)을 `docs/CHANGELOG.md`로 분리하고, README에는 링크만 남김 | README가 약 270줄로 줄어 읽기 쉬워짐 | **규칙 4(`/git-commit` 시 README 하단에 이력 누적)를 함께 바꿔야 함** — AGENTS/GEMINI/rules/CLAUDE + git-commit 스킬 2곳 |
| C-3 | `dist/` → `wheels/`로 이름 변경 + `install.bat` 수정 | 폴더 용도가 이름에서 드러남 | `.gitignore` 갱신. 안에 같은 패키지의 다른 버전 wheel이 섞여 있음 (huggingface_hub·tokenizers·transformers 각 2개) |

---

## 6. 결정 필요 사항

> [!CAUTION]
> 1. **실행 순서**: §4의 ① / ② / ③ 중 선택
> 2. **A-2**: 생성된 MP3를 Git 추적에서 빼도 되는지 (GitHub 백업이 사라짐)
> 3. **C단계** 각 항목 적용 여부. 특히 C-2는 커밋 규칙 변경을 동반함
