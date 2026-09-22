/**
 * 05-gichul_db: 지문 검색 결과: 트리 탭 · 2x2 그리드 · 정답/태그 (섹션 6) (results-passage.js)
 * - main.js 에서 분리
 */

import { appState } from "./state.js";
import {
  answerEditForm,
  answerEditQ,
  answerEditVal,
  breadcrumbTrail,
  btnAddPassageTag,
  btnCancelAnswer,
  btnCopyExplanation,
  btnCopyPassage,
  btnEditAnswer,
  btnSaveAnswer,
  btnTabScrollLeft,
  btnTabScrollRight,
  btnTreeChangeExam,
  btnTreeResetExam,
  btnUploadRateFromViewer,
  choiceBarsList,
  choiceRatesContainer,
  choiceRatesEmpty,
  choiceRatesStatsSub,
  emptyResultsBox,
  inputPassageTag,
  mainSearchInput,
  metaAnswer,
  metaAnswerStatus,
  metaCorrectRate,
  metaPassageId,
  metaQNum,
  metaQuestionTitle,
  metaQuestionType,
  panelExplanation,
  panelPassageText,
  panelPdfImageContainer,
  passageDifficultyBadge,
  passageTabBar,
  passageTabCount,
  passageTagsList,
  passageViewContainer,
  resultsSearchInput,
  selectQuestionType,
  treeBreadcrumbHome,
  treeStepSelector,
  validationBadge,
} from "./dom.js";
import { setHeaderSlotState } from "./navigation.js";
import { hasActiveSearchFilters, highlightTextKeyword, loadStats, resetAllSearchFilters } from "./search.js";
import { copyToClipboard, escapeHtml, showToast } from "./utils.js";
import { triggerSingleFileUpload } from "./upload.js";

let currentDetailPassage = null;
const ANSWER_SOURCE_LABELS = { uploaded_json: "정답 JSON", verified_key: "검증 키 파일", csv: "정답률 CSV", image_consensus: "이미지 모델 합의", image_single: "이미지 단일 모델", hwp: "HWP 해설", manual: "수동 확정", none: "출처 없음" };
// =========================================================================
// 6. [지문 검색 결과] 상단 문항별 탭 & 2x2 그리드 렌더링
// =========================================================================

/** 41~42번(1지문2문항), 43~45번(1지문3문항)을 단일 탭으로 병합 (O(1) Map 색인 최적화) */
export function groupPassageItems(rawItems) {
  if (!rawItems || rawItems.length === 0) return [];

  const result = [];
  const handledIds = new Set();

  // 대량 데이터 고속 처리를 위해 exam_id + q_num 인덱스 Map 사전 구축
  const itemMap = new Map();
  for (let i = 0; i < rawItems.length; i++) {
    const it = rawItems[i];
    if (it.exam_id && it.q_num !== undefined) {
      itemMap.set(`${it.exam_id}_${it.q_num}`, it);
    }
  }

  for (let i = 0; i < rawItems.length; i++) {
    const p = rawItems[i];
    if (handledIds.has(p.id)) continue;

    // 41~42번 (1지문 2문항) 통합
    if (p.q_num === 41 || (p.question_type === "1지문2문항" && p.q_num === 41)) {
      const p42 = itemMap.get(`${p.exam_id}_42`);
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
          answer_verified: [p, p42].every((x) => Number(x.answer_verified) === 1) ? 1 : 0,
          pdf_crop_images: [p.pdf_crop_image, p42.pdf_crop_image].filter(Boolean),
          explanation_text: expText41_42
        });
        continue;
      }
    }

    // 43~45번 (1지문 3문항) 통합
    if (p.q_num === 43 || (p.question_type === "1지문3문항" && p.q_num === 43)) {
      const p44 = itemMap.get(`${p.exam_id}_44`);
      const p45 = itemMap.get(`${p.exam_id}_45`);
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
          answer_verified: [p, p44, p45].every((x) => Number(x.answer_verified) === 1) ? 1 : 0,
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

/** 학년 정렬 헬퍼: 3학년 -> 2학년 -> 1학년 내림차순 정렬 (고3 -> 고2 -> 고1) */
function sortGradesDescending(gradesList) {
  return [...gradesList].sort((a, b) => {
    const numA = parseInt(String(a).replace(/[^0-9]/g, ""), 10) || 0;
    const numB = parseInt(String(b).replace(/[^0-9]/g, ""), 10) || 0;
    if (numB !== numA) {
      return numB - numA; // 내림차순: 3 -> 2 -> 1
    }
    return String(b).localeCompare(String(a));
  });
}

/** 년도 정렬 헬퍼: 최신 년도 내림차순 (2026 -> 2025 -> 2024 ...) */
function sortYearsDescending(yearsList) {
  return [...yearsList].sort((a, b) => {
    const numA = parseInt(String(a).replace(/[^0-9]/g, ""), 10) || 0;
    const numB = parseInt(String(b).replace(/[^0-9]/g, ""), 10) || 0;
    if (numB !== numA) {
      return numB - numA;
    }
    return String(b).localeCompare(String(a));
  });
}

/** 월 정렬 헬퍼: 최신 월 내림차순 (11월 -> 9월 -> 6월 -> 3월 ...) */
function sortMonthsDescending(monthsList) {
  return [...monthsList].sort((a, b) => {
    const numA = parseInt(String(a).replace(/[^0-9]/g, ""), 10) || 0;
    const numB = parseInt(String(b).replace(/[^0-9]/g, ""), 10) || 0;
    if (numB !== numA) {
      return numB - numA;
    }
    return String(b).localeCompare(String(a));
  });
}

/** 지문 결과 화면 렌더링 (트리 계층 기반) */
export function renderPassageView(items, targetPassageId = null) {
  if (!items || items.length === 0) {
    emptyResultsBox.style.display = "flex";
    passageViewContainer.style.display = "none";
    clear2x2Panels();
    return;
  }

  emptyResultsBox.style.display = "none";
  passageViewContainer.style.display = "flex";

  const tree = buildExamTree(items);
  const grades = sortGradesDescending(Object.keys(tree));

  // 단일 시험인지 확인: 총 고유 (grade, year, month) 조합 개수 계산
  let totalExamsCount = 0;
  let singleExamCombo = null;
  grades.forEach((g) => {
    sortYearsDescending(Object.keys(tree[g])).forEach((y) => {
      sortMonthsDescending(Object.keys(tree[g][y])).forEach((m) => {
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
      appState.treeNavState.grade = h.grade;
      appState.treeNavState.year = h.year;
      appState.treeNavState.month = h.month;
    }
  } else if (totalExamsCount === 1 && singleExamCombo) {
    // 2) 검색 결과가 단 1개의 시험인 경우: 자동으로 즉시 최하위 문항 탭으로 직행!
    appState.treeNavState.grade = singleExamCombo.grade;
    appState.treeNavState.year = singleExamCombo.year;
    appState.treeNavState.month = singleExamCombo.month;
  } else {
    // 3) 복수 시험인 경우: 현재 선택된 상태가 유효한지 검사
    if (!appState.treeNavState.grade || !tree[appState.treeNavState.grade]) {
      if (grades.length === 1) {
        appState.treeNavState.grade = grades[0];
      } else {
        appState.treeNavState.grade = null;
        appState.treeNavState.year = null;
        appState.treeNavState.month = null;
      }
    }

    if (appState.treeNavState.grade && tree[appState.treeNavState.grade]) {
      const years = sortYearsDescending(Object.keys(tree[appState.treeNavState.grade]));
      if (!appState.treeNavState.year || !tree[appState.treeNavState.grade][appState.treeNavState.year]) {
        if (years.length === 1) {
          appState.treeNavState.year = years[0];
        } else {
          appState.treeNavState.year = null;
          appState.treeNavState.month = null;
        }
      }
    }

    if (appState.treeNavState.grade && appState.treeNavState.year && tree[appState.treeNavState.grade]?.[appState.treeNavState.year]) {
      const months = sortMonthsDescending(Object.keys(tree[appState.treeNavState.grade][appState.treeNavState.year]));
      if (!appState.treeNavState.month || !tree[appState.treeNavState.grade][appState.treeNavState.year][appState.treeNavState.month]) {
        if (months.length === 1) {
          appState.treeNavState.month = months[0];
        } else {
          appState.treeNavState.month = null;
        }
      }
    }
  }

  // 단계별 UI 렌더링 실행
  updateTreeUI(tree, items, totalExamsCount, targetPassageId);
}

/** 트리 단계에 따라 상위 선택기 / 최하위 문항 1행 10개 탭 전환 */
function updateTreeUI(tree, allItems, totalExamsCount, targetPassageId = null) {
  const grades = sortGradesDescending(Object.keys(tree));

  // 상단 브레드크럼 갱신
  renderBreadcrumb(tree, allItems, totalExamsCount);

  // Case 1: 학년 미선택 상태 -> 학년 선택 버튼들 표시 (3학년 -> 2학년 -> 1학년 내림차순 정렬)
  if (!appState.treeNavState.grade || !tree[appState.treeNavState.grade]) {
    treeStepSelector.style.display = "flex";
    passageTabBar.style.display = "none";
    reset2x2ContentPanels();

    let html = `<span class="tree-step-title">📁 학년 선택:</span><div class="tree-step-buttons">`;
    grades.forEach((g) => {
      let count = 0;
      sortYearsDescending(Object.keys(tree[g])).forEach((y) => {
        sortMonthsDescending(Object.keys(tree[g][y])).forEach((m) => {
          count += tree[g][y][m].items.length;
        });
      });
      html += `<button type="button" class="btn-tree-chip" data-grade="${escapeHtml(g)}">${escapeHtml(g)} <span class="chip-count">${count}</span></button>`;
    });
    html += `</div>`;
    treeStepSelector.innerHTML = html;

    treeStepSelector.querySelectorAll(".btn-tree-chip").forEach((btn) => {
      btn.addEventListener("click", () => {
        appState.treeNavState.grade = btn.dataset.grade;
        appState.treeNavState.year = null;
        appState.treeNavState.month = null;
        const years = sortYearsDescending(Object.keys(tree[appState.treeNavState.grade] || {}));
        if (years.length === 1) {
          appState.treeNavState.year = years[0];
          const months = sortMonthsDescending(Object.keys(tree[appState.treeNavState.grade][appState.treeNavState.year] || {}));
          if (months.length === 1) {
            appState.treeNavState.month = months[0];
          }
        }
        updateTreeUI(tree, allItems, totalExamsCount);
      });
    });
    return;
  }

  // Case 2: 학년 선택됨, 년도 미선택 상태 -> 년도 선택 버튼들 표시 (최신 년도 내림차순 정렬)
  const years = sortYearsDescending(Object.keys(tree[appState.treeNavState.grade] || {}));
  if (!appState.treeNavState.year || !tree[appState.treeNavState.grade][appState.treeNavState.year]) {
    treeStepSelector.style.display = "flex";
    passageTabBar.style.display = "none";
    reset2x2ContentPanels();

    let html = `<span class="tree-step-title">📅 [${escapeHtml(appState.treeNavState.grade)}] 년도 선택:</span><div class="tree-step-buttons">`;
    years.forEach((y) => {
      let count = 0;
      sortMonthsDescending(Object.keys(tree[appState.treeNavState.grade][y])).forEach((m) => {
        count += tree[appState.treeNavState.grade][y][m].items.length;
      });
      html += `<button type="button" class="btn-tree-chip" data-year="${escapeHtml(y)}">${escapeHtml(y)} <span class="chip-count">${count}</span></button>`;
    });
    html += `</div>`;
    treeStepSelector.innerHTML = html;

    treeStepSelector.querySelectorAll(".btn-tree-chip").forEach((btn) => {
      btn.addEventListener("click", () => {
        appState.treeNavState.year = btn.dataset.year;
        appState.treeNavState.month = null;
        const months = sortMonthsDescending(Object.keys(tree[appState.treeNavState.grade][appState.treeNavState.year] || {}));
        if (months.length === 1) {
          appState.treeNavState.month = months[0];
        }
        updateTreeUI(tree, allItems, totalExamsCount);
      });
    });
    return;
  }

  // Case 3: 학년과 년도 선택됨, 월 미선택 상태 -> 월 선택 버튼들 표시 (최신 월 내림차순 정렬)
  const months = sortMonthsDescending(Object.keys(tree[appState.treeNavState.grade][appState.treeNavState.year] || {}));
  if (!appState.treeNavState.month || !tree[appState.treeNavState.grade][appState.treeNavState.year][appState.treeNavState.month]) {
    treeStepSelector.style.display = "flex";
    passageTabBar.style.display = "none";
    reset2x2ContentPanels();

    let html = `<span class="tree-step-title">📆 [${escapeHtml(appState.treeNavState.grade)} ${escapeHtml(appState.treeNavState.year)}] 월/시험 선택:</span><div class="tree-step-buttons">`;
    months.forEach((m) => {
      const examObj = tree[appState.treeNavState.grade][appState.treeNavState.year][m];
      const count = examObj.items.length;
      const examType = examObj.examType ? ` (${examObj.examType})` : "";
      html += `<button type="button" class="btn-tree-chip" data-month="${escapeHtml(m)}">${escapeHtml(m)}${escapeHtml(examType)} <span class="chip-count">${count}</span></button>`;
    });
    html += `</div>`;
    treeStepSelector.innerHTML = html;

    treeStepSelector.querySelectorAll(".btn-tree-chip").forEach((btn) => {
      btn.addEventListener("click", () => {
        appState.treeNavState.month = btn.dataset.month;
        updateTreeUI(tree, allItems, totalExamsCount);
      });
    });
    return;
  }

  // Case 4: 학년, 년도, 월 모두 선택 완료! -> 상위 선택 버튼들은 숨기고, 최하위 문항 탭만 1행 10개로 표시!
  treeStepSelector.style.display = "none";
  passageTabBar.style.display = "grid";

  const examData = tree[appState.treeNavState.grade][appState.treeNavState.year][appState.treeNavState.month];
  appState.currentExamQuestions = (examData && examData.items) ? examData.items : [];

  // 문항 탭 렌더링
  renderPassageTabs(appState.currentExamQuestions);

  // 대상 문항 선택
  let activeIdx = 0;
  if (targetPassageId) {
    const fIdx = appState.currentExamQuestions.findIndex((p) => p.id === targetPassageId || (p.all_ids && p.all_ids.includes(targetPassageId)));
    if (fIdx >= 0) activeIdx = fIdx;
  }
  selectPassageTab(activeIdx, appState.currentExamQuestions);
}

/** 인라인 브레드크럼 바 렌더링 */
function renderBreadcrumb(tree, allItems, totalExamsCount) {
  if (!breadcrumbTrail) return;

  let trailHtml = "";
  const isExamSelected = !!(appState.treeNavState.grade && appState.treeNavState.year && appState.treeNavState.month);

  if (isExamSelected) {
    const examData = tree[appState.treeNavState.grade]?.[appState.treeNavState.year]?.[appState.treeNavState.month];
    const count = examData ? examData.items.length : 0;
    const examType = examData?.examType ? ` · ${examData.examType}` : "";

    trailHtml = `
        <span class="breadcrumb-item" data-step="grade" title="학년 변경">${escapeHtml(appState.treeNavState.grade)}</span>
        <span class="breadcrumb-separator">&gt;</span>
        <span class="breadcrumb-item" data-step="year" title="년도 변경">${escapeHtml(appState.treeNavState.year)}</span>
        <span class="breadcrumb-separator">&gt;</span>
        <span class="breadcrumb-item active" data-step="month" title="월/시험 변경">${escapeHtml(appState.treeNavState.month)}${escapeHtml(examType)}</span>
        <span class="breadcrumb-count-badge">(${count}문항)</span>
      `;
  } else if (appState.treeNavState.grade && appState.treeNavState.year) {
    trailHtml = `
        <span class="breadcrumb-item" data-step="grade" title="학년 변경">${escapeHtml(appState.treeNavState.grade)}</span>
        <span class="breadcrumb-separator">&gt;</span>
        <span class="breadcrumb-item active" data-step="year">${escapeHtml(appState.treeNavState.year)}</span>
        <span class="breadcrumb-separator">&gt;</span>
        <span class="breadcrumb-hint">월/시험을 선택하세요</span>
      `;
  } else if (appState.treeNavState.grade) {
    trailHtml = `
        <span class="breadcrumb-item active" data-step="grade">${escapeHtml(appState.treeNavState.grade)}</span>
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
        appState.treeNavState.grade = null;
        appState.treeNavState.year = null;
        appState.treeNavState.month = null;
      } else if (step === "year") {
        appState.treeNavState.year = null;
        appState.treeNavState.month = null;
      } else if (step === "month") {
        appState.treeNavState.month = null;
      }
      updateTreeUI(tree, allItems, totalExamsCount);
    });
  });

  // "↺ 검색 조건 초기화" 버튼: 트리 선택 상태이거나 상단 검색/필터 조건이 있는 경우 표시
  if (btnTreeResetExam) {
    const hasTreeSelection = !!(appState.treeNavState.grade || appState.treeNavState.year || appState.treeNavState.month);
    const hasActiveFilters = typeof hasActiveSearchFilters === "function" ? hasActiveSearchFilters() : false;
    const shouldShow = hasTreeSelection || hasActiveFilters || totalExamsCount > 1;

    if (shouldShow) {
      btnTreeResetExam.style.display = "inline-flex";
      btnTreeResetExam.onclick = () => {
        if (hasActiveFilters) {
          // 상단 검색 조건(필터/검색어)이 설정된 경우: 전체 검색 조건 초기화 및 전체 지문 재조회
          resetAllSearchFilters(true);
        } else {
          // 필터 없이 트리 탐색만 한 경우: 트리 선택 단계를 처음(학년 선택)으로 복귀
          appState.treeNavState.grade = null;
          appState.treeNavState.year = null;
          appState.treeNavState.month = null;
          reset2x2ContentPanels();
          updateTreeUI(tree, allItems, totalExamsCount);
          showToast("선택 단계가 초기화되었습니다.", "info");
        }
      };
    } else {
      btnTreeResetExam.style.display = "none";
    }
  }

  // 브레드크럼 홈 아이콘(📍) 클릭 시 처음 학년 선택으로 복귀 (필터가 있으면 필터도 함께 초기화)
  if (treeBreadcrumbHome) {
    treeBreadcrumbHome.style.cursor = "pointer";
    treeBreadcrumbHome.onclick = () => {
      const hasActiveFilters = typeof hasActiveSearchFilters === "function" ? hasActiveSearchFilters() : false;
      if (hasActiveFilters) {
        resetAllSearchFilters(true);
      } else if (appState.treeNavState.grade || appState.treeNavState.year || appState.treeNavState.month) {
        appState.treeNavState.grade = null;
        appState.treeNavState.year = null;
        appState.treeNavState.month = null;
        reset2x2ContentPanels();
        updateTreeUI(tree, allItems, totalExamsCount);
        showToast("선택 단계가 초기화되었습니다.", "info");
      }
    };
  }

  // "🔄 다른 시험 선택" 버튼: 복수 시험일 때만 노출
  if (btnTreeChangeExam) {
    if (totalExamsCount > 1 && isExamSelected) {
      btnTreeChangeExam.style.display = "inline-flex";
      btnTreeChangeExam.onclick = () => {
        appState.treeNavState.month = null;
        const years = Object.keys(tree[appState.treeNavState.grade] || {});
        if (years.length <= 1) {
          appState.treeNavState.grade = null;
          appState.treeNavState.year = null;
        }
        reset2x2ContentPanels();
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
export function selectPassageTab(idx, items) {
  if (!items || items.length === 0) return;
  if (idx < 0) idx = 0;
  if (idx >= items.length) idx = items.length - 1;
  appState.currentPassageIndex = idx;

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
  setHeaderSlotState("passage");
}

/** 서버에서 갱신된 단일 지문 데이터를 현재 결과 목록에 반영하고 뷰어를 다시 그림 */
function applyPassageUpdate(fresh, focusId) {
  if (!fresh || !fresh.id) return;
  const flatten = (items) => items.flatMap((it) => (it.isGroup && it.subItems) ? it.subItems : [it]);
  const replaceIn = (items) => flatten(items).map((it) => (it.id === fresh.id ? { ...it, ...fresh } : it));
  if (appState.passagesData && appState.passagesData.length) appState.passagesData = groupPassageItems(replaceIn(appState.passagesData));
  if (appState.rawPassagesData && appState.rawPassagesData.length) appState.rawPassagesData = groupPassageItems(replaceIn(appState.rawPassagesData));
  renderPassageView(appState.passagesData, focusId || fresh.id);
}

/** 2x2 패널에 특정 지문 상세 정보 로드 */
function loadPassageDetail(p) {
  if (!p) return;
  appState.currentPassageId = p.id;
  setHeaderSlotState("passage");

  // [좌측 상단]: PDF 문항 캡처 이미지 (단일 또는 그룹 이미지들)
  const rawImages = (p.pdf_crop_images && p.pdf_crop_images.length > 0)
    ? p.pdf_crop_images
    : (p.pdf_crop_image ? [p.pdf_crop_image] : []);

  // 브라우저 디스크 캐시로 인해 형광펜 하이라이트 반영 전 이미지가 노출되는 것을 방지하기 위해 캐시 버스팅 적용
  const images = rawImages.map(url => {
    if (!url) return "";
    const sep = url.includes("?") ? "&" : "?";
    return `${url}${sep}t=${Date.now()}`;
  });

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
  if (metaAnswerStatus) {
    const src = p.answer_source || "none";
    const verified = Number(p.answer_verified) === 1;
    metaAnswerStatus.textContent = verified ? `✔ 검증 · ${ANSWER_SOURCE_LABELS[src] || src}` : `⚠ 미검증 · ${ANSWER_SOURCE_LABELS[src] || src}`;
    metaAnswerStatus.className = `answer-status-badge ${verified ? "ok" : "warn"}`;
    metaAnswerStatus.style.display = p.answer_text ? "inline-flex" : "none";
  }
  currentDetailPassage = p;
  if (btnEditAnswer) btnEditAnswer.style.display = "inline-block";
  if (answerEditForm) answerEditForm.style.display = "none";
  if (metaQuestionTitle) metaQuestionTitle.textContent = p.question_title || "-";
  validationBadge.textContent = p.remarks || `일치율 ${(p.validation_ratio * 100).toFixed(1)}%`;

  // 20대 문제 유형 선택기 반영
  if (selectQuestionType) {
    selectQuestionType.value = p.question_type || "글의목적";
    selectQuestionType.onchange = async () => {
      const newType = selectQuestionType.value;
      try {
        const res = await fetch(`/api/passages/${encodeURIComponent(appState.currentPassageId)}/question-type`, {
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
  renderChoiceRates(p);
}

function getDifficultyInfo(rate) {
  if (rate === null || rate === undefined || isNaN(rate)) {
    return { level: "none", label: "미등록", badgeClass: "badge-rate-none" };
  }
  const r = parseFloat(rate);
  if (r < 40.0) {
    return { level: "killer", label: "🔴 킬러 · 고난도", badgeClass: "badge-rate-killer" };
  } else if (r < 60.0) {
    return { level: "hard", label: "🟠 중고난도", badgeClass: "badge-rate-hard" };
  } else if (r < 80.0) {
    return { level: "medium", label: "🟡 보통 난이도", badgeClass: "badge-rate-medium" };
  } else {
    return { level: "easy", label: "🟢 평이 문항", badgeClass: "badge-rate-easy" };
  }
}

export function renderChoiceRates(p) {
  if (!choiceRatesContainer) return;

  const rate = (p.correct_rate !== null && p.correct_rate !== undefined) ? parseFloat(p.correct_rate) : null;
  const diff = getDifficultyInfo(rate);

  // 1. 메타 정답률 배지 렌더링
  if (metaCorrectRate) {
    if (rate !== null) {
      metaCorrectRate.innerHTML = `<span class="${diff.badgeClass}" title="정답률 ${rate.toFixed(1)}%">${rate.toFixed(1)}%</span>`;
    } else {
      metaCorrectRate.innerHTML = `<span class="badge-rate-none">미등록</span>`;
    }
  }

  if (passageDifficultyBadge) {
    passageDifficultyBadge.className = `choice-rates-difficulty-badge ${diff.badgeClass}`;
    passageDifficultyBadge.textContent = diff.label;
  }

  // 2. 선지별 선택률 파싱
  let ratesObj = null;
  if (p.choice_rates_obj && typeof p.choice_rates_obj === "object") {
    ratesObj = p.choice_rates_obj;
  } else if (p.choice_rates) {
    if (typeof p.choice_rates === "object") {
      ratesObj = p.choice_rates;
    } else if (typeof p.choice_rates === "string") {
      try {
        ratesObj = JSON.parse(p.choice_rates);
      } catch (e) {
        ratesObj = null;
      }
    }
  }

  // 데이터가 없는 경우 -> 엠프티 안내 및 단독 등록 버튼 노출
  if (!ratesObj || (!ratesObj["1"] && !ratesObj["2"] && !ratesObj["3"] && !ratesObj["4"] && !ratesObj["5"])) {
    if (choiceBarsList) choiceBarsList.innerHTML = "";
    if (choiceRatesStatsSub) choiceRatesStatsSub.textContent = "정답률 데이터가 등록되지 않았습니다.";
    if (choiceRatesEmpty) choiceRatesEmpty.style.display = "flex";
    return;
  }

  if (choiceRatesEmpty) choiceRatesEmpty.style.display = "none";

  // 총 응시자 수 표기
  const totalCount = ratesObj.counts?.total;
  if (choiceRatesStatsSub) {
    choiceRatesStatsSub.textContent = totalCount ? `총 응시자 ${totalCount.toLocaleString()}명 기준` : `선지별 선택 비율`;
  }

  // 정답 선지 및 원문자 정규화
  const circleSymbols = { "1": "①", "2": "②", "3": "③", "4": "④", "5": "⑤" };
  const circleToNum = { "①": "1", "②": "2", "③": "3", "④": "4", "⑤": "5", "1": "1", "2": "2", "3": "3", "4": "4", "5": "5" };
  const ansRaw = (p.answer_text || "").trim();
  const correctAnsNum = circleToNum[ansRaw] || "";

  // 매력적 오답 정보
  const attractiveWrong = ratesObj.attractive_wrong;
  const attractiveChoice = attractiveWrong ? String(attractiveWrong.choice) : "";

  if (choiceBarsList) {
    choiceBarsList.innerHTML = "";
    for (let ch = 1; ch <= 5; ch++) {
      const chStr = String(ch);
      const circleSym = circleSymbols[chStr];
      const val = ratesObj[chStr] !== undefined ? parseFloat(ratesObj[chStr]) : 0.0;
      const count = (ratesObj.counts && ratesObj.counts[chStr] !== undefined) ? ratesObj.counts[chStr] : null;

      const isCorrect = (chStr === correctAnsNum);
      const isTrap = !isCorrect && (chStr === attractiveChoice);

      let rowClass = "choice-bar-row";
      if (isCorrect) rowClass += " choice-correct";
      else if (isTrap) rowClass += " choice-trap";

      let tagHtml = "";
      if (isCorrect) {
        tagHtml = `<span class="choice-star">★ 정답</span>`;
      } else if (isTrap) {
        tagHtml = `<span class="choice-trap-tag">🚨 매력적 오답</span>`;
      }

      const countLabel = (count !== null) ? `<span class="choice-count-label">(${count.toLocaleString()}명)</span>` : "";

      const row = document.createElement("div");
      row.className = rowClass;
      row.innerHTML = `
          <div class="choice-label-badge">
            <span class="choice-num-circle">${circleSym}</span>
            ${tagHtml}
          </div>
          <div class="choice-progress-wrapper" title="${circleSym} 선택률: ${val.toFixed(1)}%${count !== null ? ` (${count}명)` : ''}">
            <div class="choice-progress-fill" style="width: ${Math.min(100, Math.max(0, val))}%;"></div>
          </div>
          <div class="choice-percent-val">
            <strong>${val.toFixed(1)}%</strong>
            ${countLabel}
          </div>
        `;
      choiceBarsList.appendChild(row);
    }
  }
}

function reset2x2ContentPanels() {
  panelPdfImageContainer.innerHTML = `<div class="pdf-placeholder">탐색할 시험 및 문항을 선택하세요.</div>`;
  panelPassageText.textContent = "-";
  panelPassageText.dataset.rawText = "";
  panelExplanation.textContent = "-";
  metaPassageId.textContent = "-";
  metaQNum.textContent = "-";
  if (metaQuestionType) metaQuestionType.textContent = "-";
  metaAnswer.textContent = "-";
  if (metaAnswerStatus) metaAnswerStatus.style.display = "none";
  if (btnEditAnswer) btnEditAnswer.style.display = "none";
  if (answerEditForm) answerEditForm.style.display = "none";
  currentDetailPassage = null;
  if (metaCorrectRate) metaCorrectRate.innerHTML = "-";
  if (metaQuestionTitle) metaQuestionTitle.textContent = "-";
  if (choiceBarsList) choiceBarsList.innerHTML = "";
  if (passageDifficultyBadge) {
    passageDifficultyBadge.textContent = "-";
    passageDifficultyBadge.className = "choice-rates-difficulty-badge";
  }
  if (choiceRatesStatsSub) choiceRatesStatsSub.textContent = "-";
  if (choiceRatesEmpty) choiceRatesEmpty.style.display = "none";
  passageTagsList.innerHTML = "";
  appState.currentPassageId = null;
  setHeaderSlotState("passage");
}

function clear2x2Panels() {
  reset2x2ContentPanels();
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
      await deletePassageTag(appState.currentPassageId, tag);
    });

    passageTagsList.appendChild(badge);
  });
}

/** 지문 태그 추가 API */
async function addPassageTagAction() {
  const tagName = inputPassageTag.value.trim();
  if (!tagName || !appState.currentPassageId) return;

  try {
    const res = await fetch(`/api/passages/${encodeURIComponent(appState.currentPassageId)}/tags`, {
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

// ---- 이벤트 바인딩 및 초기화 (main.js 에서 원본 순서대로 호출) ----
export function init() {

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

    const targetList = (appState.currentExamQuestions && appState.currentExamQuestions.length > 0) ? appState.currentExamQuestions : appState.passagesData;
    if (!targetList || targetList.length === 0) return;

    if (e.key === "ArrowLeft") {
      if (appState.currentPassageIndex > 0) {
        selectPassageTab(appState.currentPassageIndex - 1, targetList);
      }
    } else if (e.key === "ArrowRight") {
      if (appState.currentPassageIndex < targetList.length - 1) {
        selectPassageTab(appState.currentPassageIndex + 1, targetList);
      }
    }
  });

  /** 정답 수동 정정: 편집 폼 표시 */
  if (btnEditAnswer) {
    btnEditAnswer.addEventListener("click", () => {
      const p = currentDetailPassage;
      if (!p || !answerEditForm) return;
      const targets = (p.isGroup && p.subItems) ? p.subItems : [p];
      answerEditQ.innerHTML = targets.map((t, i) => `<option value="${i}">${t.q_num}번</option>`).join("");
      answerEditQ.style.display = targets.length > 1 ? "inline-block" : "none";
      answerEditQ.value = "0";
      answerEditVal.value = ["①", "②", "③", "④", "⑤"].includes(targets[0].answer_text) ? targets[0].answer_text : "①";
      answerEditForm.style.display = "inline-flex";
    });
    answerEditQ.addEventListener("change", () => {
      const p = currentDetailPassage;
      const targets = (p && p.isGroup && p.subItems) ? p.subItems : [p];
      const t = targets[Number(answerEditQ.value)] || targets[0];
      if (t && ["①", "②", "③", "④", "⑤"].includes(t.answer_text)) answerEditVal.value = t.answer_text;
    });
    btnCancelAnswer.addEventListener("click", () => { answerEditForm.style.display = "none"; });
    btnSaveAnswer.addEventListener("click", async () => {
      const p = currentDetailPassage;
      if (!p) return;
      const targets = (p.isGroup && p.subItems) ? p.subItems : [p];
      const target = targets[Number(answerEditQ.value)] || targets[0];
      const newAns = answerEditVal.value;
      if (target.answer_text === newAns) { answerEditForm.style.display = "none"; return; }
      if (!confirm(`${target.id} 정답을 '${target.answer_text || "-"}' → '${newAns}' 로 정정할까요?\n(DB·해설·형광펜 이미지·검증 키 파일에 함께 반영됩니다)`)) return;
      btnSaveAnswer.disabled = true;
      btnSaveAnswer.textContent = "반영 중...";
      try {
        const res = await fetch(`/api/passages/${encodeURIComponent(target.id)}/answer`, {
          method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ answer: newAns })
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "정답 정정 실패");
        applyPassageUpdate(data.passage, p.id);
        showToast(data.message || "정답이 정정되었습니다.", "success");
      } catch (err) {
        console.error(err);
        showToast(err.message || "정답 정정 중 오류가 발생했습니다.", "error");
      } finally {
        btnSaveAnswer.disabled = false;
        btnSaveAnswer.textContent = "저장";
        if (answerEditForm) answerEditForm.style.display = "none";
      }
    });
  }

  if (btnUploadRateFromViewer) {
    btnUploadRateFromViewer.addEventListener("click", () => {
      const currentExamId = currentDetailPassage ? currentDetailPassage.exam_id : null;
      if (!currentExamId) return;
      triggerSingleFileUpload(currentExamId, "csv", btnUploadRateFromViewer);
    });
  }

  btnAddPassageTag.addEventListener("click", addPassageTagAction);
  inputPassageTag.addEventListener("keydown", (e) => {
    if (e.key === "Enter") addPassageTagAction();
  });

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
}
