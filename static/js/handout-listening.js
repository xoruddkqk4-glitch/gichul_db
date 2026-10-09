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
            <div class="listening-card-left">
              <span style="font-size: 0.8rem; font-weight: 700; color: #6d28d9;">출제 번호:</span>
              <input type="number" class="input-listening-custom-num" data-id="${escapeHtml(item.id)}" value="${escapeHtml(qNumVal)}" min="1" max="999" title="인쇄용 문항 번호 직접 수정">
              <span class="listening-card-source">${escapeHtml(item.id)}</span>
              ${pInfo.question_type ? `<span style="font-size: 0.76rem; background: #e0e7ff; color: #3730a3; padding: 2px 6px; border-radius: 4px;">${escapeHtml(pInfo.question_type)}</span>` : ""}
            </div>
            <div class="listening-card-actions">
              ${audioUrl ? `
                <button type="button" class="btn-card-audio" data-url="${escapeHtml(audioUrl)}" title="문항 음성 미리듣기">
                  ▶ 재생
                </button>
              ` : `
                <span style="font-size: 0.74rem; color: #94a3b8; padding: 2px 4px;">(음성 미생성)</span>
              `}
              <button type="button" class="btn-card-order btn-order-up" data-idx="${globalIdx}" title="위로 이동" ${globalIdx === 0 ? "disabled" : ""}>▲</button>
              <button type="button" class="btn-card-order btn-order-down" data-idx="${globalIdx}" title="아래로 이동" ${globalIdx === items.length - 1 ? "disabled" : ""}>▼</button>
              <button type="button" class="btn-card-delete" data-id="${escapeHtml(item.id)}" title="유인물에서 제외">✕ 삭제</button>
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

/** 전체 통합 MP3 오디오 다운로드 실행 */
async function downloadMergedAudio() {
  const items = getListeningCartItems();
  if (items.length === 0) {
    alert("통합 MP3로 다운로드할 듣기 문항이 없습니다. 문항을 먼저 추가해 주세요.");
    return;
  }

  const curProj = getCurrentListeningProject();
  const btnAudio = document.getElementById("btnDownloadListeningMergedAudio");
  const origHtml = btnAudio ? btnAudio.innerHTML : "";
  if (btnAudio) {
    btnAudio.disabled = true;
    btnAudio.innerHTML = `<span>⏳ 음성 결합 및 MP3 인코딩 중...</span>`;
  }

  try {
    const res = await fetch("/api/handouts/listening/download-audio", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        passage_ids: items.map((it) => it.id),
        project_name: curProj.name || "듣기유인물",
      }),
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || "오디오 결합에 실패했습니다.");
    }

    const blob = await res.blob();
    let filename = `${curProj.name || "듣기유인물"}_전체통합듣기.mp3`;
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
    alert(`통합 MP3 다운로드 실패: ${err.message}`);
  } finally {
    if (btnAudio) {
      btnAudio.disabled = false;
      btnAudio.innerHTML = origHtml;
    }
  }
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
    btnDlMergedAudio.addEventListener("click", downloadMergedAudio);
  }

  const btnDlZip = document.getElementById("btnDownloadListeningZip");
  if (btnDlZip) {
    btnDlZip.addEventListener("click", () => downloadListeningHandout("zip"));
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
