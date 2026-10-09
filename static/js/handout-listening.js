/**
 * 05-gichul_db: 교사용 듣기 유인물 제작소 프론트엔드 모듈 (handout-listening.js)
 * - B4 세로 2x3 테이블 규격 (한 페이지 2문항) 레이아웃 화면 미리보기
 * - 듣기 문항 카드 렌더링, 1열(문항)/2열(약형드랩)/3열(표현정리) 실시간 뷰
 * - 문항 번호 수정, 순서 변경, 개별 오디오 미리듣기, 문항 삭제
 * - 1번부터 / N번부터 순차 재부여 및 전체 비우기
 * - 머리말 서식 설정 자동 저장
 * - 문제지 / 해설지 B4 HWPX 다운로드, 통합 MP3 다운로드, 일괄 ZIP 다운로드
 */

import {
  getListeningProjects,
  getCurrentListeningProjectId,
  getCurrentListeningProject,
  getListeningProjectSettings,
  saveListeningProjectSettings,
  getListeningCartItems,
  saveListeningCartItems,
  removeFromListeningCart,
  reorderListeningCart,
  setListeningCustomQNum,
  renumberListeningCart,
  clearListeningCart,
  syncAllProjectDropdowns
} from "./handout-cart.js";
import { listeningClassroom } from "./listening-classroom.js";

// 오디오 미리듣기 재생 상태 관리
let currentPlayingAudio = null;
let currentPlayingBtn = null;

function stopCurrentAudio() {
  if (currentPlayingAudio) {
    try {
      currentPlayingAudio.pause();
      currentPlayingAudio.currentTime = 0;
    } catch (e) {
      // 무시
    }
    currentPlayingAudio = null;
  }
  if (currentPlayingBtn) {
    currentPlayingBtn.innerHTML = "▶ 재생";
    currentPlayingBtn.style.background = "#0284c7";
    currentPlayingBtn = null;
  }
}

/** HTML 특수문자 이스케이프 헬퍼 */
function escapeHtml(str) {
  if (!str) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

/** 듣기 유인물 화면 전체 렌더링 */
export async function renderListeningHandoutView() {
  const container = document.getElementById("handoutListeningItemsList");
  const countBadge = document.getElementById("listeningCountBadge");
  if (!container) return;

  stopCurrentAudio();

  const items = getListeningCartItems();
  const proj = getCurrentListeningProject();
  const settings = getListeningProjectSettings(proj.id);

  // 머리말 설정 폼 필드 복원
  const inLeft = document.getElementById("listeningHeaderLeft");
  const inCenter = document.getElementById("listeningHeaderCenter");
  const inRight = document.getElementById("listeningHeaderRight");

  if (inLeft && !inLeft.dataset.userEditing) inLeft.value = settings.header_left || "";
  if (inCenter && !inCenter.dataset.userEditing) inCenter.value = settings.header_center || "";
  if (inRight && !inRight.dataset.userEditing) inRight.value = settings.header_right || "";

  if (countBadge) {
    countBadge.textContent = `${items.length}문항`;
  }

  if (items.length === 0) {
    container.innerHTML = `
      <div style="text-align: center; padding: 60px 20px; background: #faf5ff; border: 2px dashed #d8b4fe; border-radius: 12px; color: #6b21a8;">
        <div style="font-size: 3rem; margin-bottom: 12px;">🎧</div>
        <h3 style="font-size: 1.15rem; font-weight: 800; margin-bottom: 8px;">보관된 듣기 문항이 없습니다.</h3>
        <p style="font-size: 0.88rem; color: #7e22ce; line-height: 1.6; max-width: 460px; margin: 0 auto;">
          검색 화면에서 <strong>영어 듣기 문항(1~17번)</strong>을 열람하신 후,<br>
          상단의 <strong>[🎧 듣기 유인물 담기]</strong> 버튼을 클릭하여 문항을 추가해 주세요.<br>
          <span style="font-size: 0.82rem; color: #a855f7;">* B4 세로 양식으로 페이지당 2문항씩 자동 배치됩니다.</span>
        </p>
      </div>
    `;
    return;
  }

  // 로딩 표시
  container.innerHTML = `
    <div style="text-align: center; padding: 40px; color: #7c3aed; font-weight: 600;">
      ⏳ 듣기 문항 및 FELS 약형드랩 데이터를 불러오는 중...
    </div>
  `;

  // 서버에서 상세 미리보기 데이터 조회
  let previewData = [];
  try {
    const res = await fetch("/api/handouts/listening/preview-info", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ passage_ids: items.map((it) => it.id) }),
    });
    if (res.ok) {
      const data = await res.json();
      previewData = data.items || [];
    }
  } catch (err) {
    console.warn("듣기 유인물 미리보기 로드 실패", err);
  }

  // ID 매핑 테이블 생성
  const previewMap = new Map();
  previewData.forEach((p) => previewMap.set(p.id, p));

  // 2문항씩 페이지 단위로 그룹화 (B4 세로 2x3 테이블 규격)
  const pages = [];
  for (let i = 0; i < items.length; i += 2) {
    pages.push(items.slice(i, i + 2));
  }

  let html = "";
  pages.forEach((pageItems, pageIdx) => {
    html += `
      <div class="listening-page-group">
        <div class="listening-page-header">
          <div class="listening-page-title">
            <span>📄 Page ${pageIdx + 1}</span>
            <span class="listening-page-badge">B4 세로 2문항/페이지</span>
          </div>
          <div style="font-size: 0.82rem; color: #6d28d9; font-weight: 700;">
            포함 문항: ${pageItems.map((it) => `${it.custom_q_num || "?"}번`).join(", ")}
          </div>
        </div>
        <div class="listening-page-items">
    `;

    pageItems.forEach((item, itemInPageIdx) => {
      const globalIdx = pageIdx * 2 + itemInPageIdx;
      const pInfo = previewMap.get(item.id) || {};
      const qNumVal = item.custom_q_num || String(globalIdx + 1);

      const titleText = pInfo.question_title || `${qNumVal}. 대화를 듣고, 알맞은 답을 고르시오.`;
      const choicesText = pInfo.choices_text || "";
      const fullQText = choicesText ? `${titleText}\n\n${choicesText}` : titleText;

      const felsBlankText = pInfo.fels_blank_text || pInfo.script_text || "(대본 텍스트 없음)";
      const audioUrl = pInfo.audio_file_path || "";
      const korTrans = pInfo.korean_translation || "(해설지 우리말 해석 자동 연동)";

      html += `
        <div class="listening-card-item" data-id="${escapeHtml(item.id)}" data-idx="${globalIdx}">
          <div class="listening-card-header">
            <div class="handout-item-qnum-box">
              <span style="font-size: 0.85rem; font-weight: 700; color: #475569;">인쇄 번호:</span>
              <input type="text" class="handout-item-qnum-input input-listening-custom-num" data-id="${escapeHtml(item.id)}" value="${escapeHtml(qNumVal)}" title="유인물에 실제로 인쇄될 문항 번호를 직접 입력하세요">
              <span style="font-size: 0.85rem; font-weight: 700; color: #1d4ed8;">번</span>
              <span class="handout-item-source-badge btn-goto-passage" data-id="${escapeHtml(item.id)}" title="해당 지문 결과창으로 이동">[${escapeHtml(item.id.replace(/^\[/, "").replace(/\]$/, ""))}]</span>
              ${pInfo.question_type ? `<span style="font-size: 0.8rem; color: #64748b;">(${escapeHtml(pInfo.question_type)})</span>` : ""}
            </div>
            <div class="handout-item-controls">
              ${audioUrl ? `
                <button type="button" class="btn-card-audio" data-url="${escapeHtml(audioUrl)}" title="문항 음성 미리듣기" style="padding: 3px 8px; font-size: 0.76rem; border-radius: 4px; border: 1px solid #c7d2fe; background: #e0e7ff; color: #3730a3; cursor: pointer; font-weight: 600;">
                  ▶ 재생
                </button>
              ` : `
                <span style="font-size: 0.74rem; color: #94a3b8; padding: 2px 4px;">(음성 미생성)</span>
              `}
              <button type="button" class="btn-card-move btn-order-up" data-idx="${globalIdx}" title="위로 이동" ${globalIdx === 0 ? "disabled" : ""}>▲</button>
              <button type="button" class="btn-card-move btn-order-down" data-idx="${globalIdx}" title="아래로 이동" ${globalIdx === items.length - 1 ? "disabled" : ""}>▼</button>
              <button type="button" class="btn-card-delete" data-id="${escapeHtml(item.id)}" title="이 문항 삭제">✕</button>
            </div>
          </div>

          <!-- B4 세로 2x3 테이블 3열 미리보기 구조 -->
          <div class="listening-preview-3col">
            <div class="listening-preview-col">
              <div class="preview-col-label">1열: 듣기 문항 텍스트</div>
              <div class="preview-col-content">${escapeHtml(fullQText)}</div>
            </div>
            <div class="listening-preview-col">
              <div class="preview-col-label">2열: FELS 약형드랩 [   ]</div>
              <div class="preview-col-content" style="color: #6d28d9;">${escapeHtml(felsBlankText)}</div>
            </div>
            <div class="listening-preview-col">
              <div class="preview-col-label">3열: [표현 정리] 5행 필기표 / 해설</div>
              <div class="preview-col-content" style="color: #475569; font-size: 0.78rem;">
                <div style="font-weight: 700; color: #0f766e; margin-bottom: 4px;">[문제지: 우리말 | 영어 5행 빈칸]</div>
                <div style="color: #0369a1; font-weight: 700;">[해설지 대본 전문 / 우리말 해석]:</div>
                <div>${escapeHtml(korTrans.slice(0, 150))}${korTrans.length > 150 ? "..." : ""}</div>
              </div>
            </div>
          </div>
        </div>
      `;
    });

    html += `
        </div>
      </div>
    `;
  });

  container.innerHTML = html;
  bindListeningCardEvents(container);
}

/** 카드 내부 인터랙션 이벤트 바인딩 */
function bindListeningCardEvents(container) {
  // 출처 클릭 시 해당 지문 결과창으로 즉시 이동
  container.querySelectorAll(".btn-goto-passage").forEach((badge) => {
    badge.addEventListener("click", () => {
      const pid = badge.dataset.id;
      if (pid) {
        import("./results-sentence.js").then((m) => {
          m.navigateToPassageView(pid, "listening");
        });
      }
    });
  });

  // 번호 직접 수정
  container.querySelectorAll(".input-listening-custom-num").forEach((input) => {
    input.addEventListener("change", (e) => {
      const pid = e.target.dataset.id;
      const val = e.target.value.trim();
      if (pid && val) {
        setListeningCustomQNum(pid, val);
      }
    });
  });

  // 오디오 미리듣기 토글
  container.querySelectorAll(".btn-card-audio").forEach((btn) => {
    btn.addEventListener("click", () => {
      const url = btn.dataset.url;
      if (!url) return;

      if (currentPlayingBtn === btn && currentPlayingAudio && !currentPlayingAudio.paused) {
        stopCurrentAudio();
        return;
      }

      stopCurrentAudio();

      const audio = new Audio(url);
      currentPlayingAudio = audio;
      currentPlayingBtn = btn;

      btn.innerHTML = "⏹ 중지";
      btn.style.background = "#e11d48";

      audio.play().catch((err) => {
        console.warn("오디오 재생 오류", err);
        stopCurrentAudio();
      });

      audio.onended = () => {
        stopCurrentAudio();
      };
      audio.onerror = () => {
        stopCurrentAudio();
      };
    });
  });

  // 순서 위로 이동
  container.querySelectorAll(".btn-order-up").forEach((btn) => {
    btn.addEventListener("click", () => {
      const idx = parseInt(btn.dataset.idx, 10);
      if (idx > 0) {
        reorderListeningCart(idx, idx - 1);
        renderListeningHandoutView();
      }
    });
  });

  // 순서 아래로 이동
  container.querySelectorAll(".btn-order-down").forEach((btn) => {
    btn.addEventListener("click", () => {
      const idx = parseInt(btn.dataset.idx, 10);
      const items = getListeningCartItems();
      if (idx < items.length - 1) {
        reorderListeningCart(idx, idx + 1);
        renderListeningHandoutView();
      }
    });
  });

  // 문항 삭제
  container.querySelectorAll(".btn-card-delete").forEach((btn) => {
    btn.addEventListener("click", () => {
      const pid = btn.dataset.id;
      if (pid) {
        removeFromListeningCart(pid);
        renderListeningHandoutView();
      }
    });
  });
}

/** 머리말 설정 입력 변경 시 자동 저장 */
function setupListeningHeaderAutoSave() {
  const inLeft = document.getElementById("listeningHeaderLeft");
  const inCenter = document.getElementById("listeningHeaderCenter");
  const inRight = document.getElementById("listeningHeaderRight");

  const saveSettings = () => {
    const curPId = getCurrentListeningProjectId();
    saveListeningProjectSettings(curPId, {
      header_left: (inLeft ? inLeft.value : "").trim(),
      header_center: (inCenter ? inCenter.value : "").trim(),
      header_right: (inRight ? inRight.value : "").trim(),
    });
  };

  [inLeft, inCenter, inRight].forEach((input) => {
    if (!input) return;
    input.addEventListener("focus", () => {
      input.dataset.userEditing = "true";
    });
    input.addEventListener("blur", () => {
      delete input.dataset.userEditing;
      saveSettings();
    });
    input.addEventListener("input", saveSettings);
  });
}

/** 다운로드 실행 헬퍼 */
async function downloadListeningHandout(handoutType) {
  const items = getListeningCartItems();
  if (items.length === 0) {
    alert("유인물로 다운로드할 듣기 문항이 없습니다. 문항을 먼저 추가해 주세요.");
    return;
  }

  const curProj = getCurrentListeningProject();
  const settings = getListeningProjectSettings(curProj.id);

  const customQNums = {};
  items.forEach((it, idx) => {
    customQNums[it.id] = String(it.custom_q_num || (idx + 1)).trim();
  });

  const inLeft = document.getElementById("listeningHeaderLeft");
  const inCenter = document.getElementById("listeningHeaderCenter");
  const inRight = document.getElementById("listeningHeaderRight");

  const payload = {
    handout_type: handoutType,
    passage_ids: items.map((it) => it.id),
    custom_q_nums: customQNums,
    header_left: inLeft ? inLeft.value.trim() : (settings.header_left || ""),
    header_center: inCenter ? inCenter.value.trim() : (settings.header_center || ""),
    header_right: inRight ? inRight.value.trim() : (settings.header_right || ""),
  };

  // 다운로드 버튼 로딩 시각 피드백
  let activeBtn = null;
  if (handoutType === "question") activeBtn = document.getElementById("btnDownloadListeningQuestion");
  else if (handoutType === "explanation") activeBtn = document.getElementById("btnDownloadListeningExplanation");
  else if (handoutType === "zip") activeBtn = document.getElementById("btnDownloadListeningZip");

  const origHtml = activeBtn ? activeBtn.innerHTML : "";
  if (activeBtn) {
    activeBtn.disabled = true;
    activeBtn.innerHTML = `<span>⏳ 생성 및 변환 중...</span>`;
  }

  try {
    const res = await fetch("/api/handouts/listening/download", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || "유인물 생성에 실패했습니다.");
    }

    const blob = await res.blob();
    let filename = `듣기유인물_${handoutType}.hwpx`;
    const cd = res.headers.get("Content-Disposition");
    if (cd) {
      const mUtf = cd.match(/filename\*=UTF-8''([^;]+)/i);
      if (mUtf) {
        filename = decodeURIComponent(mUtf[1]);
      } else {
        const mAsc = cd.match(/filename="?([^";]+)"?/i);
        if (mAsc) filename = mAsc[1];
      }
    }

    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(link.href);
  } catch (err) {
    alert(`다운로드 실패: ${err.message}`);
  } finally {
    if (activeBtn) {
      activeBtn.disabled = false;
      activeBtn.innerHTML = origHtml;
    }
  }
}

let currentMergeJobId = null;
let mergeProgressTimer = null;

/** 전체 통합 MP3 음원 상태 확인 모달 열기 */
export async function openListeningAudioModal() {
  const items = getListeningCartItems();
  if (items.length === 0) {
    alert("통합 MP3로 다운로드할 듣기 문항이 없습니다. 문항을 먼저 추가해 주세요.");
    return;
  }

  const modal = document.getElementById("listeningAudioStatusModal");
  if (!modal) return;

  modal.style.display = "flex";

  // 작업 상태 초기화
  currentMergeJobId = null;
  if (mergeProgressTimer) {
    clearInterval(mergeProgressTimer);
    mergeProgressTimer = null;
  }

  // UI 초기화
  const progPanel = document.getElementById("listeningAudioProgressPanel");
  if (progPanel) progPanel.style.display = "none";

  const btnStart = document.getElementById("btnStartListeningAudioMerge");
  const btnStop = document.getElementById("btnStopListeningAudioMerge");
  if (btnStart) {
    btnStart.style.display = "inline-block";
    btnStart.disabled = false;
    btnStart.innerHTML = "▶ 음성 결합 및 MP3 다운로드 시작";
  }
  if (btnStop) btnStop.style.display = "none";

  const tbody = document.getElementById("listeningAudioTableBody");
  if (tbody) {
    tbody.innerHTML = `
      <tr>
        <td colspan="5" style="text-align: center; padding: 30px; color: #7c3aed; font-weight: 600;">
          ⏳ 문항별 음원 상태를 조회하는 중입니다...
        </td>
      </tr>
    `;
  }

  const curProj = getCurrentListeningProject();

  // 음원 상태 API 조회
  try {
    const res = await fetch("/api/handouts/listening/audio-status", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        passage_ids: items.map((it) => it.id),
        project_name: curProj.name || "듣기유인물",
      }),
    });

    if (!res.ok) {
      throw new Error("음원 상태 조회에 실패했습니다.");
    }

    const data = await res.json();
    renderListeningAudioStatusTable(data);
  } catch (err) {
    if (tbody) {
      tbody.innerHTML = `
        <tr>
          <td colspan="5" style="text-align: center; padding: 25px; color: #dc2626;">
            ❌ 음원 상태 조회 실패: ${err.message}
          </td>
        </tr>
      `;
    }
  }
}

/** 문항별 음원 상태 테이블 렌더링 */
function renderListeningAudioStatusTable(data) {
  const totalCountElem = document.getElementById("listeningAudioTotalCount");
  const readyCountElem = document.getElementById("listeningAudioReadyCount");
  const missingCountElem = document.getElementById("listeningAudioMissingCount");

  if (totalCountElem) totalCountElem.textContent = data.total_count || 0;
  if (readyCountElem) readyCountElem.textContent = data.ready_count || 0;
  if (missingCountElem) missingCountElem.textContent = data.missing_count || 0;

  const tbody = document.getElementById("listeningAudioTableBody");
  if (!tbody) return;

  const items = data.items || [];
  if (items.length === 0) {
    tbody.innerHTML = `
      <tr>
        <td colspan="5" style="text-align: center; padding: 25px; color: #9ca3af;">
          선택된 문항이 없습니다.
        </td>
      </tr>
    `;
    return;
  }

  let html = "";
  items.forEach((it, idx) => {
    const safePid = encodeURIComponent(it.id);
    const statusBadge = it.has_audio
      ? `<span class="listening-badge-ready" style="display: inline-block; padding: 4px 8px; border-radius: 4px; background: #ecfdf5; color: #047857; font-weight: 700; font-size: 0.78rem;">✅ 준비됨 (${it.file_size_kb}KB)</span>`
      : `<span class="listening-badge-missing" style="display: inline-block; padding: 4px 8px; border-radius: 4px; background: #fffbeb; color: #b45309; font-weight: 700; font-size: 0.78rem;">⚠️ 미생성 (자동 합성 예정)</span>`;

    const playBtn = (it.has_audio && it.audio_url)
      ? `<button type="button" class="btn-audio-mini-play" data-url="${it.audio_url}" style="padding: 3px 8px; font-size: 0.75rem; border-radius: 4px; border: 1px solid #c7d2fe; background: #e0e7ff; color: #3730a3; cursor: pointer; font-weight: 600;">▶ 재생</button>`
      : `<span style="color: #9ca3af;">-</span>`;

    html += `
      <tr id="audioStatusRow_${safePid}" style="border-bottom: 1px solid #f3f4f6; transition: background 0.2s;">
        <td style="padding: 10px 12px; text-align: center; color: #6b7280; font-weight: 600;">${idx + 1}</td>
        <td style="padding: 10px 12px; text-align: center; font-weight: 700; color: #7c3aed;">${it.q_num}번</td>
        <td style="padding: 10px 12px; color: #1f2937; line-height: 1.4;">${it.title || "-"}</td>
        <td id="audioBadgeCell_${safePid}" style="padding: 10px 12px; text-align: center;">${statusBadge}</td>
        <td style="padding: 10px 12px; text-align: center;">${playBtn}</td>
      </tr>
    `;
  });

  tbody.innerHTML = html;

  // 미리듣기 버튼 오디오 이벤트 바인딩
  tbody.querySelectorAll(".btn-audio-mini-play").forEach((btn) => {
    btn.addEventListener("click", () => {
      const url = btn.getAttribute("data-url");
      if (url) {
        const audio = new Audio(url);
        audio.play().catch((e) => alert("오디오 재생 실패: " + e.message));
      }
    });
  });
}

/** 통합 MP3 결합 작업 시작 */
async function startListeningAudioMerge() {
  const items = getListeningCartItems();
  if (items.length === 0) return;

  const curProj = getCurrentListeningProject();
  const btnStart = document.getElementById("btnStartListeningAudioMerge");
  const btnStop = document.getElementById("btnStopListeningAudioMerge");
  const progPanel = document.getElementById("listeningAudioProgressPanel");
  const progMsg = document.getElementById("listeningAudioProgressMessage");
  const progPct = document.getElementById("listeningAudioProgressPercent");
  const progBar = document.getElementById("listeningAudioProgressBar");

  if (btnStart) btnStart.style.display = "none";
  if (btnStop) btnStop.style.display = "inline-block";
  if (progPanel) progPanel.style.display = "block";
  if (progMsg) progMsg.textContent = "⏳ 비동기 결합 작업을 초기화하는 중...";
  if (progPct) progPct.textContent = "0%";
  if (progBar) progBar.style.width = "0%";

  try {
    const res = await fetch("/api/handouts/listening/start-merge-audio", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        passage_ids: items.map((it) => it.id),
        project_name: curProj.name || "듣기유인물",
      }),
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || "작업 시작 실패");
    }

    const data = await res.json();
    currentMergeJobId = data.job_id;

    if (mergeProgressTimer) clearInterval(mergeProgressTimer);
    mergeProgressTimer = setInterval(pollMergeProgress, 1000);
  } catch (err) {
    alert("오디오 결합 시작 실패: " + err.message);
    if (btnStart) btnStart.style.display = "inline-block";
    if (btnStop) btnStop.style.display = "none";
  }
}

/** 결합 진행률 폴링 */
async function pollMergeProgress() {
  if (!currentMergeJobId) return;

  try {
    const res = await fetch(`/api/handouts/listening/merge-audio-progress/${currentMergeJobId}`);
    if (!res.ok) return;

    const data = await res.json();
    const progMsg = document.getElementById("listeningAudioProgressMessage");
    const progPct = document.getElementById("listeningAudioProgressPercent");
    const progBar = document.getElementById("listeningAudioProgressBar");
    const btnStart = document.getElementById("btnStartListeningAudioMerge");
    const btnStop = document.getElementById("btnStopListeningAudioMerge");

    if (progMsg) progMsg.textContent = data.message || "작업 진행 중...";
    if (progPct) progPct.textContent = `${data.percent || 0}%`;
    if (progBar) progBar.style.width = `${data.percent || 0}%`;

    // 현재 처리 중인 문항 표시
    if (data.current_passage_id) {
      const safePid = encodeURIComponent(data.current_passage_id);
      const row = document.getElementById(`audioStatusRow_${safePid}`);
      if (row) {
        row.style.background = "#f0fdf4";
      }
      const badge = document.getElementById(`audioBadgeCell_${safePid}`);
      if (badge && data.step === "tts") {
        badge.innerHTML = `<span style="display: inline-block; padding: 4px 8px; border-radius: 4px; background: #e0f2fe; color: #0284c7; font-weight: 700; font-size: 0.78rem;">🔄 AI 합성 중...</span>`;
      }
    }

    // 완료된 경우
    if (data.status === "completed") {
      clearInterval(mergeProgressTimer);
      mergeProgressTimer = null;
      if (progPct) progPct.textContent = "100%";
      if (progBar) progBar.style.width = "100%";
      if (progMsg) progMsg.innerHTML = "🎉 <strong>전체 통합 MP3 생성이 완료되어 다운로드를 시작합니다!</strong>";

      if (btnStop) btnStop.style.display = "none";
      if (btnStart) {
        btnStart.style.display = "inline-block";
        btnStart.innerHTML = "🔄 다시 다운로드";
      }

      // 결과 다운로드 실행
      downloadMergedAudioResult(currentMergeJobId);
    }
    // 취소된 경우
    else if (data.status === "cancelled") {
      clearInterval(mergeProgressTimer);
      mergeProgressTimer = null;
      if (progMsg) progMsg.innerHTML = "⏹ <strong>작업이 중단되었습니다.</strong>";
      if (btnStop) btnStop.style.display = "none";
      if (btnStart) {
        btnStart.style.display = "inline-block";
        btnStart.innerHTML = "▶ 다시 시작";
      }
    }
    // 실패한 경우
    else if (data.status === "failed") {
      clearInterval(mergeProgressTimer);
      mergeProgressTimer = null;
      if (progMsg) progMsg.innerHTML = `❌ <strong>오류 발생:</strong> ${data.error || "실패"}`;
      if (btnStop) btnStop.style.display = "none";
      if (btnStart) {
        btnStart.style.display = "inline-block";
        btnStart.innerHTML = "▶ 다시 시도";
      }
    }
  } catch (e) {
    console.warn("진행률 폴링 중 오류:", e);
  }
}

/** 작업 중단 */
async function stopListeningAudioMerge() {
  if (!currentMergeJobId) return;

  const targetJobId = currentMergeJobId;
  const btnStop = document.getElementById("btnStopListeningAudioMerge");
  const btnStart = document.getElementById("btnStartListeningAudioMerge");
  const progMsg = document.getElementById("listeningAudioProgressMessage");

  if (mergeProgressTimer) {
    clearInterval(mergeProgressTimer);
    mergeProgressTimer = null;
  }

  if (btnStop) {
    btnStop.disabled = true;
    btnStop.textContent = "⏳ 중단하는 중...";
  }

  try {
    await fetch(`/api/handouts/listening/cancel-merge-audio/${targetJobId}`, {
      method: "POST",
    });
    if (progMsg) progMsg.innerHTML = "⏹ <strong>사용자에 의해 음성 생성이 즉각 중단되었습니다.</strong>";
  } catch (err) {
    console.warn("중단 요청 실패:", err);
  } finally {
    if (btnStop) {
      btnStop.disabled = false;
      btnStop.style.display = "none";
    }
    if (btnStart) {
      btnStart.style.display = "inline-block";
      btnStart.innerHTML = "▶ 다시 시작";
    }
  }
}

/** 최종 MP3 파일 다운로드 브라우저 트리거 */
function downloadMergedAudioResult(jobId) {
  if (!jobId) return;
  const link = document.createElement("a");
  link.href = `/api/handouts/listening/download-merged-result/${jobId}`;
  link.download = "";
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
}

/** 모달 닫기 */
function closeListeningAudioModal() {
  const activeJobId = currentMergeJobId;
  if (mergeProgressTimer || activeJobId) {
    // 진행 중인 백엔드 비동기 작업을 백그라운드에서 즉각 강제 중단
    if (mergeProgressTimer) {
      clearInterval(mergeProgressTimer);
      mergeProgressTimer = null;
    }
    currentMergeJobId = null;

    if (activeJobId) {
      fetch(`/api/handouts/listening/cancel-merge-audio/${activeJobId}`, {
        method: "POST",
        keepalive: true,
      }).catch((e) => console.warn("모달 닫기 시 작업 취소 통신:", e));
    }
  }

  const modal = document.getElementById("listeningAudioStatusModal");
  if (modal) modal.style.display = "none";
}


/** 이벤트 초기화 및 탭 전환 연결 */
export function initListeningHandoutEvents() {
  setupListeningHeaderAutoSave();

  // 1번부터 순차 재부여
  const btnRenumber1 = document.getElementById("btnListeningRenumber1");
  if (btnRenumber1) {
    btnRenumber1.addEventListener("click", () => {
      renumberListeningCart(1);
      renderListeningHandoutView();
    });
  }

  // N번부터 순차 재부여
  const btnRenumberN = document.getElementById("btnListeningRenumberN");
  const inStartNum = document.getElementById("inputListeningStartNum");
  if (btnRenumberN) {
    btnRenumberN.addEventListener("click", () => {
      const startVal = inStartNum ? (parseInt(inStartNum.value, 10) || 1) : 1;
      renumberListeningCart(startVal);
      renderListeningHandoutView();
    });
  }

  // 전체 비우기
  const btnClearAll = document.getElementById("btnListeningClearAll");
  if (btnClearAll) {
    btnClearAll.addEventListener("click", () => {
      const items = getListeningCartItems();
      if (items.length === 0) {
        alert("비울 듣기 문항이 없습니다.");
        return;
      }
      if (confirm(`현재 듣기 프로젝트에 담긴 모든 문항(${items.length}개)을 비우시겠습니까?`)) {
        clearListeningCart();
        renderListeningHandoutView();
      }
    });
  }

  // 다운로드 버튼들
  const btnDlQuestion = document.getElementById("btnDownloadListeningQuestion");
  if (btnDlQuestion) {
    btnDlQuestion.addEventListener("click", () => downloadListeningHandout("question"));
  }

  const btnDlExplanation = document.getElementById("btnDownloadListeningExplanation");
  if (btnDlExplanation) {
    btnDlExplanation.addEventListener("click", () => downloadListeningHandout("explanation"));
  }

  const btnDlMergedAudio = document.getElementById("btnDownloadListeningMergedAudio");
  if (btnDlMergedAudio) {
    btnDlMergedAudio.addEventListener("click", openListeningAudioModal);
  }

  // 듣기 음원 확인 및 결합 모달 내부 버튼들
  const btnCloseModal = document.getElementById("btnCloseListeningAudioModal");
  if (btnCloseModal) {
    btnCloseModal.addEventListener("click", closeListeningAudioModal);
  }

  const btnCancelModal = document.getElementById("btnCancelListeningAudioModal");
  if (btnCancelModal) {
    btnCancelModal.addEventListener("click", closeListeningAudioModal);
  }

  const btnStartMerge = document.getElementById("btnStartListeningAudioMerge");
  if (btnStartMerge) {
    btnStartMerge.addEventListener("click", startListeningAudioMerge);
  }

  const btnStopMerge = document.getElementById("btnStopListeningAudioMerge");
  if (btnStopMerge) {
    btnStopMerge.addEventListener("click", stopListeningAudioMerge);
  }

  const audioModal = document.getElementById("listeningAudioStatusModal");
  if (audioModal) {
    audioModal.addEventListener("click", (e) => {
      if (e.target === audioModal) {
        closeListeningAudioModal();
      }
    });
  }

  const btnDlZip = document.getElementById("btnDownloadListeningZip");
  if (btnDlZip) {
    btnDlZip.addEventListener("click", () => downloadListeningHandout("zip"));
  }

  // 교사용 칠판형 듣기 수업 모드 열기 버튼
  const btnOpenClassroom = document.getElementById("btnOpenListeningClassroomModal");
  if (btnOpenClassroom) {
    btnOpenClassroom.addEventListener("click", async () => {
      const items = getListeningCartItems();
      if (!items || items.length === 0) {
        alert("수업을 진행할 듣기 문항이 없습니다. 먼저 듣기 문항을 장바구니에 담아주세요.");
        return;
      }

      const origText = btnOpenClassroom.innerHTML;
      btnOpenClassroom.disabled = true;
      btnOpenClassroom.innerHTML = "<span>⏳ 수업 데이터 준비 중...</span>";

      try {
        const curProj = getCurrentListeningProject();
        const projectTitle = curProj ? curProj.title : "듣기 프로젝트";

        const res = await fetch("/api/handouts/listening/classroom-data", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            items,
            project_title: projectTitle
          })
        });

        if (!res.ok) {
          const errData = await res.json().catch(() => ({}));
          throw new Error(errData.detail || `서버 응답 오류 (${res.status})`);
        }

        const data = await res.json();
        await listeningClassroom.open(data);
      } catch (err) {
        console.error("Failed to load listening classroom data:", err);
        alert(`수업 모드 실행 실패: ${err.message}`);
      } finally {
        btnOpenClassroom.disabled = false;
        btnOpenClassroom.innerHTML = origText;
      }
    });
  }

  // 상단 3대 모드 선택기 탭 바 (독해 유인물 ↔ 문장 유인물 ↔ 듣기 유인물)
  const tabPassage = document.getElementById("tabHandoutPassage");
  const tabSentence = document.getElementById("tabHandoutSentence");
  const tabListening = document.getElementById("tabHandoutListening");

  const layoutPassage = document.getElementById("handoutPassageLayout");
  const layoutSentence = document.getElementById("handoutSentenceLayout");
  const layoutListening = document.getElementById("handoutListeningLayout");

  const barPassage = document.getElementById("handoutPassageProjectBar");
  const barSentence = document.getElementById("handoutSentenceProjectBar");
  const barListening = document.getElementById("handoutListeningProjectBar");

  const hdrIcon = document.getElementById("handoutHeaderIcon");
  const hdrTitle = document.getElementById("handoutMainPageTitle");
  const hdrSubtitle = document.getElementById("handoutMainSubtitle");

  if (tabListening) {
    tabListening.addEventListener("click", () => {
      tabListening.classList.add("active");
      if (tabPassage) tabPassage.classList.remove("active");
      if (tabSentence) tabSentence.classList.remove("active");

      if (hdrIcon) hdrIcon.textContent = "🎧";
      if (hdrTitle) hdrTitle.textContent = "교사용 듣기 유인물 제작소";
      if (hdrSubtitle) hdrSubtitle.textContent = "선택한 영어 듣기 문항으로 B4 세로 2x3 테이블 규격의 문제지·해설지 HWPX 및 통합 MP3를 자동 생성합니다.";

      if (barPassage) barPassage.style.display = "none";
      if (barSentence) barSentence.style.display = "none";
      if (barListening) barListening.style.display = "flex";

      if (layoutPassage) layoutPassage.style.display = "none";
      if (layoutSentence) layoutSentence.style.display = "none";
      if (layoutListening) layoutListening.style.display = "grid";

      syncAllProjectDropdowns();
      renderListeningHandoutView();
    });
  }

  // 외부 변경 이벤트 동기화
  window.addEventListener("handout-listening-cart-changed", () => {
    if (layoutListening && layoutListening.style.display !== "none") {
      renderListeningHandoutView();
    }
  });

  window.addEventListener("handout-listening-project-changed", () => {
    if (layoutListening && layoutListening.style.display !== "none") {
      renderListeningHandoutView();
    }
  });
}
