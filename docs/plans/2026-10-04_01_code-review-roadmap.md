# Implementation Plan — 코드 리뷰 개선 로드맵 (4단계)

> [!IMPORTANT]
> `/ask` 모드로 작성한 계획서입니다. **자동으로 실행하지 않습니다.**
> 단계별로 `/apply 1단계` → (확인) → `/apply 2단계` 순서로 요청해 주세요.
> 한 단계가 끝날 때마다 정적 검증 결과를 보고하고 커밋하지 않은 채 대기합니다. 커밋은 `/git-commit`을 입력했을 때만 합니다.

- 근거 문서: [2026-10-04_code-review-report.md](../reviews/2026-10-04_code-review-report.md) (항목 번호 `3-x`는 보고서 번호)
- 계획서 목록과 상태: [docs/README.md](../README.md)

## 진행 현황

| 단계 | 주제 | 상태 |
|---|---|---|
| 1단계 | 확정 버그 즉시 수정 (5건) | ✅ 완료 (2026-10-04, 커밋 `ab3a4ee7`) |
| 2단계 | 안정성: 서버 멈춤, 트랜잭션, DB 연결, FTS, TTS | ✅ 완료 (2026-10-04, 미커밋) |
| 3단계 | 구조 개선: 공통 함수, import 부작용, 시험 프로파일, 로깅, 라우터 분리 | ⬜ 대기 |
| 4단계 | 품질 기반: 테스트, 보안, 저장소 정리, 프론트 분리 | ⬜ 대기 |

### 모든 단계 공통 검증 (Rule 2)
```powershell
python -m py_compile <수정한 .py 파일들>
node --check <수정한 .js 파일들>
python -m pytest tests -q      # 기존 단위 테스트 (수 초 이내)
```
브라우저 검증은 하지 않습니다 (Rule 1). 단계마다 **사용자 수동 확인 항목**을 따로 적어 두었습니다.

---

## 1단계 — 확정 버그 즉시 수정

> 위험도 낮음, 변경 범위 작음. DB 스키마는 바꾸지 않습니다.

### 1-1. 검색 캐시 무효화 (보고서 3-1)
**[MODIFY] [app.py](file:///c:/Users/user/Desktop/web%20app/05-gichul_db/app.py)**
- `no_cache_static_js` 미들웨어([L98-L104](file:///c:/Users/user/Desktop/web%20app/05-gichul_db/app.py#L98-L104)) 아래에 쓰기 요청용 미들웨어를 추가합니다.
  ```python
  _WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}

  @app.middleware("http")
  async def invalidate_cache_on_write(request, call_next):
      response = await call_next(request)
      if (request.method in _WRITE_METHODS
              and request.url.path.startswith("/api/")
              and response.status_code < 400):
          search_cache.clear()
          db.invalidate_exams_cache()
      return response
  ```
- [background_auto_analyze_exam_grammar](file:///c:/Users/user/Desktop/web%20app/05-gichul_db/app.py#L1180-L1224)는 응답이 나간 뒤에 실행되므로 미들웨어가 잡지 못합니다. 그래서 함수 끝에서 `search_cache.clear()`를 직접 호출합니다.

### 1-2. 듣기 ZIP 다운로드 수정 (보고서 3-2)
**[MODIFY] [app.py:L503-L514](file:///c:/Users/user/Desktop/web%20app/05-gichul_db/app.py#L503-L514)**
- `create_listening_zip()`은 dict를 반환하므로, 그 안의 `zip_filename`으로 실제 경로를 만듭니다. `ValueError`는 404로 바꿉니다.
  ```python
  try:
      result = tts_service.create_listening_zip(clean_id)
  except ValueError as e:
      raise HTTPException(status_code=404, detail=str(e))
  zip_path = os.path.join(tts_service.AUDIO_DIR, result["zip_filename"])
  ```
- 프론트엔드([results-passage.js:L3094-L3099](file:///c:/Users/user/Desktop/web%20app/05-gichul_db/static/js/results-passage.js#L3094-L3099))는 `window.open` GET 방식을 그대로 씁니다. 수정할 필요가 없습니다.

### 1-3. 문장 조회를 SQL 조건으로 바꾸기 (보고서 3-4)
**[MODIFY] [database.py search_sentences](file:///c:/Users/user/Desktop/web%20app/05-gichul_db/database.py#L1778-L1934)**
- 파라미터 `exam_id: str = ""`와 `sentence_ids: Optional[List[str]] = None`을 추가합니다.
  - `exam_id`: 대괄호를 정규화한 뒤 `AND p.exam_id = ?`
  - `sentence_ids`: `AND s.id IN (?,?,...)` (빈 리스트면 즉시 `[]` 반환)

**[MODIFY] [app.py](file:///c:/Users/user/Desktop/web%20app/05-gichul_db/app.py)**
| 위치 | 현재 | 변경 |
|---|---|---|
| [L925-L931](file:///c:/Users/user/Desktop/web%20app/05-gichul_db/app.py#L925-L931) 단일 분석 폴백 | `limit=2000` 후 루프 | `db.search_sentences(sentence_ids=[clean_id])` |
| [L1107-L1110](file:///c:/Users/user/Desktop/web%20app/05-gichul_db/app.py#L1107-L1110) 배치 분석 | 전체 7만 문장 로드 후 필터 | `db.search_sentences(sentence_ids=req.sentence_ids)` |
| [L1187-L1189](file:///c:/Users/user/Desktop/web%20app/05-gichul_db/app.py#L1187-L1189) 업로드 후 자동 분석 | 최신 1,000문장 중 접두사 필터 | `db.search_sentences(exam_id=exam_id)` |

> [!TIP]
> 프론트엔드 일괄 분석([grammar.js:L799-L817](file:///c:/Users/user/Desktop/web%20app/05-gichul_db/static/js/grammar.js#L799-L817))은 **문장 1개마다** 배치 API를 호출합니다. 지금은 호출할 때마다 7만 문장과 태그·어법을 전부 읽고 있습니다. 이번 수정으로 일괄 분석 속도가 크게 빨라집니다.

### 1-4. FTS 오류 시 LIKE로 넘어가는 경로 살리기 (보고서 3-9)
**[MODIFY] [database.py](file:///c:/Users/user/Desktop/web%20app/05-gichul_db/database.py)** — `search_passages`, `search_sentences` 두 함수
- 내부 전용 파라미터 `_use_fts: bool = True`를 추가합니다. 키워드 조건 블록을 `if _use_fts:` (FTS) / `else:` (LIKE)로 나눕니다. 지금 쓸모없는 `try/except`는 제거합니다.
- `cursor.execute(query, params)`를 감싸서 처리합니다.
  ```python
  except sqlite3.OperationalError:
      if keyword and _use_fts:
          return search_passages(..., _use_fts=False)  # 동일 인자로 재호출
      raise
  ```

### 1-5. HWP 단독 업로드 실패를 정확히 알리기 (보고서 3-5 일부)
**[MODIFY] [app.py:L1934-L1940](file:///c:/Users/user/Desktop/web%20app/05-gichul_db/app.py#L1934-L1940)**
- 파싱 실패 시 `"status": "partial"`과 함께 "⚠ 파일은 저장했지만 해설 파싱에 실패했습니다: ..." 메시지를 반환합니다. HTTP는 200을 유지합니다 (파일 저장 자체는 성공했기 때문).

**[MODIFY] [upload.js:L1543-L1544](file:///c:/Users/user/Desktop/web%20app/05-gichul_db/static/js/upload.js#L1543-L1544)**
- `data.status === "partial"`이면 `🎉` 대신 `⚠️`로 알립니다.

### 1단계 검증
- `python -m py_compile app.py database.py` · `node --check static/js/upload.js` · `pytest tests -q`
- **사용자 수동 확인**
  1. 지문에 태그를 추가한 뒤 같은 검색어로 다시 검색했을 때 태그가 바로 보이는지
  2. 듣기 문항 화면의 "ZIP 다운로드": 생성된 MP3가 없으면 404 안내, 있으면 ZIP 저장
  3. 문장 일괄 어법 분석 속도가 빨라졌는지

### 1단계 적용 결과 (2026-10-04)
**계획과 다르게 적용한 점**
- 1-1: 캐시는 응답 상태 코드와 관계없이 비웁니다. 실패 응답이어도 일부 데이터가 이미 저장됐을 수 있기 때문입니다. `/api/settings/`(AI 키·TTS 미리듣기) 쓰기는 검색 결과와 무관하므로 제외했습니다. 백그라운드 분석은 `finally`에서 검색 캐시와 통계 캐시를 모두 비웁니다.
- 1-3: `sentence_ids`는 `IN (?,?,...)` 대신 `IN (SELECT value FROM json_each(?))`로 구현했습니다. 문장 수가 많아도 SQLite 변수 개수 제한에 걸리지 않습니다 (SQLite 3.45.1).
- 1-4: 재호출용 인자는 함수 첫 줄의 `locals()`로 보관합니다. 행을 읽는 도중에 나는 FTS 오류도 잡도록 `fetchall()`까지 `try`에 넣었습니다.
- 1-5: 예외뿐 아니라 **해설을 하나도 추출하지 못한 경우**에도 `partial`을 반환합니다. `upload.js`의 **일괄 갱신 경로**(등록된 시험지에 HWP 갱신)에서도 `partial`을 실패로 집계하고 사유를 남기도록 했습니다.

**검증**
- `python -m py_compile app.py database.py` 통과, `node --check static/js/upload.js` 통과, `pytest tests -q` 76개 통과
- 실제 DB 읽기 전용 확인
  - `search_sentences(exam_id=...)`: 235건 = 직접 집계한 값과 일치 (15ms)
  - `sentence_ids` 5개 조회: 2ms (기존 방식인 전체 문장 로드는 904ms)
  - 빈 리스트·없는 ID는 `[]` 반환
  - FTS 구문 오류를 일부러 일으키면 지문·문장 검색 모두 LIKE로 대체되어 결과를 반환
- `TestClient` API 확인 (DB를 바꾸지 않는 요청만 사용)
  - `/api/` 쓰기 요청 뒤 검색 캐시와 통계 캐시가 비워짐. `/api/settings/` 쓰기와 GET 요청 뒤에는 캐시 유지
  - 없는 시험지의 ZIP 다운로드: 404와 안내 메시지 (기존에는 dict를 파일 경로로 다뤄 500 오류)

---

## 2단계 — 안정성

> [!WARNING]
> **시작 전 DB 백업 필수**: 서버를 끈 상태에서 `Copy-Item gichul.db gichul.backup-<날짜>.db`
> FTS 트리거 교체(2-4)와 저장 방식 변경(2-2)이 포함되어 있습니다.

### 2-1. 오래 걸리는 작업 때문에 서버가 멈추는 문제 해결 (보고서 3-6)
**[MODIFY] [app.py](file:///c:/Users/user/Desktop/web%20app/05-gichul_db/app.py)**
- `await`를 쓰지 않는 모든 라우트(약 45개)를 `async def` → `def`로 바꿉니다. FastAPI가 자동으로 스레드풀에서 실행합니다.
  - **`async`를 유지할 것**: 미들웨어 2개, `generate-audio`, `generate-listening-audio`, `tts/preview`, `edge-tts/preview` (모두 `await tts_service...` 사용)
  - `UploadFile.file`은 동기 파일 객체라서 `def` 라우트에서도 `shutil.copyfileobj`가 그대로 동작합니다.
- PDF 처리 직렬화 락을 추가합니다. PyMuPDF는 멀티스레드 사용이 보장되지 않기 때문입니다.
  ```python
  INGEST_LOCK = threading.Lock()   # 업로드/크롭 재생성/듣기 동기화 직렬화
  ```
  적용 대상: `api_upload_exam`, `api_upload_exam_single_file`, `api_recapture_passage_pdf`, `api_update_answer`(크롭 재생성 부분), `api_sync_exam_listening`

**[MODIFY] [hwp_parser.py](file:///c:/Users/user/Desktop/web%20app/05-gichul_db/hwp_parser.py#L236-L352)** — ⚠ 필수
- 지금은 HWP COM이 항상 이벤트 루프 스레드 하나에서만 호출되고 있습니다. 라우트를 `def`로 바꾸면 매번 다른 스레드에서 호출되므로 COM 오류(`CoInitialize has not been called`)가 납니다.
- COM 호출만 담당하는 스레드 하나를 두고, 모든 COM 호출을 그쪽으로 보냅니다.
  ```python
  import pythoncom
  from concurrent.futures import ThreadPoolExecutor
  _COM_EXECUTOR = ThreadPoolExecutor(max_workers=1, thread_name_prefix="hwp-com",
                                     initializer=pythoncom.CoInitialize)
  ```
  - `extract_hwp_text_pyhwpx`, `convert_hwp_to_pdf`, `cleanup_shared_hwp`의 기존 본문을 `_..._impl` 함수로 옮깁니다. 공개 함수는 `_COM_EXECUTOR.submit(impl, ...).result()`를 돌려줍니다.
  - COM을 직접 쓰는 곳은 이 3개 함수뿐임을 grep으로 확인했습니다.

**[MODIFY] [tts_service.py:L411](file:///c:/Users/user/Desktop/web%20app/05-gichul_db/tts_service.py#L411)**
- `asyncio.get_event_loop()` → `asyncio.get_running_loop()`

### 2-2. 업로드 트랜잭션 + 재업로드 시 문장 교체 (보고서 3-5)
**[MODIFY] [database.py](file:///c:/Users/user/Desktop/web%20app/05-gichul_db/database.py)**
- 헬퍼를 추가합니다.
  ```python
  @contextmanager
  def transaction():
      conn = get_connection()
      try:
          yield conn
          conn.commit()
      except Exception:
          conn.rollback()
          raise
      finally:
          conn.close()
  ```
- `save_exam`, `save_passage`, `set_answer_status`, `save_exam_correct_rates`에 `conn=None` 파라미터를 추가합니다. `conn`이 주어지면 그 연결을 쓰고 commit하지 않습니다. 없으면 지금처럼 동작합니다.
- 새 함수 `replace_passage_sentences(passage_id, sentences, conn=None) -> dict`를 추가합니다.
  1. 해당 지문의 기존 `{id: sentence_text}`를 조회합니다.
  2. 새 문장들을 UPSERT합니다. 기존 id인데 **텍스트가 바뀌었으면** AI 어법(`source_type='AI'`)을 삭제하고 `grammar_analyzed=0`으로 되돌립니다. 사용자 어법(USER)은 유지합니다.
  3. 새 목록에 없는 기존 문장은 삭제합니다. FK CASCADE로 해당 태그와 어법도 함께 지워집니다.
  4. 반환값: `{"inserted", "updated", "text_changed", "removed"}` 개수

**[MODIFY] [app.py api_upload_exam](file:///c:/Users/user/Desktop/web%20app/05-gichul_db/app.py#L1228-L1506)**
- 순서를 다음과 같이 바꿉니다.
  1. 파일 저장
  2. **파싱 전체**: 정답 수집 → PDF → HWP → 교차검증. 이 단계에서는 DB에 쓰지 않습니다. 파서들이 DB를 읽지 않는다는 것도 확인했습니다.
  3. `with db.transaction() as conn:` 안에서 `save_exam` → 지문/문장(`replace_passage_sentences`) → `set_answer_status` → 정답률 저장
  4. 커밋한 뒤 듣기 동기화를 실행합니다. 이 단계는 별도 처리이며, 실패하면 응답에 `warnings`로 담습니다.
- 응답에 `sentences_removed` 등 교체 통계를 추가합니다.

### 2-3. DB 연결 닫기와 연결 비용 정리 (보고서 3-8)
**[MODIFY] [database.py get_connection](file:///c:/Users/user/Desktop/web%20app/05-gichul_db/database.py#L29-L40)**
- 기존 `with get_connection() as conn:` 사용처 53곳을 고치지 않아도 되도록, `with` 블록이 끝날 때 연결이 자동으로 닫히는 클래스를 씁니다.
  ```python
  class _ClosingConnection(sqlite3.Connection):
      def __exit__(self, exc_type, exc, tb):
          try:
              return super().__exit__(exc_type, exc, tb)  # commit/rollback
          finally:
              self.close()

  conn = sqlite3.connect(DB_PATH, timeout=15, factory=_ClosingConnection)
  ```
- `PRAGMA journal_mode = WAL`은 DB 파일에 영구 저장되는 설정입니다. 매 연결마다 하던 것을 `init_db()`에서 한 번만 하도록 옮깁니다.
- `timeout=15`: 스레드풀 전환 후 동시 쓰기가 생기면 `database is locked` 오류가 날 수 있어서 대기 시간을 늘립니다.
- **위험 점검**: `with` 블록이 끝난 뒤에 `conn`이나 커서를 쓰는 코드가 있는지 grep으로 확인합니다. `sqlite3.Row` 객체는 연결이 닫힌 뒤에도 쓸 수 있습니다.
- `with` 없이 연결을 여는 곳도 정리합니다: [listening_parser.py:L572](file:///c:/Users/user/Desktop/web%20app/05-gichul_db/listening_parser.py#L572)는 `try/finally: conn.close()`로 바꿉니다. (`tools/resync_answers.py`는 이미 close하고 있습니다.)

### 2-4. FTS 트리거가 필요한 컬럼에만 반응하게 하기 (보고서 3-7)
**[MODIFY] [database.py init_db](file:///c:/Users/user/Desktop/web%20app/05-gichul_db/database.py#L341-L376)**
- `DROP TRIGGER IF EXISTS trg_sentences_au` / `trg_passages_au`를 실행한 뒤 다음처럼 다시 만듭니다.
  - `AFTER UPDATE OF sentence_text ON sentences`
  - `AFTER UPDATE OF passage_text, question_title, explanation_text, script_text ON passages`
- 효과: 별표 토글, `grammar_analyzed`, 메모, 오디오 경로, 정답률 같은 컬럼을 바꿀 때 FTS 재색인을 하지 않습니다.
- 외부 콘텐츠 FTS5(`content='sentences'`)로 바꾸는 것은 데이터 재색인이 필요해서 **이번 범위에서 제외**합니다. 필요하면 4단계 이후에 따로 진행합니다.

### 2-5. XTTS 음성을 올바른 MP3로 저장 (보고서 3-3)

> **결정 (2026-10-04)**: 모든 음성 파일을 **MP3로 통일**합니다 (선택지 ②). 기본 엔진은 **XTTS를 유지**합니다. Edge-TTS로 바꾸지 않습니다.

**현재 문제**: XTTS는 대사마다 WAV(헤더 포함)를 만든 뒤 그 바이트를 그대로 이어 붙여 `.mp3` 이름으로 저장합니다. 내용은 WAV인데 확장자만 MP3이고, 첫 번째 WAV 헤더에 적힌 길이 때문에 **첫 대사만 재생될 수 있습니다**. 2026-10-04 확인 시 `static/audio` 33개 중 `고3-2025년-11월-01번.mp3` 1개가 이 상태였습니다.

**[MODIFY] [requirements.txt](file:///c:/Users/user/Desktop/web%20app/05-gichul_db/requirements.txt)**
- `lameenc>=1.8` 추가. LAME MP3 인코더를 담은 pip 패키지로, ffmpeg 같은 외부 프로그램이 필요 없습니다.
  - 확인: `lameenc-1.8.4-cp311-cp311-win_amd64.whl` (153 kB, 의존 패키지 없음)이 제공되어 현재 환경(Python 3.11, Windows 64비트)에 바로 설치됩니다 (`pip install --dry-run`으로 확인).
  - 기본 엔진이 XTTS이므로 `install.bat`의 XTTS 단계가 아니라 기본 `requirements.txt`에 넣습니다.

**[MODIFY] [tts_service.py](file:///c:/Users/user/Desktop/web%20app/05-gichul_db/tts_service.py)**
- 새 함수 `_wav_turns_to_mp3(wav_chunks: list[bytes], pause_sec=0.6) -> bytes`
  1. 표준 라이브러리 `wave`로 각 대사 WAV를 열어 PCM 데이터만 꺼냅니다. 샘플레이트·채널·16비트 여부는 첫 대사 기준이며, 다른 대사가 다르면 오류를 냅니다 (XTTS 출력은 24kHz 모노 16비트로 동일).
  2. 대사 사이에 0.6초 무음(0으로 채운 PCM)을 넣어 하나의 PCM으로 잇습니다. numpy/soundfile은 쓰지 않습니다.
  3. `lameenc.Encoder`(비트레이트 128kbps, 원본 샘플레이트·채널 그대로)로 MP3를 만들고 `flush()`까지 포함해 반환합니다.
  4. `lameenc`가 설치되지 않았으면 "pip install lameenc" 안내가 담긴 `RuntimeError`를 냅니다. 환경을 확인하는 `get_hardware_status()`에도 `lameenc` 설치 여부를 포함합니다.
- XTTS 경로([L404-L416](file:///c:/Users/user/Desktop/web%20app/05-gichul_db/tts_service.py#L404-L416)): 대사별 WAV 바이트를 리스트에 모은 뒤 `_wav_turns_to_mp3`로 변환합니다. 저장 파일명·`audio_file_path`는 지금처럼 `.mp3`입니다.
  - MP3 인코딩은 CPU 작업이므로 `run_in_executor`로 실행해 이벤트 루프를 막지 않게 합니다.
- Edge-TTS 경로는 MP3 프레임을 잇는 지금 방식을 유지합니다.
- **기본 엔진(`xtts`)은 바꾸지 않습니다** ([L124](file:///c:/Users/user/Desktop/web%20app/05-gichul_db/tts_service.py#L124), [L396](file:///c:/Users/user/Desktop/web%20app/05-gichul_db/tts_service.py#L396), [L482](file:///c:/Users/user/Desktop/web%20app/05-gichul_db/tts_service.py#L482), [state.js:L35](file:///c:/Users/user/Desktop/web%20app/05-gichul_db/static/js/state.js#L35), [ai-settings.js:L662](file:///c:/Users/user/Desktop/web%20app/05-gichul_db/static/js/ai-settings.js#L662) 유지).
- `create_listening_zip`은 모든 파일이 `.mp3`이므로 수정하지 않습니다.

**기존에 잘못 저장된 파일**
- 내용이 WAV인 `.mp3` 파일은 해당 문항의 음성을 다시 생성하면 정상 MP3로 바뀝니다. 자동 변환은 하지 않고, 적용 후 이런 파일 목록만 보고합니다 (파일 앞 4바이트가 `RIFF`인지 검사).

### 2단계 검증
- `py_compile`: app.py, database.py, hwp_parser.py, tts_service.py, listening_parser.py · `pytest tests -q`
- `_wav_turns_to_mp3` 단독 확인: 테스트용 WAV 2개(각 1초)를 만들어 변환 → 결과가 MP3 헤더(`ID3` 또는 `0xFF` 프레임)로 시작하고 길이가 약 2.6초(1+0.6+1)인지
- DB 트리거 확인 명령:
  ```powershell
  python -c "import sqlite3;c=sqlite3.connect('gichul.db');print([r[0] for r in c.execute(\"select sql from sqlite_master where type='trigger' and name like '%_au'\")])"
  ```
- **사용자 수동 확인**
  1. 문장 일괄 분석을 돌리는 중에 다른 탭에서 검색이 즉시 되는지 (서버 멈춤이 사라졌는지)
  2. HWP가 포함된 시험지를 업로드했을 때 정상 처리되는지 (COM 전용 스레드 동작 확인)
  3. 같은 시험지를 다시 업로드했을 때 응답의 `sentences_removed` 값과 문장 목록에 중복이 없는지
  4. **XTTS**로 대사가 여러 개인 듣기 1문항을 생성해 **끝까지** 재생되는지 (예: `고3-2025년-11월-01번` 재생성)
  5. Edge-TTS로도 1문항을 생성해 재생되는지, 듣기 ZIP에 두 파일이 모두 담기는지

### 2단계 적용 결과 (2026-10-04)
**계획과 다르게 적용한 점**
- 2-1
  - `async def` → `def` 변환은 44개입니다. `async`는 미들웨어 2개와 TTS 라우트 4개만 남았습니다.
  - `INGEST_LOCK`은 함수 본문에 직접 거는 대신 `@_ingest_serialized` 데코레이터(`functools.wraps`로 FastAPI 시그니처 유지)로 5개 라우트에 적용했습니다. `api_update_answer`는 크롭 재생성 부분만이 아니라 라우트 전체를 직렬화합니다.
  - COM 스레드 초기화는 `pythoncom.CoInitialize`를 `try/except`로 감싼 함수로 했습니다 (초기화 실패 시 실행기가 고장 나지 않도록). 이미 COM 스레드에서 불리면 바로 실행해 교착을 막습니다.
  - 종료 시 Quit은 `threading._register_atexit`에 등록했습니다. 실행기는 일반 `atexit`보다 먼저 작업 수신을 멈추기 때문입니다. `atexit` 등록도 안전망으로 남겨 두었습니다.
  - 함께 발견한 버그: `api_sync_exam_listening`이 결과 dict 전체를 `synced_count`로 돌려주던 것을 숫자만 돌려주도록 고쳤습니다.
- 2-2
  - 저장 함수는 `_use_conn(conn)` 헬퍼를 씁니다. `conn`을 주면 그대로 쓰고, 없으면 새 연결을 열어 끝날 때 commit 후 닫습니다. `transaction()`은 `_ClosingConnection`의 `with`를 그대로 쓰는 형태로 구현했습니다.
  - **같은 문장 판정 규칙 추가**: 저장된 문장은 어법 분석 전처리로 선지 기호 제거·빈칸 정답 채움·구두점 공백 정리가 되어 있을 수 있습니다. 단순 문자열 비교를 하면 재업로드할 때마다 AI 분석이 지워집니다. 그래서 소문자 단어 토큰으로 비교하고, 새 문장의 빈칸 자리는 임의의 단어와 일치하는 것으로 봅니다 (`_sentence_equivalent`). 같은 문장이면 저장된 텍스트·별표·어법을 그대로 두고 순서와 비고만 갱신합니다.
  - 텍스트가 바뀐 문장은 `grammar_analyzed`를 무조건 0으로 두지 않고, 남은(사용자) 어법이 있으면 1, 없으면 0으로 둡니다.
  - 새 문장 목록이 **비어 있으면 교체하지 않습니다** (파싱 실패로 문장이 통째로 지워지는 것을 막기 위함). 이 경우 응답 `warnings`에 문항 번호를 남깁니다.
  - 정답률 저장 실패는 트랜잭션 안에서 잡아 `warnings`에 담고, 독해 저장은 유지합니다 (기존 동작과 동일).
  - 응답에 `sentences_inserted`, `sentences_text_changed`, `sentences_removed`, `warnings`를 추가했습니다.
  - 함께 발견한 버그 2건
    - `listening_parser.sync_exam_listening`은 업로드처럼 HWP 경로를 직접 넘겨받으면 마지막 줄의 `hwp_files`가 정의되지 않아 **항상 NameError**를 냈습니다 (듣기 문항 저장은 된 뒤). `bool(target_hwp)`로 고쳤습니다.
    - `api_upload_exam`은 듣기 동기화 결과 dict를 그대로 `listening_count`에 넣어 메시지에 표시했습니다. `saved_count`를 꺼내도록 고쳤습니다.
- 2-3
  - `listening_parser.py`의 `with` 없는 연결은 `try/finally` 대신 `with` 블록으로 바꿨습니다. 시험지 정보와 기존 듣기 정답을 함수 앞부분에서 한 번에 읽고 바로 닫습니다.
  - `with` 블록 뒤에 `conn`/커서를 쓰는 코드는 AST 검사로 확인했습니다 (문제를 일부러 넣은 샘플로 검사기 동작도 확인). 적용 후 재검사에서 7건이 나왔지만, 모두 새로 추가한 `conn` 파라미터를 `_use_conn(conn)`에 넘기는 부분이라 검사기 오탐입니다. 실제 문제는 0건입니다.
- 2-4: 트리거는 매번 지우지 않고, 기존 정의에 `UPDATE OF`가 없을 때만 교체합니다. 교체할 때 `[Init DB] FTS 갱신 트리거 교체` 메시지를 출력합니다. **서버를 다음에 켤 때 실제 DB에서 한 번 교체됩니다.**
- 2-5
  - `lameenc 1.8.4`를 설치했습니다. XTTS 경로는 합성을 시작하기 전에 `lameenc` 설치 여부부터 확인합니다. 상태는 `get_hardware_status()["mp3_encoder_installed"]`에 표시합니다.
  - 품질 설정은 `set_quality(2)`(고품질)입니다. XTTS 출력(24kHz)은 MPEG-2 Layer III 프레임(`FF F3`)으로 인코딩됩니다.

**검증**
- `python -m py_compile app.py database.py hwp_parser.py tts_service.py listening_parser.py` 통과, `pytest tests -q` 76개 통과
- 실제 DB의 **임시 사본**으로 확인 (실제 DB는 바꾸지 않음)
  - `init_db`: `_au` 트리거 2개가 `UPDATE OF` 형태로 교체됨. `ai`/`ad` 트리거 4개 유지
  - `transaction()` 안에서 예외 발생 시 저장분 롤백. `conn` 없이 호출하면 자체 커밋
  - `replace_passage_sentences` (문장 34개·어법 28개인 지문)
    - 같은 목록 재저장: 34개 모두 `updated`, 어법 주석 그대로
    - 빈 목록: 아무것도 삭제하지 않음
    - 1개 변경·1개 제거·1개 추가: `{inserted 1, updated 32, text_changed 1, removed 1}`. 변경 문장은 AI 어법 삭제와 FTS 재색인, 제거 문장은 어법까지 CASCADE 삭제
  - 별표를 바꿔도 FTS 행이 다시 만들어지지 않음 (rowid 동일)
  - `_sentence_equivalent`: 선지 기호 차이, 빈칸↔정답 채움(문두·문중·문미)은 같은 문장으로, 단어가 다르면 다른 문장으로 판정
- `_wav_turns_to_mp3`: 1초 WAV 2개 → MP3 헤더 `FF F3`, 약 2.66초 (42,624바이트, 128kbps)
- COM 전용 스레드: 서로 다른 스레드 3개에서 호출해도 모두 `hwp-com_0` 한 스레드에서 실행
- `sync_exam_listening(없는 시험지)`: 연결을 닫고 `ValueError`
- 1단계 검증 스크립트 재실행: FTS→LIKE 대체, 캐시 무효화, ZIP 404 모두 유지
- 내용이 WAV인 `.mp3`: `고3-2025년-11월-01번.mp3` 1개 (해당 문항 음성을 다시 생성하면 정상 MP3로 바뀜)

---

## 3단계 — 구조 개선

> 동작은 그대로 두고 구조만 정리합니다. 단계 안에서도 **3-A → 3-E 순서로 하나씩** 적용하기를 권장합니다. 각 항목을 따로 `/apply 3-A`처럼 요청하셔도 됩니다.

### 3-A. 공통 함수 추출 (보고서 3-11 일부)
**[NEW] `text_utils.py`** (DB에 의존하지 않는 순수 함수만)
- `normalize_bracket_id(raw) -> str` — app.py에 20회 넘게 반복되는 `clean_id` 패턴을 대체합니다.
- `apply_answer_header(explanation, answer) -> str` — `[정답]` 헤더 갱신 코드 4곳을 대체합니다 ([app.py:L1404](file:///c:/Users/user/Desktop/web%20app/05-gichul_db/app.py#L1404-L1411), [L1696](file:///c:/Users/user/Desktop/web%20app/05-gichul_db/app.py#L1696-L1699), [L1756](file:///c:/Users/user/Desktop/web%20app/05-gichul_db/app.py#L1756-L1759), [database.py:L207](file:///c:/Users/user/Desktop/web%20app/05-gichul_db/database.py#L207-L215))
- `extract_answer_num`, `extract_choices`, `clean_choice_markers`를 [grammar_analyzer.py:L606-L680](file:///c:/Users/user/Desktop/web%20app/05-gichul_db/grammar_analyzer.py#L606-L680)에서 옮겨옵니다.
- `fill_blanks(sentence, passage_text, answer_text, explanation_text) -> str` — [prepare_sentence_for_analysis](file:///c:/Users/user/Desktop/web%20app/05-gichul_db/grammar_analyzer.py#L683-L765)에서 DB 조회 부분(L701-L722)을 뺀 순수 버전입니다.

**[MODIFY] grammar_analyzer.py**
- `prepare_sentence_for_analysis`는 "DB에서 지문 정보를 보강한 뒤 `fill_blanks` 호출"만 하도록 줄입니다. 옮긴 함수들은 기존 이름으로 다시 내보내서 하위 호환을 유지합니다.

**[NEW] `services/grammar_service.py`**
- `analyze_and_save_sentence(sentence_row, passage_cache) -> dict` — 단일/배치/백그라운드 3곳에 복제된 "전처리 → 분석 → 저장" 루프를 하나로 합칩니다.

### 3-B. import 부작용 제거 + 의존 방향 정리 (보고서 3-10)
- [database.py:L2063](file:///c:/Users/user/Desktop/web%20app/05-gichul_db/database.py#L2063)의 `init_db()` 자동 호출을 제거합니다. 대신 app.py의 FastAPI `lifespan`에서 호출합니다. `tools/*.py` 스크립트에는 `db.init_db()`를 명시적으로 넣습니다.
- [tts_service.py:L34-L51](file:///c:/Users/user/Desktop/web%20app/05-gichul_db/tts_service.py#L34-L51)의 torch/torchaudio 패치를 `_get_or_load_xtts_model()` 안으로 옮겨서 필요할 때만 실행합니다.
- [database.search_sentences:L1923-L1931](file:///c:/Users/user/Desktop/web%20app/05-gichul_db/database.py#L1923-L1931): 아직 빈칸이 남은 문장의 지문 정보를 **한 번에 조회**한 뒤 `text_utils.fill_blanks`를 호출합니다. 지금은 행마다 DB를 따로 조회하는 N+1 구조이고, `grammar_analyzer`를 import하는 역방향 의존도 함께 없어집니다.
- [validator.py:L102-L117](file:///c:/Users/user/Desktop/web%20app/05-gichul_db/validator.py#L102-L117): `text_utils.fill_blanks`를 직접 사용합니다. 지문 정보가 이미 다 있으므로 DB 조회가 필요 없습니다.

### 3-C. 시험 프로파일을 데이터로 관리 (보고서 3-12)
**[NEW] `exam_profiles.py`**
```python
@dataclass(frozen=True)
class ExamProfile:
    reading_start: int        # 18 / 23
    reading_end: int          # 45 / 50
    listening_end: int        # 17 / 22
    is_50_questions: bool     # 2006~2011
    is_ab_period: bool        # 2012-06 ~ 2013
    special_crop: str | None  # "crop_2013_09" 등

def get_exam_profile(grade, year, month, subtype=None) -> ExamProfile: ...
```
- 대체 대상 (텍스트 기반 감지 `detect_listening_range`는 유지하고, 프로파일은 **기본값**만 제공):
  - app.py: [L218-L221](file:///c:/Users/user/Desktop/web%20app/05-gichul_db/app.py#L218-L221), [L272-L277](file:///c:/Users/user/Desktop/web%20app/05-gichul_db/app.py#L271-L277), [L1303-L1308](file:///c:/Users/user/Desktop/web%20app/05-gichul_db/app.py#L1303-L1308), [L1660-L1661](file:///c:/Users/user/Desktop/web%20app/05-gichul_db/app.py#L1660-L1661)
  - pdf_parser.py: [L205-L213](file:///c:/Users/user/Desktop/web%20app/05-gichul_db/pdf_parser.py#L205-L213), [L239-L240](file:///c:/Users/user/Desktop/web%20app/05-gichul_db/pdf_parser.py#L239-L240), [L337-L341](file:///c:/Users/user/Desktop/web%20app/05-gichul_db/pdf_parser.py#L337-L341)
  - hwp_parser.py: [L556-L560](file:///c:/Users/user/Desktop/web%20app/05-gichul_db/hwp_parser.py#L556-L560)
  - listening_parser.py: 연도/문항 번호 분기 (적용할 때 grep으로 모든 위치를 확정)
- **회귀 방지**: 바꾸기 전에 `scratch/profile_snapshot.py`로 DB에 있는 모든 시험의 (grade, year, month, subtype)에 대해 기존 로직의 결과값을 JSON으로 저장합니다. 바꾼 뒤 새 프로파일 결과와 비교해서 **차이가 0건**이어야 합니다.

### 3-D. 로깅과 오류 처리 통일 (보고서 3-14)
**[NEW] `logging_config.py`**
- 콘솔 + `logs/app.log` (`RotatingFileHandler`, 5MB × 3개). `.gitignore`에 `logs/`를 추가합니다.
- app.py `lifespan`에서 설정을 적용합니다.

**[MODIFY]** app.py, database.py, grammar_analyzer.py, hwp_parser.py, pdf_parser.py, listening_parser.py, validator.py
- `print(...)` → `logger.info/warning/error` (총 54곳)
- 오류를 그냥 버리는 `except Exception: pass`(43곳) → `logger.debug("...", exc_info=True)`. 단, 마이그레이션의 `except sqlite3.OperationalError: pass`처럼 예상된 실패는 그대로 둡니다.
- `@app.exception_handler(Exception)` 공통 핸들러를 추가합니다. 스택 트레이스를 로그로 남기고 `{"success": False, "detail": ...}`를 반환합니다. 프론트엔드가 `data.detail`을 쓰므로 이 키는 유지합니다.

### 3-E. 라우터 분리 (보고서 3-11)
**[NEW] 패키지 구조**
```
core/state.py           # search_cache, INGEST_LOCK, 경로 상수
routers/search.py       # stats, search/passages, exams/{id}/passages, search/sentences, GET passages/{id}
routers/passages.py     # question-type, memo, answer, recapture, 지문/문장 태그, star
routers/listening.py    # generate-audio, generate-listening-audio, download-listening-zip, sync-listening
routers/grammar.py      # analyze-grammar, batch, categories/settings, annotations
routers/settings.py     # settings/ai, ai/test, openrouter, lmstudio, tts hardware/preview
routers/exams.py        # upload, exams 목록/삭제, raw-files, download-file/zip, upload-file, delete 계열
services/ingest.py      # _regenerate_exam_crops, 업로드 파이프라인 본문, 백그라운드 분석
```
- `app.py`에는 앱 생성, 미들웨어, static 마운트, lifespan, `include_router`만 남깁니다. 목표는 약 100줄입니다.
- ⚠ **라우트 등록 순서를 지금과 같게 유지**합니다. `{exam_id:path}`, `{passage_id:path}`처럼 경로 전체를 받는 파라미터가 있어서, 순서가 바뀌면 다른 라우트가 먼저 매칭될 수 있습니다.
- 검증: 분리 전후의 `app.routes` (메서드, 경로) 목록을 덤프해서 비교합니다. 차이가 0건이어야 합니다.

### 3단계 검증
- 새로 만들거나 수정한 모든 .py에 `py_compile` · `pytest tests -q`
- 라우트 목록 비교, 프로파일 스냅샷 비교 결과 보고
- **사용자 수동 확인**: 서버 기동 로그가 정상인지, 검색/업로드/어법 분석/TTS를 한 번씩 실행해 보기

---

## 4단계 — 품질 기반

### 4-A. 테스트 확충 (보고서 3-13)
- [database.py:L16](file:///c:/Users/user/Desktop/web%20app/05-gichul_db/database.py#L16): `DB_PATH = os.environ.get("GICHUL_DB_PATH") or <기본값>`
- **[MODIFY] tests/conftest.py**: `tmp_path` 임시 DB 픽스처(`init_db` 호출)와 `TestClient` 픽스처를 추가합니다. `httpx`는 0.28.1이 이미 설치되어 있지만 requirements에는 없어서 개발/테스트 섹션에 추가합니다.
- **[NEW] 테스트 파일**
  | 파일 | 검증 내용 |
  |---|---|
  | `tests/test_db_search.py` | `exam_id`/`sentence_ids` 필터, FTS 특수문자 → LIKE 대체 경로 |
  | `tests/test_db_sentences.py` | `replace_passage_sentences`: 삭제/텍스트 변경 시 AI 어법 초기화 |
  | `tests/test_api_smoke.py` | 태그 추가 후 재검색에 반영(캐시), ZIP 404, 배치 분석 키 없음 400 |
  | `tests/test_text_utils.py` | `fill_blanks`, `apply_answer_header`, `normalize_bracket_id` |
  | `tests/test_exam_profiles.py` | 2008/2012-06/2013/2013-09/2020 프로파일 기대값 |
- `scratch/`의 116개 스크립트 중 회귀 가치가 있는 것(`test_smart_resolver`, `test_dedup_algorithm` 등)은 검토해서 옮길지 정하고, 목록만 보고합니다.

### 4-B. 보안과 안전성 (보고서 3-15)
- 업로드 파일명: `safe_name = os.path.basename(f.filename)`에 허용 문자 화이트리스트를 적용합니다 ([app.py:L1249-L1279](file:///c:/Users/user/Desktop/web%20app/05-gichul_db/app.py#L1249-L1279), [L1665-L1667](file:///c:/Users/user/Desktop/web%20app/05-gichul_db/app.py#L1665-L1667)). `{grade}_{year}_{month}_` 접두사는 크롭 재생성 glob이 이 이름에 의존하므로 유지합니다.
- 시드 API 제거: [api_seed_sample_data](file:///c:/Users/user/Desktop/web%20app/05-gichul_db/app.py#L2041-L2179), `dom.js`의 `btnSeedSample`, [upload.js:L1599-L1620](file:///c:/Users/user/Desktop/web%20app/05-gichul_db/static/js/upload.js#L1599-L1620) 핸들러. HTML에는 해당 버튼이 없습니다.
- 토스트: [utils.js:L44](file:///c:/Users/user/Desktop/web%20app/05-gichul_db/static/js/utils.js#L44)에서 `innerHTML` → `span.textContent`로 바꿉니다. HTML을 넘기는 `showToast` 호출이 0건인 것을 확인했습니다.
- `DELETE /api/exams/{exam_id}`에도 `normalize_bracket_id`를 적용합니다.
- (선택) API 키를 Windows `keyring`에 저장. 의존성이 추가되고 기존 키를 옮겨야 해서, 적용할지는 그때 결정합니다.

### 4-C. 교차검증 수치 바로잡기 (보고서 3-16)
- [validator.py:L80](file:///c:/Users/user/Desktop/web%20app/05-gichul_db/validator.py#L80): 한쪽 본문이 없으면 `ratio=None`, `remarks="비교 불가 (HWP/PDF 중 한쪽 없음)"`으로 기록합니다.
- `ratio < 0.9`이면 `remarks`에 `⚠ 검토 필요`를 붙입니다.
- 프론트엔드 일치율 표시 부분이 `None`(null)을 받아도 깨지지 않도록 처리합니다 (적용할 때 grep으로 위치 확정).

### 4-D. 저장소와 작업 폴더 정리 (보고서 3-17, 3-18) — ⚠ 사용자 결정 필요
| 작업 | 위험 | 비고 |
|---|---|---|
| ~~0바이트 빈 파일 삭제: `database.db`, `database.sqlite3`, `exam_database.db`~~ | – | **루트 정리 A-1에서 처리**하므로 여기서는 건너뜁니다 |
| `requirements-xtts.txt` 분리 (torch, coqui-tts, soundfile) | 없음 | 문서화 목적 |
| `static/captures/`를 `.gitignore`에 추가 + `git rm -r --cached` | 중간 | 이후 GitHub에 크롭 이미지 백업이 없어집니다. 원본 PDF가 있는 `uploads/`도 Git에 없으므로 **별도 백업을 먼저** 해야 합니다 |
| `git filter-repo`로 히스토리에서 이미지 제거 | **높음** | 강제 푸시가 필요하고 되돌릴 수 없습니다. 실행 직전에 다시 확인을 받습니다 |
| `scratch/jsmod/node_modules` 삭제 | 낮음 | Git 추적 대상이 아니므로 로컬 디스크만 정리됩니다 |

> [!NOTE]
> **`dist/`는 삭제하지 않습니다.** 처음에는 정리 대상으로 넣었지만, [install.bat](file:///c:/Users/user/Desktop/web%20app/05-gichul_db/install.bat)의 `[4/4]` 단계가 `pip install --find-links=dist coqui-tts torchcodec`로 XTTS 오프라인 설치에 쓰고 있음을 확인했습니다. 폴더 이름을 용도에 맞게 바꾸고 싶다면 [루트 정리 C-3](2026-10-04_02_root-folder-cleanup.md#5-c단계--선택-항목-적용할-때-하나씩-결정) (`dist/` → `wheels/` + `install.bat` 수정)을 적용합니다.

### 4-E. 프론트엔드 분리 (보고서 3-19) — 여러 번에 나눠 진행
1. `style.css`를 기능별 파일로 나눕니다 (`base.css`, `search.css`, `viewer.css`, `grammar.css`, `upload.css`, `modal.css`). `index.html`에 `<link>` 여러 개로 연결합니다.
2. `index.html`의 인라인 `style=""` 367개를 화면 영역별로 클래스로 옮깁니다. 한 번에 한 영역(헤더 → 검색 → 뷰어 → 모달)씩 진행합니다.
3. `results-passage.js`(3,110줄)를 `passage-render.js`(화면 그리기), `passage-api.js`(fetch 호출), `passage-events.js`(이벤트 바인딩)로 나눕니다.
- 검증: `node --check` + 사용자가 직접 화면을 확인합니다. 화면 깨짐 위험이 있으므로 원하시면 `/scratchpad` 검증을 요청해 주세요.

### 4단계 검증
- `pytest tests -q` 전체 통과 (새 테스트 포함)
- `py_compile`, `node --check`
- 4-D는 실행 전후의 `git count-objects -vH` 수치를 보고합니다.

---

## 결정 필요 사항 요약

> [!CAUTION]
> - **4-D 저장소 이미지 정리**: 추적 해제만 할지, 히스토리까지 지울지(강제 푸시)
> - **4-B API 키 keyring 저장**: 적용할지 여부
> - ~~**2-5 XTTS 결과 형식**~~ → **결정됨 (2026-10-04)**: `lameenc`로 MP3 통일, 기본 엔진 XTTS 유지

위 사항은 해당 단계를 `/apply`할 때 다시 확인합니다. 그 외에는 계획서대로 진행합니다.
