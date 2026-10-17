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
  passage_text: "TXT 지문 본문 텍스트",
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

  // 1. 바로가기
  container.querySelectorAll(".btn-goto-report").forEach((btn) => {
    btn.addEventListener("click", () => {
      const targetType = btn.dataset.type;
      const targetId = btn.dataset.id;
      handleGotoReportTarget(targetType, targetId);
    });
  });

  // 2. 수동 완료 (삭제)
  container.querySelectorAll(".btn-resolve-report").forEach((btn) => {
    btn.addEventListener("click", () => {
      const reportId = btn.dataset.id;
      handleResolveReport(reportId);
    });
  });

  // 3. 인라인 퀵 에디터 토글
  container.querySelectorAll(".btn-quick-edit-report").forEach((btn) => {
    btn.addEventListener("click", () => {
      const reportId = btn.dataset.id;
      const editorPanel = document.getElementById(`reportInlineEditor-${reportId}`);
      if (!editorPanel) return;
      const isOpen = editorPanel.style.display !== "none";
      editorPanel.style.display = isOpen ? "none" : "flex";
      btn.textContent = isOpen ? "✏️ 빠른 수정" : "닫기 ✕";
    });
  });

  // 4. 인라인 취소
  container.querySelectorAll(".btn-editor-cancel").forEach((btn) => {
    btn.addEventListener("click", () => {
      const reportId = btn.dataset.id;
      const editorPanel = document.getElementById(`reportInlineEditor-${reportId}`);
      const toggleBtn = container.querySelector(`.btn-quick-edit-report[data-id="${reportId}"]`);
      if (editorPanel) editorPanel.style.display = "none";
      if (toggleBtn) toggleBtn.textContent = "✏️ 빠른 수정";
    });
  });

  // 5. 인라인 AI 교정 제안 버튼
  container.querySelectorAll(".inline-editor-ai-btn").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const reportId = btn.dataset.id;
      await handleSingleAiDiagnose(reportId, btn);
    });
  });

  // 6. 인라인 저장만 하기
  container.querySelectorAll(".btn-editor-save").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const reportId = btn.dataset.id;
      await handleInlineSave(reportId, false);
    });
  });

  // 7. 인라인 저장 및 오류 해결(삭제)
  container.querySelectorAll(".btn-editor-save-resolve").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const reportId = btn.dataset.id;
      await handleInlineSave(reportId, true);
    });
  });

  // 8. 지문 본문 <-> 해설 전환 탭 이벤트
  container.querySelectorAll(".btn-editor-tab").forEach((tabBtn) => {
    tabBtn.addEventListener("click", () => {
      const reportId = tabBtn.dataset.id;
      const targetField = tabBtn.dataset.targetField;
      const report = allFetchedReports.find((r) => String(r.id) === String(reportId));
      if (!report) return;

      const textarea = document.getElementById(`inlineEditTextarea-${reportId}`);
      const labelSpan = document.getElementById(`inlineEditorLabel-${reportId}`);
      if (!textarea) return;

      // 탭 스타일 전환
      const tabs = container.querySelectorAll(`.btn-editor-tab[data-id="${reportId}"]`);
      tabs.forEach((t) => {
        const isCurrent = t.dataset.targetField === targetField;
        t.style.background = isCurrent ? "#3b82f6" : "#ffffff";
        t.style.color = isCurrent ? "#ffffff" : "#475569";
      });

      if (targetField === "passage_text") {
        textarea.dataset.field = "passage_text";
        textarea.value = report.passage_text || "";
        if (labelSpan) labelSpan.textContent = "📝 지문 본문 수정";
      } else {
        textarea.dataset.field = "explanation_text";
        textarea.value = report.explanation_text || "";
        if (labelSpan) labelSpan.textContent = "💡 해설 텍스트 수정";
      }
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

  // 인라인 에디터 기본 필드 결정
  const hasPassageTextError = (r.error_types || []).includes("passage_text") || (r.comment || "").includes("문항 텍스트") || (r.comment || "").includes("본문") || (r.comment || "").includes("지문");
  const hasExplanationError = (r.error_types || []).includes("explanation") || (r.comment || "").includes("해설");
  const isAnswerError = (r.error_types || []).includes("answer") || (r.comment || "").includes("정답");
  const isTextError = hasPassageTextError || (r.error_types || []).includes("accuracy");

  // 문항인 경우 지문 본문 오류가 명시되었거나 우선되는 경우 본문 모드 적용
  const isPassageTextMode = isPassage && (hasPassageTextError || (!hasExplanationError && isTextError));

  const defaultText = isPassage
    ? (isPassageTextMode ? (r.passage_text || "") : (r.explanation_text || ""))
    : (r.sentence_text || "");

  const fieldLabel = isPassage
    ? (isPassageTextMode ? "📝 지문 본문 수정" : "💡 해설 텍스트 수정")
    : "📝 문장 텍스트 수정";

  const fieldKey = isPassage
    ? (isPassageTextMode ? "passage_text" : "explanation_text")
    : "sentence_text";

  // 정답 수정 라디오 (문항인 경우)
  const answerSectionHtml = (isPassage && isAnswerError) ? `
    <div class="inline-editor-answer-group">
      <span style="font-weight:700; color:#334155;">정답 선택:</span>
      ${[1, 2, 3, 4, 5].map(num => `
        <label>
          <input type="radio" name="inlineAnswer-${r.id}" value="${num}" ${String(r.answer_text).includes(String(num)) ? "checked" : ""}>
          ${["①", "②", "③", "④", "⑤"][num - 1]}
        </label>
      `).join("")}
    </div>
  ` : "";

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
          <button type="button" class="btn-quick-edit-report" data-id="${r.id}" title="모달 안에서 즉시 확인하고 직접 수정">
            ✏️ 빠른 수정
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

      <!-- 인라인 퀵 에디터 패널 (아코디언 형태) -->
      <div class="report-inline-editor" id="reportInlineEditor-${r.id}" style="display: none;">
        <div class="inline-editor-toolbar">
          <div class="inline-editor-title">
            <span id="inlineEditorLabel-${r.id}">${fieldLabel}</span>
            ${isPassage ? `
              <div class="inline-editor-tabs" style="display:inline-flex; gap:0.25rem; margin-left:0.5rem;">
                <button type="button" class="btn-editor-tab ${isPassageTextMode ? 'active' : ''}" data-id="${r.id}" data-target-field="passage_text" style="font-size:0.72rem; padding:0.15rem 0.45rem; border-radius:4px; border:1px solid #cbd5e1; background:${isPassageTextMode ? '#3b82f6' : '#ffffff'}; color:${isPassageTextMode ? '#ffffff' : '#475569'}; cursor:pointer; font-weight:600;">본문</button>
                <button type="button" class="btn-editor-tab ${!isPassageTextMode ? 'active' : ''}" data-id="${r.id}" data-target-field="explanation_text" style="font-size:0.72rem; padding:0.15rem 0.45rem; border-radius:4px; border:1px solid #cbd5e1; background:${!isPassageTextMode ? '#3b82f6' : '#ffffff'}; color:${!isPassageTextMode ? '#ffffff' : '#475569'}; cursor:pointer; font-weight:600;">해설</button>
              </div>
            ` : ""}
          </div>
          <button type="button" class="inline-editor-ai-btn" data-id="${r.id}" title="AI가 오류 내용을 분석하여 올바른 텍스트를 제안합니다">
            ✨ AI 자동 분리/교정 제안
          </button>
        </div>

        ${answerSectionHtml}

        <textarea class="inline-editor-textarea" id="inlineEditTextarea-${r.id}" data-field="${fieldKey}" placeholder="수정할 내용을 입력하세요...">${escapeHtml(defaultText)}</textarea>

        <div id="inlineEditorNotice-${r.id}" style="display:none; font-size:0.76rem; color:#6d28d9; padding: 0.2rem 0.4rem; background:#ede9fe; border-radius:4px;"></div>

        <div class="inline-editor-actions">
          <button type="button" class="btn-editor-cancel" data-id="${r.id}">취소</button>
          <button type="button" class="btn-editor-save" data-id="${r.id}" title="DB에 내용만 저장하고 신고는 유지">💾 저장만 하기</button>
          <button type="button" class="btn-editor-save-resolve" data-id="${r.id}" title="DB에 내용 저장 후 오류 신고를 완료 처리(삭제)">💾 저장 및 해결 완료</button>
        </div>
      </div>
    </div>
  `;
}

/**
 * 단일 신고 항목 AI 진단 호출
 */
async function handleSingleAiDiagnose(reportId, triggerBtn) {
  const originalText = triggerBtn ? triggerBtn.textContent : "";
  if (triggerBtn) {
    triggerBtn.disabled = true;
    triggerBtn.textContent = "⏳ 분석 중...";
  }

  try {
    const res = await fetch("/api/reports/batch-diagnose", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ report_ids: [parseInt(reportId, 10)] }),
    });
    const data = await res.json();
    if (!res.ok || !data.success) {
      throw new Error(data.detail || "AI 진단 요청 실패");
    }

    const diag = (data.diagnoses || [])[0];
    if (!diag) throw new Error("진단 결과가 없습니다.");

    const textarea = document.getElementById(`inlineEditTextarea-${reportId}`);
    const noticeEl = document.getElementById(`inlineEditorNotice-${reportId}`);

    if (textarea && diag.after_text) {
      textarea.value = diag.after_text;
      textarea.focus();
    }

    if (noticeEl) {
      if (diag.chained) {
        noticeEl.style.display = "block";
        noticeEl.textContent = `💡 AI 진단: ${diag.diagnosis} (다음 ${diag.chained.q_num}번 문항으로 이관할 텍스트가 감지되었습니다. 일괄 저장 시 함께 반영됩니다.)`;
      } else {
        noticeEl.style.display = "block";
        noticeEl.textContent = `💡 AI 제안: ${diag.diagnosis}`;
      }
    }

    showToast("AI 분석 교정안이 에디터에 채워졌습니다. 확인 후 저장해 주세요!", "success");
  } catch (err) {
    showToast(`AI 분석 실패: ${err.message}`, "error");
  } finally {
    if (triggerBtn) {
      triggerBtn.disabled = false;
      triggerBtn.textContent = originalText;
    }
  }
}

/**
 * 인라인 저장 및 완료 처리
 */
async function handleInlineSave(reportId, resolveReport = false) {
  const report = allFetchedReports.find((r) => String(r.id) === String(reportId));
  if (!report) {
    showToast("신고 정보를 찾을 수 없습니다.", "error");
    return;
  }

  const textarea = document.getElementById(`inlineEditTextarea-${reportId}`);
  if (!textarea) return;

  const newText = textarea.value.trim();
  const fieldKey = textarea.dataset.field; // explanation_text | passage_text | sentence_text
  const targetId = report.target_type === "passage" ? report.passage_id : report.sentence_id;
  const cleanId = (targetId || "").replace(/^\[|\]$/g, "");

  try {
    // 1. 본문/해설/문장 DB 갱신
    if (report.target_type === "passage") {
      let endpoint = `/api/passages/${encodeURIComponent(cleanId)}/explanation`;
      let bodyData = { explanation_text: newText };

      if (fieldKey === "passage_text") {
        endpoint = `/api/passages/${encodeURIComponent(cleanId)}/text`;
        bodyData = { passage_text: newText };
      }

      const res = await fetch(endpoint, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(bodyData),
      });
      const data = await res.json();
      if (!res.ok || !data.success) {
        throw new Error(data.detail || "데이터 갱신에 실패했습니다.");
      }

      // 정답 라디오가 선택되어 있으면 정답도 갱신
      const checkedAns = document.querySelector(`input[name="inlineAnswer-${reportId}"]:checked`);
      if (checkedAns) {
        await fetch(`/api/passages/${encodeURIComponent(cleanId)}/answer`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ answer: checkedAns.value }),
        });
      }
    } else {
      // 문장 갱신
      const res = await fetch(`/api/sentences/${encodeURIComponent(cleanId)}/text`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ sentence_text: newText }),
      });
      const data = await res.json();
      if (!res.ok || !data.success) {
        throw new Error(data.detail || "문장 갱신에 실패했습니다.");
      }
    }

    // 2. 오류 신고 완료(삭제) 처리
    if (resolveReport) {
      await fetch(`/api/reports/${reportId}`, { method: "DELETE" });
      showToast("내용이 DB에 저장되고 오류 신고가 해결 완료되었습니다!", "success");

      // UI 카드 애니메이션 후 제거
      const cardEl = document.getElementById(`reportItem-${reportId}`);
      if (cardEl) {
        cardEl.style.transition = "all 0.3s ease";
        cardEl.style.opacity = "0";
        cardEl.style.transform = "translateY(-10px)";
        setTimeout(() => {
          allFetchedReports = allFetchedReports.filter((r) => String(r.id) !== String(reportId));
          loadReportsList();
        }, 300);
      } else {
        loadReportsList();
      }
    } else {
      showToast("내용이 DB에 성공적으로 저장되었습니다.", "success");
      const editorPanel = document.getElementById(`reportInlineEditor-${reportId}`);
      if (editorPanel) editorPanel.style.display = "none";
    }

    updateHeaderReportBadge();
  } catch (err) {
    showToast(`저장 실패: ${err.message}`, "error");
  }
}

/**
 * 일괄 AI 진단 및 검토 패널 오픈
 */
async function handleBatchAiDiagnose() {
  const btn = document.getElementById("btnBatchAiDiagnose");
  const panel = document.getElementById("reportsBatchReviewPanel");
  if (!panel) return;

  const originalText = btn ? btn.textContent : "";
  if (btn) {
    btn.disabled = true;
    btn.textContent = "⏳ AI 일괄 분석 중...";
  }

  panel.style.display = "flex";
  panel.innerHTML = '<div class="text-center py-4 text-muted">접수된 모든 오류 신고 항목을 AI가 심층 분석하고 있습니다...</div>';

  try {
    const res = await fetch("/api/reports/batch-diagnose", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({}),
    });
    const data = await res.json();
    if (!res.ok || !data.success) {
      throw new Error(data.detail || "일괄 진단 요청에 실패했습니다.");
    }

    renderBatchReviewPanel(data.diagnoses || []);
  } catch (err) {
    panel.innerHTML = `<div class="text-center py-4 text-danger">AI 일괄 진단 오류: ${escapeHtml(err.message)}</div>`;
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.textContent = originalText;
    }
  }
}

/**
 * 일괄 AI 진단 결과 검토 패널 렌더링
 */
let currentDiagnosesList = [];
function renderBatchReviewPanel(diagnoses) {
  const panel = document.getElementById("reportsBatchReviewPanel");
  if (!panel) return;

  currentDiagnosesList = diagnoses;

  if (diagnoses.length === 0) {
    panel.innerHTML = `
      <div class="text-center py-3">
        <p>검토할 대기 중인 오류 신고가 없습니다.</p>
        <button type="button" class="btn btn-secondary btn-xs" id="btnCloseBatchReviewPanel">검토 패널 닫기</button>
      </div>
    `;
    const closeBtn = document.getElementById("btnCloseBatchReviewPanel");
    if (closeBtn) closeBtn.addEventListener("click", () => { panel.style.display = "none"; });
    return;
  }

  panel.innerHTML = `
    <div class="review-panel-header">
      <div class="review-panel-title">
        <span>📋 AI 일괄 진단 결과 검토 (총 ${diagnoses.length}건)</span>
      </div>
      <div class="review-panel-actions-top">
        <button type="button" class="btn btn-secondary btn-xs" id="btnCloseBatchReviewPanel">닫기 ✕</button>
      </div>
    </div>
    <p style="font-size:0.8rem; color:#64748b; margin:0;">
      AI가 제안한 Before/After 교정안입니다. After 텍스트창에서 직접 수정하실 수 있으며, 승인할 항목만 체크 후 일괄 적용하세요.
    </p>

    <div class="review-items-list">
      ${diagnoses.map((d, idx) => {
        const qNumStr = d.q_num ? `${d.q_num}번` : "";
        const targetTitle = `${d.grade || ""} ${d.year || ""} ${d.month ? d.month + "월" : ""} ${qNumStr}`.trim() || d.target_id;
        const chainedHtml = d.chained ? `
          <div class="review-chained-notice">
            <span>🔗 연계 작업: <strong>${d.chained.q_num}번 문항</strong>의 해설에도 분리된 텍스트가 자동 주입됩니다.</span>
          </div>
        ` : "";

        return `
          <div class="review-item-card" id="reviewCard-${idx}">
            <div class="review-item-header">
              <div class="review-item-title-box">
                <input type="checkbox" class="chk-review-item" data-index="${idx}" id="chkReviewItem-${idx}" checked>
                <label for="chkReviewItem-${idx}" style="cursor:pointer;">
                  <strong>${escapeHtml(targetTitle)}</strong>
                  <span style="font-size:0.75rem; color:#4338ca; font-weight:normal; margin-left:0.3rem;">[${escapeHtml(d.diagnosis || "교정안")}]</span>
                </label>
              </div>
              <span style="font-size:0.74rem; color:#64748b;">신고내용: ${escapeHtml(d.comment || "-")}</span>
            </div>

            <div class="review-item-diff-container">
              <div class="diff-col">
                <span class="diff-label diff-label-before">🔴 현재 DB (Before)</span>
                <div class="diff-box-before">${escapeHtml(d.before_text || "(비어 있음)")}</div>
              </div>
              <div class="diff-col">
                <span class="diff-label diff-label-after">🟢 AI 제안 (After - 직접 수정 가능)</span>
                <textarea class="diff-box-after-textarea" id="reviewAfterText-${idx}">${escapeHtml(d.after_text || "")}</textarea>
              </div>
            </div>
            ${chainedHtml}
          </div>
        `;
      }).join("")}
    </div>

    <div class="review-panel-footer">
      <div>
        <button type="button" class="btn btn-outline-secondary btn-xs" id="btnToggleAllReviewItems">전체 해제/선택</button>
      </div>
      <div style="display:flex; gap:0.5rem; align-items:center;">
        <button type="button" class="btn btn-secondary btn-sm" id="btnCancelBatchReview">취소</button>
        <button type="button" class="btn btn-success btn-sm" id="btnApplyBatchReview" style="font-weight:700;">
          💾 선택한 항목 일괄 승인 및 DB 적용
        </button>
      </div>
    </div>
  `;

  // 이벤트 바인딩
  const closeBtn = document.getElementById("btnCloseBatchReviewPanel");
  const cancelBtn = document.getElementById("btnCancelBatchReview");
  if (closeBtn) closeBtn.addEventListener("click", () => { panel.style.display = "none"; });
  if (cancelBtn) cancelBtn.addEventListener("click", () => { panel.style.display = "none"; });

  // 전체 선택/해제 토글
  const toggleBtn = document.getElementById("btnToggleAllReviewItems");
  if (toggleBtn) {
    let allChecked = true;
    toggleBtn.addEventListener("click", () => {
      allChecked = !allChecked;
      panel.querySelectorAll(".chk-review-item").forEach((chk) => {
        chk.checked = allChecked;
      });
      toggleBtn.textContent = allChecked ? "전체 해제" : "전체 선택";
    });
  }

  // 일괄 적용 실행
  const applyBtn = document.getElementById("btnApplyBatchReview");
  if (applyBtn) {
    applyBtn.addEventListener("click", handleApplyBatchReview);
  }
}

/**
 * 검토된 항목 일괄 승인 적용 처리
 */
async function handleApplyBatchReview() {
  const panel = document.getElementById("reportsBatchReviewPanel");
  const checkedBoxes = panel.querySelectorAll(".chk-review-item:checked");

  if (checkedBoxes.length === 0) {
    showToast("적용할 항목을 최소 1개 이상 선택해 주세요.", "warning");
    return;
  }

  const itemsToApply = [];
  checkedBoxes.forEach((chk) => {
    const idx = parseInt(chk.dataset.index, 10);
    const d = currentDiagnosesList[idx];
    if (!d) return;

    const afterTextarea = document.getElementById(`reviewAfterText-${idx}`);
    const finalText = afterTextarea ? afterTextarea.value.trim() : d.after_text;

    const fixItem = {
      report_id: d.report_id,
      target_type: d.target_type,
      passage_id: d.target_type === "passage" ? d.target_id : null,
      sentence_id: d.target_type === "sentence" ? d.target_id : null,
    };

    if (d.field_name === "explanation_text") {
      fixItem.explanation_text = finalText;
    } else if (d.field_name === "passage_text") {
      fixItem.passage_text = finalText;
    } else if (d.field_name === "sentence_text") {
      fixItem.sentence_text = finalText;
    }

    if (d.chained) {
      fixItem.chained_passage_id = d.chained.passage_id;
      fixItem.chained_explanation_text = d.chained.after_text;
      fixItem.chained_report_id = d.chained.report_id;
    }

    itemsToApply.push(fixItem);
  });

  const applyBtn = document.getElementById("btnApplyBatchReview");
  if (applyBtn) {
    applyBtn.disabled = true;
    applyBtn.textContent = "⏳ DB 적용 중...";
  }

  try {
    const res = await fetch("/api/reports/batch-apply", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ items: itemsToApply }),
    });
    const data = await res.json();
    if (!res.ok || !data.success) {
      throw new Error(data.detail || "일괄 적용에 실패했습니다.");
    }

    showToast(data.message || "선택한 항목들이 성공적으로 DB에 적용되고 해결되었습니다!", "success");
    panel.style.display = "none";
    loadReportsList();
    updateHeaderReportBadge();
  } catch (err) {
    showToast(`일괄 적용 실패: ${err.message}`, "error");
  } finally {
    if (applyBtn) {
      applyBtn.disabled = false;
      applyBtn.textContent = "💾 선택한 항목 일괄 승인 및 DB 적용";
    }
  }
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

  // 3. 일괄 AI 분석 버튼
  const btnBatchAi = document.getElementById("btnBatchAiDiagnose");
  if (btnBatchAi) {
    btnBatchAi.addEventListener("click", handleBatchAiDiagnose);
  }

  // 4. 오류 목록 탭 필터 버튼들
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

  // 5. 지문 오류 신고 모달 닫기 및 제출
  const btnClosePassage = document.getElementById("btnCloseReportPassageModal");
  const btnCancelPassage = document.getElementById("btnCancelReportPassage");
  const btnSubmitPassage = document.getElementById("btnSubmitReportPassage");
  if (btnClosePassage) btnClosePassage.addEventListener("click", closePassageReportModal);
  if (btnCancelPassage) btnCancelPassage.addEventListener("click", closePassageReportModal);
  if (btnSubmitPassage) btnSubmitPassage.addEventListener("click", submitPassageReport);

  // 6. 문장 오류 신고 모달 닫기 및 제출
  const btnCloseSentence = document.getElementById("btnCloseReportSentenceModal");
  const btnCancelSentence = document.getElementById("btnCancelReportSentence");
  const btnSubmitSentence = document.getElementById("btnSubmitReportSentence");
  if (btnCloseSentence) btnCloseSentence.addEventListener("click", closeSentenceReportModal);
  if (btnCancelSentence) btnCancelSentence.addEventListener("click", closeSentenceReportModal);
  if (btnSubmitSentence) btnSubmitSentence.addEventListener("click", submitSentenceReport);

  // 초기 헤더 배지 로드
  updateHeaderReportBadge();
}

