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
  const btnSearch = document.getElementById("btnSearch");

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
  const btnResultsSearch = document.getElementById("btnResultsSearch");
  const btnToggleSearchWithin = document.getElementById("btnToggleSearchWithin") || document.getElementById("btnSearchWithinResults");
  let isSearchWithinActive = false;
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
  const breadcrumbTrail = document.getElementById("breadcrumbTrail");
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
  const btnToggleStarred = document.getElementById("btnToggleStarred");
  const resultsFilterGrammarPos = document.getElementById("resultsFilterGrammarPos");
  const resultsFilterGrammarCategory = document.getElementById("resultsFilterGrammarCategory");
  const btnResultsToggleStarred = document.getElementById("btnResultsToggleStarred");
  const btnBatchAnalyzeStarred = document.getElementById("btnBatchAnalyzeStarred");
  let isStarredFilterActive = false;
  let grammarCategoriesList = [];

  // AI 설정 모달 요소
  const btnOpenAiSettingsModal = document.getElementById("btnOpenAiSettingsModal");
  const aiSettingsModal = document.getElementById("aiSettingsModal");
  const btnCloseAiSettingsModal = document.getElementById("btnCloseAiSettingsModal");
  const btnCancelAiSettings = document.getElementById("btnCancelAiSettings");
  const aiProviderSelect = document.getElementById("aiProviderSelect");
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
      btnHeaderFlow.textContent = "📝 전체 문장";
      btnHeaderFlow.title = "현재 지문의 전체 문장 결과창 보기";
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
  }

  /** 결과 화면으로 전환 */
  function showResultsScreen() {
    homeSearchView.style.display = "none";
    resultsView.style.display = "flex";
    window.scrollTo({ top: 0, behavior: "smooth" });
    updateGrammarFiltersVisibility();
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

  /** 텍스트 내에서 검색 표현을 찾아 파스텔톤 빨간색 형광펜으로 감싸기 */
  function highlightTextKeyword(text, rawQuery, highlightClass = "sentence-highlight") {
    if (!text) return "";
    const cleanText = escapeHtml(text);
    if (!rawQuery) return cleanText;

    const { keyword } = parseSearchQuery(rawQuery);
    if (!keyword || !keyword.trim()) return cleanText;

    // HTML 이스케이프된 키워드로 정규식 특수문자 이스케이프
    const escapedKw = escapeHtml(keyword.trim()).replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    const regex = new RegExp(`(${escapedKw})`, "gi");

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

    // 결과 화면으로 전환 및 로딩 표시
    showResultsScreen();
    loadingIndicator.style.display = "flex";
    emptyResultsBox.style.display = "none";
    passageViewContainer.style.display = "none";
    sentenceViewContainer.style.display = "none";

    const params = new URLSearchParams();
    if (keyword) params.append("keyword", keyword);
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

    params.append("limit", "500");

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
        if (kw) {
          const inBody = (p.passage_text || "").toLowerCase().includes(kw);
          const inTitle = (p.question_title || "").toLowerCase().includes(kw);
          const inId = (p.display_id || p.id || "").toLowerCase().includes(kw);
          const inExp = (p.explanation_text || "").toLowerCase().includes(kw);
          const inType = (p.question_type || "").toLowerCase().includes(kw);
          const inTags = (p.tags || []).some(t => t.toLowerCase().includes(kw));
          
          let inSub = false;
          if (p.isGroup && p.subItems) {
            inSub = p.subItems.some(si => 
              (si.passage_text || "").toLowerCase().includes(kw) ||
              (si.question_title || "").toLowerCase().includes(kw)
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
        if (kw) {
          const inEng = (s.sentence_text || "").toLowerCase().includes(kw);
          const inKor = (s.korean_translation || "").toLowerCase().includes(kw);
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
  }

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
      resultsTotalCount.textContent = sentencesData.length;
      renderSentenceView(sentencesData);

      // 상단 문장 건수 표시 커스텀 타이틀 반영
      if (sentenceMatchCount) {
        sentenceMatchCount.innerHTML = `<strong>${escapeHtml(passageId)}</strong> 문항 전체 문장 (${sentencesData.length}개)`;
      }

      // 동일 위치(헤더 슬롯) 버튼을 '지문 결과창으로 돌아가기'로 전환
      setHeaderSlotState("sentence");
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

  function renderGrammarBadges(annos) {
    if (!annos || annos.length === 0) {
      return '<span class="empty-grammar-text">미분석</span>';
    }
    return annos
      .map((a) => {
        const badgeClass =
          a.pos === "특수구문" ? "badge-special" : a.pos === "동사" ? "badge-verb" : "";
        const titleText = `${a.full_path || ""}\n${
          a.target_expression ? `[해당 어구] ${a.target_expression}\n` : ""
        }${a.explanation ? `[해설] ${a.explanation}` : ""}`.trim();
        return `<span class="grammar-tag-badge ${badgeClass}" title="${escapeHtml(titleText)}">🏷️ ${escapeHtml(a.leaf_name || a.pos)}</span>`;
      })
      .join(" ");
  }

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

    // 현재 검색창에 입력된 검색 키워드 확인
    const currentQuery = (resultsSearchInput && resultsSearchInput.value.trim()) || 
                         (mainSearchInput && mainSearchInput.value.trim()) || "";

    items.forEach((s) => {
      const tr = document.createElement("tr");

      const tagsHtml = (s.tags || [])
        .map(
          (t) =>
            `<span class="tag-badge" style="font-size: 0.72rem; padding: 0.15rem 0.45rem;">#${escapeHtml(t)}
             <button class="tag-remove-btn" style="font-size: 0.75rem;" data-sent-id="${escapeHtml(s.id)}" data-tag="${escapeHtml(t)}">&times;</button></span>`
        )
        .join(" ");

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
            ${renderGrammarBadges(s.grammar_annotations)}
          </div>
        </td>
        <td class="col-tags">
          <div class="tags-container-${cssSafeId(s.id)}" style="display: flex; flex-wrap: wrap; gap: 0.25rem; margin-bottom: 0.25rem;">
            ${tagsHtml || '<span style="color: var(--text-light); font-size: 0.75rem;">태그 없음</span>'}
          </div>
          <div class="inline-tag-form">
            <input type="text" class="inline-tag-input input-tag-${cssSafeId(s.id)}" placeholder="+태그 입력">
            <button class="btn btn-secondary btn-sm btn-add-tag-${cssSafeId(s.id)}" style="padding: 0.15rem 0.4rem; font-size: 0.72rem;">추가</button>
          </div>
        </td>
        <td class="col-remarks">${escapeHtml(s.exam_type || "")} ${s.word_count ? `(${s.word_count}단어)` : ""}</td>
        <td class="col-action">
          <div class="action-btn-group">
            <button class="copy-btn btn-copy-sentence" data-text="${escapeHtml(s.sentence_text)}">
              📋 복사
            </button>
            <button type="button" class="btn-analyze-inline" data-id="${escapeHtml(s.id)}" title="AI로 어법 포인트 분석">
              🤖 분석
            </button>
          </div>
        </td>
      `;

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
              const container = tr.querySelector(`#grammar-tags-${cssSafeId(s.id)}`);
              if (container) {
                container.innerHTML = renderGrammarBadges(s.grammar_annotations);
              }
              showToast(`${s.grammar_annotations.length}개의 어법 포인트가 분석되었습니다.`, "success");
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
            tagInput.value = "";
            showToast(`문장 태그 '#${val}' 추가 완료`, "success");
            executeSearch("results");
            loadStats();
          }
        } catch (e) {
          console.error(e);
        }
      };

      addTagBtn.addEventListener("click", handleAddSentenceTag);
      tagInput.addEventListener("keydown", (e) => {
        if (e.key === "Enter") handleAddSentenceTag();
      });

      // 인라인 태그 삭제 이벤트 바인딩
      tr.querySelectorAll(".tag-remove-btn").forEach((btn) => {
        btn.addEventListener("click", async () => {
          const tagToDelete = btn.dataset.tag;
          try {
            const res = await fetch(
              `/api/sentences/${encodeURIComponent(s.id)}/tags/${encodeURIComponent(tagToDelete)}`,
              { method: "DELETE" }
            );
            if (res.ok) {
              showToast(`문장 태그 '#${tagToDelete}' 삭제 완료`, "info");
              executeSearch("results");
              loadStats();
            }
          } catch (e) {
            console.error(e);
          }
        });
      });

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

  if (filterGrammarPos) {
    filterGrammarPos.addEventListener("change", () => {
      const pos = filterGrammarPos.value;
      if (resultsFilterGrammarPos) resultsFilterGrammarPos.value = pos;
      updateSubGrammarCategories(pos, filterGrammarCategory);
      updateSubGrammarCategories(pos, resultsFilterGrammarCategory);
    });
  }

  if (resultsFilterGrammarPos) {
    resultsFilterGrammarPos.addEventListener("change", () => {
      const pos = resultsFilterGrammarPos.value;
      if (filterGrammarPos) filterGrammarPos.value = pos;
      updateSubGrammarCategories(pos, filterGrammarCategory);
      updateSubGrammarCategories(pos, resultsFilterGrammarCategory);
      if (isSearchWithinActive && rawSentencesData && rawSentencesData.length > 0) {
        executeSearchWithinResults();
      } else {
        executeSearch("results");
      }
    });
  }

  if (filterGrammarCategory) {
    filterGrammarCategory.addEventListener("change", () => {
      if (resultsFilterGrammarCategory) resultsFilterGrammarCategory.value = filterGrammarCategory.value;
    });
  }
  if (resultsFilterGrammarCategory) {
    resultsFilterGrammarCategory.addEventListener("change", () => {
      if (filterGrammarCategory) filterGrammarCategory.value = resultsFilterGrammarCategory.value;
      if (isSearchWithinActive && rawSentencesData && rawSentencesData.length > 0) {
        executeSearchWithinResults();
      } else {
        executeSearch("results");
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
        executeSearch("results");
      }
    });
  }

  // 중요 문장 일괄 AI 분석
  if (btnBatchAnalyzeStarred) {
    btnBatchAnalyzeStarred.addEventListener("click", async () => {
      const starredSentences = sentencesData.filter((s) => s.is_starred === 1 || s.is_starred === true);
      if (starredSentences.length === 0) {
        showToast("별표(⭐) 표시된 중요 문장이 없습니다. 먼저 문장에 별표를 추가해 주세요.", "warning");
        return;
      }
      if (!confirm(`현재 별표(⭐) 표시된 ${starredSentences.length}개 중요 문장을 일괄 AI 어법 분석하시겠습니까?`)) {
        return;
      }
      btnBatchAnalyzeStarred.disabled = true;
      btnBatchAnalyzeStarred.textContent = "⏳ 일괄 분석 중...";
      try {
        const res = await fetch("/api/sentences/batch-analyze-grammar", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            sentence_ids: starredSentences.map((s) => s.id),
            starred_only: true,
          }),
        });
        const data = await res.json();
        if (res.ok) {
          showToast(`성공적으로 ${data.total_processed}개 문장의 어법 분석을 완료했습니다!`, "success");
          executeSearch("results");
        } else {
          showToast(data.detail || data.message || "일괄 분석 실패", "error");
        }
      } catch (err) {
        console.error(err);
        showToast("일괄 분석 통신 오류가 발생했습니다.", "error");
      } finally {
        btnBatchAnalyzeStarred.disabled = false;
        btnBatchAnalyzeStarred.textContent = "⭐ 중요 문장 일괄 어법 분석";
      }
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

  async function openAiSettingsModal() {
    if (!aiSettingsModal) return;
    aiSettingsStatus.style.display = "none";
    try {
      const res = await fetch("/api/settings/ai");
      if (res.ok) {
        const data = await res.json();
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
    if (aiModelInput) {
      aiModelInput.placeholder = `예: ${info.model}`;
      // 사용자가 직접 엔진(Provider)을 변경했으면 해당 엔진의 기본 권장 모델명으로 자동 갱신!
      if (isUserChange) {
        aiModelInput.value = info.model;
      }
    }
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

  // 초기 상태: 지문 검색 모드이므로 어법 필터 숨김
  updateGrammarFiltersVisibility();
});

