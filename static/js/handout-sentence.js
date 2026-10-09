/**
 * 05-gichul_db: 교사용 문장 유인물 제작소 전용 로직 (handout-sentence.js)
 * - A4 단면 문장 유인물 (default_a4_sentence.hwpx) 뷰 로직
 * - 선택된 문장 목록 렌더링, 문장 번호(1번부터/N번부터) 재부여 및 개별 번호 직접 수정
 * - 문장 전용 프로젝트 바 연동 및 순서 변경(위/아래), 개별 삭제, 전체 비우기
 * - 머리말(왼쪽/가운데/오른쪽) 및 유인물 메인 제목 자동 저장 & 복원
 * - 개념 설명 1x1 테이블 포함 여부(6문장 vs 10문장) 토글 및 상태 안내
 * - HWPX 문장 유인물 파일 다운로드 비동기 요청 및 저장 (해설 불필요 · 단일 문제지 전용)
 */

import {
  getSentenceCartItems,
  removeFromSentenceCart,
  reorderSentenceCart,
  clearSentenceCart,
  getCurrentSentenceProject,
  getSentenceProjectSettings,
  saveSentenceProjectSettings,
  setCustomSentenceNum,
  renumberSentenceCart,
  updateFloatingCartUI,
  syncAllProjectDropdowns,
  getCartItems,
} from "./handout-cart.js";
import { escapeHtml, showToast } from "./utils.js";

// 로컬스토리지 키
const KEY_SENTENCE_HEADER_LEFT = "gichul_sentence_header_left";
const KEY_SENTENCE_HEADER_CENTER = "gichul_sentence_header_center";
const KEY_SENTENCE_HEADER_RIGHT = "gichul_sentence_header_right";
const KEY_SENTENCE_MAIN_TITLE = "gichul_sentence_main_title";
const KEY_SENTENCE_INCLUDE_CONCEPT = "gichul_sentence_include_concept";

/** 문장 유인물 뷰 렌더링 */
export async function renderSentenceHandoutView() {
  const container = document.getElementById("handoutSentenceLayout");
  if (!container) return;

  const items = getSentenceCartItems();
  updateSentenceToolbarStats(items);

  // 헤더 및 배지 동기화
  const totalBadge = document.getElementById("handoutTotalCountBadge");
  if (totalBadge) {
    totalBadge.textContent = `${items.length}개 문장`;
  }
  const estPage = document.getElementById("handoutEstimatedPages");
  if (estPage) {
    const chkConcept = document.getElementById("chkSentenceIncludeConcept");
    const limit = (chkConcept && !chkConcept.checked) ? 10 : 6;
    const pages = Math.max(1, Math.ceil(items.length / limit));
    estPage.textContent = items.length > 0 ? `(예상 ${pages}페이지)` : "";
  }

  // 드롭다운 갱신
  syncAllProjectDropdowns();

  // 설정 폼 복원
  restoreSentenceFormSettings();

  if (items.length === 0) {
    renderSentenceEmptyState();
    return;
  }

  const listEl = document.getElementById("handoutSentenceItemsList");
  if (!listEl) return;

  listEl.innerHTML = `
    <div style="text-align: center; padding: 40px; color: #64748b;">
      <div class="loading-spinner" style="margin: 0 auto 12px;"></div>
      <p style="font-size: 0.9rem;">문장 메타데이터를 불러오는 중입니다...</p>
    </div>
  `;

  try {
    const res = await fetch("/api/handouts/sentence-preview-info", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ sentence_ids: items.map((it) => it.id) }),
    });

    if (!res.ok) throw new Error("문장 미리보기 정보 조회 실패");
    const data = await res.json();
    const fetchedSentences = data.items || [];

    // items 의 custom_num 매핑 결합
    const numMap = new Map();
    items.forEach((it, idx) => {
      numMap.set(it.id, it.custom_num ? String(it.custom_num) : String(idx + 1));
    });

    const sentences = fetchedSentences.map((s, idx) => ({
      ...s,
      custom_num: numMap.get(s.id) || String(idx + 1),
    }));

    renderSentenceCards(sentences);
  } catch (err) {
    console.error("문장 미리보기 로드 실패", err);
    listEl.innerHTML = `
      <div style="text-align: center; padding: 30px; color: #ef4444;">
        <p>문장 정보를 불러오지 못했습니다: ${escapeHtml(err.message)}</p>
      </div>
    `;
  }
}

/** 문장 툴바 통계 및 권장 문장 수 갱신 */
function updateSentenceToolbarStats(items) {
  const badge = document.getElementById("sentenceCountBadge");
  const chkConcept = document.getElementById("chkSentenceIncludeConcept");
  const isConceptIncluded = chkConcept ? chkConcept.checked : true;

  const targetLimit = isConceptIncluded ? 6 : 10;
  if (badge) {
    badge.textContent = `${items.length}개 선택됨`;
    badge.style.background = items.length === targetLimit ? "#dcfce7" : (items.length > targetLimit ? "#fef3c7" : "#e0e7ff");
    badge.style.color = items.length === targetLimit ? "#15803d" : (items.length > targetLimit ? "#b45309" : "#3730a3");
  }

  const notice = document.getElementById("sentenceGuidanceNotice");
  if (notice) {
    if (items.length === targetLimit) {
      notice.innerHTML = `✔ <strong>${targetLimit}문장 딱 맞춤</strong> (1페이지 완성 분량)`;
      notice.style.color = "#16a34a";
    } else if (items.length > targetLimit) {
      notice.innerHTML = `⚠️ 권장 ${targetLimit}문장을 초과했습니다 (${items.length}개 선택됨)`;
      notice.style.color = "#d97706";
    } else {
      notice.innerHTML = `권장: <strong>${targetLimit}문장</strong> (현재 ${items.length}/${targetLimit}개)`;
      notice.style.color = "#64748b";
    }
  }
}

/** 문장 목록이 비어있을 때 빈 화면 렌더링 */
function renderSentenceEmptyState() {
  const listEl = document.getElementById("handoutSentenceItemsList");
  if (!listEl) return;

  listEl.innerHTML = `
    <div style="text-align: center; padding: 60px 20px; background: #ffffff; border: 2px dashed #cbd5e1; border-radius: 12px; margin: 10px 0;">
      <span style="font-size: 2.5rem; display: block; margin-bottom: 12px;">📝</span>
      <h3 style="font-size: 1.1rem; font-weight: 700; color: #1e293b; margin-bottom: 8px;">보관함에 담긴 문장이 없습니다</h3>
      <p style="font-size: 0.88rem; color: #64748b; line-height: 1.5; margin-bottom: 20px;">
        상단 <strong>[문장]</strong> 검색 탭에서 원하는 기출 문장들을 검색한 후,<br>
        문장 옆 <code>[📄 유인물 담기]</code> 체크박스를 클릭하여 여기에 담아보세요!
      </p>
      <button type="button" class="btn btn-primary btn-sm" id="btnGoBackToSentenceSearch">
        🔍 문장 검색 화면으로 가기
      </button>
    </div>
  `;

  const btnGo = document.getElementById("btnGoBackToSentenceSearch");
  if (btnGo) {
    btnGo.addEventListener("click", () => {
      import("./navigation.js").then((m) => {
        if (typeof m.backFromHandoutView === "function") {
          m.backFromHandoutView();
        } else if (typeof m.showResultsScreen === "function") {
          m.showResultsScreen();
        }
      });
    });
  }
}

/** 문장 카드 목록 렌더링 */
function renderSentenceCards(sentences) {
  const listEl = document.getElementById("handoutSentenceItemsList");
  if (!listEl) return;

  const chkConcept = document.getElementById("chkSentenceIncludeConcept");
  const targetLimit = (chkConcept && !chkConcept.checked) ? 10 : 6;

  let html = "";
  sentences.forEach((s, idx) => {
    const isExceeded = idx >= targetLimit;
    const borderStyle = isExceeded ? "border-left: 4px solid #f59e0b;" : "border-left: 4px solid #3b82f6;";
    const customNum = s.custom_num || String(idx + 1);

    html += `
      <div class="sentence-card-item" data-id="${escapeHtml(s.id)}" data-index="${idx}" style="${borderStyle}">
        <div class="handout-item-header">
          <div class="handout-item-qnum-box">
            <span style="font-size: 0.85rem; font-weight: 700; color: #475569;">인쇄 번호:</span>
            <input type="text" class="handout-item-qnum-input input-sentence-custom-num" data-id="${escapeHtml(s.id)}" value="${escapeHtml(customNum)}" title="유인물에 실제로 인쇄될 문장 번호를 직접 입력하세요">
            <span style="font-size: 0.85rem; font-weight: 700; color: #1d4ed8;">번</span>
            <span class="handout-item-source-badge btn-goto-passage" data-id="${escapeHtml(s.passage_id || s.source_label || s.id)}" title="해당 지문 결과창으로 이동">[${escapeHtml(s.source_label || s.id)}]</span>
            ${isExceeded ? '<span style="font-size: 0.72rem; color: #b45309; background: #fef3c7; padding: 1px 6px; border-radius: 4px;">초과 문항</span>' : ''}
          </div>
          <div class="handout-item-controls">
            <button type="button" class="btn-card-move btn-sentence-move-up" data-index="${idx}" title="위로 이동" ${idx === 0 ? "disabled" : ""}>▲</button>
            <button type="button" class="btn-card-move btn-sentence-move-down" data-index="${idx}" title="아래로 이동" ${idx === sentences.length - 1 ? "disabled" : ""}>▼</button>
            <button type="button" class="btn-card-delete btn-sentence-delete" data-id="${escapeHtml(s.id)}" title="이 문장 삭제">✕</button>
          </div>
        </div>
        <div class="sentence-card-body">
          ${escapeHtml(s.sentence_text || "(문장 본문이 없습니다)")}
        </div>
      </div>
    `;
  });

  listEl.innerHTML = html;

  // 출처 클릭 시 해당 지문 결과창으로 즉시 이동
  listEl.querySelectorAll(".btn-goto-passage").forEach((badge) => {
    badge.addEventListener("click", () => {
      const pid = badge.dataset.id;
      if (pid) {
        import("./results-sentence.js").then((m) => {
          m.navigateToPassageView(pid);
        });
      }
    });
  });

  // 이벤트 바인딩: 위/아래 이동 및 삭제
  listEl.querySelectorAll(".btn-sentence-move-up").forEach((btn) => {
    btn.addEventListener("click", () => {
      const idx = parseInt(btn.dataset.index, 10);
      if (idx > 0) {
        reorderSentenceCart(idx, idx - 1);
        renderSentenceHandoutView();
      }
    });
  });

  listEl.querySelectorAll(".btn-sentence-move-down").forEach((btn) => {
    btn.addEventListener("click", () => {
      const idx = parseInt(btn.dataset.index, 10);
      const items = getSentenceCartItems();
      if (idx < items.length - 1) {
        reorderSentenceCart(idx, idx + 1);
        renderSentenceHandoutView();
      }
    });
  });

  listEl.querySelectorAll(".btn-sentence-delete").forEach((btn) => {
    btn.addEventListener("click", () => {
      const sid = btn.dataset.id;
      if (sid) {
        removeFromSentenceCart(sid);
        renderSentenceHandoutView();
      }
    });
  });

  // 이벤트 바인딩: 문장 번호 직접 수정
  listEl.querySelectorAll(".input-sentence-custom-num").forEach((input) => {
    input.addEventListener("input", (e) => {
      const sid = input.dataset.id;
      const val = e.target.value.trim();
      if (sid && val) {
        setCustomSentenceNum(sid, val);
      }
    });
  });
}

/** 문장 유인물 설정 폼 복원 */
function restoreSentenceFormSettings() {
  const curSettings = getSentenceProjectSettings();

  const inputLeft = document.getElementById("sentenceHeaderLeft");
  const inputCenter = document.getElementById("sentenceHeaderCenter");
  const inputRight = document.getElementById("sentenceHeaderRight");
  const inputTitle = document.getElementById("sentenceMainTitle");
  const chkConcept = document.getElementById("chkSentenceIncludeConcept");

  if (inputLeft) {
    inputLeft.value = curSettings.header_left ?? localStorage.getItem(KEY_SENTENCE_HEADER_LEFT) ?? "OO고등학교 영어과";
  }
  if (inputCenter) {
    inputCenter.value = curSettings.header_center ?? localStorage.getItem(KEY_SENTENCE_HEADER_CENTER) ?? "2026학년도 1학기 기말고사 대비 영어 기출";
  }
  if (inputRight) {
    inputRight.value = curSettings.header_right ?? localStorage.getItem(KEY_SENTENCE_HEADER_RIGHT) ?? "제 2 학년 (   )반 (   )번  이름: (        )";
  }
  if (inputTitle) {
    inputTitle.value = curSettings.main_title ?? localStorage.getItem(KEY_SENTENCE_MAIN_TITLE) ?? "핵심 기출 구문 분석 뽀개기";
  }
  if (chkConcept) {
    const savedConcept = curSettings.include_concept_table ?? (localStorage.getItem(KEY_SENTENCE_INCLUDE_CONCEPT) !== "false");
    chkConcept.checked = savedConcept;
    updateConceptNotice(savedConcept);
  }
}

/** 문장 유인물 설정 폼 저장 */
function saveSentenceFormSettings() {
  const inputLeft = document.getElementById("sentenceHeaderLeft");
  const inputCenter = document.getElementById("sentenceHeaderCenter");
  const inputRight = document.getElementById("sentenceHeaderRight");
  const inputTitle = document.getElementById("sentenceMainTitle");
  const chkConcept = document.getElementById("chkSentenceIncludeConcept");

  const sSettings = {
    header_left: inputLeft ? inputLeft.value.trim() : "",
    header_center: inputCenter ? inputCenter.value.trim() : "",
    header_right: inputRight ? inputRight.value.trim() : "",
    main_title: inputTitle ? inputTitle.value.trim() : "",
    include_concept_table: chkConcept ? chkConcept.checked : true,
  };

  localStorage.setItem(KEY_SENTENCE_HEADER_LEFT, sSettings.header_left);
  localStorage.setItem(KEY_SENTENCE_HEADER_CENTER, sSettings.header_center);
  localStorage.setItem(KEY_SENTENCE_HEADER_RIGHT, sSettings.header_right);
  localStorage.setItem(KEY_SENTENCE_MAIN_TITLE, sSettings.main_title);
  localStorage.setItem(KEY_SENTENCE_INCLUDE_CONCEPT, sSettings.include_concept_table ? "true" : "false");

  saveSentenceProjectSettings(null, sSettings);
}

/** 개념 설명 토글 안내 문구 갱신 */
function updateConceptNotice(includeConcept) {
  const noticeEl = document.getElementById("conceptTableNotice");
  if (noticeEl) {
    if (includeConcept) {
      noticeEl.style.background = "#f0fdf4";
      noticeEl.style.borderColor = "#bbf7d0";
      noticeEl.style.color = "#166534";
      noticeEl.innerHTML = `<strong>✔ 개념 설명 박스 사용 중</strong>: 상단 1x1 빈칸 필기 박스가 생성되며 <strong>총 6문장</strong>이 배치됩니다.`;
    } else {
      noticeEl.style.background = "#eff6ff";
      noticeEl.style.borderColor = "#bfdbfe";
      noticeEl.style.color = "#1e40af";
      noticeEl.innerHTML = `<strong>✔ 개념 설명 박스 제외</strong>: 예문 표가 상단까지 확장되며 <strong>총 10문장</strong>이 넉넉하게 배치됩니다.`;
    }
  }

  // 툴바 가이드라인 재계산
  const items = getSentenceCartItems();
  updateSentenceToolbarStats(items);
}

/** 문장 유인물 HWPX 다운로드 비동기 요청 (해설 불필요 · 단일 문제지 전용) */
export async function downloadSentenceHandout() {
  const items = getSentenceCartItems();
  if (items.length === 0) {
    showToast("유인물로 제작할 문장이 없습니다.", "warning");
    return;
  }

  saveSentenceFormSettings();

  const inputLeft = document.getElementById("sentenceHeaderLeft");
  const inputCenter = document.getElementById("sentenceHeaderCenter");
  const inputRight = document.getElementById("sentenceHeaderRight");
  const inputTitle = document.getElementById("sentenceMainTitle");
  const chkConcept = document.getElementById("chkSentenceIncludeConcept");
  const btnDownload = document.getElementById("btnDownloadSentenceHandout");

  // 문장별 인쇄 번호 맵 생성
  const customSentenceNums = {};
  items.forEach((it, idx) => {
    customSentenceNums[it.id] = String(it.custom_num || (idx + 1));
  });

  const payload = {
    sentence_ids: items.map((it) => it.id),
    custom_sentence_nums: customSentenceNums,
    include_concept_table: chkConcept ? chkConcept.checked : true,
    main_title: (inputTitle ? inputTitle.value.trim() : "") || "핵심 기출 구문 분석",
    header_left: inputLeft ? inputLeft.value.trim() : "",
    header_center: inputCenter ? inputCenter.value.trim() : "",
    header_right: inputRight ? inputRight.value.trim() : "",
  };

  const origBtnText = btnDownload ? btnDownload.innerHTML : "";
  if (btnDownload) {
    btnDownload.disabled = true;
    btnDownload.innerHTML = `<span>⏳ 문장 유인물 생성 중...</span>`;
  }

  try {
    const res = await fetch("/api/handouts/generate-sentence", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (!res.ok) {
      let errDetail = "문장 유인물 생성 실패";
      try {
        const errJson = await res.json();
        errDetail = errJson.detail || errDetail;
      } catch (e) {}
      throw new Error(errDetail);
    }

    // 파일 다운로드 트리거
    const blob = await res.blob();
    let filename = `문장유인물_A4_${items.length}문장.hwpx`;
    const disposition = res.headers.get("Content-Disposition");
    if (disposition) {
      const mUtf = disposition.match(/filename\*=UTF-8''([^;]+)/i);
      if (mUtf && mUtf[1]) {
        filename = decodeURIComponent(mUtf[1]);
      } else {
        const mAscii = disposition.match(/filename="?([^";]+)"?/i);
        if (mAscii && mAscii[1]) filename = mAscii[1];
      }
    }

    const url = window.URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    window.URL.revokeObjectURL(url);

    showToast(`📝 '${filename}' 유인물 다운로드 완료! (C드라이브 다운로드 폴더 저장)`, "success");
  } catch (err) {
    console.error("문장 유인물 다운로드 실패", err);
    showToast(`유인물 생성 오류: ${err.message}`, "error");
  } finally {
    if (btnDownload) {
      btnDownload.disabled = false;
      btnDownload.innerHTML = origBtnText;
    }
  }
}

/** 전체 이벤트 리스너 초기화 */
export function initSentenceHandoutEvents() {
  // 전체 비우기
  const btnClearAll = document.getElementById("btnSentenceClearAll");
  if (btnClearAll) {
    btnClearAll.addEventListener("click", () => {
      const items = getSentenceCartItems();
      if (items.length === 0) return;
      if (confirm(`현재 문장 프로젝트의 모든 문장(${items.length}개)을 비우시겠습니까?`)) {
        clearSentenceCart();
        renderSentenceHandoutView();
        showToast("문장 보관함이 비워졌습니다.", "info");
      }
    });
  }

  // 문장 번호 1번부터 순차 재부여
  const btnRenumber1 = document.getElementById("btnSentenceRenumber1");
  if (btnRenumber1) {
    btnRenumber1.addEventListener("click", () => {
      const items = getSentenceCartItems();
      if (items.length === 0) return;
      renumberSentenceCart(1);
      renderSentenceHandoutView();
      showToast("모든 문장 번호가 1번부터 순차 부여되었습니다.", "success");
    });
  }

  // 문장 번호 N번부터 부여
  const btnRenumberN = document.getElementById("btnSentenceRenumberN");
  const inputStartNum = document.getElementById("inputSentenceStartNum");
  if (btnRenumberN) {
    btnRenumberN.addEventListener("click", () => {
      const items = getSentenceCartItems();
      if (items.length === 0) return;
      const startVal = parseInt(inputStartNum ? inputStartNum.value : "1", 10) || 1;
      renumberSentenceCart(startVal);
      renderSentenceHandoutView();
      showToast(`문장 번호가 ${startVal}번부터 순차 부여되었습니다.`, "success");
    });
  }

  // 개념 설명 테이블 체크박스 변경
  const chkConcept = document.getElementById("chkSentenceIncludeConcept");
  if (chkConcept) {
    chkConcept.addEventListener("change", (e) => {
      updateConceptNotice(e.target.checked);
      saveSentenceFormSettings();
    });
  }

  // 폼 입력 필드 자동 저장
  ["sentenceHeaderLeft", "sentenceHeaderCenter", "sentenceHeaderRight", "sentenceMainTitle"].forEach((id) => {
    const el = document.getElementById(id);
    if (el) {
      el.addEventListener("input", saveSentenceFormSettings);
      el.addEventListener("change", saveSentenceFormSettings);
    }
  });

  // 다운로드 버튼
  const btnDownload = document.getElementById("btnDownloadSentenceHandout");
  if (btnDownload) {
    btnDownload.addEventListener("click", downloadSentenceHandout);
  }

  // 상단 모드 선택기 탭 전환 (지문 유인물 ↔ 문장 유인물)
  const tabPassage = document.getElementById("tabHandoutPassage");
  const tabSentence = document.getElementById("tabHandoutSentence");

  const layoutPassage = document.getElementById("handoutPassageLayout");
  const layoutSentence = document.getElementById("handoutSentenceLayout");

  const barPassage = document.getElementById("handoutPassageProjectBar");
  const barSentence = document.getElementById("handoutSentenceProjectBar");

  const hdrIcon = document.getElementById("handoutHeaderIcon");
  const hdrTitle = document.getElementById("handoutMainPageTitle");
  const hdrSubtitle = document.getElementById("handoutMainSubtitle");
  const btnBack = document.getElementById("btnHandoutBackToResults") || document.getElementById("btnHandoutBackToPrevious");
  const btnHome = document.getElementById("btnHandoutBackToHome");

  if (btnHome) {
    btnHome.addEventListener("click", () => {
      import("./navigation.js").then((m) => {
        if (typeof m.showHomeScreen === "function") {
          m.showHomeScreen();
        }
      });
    });
  }

  const tabListening = document.getElementById("tabHandoutListening");
  const layoutListening = document.getElementById("handoutListeningLayout");
  const barListening = document.getElementById("handoutListeningProjectBar");

  if (tabPassage && tabSentence) {
    tabPassage.addEventListener("click", () => {
      tabPassage.classList.add("active");
      tabSentence.classList.remove("active");
      if (tabListening) tabListening.classList.remove("active");

      if (hdrIcon) hdrIcon.textContent = "📄";
      if (hdrTitle) hdrTitle.textContent = "교사용 독해 유인물 제작소";
      if (hdrSubtitle) hdrSubtitle.textContent = "선택한 기출 문항으로 B4 가로 2문항 규격의 문제지 및 해설지 HWPX 문서를 자동 생성합니다.";
      if (btnBack) {
        btnBack.textContent = "🔙 이전 화면으로 돌아가기";
        btnBack.title = "유인물 제작소 진입 전 이전 화면으로 복귀";
      }

      if (barPassage) barPassage.style.display = "flex";
      if (barSentence) barSentence.style.display = "none";
      if (barListening) barListening.style.display = "none";

      if (layoutPassage) layoutPassage.style.display = "grid";
      if (layoutSentence) layoutSentence.style.display = "none";
      if (layoutListening) layoutListening.style.display = "none";

      syncAllProjectDropdowns();
      import("./handout-passage.js").then((m) => {
        if (m.renderHandoutView) m.renderHandoutView();
      });
    });

    tabSentence.addEventListener("click", () => {
      tabSentence.classList.add("active");
      tabPassage.classList.remove("active");
      if (tabListening) tabListening.classList.remove("active");

      if (hdrIcon) hdrIcon.textContent = "📝";
      if (hdrTitle) hdrTitle.textContent = "교사용 문장 유인물 제작소";
      if (hdrSubtitle) hdrSubtitle.textContent = "선택한 기출 문장으로 A4 세로 규격의 구문 분석 훈련용 HWPX 문서를 자동 생성합니다. (해설 유인물 불필요)";
      if (btnBack) {
        btnBack.textContent = "🔙 이전 화면으로 돌아가기";
        btnBack.title = "유인물 제작소 진입 전 이전 화면으로 복귀";
      }

      if (barPassage) barPassage.style.display = "none";
      if (barSentence) barSentence.style.display = "flex";
      if (barListening) barListening.style.display = "none";

      if (layoutPassage) layoutPassage.style.display = "none";
      if (layoutSentence) layoutSentence.style.display = "grid";
      if (layoutListening) layoutListening.style.display = "none";

      syncAllProjectDropdowns();
      renderSentenceHandoutView();
    });
  }

  // 카트 변경 리스너
  window.addEventListener("handout-sentence-cart-changed", () => {
    const container = document.getElementById("handoutViewContainer");
    if (container && container.style.display !== "none") {
      renderSentenceHandoutView();
    }
  });

  // 프로젝트 전환 리스너
  window.addEventListener("handout-sentence-project-changed", () => {
    const container = document.getElementById("handoutViewContainer");
    if (container && container.style.display !== "none") {
      renderSentenceHandoutView();
    }
  });
}
