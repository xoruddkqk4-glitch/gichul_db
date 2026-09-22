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
} from "./dom.js";
import { executeSearch, executeSearchWithinResults } from "./search.js";
import { getGrammarBadgeClass, showGrammarPopover, showSentencesForPassage } from "./results-sentence.js";
import { escapeHtml, showToast } from "./utils.js";

let grammarCategoriesList = [];
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

async function loadGrammarCategories() {
  try {
    const res = await fetch("/static/data/grammar_categories.json");
    if (res.ok) {
      const data = await res.json();
      grammarCategoriesList = data.list || [];
    }
  } catch (e) {
    console.error("어법 범주 데이터 로드 실패:", e);
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
            explanation: `수동 등록 (${found.full_path})`
          };
        }
        return null;
      }).filter(Boolean);

      try {
        const res = await fetch(`/api/sentences/${encodeURIComponent(activeGrammarModalSentence.id)}/grammar-annotations/batch`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ annotations: selectedItems })
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
}
