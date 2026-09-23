/**
 * 05-gichul_db: 지문 검색 결과: 트리 탭 · 2x2 그리드 · 정답/태그 (섹션 6) (results-passage.js)
 * - main.js 에서 분리
 */

import { appState } from "./state.js";
import {
  answerEditForm,
  answerEditQ,
  answerEditVal,
  badgeBottomLeftSource,
  badgeTopLeftSource,
  badgeTopRightSource,
  breadcrumbTrail,
  btnAddPassageTag,
  btnCancelAnswer,
  btnCopyExplanation,
  btnCopyFels,
  btnCopyFelsBlank,
  btnCopyFelsAnswer,
  btnCopyPassage,
  btnCopyScript,
  btnDownloadListeningMp3,
  btnDownloadListeningZip,
  btnEditAnswer,
  btnGenerateAllListeningAudio,
  btnGenerateListeningAudio,
  btnRecapturePdf,
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
  listeningBottomLeftActions,
  listeningTopRightActions,
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
  panelTitleBottomLeft,
  panelTitleTopLeft,
  panelTitleTopRight,
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

/**
 * 50문항 체제 시험지에서 발문 및 본문 텍스트를 분석하여 40~50번 복합 지문 그룹을 동적으로 판별
 * 예: [[46, 47], [48, 50]] 또는 [[46, 48], [49, 50]] 또는 [[46, 47], [48, 49]] 또는 [[47, 48], [49, 50]]
 */
function resolveCompoundGroupsFor50(examId, itemMap) {
  const p46 = itemMap.get(`${examId}_46`);
  const p47 = itemMap.get(`${examId}_47`);
  const p48 = itemMap.get(`${examId}_48`);
  const p49 = itemMap.get(`${examId}_49`);
  const p50 = itemMap.get(`${examId}_50`);

  const t46 = p46 ? `${p46.question_title || ""} ${p46.passage_text || ""}` : "";
  const t47 = p47 ? `${p47.question_title || ""} ${p47.passage_text || ""}` : "";
  const t48 = p48 ? `${p48.question_title || ""} ${p48.passage_text || ""}` : "";
  const t49 = p49 ? `${p49.question_title || ""} ${p49.passage_text || ""}` : "";
  const t50 = p50 ? `${p50.question_title || ""} ${p50.passage_text || ""}` : "";

  const allText = `${t46}\n${t47}\n${t48}\n${t49}\n${t50}`;

  // 1. 발문 및 본문 내 명시적 헤더 [X~Y] 탐색
  const has46_47 = /\[?\s*46\s*[~～\-]\s*47\s*\]?/.test(t46) || /\[?\s*46\s*[~～\-]\s*47\s*\]?/.test(allText);
  const has48_50 = /\[?\s*48\s*[~～\-]\s*50\s*\]?/.test(t48) || /\[?\s*48\s*[~～\-]\s*50\s*\]?/.test(allText);
  const has48_49 = /\[?\s*48\s*[~～\-]\s*49\s*\]?/.test(t48) || /\[?\s*48\s*[~～\-]\s*49\s*\]?/.test(allText);
  const has46_48 = /\[?\s*46\s*[~～\-]\s*48\s*\]?/.test(t46) || /\[?\s*46\s*[~～\-]\s*48\s*\]?/.test(allText);
  const has47_48 = /\[?\s*47\s*[~～\-]\s*48\s*\]?/.test(t47) || /\[?\s*47\s*[~～\-]\s*48\s*\]?/.test(allText);

  if (has46_47 && has48_50) {
    return [[46, 47], [48, 50]];
  }
  if (has46_47 && has48_49) {
    return [[46, 47], [48, 49]];
  }
  if (has47_48) {
    return [[47, 48], [49, 50]];
  }
  if (has46_48) {
    return [[46, 48], [49, 50]];
  }

  // 2. 발문 키워드 기반 판별: 1지문 3문항(장문 독해 순서 배열 A~D) 시작점 확인
  const is3QOrderStart = (txt) =>
    /\(A\)\s*에\s*이어질|주어진\s*글\s*\(A\)|순서대로\s*바르게\s*배열|순서에\s*맞게\s*배열/i.test(txt);

  if (is3QOrderStart(t48)) {
    // 48번이 장문 독해(A~D) 순서 배열 시작점 -> [46~47] 2문항 + [48~50] 3문항
    return [[46, 47], [48, 50]];
  }
  if (is3QOrderStart(t46)) {
    // 46번이 장문 독해(A~D) 순서 배열 시작점 -> [46~48] 3문항 + [49~50] 2문항
    return [[46, 47, 48], [49, 50]];
  }

  // 46번이 단독 어법/요약이고 47번이 '위 글'인 경우
  if (/빈칸\s*\(A\)[,\s]*\(B\)/.test(t46) && /위\s*글/.test(t47)) {
    return [[47, 48], [49, 50]];
  }

  if (has48_49) {
    return [[46, 47], [48, 49]];
  }

  // 기본값: 표준 46~48번(3문항) + 49~50번(2문항)
  return [[46, 48], [49, 50]];
}

/** 41~42번/43~45번(45문항 체제) 또는 46~48번/49~50번/46~47번/48~50번 등(50문항 체제) 복합 지문을 발문 분석을 통해 동적으로 단일 탭으로 병합 */
export function groupPassageItems(rawItems) {
  if (!rawItems || rawItems.length === 0) return [];

  const result = [];
  const handledIds = new Set();

  // exam별 50문항 체제 여부 판별 (1: reading_end_q >= 48, 2: q_num >= 46 존재, 3: 2006~2011년 기출)
  const examIs50Map = new Map();
  for (let i = 0; i < rawItems.length; i++) {
    const it = rawItems[i];
    if (!it.exam_id) continue;
    if (!examIs50Map.has(it.exam_id)) examIs50Map.set(it.exam_id, false);
    const yMatch = it.exam_id.match(/(\d{4})년/) || (it.year ? [null, it.year] : null);
    const yr = yMatch ? parseInt(yMatch[1], 10) : 0;
    if (it.reading_end_q >= 48 || it.q_num >= 46 || (yr >= 2006 && yr <= 2011)) {
      examIs50Map.set(it.exam_id, true);
    }
  }

  // 대량 데이터 고속 처리를 위해 exam_id + q_num 인덱스 Map 사전 구축
  const itemMap = new Map();
  for (let i = 0; i < rawItems.length; i++) {
    const it = rawItems[i];
    if (it.exam_id && it.q_num !== undefined) {
      itemMap.set(`${it.exam_id}_${it.q_num}`, it);
    }
  }

  // 50문항 체제 시험별 동적 복합 지문 그룹 캐시
  const examCompoundGroupsMap = new Map();

  for (let i = 0; i < rawItems.length; i++) {
    const p = rawItems[i];
    if (handledIds.has(p.id)) continue;

    const is50Exam = examIs50Map.get(p.exam_id) || false;

    if (is50Exam) {
      // =======================================================================
      // [총 50문항 체제]: 발문 분석 기반 동적 복합 지문 통합 ([46~48]+[49~50] 또는 [46~47]+[48~50] 등)
      // =======================================================================
      if (!examCompoundGroupsMap.has(p.exam_id)) {
        examCompoundGroupsMap.set(p.exam_id, resolveCompoundGroupsFor50(p.exam_id, itemMap));
      }
      const groups = examCompoundGroupsMap.get(p.exam_id) || [];
      const matchedGroup = groups.find((g) => g[0] === p.q_num);

      if (matchedGroup) {
        const [gStart, gEnd] = matchedGroup;
        const subItems = [];
        let allFound = true;
        for (let q = gStart; q <= gEnd; q++) {
          const item = itemMap.get(`${p.exam_id}_${q}`);
          if (item) {
            subItems.push(item);
          } else {
            allFound = false;
            break;
          }
        }

        if (allFound && subItems.length > 1) {
          subItems.forEach((si) => handledIds.add(si.id));

          const examPrefix = p.id.replace(new RegExp(`-${gStart}번\\]$`), "").replace(/^\[/, "");
          const ansLabel = subItems.map((si) => `${si.q_num}.${si.answer_text || "-"}`).join(" / ");
          const combinedAns = `[정답] ` + subItems.map((si) => `${si.q_num}. ${si.answer_text || "-"}`).join("   ");
          const baseExp = (subItems.map((si) => si.explanation_text).filter(Boolean)[0] || "").replace(/^\[정답\][^\n]*\n*/, "");
          const expText = `${combinedAns}\n\n${baseExp.trim()}`;
          const qCount = subItems.length;
          const groupTypeLabel = `1지문${qCount}문항`;
          const rangeLabel = `${gStart}~${gEnd}번`;

          result.push({
            ...p,
            isGroup: true,
            groupType: `${gStart}-${gEnd}`,
            q_num_label: rangeLabel,
            display_id: `[${examPrefix}-${rangeLabel}]`,
            all_ids: subItems.map((si) => si.id),
            subItems: subItems,
            question_type: groupTypeLabel,
            answer_text: ansLabel,
            answer_verified: subItems.every((x) => Number(x.answer_verified) === 1) ? 1 : 0,
            pdf_crop_images: Array.from(new Set(subItems.map((si) => si.pdf_crop_image).filter(Boolean))),
            explanation_text: expText
          });
          continue;
        }
      }

    } else {
      // =======================================================================
      // [총 45문항 체제 (2012년 이후)]: 41~42번 (1지문2문항) / 43~45번 (1지문3문항)
      // =======================================================================

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
            pdf_crop_images: Array.from(new Set([p.pdf_crop_image, p42.pdf_crop_image].filter(Boolean))),
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
            pdf_crop_images: Array.from(new Set([p.pdf_crop_image, p44.pdf_crop_image, p45.pdf_crop_image].filter(Boolean))),
            explanation_text: expText43_45
          });
          continue;
        }
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

/** 지문 본문이나 문제 텍스트에 오염되어 포함된 정답표/해설 텍스트 블록을 안전하게 잘라냄 */
function cleanQuestionExplanationLeak(text) {
  if (!text) return "";
  // 예: '2026학년도 영어영역 정답 및 해설', '정답 및 해설', '정답표', '[출제의도]', '[해설]' 등으로 시작하는 블록 감지
  const leakRegex = /(?:^|\n)\s*(?:[^\n]{0,35})?(?:정답\s*(?:및|과)?\s*해설|정답표|정답\s*및\s*풀이|해설\s*및\s*정답|\[\s*출제\s*의도\s*\]|\[\s*해설\s*\])/i;
  const match = text.search(leakRegex);
  if (match !== -1) {
    return text.substring(0, match).trim();
  }
  return text.trim();
}

/** 42번, 44번, 45번 등 복합 지문 하위 문항에서 지문 본문 반복을 제외하고 발문+선지만 추출 */
function extractQuestionChoicesOnly(text, questionTitle) {
  if (!text) return questionTitle || "";
  const cleaned = cleanQuestionExplanationLeak(text);
  const cIdx = cleaned.indexOf("①");
  if (cIdx !== -1) {
    const choices = cleaned.substring(cIdx).trim();
    return `${questionTitle || ""}\n\n${choices}`.trim();
  }
  return questionTitle || cleaned;
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
      let questionCount = 0;
      let examCount = 0;
      sortYearsDescending(Object.keys(tree[g])).forEach((y) => {
        const months = sortMonthsDescending(Object.keys(tree[g][y]));
        examCount += months.length;
        months.forEach((m) => {
          questionCount += tree[g][y][m].items.length;
        });
      });
      html += `<button type="button" class="btn-tree-chip" data-grade="${escapeHtml(g)}">${escapeHtml(g)} <span class="chip-count">${questionCount.toLocaleString()}문항 (${examCount}회)</span></button>`;
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
      let questionCount = 0;
      const months = sortMonthsDescending(Object.keys(tree[appState.treeNavState.grade][y]));
      const examCount = months.length;
      months.forEach((m) => {
        questionCount += tree[appState.treeNavState.grade][y][m].items.length;
      });
      html += `<button type="button" class="btn-tree-chip" data-year="${escapeHtml(y)}">${escapeHtml(y)} <span class="chip-count">${questionCount.toLocaleString()}문항 (${examCount}회)</span></button>`;
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
      html += `<button type="button" class="btn-tree-chip" data-month="${escapeHtml(m)}">${escapeHtml(m)}${escapeHtml(examType)} <span class="chip-count">${count}문항</span></button>`;
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
    const examSetHint = totalExamsCount ? ` (${totalExamsCount}회차 시험지 세트)` : "";
    trailHtml = `
        <span class="breadcrumb-hint">총 ${allItems.length.toLocaleString()}개 문항${examSetHint} 중 탐색할 학년을 선택하세요</span>
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

/** FELS 학생용 빈칸 텍스트([ ]) 복사 (최장 단어 글자수 균일 공백 적용) */
export function copyFelsBlankVersion() {
  const felsText = currentDetailPassage ? (currentDetailPassage.fels_text || "") : "";
  if (!felsText) {
    showToast("복사할 FELS 텍스트가 없습니다.", "warning");
    return;
  }
  // 1. 모든 괄호 안의 기능어 단어 추출 (<단어> 및 [단어] 지원, 순수 공백 제외)
  const matches = Array.from(felsText.matchAll(/<([^>]+?)>|\[([^\]]+?)\]/g));
  const words = matches
    .map((m) => (m[1] || m[2] || "").trim())
    .filter((w) => w.length > 0);

  // 2. 들어가는 단어의 철자수와는 상관 없이 최고 긴 단어의 길이 계산
  let maxLen = 0;
  for (const w of words) {
    if (w.length > maxLen) maxLen = w.length;
  }
  if (maxLen === 0) maxLen = 5;

  // 3. 최고 긴 단어의 길이에 맞게 모든 [ ]에 동일한 개수의 공백 빈칸 적용
  const blankStr = `[${" ".repeat(maxLen)}]`;
  const blankText = felsText.replace(/<([^>]+?)>|\[([^\]]+?)\]/g, (match, p1, p2) => {
    const content = (p1 || p2 || "").trim();
    return content ? blankStr : match;
  });

  copyToClipboard(
    blankText,
    `FELS 학생용 빈칸([ ]) 텍스트가 클립보드에 복사되었습니다! (최장 ${maxLen}자 기준 공백 일괄 적용)`
  );
}

/** FELS 교사용 정답 텍스트([단어]) 복사 */
export function copyFelsAnswerVersion() {
  const felsText = currentDetailPassage ? (currentDetailPassage.fels_text || "") : "";
  if (!felsText) {
    showToast("복사할 FELS 텍스트가 없습니다.", "warning");
    return;
  }
  // <단어>가 있는 경우 [단어]로 일관되게 치환하여 교사용 정답지 생성 (학생용 [ ] 빈칸과 1:1 대응)
  const answerText = felsText.replace(/<([^>]+?)>/g, "[$1]");
  copyToClipboard(
    answerText,
    "FELS 교사용 정답 텍스트([단어])가 클립보드에 복사되었습니다! (정답지·해설용)"
  );
}

/** 2x2 패널에 특정 지문 상세 정보 로드 */
function loadPassageDetail(p) {
  if (!p) return;
  appState.currentPassageId = p.id;
  setHeaderSlotState("passage");

  const isListening = p.area === "listening";

  // 1. 헤더 텍스트 및 배지 동적 전환
  if (panelTitleTopLeft) panelTitleTopLeft.textContent = isListening ? "🖼️ 문제 + 📜 대본 캡처 (상하 수직 배열)" : "🖼️ PDF 문항 캡처 이미지";
  if (badgeTopLeftSource) badgeTopLeftSource.textContent = "고화질 원본";
  if (panelTitleTopRight) panelTitleTopRight.textContent = isListening ? "📝 영문 대본 텍스트 & 🎙️ 음성 듣기" : "📝 TXT 지문 본문 텍스트";
  const ttsLabel = (appState.ttsEngine === "elevenlabs") ? "ElevenLabs TTS" : "Edge-TTS (무료)";
  if (badgeTopRightSource) badgeTopRightSource.textContent = isListening ? ttsLabel : "순수 영문";
  if (panelTitleBottomLeft) panelTitleBottomLeft.textContent = isListening ? "🎯 FELS (기능어 약형드랩) 교사용 텍스트" : "📘 HWP 정답 및 해설";
  if (badgeBottomLeftSource) badgeBottomLeftSource.textContent = isListening ? "7대 기능어 추출" : "공식 해설지";

  // 2. 우측 상단 & 좌측 하단 버튼 그룹 표시 전환
  if (btnCopyPassage) btnCopyPassage.style.display = isListening ? "none" : "inline-flex";
  if (listeningTopRightActions) listeningTopRightActions.style.display = isListening ? "flex" : "none";

  if (btnCopyExplanation) btnCopyExplanation.style.display = isListening ? "none" : "inline-flex";
  if (listeningBottomLeftActions) listeningBottomLeftActions.style.display = isListening ? "flex" : "none";

  // [좌측 상단]: PDF 문항 캡처 이미지 (단일 또는 그룹 이미지들)
  let rawImages = (p.pdf_crop_images && p.pdf_crop_images.length > 0)
    ? p.pdf_crop_images
    : (p.pdf_crop_image ? [p.pdf_crop_image] : []);

  // 동일한 이미지 URL이 중복 지정된 경우 1장만 노출
  rawImages = Array.from(new Set(rawImages.filter(Boolean)));

  // 캐시 버스팅 적용
  const images = rawImages.map(url => {
    if (!url) return "";
    const sep = url.includes("?") ? "&" : "?";
    return `${url}${sep}t=${Date.now()}`;
  });

  if (isListening) {
    // 듣기 모드: 문제지 크롭(위) + 구분선 + 대본 크롭(아래) 상하 수직 배열
    const qImgSrc = (images.length > 0) ? images[0] : "";
    let sImgSrc = p.script_crop_image || "";
    if (sImgSrc) {
      const sep = sImgSrc.includes("?") ? "&" : "?";
      sImgSrc = `${sImgSrc}${sep}t=${Date.now()}`;
    }

    const qCropHtml = qImgSrc
      ? `<div class="listening-crop-img-wrapper"><img src="${qImgSrc}" class="pdf-crop-img listening-crop-img" alt="${escapeHtml(p.display_id || p.id)} 문제지 캡처" title="클릭 시 새 창에서 원본 크기 확대 보기"></div>`
      : `<div class="pdf-placeholder" style="padding: 1.5rem 1rem; min-height: 100px;">🖼️ 문제지 캡처 이미지가 생성되지 않았습니다.</div>`;

    const sCropHtml = sImgSrc
      ? `<div class="listening-crop-img-wrapper"><img src="${sImgSrc}" class="pdf-crop-img listening-crop-img" alt="${escapeHtml(p.display_id || p.id)} 대본 캡처" title="클릭 시 새 창에서 원본 크기 확대 보기"></div>`
      : `<div class="pdf-placeholder" style="padding: 1.25rem 1rem; min-height: 100px;">
           <div style="font-size: 0.88rem; font-weight: 600; color: #64748b;">📜 대본 크롭 이미지가 아직 등록되지 않았습니다.</div>
           <div style="font-size: 0.78rem; color: #94a3b8; margin-top: 4px;">대본 PDF 파일 또는 해설 PDF 파일을 업로드하면 대본 섹션이 자동 크롭됩니다.</div>
         </div>`;

    panelPdfImageContainer.innerHTML = `
      <div class="listening-crops-container">
        <div class="listening-crop-section">
          <div class="listening-crop-section-header">
            <span class="crop-section-badge badge-q">📑 문제지 캡처</span>
            <span class="crop-section-hint">클릭 시 새 창 확대 보기</span>
          </div>
          ${qCropHtml}
        </div>

        <div class="crop-section-divider">
          <span class="crop-divider-line"></span>
          <span class="crop-divider-badge">📜 원본 대본 인쇄본</span>
          <span class="crop-divider-line"></span>
        </div>

        <div class="listening-crop-section">
          <div class="listening-crop-section-header">
            <span class="crop-section-badge badge-s">📜 대본 / 해설지 원본</span>
            <span class="crop-section-hint">클릭 시 새 창 확대 보기</span>
          </div>
          ${sCropHtml}
        </div>
      </div>
    `;

    panelPdfImageContainer.querySelectorAll(".listening-crop-img").forEach((img) => {
      img.addEventListener("click", () => window.open(img.src, "_blank"));
    });
  } else if (images.length > 0) {
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
          <div style="font-size: 0.98rem; font-weight: 700; margin-bottom: 6px; color: #475569;">
            🖼️ PDF 문항 캡처 이미지가 생성되지 않았거나 없습니다.
          </div>
          <div style="color: var(--text-light); font-size: 0.8rem; line-height: 1.5; max-width: 440px; margin: 0 auto;">
            시험지 업로드 시 PDF 파일을 함께 등록하시면 원본 문항 인쇄 영역이 고화질로 자동 크롭됩니다.
          </div>
          <div>
            <button type="button" class="btn-inline-recapture">
              🔄 지금 다시 캡처 실행
            </button>
          </div>
        </div>
      `;
  }

  // [우측 상단]: TXT 지문 본문 / 듣기 스크립트 + ElevenLabs TTS
  if (isListening) {
    const rawScript = p.script_text || p.passage_text || "대본 정보가 등록되지 않았습니다.";
    panelPassageText.dataset.rawText = rawScript;

    let formattedScript = escapeHtml(rawScript);
    formattedScript = formattedScript.replace(
      /(^|\n)\s*(M|W|Man|Woman|Boy|Girl|남|여)\s*:\s*/g,
      (match, p1, speaker) => {
        const isMale = /^(M|Man|Boy|남)$/i.test(speaker);
        const cls = isMale ? "speaker-tag speaker-male" : "speaker-tag speaker-female";
        return `${p1}<span class="${cls}">${speaker}:</span> `;
      }
    );

    const currentQuery = (resultsSearchInput && resultsSearchInput.value.trim()) || 
                         (mainSearchInput && mainSearchInput.value.trim()) || "";
    if (currentQuery) {
      formattedScript = highlightTextKeyword(formattedScript, currentQuery, "passage-highlight");
    }

    const hasAudio = !!p.audio_file_path;
    const audioSrc = hasAudio ? `${p.audio_file_path}?t=${Date.now()}` : "";

    panelPassageText.innerHTML = `
      <div class="listening-top-right-wrapper">
        <div class="listening-audio-bar">
          <div class="audio-player-row">
            <audio id="listeningAudioPlayer" controls src="${audioSrc}" style="flex: 1; height: 38px; border-radius: 8px;"></audio>
            <span class="audio-status-chip ${hasAudio ? 'ready' : 'empty'}" id="audioStatusChip">
              ${hasAudio ? '🎙️ 음성 준비됨' : '🎙️ 음성 미생성'}
            </span>
          </div>
        </div>
        <div class="listening-script-text-box">
          ${formattedScript}
        </div>
      </div>
    `;
  } else {
    let rawPassageText = "";
    if (p.isGroup && p.subItems && p.subItems.length > 1) {
      const parts = p.subItems.map((si, sIdx) => {
        if (sIdx === 0) {
          return cleanQuestionExplanationLeak(si.passage_text || si.question_title || "");
        } else {
          return extractQuestionChoicesOnly(si.passage_text, si.question_title);
        }
      });
      rawPassageText = parts.filter(Boolean).join("\n\n----------------------------------------\n\n");
    } else {
      rawPassageText = cleanQuestionExplanationLeak(p.passage_text) || "지문 본문 텍스트가 비어 있습니다.";
    }

    panelPassageText.dataset.rawText = rawPassageText;
    const currentQuery = (resultsSearchInput && resultsSearchInput.value.trim()) || 
                         (mainSearchInput && mainSearchInput.value.trim()) || "";
    panelPassageText.innerHTML = highlightTextKeyword(rawPassageText, currentQuery, "passage-highlight");
  }

  // [좌측 하단]: HWP 정답 및 해설 / FELS 교사용 텍스트
  if (isListening) {
    const rawFels = p.fels_text || "FELS 데이터가 아직 생성되지 않았습니다.";
    panelExplanation.dataset.rawFels = rawFels;

    let formattedFels = escapeHtml(rawFels);
    formattedFels = formattedFels.replace(
      /(?:&lt;|\[)([^&\]\n]+?)(?:&gt;|\])/g,
      (match, p1) => {
        const word = (p1 || "").trim();
        return word ? `<span class="fels-tag-word">[${word}]</span>` : match;
      }
    );
    formattedFels = formattedFels.replace(
      /(^|\n)\s*(M|W|Man|Woman|Boy|Girl|남|여)\s*:\s*/g,
      (match, p1, speaker) => {
        const isMale = /^(M|Man|Boy|남)$/i.test(speaker);
        const cls = isMale ? "speaker-tag speaker-male" : "speaker-tag speaker-female";
        return `${p1}<span class="${cls}">${speaker}:</span> `;
      }
    );

    panelExplanation.innerHTML = `
      <div class="listening-fels-container">
        <div class="fels-guide-banner" style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px;">
          <div style="display: flex; align-items: center; gap: 6px;">
            <span class="fels-badge-icon">🎯</span>
            <span><strong>FELS 기능어 약형드랩:</strong> 7대 기능어가 [단어]로 추출되었습니다. 용도에 맞게 선택하여 복사하세요:</span>
          </div>
          <div style="display: flex; gap: 6px; align-items: center;">
            <button type="button" class="btn btn-primary btn-xs" id="btnBannerCopyBlank" style="font-size: 0.76rem; font-weight: 700; padding: 3px 10px; border-radius: 5px; cursor: pointer;">
              📝 학생용 빈칸 복사 ([ ])
            </button>
            <button type="button" class="btn btn-secondary btn-xs" id="btnBannerCopyAnswer" style="font-size: 0.76rem; font-weight: 700; padding: 3px 10px; border-radius: 5px; cursor: pointer;">
              🔑 교사용 정답 복사 ([단어])
            </button>
          </div>
        </div>
        <div class="fels-content-box">
          ${formattedFels}
        </div>
      </div>
    `;

    // 인라인 FELS 복사 버튼 이벤트 연결
    const bBlank = panelExplanation.querySelector("#btnBannerCopyBlank");
    if (bBlank) bBlank.addEventListener("click", copyFelsBlankVersion);
    const bAnswer = panelExplanation.querySelector("#btnBannerCopyAnswer");
    if (bAnswer) bAnswer.addEventListener("click", copyFelsAnswerVersion);
  } else {
    panelExplanation.textContent = p.explanation_text || "해설 정보가 등록되지 않았습니다.";
  }

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
  if (btnRecapturePdf) btnRecapturePdf.disabled = false;
  if (btnEditAnswer) btnEditAnswer.style.display = "inline-flex";
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

/** 단일 지문의 choice_rates 객체 파싱 헬퍼 */
function parseChoiceRatesObj(p) {
  if (!p) return null;
  if (p.choice_rates_obj && typeof p.choice_rates_obj === "object") {
    return p.choice_rates_obj;
  }
  if (p.choice_rates) {
    if (typeof p.choice_rates === "object") return p.choice_rates;
    if (typeof p.choice_rates === "string") {
      try {
        return JSON.parse(p.choice_rates);
      } catch (e) {
        return null;
      }
    }
  }
  return null;
}

/** 5개 선지 게이지 바 HTML 생성 헬퍼 */
function renderSingleQuestionBars(ratesObj, answerText) {
  if (!ratesObj || (!ratesObj["1"] && !ratesObj["2"] && !ratesObj["3"] && !ratesObj["4"] && !ratesObj["5"])) {
    return `<div class="choice-sub-empty-msg">선지 선택률 데이터가 등록되지 않았습니다.</div>`;
  }

  const circleSymbols = { "1": "①", "2": "②", "3": "③", "4": "④", "5": "⑤" };
  const circleToNum = { "①": "1", "②": "2", "③": "3", "④": "4", "⑤": "5", "1": "1", "2": "2", "3": "3", "4": "4", "5": "5" };
  const ansRaw = (answerText || "").trim();
  const correctAnsNum = circleToNum[ansRaw] || "";

  const attractiveWrong = ratesObj.attractive_wrong;
  const attractiveChoice = attractiveWrong ? String(attractiveWrong.choice) : "";

  let rowsHtml = "";
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

    rowsHtml += `
      <div class="${rowClass}">
        <div class="choice-label-badge">
          <span class="choice-num-circle">${circleSym}</span>
          ${tagHtml}
        </div>
        <div class="choice-progress-wrapper" title="${circleSym} 선택률: ${val.toFixed(1)}%${count !== null ? ` (${count.toLocaleString()}명)` : ''}">
          <div class="choice-progress-fill" style="width: ${Math.min(100, Math.max(0, val))}%;"></div>
        </div>
        <div class="choice-percent-val">
          <strong>${val.toFixed(1)}%</strong>
          ${countLabel}
        </div>
      </div>
    `;
  }
  return `<div class="choice-bars-sublist" style="display: flex; flex-direction: column; gap: 0.35rem;">${rowsHtml}</div>`;
}

export function renderChoiceRates(p) {
  if (!choiceRatesContainer) return;
  if (!p) return;

  // 단일 갱신 시 현재 상세가 복합 지문이면 복합 지문 컨텍스트 유지
  let targetP = p;
  if ((!p.isGroup || !p.subItems) && currentDetailPassage && currentDetailPassage.isGroup && Array.isArray(currentDetailPassage.subItems)) {
    currentDetailPassage.subItems = currentDetailPassage.subItems.map((si) => (si.id === p.id ? { ...si, ...p } : si));
    targetP = currentDetailPassage;
  }

  const isMultiQuestion = !!(targetP.isGroup && Array.isArray(targetP.subItems) && targetP.subItems.length > 1);

  // 1. 메타 정답률 배지 렌더링 (단일 문항 vs 1지문 다문항 문항별 배지)
  if (metaCorrectRate) {
    if (isMultiQuestion) {
      metaCorrectRate.innerHTML = `
        <div class="meta-multi-rates-wrapper">
          ${targetP.subItems.map((si) => {
            const r = (si.correct_rate !== null && si.correct_rate !== undefined) ? parseFloat(si.correct_rate) : null;
            const d = getDifficultyInfo(r);
            const badgeHtml = r !== null
              ? `<span class="${d.badgeClass}" title="${si.q_num}번 정답률 ${r.toFixed(1)}%">${r.toFixed(1)}%</span>`
              : `<span class="badge-rate-none">미등록</span>`;
            return `<span class="meta-multi-rate-item">
              <strong style="color: #475569; font-size: 0.80rem;">${si.q_num}번:</strong> ${badgeHtml}
            </span>`;
          }).join("")}
        </div>
      `;
    } else {
      const rate = (targetP.correct_rate !== null && targetP.correct_rate !== undefined) ? parseFloat(targetP.correct_rate) : null;
      const diff = getDifficultyInfo(rate);
      if (rate !== null) {
        metaCorrectRate.innerHTML = `<span class="${diff.badgeClass}" title="정답률 ${rate.toFixed(1)}%">${rate.toFixed(1)}%</span>`;
      } else {
        metaCorrectRate.innerHTML = `<span class="badge-rate-none">미등록</span>`;
      }
    }
  }

  // 2. 1지문 다문항 복합 처리
  if (isMultiQuestion) {
    const subItems = targetP.subItems;
    const hasAnyRates = subItems.some((si) => {
      const ro = parseChoiceRatesObj(si);
      return ro && (ro["1"] || ro["2"] || ro["3"] || ro["4"] || ro["5"]);
    });

    if (!hasAnyRates) {
      if (choiceBarsList) choiceBarsList.innerHTML = "";
      if (choiceRatesStatsSub) choiceRatesStatsSub.textContent = "복합 문항 정답률 데이터가 등록되지 않았습니다.";
      if (passageDifficultyBadge) {
        passageDifficultyBadge.className = "choice-rates-difficulty-badge badge-rate-none";
        passageDifficultyBadge.style.background = "";
        passageDifficultyBadge.style.color = "";
        passageDifficultyBadge.style.border = "";
        passageDifficultyBadge.textContent = "미등록";
      }
      if (choiceRatesEmpty) choiceRatesEmpty.style.display = "flex";
      return;
    }

    if (choiceRatesEmpty) choiceRatesEmpty.style.display = "none";

    // 총 응시자 수 표기
    const totalCount = subItems.map((si) => parseChoiceRatesObj(si)?.counts?.total).find(Boolean);
    if (choiceRatesStatsSub) {
      choiceRatesStatsSub.textContent = totalCount ? `총 응시자 ${totalCount.toLocaleString()}명 기준 · 문항별 선지 선택률` : `문항별 선지 선택률`;
    }
    if (passageDifficultyBadge) {
      passageDifficultyBadge.className = "choice-rates-difficulty-badge";
      passageDifficultyBadge.style.background = "#eff6ff";
      passageDifficultyBadge.style.color = "#1d4ed8";
      passageDifficultyBadge.style.border = "1px solid #bfdbfe";
      passageDifficultyBadge.textContent = `총 ${subItems.length}문항 복합`;
    }

    if (choiceBarsList) {
      // 상단 문항 전환 탭 + 문항별 개별 카드 렌더링
      const tabsHtml = `
        <div class="choice-multi-q-tabs">
          <button type="button" class="btn-choice-q-pill active" data-q="all">전체 문항 (${subItems.length})</button>
          ${subItems.map((si) => `<button type="button" class="btn-choice-q-pill" data-q="${si.q_num}">${si.q_num}번 문항</button>`).join("")}
        </div>
      `;

      const cardsHtml = subItems.map((si) => {
        const ro = parseChoiceRatesObj(si);
        const r = (si.correct_rate !== null && si.correct_rate !== undefined) ? parseFloat(si.correct_rate) : null;
        const d = getDifficultyInfo(r);

        return `
          <div class="choice-multi-q-card" data-qnum="${si.q_num}">
            <div class="choice-multi-q-card-header">
              <div class="choice-multi-q-card-title">
                <span class="choice-multi-q-badge">📌 ${si.q_num}번 문항</span>
                <span class="choice-rates-difficulty-badge ${d.badgeClass}">${d.label}</span>
              </div>
              <div class="choice-multi-q-card-meta">
                <span class="choice-multi-rate-text">정답률 <strong style="color: ${r !== null && r < 50 ? '#dc2626' : (r !== null && r < 70 ? '#d97706' : '#059669')};">${r !== null ? r.toFixed(1) + '%' : '미등록'}</strong></span>
                <span class="choice-multi-sep">|</span>
                <span class="choice-multi-ans-text">정답 <strong style="color: #059669;">${si.answer_text || '-'}</strong></span>
              </div>
            </div>
            <div class="choice-multi-bars-body">
              ${renderSingleQuestionBars(ro, si.answer_text)}
            </div>
          </div>
        `;
      }).join("");

      choiceBarsList.innerHTML = tabsHtml + cardsHtml;

      // 탭 클릭 필터링 이벤트 바인딩
      const tabBtns = choiceBarsList.querySelectorAll(".btn-choice-q-pill");
      const cards = choiceBarsList.querySelectorAll(".choice-multi-q-card");
      tabBtns.forEach((btn) => {
        btn.addEventListener("click", () => {
          tabBtns.forEach((b) => b.classList.remove("active"));
          btn.classList.add("active");
          const targetQ = btn.dataset.q;
          cards.forEach((card) => {
            if (targetQ === "all" || card.dataset.qnum === targetQ) {
              card.style.display = "block";
            } else {
              card.style.display = "none";
            }
          });
        });
      });
    }
    return;
  }

  // 3. 단일 문항 처리 (기존 로직 유지)
  const rate = (targetP.correct_rate !== null && targetP.correct_rate !== undefined) ? parseFloat(targetP.correct_rate) : null;
  const diff = getDifficultyInfo(rate);

  if (passageDifficultyBadge) {
    passageDifficultyBadge.style.display = "inline-flex";
    passageDifficultyBadge.className = `choice-rates-difficulty-badge ${diff.badgeClass}`;
    passageDifficultyBadge.style.background = "";
    passageDifficultyBadge.style.color = "";
    passageDifficultyBadge.style.border = "";
    passageDifficultyBadge.textContent = diff.label;
  }

  const ratesObj = parseChoiceRatesObj(targetP);
  if (!ratesObj || (!ratesObj["1"] && !ratesObj["2"] && !ratesObj["3"] && !ratesObj["4"] && !ratesObj["5"])) {
    if (choiceBarsList) choiceBarsList.innerHTML = "";
    if (choiceRatesStatsSub) choiceRatesStatsSub.textContent = "정답률 데이터가 등록되지 않았습니다.";
    if (choiceRatesEmpty) choiceRatesEmpty.style.display = "flex";
    return;
  }

  if (choiceRatesEmpty) choiceRatesEmpty.style.display = "none";

  const totalCount = ratesObj.counts?.total;
  if (choiceRatesStatsSub) {
    choiceRatesStatsSub.textContent = totalCount ? `총 응시자 ${totalCount.toLocaleString()}명 기준` : `선지별 선택 비율`;
  }

  if (choiceBarsList) {
    choiceBarsList.innerHTML = renderSingleQuestionBars(ratesObj, targetP.answer_text);
  }
}

function reset2x2ContentPanels() {
  panelPdfImageContainer.innerHTML = `<div class="pdf-placeholder">탐색할 시험 및 문항을 선택하세요.</div>`;
  if (btnRecapturePdf) btnRecapturePdf.disabled = true;
  if (panelTitleTopLeft) panelTitleTopLeft.textContent = "🖼️ PDF 문항 캡처 이미지";
  if (badgeTopLeftSource) badgeTopLeftSource.textContent = "고화질 원본";
  if (panelTitleTopRight) panelTitleTopRight.textContent = "📝 TXT 지문 본문 텍스트";
  if (badgeTopRightSource) badgeTopRightSource.textContent = "순수 영문";
  if (panelTitleBottomLeft) panelTitleBottomLeft.textContent = "📘 HWP 정답 및 해설";
  if (badgeBottomLeftSource) badgeBottomLeftSource.textContent = "공식 해설지";
  if (btnCopyPassage) btnCopyPassage.style.display = "inline-flex";
  if (listeningTopRightActions) listeningTopRightActions.style.display = "none";
  if (btnCopyExplanation) btnCopyExplanation.style.display = "inline-flex";
  if (listeningBottomLeftActions) listeningBottomLeftActions.style.display = "none";

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
    passageDifficultyBadge.style.background = "";
    passageDifficultyBadge.style.color = "";
    passageDifficultyBadge.style.border = "";
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

  /** PDF 문항 캡처 다시 실행 */
  async function handleRecapturePdf() {
    const p = currentDetailPassage;
    if (!p) {
      showToast("선택된 문항이 없습니다. 문항을 먼저 선택해 주세요.", "warning");
      return;
    }
    const targetId = p.id;
    if (btnRecapturePdf) {
      btnRecapturePdf.disabled = true;
      btnRecapturePdf.textContent = "⏳ 캡처 중...";
    }
    showToast(`${p.display_id || p.id} PDF 문항 캡처를 다시 생성하는 중입니다...`, "info");
    try {
      const res = await fetch(`/api/passages/${encodeURIComponent(targetId)}/recapture`, {
        method: "POST",
      });
      const data = await res.json();
      if (!res.ok || !data.success) {
        throw new Error(data.message || data.detail || "PDF 문항 다시 캡처 실패");
      }
      if (Array.isArray(data.passages) && data.passages.length > 0) {
        const updatedMap = new Map(data.passages.map(it => [it.id, it]));
        const flatten = (items) => items.flatMap((it) => (it.isGroup && it.subItems) ? it.subItems : [it]);
        const replaceIn = (items) => flatten(items).map((it) => updatedMap.has(it.id) ? { ...it, ...updatedMap.get(it.id) } : it);
        if (appState.passagesData && appState.passagesData.length) appState.passagesData = groupPassageItems(replaceIn(appState.passagesData));
        if (appState.rawPassagesData && appState.rawPassagesData.length) appState.rawPassagesData = groupPassageItems(replaceIn(appState.rawPassagesData));
        renderPassageView(appState.passagesData, p.id);
      } else if (data.passage) {
        applyPassageUpdate(data.passage, p.id);
      }
      showToast(data.message || "PDF 캡처가 성공적으로 재생성되었습니다.", "success");
    } catch (err) {
      console.error(err);
      showToast(err.message || "PDF 캡처 재생성 중 오류가 발생했습니다.", "error");
    } finally {
      if (btnRecapturePdf) {
        btnRecapturePdf.disabled = false;
        btnRecapturePdf.textContent = "🔄 다시 캡처";
      }
    }
  }

  if (btnRecapturePdf) {
    btnRecapturePdf.addEventListener("click", handleRecapturePdf);
  }

  // PDF placeholder 내부 인라인 다시 캡처 버튼 이벤트 위임
  if (panelPdfImageContainer) {
    panelPdfImageContainer.addEventListener("click", (e) => {
      if (e.target && e.target.closest(".btn-inline-recapture")) {
        handleRecapturePdf();
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

  // 듣기 모드 전용 버튼 이벤트 바인딩
  if (btnCopyFelsBlank) {
    btnCopyFelsBlank.addEventListener("click", copyFelsBlankVersion);
  }
  if (btnCopyFelsAnswer) {
    btnCopyFelsAnswer.addEventListener("click", copyFelsAnswerVersion);
  }
  if (btnCopyFels) {
    btnCopyFels.addEventListener("click", copyFelsBlankVersion);
  }

  if (btnCopyScript) {
    btnCopyScript.addEventListener("click", () => {
      const scText = currentDetailPassage ? (currentDetailPassage.script_text || currentDetailPassage.passage_text || "") : "";
      if (!scText) {
        showToast("복사할 대본 텍스트가 없습니다.", "warning");
        return;
      }
      copyToClipboard(scText, "영문 대본 텍스트가 클립보드에 복사되었습니다!");
    });
  }

  if (btnGenerateListeningAudio) {
    btnGenerateListeningAudio.addEventListener("click", async () => {
      if (!currentDetailPassage) return;
      btnGenerateListeningAudio.disabled = true;
      btnGenerateListeningAudio.textContent = "⏳ 음성 합성 중...";
      try {
        const res = await fetch(`/api/passages/${encodeURIComponent(currentDetailPassage.id)}/generate-audio`, { method: "POST" });
        let resData;
        const contentType = res.headers.get("content-type") || "";
        if (contentType.includes("application/json")) {
          resData = await res.json();
        } else {
          const rawText = await res.text();
          resData = { success: false, message: rawText || `서버 오류 (${res.status})` };
        }

        if (res.ok && resData.success) {
          currentDetailPassage.audio_file_path = resData.audio_url;
          showToast("🎙️ 문항 듣기 음성이 성공적으로 생성되었습니다!", "success");
          const player = document.getElementById("listeningAudioPlayer");
          const chip = document.getElementById("audioStatusChip");
          if (player) {
            player.src = `${resData.audio_url}?t=${Date.now()}`;
            player.load();
          }
          if (chip) {
            chip.className = "audio-status-chip ready";
            chip.textContent = "🎙️ 음성 준비됨";
          }
        } else {
          showToast(resData.detail || resData.message || "음성 합성 실패", "error");
        }
      } catch (e) {
        showToast(`오류 발생: ${e.message}`, "error");
      } finally {
        btnGenerateListeningAudio.disabled = false;
        btnGenerateListeningAudio.textContent = "🎙️ 음성 생성";
      }
    });
  }

  if (btnGenerateAllListeningAudio) {
    btnGenerateAllListeningAudio.addEventListener("click", async () => {
      if (!currentDetailPassage) return;
      if (!confirm(`[${currentDetailPassage.exam_id}] 전체 듣기 문항(1~17번)의 음성을 일괄 생성하시겠습니까?\n\n(Edge-TTS 엔진 선택 시 비용 없이 완전 무료로 생성됩니다)`)) {
        return;
      }
      btnGenerateAllListeningAudio.disabled = true;
      btnGenerateAllListeningAudio.textContent = "⏳ 일괄 합성 진행 중...";
      try {
        const res = await fetch(`/api/exams/${encodeURIComponent(currentDetailPassage.exam_id)}/generate-listening-audio`, { method: "POST" });
        let resData;
        const contentType = res.headers.get("content-type") || "";
        if (contentType.includes("application/json")) {
          resData = await res.json();
        } else {
          const rawText = await res.text();
          resData = { success: false, message: rawText || `서버 오류 (${res.status})` };
        }

        if (res.ok && resData.success) {
          showToast(`🎙️ 전체 듣기 문항 일괄 생성이 완료되었습니다! (성공: ${resData.generated_count || resData.success_count || 0}개)`, "success");
          const freshRes = await fetch(`/api/passages/${encodeURIComponent(currentDetailPassage.id)}`);
          if (freshRes.ok) {
            const freshData = await freshRes.json();
            currentDetailPassage.audio_file_path = freshData.audio_file_path;
            const player = document.getElementById("listeningAudioPlayer");
            const chip = document.getElementById("audioStatusChip");
            if (player && currentDetailPassage.audio_file_path) {
              player.src = `${currentDetailPassage.audio_file_path}?t=${Date.now()}`;
              player.load();
            }
            if (chip && currentDetailPassage.audio_file_path) {
              chip.className = "audio-status-chip ready";
              chip.textContent = "🎙️ 음성 준비됨";
            }
          }
        } else {
          showToast(resData.detail || resData.message || "일괄 합성 실패", "error");
        }
      } catch (e) {
        showToast(`오류 발생: ${e.message}`, "error");
      } finally {
        btnGenerateAllListeningAudio.disabled = false;
        btnGenerateAllListeningAudio.textContent = "🎙️ 전체 일괄 생성";
      }
    });
  }

  if (btnDownloadListeningMp3) {
    btnDownloadListeningMp3.addEventListener("click", () => {
      if (!currentDetailPassage || !currentDetailPassage.audio_file_path) {
        showToast("생성된 음성 파일이 없습니다. [🎙️ 음성 생성]을 먼저 실행해 주세요.", "warning");
        return;
      }
      const a = document.createElement("a");
      a.href = currentDetailPassage.audio_file_path;
      a.download = `${currentDetailPassage.id.replace(/[\[\]]/g, '')}.mp3`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
    });
  }

  if (btnDownloadListeningZip) {
    btnDownloadListeningZip.addEventListener("click", () => {
      if (!currentDetailPassage) return;
      const url = `/api/exams/${encodeURIComponent(currentDetailPassage.exam_id)}/download-listening-zip`;
      window.open(url, "_blank");
    });
  }
}
