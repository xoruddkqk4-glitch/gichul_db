/**
 * 05-gichul_db: 통계 로드 · 검색 실행 · 필터 초기화 (섹션 4~5) (search.js)
 * - main.js 에서 분리
 */

import { appState } from "./state.js";
import {
  btnClearMainSearch,
  btnClearResultsSearch,
  btnHomeToggleWholeWord,
  btnResetHomeFilters,
  btnResetResultsFilters,
  btnResultsSearch,
  btnSearch,
  btnToggleSearchWithin,
  btnToggleWholeWord,
  emptyResultsBox,
  filterCorrectRate,
  filterExamType,
  filterGrade,
  filterGrammarCategory,
  filterGrammarPos,
  filterMonth,
  filterQuestionType,
  filterTag,
  filterYear,
  loadingIndicator,
  mainSearchInput,
  passageViewContainer,
  resultsFilterCorrectRate,
  resultsFilterExamType,
  resultsFilterGrade,
  resultsFilterGrammarCategory,
  resultsFilterGrammarPos,
  resultsFilterMonth,
  resultsFilterQuestionType,
  resultsFilterYear,
  resultsSearchInput,
  resultsTotalCount,
  resultsView,
  sentenceViewContainer,
  statPassages,
  statsBadge,
  statSentences,
} from "./dom.js";
import { setHeaderSlotState, setMode, showResultsScreen, updateGrammarFiltersVisibility } from "./navigation.js";
import { groupPassageItems, renderPassageView } from "./results-passage.js";
import { renderSentenceView } from "./results-sentence.js";
import { escapeHtml, showToast } from "./utils.js";
import { resetAllGrammarFilters, updateGrammarBreadcrumbFilterUI } from "./grammar.js";
import { getYearsQueryParam, isAllYearsSelected, resetYearFilter, initYearFilter } from "./year-filter.js";
import { updateMonthOptionsByGrade, initMonthFilter } from "./month-filter.js";

// 독해 21대 문제 유형
export const READING_QUESTION_TYPES = [
  "글의목적", "심경변화", "주장", "어휘함축", "글의요지", "글의주제", "글의제목",
  "도표", "불일치", "실용문불일치", "실용문일치", "어법", "어휘", "빈칸",
  "문장빼기", "글의순서", "문장넣기", "글의요약", "1지문2문항", "1지문3문항", "기타"
];

// 12대 듣기 문제 유형 (+ 기타)
export const LISTENING_QUESTION_TYPES = [
  "화자의 목적/의견/요지",
  "그림 불일치",
  "화자의 할일",
  "금액",
  "이유",
  "언급되지 않은 것",
  "불일치",
  "도표 불일치",
  "짧은 응답",
  "긴 응답",
  "할 말",
  "1담화 2문항",
  "기타"
];

/** 현재 선택된 영역(독해 vs 듣기)에 따라 홈 및 결과창의 문제유형 드롭다운 옵션 동적 갱신 */
export function updateQuestionTypeOptions(area) {
  const isListening = (area || appState.currentArea) === "listening";
  const types = isListening ? LISTENING_QUESTION_TYPES : READING_QUESTION_TYPES;

  const updateSelect = (selectEl, defaultLabel) => {
    if (!selectEl) return;
    const currentVal = selectEl.value;
    selectEl.innerHTML = `<option value="">${defaultLabel}</option>` +
      types.map(t => `<option value="${escapeHtml(t)}">${escapeHtml(t)}</option>`).join("");
    // 기존 선택값이 새 목록에 있으면 유지, 없으면 빈값으로 리셋
    if (types.includes(currentVal)) {
      selectEl.value = currentVal;
    } else {
      selectEl.value = "";
    }
  };

  updateSelect(filterQuestionType, "전체 문제유형");
  updateSelect(resultsFilterQuestionType, "문제유형");
}

let isWholeWordActive = false;
// =========================================================================
// 4. 통계 데이터 로드 및 통계 배지 클릭(전체 지문 보기)
// =========================================================================

export async function loadStats() {
  try {
    const res = await fetch("/api/stats");
    if (res.ok) {
      const data = await res.json();
      statPassages.textContent = data.passages || 0;
      statSentences.textContent = data.sentences || 0;
    }
  } catch (e) {
    console.error("통계 로드 실패:", e);
  }
}

/** 검색어 문자열에서 #태그 자동 추출 (예: "#빈칸", "climate #빈칸") */
function parseSearchQuery(rawQuery) {
  let q = (rawQuery || "").trim();
  let tag = "";
  const tagMatch = q.match(/#([^\s#]+)/);
  if (tagMatch) {
    tag = tagMatch[1];
    q = q.replace(/#[^\s#]+/g, "").trim();
  }
  return { keyword: q, tag: tag };
}

/** 키워드 일치 여부 검사 (부분 일치 또는 온전한 단어 일치 지원) */
function checkTextMatch(text, kw, isWholeWord = false) {
  if (!text || !kw) return false;
  if (!isWholeWord) {
    return text.toLowerCase().includes(kw.toLowerCase());
  }
  const escapedKw = kw.trim().replace(/[.*+?^${}()|[\]\\]/g, "\\$&").replace(/\s+/g, "\\s+");
  const regex = new RegExp(`(?<=^|[^a-zA-Z0-9가-힣_])(${escapedKw})(?=[^a-zA-Z0-9가-힣_]|$)`, "i");
  return regex.test(text);
}

/** 텍스트 내에서 검색 표현을 찾아 파스텔톤 빨간색 형광펜으로 감싸기 */
export function highlightTextKeyword(text, rawQuery, highlightClass = "sentence-highlight") {
  if (!text) return "";
  const cleanText = escapeHtml(text);
  if (!rawQuery) return cleanText;

  const { keyword } = parseSearchQuery(rawQuery);
  if (!keyword || !keyword.trim()) return cleanText;

  // HTML 이스케이프된 키워드로 정규식 특수문자 이스케이프 (공백은 \s+ 처리)
  const escapedKw = escapeHtml(keyword.trim()).replace(/[.*+?^${}()|[\]\\]/g, "\\$&").replace(/\s+/g, "\\s+");
  const pattern = isWholeWordActive
    ? `(?<=^|[^a-zA-Z0-9가-힣_])(${escapedKw})(?=[^a-zA-Z0-9가-힣_]|$)`
    : `(${escapedKw})`;
  const regex = new RegExp(pattern, "gi");

  return cleanText.replace(regex, `<mark class="${highlightClass}">$1</mark>`);
}

export function highlightSentenceKeyword(text, rawQuery) {
  return highlightTextKeyword(text, rawQuery, "sentence-highlight");
}
// =========================================================================
// 5. 검색 실행 함수
// =========================================================================

/** 통합 검색 실행 */
export async function executeSearch(source = "home") {
  let keyword = "";
  let grade = "";
  let year = "";
  let month = "";
  let examType = "";
  let questionType = "";
  let correctRateRange = "";
  let tag = "";

  if (source === "all" || source === "all_passages") {
    // 전체 보기 (조건 없음)
    keyword = "";
    grade = "";
    year = "";
    month = "";
    examType = "";
    questionType = "";
    correctRateRange = "";
    tag = "";
    resetYearFilter();
    updateMonthOptionsByGrade("");
  } else if (source === "home") {
    const parsed = parseSearchQuery(mainSearchInput.value);
    keyword = parsed.keyword;
    tag = parsed.tag;
    grade = filterGrade.value;
    year = filterYear.value;
    month = filterMonth.value;
    examType = filterExamType ? filterExamType.value : "";
    questionType = filterQuestionType ? filterQuestionType.value : "";
    correctRateRange = filterCorrectRate ? filterCorrectRate.value : "";

    // 결과창 바에 동기화
    if (resultsSearchInput) resultsSearchInput.value = mainSearchInput.value.trim();
    if (resultsFilterGrade) resultsFilterGrade.value = grade;
    if (resultsFilterYear) resultsFilterYear.value = year;
    if (resultsFilterMonth) resultsFilterMonth.value = month;
    if (resultsFilterExamType) resultsFilterExamType.value = examType;
    if (resultsFilterQuestionType) resultsFilterQuestionType.value = questionType;
    if (resultsFilterCorrectRate) resultsFilterCorrectRate.value = correctRateRange;
    if (resultsFilterGrammarPos && filterGrammarPos) resultsFilterGrammarPos.value = filterGrammarPos.value;
    if (resultsFilterGrammarCategory && filterGrammarCategory) resultsFilterGrammarCategory.value = filterGrammarCategory.value;
  } else {
    const parsed = parseSearchQuery(resultsSearchInput.value);
    keyword = parsed.keyword;
    tag = parsed.tag;
    grade = resultsFilterGrade.value;
    year = resultsFilterYear.value;
    month = resultsFilterMonth.value;
    examType = resultsFilterExamType.value;
    questionType = resultsFilterQuestionType.value;
    correctRateRange = resultsFilterCorrectRate ? resultsFilterCorrectRate.value : "";

    // 홈 바에 역동기화
    mainSearchInput.value = resultsSearchInput.value.trim();
    filterGrade.value = grade;
    filterYear.value = year;
    filterMonth.value = month;
    filterExamType.value = examType;
    filterQuestionType.value = questionType;
    if (filterCorrectRate) filterCorrectRate.value = correctRateRange;
    if (filterGrammarPos && resultsFilterGrammarPos) filterGrammarPos.value = resultsFilterGrammarPos.value;
    if (filterGrammarCategory && resultsFilterGrammarCategory) filterGrammarCategory.value = resultsFilterGrammarCategory.value;
  }

  if (typeof updateGrammarBreadcrumbFilterUI === "function") {
    updateGrammarBreadcrumbFilterUI();
  }
  if (typeof updateFilterResetButtonsUI === "function") {
    updateFilterResetButtonsUI();
  }

  // 결과 화면으로 전환 및 로딩 표시
  showResultsScreen();
  loadingIndicator.style.display = "flex";
  emptyResultsBox.style.display = "none";
  passageViewContainer.style.display = "none";
  sentenceViewContainer.style.display = "none";

  const params = new URLSearchParams();
  if (keyword) params.append("keyword", keyword);
  if (isWholeWordActive) params.append("whole_word", "true");
  if (grade) params.append("grade", grade);
  params.append("area", appState.currentArea || "reading");

  const yearsParam = getYearsQueryParam();
  if (yearsParam) {
    if (yearsParam.includes(",")) {
      params.append("years", yearsParam);
    } else {
      params.append("year", yearsParam);
    }
  } else if (year) {
    params.append("year", year);
  }

  if (month) params.append("month", month);
  if (examType) params.append("exam_type", examType);
  if (questionType) params.append("question_type", questionType);
  if (correctRateRange) params.append("correct_rate_range", correctRateRange);
  if (tag) params.append("tag", tag);

  const activeGrammarPos = (resultsFilterGrammarPos && resultsFilterGrammarPos.value) || (filterGrammarPos && filterGrammarPos.value) || "";
  const activeGrammarCat = (resultsFilterGrammarCategory && resultsFilterGrammarCategory.value) || (filterGrammarCategory && filterGrammarCategory.value) || "";

  if (activeGrammarCat) {
    params.append("grammar_cat_id", activeGrammarCat);
  } else if (activeGrammarPos) {
    params.append("grammar_pos", activeGrammarPos);
  }

  if (appState.isStarredFilterActive) {
    params.append("is_starred", "true");
  }

  params.append("limit", "0");

  try {
    if (appState.currentMode === "passage") {
      appState.treeNavState = { grade: null, year: null, month: null };
      const res = await fetch(`/api/search/passages?${params.toString()}`);
      const data = await res.json();
      appState.passagesData = groupPassageItems(data.items || []);
      appState.rawPassagesData = [...appState.passagesData]; // 원본 캐시 갱신
      resultsTotalCount.textContent = appState.passagesData.length;
      renderPassageView(appState.passagesData);
      setHeaderSlotState("passage");
      updateGrammarFiltersVisibility();
    } else {
      const res = await fetch(`/api/search/sentences?${params.toString()}`);
      const data = await res.json();
      appState.sentencesData = data.items || [];
      appState.rawSentencesData = [...appState.sentencesData]; // 원본 캐시 갱신
      resultsTotalCount.textContent = appState.sentencesData.length;
      renderSentenceView(appState.sentencesData);
      setHeaderSlotState("sentence");
      updateGrammarFiltersVisibility();
    }
  } catch (err) {
    console.error("검색 오류:", err);
    showToast("검색 중 오류가 발생했습니다.", "error");
  } finally {
    loadingIndicator.style.display = "none";
    if (typeof updateFilterResetButtonsUI === "function") {
      updateFilterResetButtonsUI();
    }
  }
}

/** 현재 로드된 결과 목록 내에서 키워드 또는 #태그로 즉시 필터링(결과 내 검색) */
export function executeSearchWithinResults() {
  const rawVal = resultsSearchInput ? resultsSearchInput.value.trim() : "";

  if (!rawVal) {
    // 검색어가 비어있으면 원본 목록 전체 복원
    if (appState.currentMode === "passage") {
      appState.passagesData = [...appState.rawPassagesData];
      resultsTotalCount.textContent = appState.passagesData.length;
      renderPassageView(appState.passagesData);
    } else {
      appState.sentencesData = [...appState.rawSentencesData];
      resultsTotalCount.textContent = appState.sentencesData.length;
      renderSentenceView(appState.sentencesData);
    }
    showToast("전체 검색 결과가 다시 표시됩니다.", "info");
    return;
  }

  const { keyword: kwRaw, tag: tagRaw } = parseSearchQuery(rawVal);
  const kw = kwRaw.toLowerCase();
  const tagLower = tagRaw.toLowerCase();

  if (appState.currentMode === "passage") {
    if (!appState.rawPassagesData || appState.rawPassagesData.length === 0) {
      showToast("필터링할 지문 검색 결과가 없습니다.", "warning");
      return;
    }

    const filtered = appState.rawPassagesData.filter(p => {
      // 1. #태그 조건 필터링
      let tagMatch = true;
      if (tagLower) {
        const inTags = (p.tags || []).some(t => t.toLowerCase().includes(tagLower));
        const inType = (p.question_type || "").toLowerCase().includes(tagLower);
        tagMatch = inTags || inType;
      }

      // 2. 키워드 조건 필터링
      let kwMatch = true;
      if (kwRaw) {
        const inBody = checkTextMatch(p.passage_text, kwRaw, isWholeWordActive);
        const inTitle = checkTextMatch(p.question_title, kwRaw, isWholeWordActive);
        const inId = (p.display_id || p.id || "").toLowerCase().includes(kw);
        const inExp = checkTextMatch(p.explanation_text, kwRaw, isWholeWordActive);
        const inType = (p.question_type || "").toLowerCase().includes(kw);
        const inTags = (p.tags || []).some(t => t.toLowerCase().includes(kw));
        
        let inSub = false;
        if (p.isGroup && p.subItems) {
          inSub = p.subItems.some(si => 
            checkTextMatch(si.passage_text, kwRaw, isWholeWordActive) ||
            checkTextMatch(si.question_title, kwRaw, isWholeWordActive)
          );
        }

        kwMatch = inBody || inTitle || inId || inExp || inType || inTags || inSub;
      }

      return tagMatch && kwMatch;
    });

    if (filtered.length === 0) {
      showToast(`결과 목록 내에서 '${rawVal}' 조건에 일치하는 문항이 없습니다.`, "warning");
    } else {
      showToast(`결과 내 검색: ${filtered.length}개 문항이 필터링되었습니다.`, "success");
    }

    appState.treeNavState = { grade: null, year: null, month: null };
    appState.passagesData = filtered;
    resultsTotalCount.textContent = filtered.length;
    renderPassageView(appState.passagesData);
  } else {
    if (!appState.rawSentencesData || appState.rawSentencesData.length === 0) {
      showToast("필터링할 문장 검색 결과가 없습니다.", "warning");
      return;
    }

    const activePos = (resultsFilterGrammarPos && resultsFilterGrammarPos.value) || (filterGrammarPos && filterGrammarPos.value) || "";
    const activeCatId = (resultsFilterGrammarCategory && resultsFilterGrammarCategory.value) || (filterGrammarCategory && filterGrammarCategory.value) || "";

    const filtered = appState.rawSentencesData.filter(s => {
      let tagMatch = true;
      if (tagLower) {
        const inTags = (s.tags || []).some(t => t.toLowerCase().includes(tagLower));
        const inPid = (s.passage_id || "").toLowerCase().includes(tagLower);
        tagMatch = inTags || inPid;
      }

      let kwMatch = true;
      if (kwRaw) {
        const inEng = checkTextMatch(s.sentence_text, kwRaw, isWholeWordActive);
        const inKor = checkTextMatch(s.korean_translation, kwRaw, isWholeWordActive);
        const inId = (s.sentence_id || s.id || "").toLowerCase().includes(kw);
        kwMatch = inEng || inKor || inId;
      }

      let posMatch = true;
      if (activePos) {
        posMatch = (s.grammar_annotations || []).some(a => a.pos_category === activePos);
      }

      let catMatch = true;
      if (activeCatId) {
        catMatch = (s.grammar_annotations || []).some(a => a.cat_id === activeCatId);
      }

      let starMatch = true;
      if (appState.isStarredFilterActive) {
        starMatch = (s.is_starred === 1 || s.is_starred === true);
      }

      return tagMatch && kwMatch && posMatch && catMatch && starMatch;
    });

    if (filtered.length === 0) {
      showToast(`선택한 어법 및 키워드 조건에 일치하는 문장이 없습니다.`, "warning");
    } else {
      showToast(`결과 필터링: ${filtered.length}개 문장이 표시됩니다.`, "success");
    }

    appState.sentencesData = filtered;
    resultsTotalCount.textContent = filtered.length;
    renderSentenceView(appState.sentencesData);
  }

  updateClearButtons();
}

/** 검색창 초기화 x 버튼 가시성 업데이트 */
export function updateClearButtons() {
  if (btnClearMainSearch && mainSearchInput) {
    btnClearMainSearch.style.display = mainSearchInput.value.trim().length > 0 ? "inline-flex" : "none";
  }
  if (btnClearResultsSearch && resultsSearchInput) {
    btnClearResultsSearch.style.display = resultsSearchInput.value.trim().length > 0 ? "inline-flex" : "none";
  }
  if (typeof updateFilterResetButtonsUI === "function") {
    updateFilterResetButtonsUI();
  }
}

/** 온전한 단어 검색 토글 상태 동기화 및 제어 */
function setWholeWordState(active) {
  isWholeWordActive = !!active;
  [btnHomeToggleWholeWord, btnToggleWholeWord].forEach(btn => {
    if (btn) {
      btn.classList.toggle("active", isWholeWordActive);
      btn.setAttribute("aria-pressed", String(isWholeWordActive));
    }
  });
}

/** 결과 내 검색 토글 상태 제어 */
export function setSearchWithinState(active) {
  appState.isSearchWithinActive = !!active;
  if (btnToggleSearchWithin) {
    btnToggleSearchWithin.classList.toggle("active", appState.isSearchWithinActive);
    btnToggleSearchWithin.setAttribute("aria-pressed", String(appState.isSearchWithinActive));
  }
}

// 결과창 검색 실행 함수 (토글 활성 여부에 따라 결과 내 검색 또는 전체 DB 검색 수행)
function handleResultsSearch() {
  if (appState.isSearchWithinActive) {
    executeSearchWithinResults();
  } else {
    executeSearch("results");
  }
}
// =========================================================================
// 검색 조건(필터/검색어) 초기화 및 동기화 관리
// =========================================================================

/** 현재 활성화된 검색 조건(검색어, 학년, 연도, 월, 시험구분, 문제유형, 어법, 별표, 결과내검색)이 있는지 확인 */
export function hasActiveSearchFilters() {
  const hasKeyword = !!((resultsSearchInput && resultsSearchInput.value.trim()) || (mainSearchInput && mainSearchInput.value.trim()));
  const hasGrade = !!((resultsFilterGrade && resultsFilterGrade.value) || (filterGrade && filterGrade.value));
  const hasYear = !isAllYearsSelected();
  const hasMonth = !!((resultsFilterMonth && resultsFilterMonth.value) || (filterMonth && filterMonth.value));
  const hasExamType = !!((resultsFilterExamType && resultsFilterExamType.value) || (filterExamType && filterExamType.value));
  const hasQuestionType = !!((resultsFilterQuestionType && resultsFilterQuestionType.value) || (filterQuestionType && filterQuestionType.value));
  const hasCorrectRate = !!((resultsFilterCorrectRate && resultsFilterCorrectRate.value) || (filterCorrectRate && filterCorrectRate.value));
  const hasGrammarPos = !!((resultsFilterGrammarPos && resultsFilterGrammarPos.value) || (filterGrammarPos && filterGrammarPos.value));
  const hasGrammarCat = !!((resultsFilterGrammarCategory && resultsFilterGrammarCategory.value) || (filterGrammarCategory && filterGrammarCategory.value));
  return hasKeyword || hasGrade || hasYear || hasMonth || hasExamType || hasQuestionType || hasCorrectRate || hasGrammarPos || hasGrammarCat || !!appState.isStarredFilterActive || !!appState.isSearchWithinActive;
}

/** 검색 조건 초기화 버튼 가시성 및 필터 드롭다운 active 스타일 업데이트 */
export function updateFilterResetButtonsUI() {
  const hasFilters = hasActiveSearchFilters();
  const hasYear = !isAllYearsSelected();

  // 연도 트리거 버튼 active 스타일 동기화
  document.querySelectorAll(".year-multiselect-trigger").forEach(btn => {
    btn.classList.toggle("active", hasYear);
  });

  // 드롭다운 필터 active 스타일 동기화
  const pairs = [
    [filterGrade, resultsFilterGrade],
    [filterYear, resultsFilterYear],
    [filterMonth, resultsFilterMonth],
    [filterExamType, resultsFilterExamType],
    [filterQuestionType, resultsFilterQuestionType],
    [filterCorrectRate, resultsFilterCorrectRate],
  ];
  pairs.forEach(([homeEl, resEl]) => {
    if (homeEl) homeEl.classList.toggle("active", !!homeEl.value);
    if (resEl) resEl.classList.toggle("active", !!resEl.value);
  });

  // 결과창 검색 조건 초기화 버튼 (가장 긴 형태의 배열 상태 유지를 위해 자리 유지)
  if (btnResetResultsFilters) {
    btnResetResultsFilters.style.visibility = hasFilters ? "visible" : "hidden";
    btnResetResultsFilters.style.opacity = hasFilters ? "1" : "0";
    btnResetResultsFilters.style.pointerEvents = hasFilters ? "auto" : "none";
  }

  // 홈 화면 검색 조건 초기화 버튼 (가장 긴 형태의 배열 상태 유지를 위해 자리 유지)
  if (btnResetHomeFilters) {
    btnResetHomeFilters.style.visibility = hasFilters ? "visible" : "hidden";
    btnResetHomeFilters.style.opacity = hasFilters ? "1" : "0";
    btnResetHomeFilters.style.pointerEvents = hasFilters ? "auto" : "none";
  }
}

/** 모든 검색 조건(검색어, 기본 필터, 어법 필터, 트리 네비게이션, 결과 내 검색)을 초기화 */
export function resetAllSearchFilters(triggerSearch = true) {
  // 1. 검색어 초기화
  if (mainSearchInput) mainSearchInput.value = "";
  if (resultsSearchInput) resultsSearchInput.value = "";
  if (btnClearMainSearch) btnClearMainSearch.style.display = "none";
  if (btnClearResultsSearch) btnClearResultsSearch.style.display = "none";

  // 2. 기본 필터 드롭다운 초기화
  if (filterGrade) filterGrade.value = "";
  if (resultsFilterGrade) resultsFilterGrade.value = "";
  if (filterYear) filterYear.value = "";
  if (resultsFilterYear) resultsFilterYear.value = "";
  if (filterMonth) filterMonth.value = "";
  if (resultsFilterMonth) resultsFilterMonth.value = "";
  if (filterExamType) filterExamType.value = "";
  if (resultsFilterExamType) resultsFilterExamType.value = "";
  if (filterQuestionType) filterQuestionType.value = "";
  if (resultsFilterQuestionType) resultsFilterQuestionType.value = "";
  if (filterCorrectRate) filterCorrectRate.value = "";
  if (resultsFilterCorrectRate) resultsFilterCorrectRate.value = "";
  if (filterTag) filterTag.value = "";

  resetYearFilter();
  updateMonthOptionsByGrade("");

  // 3. 어법 필터 초기화
  if (typeof resetAllGrammarFilters === "function") {
    resetAllGrammarFilters(false);
  }

  // 4. 결과 내 검색 및 트리 상태 초기화
  if (typeof setSearchWithinState === "function") {
    setSearchWithinState(false);
  }
  appState.treeNavState.grade = null;
  appState.treeNavState.year = null;
  appState.treeNavState.month = null;

  // 5. 버튼 가시성 및 UI 갱신
  updateFilterResetButtonsUI();

  // 6. 검색 재실행 (결과 화면에서 전체 지문/문장 조회)
  if (triggerSearch) {
    executeSearch(appState.currentMode === "passage" ? "all_passages" : "results");
    showToast("검색 조건이 초기화되었습니다.", "info");
  }
}

// 영역 선택 토글 (독해 vs 듣기) 공통 설정 함수
export function setSearchArea(area, triggerSearch = true) {
  appState.currentArea = area;
  document.querySelectorAll(".area-toggle-btn").forEach(btn => {
    const bArea = btn.getAttribute("data-area");
    btn.classList.toggle("active", bArea === area);
  });
  updateQuestionTypeOptions(area);
  if (triggerSearch) {
    const resultsScreen = document.getElementById("resultsScreen");
    if (resultsScreen && resultsScreen.style.display !== "none") {
      executeSearch("results");
    }
  }
}

// ---- 이벤트 바인딩 및 초기화 (main.js 에서 원본 순서대로 호출) ----
export function init() {
  loadStats();
  updateQuestionTypeOptions(appState.currentArea || "reading");

  // [첫번째 첨부 이미지 클릭] : 통계 배지 클릭 시 -> 전체 지문이 결과창에 표시됨
  if (statsBadge) {
    statsBadge.addEventListener("click", () => {
      // 모든 필터 및 검색어 비우기 (전체 지문 조회)
      mainSearchInput.value = "";
      if (resultsSearchInput) resultsSearchInput.value = "";
      filterGrade.value = "";
      filterYear.value = "";
      filterMonth.value = "";
      filterExamType.value = "";
      filterQuestionType.value = "";
      if (filterCorrectRate) filterCorrectRate.value = "";
      if (filterTag) filterTag.value = "";

      if (resultsFilterGrade) resultsFilterGrade.value = "";
      if (resultsFilterYear) resultsFilterYear.value = "";
      if (resultsFilterMonth) resultsFilterMonth.value = "";
      if (resultsFilterExamType) resultsFilterExamType.value = "";
      if (resultsFilterQuestionType) resultsFilterQuestionType.value = "";
      if (resultsFilterCorrectRate) resultsFilterCorrectRate.value = "";

      resetYearFilter();
      updateMonthOptionsByGrade("");

      setMode("passage");
      updateClearButtons();
      executeSearch("all_passages");
    });
  }

  // 월 필터 및 연도 복수 선택 모듈 초기화
  initMonthFilter();
  initYearFilter((sourcePrefix) => {
    if (resultsView && resultsView.style.display !== "none") {
      setSearchWithinState(false);
      updateFilterResetButtonsUI();
      executeSearch("results");
    } else {
      updateFilterResetButtonsUI();
    }
  });

  // 검색창 입력 시 x 버튼 동적 표시/숨김
  if (mainSearchInput) {
    mainSearchInput.addEventListener("input", updateClearButtons);
  }
  if (resultsSearchInput) {
    resultsSearchInput.addEventListener("input", updateClearButtons);
  }

  // 홈 검색창 x 버튼 클릭: 입력값 초기화
  if (btnClearMainSearch) {
    btnClearMainSearch.addEventListener("click", () => {
      if (mainSearchInput) {
        mainSearchInput.value = "";
        mainSearchInput.focus();
      }
      updateClearButtons();
    });
  }

  // 결과창 검색창 x 버튼 클릭: 입력값 초기화 및 결과창 초기화(전체 결과 재검색/표시)
  if (btnClearResultsSearch) {
    btnClearResultsSearch.addEventListener("click", () => {
      if (resultsSearchInput) {
        resultsSearchInput.value = "";
        resultsSearchInput.focus();
      }
      if (mainSearchInput) {
        mainSearchInput.value = "";
      }
      updateClearButtons();
      handleResultsSearch();
    });
  }

  // 단어 단위 검색 토글 버튼 이벤트 연결
  [btnHomeToggleWholeWord, btnToggleWholeWord].forEach(btn => {
    if (btn) {
      btn.addEventListener("click", () => {
        setWholeWordState(!isWholeWordActive);
        if (isWholeWordActive) {
          showToast("단어 단위 검색이 켜졌습니다. (독립 단어만 정확히 일치)", "info");
        } else {
          showToast("단어 단위 검색이 꺼졌습니다. (부분 일치 검색)", "info");
        }
        // 결과창 화면이 표시되어 있으면 현재 조건으로 즉시 재검색 실행
        if (resultsView && resultsView.style.display !== "none") {
          handleResultsSearch();
        }
      });
    }
  });

  // 홈 검색 트리거
  btnSearch.addEventListener("click", () => executeSearch("home"));
  mainSearchInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") executeSearch("home");
  });

  // 영역 선택 토글 클릭 핸들러 (독해 vs 듣기)
  document.querySelectorAll(".area-toggle-group").forEach(group => {
    group.addEventListener("click", (e) => {
      const btn = e.target.closest(".area-toggle-btn");
      if (!btn) return;
      const targetArea = btn.getAttribute("data-area");
      if (!targetArea) return;
      if (btn.classList.contains("disabled") || btn.disabled) {
        showToast("🎧 듣기 영역 서비스는 현재 준비 중입니다.", "info");
        return;
      }
      if (targetArea !== appState.currentArea) {
        setSearchArea(targetArea, true);
        showToast(targetArea === "listening" ? "🎧 듣기 영역 모드로 전환되었습니다." : "📖 독해 영역 모드로 전환되었습니다.", "info");
      }
    });
  });

  // 결과 내 검색 토글 클릭 핸들러
  if (btnToggleSearchWithin) {
    btnToggleSearchWithin.addEventListener("click", () => {
      setSearchWithinState(!appState.isSearchWithinActive);
      if (appState.isSearchWithinActive) {
        showToast("결과 내 재검색 모드가 켜졌습니다. (검색 버튼을 누르면 현재 결과 목록 내에서 필터링됩니다)", "info");
      } else {
        showToast("결과 내 재검색 모드가 꺼졌습니다. (검색 버튼을 누르면 전체 DB를 검색합니다)", "info");
      }
    });
  }

  // 결과창 검색 트리거 (검색 버튼 및 엔터키)
  if (btnResultsSearch) {
    btnResultsSearch.addEventListener("click", handleResultsSearch);
  }
  if (resultsSearchInput) {
    resultsSearchInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter") handleResultsSearch();
    });
  }

  // 결과창 '↺ 검색 조건 초기화' 버튼 이벤트
  if (btnResetResultsFilters) {
    btnResetResultsFilters.addEventListener("click", () => {
      resetAllSearchFilters(true);
    });
  }

  // 홈 화면 '↺ 검색 조건 초기화' 버튼 이벤트
  if (btnResetHomeFilters) {
    btnResetHomeFilters.addEventListener("click", () => {
      resetAllSearchFilters(false);
      showToast("검색 조건이 초기화되었습니다.", "info");
    });
  }

  // 홈 필터 드롭다운 변경 시 초기화 버튼 상태 업데이트
  [filterGrade, filterYear, filterMonth, filterExamType, filterQuestionType, filterCorrectRate].forEach((el) => {
    if (el) {
      el.addEventListener("change", updateFilterResetButtonsUI);
    }
  });

  // 결과창 필터 변경 시 자동 재검색 (필터 변경은 항상 DB 전체 기반으로 재검색)
  [resultsFilterGrade, resultsFilterYear, resultsFilterMonth, resultsFilterExamType, resultsFilterQuestionType, resultsFilterCorrectRate].forEach((el) => {
    if (el) {
      el.addEventListener("change", () => {
        setSearchWithinState(false);
        updateFilterResetButtonsUI();
        executeSearch("results");
      });
    }
  });
}
