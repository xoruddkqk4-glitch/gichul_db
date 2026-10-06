/**
 * 05-gichul_db: 문항 및 문장 오류 신고 및 관리 시스템 (reports.js)
 */

import { showToast, escapeHtml } from "./utils.js";
import { setMode } from "./navigation.js";
import { mainSearchInput } from "./dom.js";
import { executeSearch } from "./search.js";

// 오류 유형 영문 -> 한국어 라벨 매핑
const ERROR_TYPE_LABELS = {
  pdf_capture: "PDF 캡처 오류",
  explanation: "해설지 오류",
  answer: "정답 오류",
  accuracy: "정답률 오류",
  other: "기타 오류",
};

let allFetchedReports = [];
let currentReportsFilter = "all";

/**
 * 헤더 우측 상단 미처리 오류 건수 배지 갱신
 */
export async function updateHeaderReportBadge() {
  const badge = document.getElementById("headerReportCountBadge");
  if (!badge) return;

  try {
    const res = await fetch("/api/reports/count");
    if (!res.ok) return;
    const data = await res.json();
    const count = data.count || 0;

    if (count > 0) {
      badge.textContent = count > 99 ? "99+" : String(count);
      badge.style.display = "inline-flex";
    } else {
      badge.style.display = "none";
    }
  } catch (err) {
    console.debug("오류 건수 조회 실패:", err);
  }
}

/**
 * 지문(문항) 오류 신고 모달 열기
 * @param {Object} passage - 현재 보고 있는 지문 객체
 */
export function openPassageReportModal(passage) {
  if (!passage) {
    showToast("신고할 문항 정보를 찾을 수 없습니다.", "error");
    return;
  }

  const modal = document.getElementById("modalReportPassage");
  const titleEl = document.getElementById("reportPassageTargetTitle");
  const pIdInput = document.getElementById("reportPassageId");
  const eIdInput = document.getElementById("reportPassageExamId");
  const commentInput = document.getElementById("inputReportPassageComment");

  const cleanId = (passage.id || "").replace(/^\[|\]$/g, "");
  const qNum = passage.q_num ? `${passage.q_num}번` : "";
  const areaLabel = passage.area === "listening" ? "듣기" : "독해";

  if (titleEl) {
    titleEl.textContent = `[${cleanId}] (${areaLabel} ${qNum})`;
  }
  if (pIdInput) pIdInput.value = cleanId;
  if (eIdInput) eIdInput.value = passage.exam_id || "";
  if (commentInput) commentInput.value = "";

  // 체크박스 초기화
  modal.querySelectorAll('input[name="passageErrorType"]').forEach((chk) => {
    chk.checked = false;
  });

  modal.style.display = "flex";
}

/**
 * 지문 오류 신고 모달 닫기
 */
export function closePassageReportModal() {
  const modal = document.getElementById("modalReportPassage");
  if (modal) modal.style.display = "none";
}

/**
 * 지문 오류 신고 제출
 */
async function submitPassageReport() {
  const modal = document.getElementById("modalReportPassage");
  const pIdInput = document.getElementById("reportPassageId");
  const eIdInput = document.getElementById("reportPassageExamId");
  const commentInput = document.getElementById("inputReportPassageComment");
  const submitBtn = document.getElementById("btnSubmitReportPassage");

  const selectedTypes = [];
  modal.querySelectorAll('input[name="passageErrorType"]:checked').forEach((chk) => {
    selectedTypes.push(chk.value);
  });

  const comment = (commentInput ? commentInput.value : "").trim();

  if (selectedTypes.length === 0) {
    showToast("최소 1개 이상의 오류 유형을 선택해 주세요.", "warning");
    return;
  }

  if (selectedTypes.includes("other") && !comment) {
    showToast("기타 오류를 선택하신 경우 상세 내용을 입력해 주세요.", "warning");
    if (commentInput) commentInput.focus();
    return;
  }

  const payload = {
    target_type: "passage",
    passage_id: pIdInput ? pIdInput.value : "",
    exam_id: eIdInput ? eIdInput.value : "",
    error_types: selectedTypes,
    comment: comment,
  };

  try {
    if (submitBtn) submitBtn.disabled = true;
    const res = await fetch("/api/reports", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    const data = await res.json();
    if (!res.ok || !data.success) {
      throw new Error(data.detail || "오류 신고 등록에 실패했습니다.");
    }

    showToast("오류 신고가 성공적으로 접수되었습니다. 검토 후 신속히 반영하겠습니다!", "success");
    closePassageReportModal();
    updateHeaderReportBadge();
  } catch (err) {
    showToast(`신고 접수 실패: ${err.message}`, "error");
  } finally {
    if (submitBtn) submitBtn.disabled = false;
  }
}

/**
 * 문장 오류 신고 모달 열기
 * @param {string} sentenceId - 문장 식별자
 * @param {string} sentenceText - 문장 텍스트
 */
export function openSentenceReportModal(sentenceId, sentenceText) {
  if (!sentenceId) {
    showToast("신고할 문장 정보를 찾을 수 없습니다.", "error");
    return;
  }

  const modal = document.getElementById("modalReportSentence");
  const titleEl = document.getElementById("reportSentenceTargetTitle");
  const previewEl = document.getElementById("reportSentencePreviewText");
  const sIdInput = document.getElementById("reportSentenceId");
  const commentInput = document.getElementById("inputReportSentenceComment");

  const cleanId = (sentenceId || "").replace(/^\[|\]$/g, "");

  if (titleEl) titleEl.textContent = `[${cleanId}] 문장`;
  if (previewEl) previewEl.textContent = sentenceText || "(문장 텍스트 없음)";
  if (sIdInput) sIdInput.value = cleanId;
  if (commentInput) commentInput.value = "";

  modal.style.display = "flex";
  if (commentInput) commentInput.focus();
}

/**
 * 문장 오류 신고 모달 닫기
 */
export function closeSentenceReportModal() {
  const modal = document.getElementById("modalReportSentence");
  if (modal) modal.style.display = "none";
}

/**
 * 문장 오류 신고 제출
 */
async function submitSentenceReport() {
  const sIdInput = document.getElementById("reportSentenceId");
  const commentInput = document.getElementById("inputReportSentenceComment");
  const submitBtn = document.getElementById("btnSubmitReportSentence");

  const comment = (commentInput ? commentInput.value : "").trim();
  if (!comment) {
    showToast("오류 내용을 자세히 입력해 주세요.", "warning");
    if (commentInput) commentInput.focus();
    return;
  }

  const payload = {
    target_type: "sentence",
    sentence_id: sIdInput ? sIdInput.value : "",
    error_types: ["sentence_content"],
    comment: comment,
  };

  try {
    if (submitBtn) submitBtn.disabled = true;
    const res = await fetch("/api/reports", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    const data = await res.json();
    if (!res.ok || !data.success) {
      throw new Error(data.detail || "문장 오류 신고 등록에 실패했습니다.");
    }

    showToast("문장 오류 신고가 성공적으로 접수되었습니다. 검토 후 신속히 수정하겠습니다!", "success");
    closeSentenceReportModal();
    updateHeaderReportBadge();
  } catch (err) {
    showToast(`신고 접수 실패: ${err.message}`, "error");
  } finally {
    if (submitBtn) submitBtn.disabled = false;
  }
}

/**
 * 오류 신고 목록 통합 모달 열기
 */
export function openReportsListModal() {
  const modal = document.getElementById("modalReportsList");
  if (modal) modal.style.display = "flex";
  loadReportsList();
}

/**
 * 오류 신고 목록 통합 모달 닫기
 */
export function closeReportsListModal() {
  const modal = document.getElementById("modalReportsList");
  if (modal) modal.style.display = "none";
}

/**
 * 오류 신고 목록 로드 및 렌더링
 */
export async function loadReportsList() {
  const container = document.getElementById("reportsItemsContainer");
  const statusText = document.getElementById("reportsListStatusText");
  const countTabAll = document.getElementById("countTabAll");
  const countTabPassage = document.getElementById("countTabPassage");
  const countTabSentence = document.getElementById("countTabSentence");

  if (container) {
    container.innerHTML = '<div class="text-center py-4 text-muted">오류 신고 내역을 불러오는 중입니다...</div>';
  }

  try {
    const res = await fetch("/api/reports?target_type=all&status=pending");
    if (!res.ok) throw new Error("신고 내역을 불러오지 못했습니다.");
    const data = await res.json();
    allFetchedReports = data.reports || [];

    // 카운트 집계
    const totalCount = allFetchedReports.length;
    const passageCount = allFetchedReports.filter((r) => r.target_type === "passage").length;
    const sentenceCount = allFetchedReports.filter((r) => r.target_type === "sentence").length;

    if (countTabAll) countTabAll.textContent = String(totalCount);
    if (countTabPassage) countTabPassage.textContent = String(passageCount);
    if (countTabSentence) countTabSentence.textContent = String(sentenceCount);
    if (statusText) statusText.textContent = `현재 총 ${totalCount}건의 미해결 오류가 접수되어 있습니다.`;

    renderFilteredReports();
    updateHeaderReportBadge();
  } catch (err) {
    if (container) {
      container.innerHTML = `<div class="text-center py-4 text-danger">신고 내역 로드 오류: ${escapeHtml(err.message)}</div>`;
    }
  }
}

/**
 * 현재 선택된 탭 필터에 맞춰 목록 렌더링
 */
function renderFilteredReports() {
  const container = document.getElementById("reportsItemsContainer");
  if (!container) return;

  let filtered = allFetchedReports;
  if (currentReportsFilter === "passage") {
    filtered = allFetchedReports.filter((r) => r.target_type === "passage");
  } else if (currentReportsFilter === "sentence") {
    filtered = allFetchedReports.filter((r) => r.target_type === "sentence");
  }

  if (filtered.length === 0) {
    container.innerHTML = `
      <div class="report-empty-state">
        <div class="report-empty-icon">🎉</div>
        <div class="report-empty-title">신고된 오류가 없습니다!</div>
        <div class="report-empty-subtitle">모든 기출 문항과 문장이 정상 상태입니다.</div>
      </div>
    `;
    return;
  }

  container.innerHTML = filtered.map((r) => renderReportCard(r)).join("");

  // 이벤트 바인딩: 바로가기 & 수정완료(삭제)
  container.querySelectorAll(".btn-goto-report").forEach((btn) => {
    btn.addEventListener("click", () => {
      const targetType = btn.dataset.type;
      const targetId = btn.dataset.id;
      handleGotoReportTarget(targetType, targetId);
    });
  });

  container.querySelectorAll(".btn-resolve-report").forEach((btn) => {
    btn.addEventListener("click", () => {
      const reportId = btn.dataset.id;
      handleResolveReport(reportId);
    });
  });
}

/**
 * 단일 신고 항목 카드 렌더링
 */
function renderReportCard(r) {
  const isPassage = r.target_type === "passage";
  const badgeClass = isPassage ? "badge-passage" : "badge-sentence";
  const badgeText = isPassage ? "📘 문항" : "📝 문장";

  // 제목/출처 구성
  let targetDisplay = "";
  if (isPassage) {
    const gradeStr = r.grade || "";
    const yearStr = r.year ? `${r.year}년` : "";
    const monthStr = r.month ? `${String(r.month).padStart(2, "0")}월` : "";
    const qNumStr = r.q_num ? `${r.q_num}번` : "";
    const qTypeStr = r.question_type ? `[${r.question_type}]` : "";
    targetDisplay = `${gradeStr} ${yearStr} ${monthStr} ${qNumStr} ${qTypeStr}`.trim() || r.passage_id;
  } else {
    targetDisplay = r.sentence_id || "문장";
  }

  // 오류 유형 태그 알약(Pills)
  const typePills = (r.error_types || [])
    .map((t) => `<span class="report-type-pill">${escapeHtml(ERROR_TYPE_LABELS[t] || t)}</span>`)
    .join(" ");

  // 문장 미리보기 (문장 신고 시)
  const sentenceQuoteHtml = r.sentence_text
    ? `<div class="report-item-sentence-quote">"${escapeHtml(r.sentence_text)}"</div>`
    : "";

  const createdTime = r.created_at ? r.created_at.slice(0, 16).replace("T", " ") : "";
  const targetId = isPassage ? r.passage_id : r.sentence_id;

  return `
    <div class="report-item-card" id="reportItem-${r.id}">
      <div class="report-item-header">
        <div class="report-item-meta">
          <span class="report-target-badge ${badgeClass}">${badgeText}</span>
          <span class="report-target-title">${escapeHtml(targetDisplay)}</span>
          ${typePills}
        </div>
        <div class="report-item-actions">
          <button type="button" class="btn-goto-report" data-type="${r.target_type}" data-id="${escapeHtml(targetId)}" title="이 문항/문장 결과 화면으로 즉시 이동">
            바로가기 ↗
          </button>
          <button type="button" class="btn-resolve-report" data-id="${r.id}" title="오류 수정 완료 처리 및 목록에서 영구 삭제">
            ✅ 수정 완료 (삭제)
          </button>
        </div>
      </div>
      ${sentenceQuoteHtml}
      <div class="report-item-body">${escapeHtml(r.comment || "(상세 코멘트 없음)")}</div>
      <div class="report-item-footer">
        <span>신고 일시: ${escapeHtml(createdTime)}</span>
      </div>
    </div>
  `;
}

/**
 * 바로가기 클릭 시 해당 문항/문장으로 이동
 */
function handleGotoReportTarget(targetType, targetId) {
  if (!targetId) {
    showToast("대상 식별자가 유효하지 않습니다.", "warning");
    return;
  }

  closeReportsListModal();

  if (targetType === "passage") {
    setMode("passage");
  } else {
    setMode("sentence");
  }

  if (mainSearchInput) {
    mainSearchInput.value = targetId.startsWith("[") && targetId.endsWith("]") ? targetId : `[${targetId}]`;
  }

  executeSearch();
  showToast(`[${targetId}] 화면으로 이동했습니다.`, "info");
}

/**
 * 오류 신고 수정 완료 (삭제)
 */
async function handleResolveReport(reportId) {
  if (!confirm("이 오류를 수정한 것으로 처리하고 목록에서 삭제하시겠습니까?")) {
    return;
  }

  try {
    const res = await fetch(`/api/reports/${reportId}`, {
      method: "DELETE",
    });
    const data = await res.json();
    if (!res.ok || !data.success) {
      throw new Error(data.detail || "삭제 처리에 실패했습니다.");
    }

    showToast("오류 신고 항목이 삭제(수정 완료)되었습니다.", "success");

    // 로컬 목록에서 제거 및 실시간 재렌더링
    allFetchedReports = allFetchedReports.filter((r) => String(r.id) !== String(reportId));
    loadReportsList();
  } catch (err) {
    showToast(`삭제 실패: ${err.message}`, "error");
  }
}

/**
 * 보고서 모듈 초기화 및 이벤트 리스너 바인딩
 */
export function initReports() {
  // 1. 헤더 우측 상단 '오류 신고 내역' 버튼
  const btnOpenReports = document.getElementById("btnOpenReportsModal");
  if (btnOpenReports) {
    btnOpenReports.addEventListener("click", openReportsListModal);
  }

  // 2. 오류 목록 모달 닫기 및 새로고침
  const btnCloseList = document.getElementById("btnCloseReportsListModal");
  const btnCloseListFooter = document.getElementById("btnCloseReportsListFooter");
  const btnRefreshList = document.getElementById("btnRefreshReportsList");
  if (btnCloseList) btnCloseList.addEventListener("click", closeReportsListModal);
  if (btnCloseListFooter) btnCloseListFooter.addEventListener("click", closeReportsListModal);
  if (btnRefreshList) btnRefreshList.addEventListener("click", loadReportsList);

  // 3. 오류 목록 탭 필터 버튼들
  const tabFilterBtns = [
    document.getElementById("tabFilterAllReports"),
    document.getElementById("tabFilterPassageReports"),
    document.getElementById("tabFilterSentenceReports"),
  ];

  tabFilterBtns.forEach((btn) => {
    if (!btn) return;
    btn.addEventListener("click", () => {
      tabFilterBtns.forEach((b) => b && b.classList.remove("active"));
      btn.classList.add("active");
      currentReportsFilter = btn.dataset.filter || "all";
      renderFilteredReports();
    });
  });

  // 4. 지문 오류 신고 모달 닫기 및 제출
  const btnClosePassage = document.getElementById("btnCloseReportPassageModal");
  const btnCancelPassage = document.getElementById("btnCancelReportPassage");
  const btnSubmitPassage = document.getElementById("btnSubmitReportPassage");
  if (btnClosePassage) btnClosePassage.addEventListener("click", closePassageReportModal);
  if (btnCancelPassage) btnCancelPassage.addEventListener("click", closePassageReportModal);
  if (btnSubmitPassage) btnSubmitPassage.addEventListener("click", submitPassageReport);

  // 5. 문장 오류 신고 모달 닫기 및 제출
  const btnCloseSentence = document.getElementById("btnCloseReportSentenceModal");
  const btnCancelSentence = document.getElementById("btnCancelReportSentence");
  const btnSubmitSentence = document.getElementById("btnSubmitReportSentence");
  if (btnCloseSentence) btnCloseSentence.addEventListener("click", closeSentenceReportModal);
  if (btnCancelSentence) btnCancelSentence.addEventListener("click", closeSentenceReportModal);
  if (btnSubmitSentence) btnSubmitSentence.addEventListener("click", submitSentenceReport);

  // 초기 헤더 배지 로드
  updateHeaderReportBadge();
}
