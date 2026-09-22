/**
 * 05-gichul_db: 헤더 슬롯 · 화면 전환 · 모드 전환 (섹션 1~3) (navigation.js)
 * - main.js 에서 분리
 */

import { appState } from "./state.js";
import {
  btnBackToSearch,
  btnEmptyBackToSearch,
  btnEmptyResetFilters,
  btnGoHome,
  btnHeaderFlow,
  emptyResultsBox,
  filterCorrectRate,
  filterExamType,
  filterGrade,
  filterMonth,
  filterQuestionType,
  filterYear,
  homeGrammarFiltersGroup,
  homeSearchView,
  mainSearchInput,
  passageViewContainer,
  resultsFilterCorrectRate,
  resultsFilterExamType,
  resultsFilterGrade,
  resultsFilterMonth,
  resultsFilterQuestionType,
  resultsFilterYear,
  resultsGrammarFiltersGroup,
  resultsSearchInput,
  resultsTabModePassage,
  resultsTabModeSentence,
  resultsView,
  sentenceViewContainer,
  statsBadge,
  tabModePassage,
  tabModeSentence,
} from "./dom.js";
import {
  executeSearch,
  resetAllSearchFilters,
  setSearchWithinState,
  updateClearButtons,
  updateFilterResetButtonsUI,
} from "./search.js";
import { backToPassageView, showSentencesForPassage } from "./results-sentence.js";

// =========================================================================
// 1. 헤더 액션 슬롯 상태 제어 (통계 배지 <-> 전체 문장 <-> 지문 복귀)
// =========================================================================

/**
 * 헤더 액션 슬롯 상태 전환 함수
 * @param {'home' | 'passage' | 'sentence'} state 
 */
export function setHeaderSlotState(state) {
  if (!statsBadge || !btnHeaderFlow) return;

  const isResultsVisible = (resultsView && resultsView.style.display !== "none");
  const isHomeVisible = (homeSearchView && homeSearchView.style.display !== "none" && !isResultsVisible);

  // 1) 홈 검색 화면이 표시 중이거나 결과창이 숨겨진 경우 -> 통계 배지 표시
  if (state === "home" || isHomeVisible || !isResultsVisible) {
    statsBadge.style.display = "flex";
    btnHeaderFlow.style.display = "none";
    return;
  }

  // 2) 문장 결과창 모드 -> '지문 결과창으로 돌아가기' 버튼
  if (state === "sentence" || appState.currentMode === "sentence") {
    statsBadge.style.display = "none";
    btnHeaderFlow.style.display = "inline-flex";
    btnHeaderFlow.textContent = "🔙 지문 결과창으로 돌아가기";
    btnHeaderFlow.title = "이전 지문 상세 화면으로 복귀";
    btnHeaderFlow.classList.add("mode-back");
    return;
  }

  // 3) 지문 결과창 모드
  if (state === "passage" || appState.currentMode === "passage") {
    if (appState.currentPassageId) {
      statsBadge.style.display = "none";
      btnHeaderFlow.style.display = "inline-flex";
      btnHeaderFlow.textContent = "📝 해당 지문의 전체 문장";
      btnHeaderFlow.title = "해당 지문의 전체 문장 결과창 보기";
      btnHeaderFlow.classList.remove("mode-back");
    } else {
      statsBadge.style.display = "flex";
      btnHeaderFlow.style.display = "none";
    }
    return;
  }
}
// =========================================================================
// 2. 화면 전환 및 동기화 로직
// =========================================================================

/** 홈 검색 화면으로 복귀 */
export function showHomeScreen() {
  appState.currentPassageId = null;
  appState.currentPassageIndex = 0;
  homeSearchView.style.display = "flex";
  resultsView.style.display = "none";
  if (emptyResultsBox) emptyResultsBox.style.display = "none";
  if (passageViewContainer) passageViewContainer.style.display = "none";
  if (sentenceViewContainer) sentenceViewContainer.style.display = "none";
  if (btnBackToSearch) btnBackToSearch.style.display = "none";
  
  // 헤더 상태를 통계 배지 모드로 복원
  setHeaderSlotState("home");
  setSearchWithinState(false);
  updateGrammarFiltersVisibility();

  // 결과창 검색어 및 필터를 홈 검색창에 동기화
  if (resultsSearchInput && resultsSearchInput.value) {
    mainSearchInput.value = resultsSearchInput.value;
  }
  if (resultsFilterGrade) filterGrade.value = resultsFilterGrade.value;
  if (resultsFilterYear) filterYear.value = resultsFilterYear.value;
  if (resultsFilterMonth) filterMonth.value = resultsFilterMonth.value;
  if (resultsFilterExamType) filterExamType.value = resultsFilterExamType.value;
  if (resultsFilterQuestionType) filterQuestionType.value = resultsFilterQuestionType.value;
  if (resultsFilterCorrectRate) filterCorrectRate.value = resultsFilterCorrectRate.value;

  window.scrollTo({ top: 0, behavior: "smooth" });
  mainSearchInput.focus();
  if (typeof updateClearButtons === "function") updateClearButtons();
  if (typeof updateFilterResetButtonsUI === "function") updateFilterResetButtonsUI();
}

/** 상단 결과 내비게이션 바 높이를 동적으로 측정하여 CSS 변수(--results-nav-height)로 동기화 */
export function updateResultsNavHeight() {
  const navBar = document.querySelector(".results-nav-bar");
  if (navBar && navBar.offsetHeight > 0) {
    document.documentElement.style.setProperty("--results-nav-height", `${navBar.offsetHeight}px`);
  }
}

/** 결과 화면으로 전환 */
export function showResultsScreen() {
  homeSearchView.style.display = "none";
  resultsView.style.display = "flex";
  if (btnBackToSearch) btnBackToSearch.style.display = "inline-flex";
  window.scrollTo({ top: 0, behavior: "smooth" });
  updateGrammarFiltersVisibility();
  if (typeof updateClearButtons === "function") updateClearButtons();
  setTimeout(updateResultsNavHeight, 30);
  setHeaderSlotState(appState.currentMode);
}
// =========================================================================
// 3. 모드 전환 (지문 검색 vs 문장 검색)
// =========================================================================

/** 문장 검색 모드일 때만 어법 대분류/세부어법/중요문장 필터를 노출 (지문 검색 시 숨김) */
export function updateGrammarFiltersVisibility() {
  const isSentence = (appState.currentMode === "sentence");
  if (homeGrammarFiltersGroup) {
    homeGrammarFiltersGroup.style.display = isSentence ? "inline-flex" : "none";
  }
  if (resultsGrammarFiltersGroup) {
    resultsGrammarFiltersGroup.style.display = isSentence ? "inline-flex" : "none";
  }
}

export function setMode(mode, triggerSearch = false) {
  appState.currentMode = mode;
  if (mode === "passage") {
    tabModePassage.classList.add("active");
    tabModeSentence.classList.remove("active");
    if (resultsTabModePassage) resultsTabModePassage.classList.add("active");
    if (resultsTabModeSentence) resultsTabModeSentence.classList.remove("active");
    mainSearchInput.placeholder = "검색할 키워드, 지문 주제, 문항 번호 또는 출처([고3-2024년...])를 입력하세요...";
    if (resultsSearchInput) resultsSearchInput.placeholder = "지문 검색어 또는 출처 입력...";
  } else {
    tabModeSentence.classList.add("active");
    tabModePassage.classList.remove("active");
    if (resultsTabModeSentence) resultsTabModeSentence.classList.add("active");
    if (resultsTabModePassage) resultsTabModePassage.classList.remove("active");
    mainSearchInput.placeholder = "검색할 영어 문장 표현 또는 출처([고3-2024년...-1번째 문장])를 입력하세요...";
    if (resultsSearchInput) resultsSearchInput.placeholder = "영어 문장 또는 출처 입력...";
  }

  updateGrammarFiltersVisibility();

  if (triggerSearch && resultsView.style.display !== "none") {
    executeSearch("results");
  }
}

// ---- 이벤트 바인딩 및 초기화 (main.js 에서 원본 순서대로 호출) ----
export function init() {

  window.addEventListener("resize", updateResultsNavHeight);

  // 홈으로 이동 버튼 이벤트 연결
  btnGoHome.addEventListener("click", showHomeScreen);
  btnBackToSearch.addEventListener("click", showHomeScreen);
  if (btnEmptyBackToSearch) {
    btnEmptyBackToSearch.addEventListener("click", showHomeScreen);
  }
  if (btnEmptyResetFilters) {
    btnEmptyResetFilters.addEventListener("click", () => {
      resetAllSearchFilters(true);
    });
  }

  tabModePassage.addEventListener("click", () => setMode("passage"));
  tabModeSentence.addEventListener("click", () => setMode("sentence"));
  if (resultsTabModePassage) {
    resultsTabModePassage.addEventListener("click", () => {
      if (appState.currentMode === "passage") return;
      backToPassageView();
    });
  }
  if (resultsTabModeSentence) {
    resultsTabModeSentence.addEventListener("click", () => {
      if (appState.currentMode === "sentence") return;
      showSentencesForPassage(appState.currentPassageId);
    });
  }
}
