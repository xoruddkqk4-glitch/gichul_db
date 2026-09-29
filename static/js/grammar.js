/**
 * 05-gichul_db: 어법 범주 모달 · 브레드크럼 필터 · 일괄 분석 진행 모달 (섹션 12) (grammar.js)
 * - main.js 에서 분리
 */

import { appState } from "./state.js";
import {
  batchAnalysisModal,
  batchCurrentSentId,
  batchCurrentSentText,
  batchFooterInfo,
  batchLogCount,
  batchLogList,
  batchModalStatusBadge,
  batchProgressBar,
  batchProgressCounter,
  batchProgressLabel,
  btnApplyGrammarSelection,
  btnBatchAnalyzeAll,
  btnBatchAnalyzeStarred,
  btnCancelBatchAnalysis,
  btnCancelGrammarModal,
  btnClearGrammarSearch,
  btnCloseBatchModal,
  btnCloseGrammarModal,
  btnGrammarChangeStep,
  btnGrammarResetStep,
  btnGrammarToggleView,
  btnHeaderFlow,
  btnResetGrammarSelection,
  btnResetHomeGrammarFilter,
  btnResetResultsGrammarFilter,
  btnResultsToggleStarred,
  btnToggleStarred,
  filterGrammarCategory,
  filterGrammarPos,
  grammarBreadcrumbHome,
  grammarBreadcrumbTrail,
  grammarCategoryModal,
  grammarGridContainer,
  grammarModalSentenceInfo,
  grammarPreviewBadges,
  grammarSelectedCount,
  inputGrammarSearch,
  resultsFilterGrammarCategory,
  resultsFilterGrammarPos,
  grammarTreeStatusBadge,
  btnManageGrammarTree,
  customGrammarTreeModal,
  btnCloseCustomTreeModal,
  btnToggleCustomTreeFullscreen,
  btnCancelCustomTreeModal,
  btnSaveCustomTreeModal,
  toggleUseCustomTree,
  labelUseCustomTree,
  customTreeJsonEditor,
  btnCopyStandardTree,
  btnResetToStandardTree,
  tabBtnVisualEditor,
  tabBtnJsonEditor,
  paneVisualEditor,
  paneJsonEditor,
  statTotalGrammar,
  statActiveGrammar,
  statModifiedGrammar,
  statHiddenGrammar,
  inputCustomTreeSearch,
  btnClearCustomTreeSearch,
  chkOnlyModified,
  btnExpandAllTree,
  btnCollapseAllTree,
  sidebarTreeContainer,
  detailBreadcrumb,
  detailCountBadge,
  detailSubstat,
  btnBulkEnableCurrent,
  btnBulkDisableCurrent,
  detailCardGrid,
  customTreeSaveStatus,
} from "./dom.js";
import { executeSearch, executeSearchWithinResults } from "./search.js";
import { getGrammarBadgeClass, showGrammarPopover, showSentencesForPassage } from "./results-sentence.js";
import { escapeHtml, showToast } from "./utils.js";

let grammarCategoriesList = [];
let isCustomGrammarTree = false;
let customGrammarTreeData = null;
// =========================================================================
// 12. 어법 범주표 로드 및 캐스케이딩 드롭다운 연동
// =========================================================================
// =========================================================================
// 12-1. 어법 범주 전체 개요 및 다중 선택 모달 제어
// =========================================================================

let activeGrammarModalSentence = null;
let activeGrammarModalCallback = null;
const selectedGrammarCategoryIds = new Set();
let currentGrammarPosFilter = "ALL";
let grammarSearchTerm = "";

// 어법 모달 네비게이션 상태 (단계별 드릴다운 탐색: 1단계 품사 -> 2단계 세부 분류 -> 3단계 세부 항목)
let grammarNavState = {
  pos: null,     // string | null (e.g. '접속사')
  subPos: null,  // string | null (e.g. '관계사' or 'ALL')
  mode: "step",  // 'step' | 'all'
};

function closeGrammarCategoryModal() {
  if (grammarCategoryModal) {
    grammarCategoryModal.style.display = "none";
  }
  activeGrammarModalSentence = null;
  activeGrammarModalCallback = null;
}

function updateGrammarTreeStatusBadge() {
  if (!grammarTreeStatusBadge) return;
  if (isCustomGrammarTree) {
    grammarTreeStatusBadge.textContent = "👤 나만의 커스텀 체계";
    grammarTreeStatusBadge.classList.add("custom-active");
    grammarTreeStatusBadge.title = "현재 나만의 커스텀 어법 체계가 적용되어 있습니다.";
  } else {
    grammarTreeStatusBadge.textContent = "🏛️ 표준 243개 체계";
    grammarTreeStatusBadge.classList.remove("custom-active");
    grammarTreeStatusBadge.title = "현재 기본 표준 243개 어법 체계가 적용되어 있습니다.";
  }
}

async function loadGrammarCategories() {
  try {
    const res = await fetch("/api/grammar/categories");
    if (res.ok) {
      const data = await res.json();
      const catData = data.data || data;
      grammarCategoriesList = catData.list || [];
      isCustomGrammarTree = Boolean(data.is_custom || data.use_custom_tree);
      customGrammarTreeData = catData;
      updateGrammarTreeStatusBadge();
      return;
    }
  } catch (e) {
    console.error("어법 범주 API 로드 실패, 로컬 백업 로드 시도:", e);
  }

  try {
    const fbRes = await fetch("/static/data/grammar_categories.json");
    if (fbRes.ok) {
      const fbData = await fbRes.json();
      grammarCategoriesList = fbData.list || [];
      isCustomGrammarTree = false;
      customGrammarTreeData = fbData;
      updateGrammarTreeStatusBadge();
    }
  } catch (fbErr) {
    console.error("어법 범주 로컬 백업 로드 실패:", fbErr);
  }
}

export function openGrammarModalForSentence(sentence, onUpdateCallback) {
  if (!sentence || !grammarCategoryModal) return;

  activeGrammarModalSentence = sentence;
  activeGrammarModalCallback = onUpdateCallback;

  selectedGrammarCategoryIds.clear();
  const existing = sentence.grammar_annotations || [];
  existing.forEach((a) => {
    if (a.category_id && a.category_id !== 0) {
      selectedGrammarCategoryIds.add(Number(a.category_id));
    } else if (a.id) {
      selectedGrammarCategoryIds.add(Number(a.id));
    } else if (a.leaf_name) {
      const found = grammarCategoriesList.find(c => c.leaf === a.leaf_name);
      if (found) selectedGrammarCategoryIds.add(found.id);
    }
  });

  if (grammarModalSentenceInfo) {
    const sentSnippet = (sentence.sentence_text || "").slice(0, 100);
    grammarModalSentenceInfo.innerHTML = `
        <span style="font-weight: 700; color: var(--primary);">${escapeHtml(sentence.id)}</span>:
        "${escapeHtml(sentSnippet)}${(sentence.sentence_text || "").length > 100 ? "..." : ""}"
      `;
  }

  if (inputGrammarSearch) inputGrammarSearch.value = "";
  if (btnClearGrammarSearch) btnClearGrammarSearch.style.display = "none";
  grammarSearchTerm = "";
  grammarNavState = { pos: null, subPos: null, mode: "step" };

  renderGrammarModalView();
  updateGrammarModalPreview();

  grammarCategoryModal.style.display = "flex";
}

/** 어법 모달 브레드크럼 바 렌더링 (지문 선택기 스타일) */
function renderGrammarBreadcrumb() {
  if (!grammarBreadcrumbTrail) return;

  const isSearching = !!(grammarSearchTerm && grammarSearchTerm.trim());
  const isNavActive = !!(
    grammarNavState.pos ||
    grammarNavState.subPos ||
    grammarNavState.mode === "all" ||
    isSearching
  );

  // "↺ 설정 초기화" 버튼: 단계 선택, 전체 보기 또는 검색 중일 때 노출 (초기 9대 품사 화면으로 즉시 복귀)
  if (btnGrammarResetStep) {
    if (isNavActive) {
      btnGrammarResetStep.style.display = "inline-flex";
      btnGrammarResetStep.onclick = () => {
        grammarNavState = { pos: null, subPos: null, mode: "step" };
        grammarSearchTerm = "";
        if (inputGrammarSearch) inputGrammarSearch.value = "";
        if (btnClearGrammarSearch) btnClearGrammarSearch.style.display = "none";
        renderGrammarModalView();
        showToast("어법 탐색이 초기화되었습니다.", "info");
      };
    } else {
      btnGrammarResetStep.style.display = "none";
    }
  }

  if (isSearching) {
    const q = grammarSearchTerm.trim().toLowerCase();
    const matchCount = grammarCategoriesList.filter(it => {
      const leaf = (it.leaf || "").toLowerCase();
      const path = (it.full_path || "").toLowerCase();
      return leaf.includes(q) || path.includes(q);
    }).length;

    grammarBreadcrumbTrail.innerHTML = `
        <span class="breadcrumb-item active">🔍 "${escapeHtml(grammarSearchTerm.trim())}" 검색 결과</span>
        <span class="breadcrumb-count-badge">(${matchCount}건)</span>
      `;
    if (btnGrammarChangeStep) {
      btnGrammarChangeStep.style.display = "inline-flex";
      btnGrammarChangeStep.innerHTML = "❌ 검색 지우기";
    }
    if (btnGrammarToggleView) {
      btnGrammarToggleView.style.display = "none";
    }
    return;
  }

  if (btnGrammarToggleView) {
    btnGrammarToggleView.style.display = "inline-flex";
    btnGrammarToggleView.innerHTML = grammarNavState.mode === "all" ? "📂 단계별 탐색" : "🌐 전체 보기";
  }

  if (grammarNavState.mode === "all") {
    grammarBreadcrumbTrail.innerHTML = `
        <span class="breadcrumb-item active">전체 어법 범주 한눈에 보기</span>
        <span class="breadcrumb-count-badge">(${grammarCategoriesList.length}개)</span>
      `;
    if (btnGrammarChangeStep) btnGrammarChangeStep.style.display = "none";
    return;
  }

  // 단계별 모드 (Step Mode)
  if (grammarNavState.pos && grammarNavState.subPos) {
    // Step 3: 세부 항목 선택
    const itemsCount = grammarNavState.subPos === "ALL"
      ? grammarCategoriesList.filter(it => it.pos === grammarNavState.pos).length
      : grammarCategoriesList.filter(it => it.pos === grammarNavState.pos && ((it.path && it.path.length > 1 ? it.path[1] : "기본 분류") === grammarNavState.subPos)).length;

    const subLabel = grammarNavState.subPos === "ALL" ? "전체 펼쳐보기" : grammarNavState.subPos;

    grammarBreadcrumbTrail.innerHTML = `
        <span class="breadcrumb-item" data-step="pos" title="품사 변경">${escapeHtml(grammarNavState.pos)}</span>
        <span class="breadcrumb-separator">&gt;</span>
        <span class="breadcrumb-item active" data-step="subpos" title="세부 분류 변경">${escapeHtml(subLabel)}</span>
        <span class="breadcrumb-count-badge">(${itemsCount}개)</span>
      `;

    if (btnGrammarChangeStep) {
      btnGrammarChangeStep.style.display = "inline-flex";
      btnGrammarChangeStep.innerHTML = "🔄 다른 분류 선택";
    }
  } else if (grammarNavState.pos) {
    // Step 2: 2단계 분류 선택
    const posCount = grammarCategoriesList.filter(it => it.pos === grammarNavState.pos).length;

    grammarBreadcrumbTrail.innerHTML = `
        <span class="breadcrumb-item" data-step="pos" title="품사 변경">${escapeHtml(grammarNavState.pos)}</span>
        <span class="breadcrumb-separator">&gt;</span>
        <span class="breadcrumb-hint">세부 분류를 선택하세요</span>
        <span class="breadcrumb-count-badge">(${posCount}개)</span>
      `;

    if (btnGrammarChangeStep) {
      btnGrammarChangeStep.style.display = "inline-flex";
      btnGrammarChangeStep.innerHTML = "🔄 다른 품사 선택";
    }
  } else {
    // Step 1: 품사 선택
    grammarBreadcrumbTrail.innerHTML = `
        <span class="breadcrumb-hint">탐색할 어법 품사를 선택하세요</span>
        <span class="breadcrumb-count-badge">(총 ${grammarCategoriesList.length}개)</span>
      `;

    if (btnGrammarChangeStep) {
      btnGrammarChangeStep.style.display = "none";
    }
  }

  // 브레드크럼 항목 클릭 시 상위 단계로 즉시 복귀
  grammarBreadcrumbTrail.querySelectorAll(".breadcrumb-item").forEach(item => {
    item.addEventListener("click", () => {
      const step = item.dataset.step;
      if (step === "pos") {
        grammarNavState.subPos = null;
        renderGrammarModalView();
      }
    });
  });
}

/** 어법 모달 메인 뷰 렌더러 */
function renderGrammarModalView() {
  renderGrammarBreadcrumb();
  if (!grammarGridContainer) return;

  // A. 검색 모드
  if (grammarSearchTerm && grammarSearchTerm.trim()) {
    renderGrammarSearchView(grammarSearchTerm.trim().toLowerCase());
    return;
  }

  // B. 전체 보기 모드
  if (grammarNavState.mode === "all") {
    renderGrammarAllView();
    return;
  }

  // C. 단계별 드릴다운 모드
  if (!grammarNavState.pos) {
    renderGrammarStepPos();
  } else if (!grammarNavState.subPos) {
    renderGrammarStepSub(grammarNavState.pos);
  } else {
    renderGrammarStepItems(grammarNavState.pos, grammarNavState.subPos);
  }
}

/** Step 1: 품사 선택 카드 그리드 (9개 대분류) */
function renderGrammarStepPos() {
  const posOrder = ["명사", "대명사", "문장", "주어", "동사", "형용사/부사", "전치사", "접속사", "특수구문"];
  const posGroups = {};
  posOrder.forEach(p => { posGroups[p] = { items: [], subs: [] }; });

  grammarCategoriesList.forEach(item => {
    const pos = item.pos || "기타";
    if (!posGroups[pos]) posGroups[pos] = { items: [], subs: [] };
    posGroups[pos].items.push(item);
    const sub = (item.path && item.path.length > 1) ? item.path[1] : "기본 분류";
    if (!posGroups[pos].subs.includes(sub)) {
      posGroups[pos].subs.push(sub);
    }
  });

  let html = '<div class="grammar-step-pos-grid">';
  posOrder.forEach(pos => {
    const group = posGroups[pos];
    if (!group || group.items.length === 0) return;

    const totalCount = group.items.length;
    const subList = group.subs;
    const previewText = subList.slice(0, 4).join(" · ") + (subList.length > 4 ? ` 외 ${subList.length - 4}개` : "");
    const selectedCount = group.items.filter(it => selectedGrammarCategoryIds.has(it.id)).length;

    html += `
        <div class="grammar-step-pos-card" data-pos="${escapeHtml(pos)}">
          <div class="grammar-step-pos-header">
            <span class="grammar-step-pos-title">📌 ${escapeHtml(pos)}</span>
            <span class="grammar-step-pos-badge">${totalCount}개 어법</span>
          </div>
          <div class="grammar-step-pos-preview">${escapeHtml(previewText)}</div>
          ${selectedCount > 0 ? `<div class="grammar-step-pos-selected">✔ ${selectedCount}개 선택됨</div>` : ""}
        </div>
      `;
  });
  html += '</div>';

  grammarGridContainer.innerHTML = html;

  grammarGridContainer.querySelectorAll(".grammar-step-pos-card").forEach(card => {
    card.addEventListener("click", () => {
      grammarNavState.pos = card.dataset.pos;
      grammarNavState.subPos = null;
      renderGrammarModalView();
    });
  });
}

/** Step 2: 2단계 세부 분류 선택 카드 그리드 */
function renderGrammarStepSub(pos) {
  const posItems = grammarCategoriesList.filter(it => it.pos === pos);
  const subMap = {};

  posItems.forEach(it => {
    const sub = (it.path && it.path.length > 1) ? it.path[1] : "기본 분류";
    if (!subMap[sub]) subMap[sub] = [];
    subMap[sub].push(it);
  });

  let html = '<div class="grammar-step-sub-grid">';
  for (const [subName, items] of Object.entries(subMap)) {
    const leaves = items.map(i => i.leaf).filter(Boolean);
    const previewText = leaves.slice(0, 4).join(" · ") + (leaves.length > 4 ? ` 외 ${leaves.length - 4}개` : "");
    const selectedCount = items.filter(it => selectedGrammarCategoryIds.has(it.id)).length;

    html += `
        <div class="grammar-step-sub-card" data-subpos="${escapeHtml(subName)}">
          <div class="grammar-step-sub-header">
            <span class="grammar-step-sub-title">📂 ${escapeHtml(subName)}</span>
            <span class="grammar-step-sub-badge">${items.length}개</span>
          </div>
          <div class="grammar-step-sub-preview">${escapeHtml(previewText)}</div>
          ${selectedCount > 0 ? `<div class="grammar-step-pos-selected">✔ ${selectedCount}개 선택됨</div>` : ""}
        </div>
      `;
  }

  // 하단 전체 펼쳐보기 버튼
  html += `
      <button type="button" class="grammar-step-sub-all-btn" id="btnGrammarSubAll">
        📋 <strong>${escapeHtml(pos)}</strong> 전체 (${posItems.length}개 어법) 한 번에 펼쳐보기
      </button>
    </div>`;

  grammarGridContainer.innerHTML = html;

  grammarGridContainer.querySelectorAll(".grammar-step-sub-card").forEach(card => {
    card.addEventListener("click", () => {
      grammarNavState.subPos = card.dataset.subpos;
      renderGrammarModalView();
    });
  });

  const btnSubAll = grammarGridContainer.querySelector("#btnGrammarSubAll");
  if (btnSubAll) {
    btnSubAll.addEventListener("click", () => {
      grammarNavState.subPos = "ALL";
      renderGrammarModalView();
    });
  }
}

/** Step 3: 세부 어법 다중 선택 타일 목록 */
function renderGrammarStepItems(pos, subPos) {
  let items = [];
  if (subPos === "ALL") {
    items = grammarCategoriesList.filter(it => it.pos === pos);
  } else {
    items = grammarCategoriesList.filter(it => it.pos === pos && ((it.path && it.path.length > 1 ? it.path[1] : "기본 분류") === subPos));
  }

  if (!items || items.length === 0) {
    grammarGridContainer.innerHTML = `
        <div class="grammar-empty-state">
          <span class="empty-icon">📭</span>
          <p class="empty-title">등록된 어법 항목이 없습니다.</p>
        </div>
      `;
    return;
  }

  const tilesHtml = items.map(it => renderGrammarTile(it)).join("");
  grammarGridContainer.innerHTML = `<div class="grammar-subgroup-items">${tilesHtml}</div>`;
  bindGrammarTileEvents(grammarGridContainer);
}

/** 개별 어법 타일 HTML 렌더러 (브레드크럼 배지 스타일 적용) */
function renderGrammarTile(it) {
  const isChecked = selectedGrammarCategoryIds.has(it.id);
  const pathPills = (it.path || []).map(p => `<span class="grammar-path-pill">${escapeHtml(p)}</span>`).join('<span class="grammar-path-sep">&gt;</span>');

  return `
      <label class="grammar-item-tile ${isChecked ? "checked" : ""}" 
             data-id="${it.id}" 
             data-pos="${escapeHtml(it.pos || "")}" 
             data-leaf="${escapeHtml(it.leaf || "")}" 
             data-path="${escapeHtml(it.full_path || "")}">
        <input type="checkbox" class="grammar-item-checkbox" value="${it.id}" ${isChecked ? "checked" : ""}>
        <div class="grammar-tile-info">
          <span class="grammar-tile-leaf">${escapeHtml(it.leaf || "")}</span>
          <div class="grammar-tile-path-breadcrumb">${pathPills}</div>
        </div>
      </label>
    `;
}

/** 검색 결과 뷰 */
function renderGrammarSearchView(query) {
  const matches = grammarCategoriesList.filter(it => {
    const leaf = (it.leaf || "").toLowerCase();
    const path = (it.full_path || "").toLowerCase();
    return leaf.includes(query) || path.includes(query);
  });

  if (matches.length === 0) {
    grammarGridContainer.innerHTML = `
        <div class="grammar-empty-state">
          <span class="empty-icon">🔍</span>
          <p class="empty-title">검색된 어법 범주가 없습니다.</p>
          <p class="empty-desc">검색어 "<strong>${escapeHtml(grammarSearchTerm.trim())}</strong>"에 일치하는 어법을 찾을 수 없습니다.<br>오타를 확인하시거나 상단의 <strong>[❌ 검색 지우기]</strong>를 눌러 단계별로 탐색해보세요.</p>
        </div>
      `;
    return;
  }

  const tilesHtml = matches.map(it => renderGrammarTile(it)).join("");
  grammarGridContainer.innerHTML = `<div class="grammar-subgroup-items">${tilesHtml}</div>`;
  bindGrammarTileEvents(grammarGridContainer);
}

/** 전체 보기 모드: 9개 대분류 품사별 서브그룹 카드 전체 표시 */
function renderGrammarAllView() {
  const posGroups = {};
  const posOrder = ["명사", "대명사", "문장", "주어", "동사", "형용사/부사", "전치사", "접속사", "특수구문"];
  posOrder.forEach(p => { posGroups[p] = {}; });

  grammarCategoriesList.forEach(item => {
    const pos = item.pos || "기타";
    if (!posGroups[pos]) posGroups[pos] = {};
    const subPos = (item.path && item.path.length > 1) ? item.path[1] : "기본 분류";
    if (!posGroups[pos][subPos]) posGroups[pos][subPos] = [];
    posGroups[pos][subPos].push(item);
  });

  let html = "";
  for (const [pos, subGroups] of Object.entries(posGroups)) {
    const subEntries = Object.entries(subGroups);
    if (subEntries.length === 0) continue;

    let totalPosCount = 0;
    subEntries.forEach(([_, items]) => { totalPosCount += items.length; });
    if (totalPosCount === 0) continue;

    let subgroupsHtml = "";
    for (const [subName, items] of subEntries) {
      if (!items || items.length === 0) continue;
      const tilesHtml = items.map(it => renderGrammarTile(it)).join("");

      subgroupsHtml += `
          <div class="grammar-subgroup" data-subpos="${escapeHtml(subName)}">
            <div class="grammar-subgroup-header">
              <span class="subgroup-title">
                <span class="subgroup-bullet">📂</span>
                <span class="subgroup-name">${escapeHtml(subName)}</span>
              </span>
              <span class="subgroup-count">${items.length}개</span>
            </div>
            <div class="grammar-subgroup-items">
              ${tilesHtml}
            </div>
          </div>
        `;
    }

    html += `
        <div class="grammar-group-card" data-pos="${escapeHtml(pos)}">
          <div class="grammar-group-header">
            <span style="display: flex; align-items: center; gap: 6px;">
              <span>📌 ${escapeHtml(pos)}</span>
            </span>
            <span class="grammar-group-badge">총 ${totalPosCount}개</span>
          </div>
          <div class="grammar-subgroups-container">
            ${subgroupsHtml}
          </div>
        </div>
      `;
  }

  grammarGridContainer.innerHTML = html;
  bindGrammarTileEvents(grammarGridContainer);
}

/** 타일 체크박스 이벤트 바인딩 */
function bindGrammarTileEvents(container) {
  if (!container) return;
  container.querySelectorAll(".grammar-item-tile").forEach(tile => {
    const cb = tile.querySelector(".grammar-item-checkbox");
    const id = Number(tile.dataset.id);

    cb.addEventListener("change", (e) => {
      e.stopPropagation();
      if (cb.checked) {
        selectedGrammarCategoryIds.add(id);
        tile.classList.add("checked");
      } else {
        selectedGrammarCategoryIds.delete(id);
        tile.classList.remove("checked");
      }
      updateGrammarModalPreview();
    });
  });
}

function updateGrammarModalPreview() {
  if (grammarSelectedCount) {
    grammarSelectedCount.textContent = selectedGrammarCategoryIds.size;
  }
  if (!grammarPreviewBadges) return;

  if (selectedGrammarCategoryIds.size === 0) {
    grammarPreviewBadges.innerHTML = '<span class="text-muted" style="font-size: 0.78rem;">선택된 어법이 없습니다. 아래 항목을 체크하세요.</span>';
    return;
  }

  const selectedList = Array.from(selectedGrammarCategoryIds).map(id => {
    return grammarCategoriesList.find(c => c.id === id);
  }).filter(Boolean);

  grammarPreviewBadges.innerHTML = selectedList.map(item => `
      <span class="preview-chip">
        🏷️ ${escapeHtml(item.leaf)} (${escapeHtml(item.pos)})
        <button type="button" class="preview-chip-remove" data-id="${item.id}" title="선택 해제">&times;</button>
      </span>
    `).join("");

  grammarPreviewBadges.querySelectorAll(".preview-chip-remove").forEach(btn => {
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      const id = Number(btn.dataset.id);
      selectedGrammarCategoryIds.delete(id);
      if (grammarGridContainer) {
        const tile = grammarGridContainer.querySelector(`.grammar-item-tile[data-id="${id}"]`);
        if (tile) {
          tile.classList.remove("checked");
          const cb = tile.querySelector(".grammar-item-checkbox");
          if (cb) cb.checked = false;
        }
      }
      updateGrammarModalPreview();
      // Step 1이나 Step 2 카드의 선택 뱃지 갱신을 위해 뷰 리렌더링
      if (!grammarNavState.subPos) {
        renderGrammarModalView();
      }
    });
  });
}

function updateSubGrammarCategories(pos, targetSelect) {
  if (!targetSelect) return;
  targetSelect.innerHTML = '<option value="">세부 어법 전체</option>';
  if (!pos) return;
  const filtered = grammarCategoriesList.filter((item) => item.pos === pos);
  filtered.forEach((item) => {
    const opt = document.createElement("option");
    opt.value = item.id;
    opt.textContent = `[${item.category_no}] ${item.leaf} (${item.full_path})`;
    targetSelect.appendChild(opt);
  });
}
// =========================================================================
// 어법 계층형 브레드크럼 필터 바 상태 동기화 및 설정 초기화
// =========================================================================

/** 브레드크럼 필터 바의 active pill 스타일 및 '설정 초기화' 버튼 가시성 업데이트 */
export function updateGrammarBreadcrumbFilterUI() {
  const pos = (filterGrammarPos && filterGrammarPos.value) || (resultsFilterGrammarPos && resultsFilterGrammarPos.value) || "";
  const cat = (filterGrammarCategory && filterGrammarCategory.value) || (resultsFilterGrammarCategory && resultsFilterGrammarCategory.value) || "";

  if (filterGrammarPos) filterGrammarPos.classList.toggle("active", !!pos);
  if (resultsFilterGrammarPos) resultsFilterGrammarPos.classList.toggle("active", !!pos);

  if (filterGrammarCategory) filterGrammarCategory.classList.toggle("active", !!cat);
  if (resultsFilterGrammarCategory) resultsFilterGrammarCategory.classList.toggle("active", !!cat);

  const hasActiveFilter = !!(pos || cat || appState.isStarredFilterActive);
  if (btnResetHomeGrammarFilter) {
    btnResetHomeGrammarFilter.style.display = hasActiveFilter ? "inline-flex" : "none";
  }
  if (btnResetResultsGrammarFilter) {
    btnResetResultsGrammarFilter.style.display = hasActiveFilter ? "inline-flex" : "none";
  }
}

/** 모든 어법 필터 및 별표 필터를 무설정 상태로 초기화 */
export function resetAllGrammarFilters(triggerSearch = false) {
  if (filterGrammarPos) filterGrammarPos.value = "";
  if (resultsFilterGrammarPos) resultsFilterGrammarPos.value = "";
  if (filterGrammarCategory) filterGrammarCategory.value = "";
  if (resultsFilterGrammarCategory) resultsFilterGrammarCategory.value = "";

  updateSubGrammarCategories("", filterGrammarCategory);
  updateSubGrammarCategories("", resultsFilterGrammarCategory);

  setStarredFilter(false);
  updateGrammarBreadcrumbFilterUI();

  if (triggerSearch) {
    if (appState.isSearchWithinActive && appState.rawSentencesData && appState.rawSentencesData.length > 0) {
      executeSearchWithinResults();
    } else {
      refreshCurrentSentenceView();
    }
  }
}

// 별표 필터 토글 제어
function setStarredFilter(active) {
  appState.isStarredFilterActive = active;
  if (btnToggleStarred) {
    btnToggleStarred.classList.toggle("active", active);
    btnToggleStarred.setAttribute("aria-pressed", active ? "true" : "false");
    const icon = btnToggleStarred.querySelector(".star-icon");
    if (icon) icon.textContent = active ? "⭐" : "☆";
  }
  if (btnResultsToggleStarred) {
    btnResultsToggleStarred.classList.toggle("active", active);
    btnResultsToggleStarred.setAttribute("aria-pressed", active ? "true" : "false");
    const icon = btnResultsToggleStarred.querySelector(".star-icon");
    if (icon) icon.textContent = active ? "⭐" : "☆";
  }
  updateGrammarBreadcrumbFilterUI();
}
// =========================================================================
// 12-1. 어법 분석 완료 후 화면 갱신 헬퍼 (지문 문장 화면 유지 버그 해결)
// =========================================================================

/**
 * 어법 분석 완료 후 현재 사용자가 보고 있던 컨텍스트(단일 지문 8문장 vs 일반 검색)를
 * 정확히 판단하여 화면을 새로고침합니다.
 */
function refreshCurrentSentenceView() {
  // 1. 단일 지문의 문장 목록 화면인 경우:
  //    btnHeaderFlow에 mode-back이 있거나 currentPassageId가 유지된 경우 해당 지문 8문장만 다시 로드!
  if (appState.currentPassageId && btnHeaderFlow && btnHeaderFlow.classList.contains("mode-back")) {
    showSentencesForPassage(appState.currentPassageId);
    return;
  }
  // 2. 결과 내 검색(isSearchWithinActive) 중인 경우
  if (appState.isSearchWithinActive && appState.rawSentencesData && appState.rawSentencesData.length > 0) {
    executeSearchWithinResults();
    return;
  }
  // 3. 일반 문장 검색 결과인 경우
  executeSearch("results");
}
// =========================================================================
// 12-2. AI 어법 일괄 분석 실시간 진행 모달 구동 함수
// =========================================================================

async function runBatchAnalysisModal(targetSentences, isStarredOnly = false) {
  if (!targetSentences || targetSentences.length === 0) return;
  if (!batchAnalysisModal) return;

  const totalCount = targetSentences.length;
  let successCount = 0;
  let isCancelled = false;

  // 모달 초기 상태 세팅
  batchAnalysisModal.style.display = "flex";
  if (batchModalStatusBadge) {
    batchModalStatusBadge.className = "batch-status-badge running";
    batchModalStatusBadge.innerHTML = "⏳ 분석 중";
  }
  if (batchProgressLabel) batchProgressLabel.textContent = "진행률: 0%";
  if (batchProgressBar) batchProgressBar.style.width = "0%";
  if (batchProgressCounter) batchProgressCounter.textContent = `0 / ${totalCount} 문장 완료`;
  if (batchCurrentSentId) batchCurrentSentId.textContent = "-";
  if (batchCurrentSentText) batchCurrentSentText.textContent = "분석을 준비하고 있습니다...";
  if (batchLogCount) batchLogCount.textContent = "0건";
  if (batchLogList) batchLogList.innerHTML = "";
  if (batchFooterInfo) {
    batchFooterInfo.innerHTML = '<span class="footer-spin-icon">⏳</span> AI 분석이 실시간 진행 중입니다. 잠시만 기다려 주세요.';
  }
  if (btnCancelBatchAnalysis) {
    btnCancelBatchAnalysis.style.display = "inline-flex";
    btnCancelBatchAnalysis.disabled = false;
    btnCancelBatchAnalysis.innerHTML = "⏹️ 분석 중단";
    btnCancelBatchAnalysis.onclick = () => {
      isCancelled = true;
      btnCancelBatchAnalysis.disabled = true;
      btnCancelBatchAnalysis.innerHTML = "중단 처리 중...";
      if (batchFooterInfo) {
        batchFooterInfo.innerHTML = "현재 분석 중인 문장 완료 후 안전하게 중단됩니다...";
      }
    };
  }
  if (btnCloseBatchModal) {
    btnCloseBatchModal.style.display = "none";
  }

  // 일괄 분석 버튼 비활성화
  if (btnBatchAnalyzeStarred) btnBatchAnalyzeStarred.disabled = true;
  if (btnBatchAnalyzeAll) btnBatchAnalyzeAll.disabled = true;

  // 문장별 실시간 순차 분석 (1문장 단위로 즉각적인 화면 피드백 및 안전한 중단 지원)
  for (let i = 0; i < totalCount; i++) {
    if (isCancelled) break;

    const sent = targetSentences[i];

    // 현재 진행 중인 문장 UI 표시
    if (batchCurrentSentId) batchCurrentSentId.textContent = sent.id || `문장 #${i + 1}`;
    if (batchCurrentSentText) batchCurrentSentText.textContent = `"${sent.sentence_text || ""}"`;

    try {
      const res = await fetch("/api/sentences/batch-analyze-grammar", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          sentence_ids: [sent.id],
          starred_only: isStarredOnly,
          skip_already_analyzed: true,
        }),
      });

      const data = await res.json();
      let isSuccess = false;
      let annos = [];
      let errMsg = "";

      if (res.ok && data.results && data.results.length > 0) {
        const item = data.results[0];
        if (item.success) {
          isSuccess = true;
          annos = item.annotations || [];
          successCount++;
          sent.grammar_annotations = annos;
          sent.grammar_analyzed = 1;
          if (item.sentence_text && item.sentence_text !== sent.sentence_text) {
            sent.sentence_text = item.sentence_text;
          }
        } else {
          errMsg = item.error || "분석 오류";
        }
      } else {
        errMsg = data.detail || data.message || "서버 통신 실패";
      }

      // 실시간 로그 아이템 동적 생성
      if (batchLogList) {
        const logItem = document.createElement("div");
        logItem.className = `batch-log-item ${isSuccess ? "success" : "error"}`;

        let badgesHtml = "";
        if (isSuccess) {
          if (annos.length > 0) {
            badgesHtml = annos.map((a, aIdx) => {
              const badgeCls = getGrammarBadgeClass(a.pos);
              return `<span class="grammar-tag-badge ${badgeCls}" data-idx="${aIdx}" style="font-size: 0.72rem; padding: 2px 7px;" title="클릭하여 상세 해설 보기">🏷️ ${escapeHtml(a.category_name || a.pos)}: ${escapeHtml(a.target_phrase || "")}</span>`;
            }).join(" ");
          } else {
            badgesHtml = '<span class="grammar-badge-none" style="font-size: 0.72rem;">✓ 해당사항 없음 (특이 어법 없음)</span>';
          }
        } else {
          badgesHtml = `<span style="color: #ef4444; font-size: 0.72rem;">⚠️ 오류: ${escapeHtml(errMsg)}</span>`;
        }

        logItem.innerHTML = `
            <div class="batch-log-item-header">
              <span class="batch-log-item-id">${escapeHtml(sent.id || `문장 #${i + 1}`)}</span>
              <span class="batch-log-item-status" style="color: ${isSuccess ? 'var(--success)' : 'var(--danger)'};">
                ${isSuccess ? (annos.length > 0 ? `어법 포인트 ${annos.length}개 발견` : '분석 완료 (해당사항 없음)') : '분석 실패'}
              </span>
            </div>
            <div class="batch-log-item-badges">${badgesHtml}</div>
          `;

        // 배치 로그 내 배지 클릭 시에도 해설 팝오버 지원
        logItem.querySelectorAll(".grammar-tag-badge").forEach((b) => {
          b.addEventListener("click", (e) => {
            e.stopPropagation();
            const aIdx = parseInt(b.dataset.idx, 10);
            const anno = (annos && annos[aIdx]) ? annos[aIdx] : null;
            if (anno) showGrammarPopover(anno, b);
          });
        });

        batchLogList.appendChild(logItem);
        batchLogList.scrollTop = batchLogList.scrollHeight;
      }

    } catch (netErr) {
      console.error("문장 분석 통신 오류:", netErr);
      if (batchLogList) {
        const logItem = document.createElement("div");
        logItem.className = "batch-log-item error";
        logItem.innerHTML = `
            <div class="batch-log-item-header">
              <span class="batch-log-item-id">${escapeHtml(sent.id || `문장 #${i + 1}`)}</span>
              <span class="batch-log-item-status" style="color: var(--danger);">네트워크 통신 오류</span>
            </div>
          `;
        batchLogList.appendChild(logItem);
        batchLogList.scrollTop = batchLogList.scrollHeight;
      }
    }

    // 진행률 막대 및 카운터 업데이트
    const finishedCount = i + 1;
    const percent = Math.round((finishedCount / totalCount) * 100);
    if (batchProgressLabel) batchProgressLabel.textContent = `진행률: ${percent}%`;
    if (batchProgressBar) batchProgressBar.style.width = `${percent}%`;
    if (batchProgressCounter) batchProgressCounter.textContent = `${finishedCount} / ${totalCount} 문장 완료`;
    if (batchLogCount) batchLogCount.textContent = `${finishedCount}건`;
  }

  // 완료 또는 중단 후 모달 상태 전환
  if (btnCancelBatchAnalysis) btnCancelBatchAnalysis.style.display = "none";
  if (btnCloseBatchModal) btnCloseBatchModal.style.display = "inline-flex";

  if (isCancelled) {
    if (batchModalStatusBadge) {
      batchModalStatusBadge.className = "batch-status-badge stopped";
      batchModalStatusBadge.innerHTML = "⏹️ 분석 중단됨";
    }
    if (batchCurrentSentId) batchCurrentSentId.textContent = "중단됨";
    if (batchCurrentSentText) batchCurrentSentText.textContent = "사용자에 의해 분석이 중단되었습니다.";
    if (batchFooterInfo) {
      batchFooterInfo.innerHTML = `총 ${totalCount}개 대상 중 ${successCount}개 문장 분석 완료 후 중단되었습니다.`;
    }
  } else {
    if (batchModalStatusBadge) {
      batchModalStatusBadge.className = "batch-status-badge completed";
      batchModalStatusBadge.innerHTML = "✔ 분석 완료";
    }
    if (batchCurrentSentId) batchCurrentSentId.textContent = "완료";
    if (batchCurrentSentText) batchCurrentSentText.textContent = "모든 대상 문장의 AI 어법 분석이 성공적으로 완료되었습니다!";
    if (batchFooterInfo) {
      batchFooterInfo.innerHTML = `총 ${totalCount}개 대상 문장 중 ${successCount}개 어법 분석 완료!`;
    }
  }

  // 일괄 분석 버튼 복원
  if (btnBatchAnalyzeStarred) btnBatchAnalyzeStarred.disabled = false;
  if (btnBatchAnalyzeAll) btnBatchAnalyzeAll.disabled = false;

  // 닫기 버튼 이벤트 설정 (모달 닫고 결과 반영)
  btnCloseBatchModal.onclick = () => {
    batchAnalysisModal.style.display = "none";
    if (successCount > 0) {
      showToast(`성공적으로 ${successCount}개 문장의 어법 분석 결과를 반영했습니다!`, "success");
      refreshCurrentSentenceView();
    }
  };
}

// ---- 이벤트 바인딩 및 초기화 (main.js 에서 원본 순서대로 호출) ----
export function init() {

  if (btnCloseGrammarModal) btnCloseGrammarModal.addEventListener("click", closeGrammarCategoryModal);
  if (btnCancelGrammarModal) btnCancelGrammarModal.addEventListener("click", closeGrammarCategoryModal);

  // 모달 배경 클릭 시 닫기
  if (grammarCategoryModal) {
    grammarCategoryModal.addEventListener("click", (e) => {
      if (e.target === grammarCategoryModal) {
        closeGrammarCategoryModal();
      }
    });
  }

  // ESC 키 입력 시 모달 닫기
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      if (grammarCategoryModal && grammarCategoryModal.style.display !== "none") {
        closeGrammarCategoryModal();
      } else if (batchAnalysisModal && batchAnalysisModal.style.display !== "none" && btnCloseBatchModal && btnCloseBatchModal.style.display !== "none") {
        btnCloseBatchModal.click();
      }
    }
  });
  loadGrammarCategories();

  // 상단 브레드크럼 홈 아이콘 클릭 -> 1단계로 복귀
  if (grammarBreadcrumbHome) {
    grammarBreadcrumbHome.addEventListener("click", () => {
      if (inputGrammarSearch) inputGrammarSearch.value = "";
      grammarSearchTerm = "";
      if (btnClearGrammarSearch) btnClearGrammarSearch.style.display = "none";
      grammarNavState = { pos: null, subPos: null, mode: "step" };
      renderGrammarModalView();
    });
  }

  // 단계 변경 / 검색 지우기 버튼
  if (btnGrammarChangeStep) {
    btnGrammarChangeStep.addEventListener("click", () => {
      if (grammarSearchTerm) {
        if (inputGrammarSearch) inputGrammarSearch.value = "";
        grammarSearchTerm = "";
        if (btnClearGrammarSearch) btnClearGrammarSearch.style.display = "none";
        renderGrammarModalView();
        return;
      }
      if (grammarNavState.subPos) {
        grammarNavState.subPos = null;
      } else if (grammarNavState.pos) {
        grammarNavState.pos = null;
      }
      renderGrammarModalView();
    });
  }

  // 전체 보기 <-> 단계별 탐색 전환 버튼
  if (btnGrammarToggleView) {
    btnGrammarToggleView.addEventListener("click", () => {
      if (grammarSearchTerm) {
        if (inputGrammarSearch) inputGrammarSearch.value = "";
        grammarSearchTerm = "";
        if (btnClearGrammarSearch) btnClearGrammarSearch.style.display = "none";
      }
      grammarNavState.mode = grammarNavState.mode === "all" ? "step" : "all";
      renderGrammarModalView();
    });
  }

  if (inputGrammarSearch) {
    inputGrammarSearch.addEventListener("input", () => {
      grammarSearchTerm = inputGrammarSearch.value;
      if (btnClearGrammarSearch) {
        btnClearGrammarSearch.style.display = grammarSearchTerm ? "block" : "none";
      }
      renderGrammarModalView();
    });
  }

  if (btnClearGrammarSearch) {
    btnClearGrammarSearch.addEventListener("click", () => {
      if (inputGrammarSearch) inputGrammarSearch.value = "";
      grammarSearchTerm = "";
      btnClearGrammarSearch.style.display = "none";
      renderGrammarModalView();
    });
  }

  if (btnResetGrammarSelection) {
    btnResetGrammarSelection.addEventListener("click", () => {
      selectedGrammarCategoryIds.clear();
      renderGrammarModalView();
      updateGrammarModalPreview();
    });
  }

  if (btnApplyGrammarSelection) {
    btnApplyGrammarSelection.addEventListener("click", async () => {
      if (!activeGrammarModalSentence) return;
      btnApplyGrammarSelection.disabled = true;
      btnApplyGrammarSelection.textContent = "⏳ 저장 중...";

      const selectedItems = Array.from(selectedGrammarCategoryIds).map(id => {
        const found = grammarCategoriesList.find(c => c.id === id);
        if (found) {
          return {
            category_id: found.id,
            pos: found.pos,
            full_path: found.full_path,
            leaf_name: found.leaf,
            explanation: `사용자 분석 (${found.full_path})`,
            source_type: "USER"
          };
        }
        return null;
      }).filter(Boolean);

      try {
        const res = await fetch(`/api/sentences/${encodeURIComponent(activeGrammarModalSentence.id)}/grammar-annotations/batch`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ 
            annotations: selectedItems,
            source_type: "USER"
          })
        });
        const data = await res.json();
        if (res.ok && data.success) {
          activeGrammarModalSentence.grammar_annotations = data.annotations || [];
          activeGrammarModalSentence.grammar_analyzed = 1;
          if (typeof activeGrammarModalCallback === "function") {
            activeGrammarModalCallback();
          }
          showToast(`어법 범주 ${selectedItems.length}개가 저장되었습니다.`, "success");
          closeGrammarCategoryModal();
        } else {
          showToast(data.detail || "어법 범주 일괄 저장 실패", "error");
        }
      } catch (err) {
        console.error("Batch grammar save error:", err);
        showToast("어법 범주 저장 중 오류가 발생했습니다.", "error");
      } finally {
        btnApplyGrammarSelection.disabled = false;
        btnApplyGrammarSelection.textContent = "✔ 선택 완료 및 적용";
      }
    });
  }

  // 홈 어법 필터 바 '설정 초기화' 버튼 이벤트
  if (btnResetHomeGrammarFilter) {
    btnResetHomeGrammarFilter.addEventListener("click", () => {
      resetAllGrammarFilters(false);
      showToast("어법 필터 설정이 초기화되었습니다.", "info");
    });
  }

  // 결과창 어법 필터 바 '설정 초기화' 버튼 이벤트
  if (btnResetResultsGrammarFilter) {
    btnResetResultsGrammarFilter.addEventListener("click", () => {
      resetAllGrammarFilters(true);
      showToast("어법 필터 설정이 초기화되었습니다.", "info");
    });
  }

  if (filterGrammarPos) {
    filterGrammarPos.addEventListener("change", () => {
      const pos = filterGrammarPos.value;
      if (resultsFilterGrammarPos) resultsFilterGrammarPos.value = pos;
      updateSubGrammarCategories(pos, filterGrammarCategory);
      updateSubGrammarCategories(pos, resultsFilterGrammarCategory);
      updateGrammarBreadcrumbFilterUI();
    });
  }

  if (resultsFilterGrammarPos) {
    resultsFilterGrammarPos.addEventListener("change", () => {
      const pos = resultsFilterGrammarPos.value;
      if (filterGrammarPos) filterGrammarPos.value = pos;
      updateSubGrammarCategories(pos, filterGrammarCategory);
      updateSubGrammarCategories(pos, resultsFilterGrammarCategory);
      updateGrammarBreadcrumbFilterUI();
      if (appState.isSearchWithinActive && appState.rawSentencesData && appState.rawSentencesData.length > 0) {
        executeSearchWithinResults();
      } else {
        refreshCurrentSentenceView();
      }
    });
  }

  if (filterGrammarCategory) {
    filterGrammarCategory.addEventListener("change", () => {
      if (resultsFilterGrammarCategory) resultsFilterGrammarCategory.value = filterGrammarCategory.value;
      updateGrammarBreadcrumbFilterUI();
    });
  }
  if (resultsFilterGrammarCategory) {
    resultsFilterGrammarCategory.addEventListener("change", () => {
      if (filterGrammarCategory) filterGrammarCategory.value = resultsFilterGrammarCategory.value;
      updateGrammarBreadcrumbFilterUI();
      if (appState.isSearchWithinActive && appState.rawSentencesData && appState.rawSentencesData.length > 0) {
        executeSearchWithinResults();
      } else {
        refreshCurrentSentenceView();
      }
    });
  }

  if (btnToggleStarred) {
    btnToggleStarred.addEventListener("click", () => {
      setStarredFilter(!appState.isStarredFilterActive);
    });
  }
  if (btnResultsToggleStarred) {
    btnResultsToggleStarred.addEventListener("click", () => {
      setStarredFilter(!appState.isStarredFilterActive);
      if (appState.isSearchWithinActive && appState.rawSentencesData && appState.rawSentencesData.length > 0) {
        executeSearchWithinResults();
      } else {
        refreshCurrentSentenceView();
      }
    });
  }

  // 모달 바깥 배경 클릭 시(분석 완료 시에만 닫기)
  if (batchAnalysisModal) {
    batchAnalysisModal.addEventListener("click", (e) => {
      if (e.target === batchAnalysisModal && btnCloseBatchModal && btnCloseBatchModal.style.display !== "none") {
        btnCloseBatchModal.click();
      }
    });
  }

  // 중요 문장 일괄 AI 분석 (이미 분석된 문장 제외)
  if (btnBatchAnalyzeStarred) {
    btnBatchAnalyzeStarred.addEventListener("click", async () => {
      const starredSentences = appState.sentencesData.filter((s) => s.is_starred === 1 || s.is_starred === true);
      if (starredSentences.length === 0) {
        showToast("별표(⭐) 표시된 중요 문장이 없습니다. 먼저 문장에 별표를 추가해 주세요.", "warning");
        return;
      }

      // 이미 어법 분석이 완료된 중요 문장 제외 (어법 배지가 있거나, 분석 결과 해당사항 없음인 문장 모두 제외)
      const targetStarred = starredSentences.filter(
        (s) => !s.grammar_analyzed && (!s.grammar_annotations || s.grammar_annotations.length === 0)
      );

      if (targetStarred.length === 0) {
        showToast(`별표 표시된 중요 문장(${starredSentences.length}개)은 이미 모두 어법 분석이 완료되어 있습니다! 👍`, "info");
        return;
      }

      const totalCount = targetStarred.length;
      const alreadyCount = starredSentences.length - totalCount;
      const confirmMsg = alreadyCount > 0
        ? `별표(⭐) 중요 문장 ${starredSentences.length}개 중 이미 분석된 ${alreadyCount}개를 제외하고,\n미분석 문장 ${totalCount}개를 일괄 AI 어법 분석하시겠습니까?`
        : `현재 별표(⭐) 표시된 ${totalCount}개 중요 문장을 일괄 AI 어법 분석하시겠습니까?`;

      if (!confirm(confirmMsg)) {
        return;
      }

      await runBatchAnalysisModal(targetStarred, true);
    });
  }

  // 모든 문장 일괄 AI 분석 (이미 분석된 문장 제외)
  if (btnBatchAnalyzeAll) {
    btnBatchAnalyzeAll.addEventListener("click", async () => {
      if (!appState.sentencesData || appState.sentencesData.length === 0) {
        showToast("분석할 문장이 없습니다. 먼저 문장을 검색해 주세요.", "warning");
        return;
      }

      // 이미 어법 분석이 완료된 문장 제외 (어법 배지가 있거나, 분석 결과 해당사항 없음인 문장 모두 제외)
      const targetSentences = appState.sentencesData.filter(
        (s) => !s.grammar_analyzed && (!s.grammar_annotations || s.grammar_annotations.length === 0)
      );

      if (targetSentences.length === 0) {
        showToast(`현재 결과창의 모든 문장(${appState.sentencesData.length}개)은 이미 어법 분석이 완료되어 있습니다! 👍`, "info");
        return;
      }

      const totalTargetCount = targetSentences.length;
      const alreadyCount = appState.sentencesData.length - totalTargetCount;
      const confirmMsg = alreadyCount > 0
        ? `전체 ${appState.sentencesData.length}개 문장 중 이미 분석된 ${alreadyCount}개를 제외하고,\n미분석 문장 ${totalTargetCount}개를 일괄 AI 어법 분석하시겠습니까?`
        : `현재 결과창의 미분석 ${totalTargetCount}개 문장을 일괄 AI 어법 분석하시겠습니까?\n(실시간 진행 모달 창에서 문장별 어법 포인트를 실시간으로 확인하실 수 있습니다.)`;

      if (!confirm(confirmMsg)) {
        return;
      }

      await runBatchAnalysisModal(targetSentences, false);
    });
  }

  // 커스텀 어법 체계 관리 모달 연동
  initCustomGrammarTreeModal();
}

/**
 * 나만의 커스텀 어법 체계 관리 모달 (직관적 시각 편집기) 초기화
 */
function initCustomGrammarTreeModal() {
  if (!btnManageGrammarTree || !customGrammarTreeModal) return;

  // 메모리 상의 243개 어법 항목 상태 목록
  // { id, pos, path, full_path, leaf, original_leaf, custom_leaf, is_enabled }
  let visualItems = [];
  let standardFallbackList = [];
  let currentActiveTab = "visual"; // 'visual' | 'json'
  let selectedCategoryKey = "ALL"; // 'ALL' | 'POS:동사' | 'PATH:동사 > 시제'
  let treeExpandedState = new Map(); // key -> boolean

  const closeCustomModal = () => {
    const modalContent = customGrammarTreeModal.querySelector(".modal-custom-tree-content");
    if (modalContent) modalContent.classList.remove("is-fullscreen");
    if (btnToggleCustomTreeFullscreen) {
      btnToggleCustomTreeFullscreen.textContent = "⛶";
      btnToggleCustomTreeFullscreen.title = "전체 화면으로 확대";
    }
    customGrammarTreeModal.style.display = "none";
  };

  if (btnCloseCustomTreeModal) btnCloseCustomTreeModal.addEventListener("click", closeCustomModal);
  if (btnCancelCustomTreeModal) btnCancelCustomTreeModal.addEventListener("click", closeCustomModal);

  // 전체 화면 토글 핸들러
  if (btnToggleCustomTreeFullscreen) {
    btnToggleCustomTreeFullscreen.addEventListener("click", () => {
      const modalContent = customGrammarTreeModal.querySelector(".modal-custom-tree-content");
      if (!modalContent) return;
      const isFs = modalContent.classList.toggle("is-fullscreen");
      btnToggleCustomTreeFullscreen.textContent = isFs ? "🗗" : "⛶";
      btnToggleCustomTreeFullscreen.title = isFs ? "기본 창 크기로 복원" : "전체 화면으로 확대";
    });
  }

  // 탭 전환 핸들러 (시각적 탐색 편집기 vs JSON 직접 편집)
  if (tabBtnVisualEditor && tabBtnJsonEditor) {
    tabBtnVisualEditor.addEventListener("click", () => {
      currentActiveTab = "visual";
      tabBtnVisualEditor.classList.add("active");
      tabBtnJsonEditor.classList.remove("active");
      if (paneVisualEditor) paneVisualEditor.style.display = "flex";
      if (paneJsonEditor) paneJsonEditor.style.display = "none";
      renderVisualExplorer();
    });

    tabBtnJsonEditor.addEventListener("click", () => {
      currentActiveTab = "json";
      tabBtnJsonEditor.classList.add("active");
      tabBtnVisualEditor.classList.remove("active");
      if (paneVisualEditor) paneVisualEditor.style.display = "none";
      if (paneJsonEditor) paneJsonEditor.style.display = "flex";
      syncVisualToJson();
    });
  }

  // 표준 243개 템플릿 로드 함수
  async function loadStandardTemplate() {
    if (standardFallbackList && standardFallbackList.length > 0) return standardFallbackList;
    try {
      const res = await fetch("/static/data/grammar_categories.json");
      if (res.ok) {
        const stdJson = await res.json();
        standardFallbackList = stdJson.list || [];
        return standardFallbackList;
      }
    } catch (e) {
      console.error("Standard template load error:", e);
    }
    return grammarCategoriesList || [];
  }

  // 시각적 편집 상태 -> JSON 에디터 동기화
  function syncVisualToJson() {
    if (!customTreeJsonEditor) return;
    const activeList = visualItems
      .filter(item => item.is_enabled)
      .map(item => {
        const effectiveLeaf = (item.custom_leaf && item.custom_leaf.trim()) ? item.custom_leaf.trim() : item.original_leaf;
        let effectiveFullPath = item.full_path;
        if (effectiveLeaf !== item.original_leaf) {
          const parts = item.full_path.split(" > ");
          parts[parts.length - 1] = effectiveLeaf;
          effectiveFullPath = parts.join(" > ");
        }
        return {
          id: item.id,
          pos: item.pos,
          full_path: effectiveFullPath,
          leaf: effectiveLeaf,
          original_leaf: item.original_leaf
        };
      });

    const exportObj = {
      meta: {
        title: "사용자 커스텀 어법 체계",
        total_items: activeList.length,
        updated_at: new Date().toISOString()
      },
      list: activeList
    };
    customTreeJsonEditor.value = JSON.stringify(exportObj, null, 2);
  }

  // 상단 헤더 통계 뱃지 갱신
  function updateGlobalStats() {
    const total = visualItems.length;
    const active = visualItems.filter(i => i.is_enabled).length;
    const modified = visualItems.filter(i => i.custom_leaf && i.custom_leaf.trim() !== i.original_leaf).length;
    const hidden = total - active;

    if (statTotalGrammar) statTotalGrammar.textContent = String(total);
    if (statActiveGrammar) statActiveGrammar.textContent = String(active);
    if (statModifiedGrammar) statModifiedGrammar.textContent = String(modified);
    if (statHiddenGrammar) statHiddenGrammar.textContent = String(hidden);
  }

  // 검색어 하이라이트 헬퍼
  function highlightSearch(text, query) {
    if (!query || !text) return escapeHtml(text || "");
    const escaped = escapeHtml(text);
    const escapedQuery = query.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    const regex = new RegExp(`(${escapedQuery})`, "gi");
    return escaped.replace(regex, '<mark class="tree-search-mark">$1</mark>');
  }

  // 항목이 현재 검색어/수정 필터에 일치하는지 판별
  function matchesFilter(item, query, onlyModified) {
    if (onlyModified) {
      const isMod = item.custom_leaf && item.custom_leaf.trim() !== item.original_leaf;
      if (!isMod) return false;
    }
    if (query) {
      const q = query.toLowerCase();
      const matchName = (item.leaf || "").toLowerCase().includes(q);
      const matchCustom = (item.custom_leaf || "").toLowerCase().includes(q);
      const matchPath = (item.full_path || "").toLowerCase().includes(q);
      const matchId = String(item.id).includes(q);
      const matchPos = (item.pos || "").toLowerCase().includes(q);
      if (!matchName && !matchCustom && !matchPath && !matchId && !matchPos) return false;
    }
    return true;
  }

  // =========================================================================
  // 2-Pane Explorer: 계층 트리 구조 빌더 (사이드바용)
  // =========================================================================
  function buildSidebarTreeModel(query = "", onlyModified = false) {
    const posOrder = ["명사", "대명사", "문장", "주어", "동사", "형용사", "부사", "전치사", "접속사", "특수구문"];
    const posNodes = [];

    posOrder.forEach(pos => {
      const posItems = visualItems.filter(it => it.pos === pos);
      if (posItems.length === 0) return;

      const posNode = {
        key: "POS:" + pos,
        name: pos,
        fullPath: pos,
        isPos: true,
        items: posItems,
        children: new Map(), // name -> subNode
        stats: { total: posItems.length, active: 0, modified: 0, hidden: 0 },
        matchingItems: []
      };

      // 하위 카테고리 계층 구축 (리프 제외한 중간 폴더 경로)
      posItems.forEach(item => {
        const rawPath = (item.path && item.path.length > 0)
          ? item.path
          : (item.full_path ? item.full_path.split(" > ") : [item.pos, item.leaf]);
        
        const segments = (rawPath[0] === pos) ? rawPath.slice(1) : rawPath;
        // 마지막 리프 어법명을 제외한 폴더 세그먼트들
        const folderSegments = segments.slice(0, segments.length - 1);

        let curr = posNode;
        let currPath = pos;
        folderSegments.forEach(seg => {
          currPath += " > " + seg;
          if (!curr.children.has(seg)) {
            curr.children.set(seg, {
              key: "PATH:" + currPath,
              name: seg,
              fullPath: currPath,
              isPos: false,
              items: [],
              children: new Map(),
              stats: { total: 0, active: 0, modified: 0, hidden: 0 },
              matchingItems: []
            });
          }
          curr = curr.children.get(seg);
          curr.items.push(item);
        });
      });

      // 통계 계산 헬퍼
      function calcStats(node) {
        node.stats = {
          total: node.items.length,
          active: node.items.filter(i => i.is_enabled).length,
          modified: node.items.filter(i => i.custom_leaf && i.custom_leaf.trim() !== i.original_leaf).length,
          hidden: node.items.filter(i => !i.is_enabled).length
        };
        node.matchingItems = node.items.filter(i => matchesFilter(i, query, onlyModified));

        for (const child of node.children.values()) {
          calcStats(child);
        }
      }

      calcStats(posNode);
      posNodes.push(posNode);
    });

    return posNodes;
  }

  // =========================================================================
  // 2-Pane Explorer: 좌측 트리 사이드바 렌더러
  // =========================================================================
  function renderSidebar(treeModel, query = "", onlyModified = false) {
    if (!sidebarTreeContainer) return;

    // 루트 '전체 어법' 노드 통계 계산
    const allFilteredItems = visualItems.filter(i => matchesFilter(i, query, onlyModified));
    const allTotal = visualItems.length;

    let html = `
      <div class="sidebar-tree-row ${selectedCategoryKey === 'ALL' ? 'active' : ''}" data-cat-key="ALL" title="모든 품사의 243개 어법을 한 번에 확인합니다.">
        <span class="sidebar-node-icon">📚</span>
        <span class="sidebar-node-label" style="font-weight: 700;">전체 어법 (모든 품사)</span>
        <span class="sidebar-node-badge">${query || onlyModified ? `${allFilteredItems.length}/${allTotal}` : allTotal}</span>
      </div>
    `;

    // 하위 폴더 렌더링 재귀 헬퍼
    function renderFolderNodeHtml(node) {
      if (node.matchingItems.length === 0 && (query || onlyModified)) {
        return ""; // 검색 조건에 맞는 항목이 없으면 숨김
      }

      // 검색어가 있으면 자동 펼침, 그렇지 않으면 treeExpandedState 따름 (기본 펼침)
      const isCollapsed = query ? false : (treeExpandedState.has(node.key) ? !treeExpandedState.get(node.key) : false);
      const isSelected = selectedCategoryKey === node.key;
      const countText = (query || onlyModified) ? `${node.matchingItems.length}/${node.stats.total}` : `${node.stats.total}`;

      let childrenHtml = "";
      if (node.children.size > 0) {
        for (const child of node.children.values()) {
          childrenHtml += renderFolderNodeHtml(child);
        }
      }

      const hasChildren = node.children.size > 0;

      return `
        <div class="sidebar-tree-node" data-cat-key="${escapeHtml(node.key)}">
          <div class="sidebar-tree-row ${isSelected ? 'active' : ''}" data-cat-key="${escapeHtml(node.key)}" title="${escapeHtml(node.fullPath)}">
            ${hasChildren 
              ? `<span class="sidebar-node-toggle ${isCollapsed ? 'is-collapsed' : ''}" data-toggle-key="${escapeHtml(node.key)}">${isCollapsed ? '▶' : '▼'}</span>` 
              : `<span class="sidebar-node-toggle" style="opacity: 0.2; pointer-events: none;">•</span>`}
            <span class="sidebar-node-icon">${hasChildren ? (isCollapsed ? '📁' : '📂') : '🏷️'}</span>
            <span class="sidebar-node-label">${highlightSearch(node.name, query)}</span>
            <span class="sidebar-node-badge">${countText}</span>
          </div>
          ${hasChildren ? `
            <div class="sidebar-tree-children ${isCollapsed ? 'collapsed' : ''}">
              ${childrenHtml}
            </div>
          ` : ''}
        </div>
      `;
    }

    // 각 품사 노드 렌더링
    treeModel.forEach(posNode => {
      html += renderFolderNodeHtml(posNode);
    });

    sidebarTreeContainer.innerHTML = html;

    // 사이드바 이벤트 바인딩
    // 1. 접기/펼치기 토글
    sidebarTreeContainer.querySelectorAll(".sidebar-node-toggle").forEach(toggle => {
      toggle.addEventListener("click", (e) => {
        e.stopPropagation();
        const key = toggle.dataset.toggleKey;
        if (!key) return;
        const currentCollapsed = toggle.classList.contains("is-collapsed");
        treeExpandedState.set(key, currentCollapsed); // 접혀있었으면 true(펼침), 펼쳐있었으면 false(접음)
        renderVisualExplorer();
      });
    });

    // 2. 카테고리 선택
    sidebarTreeContainer.querySelectorAll(".sidebar-tree-row").forEach(row => {
      row.addEventListener("click", () => {
        const catKey = row.dataset.catKey;
        if (!catKey) return;
        selectedCategoryKey = catKey;
        // 사이드바 active 행 즉시 교체
        sidebarTreeContainer.querySelectorAll(".sidebar-tree-row").forEach(r => r.classList.remove("active"));
        row.classList.add("active");
        renderDetailPane(query, onlyModified);
      });
    });
  }

  // =========================================================================
  // 2-Pane Explorer: 우측 상세 편집 패널 렌더러
  // =========================================================================
  function renderDetailPane(query = "", onlyModified = false) {
    if (!detailCardGrid) return;

    // 1. 현재 선택된 카테고리에 속한 어법 목록 추출
    let scopedItems = [];
    let breadcrumbTitle = "";
    let breadcrumbChain = [];

    if (selectedCategoryKey === "ALL") {
      scopedItems = visualItems;
      breadcrumbTitle = "전체 어법 체계";
      breadcrumbChain = [{ name: "📚 전체 어법 체계", key: "ALL" }];
    } else if (selectedCategoryKey.startsWith("POS:")) {
      const pos = selectedCategoryKey.substring(4);
      scopedItems = visualItems.filter(it => it.pos === pos);
      breadcrumbTitle = `${pos} 어법 체계`;
      breadcrumbChain = [
        { name: "📚 전체", key: "ALL" },
        { name: pos, key: selectedCategoryKey }
      ];
    } else if (selectedCategoryKey.startsWith("PATH:")) {
      const pathStr = selectedCategoryKey.substring(5);
      scopedItems = visualItems.filter(it => it.full_path === pathStr || it.full_path.startsWith(pathStr + " > "));
      const segments = pathStr.split(" > ");
      breadcrumbChain = [{ name: "📚 전체", key: "ALL" }];
      let builtPath = "";
      segments.forEach((seg, idx) => {
        if (idx === 0) {
          builtPath = seg;
          breadcrumbChain.push({ name: seg, key: "POS:" + seg });
        } else {
          builtPath += " > " + seg;
          breadcrumbChain.push({ name: seg, key: "PATH:" + builtPath });
        }
      });
      breadcrumbTitle = segments.join(" > ");
    }

    // 2. 검색어 및 수정됨 필터 적용
    const filteredCards = scopedItems.filter(it => matchesFilter(it, query, onlyModified));

    // 3. 브레드크럼 UI 업데이트
    if (detailBreadcrumb) {
      detailBreadcrumb.innerHTML = breadcrumbChain.map((crumb, idx) => {
        const isLast = idx === breadcrumbChain.length - 1;
        if (isLast) {
          return `<span class="breadcrumb-item active" style="color: var(--primary); font-weight: 700;">${escapeHtml(crumb.name)}</span>`;
        } else {
          return `<span class="breadcrumb-item breadcrumb-link" data-cat-key="${escapeHtml(crumb.key)}" style="cursor: pointer; color: var(--text-muted); text-decoration: underline;" title="${escapeHtml(crumb.name)} 카테고리로 이동">${escapeHtml(crumb.name)}</span> <span style="color: var(--text-muted); font-size: 0.75rem;">&gt;</span>`;
        }
      }).join(" ");

      detailBreadcrumb.querySelectorAll(".breadcrumb-link").forEach(link => {
        link.addEventListener("click", () => {
          selectedCategoryKey = link.dataset.catKey;
          renderVisualExplorer();
        });
      });
    }

    // 4. 통계 뱃지 업데이트
    const activeCount = filteredCards.filter(i => i.is_enabled).length;
    const modifiedCount = filteredCards.filter(i => i.custom_leaf && i.custom_leaf.trim() !== i.original_leaf).length;
    const hiddenCount = filteredCards.length - activeCount;

    if (detailCountBadge) {
      detailCountBadge.textContent = `총 ${filteredCards.length}개 어법`;
    }
    if (detailSubstat) {
      detailSubstat.textContent = `사용 ${activeCount} · 수정 ${modifiedCount} · 숨김 ${hiddenCount}`;
    }

    // 5. 카드 그리드 렌더링
    if (filteredCards.length === 0) {
      detailCardGrid.innerHTML = `
        <div style="grid-column: 1 / -1; padding: 3.5rem 1rem; text-align: center; color: var(--text-muted);">
          <div style="font-size: 2rem; margin-bottom: 8px;">🔍</div>
          <strong style="font-size: 0.95rem; color: var(--text-main);">조건에 일치하는 어법 항목이 없습니다.</strong>
          <p style="font-size: 0.8rem; margin-top: 4px;">검색어를 변경하거나 좌측 트리에서 다른 카테고리를 선택해 보세요.</p>
        </div>
      `;
      return;
    }

    const cardsHtml = filteredCards.map(item => {
      const isMod = item.custom_leaf && item.custom_leaf.trim() !== item.original_leaf;
      const isHidden = !item.is_enabled;
      const currentValue = item.custom_leaf !== undefined ? item.custom_leaf : item.original_leaf;

      return `
        <div class="grammar-editor-card ${isMod ? 'modified' : ''} ${isHidden ? 'hidden-item' : ''}" data-id="${item.id}">
          <div class="card-header-row">
            <div class="card-id-wrap">
              <input type="checkbox" class="card-enable-chk" data-id="${item.id}" ${!isHidden ? "checked" : ""} title="${isHidden ? '현재 숨김 상태 (체크하여 사용)' : '현재 사용 중 (체크 해제하여 숨김)'}">
              <span class="card-id-badge">#${item.id}</span>
              <strong class="card-leaf-title" title="표준 명칭: ${escapeHtml(item.original_leaf)}">${highlightSearch(item.original_leaf, query)}</strong>
            </div>
            <div class="card-badges-wrap">
              ${isMod ? '<span class="card-badge-modified">✏️ 수정됨</span>' : ''}
              ${isHidden ? '<span class="card-badge-hidden">🚫 숨김</span>' : ''}
              ${isMod ? `<button type="button" class="btn-card-revert" data-id="${item.id}" title="표준 명칭('${escapeHtml(item.original_leaf)}')으로 복원">↺ 원래대로</button>` : ''}
            </div>
          </div>
          <div class="card-path-row" title="${escapeHtml(item.full_path)}">
            📂 ${escapeHtml(item.full_path)}
          </div>
          <div class="card-input-row">
            <span class="card-input-label">내 어법 명칭:</span>
            <div class="card-input-wrapper">
              <input 
                type="text" 
                class="card-text-input" 
                data-id="${item.id}" 
                value="${escapeHtml(currentValue)}" 
                placeholder="${escapeHtml(item.original_leaf)}"
                title="나만의 어법 명칭을 입력하세요"
              >
            </div>
          </div>
        </div>
      `;
    }).join("");

    detailCardGrid.innerHTML = cardsHtml;

    // 6. 카드 이벤트 바인딩
    // (1) 사용/숨김 체크박스
    detailCardGrid.querySelectorAll(".card-enable-chk").forEach(chk => {
      chk.addEventListener("change", () => {
        const id = Number(chk.dataset.id);
        const item = visualItems.find(x => x.id === id);
        if (item) {
          item.is_enabled = chk.checked;
          const card = chk.closest(".grammar-editor-card");
          if (card) {
            if (item.is_enabled) card.classList.remove("hidden-item");
            else card.classList.add("hidden-item");
          }
          updateGlobalStats();
          // 통계 갱신
          const curActive = filteredCards.filter(i => i.is_enabled).length;
          const curHidden = filteredCards.length - curActive;
          if (detailSubstat) {
            detailSubstat.textContent = `사용 ${curActive} · 수정 ${modifiedCount} · 숨김 ${curHidden}`;
          }
        }
      });
    });

    // (2) 인라인 명칭 수정
    detailCardGrid.querySelectorAll(".card-text-input").forEach(input => {
      input.addEventListener("input", () => {
        const id = Number(input.dataset.id);
        const item = visualItems.find(x => x.id === id);
        if (item) {
          item.custom_leaf = input.value;
          const card = input.closest(".grammar-editor-card");
          const isMod = item.custom_leaf.trim() !== item.original_leaf;
          if (card) {
            if (isMod) card.classList.add("modified");
            else card.classList.remove("modified");
          }
          updateGlobalStats();
        }
      });
    });

    // (3) 원래대로 복원 버튼
    detailCardGrid.querySelectorAll(".btn-card-revert").forEach(btn => {
      btn.addEventListener("click", () => {
        const id = Number(btn.dataset.id);
        const item = visualItems.find(x => x.id === id);
        if (item) {
          item.custom_leaf = item.original_leaf;
          renderDetailPane(query, onlyModified);
          updateGlobalStats();
        }
      });
    });
  }

  // =========================================================================
  // 전체 탐색기 렌더링 오케스트레이터
  // =========================================================================
  function renderVisualExplorer() {
    const query = (inputCustomTreeSearch ? inputCustomTreeSearch.value : "").trim().toLowerCase();
    const onlyModified = chkOnlyModified ? chkOnlyModified.checked : false;

    if (btnClearCustomTreeSearch) {
      btnClearCustomTreeSearch.style.display = query ? "block" : "none";
    }

    updateGlobalStats();

    // 1. 트리 모델 구축
    const treeModel = buildSidebarTreeModel(query, onlyModified);

    // 2. 좌측 사이드바 렌더링
    renderSidebar(treeModel, query, onlyModified);

    // 3. 우측 상세 패널 렌더링
    renderDetailPane(query, onlyModified);
  }

  // =========================================================================
  // 툴바 버튼 이벤트 바인딩
  // =========================================================================
  // 1. 검색창 입력 & 초기화
  if (inputCustomTreeSearch) {
    inputCustomTreeSearch.addEventListener("input", () => {
      renderVisualExplorer();
    });
  }

  if (btnClearCustomTreeSearch) {
    btnClearCustomTreeSearch.addEventListener("click", () => {
      if (inputCustomTreeSearch) inputCustomTreeSearch.value = "";
      renderVisualExplorer();
    });
  }

  // 2. 수정됨만 필터
  if (chkOnlyModified) {
    chkOnlyModified.addEventListener("change", () => {
      renderVisualExplorer();
    });
  }

  // 3. 사이드바 전체 펼치기 / 접기
  if (btnExpandAllTree) {
    btnExpandAllTree.addEventListener("click", () => {
      treeExpandedState.clear();
      // 모든 키를 true로 설정
      const model = buildSidebarTreeModel();
      function expandAll(node) {
        treeExpandedState.set(node.key, true);
        for (const child of node.children.values()) expandAll(child);
      }
      model.forEach(expandAll);
      renderVisualExplorer();
    });
  }

  if (btnCollapseAllTree) {
    btnCollapseAllTree.addEventListener("click", () => {
      treeExpandedState.clear();
      // 모든 키를 false로 설정
      const model = buildSidebarTreeModel();
      function collapseAll(node) {
        treeExpandedState.set(node.key, false);
        for (const child of node.children.values()) collapseAll(child);
      }
      model.forEach(collapseAll);
      renderVisualExplorer();
    });
  }

  // 4. 현재 선택된 카테고리 일괄 사용 / 숨김
  if (btnBulkEnableCurrent) {
    btnBulkEnableCurrent.addEventListener("click", () => {
      let targets = [];
      if (selectedCategoryKey === "ALL") {
        targets = visualItems;
      } else if (selectedCategoryKey.startsWith("POS:")) {
        const pos = selectedCategoryKey.substring(4);
        targets = visualItems.filter(i => i.pos === pos);
      } else if (selectedCategoryKey.startsWith("PATH:")) {
        const pathStr = selectedCategoryKey.substring(5);
        targets = visualItems.filter(i => i.full_path === pathStr || i.full_path.startsWith(pathStr + " > "));
      }

      targets.forEach(i => { i.is_enabled = true; });
      showToast(`${targets.length}개 어법이 모두 사용 처리되었습니다.`, "info");
      renderVisualExplorer();
    });
  }

  if (btnBulkDisableCurrent) {
    btnBulkDisableCurrent.addEventListener("click", () => {
      let targets = [];
      if (selectedCategoryKey === "ALL") {
        targets = visualItems;
      } else if (selectedCategoryKey.startsWith("POS:")) {
        const pos = selectedCategoryKey.substring(4);
        targets = visualItems.filter(i => i.pos === pos);
      } else if (selectedCategoryKey.startsWith("PATH:")) {
        const pathStr = selectedCategoryKey.substring(5);
        targets = visualItems.filter(i => i.full_path === pathStr || i.full_path.startsWith(pathStr + " > "));
      }

      targets.forEach(i => { i.is_enabled = false; });
      showToast(`${targets.length}개 어법이 모두 숨김 처리되었습니다.`, "info");
      renderVisualExplorer();
    });
  }

  // =========================================================================
  // 모달 오픈 핸들러
  // =========================================================================
  btnManageGrammarTree.addEventListener("click", async () => {
    const stdList = await loadStandardTemplate();

    let serverSettings = null;
    try {
      const res = await fetch("/api/grammar/settings");
      if (res.ok) serverSettings = await res.json();
    } catch (e) {
      console.error("Load settings error:", e);
    }

    const useCustom = Boolean(serverSettings && serverSettings.use_custom_tree);
    if (toggleUseCustomTree) {
      toggleUseCustomTree.checked = useCustom;
      if (labelUseCustomTree) {
        labelUseCustomTree.textContent = useCustom ? "🟢 커스텀 체계 사용 중" : "⚪ 표준 체계 사용 중";
        labelUseCustomTree.style.color = useCustom ? "#059669" : "var(--text-main)";
      }
    }

    let customMap = {};
    let customEnabledIds = null;

    if (serverSettings && serverSettings.custom_tree_json) {
      try {
        const parsed = JSON.parse(serverSettings.custom_tree_json);
        const cList = parsed.list || (Array.isArray(parsed) ? parsed : []);
        if (cList.length > 0) {
          customEnabledIds = new Set();
          cList.forEach(c => {
            if (c.id) {
              customEnabledIds.add(Number(c.id));
              customMap[c.id] = c.leaf || c.leaf_name || "";
            }
          });
        }
      } catch (e) {
        console.error("Parse custom tree json error:", e);
      }
    }

    visualItems = stdList.map(item => {
      const id = Number(item.id);
      const originalLeaf = item.leaf || item.leaf_name || "";
      const customLeaf = customMap[id] !== undefined ? customMap[id] : originalLeaf;
      const isEnabled = customEnabledIds ? customEnabledIds.has(id) : true;
      return {
        id,
        pos: item.pos || "",
        path: item.path || (item.full_path ? item.full_path.split(" > ") : []),
        full_path: item.full_path || "",
        leaf: originalLeaf,
        original_leaf: originalLeaf,
        custom_leaf: customLeaf,
        is_enabled: isEnabled
      };
    });

    if (inputCustomTreeSearch) inputCustomTreeSearch.value = "";
    if (chkOnlyModified) chkOnlyModified.checked = false;

    currentActiveTab = "visual";
    selectedCategoryKey = "ALL";
    treeExpandedState.clear();

    if (tabBtnVisualEditor) tabBtnVisualEditor.classList.add("active");
    if (tabBtnJsonEditor) tabBtnJsonEditor.classList.remove("active");
    if (paneVisualEditor) paneVisualEditor.style.display = "flex";
    if (paneJsonEditor) paneJsonEditor.style.display = "none";

    renderVisualExplorer();
    syncVisualToJson();

    customGrammarTreeModal.style.display = "flex";
  });

  // 토글 스위치 변경 시 레이블 업데이트
  if (toggleUseCustomTree && labelUseCustomTree) {
    toggleUseCustomTree.addEventListener("change", () => {
      const isChecked = toggleUseCustomTree.checked;
      labelUseCustomTree.textContent = isChecked ? "🟢 커스텀 체계 사용 중" : "⚪ 표준 체계 사용 중";
      labelUseCustomTree.style.color = isChecked ? "#059669" : "var(--text-main)";
    });
  }

  // 표준 243개로 초기화 버튼
  if (btnResetToStandardTree) {
    btnResetToStandardTree.addEventListener("click", async () => {
      if (!confirm("모든 커스텀 어법 수정을 초기화하고, 기본 243개 표준 어법 체계로 복원하시겠습니까?")) return;
      try {
        const res = await fetch("/api/grammar/settings/reset", { method: "POST" });
        if (res.ok) {
          showToast("기본 표준 243개 어법 체계로 복원되었습니다.", "success");
          if (toggleUseCustomTree) toggleUseCustomTree.checked = false;
          if (labelUseCustomTree) {
            labelUseCustomTree.textContent = "⚪ 표준 체계 사용 중";
            labelUseCustomTree.style.color = "var(--text-main)";
          }
          await loadGrammarCategories();
          renderGrammarModalView();
          closeCustomModal();
        }
      } catch (err) {
        showToast("어법 체계 초기화 실패", "error");
      }
    });
  }

  // JSON 직접 편집 시 표준 템플릿 복사
  if (btnCopyStandardTree) {
    btnCopyStandardTree.addEventListener("click", async () => {
      const stdList = await loadStandardTemplate();
      if (customTreeJsonEditor) {
        customTreeJsonEditor.value = JSON.stringify({
          meta: { title: "표준 243개 체계", total_items: stdList.length },
          list: stdList
        }, null, 2);
        showToast("표준 243개 JSON 템플릿을 에디터에 로드했습니다.", "info");
      }
    });
  }

  // 저장 버튼 핸들러
  if (btnSaveCustomTreeModal) {
    btnSaveCustomTreeModal.addEventListener("click", async () => {
      btnSaveCustomTreeModal.disabled = true;
      btnSaveCustomTreeModal.textContent = "⏳ 저장 중...";

      try {
        const useCustom = toggleUseCustomTree ? toggleUseCustomTree.checked : false;
        let finalJsonStr = "";

        if (currentActiveTab === "json") {
          finalJsonStr = (customTreeJsonEditor && customTreeJsonEditor.value) ? customTreeJsonEditor.value.trim() : "";
          if (useCustom && finalJsonStr) {
            try {
              JSON.parse(finalJsonStr);
            } catch (jsonErr) {
              showToast(`JSON 문법 오류: ${jsonErr.message}`, "error");
              btnSaveCustomTreeModal.disabled = false;
              btnSaveCustomTreeModal.textContent = "💾 커스텀 어법 체계 저장";
              return;
            }
          }
        } else {
          syncVisualToJson();
          finalJsonStr = customTreeJsonEditor ? customTreeJsonEditor.value : "";
        }

        const res = await fetch("/api/grammar/settings", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            use_custom_tree: useCustom,
            custom_tree_json: finalJsonStr || null
          })
        });

        const data = await res.json();
        if (res.ok && data.success) {
          showToast(data.message || "커스텀 어법 체계가 성공적으로 저장되었습니다.", "success");
          await loadGrammarCategories();
          renderGrammarModalView();
          closeCustomModal();
        } else {
          showToast(data.detail || "저장 실패", "error");
        }
      } catch (err) {
        console.error("Save custom grammar tree error:", err);
        showToast("어법 체계 저장 중 오류 발생", "error");
      } finally {
        btnSaveCustomTreeModal.disabled = false;
        btnSaveCustomTreeModal.textContent = "💾 커스텀 어법 체계 저장";
      }
    });
  }
}

