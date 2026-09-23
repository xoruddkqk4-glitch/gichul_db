/**
 * 05-gichul_db: DOM 요소 참조 (index.html id 기준, 전 모듈 공용) (dom.js)
 * - main.js 에서 분리. 요소 id 는 templates/index.html 과 1:1 대응
 */

// =========================================================================
// DOM 요소 캐싱
// =========================================================================

// 글로벌 헤더 & 홈 로고
export const btnGoHome = document.getElementById("btnGoHome");
export const statPassages = document.getElementById("statPassages");
export const statSentences = document.getElementById("statSentences");
export const btnSeedSample = document.getElementById("btnSeedSample");
export const btnOpenUploadModal = document.getElementById("btnOpenUploadModal");

// 헤더 동적 액션 슬롯 (통계 배지 <-> 전체 문장 버튼 <-> 지문 복귀 버튼)
export const statsBadge = document.getElementById("statsBadge");
export const btnHeaderFlow = document.getElementById("btnHeaderFlow");

// 화면 1: 홈 검색 화면
export const homeSearchView = document.getElementById("homeSearchView");
export const tabModePassage = document.getElementById("tabModePassage");
export const tabModeSentence = document.getElementById("tabModeSentence");
export const mainSearchInput = document.getElementById("mainSearchInput");
export const btnClearMainSearch = document.getElementById("btnClearMainSearch");
export const btnSearch = document.getElementById("btnSearch");
export const btnHomeToggleWholeWord = document.getElementById("btnHomeToggleWholeWord");

// 홈 필터
export const filterGrade = document.getElementById("filterGrade");
export const filterYear = document.getElementById("filterYear");
export const filterMonth = document.getElementById("filterMonth");
export const filterExamType = document.getElementById("filterExamType");
export const filterQuestionType = document.getElementById("filterQuestionType");
export const filterCorrectRate = document.getElementById("filterCorrectRate");
export const filterTag = document.getElementById("filterTag");

// 화면 2: 결과창 화면
export const resultsView = document.getElementById("resultsView");
export const btnBackToSearch = document.getElementById("btnBackToSearch");
export const resultsSearchInput = document.getElementById("resultsSearchInput");
export const btnClearResultsSearch = document.getElementById("btnClearResultsSearch");
export const btnResultsSearch = document.getElementById("btnResultsSearch");
export const btnToggleSearchWithin = document.getElementById("btnToggleSearchWithin") || document.getElementById("btnSearchWithinResults");
export const btnToggleWholeWord = document.getElementById("btnToggleWholeWord");
export const resultsTabModePassage = document.getElementById("resultsTabModePassage");
export const resultsTabModeSentence = document.getElementById("resultsTabModeSentence");

// 결과창 필터
export const resultsFilterGrade = document.getElementById("resultsFilterGrade");
export const resultsFilterYear = document.getElementById("resultsFilterYear");
export const resultsFilterMonth = document.getElementById("resultsFilterMonth");
export const resultsFilterExamType = document.getElementById("resultsFilterExamType");
export const resultsFilterQuestionType = document.getElementById("resultsFilterQuestionType");
export const resultsFilterCorrectRate = document.getElementById("resultsFilterCorrectRate");
export const btnResetResultsFilters = document.getElementById("btnResetResultsFilters");
export const btnResetHomeFilters = document.getElementById("btnResetHomeFilters");
export const resultsTotalCount = document.getElementById("resultsTotalCount");

// 상태 컨테이너
export const loadingIndicator = document.getElementById("loadingIndicator");
export const emptyResultsBox = document.getElementById("emptyResultsBox");
export const btnEmptyBackToSearch = document.getElementById("btnEmptyBackToSearch");
export const btnEmptyResetFilters = document.getElementById("btnEmptyResetFilters");

// [지문 결과 화면] 요소
export const passageViewContainer = document.getElementById("passageViewContainer");
const passageTabBarContainer = document.getElementById("passageTabBarContainer");
export const passageTabBar = document.getElementById("passageTabBar");
export const passageTabCount = document.getElementById("passageTabCount");
const treeBreadcrumbBar = document.getElementById("treeBreadcrumbBar");
export const treeBreadcrumbHome = document.getElementById("treeBreadcrumbHome");
export const breadcrumbTrail = document.getElementById("breadcrumbTrail");
export const btnTreeResetExam = document.getElementById("btnTreeResetExam");
export const btnTreeChangeExam = document.getElementById("btnTreeChangeExam");
export const treeStepSelector = document.getElementById("treeStepSelector");
export const btnTabScrollLeft = document.getElementById("btnTabScrollLeft");
export const btnTabScrollRight = document.getElementById("btnTabScrollRight");

// 2x2 그리드 요소
export const panelPdfImageContainer = document.getElementById("panelPdfImageContainer");
export const btnRecapturePdf = document.getElementById("btnRecapturePdf");
export const panelPassageText = document.getElementById("panelPassageText");
export const panelExplanation = document.getElementById("panelExplanation");
export const metaPassageId = document.getElementById("metaPassageId");
export const metaQNum = document.getElementById("metaQNum");
export const metaAnswer = document.getElementById("metaAnswer");
export const metaAnswerStatus = document.getElementById("metaAnswerStatus");
export const btnEditAnswer = document.getElementById("btnEditAnswer");
export const answerEditForm = document.getElementById("answerEditForm");
export const answerEditQ = document.getElementById("answerEditQ");
export const answerEditVal = document.getElementById("answerEditVal");
export const btnSaveAnswer = document.getElementById("btnSaveAnswer");
export const btnCancelAnswer = document.getElementById("btnCancelAnswer");
export const metaCorrectRate = document.getElementById("metaCorrectRate");
export const metaQuestionTitle = document.getElementById("metaQuestionTitle");
export const metaQuestionType = document.getElementById("metaQuestionType");
export const selectQuestionType = document.getElementById("selectQuestionType");
export const validationBadge = document.getElementById("validationBadge");
export const passageTagsList = document.getElementById("passageTagsList");
export const inputPassageTag = document.getElementById("inputPassageTag");
export const btnAddPassageTag = document.getElementById("btnAddPassageTag");
export const btnCopyPassage = document.getElementById("btnCopyPassage");
const btnCardPassageSentences = document.getElementById("btnCardPassageSentences");
export const btnCopyExplanation = document.getElementById("btnCopyExplanation");

// 선지별 선택률 시각화 패널 요소
export const choiceRatesContainer = document.getElementById("choiceRatesContainer");
export const passageDifficultyBadge = document.getElementById("passageDifficultyBadge");
export const choiceRatesStatsSub = document.getElementById("choiceRatesStatsSub");
export const choiceBarsList = document.getElementById("choiceBarsList");
export const choiceRatesEmpty = document.getElementById("choiceRatesEmpty");
export const btnUploadRateFromViewer = document.getElementById("btnUploadRateFromViewer");

// [문장 결과 화면] 요소
export const sentenceViewContainer = document.getElementById("sentenceViewContainer");
export const sentenceMatchCount = document.getElementById("sentenceMatchCount");
export const sentenceTableBody = document.getElementById("sentenceTableBody");
export const btnSentenceBackToPassage = document.getElementById("btnSentenceBackToPassage");

// 어법 범주 필터 및 별표 필터
export const homeGrammarFiltersGroup = document.getElementById("homeGrammarFiltersGroup");
export const resultsGrammarFiltersGroup = document.getElementById("resultsGrammarFiltersGroup");
export const filterGrammarPos = document.getElementById("filterGrammarPos");
export const filterGrammarCategory = document.getElementById("filterGrammarCategory");
export const btnResetHomeGrammarFilter = document.getElementById("btnResetHomeGrammarFilter");
export const btnToggleStarred = document.getElementById("btnToggleStarred");
export const resultsFilterGrammarPos = document.getElementById("resultsFilterGrammarPos");
export const resultsFilterGrammarCategory = document.getElementById("resultsFilterGrammarCategory");
export const btnResetResultsGrammarFilter = document.getElementById("btnResetResultsGrammarFilter");
export const btnResultsToggleStarred = document.getElementById("btnResultsToggleStarred");
export const btnBatchAnalyzeStarred = document.getElementById("btnBatchAnalyzeStarred");
export const btnBatchAnalyzeAll = document.getElementById("btnBatchAnalyzeAll");

// AI 설정 모달 요소
export const btnOpenAiSettingsModal = document.getElementById("btnOpenAiSettingsModal");
export const aiSettingsModal = document.getElementById("aiSettingsModal");
export const btnCloseAiSettingsModal = document.getElementById("btnCloseAiSettingsModal");
export const btnCancelAiSettings = document.getElementById("btnCancelAiSettings");
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
const aiModelInput = document.getElementById("aiModelInput");
const aiModelHelp = document.getElementById("aiModelHelp");
const aiApiKeyInput = document.getElementById("aiApiKeyInput");
const btnToggleKeyVis = document.getElementById("btnToggleKeyVis");
const currentKeyBadge = document.getElementById("currentKeyBadge");
const apiKeyGuideLink = document.getElementById("apiKeyGuideLink");
const aiSettingsStatus = document.getElementById("aiSettingsStatus");
export const btnSaveAiSettings = document.getElementById("btnSaveAiSettings");

// 업로드 모달 요소
export const uploadModal = document.getElementById("uploadModal");
export const uploadForm = document.getElementById("uploadForm");
export const btnCloseUploadModal = document.getElementById("btnCloseUploadModal");
export const btnCancelUpload = document.getElementById("btnCancelUpload");
export const modalExamType = document.getElementById("modalExamType");
export const modalMonth = document.getElementById("modalMonth");

// AI 일괄 분석 실시간 진행 모달 요소
export const batchAnalysisModal = document.getElementById("batchAnalysisModal");
export const batchModalStatusBadge = document.getElementById("batchModalStatusBadge");
export const batchProgressLabel = document.getElementById("batchProgressLabel");
export const batchProgressCounter = document.getElementById("batchProgressCounter");
export const batchProgressBar = document.getElementById("batchProgressBar");
const batchCurrentCard = document.getElementById("batchCurrentCard");
export const batchCurrentSentId = document.getElementById("batchCurrentSentId");
export const batchCurrentSentText = document.getElementById("batchCurrentSentText");
export const batchLogCount = document.getElementById("batchLogCount");
export const batchLogList = document.getElementById("batchLogList");
export const batchFooterInfo = document.getElementById("batchFooterInfo");
export const btnCancelBatchAnalysis = document.getElementById("btnCancelBatchAnalysis");
export const btnCloseBatchModal = document.getElementById("btnCloseBatchModal");

// 어법 범주 상세 해설 플로팅 팝오버 요소
export const grammarExplanationPopover = document.getElementById("grammarExplanationPopover");
export const popoverBadge = document.getElementById("popoverBadge");
export const popoverPath = document.getElementById("popoverPath");
export const btnCloseGrammarPopover = document.getElementById("btnCloseGrammarPopover");
export const popoverPhraseSection = document.getElementById("popoverPhraseSection");
export const popoverPhraseText = document.getElementById("popoverPhraseText");
export const popoverExplanationText = document.getElementById("popoverExplanationText");

export const tabBtnBatchUpload = document.getElementById("tabBtnBatchUpload");
export const tabBtnFilesStatus = document.getElementById("tabBtnFilesStatus");
export const tabBtnSingleUpload = document.getElementById("tabBtnSingleUpload");
export const tabBtnManageExams = document.getElementById("tabBtnManageExams");

export const paneBatchUpload = document.getElementById("paneBatchUpload");
export const paneFilesStatus = document.getElementById("paneFilesStatus");
export const paneSingleUpload = document.getElementById("paneSingleUpload");
export const paneManageExams = document.getElementById("paneManageExams");

export const btnCancelBatchModal = document.getElementById("btnCancelBatchModal");
export const btnCloseFilesStatusModal = document.getElementById("btnCloseFilesStatusModal");
export const btnCloseManageModal = document.getElementById("btnCloseManageModal");
export const batchDropzone = document.getElementById("batchDropzone");
export const batchFileInput = document.getElementById("batchFileInput");
export const batchPreviewContainer = document.getElementById("batchPreviewContainer");
export const batchSetsTableBody = document.getElementById("batchSetsTableBody");
export const batchSetsCount = document.getElementById("batchSetsCount");
export const btnClearBatchFiles = document.getElementById("btnClearBatchFiles");
export const btnStartBatchUpload = document.getElementById("btnStartBatchUpload");
export const batchProgressBox = document.getElementById("batchProgressBox");
export const batchProgressTitle = document.getElementById("batchProgressTitle");
export const batchProgressCount = document.getElementById("batchProgressCount");
export const batchProgressBarFill = document.getElementById("batchProgressBarFill");
export const batchProgressSubtext = document.getElementById("batchProgressSubtext");

// 10-5. 등록된 시험지 관리 및 3대 데이터 영역 선택적 삭제 로직
export const manageExamsTableBody = document.getElementById("manageExamsTableBody");
export const manageExamsTotalCount = document.getElementById("manageExamsTotalCount");
export const chkAllExams = document.getElementById("chkAllExams");
export const btnSelectAllExams = document.getElementById("btnSelectAllExams");
export const btnDeleteSelectedExams = document.getElementById("btnDeleteSelectedExams");
export const selectedExamsCount = document.getElementById("selectedExamsCount");

// 선택적 삭제 모달 요소 캐싱
export const selectiveDeleteModal = document.getElementById("selectiveDeleteModal");
export const btnCloseSelectiveDeleteModal = document.getElementById("btnCloseSelectiveDeleteModal");
export const btnCancelSelectiveDelete = document.getElementById("btnCancelSelectiveDelete");
export const btnExecuteSelectiveDelete = document.getElementById("btnExecuteSelectiveDelete");
export const selDelTargetText = document.getElementById("selDelTargetText");
export const selDelRawSizeBadge = document.getElementById("selDelRawSizeBadge");
export const selDelCoreBadge = document.getElementById("selDelCoreBadge");
export const selDelMetaBadge = document.getElementById("selDelMetaBadge");
export const chkDelRawFiles = document.getElementById("chkDelRawFiles");
export const chkDelCoreCorpus = document.getElementById("chkDelCoreCorpus");
export const chkDelMetadata = document.getElementById("chkDelMetadata");
export const chkDelRateData = document.getElementById("chkDelRateData");
export const selDelRateBadge = document.getElementById("selDelRateBadge");
export const selDelWarningMsg = document.getElementById("selDelWarningMsg");
export const btnPresetFullWipe = document.getElementById("btnPresetFullWipe");
export const btnPresetRawOnly = document.getElementById("btnPresetRawOnly");
export const btnPresetMetaOnly = document.getElementById("btnPresetMetaOnly");
export const btnPresetRateOnly = document.getElementById("btnPresetRateOnly");

// 단독 파일 업로드 트리거 및 처리 함수
export const examSingleFileInput = document.getElementById("examSingleFileInput");

export const filesTotalExamsCount = document.getElementById("filesTotalExamsCount");
export const filesTotalPdfCount = document.getElementById("filesTotalPdfCount");
export const filesTotalHwpCount = document.getElementById("filesTotalHwpCount");
export const filesTotalAnsCount = document.getElementById("filesTotalAnsCount");
export const filesTotalCsvCount = document.getElementById("filesTotalCsvCount");
export const chkFilterMissingFiles = document.getElementById("chkFilterMissingFiles");
export const btnRefreshFilesStatus = document.getElementById("btnRefreshFilesStatus");
export const filesStatusTableBody = document.getElementById("filesStatusTableBody");

export const grammarCategoryModal = document.getElementById("grammarCategoryModal");
export const btnCloseGrammarModal = document.getElementById("btnCloseGrammarModal");
export const btnCancelGrammarModal = document.getElementById("btnCancelGrammarModal");
export const btnApplyGrammarSelection = document.getElementById("btnApplyGrammarSelection");
export const btnResetGrammarSelection = document.getElementById("btnResetGrammarSelection");
export const inputGrammarSearch = document.getElementById("inputGrammarSearch");
export const btnClearGrammarSearch = document.getElementById("btnClearGrammarSearch");
export const grammarSelectedCount = document.getElementById("grammarSelectedCount");
export const grammarPreviewBadges = document.getElementById("grammarPreviewBadges");
export const grammarGridContainer = document.getElementById("grammarGridContainer");
export const grammarModalSentenceInfo = document.getElementById("grammarModalSentenceInfo");
const grammarBreadcrumbBar = document.getElementById("grammarBreadcrumbBar");
export const grammarBreadcrumbTrail = document.getElementById("grammarBreadcrumbTrail");
export const grammarBreadcrumbHome = document.getElementById("grammarBreadcrumbHome");
export const btnGrammarResetStep = document.getElementById("btnGrammarResetStep");
export const btnGrammarChangeStep = document.getElementById("btnGrammarChangeStep");
export const btnGrammarToggleView = document.getElementById("btnGrammarToggleView");

// OpenRouter 드랍다운 선택 이벤트 바인딩
export const openrouterSelectEl = document.getElementById("openrouterModelSelect");

export const btnRefreshOpenRouter = document.getElementById("btnRefreshOpenRouterModels");

export const openrouterInputEl = document.getElementById("modelInputOpenrouter");

// OpenRouter 앙상블 토글 이벤트 바인딩
export const cbOREnsembleEl = document.getElementById("cbOpenRouterEnsemble");

// 앙상블 전체 실시간 모델 목록 갱신 버튼
export const btnRefreshAllOR = document.getElementById("btnRefreshOpenRouterAllModels");

// 합의 기준 변경 시 모달 요약 즉시 갱신
export const selectConsensusModeEl = document.getElementById("selectConsensusMode");

// 듣기 전용 2x2 패널 및 컨트롤 요소
export const panelTitleTopLeft = document.getElementById("panelTitleTopLeft");
export const badgeTopLeftSource = document.getElementById("badgeTopLeftSource");
export const panelTitleTopRight = document.getElementById("panelTitleTopRight");
export const badgeTopRightSource = document.getElementById("badgeTopRightSource");
export const panelTitleBottomLeft = document.getElementById("panelTitleBottomLeft");
export const badgeBottomLeftSource = document.getElementById("badgeBottomLeftSource");

export const listeningTopRightActions = document.getElementById("listeningTopRightActions");
export const btnGenerateListeningAudio = document.getElementById("btnGenerateListeningAudio");
export const btnGenerateAllListeningAudio = document.getElementById("btnGenerateAllListeningAudio");
export const btnDownloadListeningMp3 = document.getElementById("btnDownloadListeningMp3");
export const btnDownloadListeningZip = document.getElementById("btnDownloadListeningZip");

export const listeningBottomLeftActions = document.getElementById("listeningBottomLeftActions");
export const btnCopyFels = document.getElementById("btnCopyFels");
export const btnCopyFelsBlank = document.getElementById("btnCopyFelsBlank");
export const btnCopyFelsAnswer = document.getElementById("btnCopyFelsAnswer");
export const btnCopyScript = document.getElementById("btnCopyScript");
