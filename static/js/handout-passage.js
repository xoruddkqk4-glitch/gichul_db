/**
 * 05-gichul_db: 교사용 지문 유인물 제작소 화면 로직 (handout-passage.js)
 * - 선택된 문항 목록 렌더링, 순서 변경, 사용자 지정 문항 번호 수정
 * - 머리말/꼬리말 localStorage 자동 저장 및 바인딩
 * - HWPX 템플릿 목록 조회 및 커스텀 양식 업로드
 * - 문제지 / 해설지 / ZIP 다운로드 API 연동
 */

import {
  getCartItems,
  removeFromCart,
  reorderCart,
  setCustomQNum,
  renumberCart,
  clearCart,
  updateFloatingCartUI,
} from "./handout-cart.js";

// 로컬스토리지 키
const KEY_HEADER_TITLE = "gichul_handout_header_title";
const KEY_HEADER_SUB = "gichul_handout_header_sub";
const KEY_FOOTER_TEXT = "gichul_handout_footer_text";
const KEY_HIGHLIGHT_ANSWER = "gichul_handout_highlight_answer";
const KEY_SELECTED_TEMPLATE = "gichul_handout_template";

/** escapeHtml 헬퍼 */
function escapeHtml(str) {
  if (!str) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

/** 유인물 제작소 화면 초기화 및 렌더링 */
export async function renderHandoutView() {
  const container = document.getElementById("handoutViewContainer");
  if (!container) return;

  const items = getCartItems();
  updateToolbarStats(items);

  // 설정값 폼 복원
  restoreFormSettings();

  // 템플릿 목록 로드
  await loadTemplateList();

  if (items.length === 0) {
    renderEmptyState();
    return;
  }

  // 문항 세부 정보 가져오기
  try {
    const res = await fetch("/api/handouts/preview-info", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ passage_ids: items.map((i) => i.id) }),
    });
    if (!res.ok) throw new Error("문항 정보 조회 실패");
    const data = await res.json();
    renderItemList(items, data.items || []);
  } catch (err) {
    console.error("Failed to load handout preview info", err);
    renderItemList(items, []);
  }
}

/** 툴바 통계(문항 수, 예상 페이지) 갱신 */
function updateToolbarStats(items) {
  const countEl = document.getElementById("handoutTotalCountBadge");
  const pagesEl = document.getElementById("handoutEstimatedPages");
  const btnQuestion = document.getElementById("btnDownloadQuestion");
  const btnExplanation = document.getElementById("btnDownloadExplanation");
  const btnZip = document.getElementById("btnDownloadZip");

  const total = items.length;
  const estimatedPages = Math.ceil(total / 2);

  if (countEl) countEl.textContent = `${total}개 문항`;
  if (pagesEl) pagesEl.textContent = total > 0 ? `(B4 단면 약 ${estimatedPages}페이지)` : "";

  // 문항이 없을 때는 다운로드 버튼 비활성화
  const disabled = total === 0;
  if (btnQuestion) btnQuestion.disabled = disabled;
  if (btnExplanation) btnExplanation.disabled = disabled;
  if (btnZip) btnZip.disabled = disabled;
}

/** 빈 상태 렌더링 */
function renderEmptyState() {
  const listContainer = document.getElementById("handoutItemsList");
  if (!listContainer) return;

  listContainer.innerHTML = `
    <div class="handout-empty-state">
      <div class="handout-empty-state-icon">📋</div>
      <h3 style="margin: 0 0 8px; font-size: 1.1rem; color: #1e293b;">유인물 보관함이 비어 있습니다.</h3>
      <p style="margin: 0 0 16px; font-size: 0.88rem; color: #64748b;">
        지문 검색 결과 화면에서 각 문항의 <b>[유인물 담기]</b> 체크박스를 선택해 주세요.
      </p>
      <button type="button" class="btn-handout-tool" id="btnGoBackToSearchFromEmpty">
        🔙 검색 결과 화면으로 이동
      </button>
    </div>
  `;

  const btnGoBack = document.getElementById("btnGoBackToSearchFromEmpty");
  if (btnGoBack) {
    btnGoBack.addEventListener("click", () => {
      import("./navigation.js").then((m) => {
        if (m.switchView) m.switchView("results");
      });
    });
  }
}

/** 문항 카드 목록 렌더링 */
function renderItemList(cartItems, detailItems) {
  const listContainer = document.getElementById("handoutItemsList");
  if (!listContainer) return;

  const detailMap = new Map();
  detailItems.forEach((d) => detailMap.set(d.id, d));

  let html = "";
  cartItems.forEach((cItem, idx) => {
    const detail = detailMap.get(cItem.id) || {};
    const customNum = cItem.custom_q_num || String(idx + 1);
    const rawId = (detail.id || cItem.id || "").replace(/^\[/, "").replace(/\]$/, "");
    const qType = detail.question_type || "유형 미지정";
    const crate = detail.correct_rate !== null && detail.correct_rate !== undefined ? ` / 정답률 ${detail.correct_rate}%` : "";
    const title = detail.question_title || `${cItem.id} 문항`;
    const snippet = (detail.passage_text || "").slice(0, 200).trim();

    html += `
      <div class="handout-item-card" data-id="${escapeHtml(cItem.id)}" data-index="${idx}">
        <div class="handout-item-header">
          <div class="handout-item-qnum-box">
            <span style="font-size: 0.85rem; font-weight: 700; color: #475569;">인쇄 번호:</span>
            <input type="text" class="handout-item-qnum-input" value="${escapeHtml(customNum)}" data-id="${escapeHtml(cItem.id)}" title="유인물에 실제로 인쇄될 문항 번호를 직접 입력하세요">
            <span style="font-size: 0.85rem; font-weight: 700; color: #1d4ed8;">번</span>
            <span class="handout-item-source-badge">[원출처: ${escapeHtml(rawId)}${escapeHtml(crate)}]</span>
            <span style="font-size: 0.8rem; color: #64748b;">(${escapeHtml(qType)})</span>
          </div>
          <div class="handout-item-controls">
            <button type="button" class="btn-card-move btn-move-up" data-index="${idx}" title="위로 이동" ${idx === 0 ? "disabled" : ""}>▲</button>
            <button type="button" class="btn-card-move btn-move-down" data-index="${idx}" title="아래로 이동" ${idx === cartItems.length - 1 ? "disabled" : ""}>▼</button>
            <button type="button" class="btn-card-delete" data-id="${escapeHtml(cItem.id)}" title="이 문항 삭제">✕</button>
          </div>
        </div>
        <div class="handout-item-title">${escapeHtml(title)}</div>
        ${snippet ? `<div class="handout-item-passage-snippet">${escapeHtml(snippet)}...</div>` : ""}
      </div>
    `;
  });

  listContainer.innerHTML = html;
  bindItemEvents();
}

/** 문항 카드 내부 이벤트 바인딩 */
function bindItemEvents() {
  const listContainer = document.getElementById("handoutItemsList");
  if (!listContainer) return;

  // 인쇄 번호 직접 수정 이벤트
  listContainer.querySelectorAll(".handout-item-qnum-input").forEach((inp) => {
    inp.addEventListener("change", (e) => {
      const pid = e.target.dataset.id;
      const val = e.target.value.trim();
      setCustomQNum(pid, val);
    });
  });

  // 위로 이동
  listContainer.querySelectorAll(".btn-move-up").forEach((btn) => {
    btn.addEventListener("click", () => {
      const idx = parseInt(btn.dataset.index, 10);
      if (idx > 0) {
        reorderCart(idx, idx - 1);
        renderHandoutView();
      }
    });
  });

  // 아래로 이동
  listContainer.querySelectorAll(".btn-move-down").forEach((btn) => {
    btn.addEventListener("click", () => {
      const idx = parseInt(btn.dataset.index, 10);
      const items = getCartItems();
      if (idx < items.length - 1) {
        reorderCart(idx, idx + 1);
        renderHandoutView();
      }
    });
  });

  // 개별 삭제
  listContainer.querySelectorAll(".btn-card-delete").forEach((btn) => {
    btn.addEventListener("click", () => {
      const pid = btn.dataset.id;
      removeFromCart(pid);
      renderHandoutView();
    });
  });
}

/** 템플릿 목록 조회 및 드롭다운 채우기 */
async function loadTemplateList() {
  const select = document.getElementById("handoutTemplateSelect");
  if (!select) return;

  try {
    const res = await fetch("/api/handouts/templates");
    if (!res.ok) throw new Error("템플릿 목록 로드 실패");
    const data = await res.json();
    const templates = data.templates || [];

    const savedTemplate = localStorage.getItem(KEY_SELECTED_TEMPLATE) || "";
    let html = "";
    templates.forEach((t) => {
      const isSelected = t.filename === savedTemplate;
      html += `<option value="${escapeHtml(t.filename)}" ${isSelected ? "selected" : ""}>${escapeHtml(t.name)} (${t.size_kb}KB)</option>`;
    });

    select.innerHTML = html;
  } catch (err) {
    console.error("Failed to load templates", err);
  }
}

/** 양식 설정값 localStorage 복원 */
function restoreFormSettings() {
  const inpTitle = document.getElementById("handoutHeaderTitle");
  const inpSub = document.getElementById("handoutHeaderSub");
  const inpFooter = document.getElementById("handoutFooterText");
  const chkHighlight = document.getElementById("handoutHighlightAnswer");

  if (inpTitle) inpTitle.value = localStorage.getItem(KEY_HEADER_TITLE) || "";
  if (inpSub) inpSub.value = localStorage.getItem(KEY_HEADER_SUB) || "";
  if (inpFooter) inpFooter.value = localStorage.getItem(KEY_FOOTER_TEXT) || "";
  if (chkHighlight) {
    const savedH = localStorage.getItem(KEY_HIGHLIGHT_ANSWER);
    chkHighlight.checked = savedH !== null ? savedH === "true" : true;
  }
}

/** 양식 설정값 저장 */
function saveFormSettings() {
  const inpTitle = document.getElementById("handoutHeaderTitle");
  const inpSub = document.getElementById("handoutHeaderSub");
  const inpFooter = document.getElementById("handoutFooterText");
  const chkHighlight = document.getElementById("handoutHighlightAnswer");
  const selTemplate = document.getElementById("handoutTemplateSelect");

  if (inpTitle) localStorage.setItem(KEY_HEADER_TITLE, inpTitle.value.trim());
  if (inpSub) localStorage.setItem(KEY_HEADER_SUB, inpSub.value.trim());
  if (inpFooter) localStorage.setItem(KEY_FOOTER_TEXT, inpFooter.value.trim());
  if (chkHighlight) localStorage.setItem(KEY_HIGHLIGHT_ANSWER, String(chkHighlight.checked));
  if (selTemplate) localStorage.setItem(KEY_SELECTED_TEMPLATE, selTemplate.value);
}

/** 유인물 다운로드 실행 함수 */
async function downloadHandout(handoutType) {
  saveFormSettings();
  const items = getCartItems();
  if (items.length === 0) {
    alert("유인물로 제작할 문항이 없습니다. 문항을 먼저 선택해 주세요.");
    return;
  }

  const customQNums = {};
  items.forEach((item) => {
    if (item.custom_q_num) {
      customQNums[item.id] = item.custom_q_num;
    }
  });

  const payload = {
    handout_type: handoutType,
    passage_ids: items.map((i) => i.id),
    custom_q_nums: customQNums,
    header_title: (document.getElementById("handoutHeaderTitle")?.value || "").trim(),
    header_sub: (document.getElementById("handoutHeaderSub")?.value || "").trim(),
    footer_text: (document.getElementById("handoutFooterText")?.value || "").trim(),
    highlight_answer: !!document.getElementById("handoutHighlightAnswer")?.checked,
    template_name: document.getElementById("handoutTemplateSelect")?.value || null,
  };

  const btnQ = document.getElementById("btnDownloadQuestion");
  const btnE = document.getElementById("btnDownloadExplanation");
  const btnZ = document.getElementById("btnDownloadZip");

  const originalTexts = {
    q: btnQ ? btnQ.innerHTML : "",
    e: btnE ? btnE.innerHTML : "",
    z: btnZ ? btnZ.innerHTML : "",
  };

  try {
    if (btnQ) btnQ.disabled = true;
    if (btnE) btnE.disabled = true;
    if (btnZ) btnZ.disabled = true;

    if (handoutType === "question" && btnQ) btnQ.innerHTML = "⏳ 문제지 생성 중...";
    if (handoutType === "explanation" && btnE) btnE.innerHTML = "⏳ 해설지 생성 중...";
    if (handoutType === "both_zip" && btnZ) btnZ.innerHTML = "⏳ 패키지 압축 중...";

    const res = await fetch("/api/handouts/generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (!res.ok) {
      const errJson = await res.json().catch(() => ({}));
      throw new Error(errJson.detail || "유인물 생성 중 오류가 발생했습니다.");
    }

    // 파일명 파싱 (Content-Disposition 헤더)
    let filename = handoutType === "both_zip" ? "유인물_패키지.zip" : (handoutType === "question" ? "문제지_유인물.hwpx" : "해설지_유인물.hwpx");
    const disposition = res.headers.get("Content-Disposition");
    if (disposition) {
      const matchUtf8 = disposition.match(/filename\*=UTF-8''([^;]+)/i);
      if (matchUtf8) {
        filename = decodeURIComponent(matchUtf8[1]);
      } else {
        const matchPlain = disposition.match(/filename="?([^";]+)"?/i);
        if (matchPlain) filename = matchPlain[1];
      }
    }

    const blob = await res.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    window.URL.revokeObjectURL(url);

  } catch (err) {
    console.error("Handout download failed", err);
    alert(`유인물 생성 실패: ${err.message}`);
  } finally {
    if (btnQ) {
      btnQ.disabled = false;
      btnQ.innerHTML = originalTexts.q;
    }
    if (btnE) {
      btnE.disabled = false;
      btnE.innerHTML = originalTexts.e;
    }
    if (btnZ) {
      btnZ.disabled = false;
      btnZ.innerHTML = originalTexts.z;
    }
  }
}

/** 전체 툴바 및 다운로드 이벤트 초기화 */
export function initHandoutPassageView() {
  // 1번부터 자동 재부여 버튼
  const btnRenumber1 = document.getElementById("btnHandoutRenumber1");
  if (btnRenumber1) {
    btnRenumber1.addEventListener("click", () => {
      renumberCart(1);
      renderHandoutView();
    });
  }

  // N번부터 순차 재부여 버튼
  const btnRenumberN = document.getElementById("btnHandoutRenumberN");
  const inpStartNum = document.getElementById("inputHandoutStartNum");
  if (btnRenumberN && inpStartNum) {
    btnRenumberN.addEventListener("click", () => {
      const sNum = parseInt(inpStartNum.value, 10) || 1;
      renumberCart(sNum);
      renderHandoutView();
    });
  }

  // 전체 비우기
  const btnClear = document.getElementById("btnHandoutClearAll");
  if (btnClear) {
    btnClear.addEventListener("click", () => {
      if (confirm("유인물 제작소의 모든 문항을 비우시겠습니까?")) {
        clearCart();
        renderHandoutView();
      }
    });
  }

  // 뒤로 가기 버튼
  const btnBack = document.getElementById("btnHandoutBackToResults");
  if (btnBack) {
    btnBack.addEventListener("click", () => {
      import("./navigation.js").then((m) => {
        if (m.switchView) m.switchView("results");
      });
    });
  }

  // 템플릿 업로드 트리거
  const btnUpload = document.getElementById("btnUploadHandoutTemplate");
  const fileInput = document.getElementById("inputHandoutTemplateFile");
  if (btnUpload && fileInput) {
    btnUpload.addEventListener("click", () => fileInput.click());
    fileInput.addEventListener("change", async (e) => {
      const file = e.target.files?.[0];
      if (!file) return;

      if (!file.name.toLowerCase().endswith(".hwpx")) {
        alert("HWPX 양식 파일(.hwpx)만 업로드할 수 있습니다.");
        fileInput.value = "";
        return;
      }

      const formData = new FormData();
      formData.append("file", file);

      try {
        btnUpload.disabled = true;
        btnUpload.textContent = "⏳ 업로드 중...";
        const res = await fetch("/api/handouts/templates/upload", {
          method: "POST",
          body: formData,
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "양식 업로드 실패");

        alert(`양식 '${data.filename}'이 성공적으로 등록되었습니다.`);
        localStorage.setItem(KEY_SELECTED_TEMPLATE, data.filename);
        await loadTemplateList();
      } catch (err) {
        console.error("Template upload failed", err);
        alert(`양식 업로드 실패: ${err.message}`);
      } finally {
        btnUpload.disabled = false;
        btnUpload.textContent = "📤 새 HWPX 양식 업로드";
        fileInput.value = "";
      }
    });
  }

  // 설정 폼 변경 시 자동 저장
  ["handoutHeaderTitle", "handoutHeaderSub", "handoutFooterText", "handoutHighlightAnswer", "handoutTemplateSelect"].forEach((id) => {
    const el = document.getElementById(id);
    if (el) {
      el.addEventListener("change", saveFormSettings);
      el.addEventListener("input", saveFormSettings);
    }
  });

  // 다운로드 버튼 바인딩
  const btnQ = document.getElementById("btnDownloadQuestion");
  const btnE = document.getElementById("btnDownloadExplanation");
  const btnZ = document.getElementById("btnDownloadZip");

  if (btnQ) btnQ.addEventListener("click", () => downloadHandout("question"));
  if (btnE) btnE.addEventListener("click", () => downloadHandout("explanation"));
  if (btnZ) btnZ.addEventListener("click", () => downloadHandout("both_zip"));

  // 카트 변경 시 화면 갱신 리스너
  window.addEventListener("handout-cart-changed", () => {
    const container = document.getElementById("handoutViewContainer");
    if (container && container.style.display !== "none") {
      renderHandoutView();
    }
  });
}
