/**
 * 05-gichul_db: 단락 기반 다중 기준 유사 지문 검색 & 연속 3·4단어 N-gram UI 모듈 (similar-search.js)
 */

import { appState } from "./state.js";
import {
  btnBackToSimilarResults,
  emptyResultsBox,
  filterCorrectRate,
  filterExamType,
  filterGrade,
  filterMonth,
  filterQuestionType,
  loadingIndicator,
  passageViewContainer,
  resultsFilterCorrectRate,
  resultsFilterExamType,
  resultsFilterGrade,
  resultsFilterMonth,
  resultsFilterQuestionType,
  resultsTotalCount,
  resultsView,
  sentenceEmptyGuidanceBox,
  sentenceViewContainer,
  similarBackBanner,
  similarResultsContainer,
} from "./dom.js";
import { setHeaderSlotState, setMode, showHomeScreen, showResultsScreen } from "./navigation.js";
import { groupPassageItems, renderPassageView, stopAllListeningAudio } from "./results-passage.js";
import { escapeHtml, highlightSimilarMatches, showToast } from "./utils.js";
import { getYearsQueryParam } from "./year-filter.js";
import {
  addToCart,
  addToListeningCart,
  isInCart,
  isInListeningCart,
  isListeningPassage,
  toggleCart,
  toggleListeningCart,
  updateFloatingCartUI,
} from "./handout-cart.js";

const PRESET_DEFAULT_WEIGHTS = {
  balanced: { keyword: 40, phrase: 30, proper_noun: 20, shingle: 10 },
  near_duplicate: { keyword: 25, phrase: 25, proper_noun: 15, shingle: 35 },
  proper_noun: { keyword: 25, phrase: 15, proper_noun: 55, shingle: 5 },
  phrase_combo: { keyword: 30, phrase: 55, proper_noun: 10, shingle: 5 },
  topic_broad: { keyword: 65, phrase: 20, proper_noun: 10, shingle: 5 },
};

const NGRAM_PRESETS = new Set(["ngram_3", "ngram_4", "ngram_3_4"]);

const simState = {
  preset: "balanced",
  extracted: null, // { proper_nouns, phrases, keywords, ngrams_3, ngrams_4, filtered_common_count }
  customTerms: [],
  requiredTerms: new Set(),
  excludedTerms: new Set(),
  weightsModified: false,
  extractTimer: null,
};

function getEl(id) {
  return document.getElementById(id);
}

function countWords(text) {
  const m = String(text || "").match(/[A-Za-z]+(?:'[A-Za-z]+)?/g);
  return m ? m.length : 0;
}

function updateTextCounter() {
  const textarea = getEl("similarTextInput");
  const counter = getEl("similarTextCounter");
  if (!textarea || !counter) return;
  const val = textarea.value || "";
  counter.textContent = `${val.length.toLocaleString()}자 · ${countWords(val)}단어`;
}

function syncPresetButtonsUI() {
  document.querySelectorAll(".similar-preset-btn").forEach((btn) => {
    const p = btn.getAttribute("data-preset");
    btn.classList.toggle("active", p === simState.preset);
  });

  const ngramBar = getEl("similarNgramOptionsBar");
  if (ngramBar) {
    ngramBar.style.display = NGRAM_PRESETS.has(simState.preset) ? "flex" : "none";
  }
}

function applyPresetDefaultSliders(preset) {
  const w = PRESET_DEFAULT_WEIGHTS[preset];
  if (!w) return;
  simState.weightsModified = false;
  const map = [
    ["weightSliderKeyword", "weightValKeyword", w.keyword],
    ["weightSliderPhrase", "weightValPhrase", w.phrase],
    ["weightSliderProperNoun", "weightValProperNoun", w.proper_noun],
    ["weightSliderShingle", "weightValShingle", w.shingle],
  ];
  map.forEach(([sliderId, valId, num]) => {
    const sl = getEl(sliderId);
    const vl = getEl(valId);
    if (sl) sl.value = String(num);
    if (vl) vl.textContent = `${num}%`;
  });
}

function readCustomWeightsIfApplicable() {
  if (NGRAM_PRESETS.has(simState.preset) || !simState.weightsModified) {
    return null;
  }
  const kw = parseFloat(getEl("weightSliderKeyword")?.value || "40");
  const phr = parseFloat(getEl("weightSliderPhrase")?.value || "30");
  const ent = parseFloat(getEl("weightSliderProperNoun")?.value || "20");
  const shg = parseFloat(getEl("weightSliderShingle")?.value || "10");
  const total = kw + phr + ent + shg;
  if (total <= 0) return null;
  return {
    keyword: kw / total,
    phrase: phr / total,
    proper_noun: ent / total,
    shingle: shg / total,
  };
}

function createChipElement(term, df, kindClass) {
  const key = term.toLowerCase();
  const isReq = simState.requiredTerms.has(key);

  const chip = document.createElement("span");
  chip.className = `similar-chip ${kindClass}${isReq ? " is-required" : ""}`;
  chip.setAttribute("role", "button");
  chip.setAttribute("tabindex", "0");
  chip.title = isReq
    ? "필수 포함 중 (클릭 시 해제)"
    : "클릭 시 ★ 필수 포함(AND) 조건으로 고정";

  const labelSpan = document.createElement("span");
  labelSpan.textContent = `${isReq ? "★ " : ""}${term}`;
  chip.appendChild(labelSpan);

  if (df !== undefined && df !== null && df > 0) {
    const dfBadge = document.createElement("span");
    dfBadge.className = "chip-df-badge";
    dfBadge.textContent = `(${df})`;
    chip.appendChild(dfBadge);
  }

  const removeBtn = document.createElement("button");
  removeBtn.type = "button";
  removeBtn.className = "chip-remove-btn";
  removeBtn.title = "이 검색어 제외";
  removeBtn.setAttribute("aria-label", `${term} 제외`);
  removeBtn.textContent = "×";
  removeBtn.addEventListener("click", (e) => {
    e.stopPropagation();
    simState.requiredTerms.delete(key);
    simState.excludedTerms.add(key);
    simState.customTerms = simState.customTerms.filter((ct) => ct.toLowerCase() !== key);
    renderFeatureChipsPanel();
  });
  chip.appendChild(removeBtn);

  const toggleRequired = () => {
    if (simState.requiredTerms.has(key)) {
      simState.requiredTerms.delete(key);
    } else {
      simState.requiredTerms.add(key);
    }
    renderFeatureChipsPanel();
  };
  chip.addEventListener("click", toggleRequired);
  chip.addEventListener("keydown", (e) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      toggleRequired();
    }
  });

  return chip;
}

function renderFeatureChipsPanel() {
  const panel = getEl("similarFeatureChipsPanel");
  if (!panel) return;
  const ex = simState.extracted;
  if (!ex && simState.customTerms.length === 0) {
    panel.style.display = "none";
    return;
  }
  panel.style.display = "flex";

  const filterVisible = (arr) =>
    (arr || []).filter((it) => !simState.excludedTerms.has(String(it.term).toLowerCase()));

  const entities = filterVisible(ex?.proper_nouns);
  const phrases = filterVisible(ex?.phrases);
  const keywords = filterVisible(ex?.keywords);

  const customMulti = simState.customTerms.filter((t) => t.trim().includes(" ")).map((t) => ({ term: t }));
  const customSingle = simState.customTerms.filter((t) => !t.trim().includes(" ")).map((t) => ({ term: t }));

  // 연속 3·4단어는 현재 선택된 ngram 프리셋/기본값에 따라 조합 표시
  const ng4 = filterVisible(ex?.ngrams_4);
  const ng3 = filterVisible(ex?.ngrams_3);
  let displayNgrams = [];
  if (simState.preset === "ngram_3") {
    displayNgrams = ng3;
  } else if (simState.preset === "ngram_4") {
    displayNgrams = ng4;
  } else {
    displayNgrams = [...ng4.slice(0, 10), ...ng3.slice(0, 10)];
  }

  const fillRow = (containerId, rowId, items, kindClass) => {
    const container = getEl(containerId);
    const row = getEl(rowId);
    if (!container) return;
    container.innerHTML = "";
    if (!items || items.length === 0) {
      if (row) row.style.display = "none";
      return;
    }
    if (row) row.style.display = "flex";
    items.forEach((it) => {
      container.appendChild(createChipElement(it.term, it.df, kindClass));
    });
  };

  fillRow("similarChipsProperNouns", "rowChipsProperNouns", entities, "chip-entity");
  fillRow("similarChipsPhrases", "rowChipsPhrases", [...customMulti, ...phrases], "chip-phrase");
  fillRow("similarChipsKeywords", "rowChipsKeywords", [...customSingle, ...keywords], "chip-keyword");
  fillRow("similarChipsNgrams", "rowChipsNgrams", displayNgrams, "chip-ngram");

  const hintEl = getEl("similarFilteredCommonHint");
  if (hintEl && ex) {
    const cnt = ex.filtered_common_count || 0;
    hintEl.textContent = cnt > 0 ? `(상투 구문 ${cnt}개 자동 제외됨)` : "";
  }
}

export async function extractSimilarFeatures(silent = false) {
  const textarea = getEl("similarTextInput");
  const text = textarea ? textarea.value.trim() : "";
  if (text.length < 5) {
    if (!silent) {
      showToast("검색어를 추출할 영어 단락을 5자 이상 입력하세요.", "warning");
    }
    return null;
  }

  const filterCommon = getEl("chkFilterCommonNgrams")?.checked ?? true;

  try {
    const res = await fetch("/api/search/similar/extract", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        text,
        area: appState.currentArea || "reading",
        filter_common_ngrams: filterCommon,
      }),
    });
    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      if (!silent) showToast(errData.detail || "검색어 추출에 실패했습니다.", "error");
      return null;
    }
    const data = await res.json();
    simState.extracted = data;
    renderFeatureChipsPanel();
    if (!silent) {
      showToast(
        `추출 완료: 고유명사 ${data.proper_nouns?.length || 0}개 · 표현 ${data.phrases?.length || 0}개 · 핵심어 ${data.keywords?.length || 0}개 · 3/4단어 ${(data.ngrams_3?.length || 0) + (data.ngrams_4?.length || 0)}개`,
        "success"
      );
    }
    return data;
  } catch (e) {
    console.error("유사 검색어 추출 오류:", e);
    if (!silent) showToast("검색어 추출 중 네트워크 오류가 발생했습니다.", "error");
    return null;
  }
}

function collectActiveSearchFilters() {
  const isResultsVisible = resultsView && resultsView.style.display !== "none";
  const grade = (isResultsVisible ? resultsFilterGrade?.value : filterGrade?.value) || filterGrade?.value || "";
  const month = (isResultsVisible ? resultsFilterMonth?.value : filterMonth?.value) || filterMonth?.value || "";
  const examType = (isResultsVisible ? resultsFilterExamType?.value : filterExamType?.value) || filterExamType?.value || "";
  const questionType = (isResultsVisible ? resultsFilterQuestionType?.value : filterQuestionType?.value) || filterQuestionType?.value || "";
  const correctRateRange = (isResultsVisible ? resultsFilterCorrectRate?.value : filterCorrectRate?.value) || filterCorrectRate?.value || "";
  const yearsParam = getYearsQueryParam();
  const years = yearsParam
    ? yearsParam.split(",").map((y) => parseInt(y.trim(), 10)).filter((n) => !Number.isNaN(n))
    : null;

  return {
    area: appState.currentArea || "reading",
    grade,
    years,
    month: month ? parseInt(String(month).replace(/[^0-9]/g, ""), 10) || null : null,
    exam_type: examType,
    question_type: questionType,
    correct_rate_range: correctRateRange,
  };
}

export async function executeSimilarSearch() {
  stopAllListeningAudio();
  const textarea = getEl("similarTextInput");
  const text = textarea ? textarea.value.trim() : "";

  if (!text && simState.customTerms.length === 0) {
    showToast("유사 지문을 찾을 영어 단락을 먼저 붙여 넣으세요.", "warning");
    if (textarea) textarea.focus();
    return;
  }

  // 홈 필터와 결과창 필터를 양방향 동기화
  const filters = collectActiveSearchFilters();
  if (resultsFilterGrade) resultsFilterGrade.value = filters.grade;
  if (filterGrade) filterGrade.value = filters.grade;
  if (resultsFilterMonth && filters.month) resultsFilterMonth.value = String(filters.month);
  if (resultsFilterExamType) resultsFilterExamType.value = filters.exam_type;
  if (resultsFilterQuestionType) resultsFilterQuestionType.value = filters.question_type;
  if (resultsFilterCorrectRate) resultsFilterCorrectRate.value = filters.correct_rate_range;

  showResultsScreen();
  loadingIndicator.style.display = "flex";
  if (emptyResultsBox) emptyResultsBox.style.display = "none";
  if (sentenceEmptyGuidanceBox) sentenceEmptyGuidanceBox.style.display = "none";
  if (passageViewContainer) passageViewContainer.style.display = "none";
  if (sentenceViewContainer) sentenceViewContainer.style.display = "none";
  if (similarResultsContainer) similarResultsContainer.style.display = "none";
  if (similarBackBanner) similarBackBanner.style.display = "none";

  const minNgramHits = parseInt(getEl("similarMinNgramHits")?.value || "1", 10) || 1;
  const allowGap = parseInt(getEl("similarAllowGap")?.value || "0", 10) || 0;
  const filterCommon = getEl("chkFilterCommonNgrams")?.checked ?? true;
  const useAiExpand = getEl("chkSimilarAiExpand")?.checked ?? false;
  const topK = parseInt(getEl("similarTopK")?.value || "30", 10) || 30;

  let selectedNgrams = null;
  if (simState.extracted) {
    const pool = [
      ...(simState.extracted.ngrams_4 || []).map((x) => x.term),
      ...(simState.extracted.ngrams_3 || []).map((x) => x.term),
    ].filter((t) => !simState.excludedTerms.has(t.toLowerCase()));
    selectedNgrams = pool;
  }

  const payload = {
    text,
    preset: simState.preset,
    weights: readCustomWeightsIfApplicable(),
    selected_ngrams: selectedNgrams,
    required_terms: Array.from(simState.requiredTerms),
    excluded_terms: Array.from(simState.excludedTerms),
    custom_terms: simState.customTerms,
    use_ai_expansion: useAiExpand,
    min_ngram_hits: minNgramHits,
    filter_common_ngrams: filterCommon,
    allow_gap: allowGap,
    top_k: topK,
    ...filters,
  };

  try {
    const res = await fetch("/api/search/similar", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    loadingIndicator.style.display = "none";

    if (!res.ok) {
      showToast(data.detail || "유사 지문 검색에 실패했습니다.", "error");
      if (emptyResultsBox) emptyResultsBox.style.display = "flex";
      return;
    }

    if (data.extracted) {
      simState.extracted = data.extracted;
      renderFeatureChipsPanel();
    }

    const items = data.items || [];
    appState.similarLastResponse = data;
    appState.similarResultsData = items;
    appState.fromSimilarResults = false;

    const highlightMap = {};
    items.forEach((item) => {
      highlightMap[item.id] = {
        merged_matched_spans: item.merged_matched_spans || [],
        matched_ngrams_4: item.matched_ngrams_4 || [],
        matched_ngrams_3: item.matched_ngrams_3 || [],
        matched_proper_nouns: item.matched_proper_nouns || [],
        matched_phrases: item.matched_phrases || [],
        matched_keywords: item.matched_keywords || [],
      };
    });
    appState.activeSimilarHighlight = highlightMap;

    if (resultsTotalCount) resultsTotalCount.textContent = String(items.length);
    showSimilarResultsView();
  } catch (err) {
    console.error("유사 지문 검색 오류:", err);
    loadingIndicator.style.display = "none";
    showToast("유사 지문 검색 중 오류가 발생했습니다.", "error");
    if (emptyResultsBox) emptyResultsBox.style.display = "flex";
  }
}

export function showSimilarResultsView() {
  if (!similarResultsContainer) return;
  appState.fromSimilarResults = false;
  if (passageViewContainer) passageViewContainer.style.display = "none";
  if (sentenceViewContainer) sentenceViewContainer.style.display = "none";
  if (sentenceEmptyGuidanceBox) sentenceEmptyGuidanceBox.style.display = "none";
  if (similarBackBanner) similarBackBanner.style.display = "none";

  const items = appState.similarResultsData || [];
  if (items.length === 0) {
    similarResultsContainer.style.display = "none";
    if (emptyResultsBox) emptyResultsBox.style.display = "flex";
    setHeaderSlotState("similar");
    return;
  }

  if (emptyResultsBox) emptyResultsBox.style.display = "none";
  similarResultsContainer.style.display = "flex";
  setHeaderSlotState("similar");
  syncPresetButtonsUI();
  renderSimilarCards(items, appState.similarLastResponse);
}

function renderSimilarCards(items, metaResp) {
  const summaryEl = getEl("similarResultsSummary");
  const listEl = getEl("similarCardsList");
  if (!listEl) return;

  if (summaryEl) {
    const ms = metaResp?.elapsed_ms != null ? ` (${metaResp.elapsed_ms}ms)` : "";
    const aiBadge = metaResp?.extracted?.ai_expansion?.used
      ? ` · 🤖 AI 확장 적용 (${metaResp.extracted.ai_expansion.provider || "AI"})`
      : "";
    summaryEl.textContent = `✨ 유사 지문 ${items.length}건 발견${ms}${aiBadge}`;
  }

  listEl.innerHTML = "";

  items.forEach((p, idx) => {
    const card = document.createElement("article");
    card.className = "similar-result-card";

    const scoreVal = Number(p.similarity_score || 0);
    const isHigh = scoreVal >= 55;
    const isListen = p.area === "listening" || isListeningPassage(p.id);
    const inCart = isListen ? isInListeningCart(p.id) : isInCart(p.id);

    const rateText = p.correct_rate != null ? `정답률 ${p.correct_rate}%` : "";
    const breakdown = p.score_breakdown || {};

    // 매칭 근거 칩들
    const evPills = [];
    if (p.matched_proper_nouns && p.matched_proper_nouns.length > 0) {
      evPills.push(`<span class="evidence-pill ev-entity">🟣 고유명사: ${escapeHtml(p.matched_proper_nouns.slice(0, 5).join(", "))}</span>`);
    }
    if ((p.matched_ngrams_4 && p.matched_ngrams_4.length > 0) || (p.matched_ngrams_3 && p.matched_ngrams_3.length > 0)) {
      const c4 = p.matched_ngrams_4?.length || 0;
      const c3 = p.matched_ngrams_3?.length || 0;
      const label = [c4 ? `4단어 ${c4}건` : "", c3 ? `3단어 ${c3}건` : ""].filter(Boolean).join(" · ");
      evPills.push(`<span class="evidence-pill ev-ngram">🟠 연속구문: ${escapeHtml(label)}</span>`);
    }
    if (p.matched_phrases && p.matched_phrases.length > 0) {
      evPills.push(`<span class="evidence-pill ev-phrase">🔵 표현: ${escapeHtml(p.matched_phrases.slice(0, 4).join(", "))}</span>`);
    }
    if (p.matched_keywords && p.matched_keywords.length > 0) {
      evPills.push(`<span class="evidence-pill ev-keyword">🟢 핵심어 ${p.matched_keywords.length}개 (${escapeHtml(p.matched_keywords.slice(0, 5).join(", "))})</span>`);
    }

    const snippetHtml = highlightSimilarMatches(p.snippet || p.passage_text || "", {
      merged_matched_spans: p.merged_matched_spans || [],
      matched_ngrams_4: p.matched_ngrams_4 || [],
      matched_ngrams_3: p.matched_ngrams_3 || [],
      matched_proper_nouns: p.matched_proper_nouns || [],
      matched_phrases: p.matched_phrases || [],
      matched_keywords: p.matched_keywords || [],
    });

    card.innerHTML = `
      <div class="similar-card-header">
        <div class="similar-card-title-group">
          <span class="similar-rank-badge">#${idx + 1}</span>
          <span class="similar-score-badge ${isHigh ? "high" : ""}" title="핵심어 ${breakdown.keyword || 0}% · 표현 ${breakdown.phrase || 0}% · 고유명사 ${breakdown.proper_noun || 0}% · 연속구문 ${breakdown.shingle || 0}%">
            유사도 ${scoreVal.toFixed(1)}%
          </span>
          <span class="similar-id-pill">${escapeHtml(p.id)}</span>
          <span class="similar-meta-pill">${escapeHtml(p.question_type || "기타")}</span>
          ${p.exam_type ? `<span class="similar-meta-pill">${escapeHtml(p.exam_type)}</span>` : ""}
          ${rateText ? `<span class="similar-meta-pill">${escapeHtml(rateText)}</span>` : ""}
        </div>
        <div class="similar-card-actions">
          <button type="button" class="btn ${inCart ? "btn-primary" : "btn-secondary"} btn-sm btn-similar-cart" data-id="${escapeHtml(p.id)}">
            ${inCart ? "✔ 유인물 담김" : "📄 유인물 담기"}
          </button>
          <button type="button" class="btn btn-primary btn-sm btn-similar-detail" data-index="${idx}">
            🔍 2×2 상세 보기
          </button>
        </div>
      </div>
      ${evPills.length > 0 ? `<div class="similar-evidence-bar">${evPills.join("")}</div>` : ""}
      <div class="similar-card-snippet">${snippetHtml}</div>
    `;

    card.querySelector(".btn-similar-detail")?.addEventListener("click", () => openSimilarPassageDetail(idx));
    card.querySelector(".btn-similar-cart")?.addEventListener("click", (e) => {
      const btn = e.currentTarget;
      const added = isListen ? toggleListeningCart(p.id) : toggleCart(p.id);
      btn.className = `btn ${added ? "btn-primary" : "btn-secondary"} btn-sm btn-similar-cart`;
      btn.textContent = added ? "✔ 유인물 담김" : "📄 유인물 담기";
      updateFloatingCartUI();
      showToast(added ? `${p.id} 유인물에 담았습니다.` : `${p.id} 유인물에서 제외했습니다.`, "info");
    });

    listEl.appendChild(card);
  });
}

export function openSimilarPassageDetail(idx) {
  const items = appState.similarResultsData || [];
  const target = items[idx];
  if (!target) return;

  appState.fromSimilarResults = true;
  if (similarResultsContainer) similarResultsContainer.style.display = "none";
  if (similarBackBanner) similarBackBanner.style.display = "flex";

  appState.passagesData = groupPassageItems(items);
  appState.rawPassagesData = [...appState.passagesData];
  renderPassageView(appState.passagesData, target.id);
  setHeaderSlotState("passage");
}

function bindSliderPair(sliderId, valId) {
  const sl = getEl(sliderId);
  const vl = getEl(valId);
  if (!sl || !vl) return;
  sl.addEventListener("input", () => {
    simState.weightsModified = true;
    vl.textContent = `${sl.value}%`;
  });
}

export function initSimilarSearch() {
  const textarea = getEl("similarTextInput");
  if (textarea) {
    textarea.addEventListener("input", () => {
      updateTextCounter();
      if (simState.extractTimer) clearTimeout(simState.extractTimer);
      const val = textarea.value.trim();
      if (val.length >= 25) {
        simState.extractTimer = setTimeout(() => extractSimilarFeatures(true), 500);
      }
    });
    textarea.addEventListener("keydown", (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
        e.preventDefault();
        executeSimilarSearch();
      }
    });
  }

  getEl("btnPasteSimilarText")?.addEventListener("click", async () => {
    try {
      const clip = await navigator.clipboard.readText();
      if (clip && textarea) {
        textarea.value = clip;
        updateTextCounter();
        extractSimilarFeatures(true);
        showToast("클립보드 텍스트를 붙여 넣고 검색어를 추출했습니다.", "success");
      }
    } catch (_err) {
      showToast("브라우저 클립보드 접근 권한이 없어 Ctrl+V로 직접 붙여 넣어 주세요.", "info");
      if (textarea) textarea.focus();
    }
  });

  getEl("btnClearSimilarText")?.addEventListener("click", () => {
    if (textarea) textarea.value = "";
    simState.extracted = null;
    simState.customTerms = [];
    simState.requiredTerms.clear();
    simState.excludedTerms.clear();
    updateTextCounter();
    renderFeatureChipsPanel();
    if (textarea) textarea.focus();
  });

  // 프리셋 버튼들 (홈 & 결과창 양쪽 동기화)
  document.querySelectorAll(".similar-preset-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      const newPreset = btn.getAttribute("data-preset") || "balanced";
      simState.preset = newPreset;
      applyPresetDefaultSliders(newPreset);
      syncPresetButtonsUI();
      renderFeatureChipsPanel();

      if (btn.closest("#similarResultsPresetBar")) {
        executeSimilarSearch();
      }
    });
  });

  getEl("btnToggleSimilarWeights")?.addEventListener("click", () => {
    const panel = getEl("similarWeightsPanel");
    if (!panel) return;
    const isHidden = panel.style.display === "none";
    panel.style.display = isHidden ? "grid" : "none";
  });

  bindSliderPair("weightSliderKeyword", "weightValKeyword");
  bindSliderPair("weightSliderPhrase", "weightValPhrase");
  bindSliderPair("weightSliderProperNoun", "weightValProperNoun");
  bindSliderPair("weightSliderShingle", "weightValShingle");

  getEl("chkFilterCommonNgrams")?.addEventListener("change", () => {
    const val = textarea ? textarea.value.trim() : "";
    if (val.length >= 10) extractSimilarFeatures(true);
  });

  const addCustomTerm = () => {
    const inp = getEl("inputSimilarCustomTerm");
    if (!inp) return;
    const term = inp.value.trim();
    if (!term) return;
    const key = term.toLowerCase();
    simState.excludedTerms.delete(key);
    if (!simState.customTerms.some((t) => t.toLowerCase() === key)) {
      simState.customTerms.push(term);
    }
    inp.value = "";
    renderFeatureChipsPanel();
  };

  getEl("btnAddSimilarCustomTerm")?.addEventListener("click", addCustomTerm);
  getEl("inputSimilarCustomTerm")?.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      addCustomTerm();
    }
  });

  getEl("btnExtractSimilarFeatures")?.addEventListener("click", () => extractSimilarFeatures(false));
  getEl("btnRunSimilarSearch")?.addEventListener("click", () => executeSimilarSearch());

  getEl("btnEditSimilarQuery")?.addEventListener("click", () => {
    setMode("similar");
    showHomeScreen();
  });

  getEl("btnBatchAddSimilarHandout")?.addEventListener("click", () => {
    const items = appState.similarResultsData || [];
    if (items.length === 0) return;
    let addedCount = 0;
    items.forEach((p) => {
      const isListen = p.area === "listening" || isListeningPassage(p.id);
      if (isListen) {
        if (!isInListeningCart(p.id)) {
          addToListeningCart(p.id);
          addedCount++;
        }
      } else if (!isInCart(p.id)) {
        addToCart(p.id);
        addedCount++;
      }
    });
    updateFloatingCartUI();
    renderSimilarCards(items, appState.similarLastResponse);
    showToast(`유사 지문 ${addedCount}건을 유인물 보관함에 담았습니다.`, "success");
  });

  if (btnBackToSimilarResults) {
    btnBackToSimilarResults.addEventListener("click", () => {
      showSimilarResultsView();
    });
  }

  syncPresetButtonsUI();
  updateTextCounter();
}
