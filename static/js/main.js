/**
 * 05-gichul_db: 메인 프론트엔드 자바스크립트 로직 (main.js)
 * - 통계 배지 클릭 시 전체 지문 결과 표시
 * - 동일 위치(헤더 슬롯) '전체 문장' <-> '지문 결과창으로 돌아가기' 양방향 전환
 * - 검색창 화면과 결과창 화면의 완전한 분리 및 전환
 * - 상단 가로 문항별 탭 바(복수 결과 탭 전환) 및 전체 너비 2x2 그리드
 * - 1행 테이블 문장 뷰어 및 클립보드 원클릭 복사
 * - PDF+HWP 업로드 및 상호 검증 파이프라인
 */

document.addEventListener("DOMContentLoaded", () => {
  // 상태 변수
  let currentMode = "passage"; // 'passage' 또는 'sentence'
  let currentPassageId = null;
  let currentPassageIndex = 0;
  let passagesData = [];
  let sentencesData = [];
  let rawPassagesData = []; // '결과 내 검색' 필터링용 원본 지문 목록 캐시
  let rawSentencesData = []; // '결과 내 검색' 필터링용 원본 문장 목록 캐시

  // =========================================================================
  // DOM 요소 캐싱
  // =========================================================================
  
  // 글로벌 헤더 & 홈 로고
  const btnGoHome = document.getElementById("btnGoHome");
  const statPassages = document.getElementById("statPassages");
  const statSentences = document.getElementById("statSentences");
  const btnSeedSample = document.getElementById("btnSeedSample");
  const btnOpenUploadModal = document.getElementById("btnOpenUploadModal");

  // 헤더 동적 액션 슬롯 (통계 배지 <-> 전체 문장 버튼 <-> 지문 복귀 버튼)
  const statsBadge = document.getElementById("statsBadge");
  const btnHeaderFlow = document.getElementById("btnHeaderFlow");

  // 화면 1: 홈 검색 화면
  const homeSearchView = document.getElementById("homeSearchView");
  const tabModePassage = document.getElementById("tabModePassage");
  const tabModeSentence = document.getElementById("tabModeSentence");
  const mainSearchInput = document.getElementById("mainSearchInput");
  const btnClearMainSearch = document.getElementById("btnClearMainSearch");
  const btnSearch = document.getElementById("btnSearch");
  const btnHomeToggleWholeWord = document.getElementById("btnHomeToggleWholeWord");

  // 홈 필터
  const filterGrade = document.getElementById("filterGrade");
  const filterYear = document.getElementById("filterYear");
  const filterMonth = document.getElementById("filterMonth");
  const filterExamType = document.getElementById("filterExamType");
  const filterQuestionType = document.getElementById("filterQuestionType");
  const filterTag = document.getElementById("filterTag");

  // 화면 2: 결과창 화면
  const resultsView = document.getElementById("resultsView");
  const btnBackToSearch = document.getElementById("btnBackToSearch");
  const resultsSearchInput = document.getElementById("resultsSearchInput");
  const btnClearResultsSearch = document.getElementById("btnClearResultsSearch");
  const btnResultsSearch = document.getElementById("btnResultsSearch");
  const btnToggleSearchWithin = document.getElementById("btnToggleSearchWithin") || document.getElementById("btnSearchWithinResults");
  let isSearchWithinActive = false;
  const btnToggleWholeWord = document.getElementById("btnToggleWholeWord");
  let isWholeWordActive = false;
  const resultsTabModePassage = document.getElementById("resultsTabModePassage");
  const resultsTabModeSentence = document.getElementById("resultsTabModeSentence");

  // 결과창 필터
  const resultsFilterGrade = document.getElementById("resultsFilterGrade");
  const resultsFilterYear = document.getElementById("resultsFilterYear");
  const resultsFilterMonth = document.getElementById("resultsFilterMonth");
  const resultsFilterExamType = document.getElementById("resultsFilterExamType");
  const resultsFilterQuestionType = document.getElementById("resultsFilterQuestionType");
  const resultsTotalCount = document.getElementById("resultsTotalCount");

  // 상태 컨테이너
  const loadingIndicator = document.getElementById("loadingIndicator");
  const emptyResultsBox = document.getElementById("emptyResultsBox");
  const btnEmptyBackToSearch = document.getElementById("btnEmptyBackToSearch");

  // [지문 결과 화면] 요소
  const passageViewContainer = document.getElementById("passageViewContainer");
  const passageTabBarContainer = document.getElementById("passageTabBarContainer");
  const passageTabBar = document.getElementById("passageTabBar");
  const passageTabCount = document.getElementById("passageTabCount");
  const treeBreadcrumbBar = document.getElementById("treeBreadcrumbBar");
  const treeBreadcrumbHome = document.getElementById("treeBreadcrumbHome");
  const breadcrumbTrail = document.getElementById("breadcrumbTrail");
  const btnTreeResetExam = document.getElementById("btnTreeResetExam");
  const btnTreeChangeExam = document.getElementById("btnTreeChangeExam");
  const treeStepSelector = document.getElementById("treeStepSelector");
  const btnTabScrollLeft = document.getElementById("btnTabScrollLeft");
  const btnTabScrollRight = document.getElementById("btnTabScrollRight");

  // 트리 계층형 네비게이션 상태 ([학년] -> [년도] -> [월] -> [문항 1행 10개])
  let treeNavState = {
    grade: null,
    year: null,
    month: null
  };
  let currentExamQuestions = []; // 현재 선택된 시험의 문항 목록 (최하위 10열 그리드 렌더링용)

  // 2x2 그리드 요소
  const panelPdfImageContainer = document.getElementById("panelPdfImageContainer");
  const panelPassageText = document.getElementById("panelPassageText");
  const panelExplanation = document.getElementById("panelExplanation");
  const metaPassageId = document.getElementById("metaPassageId");
  const metaQNum = document.getElementById("metaQNum");
  const metaAnswer = document.getElementById("metaAnswer");
  const metaQuestionTitle = document.getElementById("metaQuestionTitle");
  const metaQuestionType = document.getElementById("metaQuestionType");
  const selectQuestionType = document.getElementById("selectQuestionType");
  const validationBadge = document.getElementById("validationBadge");
  const passageTagsList = document.getElementById("passageTagsList");
  const inputPassageTag = document.getElementById("inputPassageTag");
  const btnAddPassageTag = document.getElementById("btnAddPassageTag");
  const btnCopyPassage = document.getElementById("btnCopyPassage");
  const btnCardPassageSentences = document.getElementById("btnCardPassageSentences");
  const btnCopyExplanation = document.getElementById("btnCopyExplanation");

  // [문장 결과 화면] 요소
  const sentenceViewContainer = document.getElementById("sentenceViewContainer");
  const sentenceMatchCount = document.getElementById("sentenceMatchCount");
  const sentenceTableBody = document.getElementById("sentenceTableBody");
  const btnSentenceBackToPassage = document.getElementById("btnSentenceBackToPassage");

  // 어법 범주 필터 및 별표 필터
  const homeGrammarFiltersGroup = document.getElementById("homeGrammarFiltersGroup");
  const resultsGrammarFiltersGroup = document.getElementById("resultsGrammarFiltersGroup");
  const filterGrammarPos = document.getElementById("filterGrammarPos");
  const filterGrammarCategory = document.getElementById("filterGrammarCategory");
  const btnResetHomeGrammarFilter = document.getElementById("btnResetHomeGrammarFilter");
  const btnToggleStarred = document.getElementById("btnToggleStarred");
  const resultsFilterGrammarPos = document.getElementById("resultsFilterGrammarPos");
  const resultsFilterGrammarCategory = document.getElementById("resultsFilterGrammarCategory");
  const btnResetResultsGrammarFilter = document.getElementById("btnResetResultsGrammarFilter");
  const btnResultsToggleStarred = document.getElementById("btnResultsToggleStarred");
  const btnBatchAnalyzeStarred = document.getElementById("btnBatchAnalyzeStarred");
  const btnBatchAnalyzeAll = document.getElementById("btnBatchAnalyzeAll");
  let isStarredFilterActive = false;
  let grammarCategoriesList = [];

  // AI 설정 모달 요소
  const btnOpenAiSettingsModal = document.getElementById("btnOpenAiSettingsModal");
  const aiSettingsModal = document.getElementById("aiSettingsModal");
  const btnCloseAiSettingsModal = document.getElementById("btnCloseAiSettingsModal");
  const btnCancelAiSettings = document.getElementById("btnCancelAiSettings");
  const aiProviderSelect = document.getElementById("aiProviderSelect");
  const openrouterModelGroup = document.getElementById("openrouterModelGroup");
  const openrouterModelSelect = document.getElementById("openrouterModelSelect");
  const btnRefreshOpenRouterModels = document.getElementById("btnRefreshOpenRouterModels");
  const openrouterModelInfoCard = document.getElementById("openrouterModelInfoCard");
  const infoModelBadge = document.getElementById("infoModelBadge");
  const infoModelName = document.getElementById("infoModelName");
  const infoModelTag = document.getElementById("infoModelTag");
  const infoModelPromptPrice = document.getElementById("infoModelPromptPrice");
  const infoModelCompletionPrice = document.getElementById("infoModelCompletionPrice");
  const infoModelContext = document.getElementById("infoModelContext");
  const infoModelDesc = document.getElementById("infoModelDesc");
  let openrouterTopModelsData = [];
  const aiModelInput = document.getElementById("aiModelInput");
  const aiModelHelp = document.getElementById("aiModelHelp");
  const aiApiKeyInput = document.getElementById("aiApiKeyInput");
  const btnToggleKeyVis = document.getElementById("btnToggleKeyVis");
  const currentKeyBadge = document.getElementById("currentKeyBadge");
  const apiKeyGuideLink = document.getElementById("apiKeyGuideLink");
  const aiSettingsStatus = document.getElementById("aiSettingsStatus");
  const btnSaveAiSettings = document.getElementById("btnSaveAiSettings");

  // 업로드 모달 요소
  const uploadModal = document.getElementById("uploadModal");
  const uploadForm = document.getElementById("uploadForm");
  const btnCloseUploadModal = document.getElementById("btnCloseUploadModal");
  const btnCancelUpload = document.getElementById("btnCancelUpload");
  const modalExamType = document.getElementById("modalExamType");
  const modalMonth = document.getElementById("modalMonth");

  // AI 일괄 분석 실시간 진행 모달 요소
  const batchAnalysisModal = document.getElementById("batchAnalysisModal");
  const batchModalStatusBadge = document.getElementById("batchModalStatusBadge");
  const batchProgressLabel = document.getElementById("batchProgressLabel");
  const batchProgressCounter = document.getElementById("batchProgressCounter");
  const batchProgressBar = document.getElementById("batchProgressBar");
  const batchCurrentCard = document.getElementById("batchCurrentCard");
  const batchCurrentSentId = document.getElementById("batchCurrentSentId");
  const batchCurrentSentText = document.getElementById("batchCurrentSentText");
  const batchLogCount = document.getElementById("batchLogCount");
  const batchLogList = document.getElementById("batchLogList");
  const batchFooterInfo = document.getElementById("batchFooterInfo");
  const btnCancelBatchAnalysis = document.getElementById("btnCancelBatchAnalysis");
  const btnCloseBatchModal = document.getElementById("btnCloseBatchModal");
  let isBatchCancelled = false;

  // 어법 범주 상세 해설 플로팅 팝오버 요소
  const grammarExplanationPopover = document.getElementById("grammarExplanationPopover");
  const popoverBadge = document.getElementById("popoverBadge");
  const popoverPath = document.getElementById("popoverPath");
  const btnCloseGrammarPopover = document.getElementById("btnCloseGrammarPopover");
  const popoverPhraseSection = document.getElementById("popoverPhraseSection");
  const popoverPhraseText = document.getElementById("popoverPhraseText");
  const popoverExplanationText = document.getElementById("popoverExplanationText");

  // =========================================================================
  // 1. 헤더 액션 슬롯 상태 제어 (통계 배지 <-> 전체 문장 <-> 지문 복귀)
  // =========================================================================

  /**
   * 헤더 액션 슬롯 상태 전환 함수
   * @param {'home' | 'passage' | 'sentence'} state 
   */
  function setHeaderSlotState(state) {
    if (!statsBadge || !btnHeaderFlow) return;

    if (state === "home") {
      statsBadge.style.display = "flex";
      btnHeaderFlow.style.display = "none";
    } else if (state === "passage") {
      statsBadge.style.display = "none";
      btnHeaderFlow.style.display = "inline-flex";
      btnHeaderFlow.textContent = "📝 해당 지문의 전체 문장";
      btnHeaderFlow.title = "해당 지문의 전체 문장 결과창 보기";
      btnHeaderFlow.classList.remove("mode-back");
    } else if (state === "sentence") {
      statsBadge.style.display = "none";
      btnHeaderFlow.style.display = "inline-flex";
      btnHeaderFlow.textContent = "🔙 지문 결과창으로 돌아가기";
      btnHeaderFlow.title = "이전 지문 상세 화면으로 복귀";
      btnHeaderFlow.classList.add("mode-back");
    }
  }

  // =========================================================================
  // 2. 화면 전환 및 동기화 로직
  // =========================================================================

  /** 홈 검색 화면으로 복귀 */
  function showHomeScreen() {
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

    window.scrollTo({ top: 0, behavior: "smooth" });
    mainSearchInput.focus();
    if (typeof updateClearButtons === "function") updateClearButtons();
  }

  /** 상단 결과 내비게이션 바 높이를 동적으로 측정하여 CSS 변수(--results-nav-height)로 동기화 */
  function updateResultsNavHeight() {
    const navBar = document.querySelector(".results-nav-bar");
    if (navBar && navBar.offsetHeight > 0) {
      document.documentElement.style.setProperty("--results-nav-height", `${navBar.offsetHeight}px`);
    }
  }

  window.addEventListener("resize", updateResultsNavHeight);

  /** 결과 화면으로 전환 */
  function showResultsScreen() {
    homeSearchView.style.display = "none";
    resultsView.style.display = "flex";
    if (btnBackToSearch) btnBackToSearch.style.display = "inline-flex";
    window.scrollTo({ top: 0, behavior: "smooth" });
    updateGrammarFiltersVisibility();
    if (typeof updateClearButtons === "function") updateClearButtons();
    setTimeout(updateResultsNavHeight, 30);
  }

  // 홈으로 이동 버튼 이벤트 연결
  btnGoHome.addEventListener("click", showHomeScreen);
  btnBackToSearch.addEventListener("click", showHomeScreen);
  if (btnEmptyBackToSearch) {
    btnEmptyBackToSearch.addEventListener("click", showHomeScreen);
  }

  // =========================================================================
  // 3. 모드 전환 (지문 검색 vs 문장 검색)
  // =========================================================================

  /** 문장 검색 모드일 때만 어법 대분류/세부어법/중요문장 필터를 노출 (지문 검색 시 숨김) */
  function updateGrammarFiltersVisibility() {
    const isSentence = (currentMode === "sentence");
    if (homeGrammarFiltersGroup) {
      homeGrammarFiltersGroup.style.display = isSentence ? "inline-flex" : "none";
    }
    if (resultsGrammarFiltersGroup) {
      resultsGrammarFiltersGroup.style.display = isSentence ? "inline-flex" : "none";
    }
  }

  function setMode(mode, triggerSearch = false) {
    currentMode = mode;
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

  tabModePassage.addEventListener("click", () => setMode("passage"));
  tabModeSentence.addEventListener("click", () => setMode("sentence"));
  if (resultsTabModePassage) {
    resultsTabModePassage.addEventListener("click", () => {
      if (currentMode === "passage") return;
      backToPassageView();
    });
  }
  if (resultsTabModeSentence) {
    resultsTabModeSentence.addEventListener("click", () => {
      if (currentMode === "sentence") return;
      showSentencesForPassage(currentPassageId);
    });
  }

  // =========================================================================
  // 4. 통계 데이터 로드 및 통계 배지 클릭(전체 지문 보기)
  // =========================================================================

  async function loadStats() {
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
  loadStats();

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
      if (filterTag) filterTag.value = "";

      if (resultsFilterGrade) resultsFilterGrade.value = "";
      if (resultsFilterYear) resultsFilterYear.value = "";
      if (resultsFilterMonth) resultsFilterMonth.value = "";
      if (resultsFilterExamType) resultsFilterExamType.value = "";
      if (resultsFilterQuestionType) resultsFilterQuestionType.value = "";

      setMode("passage");
      updateClearButtons();
      executeSearch("all_passages");
    });
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
  function highlightTextKeyword(text, rawQuery, highlightClass = "sentence-highlight") {
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

  function highlightSentenceKeyword(text, rawQuery) {
    return highlightTextKeyword(text, rawQuery, "sentence-highlight");
  }

  // =========================================================================
  // 5. 검색 실행 함수
  // =========================================================================

  /** 통합 검색 실행 */
  async function executeSearch(source = "home") {
    let keyword = "";
    let grade = "";
    let year = "";
    let month = "";
    let examType = "";
    let questionType = "";
    let tag = "";

    if (source === "all" || source === "all_passages") {
      // 전체 보기 (조건 없음)
      keyword = "";
      grade = "";
      year = "";
      month = "";
      examType = "";
      questionType = "";
      tag = "";
    } else if (source === "home") {
      const parsed = parseSearchQuery(mainSearchInput.value);
      keyword = parsed.keyword;
      tag = parsed.tag;
      grade = filterGrade.value;
      year = filterYear.value;
      month = filterMonth.value;
      examType = filterExamType ? filterExamType.value : "";
      questionType = filterQuestionType ? filterQuestionType.value : "";

      // 결과창 바에 동기화
      if (resultsSearchInput) resultsSearchInput.value = mainSearchInput.value.trim();
      if (resultsFilterGrade) resultsFilterGrade.value = grade;
      if (resultsFilterYear) resultsFilterYear.value = year;
      if (resultsFilterMonth) resultsFilterMonth.value = month;
      if (resultsFilterExamType) resultsFilterExamType.value = examType;
      if (resultsFilterQuestionType) resultsFilterQuestionType.value = questionType;
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

      // 홈 바에 역동기화
      mainSearchInput.value = resultsSearchInput.value.trim();
      filterGrade.value = grade;
      filterYear.value = year;
      filterMonth.value = month;
      filterExamType.value = examType;
      filterQuestionType.value = questionType;
      if (filterGrammarPos && resultsFilterGrammarPos) filterGrammarPos.value = resultsFilterGrammarPos.value;
      if (filterGrammarCategory && resultsFilterGrammarCategory) filterGrammarCategory.value = resultsFilterGrammarCategory.value;
    }

    if (typeof updateGrammarBreadcrumbFilterUI === "function") {
      updateGrammarBreadcrumbFilterUI();
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
    if (year) params.append("year", year);
    if (month) params.append("month", month);
    if (examType) params.append("exam_type", examType);
    if (questionType) params.append("question_type", questionType);
    if (tag) params.append("tag", tag);

    const activeGrammarPos = (resultsFilterGrammarPos && resultsFilterGrammarPos.value) || (filterGrammarPos && filterGrammarPos.value) || "";
    const activeGrammarCat = (resultsFilterGrammarCategory && resultsFilterGrammarCategory.value) || (filterGrammarCategory && filterGrammarCategory.value) || "";

    if (activeGrammarCat) {
      params.append("grammar_cat_id", activeGrammarCat);
    } else if (activeGrammarPos) {
      params.append("grammar_pos", activeGrammarPos);
    }

    if (isStarredFilterActive) {
      params.append("is_starred", "true");
    }

    params.append("limit", "5000");

    try {
      if (currentMode === "passage") {
        treeNavState = { grade: null, year: null, month: null };
        const res = await fetch(`/api/search/passages?${params.toString()}`);
        const data = await res.json();
        passagesData = groupPassageItems(data.items || []);
        rawPassagesData = [...passagesData]; // 원본 캐시 갱신
        resultsTotalCount.textContent = passagesData.length;
        renderPassageView(passagesData);
        setHeaderSlotState("passage");
        updateGrammarFiltersVisibility();
      } else {
        const res = await fetch(`/api/search/sentences?${params.toString()}`);
        const data = await res.json();
        sentencesData = data.items || [];
        rawSentencesData = [...sentencesData]; // 원본 캐시 갱신
        resultsTotalCount.textContent = sentencesData.length;
        renderSentenceView(sentencesData);
        setHeaderSlotState("sentence");
        updateGrammarFiltersVisibility();
      }
    } catch (err) {
      console.error("검색 오류:", err);
      showToast("검색 중 오류가 발생했습니다.", "error");
    } finally {
      loadingIndicator.style.display = "none";
    }
  }

  /** 현재 로드된 결과 목록 내에서 키워드 또는 #태그로 즉시 필터링(결과 내 검색) */
  function executeSearchWithinResults() {
    const rawVal = resultsSearchInput ? resultsSearchInput.value.trim() : "";

    if (!rawVal) {
      // 검색어가 비어있으면 원본 목록 전체 복원
      if (currentMode === "passage") {
        passagesData = [...rawPassagesData];
        resultsTotalCount.textContent = passagesData.length;
        renderPassageView(passagesData);
      } else {
        sentencesData = [...rawSentencesData];
        resultsTotalCount.textContent = sentencesData.length;
        renderSentenceView(sentencesData);
      }
      showToast("전체 검색 결과가 다시 표시됩니다.", "info");
      return;
    }

    const { keyword: kwRaw, tag: tagRaw } = parseSearchQuery(rawVal);
    const kw = kwRaw.toLowerCase();
    const tagLower = tagRaw.toLowerCase();

    if (currentMode === "passage") {
      if (!rawPassagesData || rawPassagesData.length === 0) {
        showToast("필터링할 지문 검색 결과가 없습니다.", "warning");
        return;
      }

      const filtered = rawPassagesData.filter(p => {
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

      treeNavState = { grade: null, year: null, month: null };
      passagesData = filtered;
      resultsTotalCount.textContent = filtered.length;
      renderPassageView(passagesData);
    } else {
      if (!rawSentencesData || rawSentencesData.length === 0) {
        showToast("필터링할 문장 검색 결과가 없습니다.", "warning");
        return;
      }

      const activePos = (resultsFilterGrammarPos && resultsFilterGrammarPos.value) || (filterGrammarPos && filterGrammarPos.value) || "";
      const activeCatId = (resultsFilterGrammarCategory && resultsFilterGrammarCategory.value) || (filterGrammarCategory && filterGrammarCategory.value) || "";

      const filtered = rawSentencesData.filter(s => {
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
        if (isStarredFilterActive) {
          starMatch = (s.is_starred === 1 || s.is_starred === true);
        }

        return tagMatch && kwMatch && posMatch && catMatch && starMatch;
      });

      if (filtered.length === 0) {
        showToast(`선택한 어법 및 키워드 조건에 일치하는 문장이 없습니다.`, "warning");
      } else {
        showToast(`결과 필터링: ${filtered.length}개 문장이 표시됩니다.`, "success");
      }

      sentencesData = filtered;
      resultsTotalCount.textContent = filtered.length;
      renderSentenceView(sentencesData);
    }

    updateClearButtons();
  }

  /** 검색창 초기화 x 버튼 가시성 업데이트 */
  function updateClearButtons() {
    if (btnClearMainSearch && mainSearchInput) {
      btnClearMainSearch.style.display = mainSearchInput.value.trim().length > 0 ? "inline-flex" : "none";
    }
    if (btnClearResultsSearch && resultsSearchInput) {
      btnClearResultsSearch.style.display = resultsSearchInput.value.trim().length > 0 ? "inline-flex" : "none";
    }
  }

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

  /** 결과 내 검색 토글 상태 제어 */
  function setSearchWithinState(active) {
    isSearchWithinActive = !!active;
    if (btnToggleSearchWithin) {
      btnToggleSearchWithin.classList.toggle("active", isSearchWithinActive);
      btnToggleSearchWithin.setAttribute("aria-pressed", String(isSearchWithinActive));
    }
  }

  // 결과 내 검색 토글 클릭 핸들러
  if (btnToggleSearchWithin) {
    btnToggleSearchWithin.addEventListener("click", () => {
      setSearchWithinState(!isSearchWithinActive);
      if (isSearchWithinActive) {
        showToast("결과 내 재검색 모드가 켜졌습니다. (검색 버튼을 누르면 현재 결과 목록 내에서 필터링됩니다)", "info");
      } else {
        showToast("결과 내 재검색 모드가 꺼졌습니다. (검색 버튼을 누르면 전체 DB를 검색합니다)", "info");
      }
    });
  }

  // 결과창 검색 실행 함수 (토글 활성 여부에 따라 결과 내 검색 또는 전체 DB 검색 수행)
  function handleResultsSearch() {
    if (isSearchWithinActive) {
      executeSearchWithinResults();
    } else {
      executeSearch("results");
    }
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

  // 결과창 필터 변경 시 자동 재검색 (필터 변경은 항상 DB 전체 기반으로 재검색)
  [resultsFilterGrade, resultsFilterYear, resultsFilterMonth, resultsFilterExamType, resultsFilterQuestionType].forEach((el) => {
    if (el) {
      el.addEventListener("change", () => {
        setSearchWithinState(false);
        executeSearch("results");
      });
    }
  });

  // =========================================================================
  // 6. [지문 검색 결과] 상단 문항별 탭 & 2x2 그리드 렌더링
  // =========================================================================

  /** 41~42번(1지문2문항), 43~45번(1지문3문항)을 단일 탭으로 병합 */
  function groupPassageItems(rawItems) {
    if (!rawItems || rawItems.length === 0) return [];

    const result = [];
    const handledIds = new Set();

    for (let i = 0; i < rawItems.length; i++) {
      const p = rawItems[i];
      if (handledIds.has(p.id)) continue;

      // 41~42번 (1지문 2문항) 통합
      if (p.q_num === 41 || (p.question_type === "1지문2문항" && p.q_num === 41)) {
        const p42 = rawItems.find(item => item.q_num === 42 && item.exam_id === p.exam_id);
        if (p42) {
          handledIds.add(p.id);
          handledIds.add(p42.id);

          const examPrefix = p.id.replace(/-41번\]$/, "").replace(/^\[/, "");
          const ans41 = p.answer_text || "-";
          const ans42 = p42.answer_text || "-";
          const ansLabel = `41.${ans41} / 42.${ans42}`;
          const combinedAns41_42 = `[정답] 41. ${ans41}   42. ${ans42}`;
          const baseExp41_42 = (p.explanation_text || p42.explanation_text || "").replace(/^\[정답\][^\n]*\n*/, "");
          const expText41_42 = `${combinedAns41_42}\n\n${baseExp41_42.trim()}`;

          result.push({
            ...p,
            isGroup: true,
            groupType: "41-42",
            q_num_label: "41~42번",
            display_id: `[${examPrefix}-41~42번]`,
            all_ids: [p.id, p42.id],
            subItems: [p, p42],
            question_type: "1지문2문항",
            answer_text: ansLabel,
            pdf_crop_images: [p.pdf_crop_image, p42.pdf_crop_image].filter(Boolean),
            explanation_text: expText41_42
          });
          continue;
        }
      }

      // 43~45번 (1지문 3문항) 통합
      if (p.q_num === 43 || (p.question_type === "1지문3문항" && p.q_num === 43)) {
        const p44 = rawItems.find(item => item.q_num === 44 && item.exam_id === p.exam_id);
        const p45 = rawItems.find(item => item.q_num === 45 && item.exam_id === p.exam_id);
        if (p44 && p45) {
          handledIds.add(p.id);
          handledIds.add(p44.id);
          handledIds.add(p45.id);

          const examPrefix = p.id.replace(/-43번\]$/, "").replace(/^\[/, "");
          const ans43 = p.answer_text || "-";
          const ans44 = p44.answer_text || "-";
          const ans45 = p45.answer_text || "-";
          const ansLabel = `43.${ans43} / 44.${ans44} / 45.${ans45}`;
          const combinedAns43_45 = `[정답] 43. ${ans43}   44. ${ans44}   45. ${ans45}`;
          const baseExp43_45 = (p.explanation_text || p44.explanation_text || p45.explanation_text || "").replace(/^\[정답\][^\n]*\n*/, "");
          const expText43_45 = `${combinedAns43_45}\n\n${baseExp43_45.trim()}`;

          result.push({
            ...p,
            isGroup: true,
            groupType: "43-45",
            q_num_label: "43~45번",
            display_id: `[${examPrefix}-43~45번]`,
            all_ids: [p.id, p44.id, p45.id],
            subItems: [p, p44, p45],
            question_type: "1지문3문항",
            answer_text: ansLabel,
            pdf_crop_images: [p.pdf_crop_image].filter(Boolean),
            explanation_text: expText43_45
          });
          continue;
        }
      }

      if (handledIds.has(p.id)) continue;

      result.push({
        ...p,
        q_num_label: p.q_num ? `${p.q_num}번` : p.id,
        display_id: p.id,
        all_ids: [p.id],
        pdf_crop_images: p.pdf_crop_image ? [p.pdf_crop_image] : []
      });
    }

    return result;
  }

  /** 42번, 44번, 45번 등 복합 지문 하위 문항에서 지문 본문 반복을 제외하고 발문+선지만 추출 */
  function extractQuestionChoicesOnly(text, questionTitle) {
    if (!text) return questionTitle || "";
    const cIdx = text.indexOf("①");
    if (cIdx !== -1) {
      const choices = text.substring(cIdx).trim();
      return `${questionTitle || ""}\n\n${choices}`.trim();
    }
    return questionTitle || text;
  }

  /** 지문 객체에서 학년, 년도, 월, 시험 유형 추출 */
  function parsePassageHierarchy(p) {
    let grade = p.grade || "";
    let year = p.year ? `${p.year}년` : "";
    let month = p.month ? `${String(p.month).padStart(2, "0")}월` : "";
    let examType = p.exam_type || "";

    const rawId = p.display_id || p.id || "";
    const match = rawId.match(/^\[?([^-]+)-(\d{4}년)-(\d{1,2}월)-(.+?)\]?$/);
    if (match) {
      if (!grade) grade = match[1];
      if (!year) year = match[2];
      if (!month) month = match[3];
    }
    if (!grade) grade = "기타";
    if (!year) year = "기타";
    if (!month) month = "기타";

    return { grade, year, month, examType };
  }

  /** 전체 지문 목록을 학년 -> 년도 -> 월 계층 트리로 구성 */
  function buildExamTree(items) {
    const tree = {};
    if (!items) return tree;

    items.forEach((p) => {
      const { grade, year, month, examType } = parsePassageHierarchy(p);
      if (!tree[grade]) tree[grade] = {};
      if (!tree[grade][year]) tree[grade][year] = {};
      if (!tree[grade][year][month]) {
        tree[grade][year][month] = {
          examType: examType,
          items: []
        };
      }
      tree[grade][year][month].items.push(p);
    });

    return tree;
  }

  /** 지문 결과 화면 렌더링 (트리 계층 기반) */
  function renderPassageView(items, targetPassageId = null) {
    if (!items || items.length === 0) {
      emptyResultsBox.style.display = "flex";
      passageViewContainer.style.display = "none";
      clear2x2Panels();
      return;
    }

    emptyResultsBox.style.display = "none";
    passageViewContainer.style.display = "flex";

    const tree = buildExamTree(items);
    const grades = Object.keys(tree);

    // 단일 시험인지 확인: 총 고유 (grade, year, month) 조합 개수 계산
    let totalExamsCount = 0;
    let singleExamCombo = null;
    grades.forEach((g) => {
      Object.keys(tree[g]).forEach((y) => {
        Object.keys(tree[g][y]).forEach((m) => {
          totalExamsCount++;
          singleExamCombo = { grade: g, year: y, month: m };
        });
      });
    });

    // 1) 특정 targetPassageId로 직접 이동하는 경우 (예: 문장 검색에서 넘어온 경우)
    if (targetPassageId) {
      const targetP = items.find((p) => p.id === targetPassageId || (p.all_ids && p.all_ids.includes(targetPassageId)));
      if (targetP) {
        const h = parsePassageHierarchy(targetP);
        treeNavState.grade = h.grade;
        treeNavState.year = h.year;
        treeNavState.month = h.month;
      }
    } else if (totalExamsCount === 1 && singleExamCombo) {
      // 2) 검색 결과가 단 1개의 시험인 경우: 자동으로 즉시 최하위 문항 탭으로 직행!
      treeNavState.grade = singleExamCombo.grade;
      treeNavState.year = singleExamCombo.year;
      treeNavState.month = singleExamCombo.month;
    } else {
      // 3) 복수 시험인 경우: 현재 선택된 상태가 유효한지 검사
      if (!treeNavState.grade || !tree[treeNavState.grade]) {
        if (grades.length === 1) {
          treeNavState.grade = grades[0];
        } else {
          treeNavState.grade = null;
          treeNavState.year = null;
          treeNavState.month = null;
        }
      }

      if (treeNavState.grade && tree[treeNavState.grade]) {
        const years = Object.keys(tree[treeNavState.grade]);
        if (!treeNavState.year || !tree[treeNavState.grade][treeNavState.year]) {
          if (years.length === 1) {
            treeNavState.year = years[0];
          } else {
            treeNavState.year = null;
            treeNavState.month = null;
          }
        }
      }

      if (treeNavState.grade && treeNavState.year && tree[treeNavState.grade]?.[treeNavState.year]) {
        const months = Object.keys(tree[treeNavState.grade][treeNavState.year]);
        if (!treeNavState.month || !tree[treeNavState.grade][treeNavState.year][treeNavState.month]) {
          if (months.length === 1) {
            treeNavState.month = months[0];
          } else {
            treeNavState.month = null;
          }
        }
      }
    }

    // 단계별 UI 렌더링 실행
    updateTreeUI(tree, items, totalExamsCount, targetPassageId);
  }

  /** 트리 단계에 따라 상위 선택기 / 최하위 문항 1행 10개 탭 전환 */
  function updateTreeUI(tree, allItems, totalExamsCount, targetPassageId = null) {
    const grades = Object.keys(tree);

    // 상단 브레드크럼 갱신
    renderBreadcrumb(tree, allItems, totalExamsCount);

    // Case 1: 학년 미선택 상태 -> 학년 선택 버튼들 표시
    if (!treeNavState.grade || !tree[treeNavState.grade]) {
      treeStepSelector.style.display = "flex";
      passageTabBar.style.display = "none";

      let html = `<span class="tree-step-title">📁 학년 선택:</span><div class="tree-step-buttons">`;
      grades.forEach((g) => {
        let count = 0;
        Object.keys(tree[g]).forEach((y) => {
          Object.keys(tree[g][y]).forEach((m) => {
            count += tree[g][y][m].items.length;
          });
        });
        html += `<button type="button" class="btn-tree-chip" data-grade="${escapeHtml(g)}">${escapeHtml(g)} <span class="chip-count">${count}</span></button>`;
      });
      html += `</div>`;
      treeStepSelector.innerHTML = html;

      treeStepSelector.querySelectorAll(".btn-tree-chip").forEach((btn) => {
        btn.addEventListener("click", () => {
          treeNavState.grade = btn.dataset.grade;
          treeNavState.year = null;
          treeNavState.month = null;
          const years = Object.keys(tree[treeNavState.grade] || {});
          if (years.length === 1) {
            treeNavState.year = years[0];
            const months = Object.keys(tree[treeNavState.grade][treeNavState.year] || {});
            if (months.length === 1) {
              treeNavState.month = months[0];
            }
          }
          updateTreeUI(tree, allItems, totalExamsCount);
        });
      });
      return;
    }

    // Case 2: 학년 선택됨, 년도 미선택 상태 -> 년도 선택 버튼들 표시
    const years = Object.keys(tree[treeNavState.grade] || {});
    if (!treeNavState.year || !tree[treeNavState.grade][treeNavState.year]) {
      treeStepSelector.style.display = "flex";
      passageTabBar.style.display = "none";

      let html = `<span class="tree-step-title">📅 [${escapeHtml(treeNavState.grade)}] 년도 선택:</span><div class="tree-step-buttons">`;
      years.forEach((y) => {
        let count = 0;
        Object.keys(tree[treeNavState.grade][y]).forEach((m) => {
          count += tree[treeNavState.grade][y][m].items.length;
        });
        html += `<button type="button" class="btn-tree-chip" data-year="${escapeHtml(y)}">${escapeHtml(y)} <span class="chip-count">${count}</span></button>`;
      });
      html += `</div>`;
      treeStepSelector.innerHTML = html;

      treeStepSelector.querySelectorAll(".btn-tree-chip").forEach((btn) => {
        btn.addEventListener("click", () => {
          treeNavState.year = btn.dataset.year;
          treeNavState.month = null;
          const months = Object.keys(tree[treeNavState.grade][treeNavState.year] || {});
          if (months.length === 1) {
            treeNavState.month = months[0];
          }
          updateTreeUI(tree, allItems, totalExamsCount);
        });
      });
      return;
    }

    // Case 3: 학년과 년도 선택됨, 월 미선택 상태 -> 월 선택 버튼들 표시
    const months = Object.keys(tree[treeNavState.grade][treeNavState.year] || {});
    if (!treeNavState.month || !tree[treeNavState.grade][treeNavState.year][treeNavState.month]) {
      treeStepSelector.style.display = "flex";
      passageTabBar.style.display = "none";

      let html = `<span class="tree-step-title">📆 [${escapeHtml(treeNavState.grade)} ${escapeHtml(treeNavState.year)}] 월/시험 선택:</span><div class="tree-step-buttons">`;
      months.forEach((m) => {
        const examObj = tree[treeNavState.grade][treeNavState.year][m];
        const count = examObj.items.length;
        const examType = examObj.examType ? ` (${examObj.examType})` : "";
        html += `<button type="button" class="btn-tree-chip" data-month="${escapeHtml(m)}">${escapeHtml(m)}${escapeHtml(examType)} <span class="chip-count">${count}</span></button>`;
      });
      html += `</div>`;
      treeStepSelector.innerHTML = html;

      treeStepSelector.querySelectorAll(".btn-tree-chip").forEach((btn) => {
        btn.addEventListener("click", () => {
          treeNavState.month = btn.dataset.month;
          updateTreeUI(tree, allItems, totalExamsCount);
        });
      });
      return;
    }

    // Case 4: 학년, 년도, 월 모두 선택 완료! -> 상위 선택 버튼들은 숨기고, 최하위 문항 탭만 1행 10개로 표시!
    treeStepSelector.style.display = "none";
    passageTabBar.style.display = "grid";

    const examData = tree[treeNavState.grade][treeNavState.year][treeNavState.month];
    currentExamQuestions = (examData && examData.items) ? examData.items : [];

    // 문항 탭 렌더링
    renderPassageTabs(currentExamQuestions);

    // 대상 문항 선택
    let activeIdx = 0;
    if (targetPassageId) {
      const fIdx = currentExamQuestions.findIndex((p) => p.id === targetPassageId || (p.all_ids && p.all_ids.includes(targetPassageId)));
      if (fIdx >= 0) activeIdx = fIdx;
    }
    selectPassageTab(activeIdx, currentExamQuestions);
  }

  /** 인라인 브레드크럼 바 렌더링 */
  function renderBreadcrumb(tree, allItems, totalExamsCount) {
    if (!breadcrumbTrail) return;

    let trailHtml = "";
    const isExamSelected = !!(treeNavState.grade && treeNavState.year && treeNavState.month);

    if (isExamSelected) {
      const examData = tree[treeNavState.grade]?.[treeNavState.year]?.[treeNavState.month];
      const count = examData ? examData.items.length : 0;
      const examType = examData?.examType ? ` · ${examData.examType}` : "";

      trailHtml = `
        <span class="breadcrumb-item" data-step="grade" title="학년 변경">${escapeHtml(treeNavState.grade)}</span>
        <span class="breadcrumb-separator">&gt;</span>
        <span class="breadcrumb-item" data-step="year" title="년도 변경">${escapeHtml(treeNavState.year)}</span>
        <span class="breadcrumb-separator">&gt;</span>
        <span class="breadcrumb-item active" data-step="month" title="월/시험 변경">${escapeHtml(treeNavState.month)}${escapeHtml(examType)}</span>
        <span class="breadcrumb-count-badge">(${count}문항)</span>
      `;
    } else if (treeNavState.grade && treeNavState.year) {
      trailHtml = `
        <span class="breadcrumb-item" data-step="grade" title="학년 변경">${escapeHtml(treeNavState.grade)}</span>
        <span class="breadcrumb-separator">&gt;</span>
        <span class="breadcrumb-item active" data-step="year">${escapeHtml(treeNavState.year)}</span>
        <span class="breadcrumb-separator">&gt;</span>
        <span class="breadcrumb-hint">월/시험을 선택하세요</span>
      `;
    } else if (treeNavState.grade) {
      trailHtml = `
        <span class="breadcrumb-item active" data-step="grade">${escapeHtml(treeNavState.grade)}</span>
        <span class="breadcrumb-separator">&gt;</span>
        <span class="breadcrumb-hint">년도를 선택하세요</span>
      `;
    } else {
      trailHtml = `
        <span class="breadcrumb-hint">총 ${allItems.length}개 문항 중 탐색할 학년을 선택하세요</span>
      `;
    }

    breadcrumbTrail.innerHTML = trailHtml;

    // 브레드크럼 항목 클릭 시 해당 상위 단계로 즉시 이동
    breadcrumbTrail.querySelectorAll(".breadcrumb-item").forEach((item) => {
      item.addEventListener("click", () => {
        const step = item.dataset.step;
        if (step === "grade") {
          treeNavState.grade = null;
          treeNavState.year = null;
          treeNavState.month = null;
        } else if (step === "year") {
          treeNavState.year = null;
          treeNavState.month = null;
        } else if (step === "month") {
          treeNavState.month = null;
        }
        updateTreeUI(tree, allItems, totalExamsCount);
      });
    });

    // "↺ 설정 초기화" 버튼: 시험 선택 상태(학년/년도/월)라면 언제든 무설정 상태(처음 학년 선택)로 복귀 가능
    if (btnTreeResetExam) {
      const hasTreeSelection = !!(treeNavState.grade || treeNavState.year || treeNavState.month);
      if (totalExamsCount > 1 && hasTreeSelection) {
        btnTreeResetExam.style.display = "inline-flex";
        btnTreeResetExam.onclick = () => {
          treeNavState.grade = null;
          treeNavState.year = null;
          treeNavState.month = null;
          updateTreeUI(tree, allItems, totalExamsCount);
          showToast("시험 선택이 초기화되었습니다.", "info");
        };
      } else {
        btnTreeResetExam.style.display = "none";
      }
    }

    // 브레드크럼 홈 아이콘(📍) 클릭 시 처음 학년 선택으로 복귀
    if (treeBreadcrumbHome) {
      treeBreadcrumbHome.style.cursor = "pointer";
      treeBreadcrumbHome.onclick = () => {
        if (treeNavState.grade || treeNavState.year || treeNavState.month) {
          treeNavState.grade = null;
          treeNavState.year = null;
          treeNavState.month = null;
          updateTreeUI(tree, allItems, totalExamsCount);
        }
      };
    }

    // "🔄 다른 시험 선택" 버튼: 복수 시험일 때만 노출
    if (btnTreeChangeExam) {
      if (totalExamsCount > 1 && isExamSelected) {
        btnTreeChangeExam.style.display = "inline-flex";
        btnTreeChangeExam.onclick = () => {
          treeNavState.month = null;
          const years = Object.keys(tree[treeNavState.grade] || {});
          if (years.length <= 1) {
            treeNavState.grade = null;
            treeNavState.year = null;
          }
          updateTreeUI(tree, allItems, totalExamsCount);
        };
      } else {
        btnTreeChangeExam.style.display = "none";
      }
    }
  }

  /** 최하위 문항별 탭 생성 (1행 10개 문항 초컴팩트 28px 버튼) */
  function renderPassageTabs(items) {
    passageTabBar.innerHTML = "";
    if (passageTabCount) passageTabCount.textContent = items.length;

    items.forEach((p, idx) => {
      const tabBtn = document.createElement("button");
      tabBtn.type = "button";
      tabBtn.className = `passage-q-tab ${idx === 0 ? "active" : ""}`;
      tabBtn.dataset.index = idx;
      tabBtn.dataset.id = p.id;

      let qLabel = p.q_num_label || (p.q_num ? `${p.q_num}번` : "");
      if (!qLabel) {
        const rawId = p.display_id || p.id || "";
        const m = rawId.match(/-([^-]+)$/);
        qLabel = m ? m[1] : rawId;
      }

      tabBtn.innerHTML = `<span class="tab-line-q">${escapeHtml(qLabel)}</span>`;
      tabBtn.title = `${escapeHtml(p.display_id || p.id)} (${p.question_type || "유형 미지정"})`;

      tabBtn.addEventListener("click", () => {
        selectPassageTab(idx, items);
      });

      passageTabBar.appendChild(tabBtn);
    });
  }

  /** 특정 문항 탭 선택 및 2x2 그리드 동기화 */
  function selectPassageTab(idx, items) {
    if (!items || items.length === 0) return;
    if (idx < 0) idx = 0;
    if (idx >= items.length) idx = items.length - 1;
    currentPassageIndex = idx;

    const tabs = passageTabBar.querySelectorAll(".passage-q-tab");
    tabs.forEach((t, i) => {
      if (i === idx) {
        t.classList.add("active");
        t.scrollIntoView({ behavior: "smooth", inline: "center", block: "nearest" });
      } else {
        t.classList.remove("active");
      }
    });

    loadPassageDetail(items[idx]);
  }

  // 상단 탭 스크롤 버튼
  if (btnTabScrollLeft) {
    btnTabScrollLeft.addEventListener("click", () => {
      passageTabBar.scrollBy({ left: -220, behavior: "smooth" });
    });
  }
  if (btnTabScrollRight) {
    btnTabScrollRight.addEventListener("click", () => {
      passageTabBar.scrollBy({ left: 220, behavior: "smooth" });
    });
  }

  // 키보드 방향키(←, →)로 문항 탭 전환 지원 (입력창에 포커스가 없을 때)
  window.addEventListener("keydown", (e) => {
    if (passageViewContainer.style.display === "none") return;
    const activeTagName = document.activeElement ? document.activeElement.tagName.toLowerCase() : "";
    if (activeTagName === "input" || activeTagName === "textarea" || activeTagName === "select") return;

    const targetList = (currentExamQuestions && currentExamQuestions.length > 0) ? currentExamQuestions : passagesData;
    if (!targetList || targetList.length === 0) return;

    if (e.key === "ArrowLeft") {
      if (currentPassageIndex > 0) {
        selectPassageTab(currentPassageIndex - 1, targetList);
      }
    } else if (e.key === "ArrowRight") {
      if (currentPassageIndex < targetList.length - 1) {
        selectPassageTab(currentPassageIndex + 1, targetList);
      }
    }
  });

  /** 2x2 패널에 특정 지문 상세 정보 로드 */
  function loadPassageDetail(p) {
    currentPassageId = p.id;

    // [좌측 상단]: PDF 문항 캡처 이미지 (단일 또는 그룹 이미지들)
    const images = (p.pdf_crop_images && p.pdf_crop_images.length > 0)
      ? p.pdf_crop_images
      : (p.pdf_crop_image ? [p.pdf_crop_image] : []);

    if (images.length > 0) {
      if (images.length === 1) {
        panelPdfImageContainer.innerHTML = `
          <img src="${images[0]}" class="pdf-crop-img" alt="${escapeHtml(p.display_id || p.id)} 문항 캡처" title="클릭 시 새 창에서 원본 크기 확대 보기">
        `;
        const imgEl = panelPdfImageContainer.querySelector("img");
        if (imgEl) {
          imgEl.addEventListener("click", () => window.open(images[0], "_blank"));
        }
      } else {
        panelPdfImageContainer.innerHTML = `
          <div class="pdf-multi-container">
            ${images.map((imgUrl, i) => `
              <div class="pdf-multi-item">
                <img src="${imgUrl}" class="pdf-crop-img" alt="${escapeHtml(p.display_id || p.id)} [${i+1}] 문항 캡처" title="클릭 시 새 창에서 원본 크기 확대 보기">
              </div>
            `).join('')}
          </div>
        `;
        panelPdfImageContainer.querySelectorAll("img").forEach((imgEl, i) => {
          imgEl.addEventListener("click", () => window.open(images[i], "_blank"));
        });
      }
    } else {
      panelPdfImageContainer.innerHTML = `
        <div class="pdf-placeholder">
          🖼️ PDF 문항 캡처 이미지가 생성되지 않았거나 없습니다.<br>
          <small style="color: var(--text-light); margin-top: 6px; display: inline-block;">
            시험지 업로드 시 PDF 파일을 함께 등록하시면 원본 문항 인쇄 영역이 고화질로 자동 크롭됩니다.
          </small>
        </div>
      `;
    }

    // [좌측 하단]: TXT 지문 본문 (41번/43번에만 지문 전체 포함, 42번/44번/45번은 발문+선지만 표시)
    let rawPassageText = "";
    if (p.isGroup && p.subItems && p.subItems.length > 1) {
      const parts = p.subItems.map((si, sIdx) => {
        if (sIdx === 0) {
          return si.passage_text || si.question_title || "";
        } else {
          return extractQuestionChoicesOnly(si.passage_text, si.question_title);
        }
      });
      rawPassageText = parts.filter(Boolean).join("\n\n----------------------------------------\n\n");
    } else {
      rawPassageText = p.passage_text || "지문 본문 텍스트가 비어 있습니다.";
    }

    panelPassageText.dataset.rawText = rawPassageText;

    // 현재 검색창에 입력된 검색 키워드로 파스텔톤 빨간색 형광펜 하이라이트 적용 (PDF 이미지는 원본 유지)
    const currentQuery = (resultsSearchInput && resultsSearchInput.value.trim()) || 
                         (mainSearchInput && mainSearchInput.value.trim()) || "";
    panelPassageText.innerHTML = highlightTextKeyword(rawPassageText, currentQuery, "passage-highlight");

    // [우측 상단]: HWP 정답 및 해설
    panelExplanation.textContent = p.explanation_text || "해설 정보가 등록되지 않았습니다.";

    // [우측 하단]: 지문 메타 정보, 문제 유형, 태그 관리
    metaPassageId.textContent = p.display_id || p.id;
    metaQNum.textContent = p.q_num_label || (p.q_num ? `${p.q_num}번` : "-");
    if (metaQuestionType) metaQuestionType.textContent = p.question_type || "-";
    metaAnswer.textContent = p.answer_text ? `${p.answer_text}` : "-";
    if (metaQuestionTitle) metaQuestionTitle.textContent = p.question_title || "-";
    validationBadge.textContent = p.remarks || `일치율 ${(p.validation_ratio * 100).toFixed(1)}%`;

    // 20대 문제 유형 선택기 반영
    if (selectQuestionType) {
      selectQuestionType.value = p.question_type || "글의목적";
      selectQuestionType.onchange = async () => {
        const newType = selectQuestionType.value;
        try {
          const res = await fetch(`/api/passages/${encodeURIComponent(currentPassageId)}/question-type`, {
            method: "PATCH",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ question_type: newType }),
          });
          if (res.ok) {
            p.question_type = newType;
            showToast(`문제 유형이 '${newType}'(으)로 즉시 저장되었습니다.`, "success");
            
            // 상단 탭의 유형 배지도 즉시 갱신
            const activeTab = passageTabBar.querySelector(`.passage-q-tab.active .tab-type-tag`);
            if (activeTab) {
              activeTab.textContent = newType;
            }
          }
        } catch (err) {
          console.error(err);
          showToast("문제 유형 변경 실패", "error");
        }
      };
    }

    renderPassageTags(p.tags || []);
  }

  function clear2x2Panels() {
    panelPdfImageContainer.innerHTML = `<div class="pdf-placeholder">지문을 선택하세요.</div>`;
    panelPassageText.textContent = "-";
    panelPassageText.dataset.rawText = "";
    panelExplanation.textContent = "-";
    metaPassageId.textContent = "-";
    metaQNum.textContent = "-";
    if (metaQuestionType) metaQuestionType.textContent = "-";
    metaAnswer.textContent = "-";
    if (metaQuestionTitle) metaQuestionTitle.textContent = "-";
    passageTagsList.innerHTML = "";
    passageTabBar.innerHTML = "";
    if (treeStepSelector) treeStepSelector.innerHTML = "";
    if (breadcrumbTrail) breadcrumbTrail.innerHTML = "";
    if (btnTreeChangeExam) btnTreeChangeExam.style.display = "none";
    if (passageTabCount) passageTabCount.textContent = "0";
  }

  /** 지문 태그 목록 렌더링 */
  function renderPassageTags(tags) {
    passageTagsList.innerHTML = "";
    if (!tags || tags.length === 0) {
      passageTagsList.innerHTML = `<span style="font-size: 0.8rem; color: var(--text-light);">등록된 태그가 없습니다.</span>`;
      return;
    }

    tags.forEach((tag) => {
      const badge = document.createElement("span");
      badge.className = "tag-badge";
      badge.innerHTML = `
        #${escapeHtml(tag)}
        <button class="tag-remove-btn" title="태그 삭제" data-tag="${escapeHtml(tag)}">&times;</button>
      `;

      badge.querySelector(".tag-remove-btn").addEventListener("click", async (e) => {
        e.stopPropagation();
        await deletePassageTag(currentPassageId, tag);
      });

      passageTagsList.appendChild(badge);
    });
  }

  /** 지문 태그 추가 API */
  async function addPassageTagAction() {
    const tagName = inputPassageTag.value.trim();
    if (!tagName || !currentPassageId) return;

    try {
      const res = await fetch(`/api/passages/${encodeURIComponent(currentPassageId)}/tags`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ tag_name: tagName }),
      });
      if (res.ok) {
        const data = await res.json();
        renderPassageTags(data.tags);
        inputPassageTag.value = "";
        showToast(`태그 '#${tagName}'이 추가되었습니다.`, "success");
        loadStats();
      }
    } catch (e) {
      console.error(e);
      showToast("태그 추가 실패", "error");
    }
  }

  btnAddPassageTag.addEventListener("click", addPassageTagAction);
  inputPassageTag.addEventListener("keydown", (e) => {
    if (e.key === "Enter") addPassageTagAction();
  });

  /** 지문 태그 삭제 API */
  async function deletePassageTag(passageId, tagName) {
    try {
      const res = await fetch(
        `/api/passages/${encodeURIComponent(passageId)}/tags/${encodeURIComponent(tagName)}`,
        { method: "DELETE" }
      );
      if (res.ok) {
        const data = await res.json();
        renderPassageTags(data.tags);
        showToast(`태그 '#${tagName}'이 삭제되었습니다.`, "info");
        loadStats();
      }
    } catch (e) {
      console.error(e);
      showToast("태그 삭제 실패", "error");
    }
  }

  // 지문 전체 복사 버튼
  btnCopyPassage.addEventListener("click", () => {
    const text = panelPassageText.dataset.rawText || panelPassageText.textContent;
    if (text && text !== "지문 본문이 여기에 표시됩니다." && text !== "-") {
      copyToClipboard(text, "지문 본문이 클립보드에 복사되었습니다! (Ctrl+V)");
    }
  });

  // 해설 복사 버튼
  btnCopyExplanation.addEventListener("click", () => {
    const text = panelExplanation.textContent;
    if (text && text !== "-") {
      copyToClipboard(text, "정답 및 해설이 클립보드에 복사되었습니다!");
    }
  });

  // =========================================================================
  // 7. [전체 문장 보기] <-> [지문 결과창으로 돌아가기] 연동
  // =========================================================================

  /** 특정 지문의 전체 문장 결과창을 1행 테이블로 표시 */
  async function showSentencesForPassage(passageId) {
    if (!passageId) {
      if (currentPassageId) {
        passageId = currentPassageId;
      } else if (currentExamQuestions && currentExamQuestions.length > 0) {
        passageId = currentExamQuestions[currentPassageIndex]?.id;
      } else if (passagesData && passagesData.length > 0) {
        passageId = passagesData[0].id;
      }
    }
    if (!passageId) {
      setMode("sentence", true);
      return;
    }

    currentPassageId = passageId;
    currentMode = "sentence";
    if (resultsTabModeSentence) resultsTabModeSentence.classList.add("active");
    if (resultsTabModePassage) resultsTabModePassage.classList.remove("active");
    if (tabModeSentence) tabModeSentence.classList.add("active");
    if (tabModePassage) tabModePassage.classList.remove("active");
    updateGrammarFiltersVisibility();

    loadingIndicator.style.display = "flex";
    passageViewContainer.style.display = "none";
    emptyResultsBox.style.display = "none";

    try {
      const res = await fetch(`/api/search/sentences?passage_id=${encodeURIComponent(passageId)}&limit=300`);
      const data = await res.json();
      sentencesData = data.items || [];
      rawSentencesData = sentencesData;
      resultsTotalCount.textContent = sentencesData.length;
      renderSentenceView(sentencesData);

      // 상단 문장 건수 표시 커스텀 타이틀 반영
      if (sentenceMatchCount) {
        sentenceMatchCount.innerHTML = `<strong>${escapeHtml(passageId)}</strong> 문항 전체 문장 (${sentencesData.length}개)`;
      }

      // 동일 위치(헤더 슬롯) 버튼을 '지문 결과창으로 돌아가기'로 전환
      setHeaderSlotState("sentence");
      setTimeout(updateResultsNavHeight, 30);
    } catch (err) {
      console.error(err);
      showToast("문장 데이터를 불러오지 못했습니다.", "error");
    } finally {
      loadingIndicator.style.display = "none";
    }
  }

  /** 전체 문장 결과창에서 이전 지문 상세 화면으로 복귀 */
  function backToPassageView() {
    currentMode = "passage";
    if (resultsTabModePassage) resultsTabModePassage.classList.add("active");
    if (resultsTabModeSentence) resultsTabModeSentence.classList.remove("active");
    if (tabModePassage) tabModePassage.classList.add("active");
    if (tabModeSentence) tabModeSentence.classList.remove("active");
    updateGrammarFiltersVisibility();

    sentenceViewContainer.style.display = "none";
    passageViewContainer.style.display = "flex";
    emptyResultsBox.style.display = "none";

    // 동일 위치(헤더 슬롯) 버튼을 '전체 문장' 버튼으로 복원
    setHeaderSlotState("passage");

    // 직전에 선택되었던 지문 상태 유지 (18번 리셋 방지)
    if (passagesData && passagesData.length > 0) {
      resultsTotalCount.textContent = passagesData.length;
      let targetIndex = currentPassageIndex;
      if (currentPassageId) {
        const found = passagesData.findIndex(p => p.id === currentPassageId || (p.all_ids && p.all_ids.includes(currentPassageId)));
        if (found >= 0) targetIndex = found;
      }
      if (targetIndex < 0 || targetIndex >= passagesData.length) targetIndex = 0;
      selectPassageTab(targetIndex, passagesData);
    } else if (currentPassageId) {
      navigateToPassageView(currentPassageId);
    } else {
      executeSearch("results");
    }
  }

  /** 출처 문자열에서 순수 지문 ID 추출 (예: [고3-2026년-07월-33번-8번째 문장] -> [고3-2026년-07월-33번]) */
  function extractPassageId(str) {
    if (!str) return "";
    const m = str.match(/(\[[^\]]+?-\d+번)(?:-\d+번째 문장\]|\])/);
    if (m) return m[1] + "]";
    return str.replace(/-\d+번째 문장\]$/, "]");
  }

  /** 문장 출처 클릭 시 해당 문항의 지문 결과 페이지로 즉시 이동 및 탭 포커스 */
  async function navigateToPassageView(targetPassageId) {
    const pId = extractPassageId(targetPassageId);
    if (!pId) return;

    currentPassageId = pId;
    currentMode = "passage";
    if (resultsTabModePassage) resultsTabModePassage.classList.add("active");
    if (resultsTabModeSentence) resultsTabModeSentence.classList.remove("active");
    if (tabModePassage) tabModePassage.classList.add("active");
    if (tabModeSentence) tabModeSentence.classList.remove("active");

    sentenceViewContainer.style.display = "none";
    passageViewContainer.style.display = "flex";
    emptyResultsBox.style.display = "none";

    // 1. 현재 passagesData 목록에 해당 지문이 이미 존재하는지 확인
    let idx = -1;
    if (passagesData && passagesData.length > 0) {
      idx = passagesData.findIndex(p => p.id === pId || (p.all_ids && p.all_ids.includes(pId)));
    }

    if (idx >= 0) {
      resultsTotalCount.textContent = passagesData.length;
      setHeaderSlotState("passage");
      renderPassageView(passagesData, pId);
      showToast(`${pId} 지문 상세로 이동했습니다.`, "info");
      return;
    }

    // 2. passagesData에 없을 경우(단독 문장 검색 등에서 유입된 경우)
    loadingIndicator.style.display = "flex";
    try {
      // 해당 시험지 전체 지문 로드 시도
      const examId = pId.substring(0, pId.lastIndexOf("-")) + "]";
      const res = await fetch(`/api/search/passages?exam_id=${encodeURIComponent(examId)}&limit=100`);
      if (res.ok) {
        const data = await res.json();
        if (data.items && data.items.length > 0) {
          passagesData = groupPassageItems(data.items);
          resultsTotalCount.textContent = passagesData.length;
          renderPassageView(passagesData, pId);
          setHeaderSlotState("passage");
          showToast(`${pId} 지문 상세로 이동했습니다.`, "info");
          return;
        }
      }

      // 단일 지문 로드 폴백
      const singleRes = await fetch(`/api/passages/${encodeURIComponent(pId)}`);
      if (singleRes.ok) {
        const singleData = await singleRes.json();
        passagesData = groupPassageItems([singleData]);
        resultsTotalCount.textContent = 1;
        renderPassageView(passagesData, pId);
        setHeaderSlotState("passage");
        showToast(`${pId} 지문 상세로 이동했습니다.`, "info");
      }
    } catch (err) {
      console.error("지문 이동 오류:", err);
      showToast("지문 화면으로 이동하지 못했습니다.", "error");
    } finally {
      loadingIndicator.style.display = "none";
    }
  }

  // 헤더 슬롯 버튼 클릭 시 상태에 따라 문장 보기 / 지문 복귀 수행
  if (btnHeaderFlow) {
    btnHeaderFlow.addEventListener("click", () => {
      if (btnHeaderFlow.classList.contains("mode-back")) {
        backToPassageView();
      } else {
        showSentencesForPassage(currentPassageId);
      }
    });
  }

  // 문장 결과창 헤더의 '지문 결과창으로 돌아가기' 버튼
  if (btnSentenceBackToPassage) {
    btnSentenceBackToPassage.addEventListener("click", () => {
      backToPassageView();
    });
  }

  // =========================================================================
  // 8. [문장 검색 결과] 1행 테이블 렌더링
  // =========================================================================

  // 문장 텍스트 형광펜 하이라이트는 상단 정의된 highlightSentenceKeyword(highlightTextKeyword 기반)를 활용

  function getGrammarBadgeClass(pos) {
    if (!pos) return "";
    const p = String(pos).trim();
    if (p === "동사") return "badge-verb";
    if (p === "접속사") return "badge-conj";
    if (p === "명사" || p === "주어") return "badge-noun";
    if (p === "대명사") return "badge-pronoun";
    if (p.includes("형용사") || p.includes("부사")) return "badge-adj-adv";
    if (p === "전치사") return "badge-prep";
    if (p === "특수구문") return "badge-special";
    if (p === "문장") return "badge-sentence";
    return "";
  }

  function renderGrammarBadges(annos, sentenceId, grammarAnalyzed) {
    if (annos && annos.length > 0) {
      return annos
        .map((a, idx) => {
          const badgeClass = getGrammarBadgeClass(a.pos);
          const identifier = a.id || a.category_id || 0;
          const removeBtn = sentenceId
            ? `<button type="button" class="grammar-remove-btn" data-sent-id="${escapeHtml(sentenceId)}" data-id="${escapeHtml(String(identifier))}" title="어법 범주 삭제">&times;</button>`
            : "";
          return `<span class="grammar-tag-badge ${badgeClass}" data-sent-id="${escapeHtml(sentenceId || '')}" data-idx="${idx}" title="클릭하여 상세 해설 보기">🏷️ ${escapeHtml(a.leaf_name || a.pos || "")}${removeBtn}</span>`;
        })
        .join(" ");
    }

    if (grammarAnalyzed === 1 || grammarAnalyzed === true) {
      return '<span class="grammar-badge-none" title="AI 어법 분석이 완료되었으나 검출된 특이 어법 포인트가 없습니다.">✓ 해당사항 없음</span>';
    }

    return '<span class="empty-grammar-text" title="아직 AI 어법 분석이 수행되지 않은 문장입니다.">미분석</span>';
  }

  /** 어법 범주 상세 해설 플로팅 팝오버 닫기 */
  function closeGrammarPopover() {
    if (grammarExplanationPopover) {
      grammarExplanationPopover.style.display = "none";
    }
  }

  /** 어법 범주 배지 클릭 시 상세 해설 플로팅 팝오버 표시 */
  function showGrammarPopover(anno, targetElement) {
    if (!grammarExplanationPopover || !anno || !targetElement) return;

    if (popoverBadge) {
      popoverBadge.className = `grammar-popover-badge ${getGrammarBadgeClass(anno.pos)}`;
      popoverBadge.textContent = `🏷️ ${anno.leaf_name || anno.pos || '어법'}`;
    }

    if (popoverPath) {
      popoverPath.textContent = anno.full_path || (anno.leaf_name || '');
      popoverPath.title = anno.full_path || '';
    }

    if (popoverPhraseSection && popoverPhraseText) {
      if (anno.target_expression && anno.target_expression.trim()) {
        popoverPhraseSection.style.display = "flex";
        popoverPhraseText.textContent = anno.target_expression.trim();
      } else {
        popoverPhraseSection.style.display = "none";
      }
    }

    if (popoverExplanationText) {
      popoverExplanationText.textContent = anno.explanation || "등록된 상세 해설 내용이 없습니다.";
    }

    grammarExplanationPopover.style.display = "block";

    // 클릭된 배지 위치 기준으로 팝오버 좌표 계산
    const rect = targetElement.getBoundingClientRect();
    const popoverWidth = grammarExplanationPopover.offsetWidth || 440;
    const popoverHeight = grammarExplanationPopover.offsetHeight || 180;

    // 가로 위치 (화면 밖 삐져나옴 방지)
    let left = rect.left;
    if (left + popoverWidth > window.innerWidth - 16) {
      left = window.innerWidth - popoverWidth - 16;
    }
    if (left < 16) left = 16;

    // 세로 위치 (기본 배지 아래쪽, 공간 부족 시 배지 위쪽으로 반전)
    let top = rect.bottom + 8;
    if (top + popoverHeight > window.innerHeight - 16) {
      const topAbove = rect.top - popoverHeight - 8;
      if (topAbove >= 16) {
        top = topAbove;
      }
    }

    grammarExplanationPopover.style.top = `${top}px`;
    grammarExplanationPopover.style.left = `${left}px`;
  }

  if (btnCloseGrammarPopover) {
    btnCloseGrammarPopover.addEventListener("click", closeGrammarPopover);
  }

  // 바깥 영역 클릭 시 팝오버 닫기
  document.addEventListener("click", (e) => {
    if (grammarExplanationPopover && grammarExplanationPopover.style.display !== "none") {
      if (!grammarExplanationPopover.contains(e.target) && !e.target.closest(".grammar-tag-badge")) {
        closeGrammarPopover();
      }
    }
  });

  // ESC 키 입력 시 팝오버 닫기
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && grammarExplanationPopover && grammarExplanationPopover.style.display !== "none") {
      closeGrammarPopover();
    }
  });

  // 화면 스크롤 시 팝오버 닫기 (캡처 모드)
  window.addEventListener("scroll", () => {
    if (grammarExplanationPopover && grammarExplanationPopover.style.display !== "none") {
      closeGrammarPopover();
    }
  }, true);

  function renderSentenceView(items) {
    if (!items || items.length === 0) {
      emptyResultsBox.style.display = "flex";
      sentenceViewContainer.style.display = "none";
      return;
    }

    emptyResultsBox.style.display = "none";
    sentenceViewContainer.style.display = "block";
    sentenceMatchCount.textContent = items.length;
    sentenceTableBody.innerHTML = "";
    setTimeout(updateResultsNavHeight, 30);

    // 현재 검색창에 입력된 검색 키워드 확인
    const currentQuery = (resultsSearchInput && resultsSearchInput.value.trim()) || 
                         (mainSearchInput && mainSearchInput.value.trim()) || "";

    items.forEach((s) => {
      const tr = document.createElement("tr");

      // 문장 태그 뱃지 HTML 렌더링 헬퍼
      const renderSentenceTagsHtml = (tags) => {
        if (!tags || tags.length === 0) {
          return '<span style="color: var(--text-light); font-size: 0.75rem;">태그 없음</span>';
        }
        return tags
          .map(
            (t) =>
              `<span class="tag-badge" style="font-size: 0.72rem; padding: 0.15rem 0.45rem;">#${escapeHtml(t)}
               <button type="button" class="tag-remove-btn" style="font-size: 0.75rem;" data-sent-id="${escapeHtml(s.id)}" data-tag="${escapeHtml(t)}">&times;</button></span>`
          )
          .join(" ");
      };

      // 출처 ID에서 문항 ID 추출 (예: [고3-2026년-07월-33번-8번째 문장] -> [고3-2026년-07월-33번])
      const targetPassageId = s.passage_id || extractPassageId(s.id);

      // 검색 표현 형광펜 하이라이트 적용
      const highlightedSentence = highlightSentenceKeyword(s.sentence_text, currentQuery);
      const isStarred = s.is_starred === 1 || s.is_starred === true;

      tr.innerHTML = `
        <td class="col-star" style="text-align: center;">
          <button type="button" class="btn-star ${isStarred ? "starred" : ""}" data-id="${escapeHtml(s.id)}" title="${isStarred ? "중요 문장 해제" : "중요 문장(⭐)으로 등록"}">
            ${isStarred ? "★" : "☆"}
          </button>
        </td>
        <td class="col-num">${s.row_num}</td>
        <td class="col-source">
          <button type="button" class="btn-source-link" data-passage-id="${escapeHtml(targetPassageId)}" title="클릭하여 ${escapeHtml(targetPassageId)} 지문 결과 화면으로 이동">
            🔗 ${escapeHtml(s.id)}
          </button>
        </td>
        <td class="col-sentence">
          <div>${highlightedSentence}</div>
        </td>
        <td class="col-grammar">
          <div class="sentence-grammar-tags" id="grammar-tags-${cssSafeId(s.id)}">
            ${renderGrammarBadges(s.grammar_annotations, s.id, s.grammar_analyzed)}
          </div>
          <button 
            type="button" 
            class="btn-open-grammar-modal btn-grammar-manage-${cssSafeId(s.id)}" 
            data-sent-id="${escapeHtml(s.id)}"
            title="어법 범주 전체 개요 창에서 중복 선택"
          >
            ⚙️ 어법 범주 선택 (${(s.grammar_annotations || []).length})
          </button>
        </td>
        <td class="col-tags">
          <div class="tags-container-${cssSafeId(s.id)}" style="display: flex; flex-wrap: wrap; gap: 0.25rem; margin-bottom: 0.25rem;">
            ${renderSentenceTagsHtml(s.tags)}
          </div>
          <div class="inline-tag-form">
            <input type="text" class="inline-tag-input input-tag-${cssSafeId(s.id)}" placeholder="+태그 입력">
            <button type="button" class="btn btn-secondary btn-sm btn-add-tag-${cssSafeId(s.id)}" style="padding: 0.15rem 0.4rem; font-size: 0.72rem;">추가</button>
          </div>
        </td>
        <td class="col-action">
          <div class="action-btn-group">
            <button class="copy-btn btn-copy-sentence" data-text="${escapeHtml(s.sentence_text)}" title="문장 복사">
              📋 복사
            </button>
            <button type="button" class="btn-analyze-inline" data-id="${escapeHtml(s.id)}" title="AI로 어법 포인트 분석">
              🤖 분석
            </button>
          </div>
        </td>
      `;

      // 어법 셀 갱신 및 삭제/클릭 이벤트 바인딩
      const updateGrammarCell = () => {
        const container = tr.querySelector(`#grammar-tags-${cssSafeId(s.id)}`);
        if (container) {
          container.innerHTML = renderGrammarBadges(s.grammar_annotations, s.id, s.grammar_analyzed);
          bindGrammarRemoveBtns();
          bindGrammarBadgeClicks();
        }
        const countBtn = tr.querySelector(`.btn-grammar-manage-${cssSafeId(s.id)}`);
        if (countBtn) {
          countBtn.textContent = `⚙️ 어법 범주 선택 (${(s.grammar_annotations || []).length})`;
        }
      };

      const bindGrammarRemoveBtns = () => {
        const container = tr.querySelector(`#grammar-tags-${cssSafeId(s.id)}`);
        if (!container) return;
        container.querySelectorAll(".grammar-remove-btn").forEach((btn) => {
          btn.addEventListener("click", async (e) => {
            e.stopPropagation();
            const identifier = btn.dataset.id;
            if (!identifier) return;
            try {
              const res = await fetch(`/api/sentences/${encodeURIComponent(s.id)}/grammar-annotations/${encodeURIComponent(identifier)}`, {
                method: "DELETE"
              });
              const data = await res.json();
              if (res.ok && data.success) {
                s.grammar_annotations = data.annotations || [];
                updateGrammarCell();
                showToast("어법 범주가 삭제되었습니다.", "info");
              } else {
                showToast(data.detail || "어법 범주 삭제 실패", "error");
              }
            } catch (err) {
              console.error("Delete grammar error:", err);
              showToast("어법 범주 삭제 중 오류가 발생했습니다.", "error");
            }
          });
        });
      };

      const bindGrammarBadgeClicks = () => {
        const container = tr.querySelector(`#grammar-tags-${cssSafeId(s.id)}`);
        if (!container) return;
        container.querySelectorAll(".grammar-tag-badge").forEach((badge) => {
          badge.addEventListener("click", (e) => {
            // 삭제 버튼(×)을 클릭한 경우는 팝오버를 열지 않음
            if (e.target.closest(".grammar-remove-btn")) return;
            e.stopPropagation();
            const idx = parseInt(badge.dataset.idx, 10);
            const anno = (s.grammar_annotations && s.grammar_annotations[idx]) ? s.grammar_annotations[idx] : null;
            if (anno) {
              showGrammarPopover(anno, badge);
            }
          });
        });
      };

      bindGrammarRemoveBtns();
      bindGrammarBadgeClicks();

      // 어법 범주 전체 개요 모달 열기 이벤트
      const openGrammarBtn = tr.querySelector(`.btn-grammar-manage-${cssSafeId(s.id)}`);
      if (openGrammarBtn) {
        openGrammarBtn.addEventListener("click", (e) => {
          e.stopPropagation();
          openGrammarModalForSentence(s, () => {
            updateGrammarCell();
          });
        });
      }

      // 별표 토글 이벤트
      const starBtn = tr.querySelector(".btn-star");
      if (starBtn) {
        starBtn.addEventListener("click", async (e) => {
          e.stopPropagation();
          try {
            const res = await fetch(`/api/sentences/${encodeURIComponent(s.id)}/star`, { method: "POST" });
            if (res.ok) {
              const data = await res.json();
              s.is_starred = data.is_starred;
              if (data.is_starred === 1) {
                starBtn.classList.add("starred");
                starBtn.textContent = "★";
                starBtn.title = "중요 문장 해제";
                showToast("중요 문장(⭐)으로 등록되었습니다.", "success");
              } else {
                starBtn.classList.remove("starred");
                starBtn.textContent = "☆";
                starBtn.title = "중요 문장(⭐)으로 등록";
                showToast("중요 문장에서 해제되었습니다.", "info");
              }
            }
          } catch (err) {
            console.error("Star toggle error:", err);
          }
        });
      }

      // 인라인 AI 어법 분석 이벤트
      const analyzeBtn = tr.querySelector(".btn-analyze-inline");
      if (analyzeBtn) {
        analyzeBtn.addEventListener("click", async (e) => {
          e.stopPropagation();
          analyzeBtn.classList.add("loading");
          analyzeBtn.textContent = "분석중...";
          try {
            const res = await fetch(`/api/sentences/${encodeURIComponent(s.id)}/analyze-grammar`, { method: "POST" });
            const data = await res.json();
            if (res.ok && data.success) {
              s.grammar_annotations = data.annotations || [];
              s.grammar_analyzed = 1;
              updateGrammarCell();
              if (s.grammar_annotations.length > 0) {
                showToast(`${s.grammar_annotations.length}개의 어법 포인트가 분석되었습니다.`, "success");
              } else {
                showToast("분석 완료: 해당 문장에 특이 어법 포인트가 없습니다 (해당사항 없음).", "info");
              }
            } else {
              showToast(data.detail || data.message || "어법 분석 실패 (상단 AI 설정을 확인하세요)", "error");
            }
          } catch (err) {
            console.error("Analyze error:", err);
            showToast("AI 어법 분석 중 오류가 발생했습니다.", "error");
          } finally {
            analyzeBtn.classList.remove("loading");
            analyzeBtn.textContent = "🤖 분석";
          }
        });
      }

      // 출처 클릭 시 해당 문항의 지문 결과 페이지로 즉시 이동
      const sourceBtn = tr.querySelector(".btn-source-link");
      if (sourceBtn) {
        sourceBtn.addEventListener("click", (e) => {
          e.stopPropagation();
          navigateToPassageView(targetPassageId);
        });
      }

      // 인라인 복사 이벤트
      const copyBtn = tr.querySelector(".btn-copy-sentence");
      copyBtn.addEventListener("click", () => {
        copyToClipboard(s.sentence_text, "문장이 복사되었습니다! (Ctrl+V)");
        copyBtn.textContent = "✔ 복사됨";
        copyBtn.classList.add("copied");
        setTimeout(() => {
          copyBtn.innerHTML = "📋 복사";
          copyBtn.classList.remove("copied");
        }, 1500);
      });

      // 인라인 태그 셀 갱신 및 삭제 이벤트 재바인딩 (인플레이스 DOM 갱신으로 화면 풀림 및 스크롤 점프 방지)
      const updateTagsCell = () => {
        const container = tr.querySelector(`.tags-container-${cssSafeId(s.id)}`);
        if (container) {
          container.innerHTML = renderSentenceTagsHtml(s.tags);
          bindTagRemoveBtns();
        }
      };

      const bindTagRemoveBtns = () => {
        const container = tr.querySelector(`.tags-container-${cssSafeId(s.id)}`);
        if (!container) return;
        container.querySelectorAll(".tag-remove-btn").forEach((btn) => {
          btn.addEventListener("click", async (e) => {
            e.stopPropagation();
            const tagToDelete = btn.dataset.tag;
            try {
              const res = await fetch(
                `/api/sentences/${encodeURIComponent(s.id)}/tags/${encodeURIComponent(tagToDelete)}`,
                { method: "DELETE" }
              );
              if (res.ok) {
                const data = await res.json();
                s.tags = data.tags || [];
                updateTagsCell();
                showToast(`문장 태그 '#${tagToDelete}' 삭제 완료`, "info");
                loadStats();
              } else {
                showToast("문장 태그 삭제 실패", "error");
              }
            } catch (e) {
              console.error(e);
              showToast("태그 삭제 중 오류가 발생했습니다.", "error");
            }
          });
        });
      };

      // 인라인 태그 추가 이벤트
      const tagInput = tr.querySelector(`.input-tag-${cssSafeId(s.id)}`);
      const addTagBtn = tr.querySelector(`.btn-add-tag-${cssSafeId(s.id)}`);

      const handleAddSentenceTag = async () => {
        const val = tagInput.value.trim();
        if (!val) return;
        try {
          const res = await fetch(`/api/sentences/${encodeURIComponent(s.id)}/tags`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ tag_name: val }),
          });
          if (res.ok) {
            const data = await res.json();
            s.tags = data.tags || [];
            updateTagsCell();
            tagInput.value = "";
            showToast(`문장 태그 '#${val}' 추가 완료`, "success");
            loadStats();
          } else {
            showToast("문장 태그 추가 실패", "error");
          }
        } catch (e) {
          console.error(e);
          showToast("태그 추가 중 오류가 발생했습니다.", "error");
        }
      };

      if (addTagBtn) addTagBtn.addEventListener("click", handleAddSentenceTag);
      if (tagInput) {
        tagInput.addEventListener("keydown", (e) => {
          if (e.key === "Enter") handleAddSentenceTag();
        });
      }

      bindTagRemoveBtns();

      sentenceTableBody.appendChild(tr);
    });
  }

  // =========================================================================
  // 9. 클립보드 복사 & 토스트 알림 헬퍼
  // =========================================================================

  function copyToClipboard(text, successMsg) {
    if (navigator.clipboard && window.isSecureContext) {
      navigator.clipboard.writeText(text).then(() => {
        showToast(successMsg, "success");
      }).catch(() => {
        fallbackCopy(text, successMsg);
      });
    } else {
      fallbackCopy(text, successMsg);
    }
  }

  function fallbackCopy(text, successMsg) {
    const textArea = document.createElement("textarea");
    textArea.value = text;
    textArea.style.position = "fixed";
    textArea.style.opacity = "0";
    document.body.appendChild(textArea);
    textArea.focus();
    textArea.select();
    try {
      document.execCommand("copy");
      showToast(successMsg, "success");
    } catch (err) {
      showToast("복사에 실패했습니다.", "error");
    }
    document.body.removeChild(textArea);
  }

  function showToast(message, type = "info") {
    const toastContainer = document.getElementById("toastContainer");
    if (!toastContainer) return;
    const toast = document.createElement("div");
    toast.className = `toast ${type}`;
    toast.innerHTML = `<span>${message}</span>`;
    toastContainer.appendChild(toast);

    setTimeout(() => {
      toast.style.opacity = "0";
      toast.style.transform = "translateY(10px)";
      toast.style.transition = "all 0.25s";
      setTimeout(() => toast.remove(), 250);
    }, 3000);
  }

  // =========================================================================
  // 10. 시험지 업로드 모달 제어 (월 자동 가이드 및 파이프라인 제출)
  // =========================================================================

  btnOpenUploadModal.addEventListener("click", () => {
    uploadModal.classList.add("show");
  });

  const closeUploadModal = () => {
    uploadModal.classList.remove("show");
  };

  btnCloseUploadModal.addEventListener("click", closeUploadModal);
  btnCancelUpload.addEventListener("click", closeUploadModal);

  // 시험 구분 변경 시 월 기본값 지능적 안내
  if (modalExamType && modalMonth) {
    modalExamType.addEventListener("change", () => {
      if (modalExamType.value === "교육청") {
        if (!["3", "4", "5", "7", "10"].includes(modalMonth.value)) {
          modalMonth.value = "7";
        }
      } else {
        if (!["6", "9", "11"].includes(modalMonth.value)) {
          modalMonth.value = "6";
        }
      }
    });
  }

  uploadForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const formData = new FormData(uploadForm);
    const submitBtn = document.getElementById("btnSubmitUpload");
    submitBtn.disabled = true;
    submitBtn.textContent = "⏳ 파싱 및 보안 승인 검증 중...";

    try {
      const res = await fetch("/api/upload", {
        method: "POST",
        body: formData,
      });
      const data = await res.json();
      if (res.ok) {
        showToast(data.message || "시험지가 성공적으로 등록되었습니다!", "success");
        closeUploadModal();
        uploadForm.reset();
        loadStats();
        // 업로드된 시험지로 자동 검색 실행
        mainSearchInput.value = data.exam_id || "";
        executeSearch("home");
      } else {
        alert(`업로드 실패: ${data.detail || "알 수 없는 오류"}`);
      }
    } catch (err) {
      console.error(err);
      alert("서버 통신 중 오류가 발생했습니다.");
    } finally {
      submitBtn.disabled = false;
      submitBtn.textContent = "🚀 상호 검증 및 DB 저장";
    }
  });

  // =========================================================================
  // 11. 샘플 데이터 즉시 주입
  // =========================================================================

  btnSeedSample.addEventListener("click", async () => {
    btnSeedSample.disabled = true;
    btnSeedSample.textContent = "주입 중...";
    try {
      const res = await fetch("/api/seed-sample-data", { method: "POST" });
      const data = await res.json();
      if (res.ok) {
        showToast(data.message, "success");
        loadStats();
        // 검색 자동 실행
        mainSearchInput.value = "";
        executeSearch("home");
      }
    } catch (e) {
      console.error(e);
      showToast("샘플 주입 실패", "error");
    } finally {
      btnSeedSample.disabled = false;
      btnSeedSample.textContent = "⚡ 샘플 데이터 주입";
    }
  });

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

  const grammarCategoryModal = document.getElementById("grammarCategoryModal");
  const btnCloseGrammarModal = document.getElementById("btnCloseGrammarModal");
  const btnCancelGrammarModal = document.getElementById("btnCancelGrammarModal");
  const btnApplyGrammarSelection = document.getElementById("btnApplyGrammarSelection");
  const btnResetGrammarSelection = document.getElementById("btnResetGrammarSelection");
  const inputGrammarSearch = document.getElementById("inputGrammarSearch");
  const btnClearGrammarSearch = document.getElementById("btnClearGrammarSearch");
  const grammarSelectedCount = document.getElementById("grammarSelectedCount");
  const grammarPreviewBadges = document.getElementById("grammarPreviewBadges");
  const grammarGridContainer = document.getElementById("grammarGridContainer");
  const grammarModalSentenceInfo = document.getElementById("grammarModalSentenceInfo");
  const grammarBreadcrumbBar = document.getElementById("grammarBreadcrumbBar");
  const grammarBreadcrumbTrail = document.getElementById("grammarBreadcrumbTrail");
  const grammarBreadcrumbHome = document.getElementById("grammarBreadcrumbHome");
  const btnGrammarResetStep = document.getElementById("btnGrammarResetStep");
  const btnGrammarChangeStep = document.getElementById("btnGrammarChangeStep");
  const btnGrammarToggleView = document.getElementById("btnGrammarToggleView");

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

  if (btnCloseGrammarModal) btnCloseGrammarModal.addEventListener("click", closeGrammarCategoryModal);
  if (btnCancelGrammarModal) btnCancelGrammarModal.addEventListener("click", closeGrammarCategoryModal);

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
  loadGrammarCategories();

  function openGrammarModalForSentence(sentence, onUpdateCallback) {
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
  function updateGrammarBreadcrumbFilterUI() {
    const pos = (filterGrammarPos && filterGrammarPos.value) || (resultsFilterGrammarPos && resultsFilterGrammarPos.value) || "";
    const cat = (filterGrammarCategory && filterGrammarCategory.value) || (resultsFilterGrammarCategory && resultsFilterGrammarCategory.value) || "";

    if (filterGrammarPos) filterGrammarPos.classList.toggle("active", !!pos);
    if (resultsFilterGrammarPos) resultsFilterGrammarPos.classList.toggle("active", !!pos);

    if (filterGrammarCategory) filterGrammarCategory.classList.toggle("active", !!cat);
    if (resultsFilterGrammarCategory) resultsFilterGrammarCategory.classList.toggle("active", !!cat);

    const hasActiveFilter = !!(pos || cat || isStarredFilterActive);
    if (btnResetHomeGrammarFilter) {
      btnResetHomeGrammarFilter.style.display = hasActiveFilter ? "inline-flex" : "none";
    }
    if (btnResetResultsGrammarFilter) {
      btnResetResultsGrammarFilter.style.display = hasActiveFilter ? "inline-flex" : "none";
    }
  }

  /** 모든 어법 필터 및 별표 필터를 무설정 상태로 초기화 */
  function resetAllGrammarFilters(triggerSearch = false) {
    if (filterGrammarPos) filterGrammarPos.value = "";
    if (resultsFilterGrammarPos) resultsFilterGrammarPos.value = "";
    if (filterGrammarCategory) filterGrammarCategory.value = "";
    if (resultsFilterGrammarCategory) resultsFilterGrammarCategory.value = "";

    updateSubGrammarCategories("", filterGrammarCategory);
    updateSubGrammarCategories("", resultsFilterGrammarCategory);

    setStarredFilter(false);
    updateGrammarBreadcrumbFilterUI();

    if (triggerSearch) {
      if (isSearchWithinActive && rawSentencesData && rawSentencesData.length > 0) {
        executeSearchWithinResults();
      } else {
        refreshCurrentSentenceView();
      }
    }
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
      if (isSearchWithinActive && rawSentencesData && rawSentencesData.length > 0) {
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
      if (isSearchWithinActive && rawSentencesData && rawSentencesData.length > 0) {
        executeSearchWithinResults();
      } else {
        refreshCurrentSentenceView();
      }
    });
  }

  // 별표 필터 토글 제어
  function setStarredFilter(active) {
    isStarredFilterActive = active;
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

  if (btnToggleStarred) {
    btnToggleStarred.addEventListener("click", () => {
      setStarredFilter(!isStarredFilterActive);
    });
  }
  if (btnResultsToggleStarred) {
    btnResultsToggleStarred.addEventListener("click", () => {
      setStarredFilter(!isStarredFilterActive);
      if (isSearchWithinActive && rawSentencesData && rawSentencesData.length > 0) {
        executeSearchWithinResults();
      } else {
        refreshCurrentSentenceView();
      }
    });
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
    if (currentPassageId && btnHeaderFlow && btnHeaderFlow.classList.contains("mode-back")) {
      showSentencesForPassage(currentPassageId);
      return;
    }
    // 2. 결과 내 검색(isSearchWithinActive) 중인 경우
    if (isSearchWithinActive && rawSentencesData && rawSentencesData.length > 0) {
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
      const starredSentences = sentencesData.filter((s) => s.is_starred === 1 || s.is_starred === true);
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
      if (!sentencesData || sentencesData.length === 0) {
        showToast("분석할 문장이 없습니다. 먼저 문장을 검색해 주세요.", "warning");
        return;
      }

      // 이미 어법 분석이 완료된 문장 제외 (어법 배지가 있거나, 분석 결과 해당사항 없음인 문장 모두 제외)
      const targetSentences = sentencesData.filter(
        (s) => !s.grammar_analyzed && (!s.grammar_annotations || s.grammar_annotations.length === 0)
      );

      if (targetSentences.length === 0) {
        showToast(`현재 결과창의 모든 문장(${sentencesData.length}개)은 이미 어법 분석이 완료되어 있습니다! 👍`, "info");
        return;
      }

      const totalTargetCount = targetSentences.length;
      const alreadyCount = sentencesData.length - totalTargetCount;
      const confirmMsg = alreadyCount > 0
        ? `전체 ${sentencesData.length}개 문장 중 이미 분석된 ${alreadyCount}개를 제외하고,\n미분석 문장 ${totalTargetCount}개를 일괄 AI 어법 분석하시겠습니까?`
        : `현재 결과창의 미분석 ${totalTargetCount}개 문장을 일괄 AI 어법 분석하시겠습니까?\n(실시간 진행 모달 창에서 문장별 어법 포인트를 실시간으로 확인하실 수 있습니다.)`;

      if (!confirm(confirmMsg)) {
        return;
      }

      await runBatchAnalysisModal(targetSentences, false);
    });
  }

  // =========================================================================
  // 13. AI 설정 모달 (Multi-LLM: Gemini / ChatGPT / Claude)
  // =========================================================================

  const providerDefaults = {
    gemini: {
      model: "gemini-1.5-flash",
      help: "💡 기본 권장: gemini-1.5-flash (하루 수천 문장 무료 분석 지원)",
      link: "https://aistudio.google.com/app/apikey",
      linkText: "Google AI Studio 무료 키 발급 ↗",
    },
    openrouter: {
      model: "deepseek/deepseek-chat",
      help: "💡 기본 권장: deepseek/deepseek-chat (OpenRouter 이용량 1위! DeepSeek, Claude, GPT, Llama 등 수백 개 모델 지원)",
      link: "https://openrouter.ai/keys",
      linkText: "OpenRouter API Keys 발급 ↗",
    },
    openai: {
      model: "gpt-4o-mini",
      help: "💡 기본 권장: gpt-4o-mini (모의고사 1회당 약 5~10원의 초저비용)",
      link: "https://platform.openai.com/api-keys",
      linkText: "OpenAI API Keys 발급 ↗",
    },
    claude: {
      model: "claude-3-5-haiku-20241022",
      help: "💡 기본 권장: claude-3-5-haiku (어법 및 한국어 해설 생성 최적)",
      link: "https://console.anthropic.com/settings/keys",
      linkText: "Anthropic Console 키 발급 ↗",
    },
  };

  /** OpenRouter 선택 모델 상세 정보 카드 렌더링 */
  function renderOpenRouterModelCard(model) {
    if (!openrouterModelInfoCard) return;
    if (!model) {
      openrouterModelInfoCard.style.display = "none";
      return;
    }
    openrouterModelInfoCard.style.display = "flex";
    if (infoModelBadge) infoModelBadge.textContent = model.badge || "추천";
    if (infoModelName) infoModelName.textContent = model.name || model.id;
    if (infoModelTag) infoModelTag.textContent = model.tag || "";
    if (infoModelPromptPrice) infoModelPromptPrice.textContent = model.prompt_price || "-";
    if (infoModelCompletionPrice) infoModelCompletionPrice.textContent = model.completion_price || "-";
    if (infoModelContext) infoModelContext.textContent = model.context_length || "-";
    if (infoModelDesc) infoModelDesc.textContent = model.description || "";
  }

  /** OpenRouter Top 5 모델 드랍다운 옵션 생성 및 현재 입력값과 동기화 */
  function renderOpenRouterModelSelectOptions() {
    if (!openrouterModelSelect) return;
    openrouterModelSelect.innerHTML = "";

    const curModel = (aiModelInput ? aiModelInput.value.trim() : "") || "deepseek/deepseek-chat";
    let matched = false;

    openrouterTopModelsData.forEach((m) => {
      const opt = document.createElement("option");
      opt.value = m.id;
      opt.textContent = `${m.badge} ${m.name} [${m.tag} | ${m.prompt_price}]`;
      if (m.id === curModel) {
        opt.selected = true;
        matched = true;
        renderOpenRouterModelCard(m);
      }
      openrouterModelSelect.appendChild(opt);
    });

    // 직접 입력 옵션
    const customOpt = document.createElement("option");
    customOpt.value = "custom";
    customOpt.textContent = "✏️ 직접 입력 (커스텀 모델명 지정)";
    if (!matched && curModel) {
      customOpt.selected = true;
      renderOpenRouterModelCard(null);
    }
    openrouterModelSelect.appendChild(customOpt);

    // 기본 미선택 시 첫번째 1위 모델 기본 선택
    if (!matched && !curModel && openrouterTopModelsData.length > 0) {
      openrouterModelSelect.selectedIndex = 0;
      const firstM = openrouterTopModelsData[0];
      if (aiModelInput) aiModelInput.value = firstM.id;
      renderOpenRouterModelCard(firstM);
    }
  }

  /** OpenRouter Top 5 모델 목록 서버 조회 */
  async function loadOpenRouterTopModels(force = false) {
    if (!openrouterModelSelect) return;
    if (btnRefreshOpenRouterModels) {
      btnRefreshOpenRouterModels.disabled = true;
      btnRefreshOpenRouterModels.textContent = "⏳ 갱신 중...";
    }
    try {
      const res = await fetch(`/api/openrouter/top-models${force ? "?force_refresh=true" : ""}`);
      const data = await res.json();
      if (res.ok && data.models && data.models.length > 0) {
        openrouterTopModelsData = data.models;
        renderOpenRouterModelSelectOptions();
        if (force) {
          showToast("OpenRouter 최신 Top 5 모델 정보가 갱신되었습니다.", "success");
        }
      }
    } catch (err) {
      console.error("OpenRouter 모델 목록 로드 실패:", err);
      if (force) {
        showToast("OpenRouter 모델 정보를 불러오지 못했습니다.", "warning");
      }
    } finally {
      if (btnRefreshOpenRouterModels) {
        btnRefreshOpenRouterModels.disabled = false;
        btnRefreshOpenRouterModels.textContent = "🔄 실시간 정보 갱신";
      }
    }
  }

  // AI 설정 상태 헤더 버튼 반영 (API 연결 작동 시 시각적 강조 디자인)
  function updateAiHeaderButton(data) {
    if (!btnOpenAiSettingsModal) return;
    if (data && data.has_key) {
      btnOpenAiSettingsModal.classList.add("api-active");
      const provName =
        data.provider === "gemini"
          ? "Gemini"
          : data.provider === "openrouter"
          ? "OpenRouter"
          : data.provider === "openai"
          ? "GPT"
          : data.provider === "anthropic"
          ? "Claude"
          : data.provider || "AI";
      btnOpenAiSettingsModal.innerHTML = `<span class="ai-status-pulse-dot"></span>⚡ AI 연결됨 <span class="ai-active-badge">${escapeHtml(provName)}</span>`;
      btnOpenAiSettingsModal.title = `AI 어법 분석기 활성화됨 (${provName}: ${data.model || "기본 모델"}) - 클릭하여 설정 변경`;
    } else {
      btnOpenAiSettingsModal.classList.remove("api-active");
      btnOpenAiSettingsModal.innerHTML = `🔑 AI 설정`;
      btnOpenAiSettingsModal.title = "AI 어법 분석기 설정 (Gemini/OpenRouter/ChatGPT/Claude)";
    }
  }

  async function refreshAiStatusIndicator() {
    if (!btnOpenAiSettingsModal) return;
    try {
      const res = await fetch("/api/settings/ai");
      if (res.ok) {
        const data = await res.json();
        updateAiHeaderButton(data);
        return data;
      }
    } catch (e) {
      console.warn("AI 설정 상태 조회 실패:", e);
    }
  }

  async function openAiSettingsModal() {
    if (!aiSettingsModal) return;
    aiSettingsStatus.style.display = "none";
    try {
      const res = await fetch("/api/settings/ai");
      if (res.ok) {
        const data = await res.json();
        updateAiHeaderButton(data);
        const prov = data.provider || "gemini";
        if (aiProviderSelect) aiProviderSelect.value = prov;
        const info = providerDefaults[prov] || providerDefaults.gemini;
        if (aiModelInput) {
          aiModelInput.value = data.model || info.model;
        }
        if (currentKeyBadge) {
          currentKeyBadge.textContent = data.has_key
            ? `현재 키: ${data.masked_key} (${data.provider})`
            : "현재 키: 미설정";
          currentKeyBadge.style.color = data.has_key ? "var(--success)" : "#64748b";
        }
        updateAiProviderHelp(false);
      }
    } catch (e) {
      console.error(e);
    }
    aiSettingsModal.style.display = "flex";
  }

  function closeAiSettingsModal() {
    if (aiSettingsModal) aiSettingsModal.style.display = "none";
    if (aiApiKeyInput) aiApiKeyInput.value = "";
  }

  function updateAiProviderHelp(isUserChange = false) {
    const prov = aiProviderSelect ? aiProviderSelect.value : "gemini";
    const info = providerDefaults[prov] || providerDefaults.gemini;
    if (aiModelHelp) aiModelHelp.textContent = info.help;
    if (apiKeyGuideLink) {
      apiKeyGuideLink.href = info.link;
      apiKeyGuideLink.textContent = info.linkText;
    }

    // OpenRouter 선택 시 Top 5 드랍다운 영역 노출 및 로드
    if (openrouterModelGroup) {
      if (prov === "openrouter") {
        openrouterModelGroup.style.display = "block";
        if (openrouterTopModelsData.length === 0) {
          loadOpenRouterTopModels(false);
        } else {
          renderOpenRouterModelSelectOptions();
        }
      } else {
        openrouterModelGroup.style.display = "none";
      }
    }

    if (aiModelInput) {
      aiModelInput.placeholder = `예: ${info.model}`;
      // 사용자가 직접 엔진(Provider)을 변경했으면 해당 엔진의 기본 권장 모델명으로 자동 갱신!
      if (isUserChange) {
        aiModelInput.value = info.model;
        if (prov === "openrouter" && openrouterTopModelsData.length > 0) {
          renderOpenRouterModelSelectOptions();
        }
      }
    }
  }

  // OpenRouter 모델 드랍다운 변경 시 모델 입력창 및 카드 자동 갱신
  if (openrouterModelSelect) {
    openrouterModelSelect.addEventListener("change", () => {
      const selectedVal = openrouterModelSelect.value;
      if (selectedVal === "custom") {
        renderOpenRouterModelCard(null);
        if (aiModelInput) {
          aiModelInput.focus();
        }
      } else {
        const found = openrouterTopModelsData.find((m) => m.id === selectedVal);
        if (found) {
          if (aiModelInput) aiModelInput.value = found.id;
          renderOpenRouterModelCard(found);
        }
      }
    });
  }

  // OpenRouter 모델 정보 실시간 새로고침 버튼
  if (btnRefreshOpenRouterModels) {
    btnRefreshOpenRouterModels.addEventListener("click", () => {
      loadOpenRouterTopModels(true);
    });
  }

  // 모델명 텍스트 직접 입력 시 Top 5 드랍다운과 양방향 연동
  if (aiModelInput) {
    aiModelInput.addEventListener("input", () => {
      if (aiProviderSelect && aiProviderSelect.value === "openrouter" && openrouterModelSelect) {
        const val = aiModelInput.value.trim();
        const found = openrouterTopModelsData.find((m) => m.id === val);
        if (found) {
          openrouterModelSelect.value = found.id;
          renderOpenRouterModelCard(found);
        } else {
          openrouterModelSelect.value = "custom";
          renderOpenRouterModelCard(null);
        }
      }
    });
  }

  if (btnOpenAiSettingsModal) {
    btnOpenAiSettingsModal.addEventListener("click", openAiSettingsModal);
  }
  if (btnCloseAiSettingsModal) {
    btnCloseAiSettingsModal.addEventListener("click", closeAiSettingsModal);
  }
  if (btnCancelAiSettings) {
    btnCancelAiSettings.addEventListener("click", closeAiSettingsModal);
  }
  if (aiProviderSelect) {
    aiProviderSelect.addEventListener("change", () => {
      updateAiProviderHelp(true);
    });
  }

  if (btnToggleKeyVis && aiApiKeyInput) {
    btnToggleKeyVis.addEventListener("click", () => {
      const isPwd = aiApiKeyInput.type === "password";
      aiApiKeyInput.type = isPwd ? "text" : "password";
      btnToggleKeyVis.textContent = isPwd ? "🙈" : "👁️";
    });
  }

  if (btnSaveAiSettings) {
    btnSaveAiSettings.addEventListener("click", async () => {
      const provider = aiProviderSelect.value;
      const apiKey = aiApiKeyInput.value.trim();
      const model = aiModelInput.value.trim();

      btnSaveAiSettings.disabled = true;
      btnSaveAiSettings.textContent = "⏳ 연결 테스트 중...";
      aiSettingsStatus.style.display = "block";
      aiSettingsStatus.style.background = "#eff6ff";
      aiSettingsStatus.style.color = "#1d4ed8";
      aiSettingsStatus.textContent = "AI 연결 핑 테스트를 수행하고 있습니다...";

      try {
        const res = await fetch("/api/settings/ai", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            provider: provider,
            api_key: apiKey,
            model: model,
            test_now: true,
          }),
        });
        const data = await res.json();
        if (res.ok && data.success) {
          aiSettingsStatus.style.background = "#ecfdf5";
          aiSettingsStatus.style.color = "#047857";
          aiSettingsStatus.textContent = `✔ ${data.message}`;
          showToast("AI 설정이 저장되었습니다.", "success");
          refreshAiStatusIndicator();
          setTimeout(() => {
            closeAiSettingsModal();
          }, 1200);
        } else {
          aiSettingsStatus.style.background = "#fef2f2";
          aiSettingsStatus.style.color = "#b91c1c";
          aiSettingsStatus.textContent = `❌ ${data.detail || data.message || "연결 테스트 실패"}`;
        }
      } catch (err) {
        console.error(err);
        aiSettingsStatus.style.background = "#fef2f2";
        aiSettingsStatus.style.color = "#b91c1c";
        aiSettingsStatus.textContent = "서버 통신 오류가 발생했습니다.";
      } finally {
        btnSaveAiSettings.disabled = false;
        btnSaveAiSettings.textContent = "🧪 연결 테스트 및 저장";
      }
    });
  }

  // 유틸 함수
  function escapeHtml(text) {
    if (!text) return "";
    return String(text)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  function cssSafeId(id) {
    return id.replace(/[^a-zA-Z0-9_-]/g, "_");
  }

  // 초기 상태: 지문 검색 모드이므로 어법 필터 숨김 및 AI 연결 상태 확인
  updateGrammarFiltersVisibility();
  refreshAiStatusIndicator();
});

