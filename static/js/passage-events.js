/**
 * 05-gichul_db: 지문 상세 뷰어 이벤트 바인딩 및 사용자 인터랙션 모듈 (passage-events.js)
 * - 오디오 재생/정지 전역 추적 (stopAllListeningAudio)
 * - TTS 음성 합성 작업(UI 잠금, 진행률 게이지 오버레이, 폴링, 단일/일괄 생성, 엔진 전환)
 * - FELS 학생용(빈칸)/교사용(정답) 클립보드 복사
 * - 문항 탭 스크롤 및 키보드 좌우 방향키 네비게이션
 * - 지문 메모(노트) 500ms 디바운스 자동 저장
 * - 정답 수동 수정 모달 폼
 * - PDF 문항 캡처 다시 실행
 * - 태그 추가/삭제 인터랙션
 * - MP3 및 ZIP 일괄 다운로드 트리거
 */

import { appState } from "./state.js";
import {
  btnAddPassageTag,
  btnCancelAnswer,
  btnCopyExplanation,
  btnCopyFels,
  btnCopyFelsAnswer,
  btnCopyFelsBlank,
  btnCopyPassage,
  btnCopyScript,
  btnDownloadListeningMp3,
  btnDownloadListeningZip,
  btnEditAnswer,
  btnGenerateAllListeningAudio,
  btnGenerateListeningAudio,
  btnRecapturePdf,
  btnSaveAnswer,
  btnSavePassageMemo,
  btnTabScrollLeft,
  btnTabScrollRight,
  btnToggleFelsAnswer,
  btnUploadRateFromViewer,
  inputPassageMemo,
  inputPassageTag,
  memoCharCount,
  memoStatusBadge,
  memoUpdatedAt,
  panelExplanation,
  panelPassageText,
  panelPdfImageContainer,
  passageTabBar,
  passageViewContainer,
  answerEditForm,
  answerEditQ,
  answerEditVal,
} from "./dom.js";
import { copyToClipboard, showToast } from "./utils.js";
import { loadStats } from "./search.js";
import { triggerSingleFileUpload } from "./upload.js";
import {
  savePassageMemoApi,
  updateAnswerApi,
  recapturePassagePdfApi,
  addPassageTagApi,
  deletePassageTagApi,
  downloadExamRawFile,
  downloadExamAllZip,
  downloadExamListeningZip,
  pollTtsProgressApi,
  generateSingleAudioApi,
  generateAllAudioApi,
  switchTtsEngineApi,
  examFullPassagesCache,
  TTS_POLL_MS,
  activeTtsJob,
  setActiveTtsJob,
} from "./passage-api.js";
import {
  currentDetailPassage,
  getCurrentDetailPassage,
  getCurrentActivePassage,
  setCurrentDetailPassage,
  currentFelsViewMode,
  formatFelsText,
  isDialogueScript,
  renderFelsBottomLeftPanel,
  applyPassageUpdate,
  renderPassageView,
  groupPassageItems,
  renderPassageTags,
  selectPassageTab,
  isRecapturingPdf,
  setIsRecapturingPdf,
  currentLoadedExamRawFilesId,
  renderBreadcrumbExamFiles,
} from "./passage-render.js";
import { openPassageReportModal } from "./reports.js";

// 메모 저장 상태 관리
export let memoSaveTimer = null;
export let isMemoDirty = false;

export function getIsMemoDirty() {
  return isMemoDirty;
}

export function setIsMemoDirty(val) {
  isMemoDirty = val;
}

export function clearMemoSaveTimer() {
  if (memoSaveTimer) {
    clearTimeout(memoSaveTimer);
    memoSaveTimer = null;
  }
}

/** 지문 메모 저장 API 호출 */
export async function savePassageMemo(silent = false) {
  const currentP = getCurrentDetailPassage();
  if (!currentP || !inputPassageMemo) return;
  const pid = currentP.id;
  const text = inputPassageMemo.value;

  if (memoStatusBadge) {
    memoStatusBadge.textContent = "저장 중...";
    memoStatusBadge.className = "memo-status-badge badge-saving";
  }

  try {
    const data = await savePassageMemoApi(pid, text);
    currentP.user_memo = text;
    currentP.user_memo_updated_at = data.updated_at;
    if (currentP.exam_id && examFullPassagesCache.has(currentP.exam_id)) {
      const cached = examFullPassagesCache.get(currentP.exam_id).get(currentP.id);
      if (cached) {
        cached.user_memo = text;
        cached.user_memo_updated_at = data.updated_at;
      }
    }
    isMemoDirty = false;

    if (memoStatusBadge) {
      memoStatusBadge.textContent = "저장됨";
      memoStatusBadge.className = "memo-status-badge badge-saved";
    }
    if (memoUpdatedAt && data.updated_at) {
      memoUpdatedAt.textContent = `최근 수정: ${data.updated_at}`;
    }
    if (!silent) {
      showToast("지문 메모가 안전하게 저장되었습니다.", "success");
    }
  } catch (err) {
    console.error("지문 메모 저장 실패:", err);
    if (memoStatusBadge) {
      memoStatusBadge.textContent = "저장 실패";
      memoStatusBadge.className = "memo-status-badge badge-dirty";
    }
    if (!silent) {
      showToast("메모 저장 중 오류가 발생했습니다.", "error");
    }
  }
}

/** 500ms 디바운스 자동 저장 핸들러 */
export function handleMemoInput() {
  if (!inputPassageMemo) return;
  isMemoDirty = true;
  const len = inputPassageMemo.value.length;
  if (memoCharCount) {
    memoCharCount.textContent = `${len}자`;
  }
  if (memoStatusBadge) {
    memoStatusBadge.textContent = "수정됨...";
    memoStatusBadge.className = "memo-status-badge badge-dirty";
  }
  if (memoSaveTimer) {
    clearTimeout(memoSaveTimer);
  }
  memoSaveTimer = setTimeout(() => {
    savePassageMemo(true);
  }, 500);
}

// ---------------------------------------------------------------------------
// 오디오 재생 제어 및 정지
// ---------------------------------------------------------------------------
let activeListeningAudio = null;
if (typeof document !== "undefined") {
  document.addEventListener(
    "play",
    (e) => {
      if (e.target && (e.target.tagName === "AUDIO" || e.target instanceof HTMLMediaElement)) {
        activeListeningAudio = e.target;
      }
    },
    true
  );
}

/** 듣기 영역 오디오 재생 즉시 완전 정지 */
export function stopAllListeningAudio() {
  try {
    if (activeListeningAudio) {
      try {
        if (!activeListeningAudio.paused) {
          activeListeningAudio.pause();
        }
        activeListeningAudio.currentTime = 0;
      } catch (e) {}
      activeListeningAudio = null;
    }

    const audios = document.querySelectorAll("audio");
    audios.forEach((audio) => {
      try {
        if (!audio.paused) {
          audio.pause();
        }
        audio.currentTime = 0;
      } catch (e) {}
    });

    const player = document.getElementById("listeningAudioPlayer");
    if (player) {
      try {
        if (!player.paused) {
          player.pause();
        }
        player.currentTime = 0;
      } catch (e) {}
    }
  } catch (err) {
    console.error("오디오 정지 오류:", err);
  }
}

// 전역 윈도우 객체 노출
if (typeof window !== "undefined") {
  window.stopAllListeningAudio = stopAllListeningAudio;
  window.addEventListener("beforeunload", stopAllListeningAudio);
  window.addEventListener("pagehide", stopAllListeningAudio);
}

// ---------------------------------------------------------------------------
// FELS 클립보드 복사 액션
// ---------------------------------------------------------------------------

/** FELS 학생용 빈칸 텍스트([ ]) 복사 */
export function copyFelsBlankVersion() {
  const p = getCurrentDetailPassage();
  const felsText = p ? p.fels_text || "" : "";
  if (!felsText) {
    showToast("복사할 FELS 텍스트가 없습니다.", "warning");
    return;
  }
  const title = p.question_title || "";
  const qType = p.question_type || "";
  const isDialogue = isDialogueScript(felsText, title, qType);
  const blankText = formatFelsText(felsText, "blank", title, qType);

  const matches = Array.from(felsText.matchAll(/<([^>]+?)>|\[([^\]]+?)\]/g));
  const maxLen = Math.max(...matches.map((m) => (m[1] || m[2] || "").trim().length), 5);

  copyToClipboard(
    blankText,
    `FELS 학생용 빈칸([ ]) 텍스트가 클립보드에 복사되었습니다! (최장 ${maxLen}자 기준 공백${
      isDialogue ? " · M1/W1 대화 순번 부여" : " · 담화문 문장 번호 부여"
    } 적용)`
  );
}

/** FELS 교사용 정답 텍스트([단어]) 복사 */
export function copyFelsAnswerVersion() {
  const p = getCurrentDetailPassage();
  const felsText = p ? p.fels_text || "" : "";
  if (!felsText) {
    showToast("복사할 FELS 텍스트가 없습니다.", "warning");
    return;
  }
  const title = p.question_title || "";
  const qType = p.question_type || "";
  const isDialogue = isDialogueScript(felsText, title, qType);
  const answerText = formatFelsText(felsText, "answer", title, qType);

  copyToClipboard(
    answerText,
    `FELS 교사용 정답 텍스트([단어])가 클립보드에 복사되었습니다! (정답지·해설용${
      isDialogue ? " · M1/W1 1:1 대화 순번" : " · 1:1 문장 번호 정렬"
    })`
  );
}

// ---------------------------------------------------------------------------
// 음성 합성(TTS) 작업 상태 제어 & UI 동기화
// ---------------------------------------------------------------------------

export function setTtsBtnLabel(btn, text) {
  if (!btn) return;
  const label = btn.querySelector(".tts-btn-label");
  if (label) label.textContent = text;
  else btn.textContent = text;
}

export function passageMatchesTtsJob(p) {
  const job = activeTtsJob;
  if (!job || !p) return false;
  if (job.kind === "batch") return !!job.examId && p.exam_id === job.examId;
  const ids = [p.id, ...((p.subItems || []).map((si) => si.id))];
  return ids.some((id) => job.targetIds.has(id));
}

export function estimateTtsPercent(info) {
  if (!info || !info.found || !info.total) return 0;
  if (info.status === "done") return 100;
  const done = info.done || 0;
  let frac;
  if (done > 0) {
    const avg = (info.steps_elapsed_sec || 0) / done;
    frac = avg > 0 ? Math.min(0.9, (info.since_step_sec || 0) / avg) : 0;
  } else {
    frac = Math.min(0.9, (info.since_step_sec || 0) / 20);
  }
  return Math.min(99, ((done + frac) / info.total) * 100);
}

/** 버튼·오디오 바·상태 칩을 현재 합성 작업 상태에 맞춘다 */
export function applyTtsUiState() {
  const job = activeTtsJob;
  const pct = job ? Math.floor(job.percent) : 0;
  const pctText = `${pct}%`;

  const genButtons = [
    [document.getElementById("btnGenerateListeningAudio"), "single", "음성 생성"],
    [document.getElementById("btnGenerateAllListeningAudio"), "batch", "전체 생성"],
  ];
  genButtons.forEach(([btn, kind, idleLabel]) => {
    if (!btn) return;
    const busy = !!job && job.kind === kind;
    btn.disabled = !!job;
    btn.classList.toggle("is-busy", busy);
    btn.style.setProperty("--tts-progress", busy ? pctText : "0%");
    btn.setAttribute("aria-busy", busy ? "true" : "false");
    setTtsBtnLabel(btn, busy ? `합성 중 ${pctText}` : idleLabel);
  });

  const p = getCurrentActivePassage();
  const locked = passageMatchesTtsJob(p);
  const btnMp3 = document.getElementById("btnDownloadListeningMp3");
  const btnZip = document.getElementById("btnDownloadListeningZip");
  if (btnMp3) btnMp3.disabled = locked;
  if (btnZip) btnZip.disabled = !!job && !!p && p.exam_id === job.examId;

  const bar = document.querySelector(".listening-audio-bar");
  const player = document.getElementById("listeningAudioPlayer");
  const chip = document.getElementById("audioStatusChip");

  if (bar) {
    bar.classList.toggle("is-locked", locked);
    bar.style.setProperty("--tts-progress", pctText);
    let overlay = bar.querySelector(".tts-lock-overlay");
    if (locked && !overlay) {
      overlay = document.createElement("div");
      overlay.className = "tts-lock-overlay";
      overlay.setAttribute("role", "status");
      overlay.innerHTML = `
        <div class="tts-lock-text"><span class="tts-lock-msg"></span><span class="tts-lock-percent"></span></div>
        <div class="tts-lock-track"><div class="tts-lock-fill"></div></div>`;
      bar.appendChild(overlay);
    }
    if (overlay && locked) {
      const info = job.info;
      const stepText = info && info.total ? ` · ${Math.min(info.done, info.total)}/${info.total}단계` : "";
      overlay.querySelector(".tts-lock-msg").textContent =
        (job.kind === "batch" ? "⏳ 전체 일괄 합성 중" : "⏳ 음성 합성 중") + stepText + " — 완료 후 재생할 수 있습니다";
      overlay.querySelector(".tts-lock-percent").textContent = pctText;
    }
  }

  if (player) {
    if (locked) {
      if (!player.paused) player.pause();
      player.setAttribute("aria-disabled", "true");
      player.tabIndex = -1;
    } else {
      player.removeAttribute("aria-disabled");
      player.removeAttribute("tabindex");
    }
  }

  if (chip) {
    if (locked) {
      chip.className = "audio-status-chip busy";
      chip.textContent = `⏳ 합성 중 ${pctText}`;
    } else if (chip.classList.contains("busy")) {
      const hasAudio = !!(p && p.audio_file_path);
      chip.className = `audio-status-chip ${hasAudio ? "ready" : "empty"}`;
      chip.textContent = hasAudio ? "🎙️ 음성 준비됨" : "🎙️ 음성 미생성";
    }
  }
}

export async function pollTtsProgress(jobId) {
  const job = activeTtsJob;
  if (!job || job.jobId !== jobId || job.polling) return;
  job.polling = true;
  try {
    const data = await pollTtsProgressApi(jobId);
    if (data && data.found) job.info = data;
  } catch (e) {
  } finally {
    job.polling = false;
  }
  if (activeTtsJob !== job) return;
  job.percent = Math.max(job.percent, estimateTtsPercent(job.info));
  applyTtsUiState();
}

export function startTtsJob(kind, { examId = "", targetIds = [] } = {}) {
  const jobId = `tts-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;
  const jobObj = {
    jobId,
    kind,
    examId,
    targetIds: new Set(targetIds.filter(Boolean)),
    percent: 0,
    info: null,
    timer: null,
    polling: false,
  };
  setActiveTtsJob(jobObj);
  stopAllListeningAudio();
  applyTtsUiState();
  jobObj.timer = setInterval(() => pollTtsProgress(jobId), TTS_POLL_MS);
  return jobId;
}

export function finishTtsJob(jobId) {
  if (!activeTtsJob || activeTtsJob.jobId !== jobId) return;
  clearInterval(activeTtsJob.timer);
  setActiveTtsJob(null);
  applyTtsUiState();
}

if (typeof document !== "undefined") {
  document.addEventListener(
    "play",
    (e) => {
      const el = e.target;
      if (el && el.id === "listeningAudioPlayer" && el.closest(".listening-audio-bar.is-locked")) {
        el.pause();
        showToast("음성 합성이 끝난 뒤에 재생할 수 있습니다.", "info");
      }
    },
    true
  );
}

// ---------------------------------------------------------------------------
// 사용자 액션 핸들러
// ---------------------------------------------------------------------------

/** PDF 문항 캡처 다시 실행 */
export async function handleRecapturePdf() {
  if (isRecapturingPdf) return;
  const p = getCurrentActivePassage();
  if (!p) {
    showToast("선택된 문항이 없습니다. 문항을 먼저 선택해 주세요.", "warning");
    return;
  }
  const targetId = p.id;
  setIsRecapturingPdf(true);
  if (btnRecapturePdf) {
    btnRecapturePdf.disabled = true;
    btnRecapturePdf.textContent = "⏳ 캡처 중...";
  }
  document.querySelectorAll(".btn-inline-recapture").forEach((btn) => {
    btn.disabled = true;
    btn.textContent = "⏳ 캡처 진행 중...";
  });
  showToast(`${p.display_id || p.id} PDF 문항 캡처를 다시 생성하는 중입니다...`, "info");
  try {
    const data = await recapturePassagePdfApi(targetId);
    if (Array.isArray(data.passages) && data.passages.length > 0) {
      const updatedMap = new Map(data.passages.map((it) => [it.id, it]));
      const flatten = (items) => items.flatMap((it) => (it.isGroup && it.subItems ? it.subItems : [it]));
      const replaceIn = (items) =>
        flatten(items).map((it) => (updatedMap.has(it.id) ? { ...it, ...updatedMap.get(it.id) } : it));
      if (appState.passagesData && appState.passagesData.length) {
        appState.passagesData = groupPassageItems(replaceIn(appState.passagesData));
      }
      if (appState.rawPassagesData && appState.rawPassagesData.length) {
        appState.rawPassagesData = groupPassageItems(replaceIn(appState.rawPassagesData));
      }
      renderPassageView(appState.passagesData, p.id);
    } else if (data.passage) {
      applyPassageUpdate(data.passage, p.id);
    }
    showToast(data.message || "PDF 캡처가 성공적으로 재생성되었습니다.", "success");
  } catch (err) {
    console.error(err);
    showToast(err.message || "PDF 캡처 재생성 중 오류가 발생했습니다.", "error");
  } finally {
    setIsRecapturingPdf(false);
    if (btnRecapturePdf) {
      btnRecapturePdf.disabled = false;
      btnRecapturePdf.textContent = "🔄 다시 캡처";
    }
    document.querySelectorAll(".btn-inline-recapture").forEach((btn) => {
      btn.disabled = false;
      btn.textContent = "🔄 지금 다시 캡처 실행";
    });
  }
}

/** 지문 태그 추가 */
export async function addPassageTagAction() {
  if (!inputPassageTag) return;
  const tagName = inputPassageTag.value.trim();
  if (!tagName || !appState.currentPassageId) return;

  try {
    const data = await addPassageTagApi(appState.currentPassageId, tagName);
    renderPassageTags(data.tags);
    inputPassageTag.value = "";
    showToast(`태그 '#${tagName}'이 추가되었습니다.`, "success");
    loadStats();
  } catch (e) {
    console.error(e);
    showToast("태그 추가 실패", "error");
  }
}

/** 지문 태그 삭제 */
export async function deletePassageTagAction(passageId, tagName) {
  try {
    const data = await deletePassageTagApi(passageId, tagName);
    renderPassageTags(data.tags);
    showToast(`태그 '#${tagName}'이 삭제되었습니다.`, "info");
    loadStats();
  } catch (e) {
    console.error(e);
    showToast("태그 삭제 실패", "error");
  }
}

/** 단일 문항 듣기 음성 생성 */
export async function handleGenerateListeningAudioAction(btnEl) {
  const targetBtn = btnEl || btnGenerateListeningAudio || document.getElementById("btnGenerateListeningAudio");
  if (activeTtsJob) {
    showToast("이미 음성 합성이 진행 중입니다. 끝난 뒤 다시 시도해 주세요.", "warning");
    return;
  }
  if (targetBtn && targetBtn.disabled) return;

  const p = getCurrentActivePassage();
  if (!p || !p.id) {
    showToast("선택된 듣기 문항이 없습니다. 상단 탭에서 문항을 먼저 선택해 주세요.", "warning");
    return;
  }

  const targetId = p.isGroup && p.subItems && p.subItems.length > 0 ? p.subItems[0].id : p.id;
  const jobId = startTtsJob("single", {
    examId: p.exam_id,
    targetIds: [p.id, targetId, ...((p.subItems || []).map((si) => si.id))],
  });
  const displayLabel = p.display_id || p.id;
  showToast(`🎙️ ${displayLabel} 문항의 영어 듣기 음성을 생성하고 있습니다...`, "info");

  try {
    const resData = await generateSingleAudioApi(targetId, jobId);
    p.audio_file_path = resData.audio_url;
    if (p.isGroup && p.subItems) {
      p.subItems.forEach((si) => {
        si.audio_file_path = resData.audio_url;
      });
    }
    setCurrentDetailPassage(p);
    appState.currentPassage = p;
    showToast(`🎙️ ${displayLabel} 문항 듣기 음성이 성공적으로 생성되었습니다!`, "success");
    const player = document.getElementById("listeningAudioPlayer");
    const chip = document.getElementById("audioStatusChip");
    if (player) {
      player.src = `${resData.audio_url}?t=${Date.now()}`;
      player.load();
    }
    if (chip) {
      chip.className = "audio-status-chip ready";
      chip.textContent = "🎙️ 음성 준비됨";
    }
  } catch (e) {
    console.error("음성 생성 오류:", e);
    showToast(`음성 생성 통신 오류: ${e.message}`, "error");
  } finally {
    finishTtsJob(jobId);
  }
}

/** 전체 듣기 문항 일괄 생성 */
export async function handleGenerateAllListeningAudioAction(btnEl) {
  const targetBtn = btnEl || btnGenerateAllListeningAudio || document.getElementById("btnGenerateAllListeningAudio");
  if (activeTtsJob) {
    showToast("이미 음성 합성이 진행 중입니다. 끝난 뒤 다시 시도해 주세요.", "warning");
    return;
  }
  if (targetBtn && targetBtn.disabled) return;

  const p = getCurrentActivePassage();
  const examId = (p && p.exam_id) || (appState.currentExamQuestions && appState.currentExamQuestions[0]?.exam_id);

  if (!examId) {
    showToast("선택된 시험지 정보가 없습니다.", "warning");
    return;
  }

  if (
    !confirm(
      `[${examId}] 전체 듣기 문항의 음성을 일괄 생성하시겠습니까?\n\n(선택된 TTS 엔진으로 1~17번 음성을 자동 합성합니다)`
    )
  ) {
    return;
  }

  const jobId = startTtsJob("batch", { examId });
  showToast(`🎙️ [${examId}] 전체 듣기 문항 일괄 생성을 시작합니다...`, "info");

  try {
    const resData = await generateAllAudioApi(examId, jobId);
    const failCnt = resData.fail_count || 0;
    showToast(
      `🎙️ 전체 듣기 문항 일괄 생성이 완료되었습니다! (성공: ${resData.generated_count || resData.success_count || 0}개${
        failCnt ? `, 실패: ${failCnt}개` : ""
      })`,
      failCnt ? "warning" : "success"
    );
    const curP = getCurrentActivePassage();
    if (curP && curP.id) {
      const freshRes = await fetch(`/api/passages/${encodeURIComponent(curP.id)}`);
      if (freshRes.ok) {
        const freshData = await freshRes.json();
        curP.audio_file_path = freshData.audio_file_path;
        if (curP.isGroup && curP.subItems) {
          curP.subItems.forEach((si) => {
            si.audio_file_path = freshData.audio_file_path;
          });
        }
        const player = document.getElementById("listeningAudioPlayer");
        const chip = document.getElementById("audioStatusChip");
        if (player && curP.audio_file_path) {
          player.src = `${curP.audio_file_path}?t=${Date.now()}`;
          player.load();
        }
        if (chip && curP.audio_file_path) {
          chip.className = "audio-status-chip ready";
          chip.textContent = "🎙️ 음성 준비됨";
        }
      }
    }
  } catch (e) {
    console.error("일괄 음성 생성 오류:", e);
    showToast(`일괄 생성 통신 오류: ${e.message}`, "error");
  } finally {
    finishTtsJob(jobId);
  }
}

/** 인라인 TTS 엔진 전환 스위처 상태 업데이트 */
export function updateTtsEngineSwitcherState(engine) {
  const curEngine = engine || appState.ttsEngine || "xtts";
  const btnXtts = document.getElementById("btnTtsEngineXtts");
  const btnEdge = document.getElementById("btnTtsEngineEdge");
  if (btnXtts) btnXtts.classList.toggle("active", curEngine === "xtts");
  if (btnEdge) btnEdge.classList.toggle("active", curEngine === "edge-tts");
}
if (typeof window !== "undefined") {
  window.updateTtsEngineSwitcherState = updateTtsEngineSwitcherState;
}

/** 인라인 TTS 엔진 즉시 전환 및 서버 저장 */
export async function handleSwitchTtsEngine(targetEngine) {
  if (!targetEngine) return;
  if (appState.ttsEngine === targetEngine) return;
  const prevEngine = appState.ttsEngine;
  appState.ttsEngine = targetEngine;
  updateTtsEngineSwitcherState(targetEngine);

  const engineName = targetEngine === "xtts" ? "수능 성우 복제 (XTTS)" : "Edge-TTS (무료)";
  showToast(`🎙️ 음성 엔진을 '${engineName}'(으)로 변경했습니다.`, "info");

  try {
    await switchTtsEngineApi(targetEngine);
    const radioXtts = document.getElementById("radioTtsXtts");
    const radioEdge = document.getElementById("radioTtsEdge");
    if (radioXtts && radioEdge) {
      radioXtts.checked = targetEngine === "xtts";
      radioEdge.checked = targetEngine === "edge-tts";
      if (typeof window.toggleTtsEngineCards === "function") {
        window.toggleTtsEngineCards();
      }
    }
  } catch (err) {
    console.error("TTS 엔진 변경 실패:", err);
    appState.ttsEngine = prevEngine;
    updateTtsEngineSwitcherState(prevEngine);
    showToast("TTS 엔진 설정 저장에 실패했습니다.", "error");
  }
}

/** 단일 문항 MP3 다운로드 실행 함수 */
export function executeDownloadPassageMp3() {
  const p = getCurrentActivePassage();
  if (!p || !p.audio_file_path) {
    showToast("현재 문항의 생성된 MP3 음성 파일이 없습니다. 먼저 [🎙️ 음성 생성]을 실행해 주세요.", "warning");
    return;
  }
  const a = document.createElement("a");
  a.href = p.audio_file_path;
  const safeId = (p.display_id || p.id).replace(/[\[\]]/g, "");
  a.download = `${safeId}.mp3`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  showToast(`⬇️ [${p.display_id || p.id}] 문항의 단일 MP3 파일을 다운로드합니다.`, "info");
}

/** 시험지 전체 듣기 문항 범위 동적 계산 및 ZIP 배지 반영 */
export function updateListeningZipRangeBadge(p) {
  const zipRangeEl = document.getElementById("ttsListeningZipRange");
  if (!zipRangeEl) return;

  let startQ = 1;
  let endQ = p && typeof p.listening_end_q === "number" && p.listening_end_q > 0 ? p.listening_end_q : null;

  if (p && typeof p.listening_start_q === "number" && p.listening_start_q > 0) {
    startQ = p.listening_start_q;
  }

  const list =
    appState.currentExamQuestions && appState.currentExamQuestions.length > 0
      ? appState.currentExamQuestions
      : appState.rawPassagesData && appState.rawPassagesData.length > 0
      ? appState.rawPassagesData
      : appState.passagesData;

  if (list && list.length > 0) {
    const listeningNums = [];
    list.forEach((item) => {
      if (item.area === "listening") {
        if (typeof item.q_num === "number") listeningNums.push(item.q_num);
        if (item.subItems && Array.isArray(item.subItems)) {
          item.subItems.forEach((si) => {
            if (typeof si.q_num === "number") listeningNums.push(si.q_num);
          });
        }
      }
    });
    if (listeningNums.length > 0) {
      startQ = Math.min(...listeningNums);
      if (!endQ) {
        endQ = Math.max(...listeningNums);
      }
    }
  }

  if (!endQ) {
    const examStr = `${p?.exam_id || ""} ${p?.year || ""}`;
    if (examStr.includes("2013")) {
      endQ = 22;
    } else {
      endQ = 17;
    }
  }

  zipRangeEl.textContent = `${startQ}~${endQ}`;
  zipRangeEl.title = `${startQ}번부터 ${endQ}번까지 시험지 전체 듣기 문항 포함`;
  const zipBtn = document.getElementById("btnDownloadListeningZip");
  if (zipBtn) {
    zipBtn.title = `이 시험지 전체(${startQ}~${endQ}번) 듣기 MP3 압축 파일(ZIP) 일괄 다운로드`;
    zipBtn.setAttribute("aria-label", `세트 전체 ${startQ}~${endQ}번 듣기 MP3 ZIP 다운로드`);
  }
}
if (typeof window !== "undefined") {
  window.updateListeningZipRangeBadge = updateListeningZipRangeBadge;
}

/** 시험지 세트 전체 ZIP 압축 일괄 다운로드 */
export function executeDownloadExamListeningZip() {
  const p = getCurrentActivePassage();
  if (!p || !p.exam_id) {
    showToast("선택된 시험지 정보가 없습니다.", "warning");
    return;
  }
  const zipRangeEl = document.getElementById("ttsListeningZipRange");
  const rangeText = zipRangeEl ? zipRangeEl.textContent : "1~17";
  showToast(`📦 [${p.exam_id}] 세트 전체(${rangeText}번) 듣기 MP3 압축 파일을 다운로드합니다...`, "info");
  downloadExamListeningZip(p.exam_id);
}

// ---------------------------------------------------------------------------
// 이벤트 리스너 초기화 (main.js에서 init으로 호출)
// ---------------------------------------------------------------------------
export function initPassageEvents() {
  // 상단 탭 스크롤 버튼
  if (btnTabScrollLeft) {
    btnTabScrollLeft.addEventListener("click", () => {
      passageTabBar.scrollBy({ left: -220, behavior: "smooth" });
    });
  }
  if (btnTabScrollRight) {
    btnTabScrollRight.addEventListener("click", () => {
      passageTabBar.scrollBy({ left: 220, behavior: "smooth" });
    });
  }

  // 키보드 방향키(←, →)로 문항 탭 전환 지원
  window.addEventListener("keydown", (e) => {
    if (passageViewContainer.style.display === "none") return;
    const activeTagName = document.activeElement ? document.activeElement.tagName.toLowerCase() : "";
    if (activeTagName === "input" || activeTagName === "textarea" || activeTagName === "select") return;

    const targetList =
      appState.currentExamQuestions && appState.currentExamQuestions.length > 0
        ? appState.currentExamQuestions
        : appState.passagesData;
    if (!targetList || targetList.length === 0) return;

    if (e.key === "ArrowLeft") {
      if (appState.currentPassageIndex > 0) {
        selectPassageTab(appState.currentPassageIndex - 1, targetList);
      }
    } else if (e.key === "ArrowRight") {
      if (appState.currentPassageIndex < targetList.length - 1) {
        selectPassageTab(appState.currentPassageIndex + 1, targetList);
      }
    }
  });

  // 정답 수동 정정
  if (btnEditAnswer) {
    btnEditAnswer.addEventListener("click", () => {
      const p = getCurrentActivePassage();
      if (!p || !answerEditForm) return;
      const targets = p.isGroup && p.subItems ? p.subItems : [p];
      answerEditQ.innerHTML = targets.map((t, i) => `<option value="${i}">${t.q_num}번</option>`).join("");
      answerEditQ.style.display = targets.length > 1 ? "inline-block" : "none";
      answerEditQ.value = "0";
      answerEditVal.value = ["①", "②", "③", "④", "⑤"].includes(targets[0].answer_text) ? targets[0].answer_text : "①";
      answerEditForm.style.display = "inline-flex";
    });
    answerEditQ.addEventListener("change", () => {
      const p = getCurrentActivePassage();
      const targets = p && p.isGroup && p.subItems ? p.subItems : [p];
      const t = targets[Number(answerEditQ.value)] || targets[0];
      if (t && ["①", "②", "③", "④", "⑤"].includes(t.answer_text)) answerEditVal.value = t.answer_text;
    });
    btnCancelAnswer.addEventListener("click", () => {
      answerEditForm.style.display = "none";
    });
    btnSaveAnswer.addEventListener("click", async () => {
      const p = getCurrentActivePassage();
      if (!p) return;
      const targets = p.isGroup && p.subItems ? p.subItems : [p];
      const target = targets[Number(answerEditQ.value)] || targets[0];
      const newAns = answerEditVal.value;
      if (target.answer_text === newAns) {
        answerEditForm.style.display = "none";
        return;
      }
      if (
        !confirm(
          `${target.id} 정답을 '${target.answer_text || "-"}' → '${newAns}' 로 정정할까요?\n(DB·해설·형광펜 이미지·검증 키 파일에 함께 반영됩니다)`
        )
      ) {
        return;
      }
      btnSaveAnswer.disabled = true;
      btnSaveAnswer.textContent = "반영 중...";
      try {
        const data = await updateAnswerApi(target.id, newAns);
        applyPassageUpdate(data.passage, p.id);
        showToast(data.message || "정답이 정정되었습니다.", "success");
      } catch (err) {
        console.error(err);
        showToast(err.message || "정답 정정 중 오류가 발생했습니다.", "error");
      } finally {
        btnSaveAnswer.disabled = false;
        btnSaveAnswer.textContent = "저장";
        if (answerEditForm) answerEditForm.style.display = "none";
      }
    });
  }

  // PDF 캡처 다시 실행
  if (btnRecapturePdf) {
    btnRecapturePdf.addEventListener("click", handleRecapturePdf);
  }

  if (panelPdfImageContainer) {
    panelPdfImageContainer.addEventListener("click", (e) => {
      const btn = e.target && e.target.closest(".btn-inline-recapture");
      if (btn && !btn.disabled && !isRecapturingPdf) {
        handleRecapturePdf();
      }
    });
  }

  // 문항 오류 신고 버튼
  const btnReportPassage = document.getElementById("btnReportPassage");
  if (btnReportPassage) {
    btnReportPassage.addEventListener("click", () => {
      const p = getCurrentActivePassage();
      if (p) {
        openPassageReportModal(p);
      } else {
        showToast("선택된 문항이 없습니다.", "warning");
      }
    });
  }

  // PDF 문항 캡처 이미지 수동 업로드
  const btnUploadCrop = document.getElementById("btnUploadPassageCrop");
  const inputUploadCrop = document.getElementById("inputUploadPassageCrop");
  if (btnUploadCrop && inputUploadCrop) {
    btnUploadCrop.addEventListener("click", () => {
      const p = getCurrentActivePassage();
      if (!p) {
        showToast("선택된 문항이 없습니다.", "warning");
        return;
      }
      inputUploadCrop.value = "";
      inputUploadCrop.click();
    });

    inputUploadCrop.addEventListener("change", async (e) => {
      const file = e.target.files && e.target.files[0];
      if (!file) return;

      const p = getCurrentActivePassage();
      if (!p) return;

      const formData = new FormData();
      formData.append("file", file);

      btnUploadCrop.disabled = true;
      btnUploadCrop.textContent = "업로드 중...";
      try {
        const cleanId = (p.id || "").replace(/^\[|\]$/g, "");
        const res = await fetch(`/api/passages/${encodeURIComponent(cleanId)}/upload-crop`, {
          method: "POST",
          body: formData,
        });
        const data = await res.json();
        if (!res.ok || !data.success) {
          throw new Error(data.detail || data.message || "이미지 업로드에 실패했습니다.");
        }

        // 최신 이미지 반영
        if (data.passage) {
          applyPassageUpdate(data.passage, p.id);
        }
        // DOM 상의 이미지 강제 리로드 (캐시 버스팅)
        if (panelPdfImageContainer && data.image_url) {
          const img = panelPdfImageContainer.querySelector("img");
          if (img) {
            img.src = data.image_url;
          }
        }
        showToast(data.message || "PDF 문항 이미지가 성공적으로 최신 파일로 교체되었습니다.", "success");
      } catch (err) {
        showToast(`이미지 교체 실패: ${err.message}`, "error");
      } finally {
        btnUploadCrop.disabled = false;
        btnUploadCrop.textContent = "📤 이미지 수동 업로드";
        inputUploadCrop.value = "";
      }
    });
  }

  // 듣기 음성 파일 수동 업로드
  const btnUploadAudio = document.getElementById("btnUploadListeningAudio");
  const inputUploadAudio = document.getElementById("inputUploadListeningAudio");
  if (btnUploadAudio && inputUploadAudio) {
    btnUploadAudio.addEventListener("click", () => {
      const p = getCurrentActivePassage();
      if (!p) {
        showToast("선택된 문항이 없습니다.", "warning");
        return;
      }
      inputUploadAudio.value = "";
      inputUploadAudio.click();
    });

    inputUploadAudio.addEventListener("change", async (e) => {
      const file = e.target.files && e.target.files[0];
      if (!file) return;

      const p = getCurrentActivePassage();
      if (!p) return;

      const formData = new FormData();
      formData.append("file", file);

      btnUploadAudio.disabled = true;
      const originalHtml = btnUploadAudio.innerHTML;
      btnUploadAudio.innerHTML = `<span class="tts-btn-icon">⏳</span><span class="tts-btn-label">업로드 중</span>`;
      try {
        const cleanId = (p.id || "").replace(/^\[|\]$/g, "");
        const res = await fetch(`/api/passages/${encodeURIComponent(cleanId)}/upload-audio`, {
          method: "POST",
          body: formData,
        });
        const data = await res.json();
        if (!res.ok || !data.success) {
          throw new Error(data.detail || data.message || "오디오 업로드에 실패했습니다.");
        }

        showToast(data.message || "듣기 오디오가 성공적으로 최신 음성으로 교체되었습니다.", "success");
      } catch (err) {
        showToast(`오디오 교체 실패: ${err.message}`, "error");
      } finally {
        btnUploadAudio.disabled = false;
        btnUploadAudio.innerHTML = originalHtml;
        inputUploadAudio.value = "";
      }
    });
  }

  if (btnUploadRateFromViewer) {
    btnUploadRateFromViewer.addEventListener("click", () => {
      const p = getCurrentActivePassage();
      const currentExamId = p ? p.exam_id : null;
      if (!currentExamId) return;
      triggerSingleFileUpload(currentExamId, "csv", btnUploadRateFromViewer);
    });
  }

  if (btnAddPassageTag) {
    btnAddPassageTag.addEventListener("click", addPassageTagAction);
  }
  if (inputPassageTag) {
    inputPassageTag.addEventListener("keydown", (e) => {
      if (e.key === "Enter") addPassageTagAction();
    });
  }

  // 지문 메모 이벤트 리스너 바인딩
  if (inputPassageMemo) {
    inputPassageMemo.addEventListener("input", handleMemoInput);
    inputPassageMemo.addEventListener("keydown", (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
        e.preventDefault();
        clearMemoSaveTimer();
        savePassageMemo(false);
      }
    });
    inputPassageMemo.addEventListener("blur", () => {
      if (isMemoDirty) {
        clearMemoSaveTimer();
        savePassageMemo(true);
      }
    });
  }
  if (btnSavePassageMemo) {
    btnSavePassageMemo.addEventListener("click", () => {
      clearMemoSaveTimer();
      savePassageMemo(false);
    });
  }

  // 지문 전체 복사 버튼
  if (btnCopyPassage) {
    btnCopyPassage.addEventListener("click", () => {
      const text = panelPassageText ? panelPassageText.dataset.rawText || panelPassageText.textContent : "";
      if (text && text !== "지문 본문이 여기에 표시됩니다." && text !== "-") {
        copyToClipboard(text, "지문 본문이 클립보드에 복사되었습니다! (Ctrl+V)");
      }
    });
  }

  // 해설 복사 버튼
  if (btnCopyExplanation) {
    btnCopyExplanation.addEventListener("click", () => {
      const text = panelExplanation ? panelExplanation.textContent : "";
      if (text && text !== "-") {
        copyToClipboard(text, "정답 및 해설이 클립보드에 복사되었습니다!");
      }
    });
  }

  // 듣기 모드 전용 버튼 이벤트 바인딩
  if (btnCopyFelsBlank) {
    btnCopyFelsBlank.addEventListener("click", copyFelsBlankVersion);
  }
  if (btnCopyFelsAnswer) {
    btnCopyFelsAnswer.addEventListener("click", copyFelsAnswerVersion);
  }
  if (btnCopyFels) {
    btnCopyFels.addEventListener("click", copyFelsBlankVersion);
  }
  if (btnToggleFelsAnswer) {
    btnToggleFelsAnswer.addEventListener("click", () => {
      const p = getCurrentActivePassage();
      if (!p) return;
      const nextMode = currentFelsViewMode === "blank" ? "answer" : "blank";
      renderFelsBottomLeftPanel(p, nextMode);
    });
  }

  if (btnCopyScript) {
    btnCopyScript.addEventListener("click", () => {
      const p = getCurrentActivePassage();
      const scText = p ? p.script_text || p.passage_text || "" : "";
      if (!scText) {
        showToast("복사할 대본 텍스트가 없습니다.", "warning");
        return;
      }
      copyToClipboard(scText, "영문 대본 텍스트가 클립보드에 복사되었습니다!");
    });
  }

  // 전역 클릭 이벤트 위임
  document.addEventListener("click", (e) => {
    const targetEngineBtn = e.target.closest(".tts-engine-btn");
    if (targetEngineBtn) {
      e.preventDefault();
      const eng = targetEngineBtn.dataset.engine;
      if (eng) handleSwitchTtsEngine(eng);
      return;
    }

    const targetSingle = e.target.closest("#btnGenerateListeningAudio");
    if (targetSingle) {
      e.preventDefault();
      handleGenerateListeningAudioAction(targetSingle);
      return;
    }

    const targetAll = e.target.closest("#btnGenerateAllListeningAudio");
    if (targetAll) {
      e.preventDefault();
      handleGenerateAllListeningAudioAction(targetAll);
      return;
    }

    const targetCopyScript = e.target.closest("#btnCopyScript");
    if (targetCopyScript) {
      e.preventDefault();
      const p = getCurrentActivePassage();
      const scText = p ? p.script_text || p.passage_text || "" : "";
      if (!scText) {
        showToast("복사할 대본 텍스트가 없습니다.", "warning");
        return;
      }
      copyToClipboard(scText, "영문 대본 텍스트가 클립보드에 복사되었습니다!");
      return;
    }

    const targetMp3 = e.target.closest("#btnDownloadListeningMp3");
    if (targetMp3) {
      e.preventDefault();
      executeDownloadPassageMp3();
      return;
    }

    const targetZip = e.target.closest("#btnDownloadListeningZip");
    if (targetZip) {
      e.preventDefault();
      executeDownloadExamListeningZip();
      return;
    }
  });

  if (btnDownloadListeningMp3) {
    btnDownloadListeningMp3.addEventListener("click", executeDownloadPassageMp3);
  }

  if (btnDownloadListeningZip) {
    btnDownloadListeningZip.addEventListener("click", executeDownloadExamListeningZip);
  }

  window.addEventListener("exam-file-uploaded", () => {
    if (currentLoadedExamRawFilesId) {
      renderBreadcrumbExamFiles(currentLoadedExamRawFilesId, true);
    }
  });
}
