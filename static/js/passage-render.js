/**
 * 05-gichul_db: 지문 검색 결과 뷰어 렌더링 모듈 (passage-render.js)
 * - 1행 10문항 탭 바 및 트리 네비게이터 계층 구조 빌더
 * - 45/50문항 체제 및 듣기 복합 지문(1지문 다문항) 동적 통합 엔진
 * - 2x2 그리드 패널(PDF/HWP/대본/FELS/정답) 렌더링
 * - FELS 기능어 약형드랩 서식화(학생용 빈칸/교사용 정답) 및 독백/대화문 판별
 * - 5개 선지 게이지 바, 정답률 및 매력적 오답 시각화
 */

import { appState } from "./state.js";
import {
  answerEditForm,
  badgeBottomLeftSource,
  badgeTopLeftSource,
  badgeTopRightSource,
  breadcrumbTrail,
  breadcrumbExamFiles,
  btnCopyExplanation,
  btnCopyPassage,
  btnCopyScript,
  btnEditAnswer,
  btnRecapturePdf,
  btnToggleFelsAnswer,
  btnTreeChangeExam,
  btnTreeResetExam,
  choiceBarsList,
  choiceRatesContainer,
  choiceRatesEmpty,
  choiceRatesStatsSub,
  emptyResultsBox,
  sentenceEmptyGuidanceBox,
  inputPassageMemo,
  listeningBottomLeftActions,
  listeningTopRightActions,
  mainSearchInput,
  memoCharCount,
  memoStatusBadge,
  memoUpdatedAt,
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
import { hasActiveSearchFilters, highlightTextKeyword, resetAllSearchFilters } from "./search.js";
import { escapeHtml } from "./utils.js";
import { triggerSingleFileUpload } from "./upload.js";
import {
  downloadExamRawFile,
  downloadExamAllZip,
  ensureExamPassagesLoaded,
  examFullPassagesCache,
  fetchExamRawFilesApi,
  updateQuestionTypeApi,
} from "./passage-api.js";
import {
  stopAllListeningAudio,
  applyTtsUiState,
  updateTtsEngineSwitcherState,
  updateListeningZipRangeBadge,
  savePassageMemo,
  getIsMemoDirty,
  clearMemoSaveTimer,
  deletePassageTagAction,
} from "./passage-events.js";

// 모듈 내부 상태
export let currentDetailPassage = null;
export function setCurrentDetailPassage(p) {
  currentDetailPassage = p;
}

export let currentLoadedExamRawFilesId = null;
export function setCurrentLoadedExamRawFilesId(id) {
  currentLoadedExamRawFilesId = id;
}

export let currentFelsViewMode = "blank"; // default: 'blank' (학생용) | 'answer' (교사용)
export function setCurrentFelsViewMode(mode) {
  currentFelsViewMode = mode;
}
export function getCurrentFelsViewMode() {
  return currentFelsViewMode;
}

export let isRecapturingPdf = false;
export function setIsRecapturingPdf(val) {
  isRecapturingPdf = val;
}

export function getCurrentDetailPassage() {
  return getCurrentActivePassage();
}

/** 현재 화면에 표시된 활성 문항 객체 안전 추출 (DOM + appState 다층 검증) */
export function getCurrentActivePassage() {
  // 1. 활성 탭 DOM 요소에서 직접 추출
  const activeTab = passageTabBar ? passageTabBar.querySelector(".passage-q-tab.active") : document.querySelector(".passage-q-tab.active");
  const activeTabId = activeTab ? activeTab.dataset.id : null;
  const activeTabIdx = activeTab && activeTab.dataset.index !== undefined ? parseInt(activeTab.dataset.index, 10) : -1;

  // 2. 현재 열린 시험지의 문항 목록(appState.currentExamQuestions)에서 검색
  if (appState.currentExamQuestions && appState.currentExamQuestions.length > 0) {
    if (activeTabId) {
      const match = appState.currentExamQuestions.find(
        (it) => it.id === activeTabId || (it.all_ids && it.all_ids.includes(activeTabId))
      );
      if (match) return match;
    }
    if (activeTabIdx >= 0 && activeTabIdx < appState.currentExamQuestions.length) {
      return appState.currentExamQuestions[activeTabIdx];
    }
  }

  // 3. appState.currentPassage 싱글톤 확인
  if (appState.currentPassage && (!activeTabId || appState.currentPassage.id === activeTabId || (appState.currentPassage.all_ids && appState.currentPassage.all_ids.includes(activeTabId)))) {
    return appState.currentPassage;
  }

  // 4. 모듈 내부 변수 확인
  if (currentDetailPassage && (!activeTabId || currentDetailPassage.id === activeTabId || (currentDetailPassage.all_ids && currentDetailPassage.all_ids.includes(activeTabId)))) {
    return currentDetailPassage;
  }

  // 5. currentPassageId로 전체 검색
  const targetId = activeTabId || appState.currentPassageId;
  if (targetId && appState.passagesData) {
    const match = appState.passagesData.find(
      (it) => it.id === targetId || (it.all_ids && it.all_ids.includes(targetId))
    );
    if (match) return match;
  }

  return currentDetailPassage || appState.currentPassage || null;
}

const ANSWER_SOURCE_LABELS = {
  uploaded_json: "정답 JSON",
  verified_key: "검증 키 파일",
  csv: "정답률 CSV",
  image_consensus: "이미지 모델 합의",
  image_single: "이미지 단일 모델",
  hwp: "HWP 해설",
  manual: "수동 확정",
  none: "출처 없음",
};

/** 지문 메모 바인딩 */
export function bindPassageMemo(p) {
  if (!inputPassageMemo) return;
  const memoText = p && p.user_memo ? p.user_memo : "";
  inputPassageMemo.value = memoText;

  if (memoCharCount) {
    memoCharCount.textContent = `${memoText.length}자`;
  }
  if (memoStatusBadge) {
    memoStatusBadge.textContent = "저장됨";
    memoStatusBadge.className = "memo-status-badge badge-saved";
  }
  if (memoUpdatedAt) {
    if (p && p.user_memo_updated_at) {
      memoUpdatedAt.textContent = `최근 수정: ${p.user_memo_updated_at}`;
    } else {
      memoUpdatedAt.textContent = "최근 수정: -";
    }
  }
}

// =========================================================================
// 6. [지문 검색 결과] 상단 문항별 탭 & 2x2 그리드 렌더링
// =========================================================================

/**
 * 50문항 체제 시험지에서 발문 및 본문 텍스트를 분석하여 40~50번 복합 지문 그룹을 동적으로 판별
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
    return [[46, 47], [48, 50]];
  }
  if (is3QOrderStart(t46)) {
    return [[46, 47, 48], [49, 50]];
  }

  if (/빈칸\s*\(A\)[,\s]*\(B\)/.test(t46) && /위\s*글/.test(t47)) {
    return [[47, 48], [49, 50]];
  }

  if (has48_49) {
    return [[46, 47], [48, 49]];
  }

  return [[46, 48], [49, 50]];
}

/**
 * 해설 텍스트를 대괄호 섹션 헤더 또는 빈 줄 단위로 의미 블록 분할
 */
function splitExplanationBlocks(text) {
  if (!text) return [];
  const clean = text.replace(/^\[정답\][^\n]*\n*/, "").trim();
  if (!clean) return [];

  const sectionSplitPattern = /(?=(?:^|\n)\s*(?:\[|［)[^\]］\n]+(?:\]|］))/g;
  const rawSections = clean.split(sectionSplitPattern);

  const blocks = [];
  rawSections.forEach((sec) => {
    const s = sec.trim();
    if (!s) return;
    const paras = s.split(/\n\s*\n/);
    paras.forEach((p) => {
      const pt = p.trim();
      if (pt) blocks.push(pt);
    });
  });
  return blocks;
}

/** 블록 간 내용 일치 및 포함 비교를 위한 정규화 */
function normalizeExplanationBlock(text) {
  return (text || "").replace(/\s+/g, " ").trim();
}

/**
 * 1지문 2문항, 1지문 3문항 등 복합 문항의 해설을 각 문항별로 온전하게 결합
 */
function combineGroupExplanations(subItems) {
  if (!subItems || subItems.length === 0) return "";

  const ansParts = subItems.map((si) => `${si.q_num}. ${si.answer_text || "-"}`);
  const combinedAns = `[정답] ` + ansParts.join("   ");

  const seenNormalizedBlocks = new Set();
  const cleanedExps = [];

  subItems.forEach((si, idx) => {
    const raw = si.explanation_text || "";
    const blocks = splitExplanationBlocks(raw);

    const filteredBlocks = [];
    blocks.forEach((b) => {
      const norm = normalizeExplanationBlock(b);
      let isDup = false;

      if (idx > 0) {
        for (const seen of seenNormalizedBlocks) {
          if (norm === seen || (norm.length >= 20 && seen.includes(norm)) || (seen.length >= 20 && norm.includes(seen))) {
            isDup = true;
            break;
          }
        }
      }

      if (!isDup) {
        filteredBlocks.push(b);
        seenNormalizedBlocks.add(norm);
      }
    });

    cleanedExps.push({
      q_num: si.q_num,
      ans: si.answer_text || "-",
      text: filteredBlocks.join("\n\n").trim(),
    });
  });

  const nonEmptyExps = cleanedExps.filter((ce) => ce.text);
  if (nonEmptyExps.length <= 1) {
    const base = nonEmptyExps[0]?.text || "";
    return base ? `${combinedAns}\n\n${base}` : combinedAns;
  }

  const blocks = [combinedAns];
  cleanedExps.forEach((ce) => {
    const t = ce.text || "해설 정보가 등록되지 않았습니다.";
    blocks.push(
      `━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n【 ${ce.q_num}번 해설 】 (정답: ${ce.ans})\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n${t}`
    );
  });

  return blocks.join("\n\n");
}

/** 듣기 영역 1담화 2문항(16~17번, 22~23번 등) 복합 객체 생성 헬퍼 */
function createGroupedListeningItem(subItems, handledIds) {
  const p = subItems[0];
  subItems.forEach((si) => handledIds.add(si.id));

  const gStart = subItems[0].q_num;
  const gEnd = subItems[subItems.length - 1].q_num;
  const rangeLabel = `${gStart}~${gEnd}번`;
  const groupType = `${gStart}-${gEnd}`;

  const examPrefix = p.id.replace(new RegExp(`-${gStart}번?\\]?$`), "").replace(/^\[/, "");
  const ansLabel = subItems.map((si) => `${si.q_num}.${si.answer_text || "-"}`).join(" / ");
  const expText = combineGroupExplanations(subItems);

  const titleList = subItems.map((si) => si.question_title).filter(Boolean);
  const combinedTitle = titleList.length > 0 ? titleList.join(" / ") : `[${rangeLabel}] 다음을 듣고 물음에 답하시오.`;

  const qCropImages = Array.from(new Set(subItems.map((si) => si.pdf_crop_image).filter(Boolean)));
  const sCropImages = Array.from(new Set(subItems.map((si) => si.script_crop_image).filter(Boolean)));

  const scriptText = subItems.map((si) => si.script_text).filter(Boolean)[0] || subItems.map((si) => si.passage_text).filter(Boolean)[0] || "";
  const felsText = subItems.map((si) => si.fels_text).filter(Boolean)[0] || "";
  const audioFilePath = subItems.map((si) => si.audio_file_path).filter(Boolean)[0] || null;

  return {
    ...p,
    area: "listening",
    isGroup: true,
    groupType: groupType,
    q_num_label: rangeLabel,
    display_id: `[${examPrefix}-${rangeLabel}]`,
    all_ids: subItems.map((si) => si.id),
    subItems: subItems,
    question_type: "1담화 2문항",
    question_title: combinedTitle,
    answer_text: ansLabel,
    answer_verified: subItems.every((x) => Number(x.answer_verified) === 1) ? 1 : 0,
    pdf_crop_images: qCropImages,
    pdf_crop_image: qCropImages[0] || p.pdf_crop_image || null,
    script_crop_image: sCropImages[0] || p.script_crop_image || null,
    script_crop_images: sCropImages,
    script_text: scriptText,
    fels_text: felsText,
    audio_file_path: audioFilePath,
    explanation_text: expText,
  };
}

/** 41~42번/43~45번(45문항 체제), 46~48번/49~50번 등(50문항 체제), 및 듣기 16~17번/22~23번 복합 지문을 동적으로 단일 탭으로 병합 */
export function groupPassageItems(rawItems) {
  if (!rawItems || rawItems.length === 0) return [];

  const result = [];
  const handledIds = new Set();

  const examIs50Map = new Map();
  for (let i = 0; i < rawItems.length; i++) {
    const it = rawItems[i];
    if (!it.exam_id) continue;
    if (!examIs50Map.has(it.exam_id)) examIs50Map.set(it.exam_id, false);
    const yMatch = it.exam_id.match(/(\d{4})년/) || (it.year ? [null, it.year] : null);
    const yr = yMatch ? parseInt(yMatch[1], 10) : 0;
    if (yr >= 2014) {
      examIs50Map.set(it.exam_id, false);
    } else if (it.reading_end_q >= 48 || it.q_num >= 46 || (yr >= 2006 && yr <= 2011)) {
      examIs50Map.set(it.exam_id, true);
    }
  }

  const itemMap = new Map();
  for (let i = 0; i < rawItems.length; i++) {
    const it = rawItems[i];
    if (it.exam_id && it.q_num !== undefined) {
      itemMap.set(`${it.exam_id}_${it.q_num}`, it);
      if (it.area) {
        itemMap.set(`${it.area}_${it.exam_id}_${it.q_num}`, it);
      }
    }
  }

  const getItem = (examId, qNum, area) => {
    if (area && itemMap.has(`${area}_${examId}_${qNum}`)) {
      return itemMap.get(`${area}_${examId}_${qNum}`);
    }
    return itemMap.get(`${examId}_${qNum}`);
  };

  const examCompoundGroupsMap = new Map();

  for (let i = 0; i < rawItems.length; i++) {
    const p = rawItems[i];
    if (handledIds.has(p.id)) continue;

    const is50Exam = examIs50Map.get(p.exam_id) || false;

    const isListening =
      p.area === "listening" ||
      p.question_type === "1담화 2문항" ||
      p.question_type === "1담화2문항" ||
      (p.script_text && p.script_text.trim().length > 0) ||
      (p.q_num <= 17 && !is50Exam && p.area !== "reading");

    if (isListening) {
      if (p.q_num === 16) {
        const p17 = getItem(p.exam_id, 17, p.area);
        if (p17) {
          result.push(createGroupedListeningItem([p, p17], handledIds));
          continue;
        }
      }

      if (p.q_num === 22) {
        const p23 = getItem(p.exam_id, 23, p.area);
        if (p23) {
          result.push(createGroupedListeningItem([p, p23], handledIds));
          continue;
        }
      }

      if (p.q_num === 21) {
        const p22 = getItem(p.exam_id, 22, p.area);
        const p23 = getItem(p.exam_id, 23, p.area);
        if (p22 && !p23) {
          const isComp21 =
            p.question_type === "1담화 2문항" ||
            p.question_type === "1담화2문항" ||
            (p.script_text && p22.script_text && p.script_text.trim() === p22.script_text.trim()) ||
            /21\s*[~～\-]\s*22/.test(p.question_title || "");
          if (isComp21) {
            result.push(createGroupedListeningItem([p, p22], handledIds));
            continue;
          }
        }
      }

      if (p.script_text && p.script_text.trim().length > 20) {
        const pNext = getItem(p.exam_id, p.q_num + 1, p.area);
        if (pNext && pNext.script_text && pNext.script_text.trim() === p.script_text.trim()) {
          result.push(createGroupedListeningItem([p, pNext], handledIds));
          continue;
        }
      }
    }

    if (is50Exam) {
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
          const expText = combineGroupExplanations(subItems);
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
            explanation_text: expText,
          });
          continue;
        }
      }
    } else {
      const isSpecial41_43GroupExam =
        (p.exam_id &&
          (p.exam_id.includes("2012년-09월") || p.exam_id.includes("2012년-11월") || p.exam_id.includes("2013년-03월")) &&
          !p.exam_id.includes("B형") &&
          (p.exam_id.includes("고2") || p.subtype === "A형")) ||
        (p.question_type === "1지문3문항" && (p.q_num === 41 || p.q_num === 42 || p.q_num === 43)) ||
        (p.q_num === 44 && (itemMap.get(`${p.exam_id}_41`)?.question_type === "1지문3문항" || p.question_type === "1지문2문항"));

      if (isSpecial41_43GroupExam) {
        if (p.q_num === 41) {
          const p42 = itemMap.get(`${p.exam_id}_42`);
          const p43 = itemMap.get(`${p.exam_id}_43`);
          if (p42 && p43) {
            handledIds.add(p.id);
            handledIds.add(p42.id);
            handledIds.add(p43.id);

            const examPrefix = p.id.replace(/-41번\]$/, "").replace(/^\[/, "");
            const ans41 = p.answer_text || "-";
            const ans42 = p42.answer_text || "-";
            const ans43 = p43.answer_text || "-";
            const ansLabel = `41.${ans41} / 42.${ans42} / 43.${ans43}`;
            const expText41_43 = combineGroupExplanations([p, p42, p43]);

            result.push({
              ...p,
              isGroup: true,
              groupType: "41-43",
              q_num_label: "41~43번",
              display_id: `[${examPrefix}-41~43번]`,
              all_ids: [p.id, p42.id, p43.id],
              subItems: [p, p42, p43],
              question_type: "1지문3문항",
              answer_text: ansLabel,
              answer_verified: [p, p42, p43].every((x) => Number(x.answer_verified) === 1) ? 1 : 0,
              pdf_crop_images: Array.from(new Set([p.pdf_crop_image, p42.pdf_crop_image, p43.pdf_crop_image].filter(Boolean))),
              explanation_text: expText41_43,
            });
            continue;
          }
        }

        if (p.q_num === 44) {
          const p45 = itemMap.get(`${p.exam_id}_45`);
          if (p45) {
            handledIds.add(p.id);
            handledIds.add(p45.id);

            const examPrefix = p.id.replace(/-44번\]$/, "").replace(/^\[/, "");
            const ans44 = p.answer_text || "-";
            const ans45 = p45.answer_text || "-";
            const ansLabel = `44.${ans44} / 45.${ans45}`;
            const expText44_45 = combineGroupExplanations([p, p45]);

            result.push({
              ...p,
              isGroup: true,
              groupType: "44-45",
              q_num_label: "44~45번",
              display_id: `[${examPrefix}-44~45번]`,
              all_ids: [p.id, p45.id],
              subItems: [p, p45],
              question_type: "1지문2문항",
              answer_text: ansLabel,
              answer_verified: [p, p45].every((x) => Number(x.answer_verified) === 1) ? 1 : 0,
              pdf_crop_images: Array.from(new Set([p.pdf_crop_image, p45.pdf_crop_image].filter(Boolean))),
              explanation_text: expText44_45,
            });
            continue;
          }
        }
      }

      if (p.q_num === 41 || (p.question_type === "1지문2문항" && p.q_num === 41)) {
        const p42 = itemMap.get(`${p.exam_id}_42`);
        if (p42) {
          handledIds.add(p.id);
          handledIds.add(p42.id);

          const examPrefix = p.id.replace(/-41번\]$/, "").replace(/^\[/, "");
          const ans41 = p.answer_text || "-";
          const ans42 = p42.answer_text || "-";
          const ansLabel = `41.${ans41} / 42.${ans42}`;
          const expText41_42 = combineGroupExplanations([p, p42]);

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
            explanation_text: expText41_42,
          });
          continue;
        }
      }

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
          const expText43_45 = combineGroupExplanations([p, p44, p45]);

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
            explanation_text: expText43_45,
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
      pdf_crop_images: p.pdf_crop_image ? [p.pdf_crop_image] : [],
    });
  }

  return result;
}

/** 지문 본문이나 문제 텍스트에 오염되어 포함된 정답표/해설 텍스트 블록을 안전하게 잘라냄 */
export function cleanQuestionExplanationLeak(text) {
  if (!text) return "";
  const leakRegex = /(?:^|\n)\s*(?:[^\n]{0,35})?(?:정답\s*(?:및|과)?\s*해설|정답표|정답\s*및\s*풀이|해설\s*및\s*정답|\[\s*출제\s*의도\s*\]|\[\s*해설\s*\])/i;
  const match = text.search(leakRegex);
  if (match !== -1) {
    return text.substring(0, match).trim();
  }
  return text.trim();
}

/** 42번, 44번, 45번 등 복합 지문 하위 문항에서 지문 본문 반복을 제외하고 발문+선지만 추출 */
export function extractQuestionChoicesOnly(text, questionTitle) {
  if (!text) return questionTitle || "";
  const cleaned = cleanQuestionExplanationLeak(text);
  const cIdx = cleaned.indexOf("①");
  if (cIdx !== -1) {
    const choices = cleaned.substring(cIdx).trim();
    return `${questionTitle || ""}\n\n${choices}`.trim();
  }
  return questionTitle || cleaned;
}

/** 지문 객체에서 학년, 년도, 월, 시험 유형, 세부 유형(A형/B형) 추출 */
export function parsePassageHierarchy(p) {
  let grade = p.grade || "";
  let year = p.year ? `${p.year}년` : "";
  let month = p.month ? `${String(p.month).padStart(2, "0")}월` : "";
  let examType = p.exam_type || "";
  let subtype = p.subtype || "";

  const rawId = p.display_id || p.id || "";
  const match = rawId.match(/^\[?([^-]+)-(\d{4}년)-(\d{1,2}월)(?:-([AB]형))?-(.+?)\]?$/i);
  if (match) {
    if (!grade) grade = match[1];
    if (!year) year = match[2];
    if (!month) month = match[3];
    if (!subtype && match[4]) subtype = match[4].toUpperCase();
  }
  if (!subtype) {
    const subMatch = (p.exam_id || rawId).match(/([AB]형)/i);
    if (subMatch) {
      subtype = subMatch[1].toUpperCase();
    }
  }
  if (!grade) grade = "기타";
  if (!year) year = "기타";
  if (!month) month = "기타";

  return { grade, year, month, examType, subtype };
}

/** 전체 지문 목록을 학년 -> 년도 -> 월(및 세부 유형) 계층 트리로 구성 */
export function buildExamTree(items) {
  const tree = {};
  if (!items) return tree;

  items.forEach((p) => {
    const { grade, year, month, examType, subtype } = parsePassageHierarchy(p);
    const monthKey = subtype ? `${month} [${subtype}]` : month;
    if (!tree[grade]) tree[grade] = {};
    if (!tree[grade][year]) tree[grade][year] = {};
    if (!tree[grade][year][monthKey]) {
      tree[grade][year][monthKey] = {
        examType: examType,
        subtype: subtype,
        rawMonth: month,
        items: [],
      };
    }
    tree[grade][year][monthKey].items.push(p);
  });

  return tree;
}

/** 학년 정렬 헬퍼: 3학년 -> 2학년 -> 1학년 내림차순 정렬 (고3 -> 고2 -> 고1) */
export function sortGradesDescending(gradesList) {
  return [...gradesList].sort((a, b) => {
    const numA = parseInt(String(a).replace(/[^0-9]/g, ""), 10) || 0;
    const numB = parseInt(String(b).replace(/[^0-9]/g, ""), 10) || 0;
    if (numB !== numA) {
      return numB - numA;
    }
    return String(b).localeCompare(String(a));
  });
}

/** 년도 정렬 헬퍼: 최신 년도 내림차순 (2026 -> 2025 -> 2024 ...) */
export function sortYearsDescending(yearsList) {
  return [...yearsList].sort((a, b) => {
    const numA = parseInt(String(a).replace(/[^0-9]/g, ""), 10) || 0;
    const numB = parseInt(String(b).replace(/[^0-9]/g, ""), 10) || 0;
    if (numB !== numA) {
      return numB - numA;
    }
    return String(b).localeCompare(String(a));
  });
}

/** 월 정렬 헬퍼: 최신 월 내림차순 (11월 -> 9월 -> 6월 -> 3월 ... 동일 월은 A형 -> B형 순) */
export function sortMonthsDescending(monthsList) {
  return [...monthsList].sort((a, b) => {
    const numA = parseInt(String(a).replace(/[^0-9]/g, ""), 10) || 0;
    const numB = parseInt(String(b).replace(/[^0-9]/g, ""), 10) || 0;
    if (numB !== numA) {
      return numB - numA;
    }
    const isA_a = a.includes("A형");
    const isB_a = a.includes("B형");
    const isA_b = b.includes("A형");
    const isB_b = b.includes("B형");
    if (isA_a && !isA_b) return -1;
    if (!isA_a && isA_b) return 1;
    if (isB_a && !isB_b) return 1;
    if (!isB_a && isB_b) return -1;
    return String(a).localeCompare(String(b));
  });
}

/** 지문 결과 화면 렌더링 (트리 계층 기반) */
export function renderPassageView(items, targetPassageId = null) {
  stopAllListeningAudio();
  if (!items || items.length === 0) {
    emptyResultsBox.style.display = "flex";
    passageViewContainer.style.display = "none";
    clear2x2Panels();
    return;
  }

  emptyResultsBox.style.display = "none";
  if (sentenceEmptyGuidanceBox) sentenceEmptyGuidanceBox.style.display = "none";
  passageViewContainer.style.display = "flex";

  const tree = buildExamTree(items);
  const grades = sortGradesDescending(Object.keys(tree));

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

  if (targetPassageId) {
    let targetP = items.find((p) => p.id === targetPassageId || (p.all_ids && p.all_ids.includes(targetPassageId)));
    if (!targetP) {
      const qMatch = targetPassageId.match(/-(\d{1,2})번/);
      if (qMatch) {
        const targetQ = parseInt(qMatch[1], 10);
        const idH = parsePassageHierarchy({ id: targetPassageId });
        const normalizeMonth = (m) => parseInt(String(m).replace(/[^0-9]/g, ""), 10) || 0;
        const normalizeYear = (y) => parseInt(String(y).replace(/[^0-9]/g, ""), 10) || 0;
        targetP =
          items.find((p) => {
            const ph = parsePassageHierarchy(p);
            const sameExam =
              (!idH.grade || ph.grade === idH.grade) &&
              (!idH.year || normalizeYear(ph.year) === normalizeYear(idH.year)) &&
              (!idH.month || normalizeMonth(ph.month) === normalizeMonth(idH.month)) &&
              (!idH.subtype || ph.subtype === idH.subtype);
            if (!sameExam) return false;
            if (p.q_num === targetQ) return true;
            if (p.subItems && p.subItems.some((s) => s.q_num === targetQ)) return true;
            return false;
          }) ||
          items.find((p) => {
            const ph = parsePassageHierarchy(p);
            return (
              (!idH.grade || ph.grade === idH.grade) &&
              (!idH.year || normalizeYear(ph.year) === normalizeYear(idH.year)) &&
              (!idH.month || normalizeMonth(ph.month) === normalizeMonth(idH.month)) &&
              (!idH.subtype || ph.subtype === idH.subtype)
            );
          });
      }
    }
    if (targetP) {
      const h = parsePassageHierarchy(targetP);
      appState.treeNavState.grade = h.grade;
      appState.treeNavState.year = h.year;
      appState.treeNavState.month = h.subtype ? `${h.month} [${h.subtype}]` : h.month;
    }
  } else if (totalExamsCount === 1 && singleExamCombo) {
    appState.treeNavState.grade = singleExamCombo.grade;
    appState.treeNavState.year = singleExamCombo.year;
    appState.treeNavState.month = singleExamCombo.month;
  } else {
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

  updateTreeUI(tree, items, totalExamsCount, targetPassageId);
}

/** 트리 단계에 따라 상위 선택기 / 최하위 문항 1행 10개 탭 전환 */
export function updateTreeUI(tree, allItems, totalExamsCount, targetPassageId = null) {
  stopAllListeningAudio();
  const grades = sortGradesDescending(Object.keys(tree));

  renderBreadcrumb(tree, allItems, totalExamsCount);

  // Case 1: 학년 미선택 상태
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

  // Case 2: 학년 선택됨, 년도 미선택 상태
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

  // Case 3: 학년과 년도 선택됨, 월 미선택 상태
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

  // Case 4: 학년, 년도, 월 모두 선택 완료
  treeStepSelector.style.display = "none";
  passageTabBar.style.display = "grid";

  let examData = tree[appState.treeNavState.grade]?.[appState.treeNavState.year]?.[appState.treeNavState.month];
  if (!examData && tree[appState.treeNavState.grade]?.[appState.treeNavState.year]) {
    const curM = String(appState.treeNavState.month || "");
    const mNum = parseInt(curM.replace(/[^0-9]/g, ""), 10);
    const mKeys = Object.keys(tree[appState.treeNavState.grade][appState.treeNavState.year]);
    const matchedM =
      mKeys.find((k) => k === curM) ||
      mKeys.find((k) => (curM.includes("B형") ? k.includes("B형") : curM.includes("A형") ? k.includes("A형") : false)) ||
      mKeys.find((k) => parseInt(String(k).replace(/[^0-9]/g, ""), 10) === mNum);
    if (matchedM) {
      appState.treeNavState.month = matchedM;
      examData = tree[appState.treeNavState.grade][appState.treeNavState.year][matchedM];
    }
  }
  appState.currentExamQuestions = examData && examData.items ? examData.items : [];

  renderPassageTabs(appState.currentExamQuestions);

  let activeIdx = 0;
  if (targetPassageId) {
    let fIdx = appState.currentExamQuestions.findIndex(
      (p) => p.id === targetPassageId || (p.all_ids && p.all_ids.includes(targetPassageId))
    );
    if (fIdx < 0) {
      const qMatch = targetPassageId.match(/-(\d{1,2})번/);
      if (qMatch) {
        const targetQ = parseInt(qMatch[1], 10);
        fIdx = appState.currentExamQuestions.findIndex((p) => {
          if (p.q_num === targetQ) return true;
          if (p.subItems && p.subItems.some((s) => s.q_num === targetQ)) return true;
          return false;
        });
      }
    }
    if (fIdx >= 0) activeIdx = fIdx;
  }
  selectPassageTab(activeIdx, appState.currentExamQuestions);

  const curEid =
    (appState.currentExamQuestions && appState.currentExamQuestions[0]?.exam_id) ||
    (examData && examData.items && examData.items[0]?.exam_id);
  if (curEid) {
    renderBreadcrumbExamFiles(curEid);
  }
}

/** 인라인 브레드크럼 바 렌더링 */
export function renderBreadcrumb(tree, allItems, totalExamsCount) {
  if (!breadcrumbTrail) return;

  let trailHtml = "";
  const isExamSelected = !!(appState.treeNavState.grade && appState.treeNavState.year && appState.treeNavState.month);

  if (isExamSelected) {
    let examData = tree[appState.treeNavState.grade]?.[appState.treeNavState.year]?.[appState.treeNavState.month];
    if (!examData && tree[appState.treeNavState.grade]?.[appState.treeNavState.year]) {
      const curM = String(appState.treeNavState.month || "");
      const mNum = parseInt(curM.replace(/[^0-9]/g, ""), 10);
      const mKeys = Object.keys(tree[appState.treeNavState.grade][appState.treeNavState.year]);
      const matchedM =
        mKeys.find((k) => k === curM) ||
        mKeys.find((k) => (curM.includes("B형") ? k.includes("B형") : curM.includes("A형") ? k.includes("A형") : false)) ||
        mKeys.find((k) => parseInt(String(k).replace(/[^0-9]/g, ""), 10) === mNum);
      if (matchedM) {
        appState.treeNavState.month = matchedM;
        examData = tree[appState.treeNavState.grade][appState.treeNavState.year][matchedM];
      }
    }
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

    let currentExamId =
      examData?.items?.[0]?.exam_id ||
      appState.currentExamQuestions?.[0]?.exam_id ||
      currentDetailPassage?.exam_id ||
      null;
    if (!currentExamId && appState.treeNavState.grade && appState.treeNavState.year && appState.treeNavState.month) {
      const g = appState.treeNavState.grade;
      const y = appState.treeNavState.year.includes("년") ? appState.treeNavState.year : `${appState.treeNavState.year}년`;
      const mClean = appState.treeNavState.month;
      const subMatch = mClean.match(/\[([AB]형)\]/i);
      const mNum = parseInt(mClean.replace(/[^0-9]/g, ""), 10);
      const mStr = `${String(mNum).padStart(2, "0")}월`;
      if (subMatch) {
        currentExamId = `[${g}-${y}-${mStr}-${subMatch[1].toUpperCase()}]`;
      } else {
        currentExamId = `[${g}-${y}-${mStr}]`;
      }
    }
    if (currentExamId) {
      renderBreadcrumbExamFiles(currentExamId);
    }
  } else if (appState.treeNavState.grade && appState.treeNavState.year) {
    hideBreadcrumbExamFiles();
    trailHtml = `
        <span class="breadcrumb-item" data-step="grade" title="학년 변경">${escapeHtml(appState.treeNavState.grade)}</span>
        <span class="breadcrumb-separator">&gt;</span>
        <span class="breadcrumb-item active" data-step="year">${escapeHtml(appState.treeNavState.year)}</span>
        <span class="breadcrumb-separator">&gt;</span>
        <span class="breadcrumb-hint">월/시험을 선택하세요</span>
      `;
  } else if (appState.treeNavState.grade) {
    hideBreadcrumbExamFiles();
    trailHtml = `
        <span class="breadcrumb-item active" data-step="grade">${escapeHtml(appState.treeNavState.grade)}</span>
        <span class="breadcrumb-separator">&gt;</span>
        <span class="breadcrumb-hint">년도를 선택하세요</span>
      `;
  } else {
    hideBreadcrumbExamFiles();
    const examSetHint = totalExamsCount ? ` (${totalExamsCount}회차 시험지 세트)` : "";
    trailHtml = `
        <span class="breadcrumb-hint">총 ${allItems.length.toLocaleString()}개 문항${examSetHint} 중 탐색할 학년을 선택하세요</span>
      `;
  }

  breadcrumbTrail.innerHTML = trailHtml;

  breadcrumbTrail.querySelectorAll(".breadcrumb-item").forEach((item) => {
    item.addEventListener("click", () => {
      stopAllListeningAudio();
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
      hideBreadcrumbExamFiles();
      updateTreeUI(tree, allItems, totalExamsCount);
    });
  });

  if (btnTreeResetExam) {
    const hasTreeSelection = !!(appState.treeNavState.grade || appState.treeNavState.year || appState.treeNavState.month);
    const hasActiveFilters = typeof hasActiveSearchFilters === "function" ? hasActiveSearchFilters() : false;
    const shouldShow = hasTreeSelection || hasActiveFilters || totalExamsCount > 1;

    if (shouldShow) {
      btnTreeResetExam.style.display = "inline-flex";
      btnTreeResetExam.onclick = () => {
        stopAllListeningAudio();
        hideBreadcrumbExamFiles();
        if (hasActiveFilters) {
          resetAllSearchFilters(true);
        } else {
          appState.treeNavState.grade = null;
          appState.treeNavState.year = null;
          appState.treeNavState.month = null;
          reset2x2ContentPanels();
          updateTreeUI(tree, allItems, totalExamsCount);
        }
      };
    } else {
      btnTreeResetExam.style.display = "none";
    }
  }

  if (treeBreadcrumbHome) {
    treeBreadcrumbHome.style.cursor = "pointer";
    treeBreadcrumbHome.onclick = () => {
      hideBreadcrumbExamFiles();
      const hasActiveFilters = typeof hasActiveSearchFilters === "function" ? hasActiveSearchFilters() : false;
      if (hasActiveFilters) {
        resetAllSearchFilters(true);
      } else if (appState.treeNavState.grade || appState.treeNavState.year || appState.treeNavState.month) {
        appState.treeNavState.grade = null;
        appState.treeNavState.year = null;
        appState.treeNavState.month = null;
        reset2x2ContentPanels();
        updateTreeUI(tree, allItems, totalExamsCount);
      }
    };
  }

  if (btnTreeChangeExam) {
    if (totalExamsCount > 1 && isExamSelected) {
      btnTreeChangeExam.style.display = "inline-flex";
      btnTreeChangeExam.onclick = () => {
        hideBreadcrumbExamFiles();
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

/** 해당 시험지 5종 원본 파일 다운로드 및 교체 툴바 렌더링 */
export async function renderBreadcrumbExamFiles(examId, forceRefresh = false) {
  if (!examId) return;
  const container = breadcrumbExamFiles || document.getElementById("breadcrumbExamFiles");
  if (!container) return;

  container.style.setProperty("display", "inline-flex", "important");

  if (!forceRefresh && currentLoadedExamRawFilesId === examId && container.querySelector(".exam-file-chip")) {
    return;
  }

  currentLoadedExamRawFilesId = examId;
  container.innerHTML = `<span style="font-size: 0.76rem; color: #64748b; font-weight: 600; padding: 2px 6px;">⏳ 파일 확인 중...</span>`;

  try {
    const data = await fetchExamRawFilesApi(examId);
    renderRawFilesChips(data, examId, container);
  } catch (err) {
    console.error("시험지 원본 파일 현황 조회 실패:", err);
    container.innerHTML = `<span style="font-size: 0.74rem; color: #ef4444; padding: 2px 6px;">⚠️ 통신 오류</span>`;
  }
}

/** 5종 파일 칩 DOM 렌더링 헬퍼 */
function renderRawFilesChips(data, examId, container) {
  const files = data.files || {};

  const fileTypesConfig = [
    { key: "pdf", icon: "📄", label: "문제", extLabel: "PDF" },
    { key: "hwp", icon: "📝", label: "해설", extLabel: "HWP" },
    { key: "script", icon: "📜", label: "대본", extLabel: "PDF" },
    { key: "ans", icon: "🖼️", label: "정답", extLabel: "JSON/PNG" },
    { key: "csv", icon: "📊", label: "정답률", extLabel: "CSV" },
  ];

  let chipsHtml = "";
  let hasAnyFile = false;

  fileTypesConfig.forEach((cfg) => {
    const f = files[cfg.key] || { exists: false, filename: "", size_formatted: "" };
    if (f.exists) hasAnyFile = true;

    const isReady = f.exists;
    const chipClass = isReady ? "is-ready" : "is-missing";
    const titleLabel = `${cfg.label} ${cfg.extLabel}`;
    const dlTitle = isReady
      ? `[다운로드] ${escapeHtml(f.filename)}${f.size_formatted ? ` (${f.size_formatted})` : ""} - 클릭하여 다운로드`
      : `[미등록] ${titleLabel} 파일이 등록되지 않았습니다. 우측 ➕ 버튼을 눌러 등록하세요.`;
    const repTitle = isReady ? `[교체] 새 ${titleLabel} 파일로 교체 업로드` : `[등록] 클릭하여 ${titleLabel} 파일 등록 업로드`;

    chipsHtml += `
      <div class="exam-file-chip ${chipClass}" data-exam-id="${escapeHtml(examId)}" data-file-type="${cfg.key}">
        <button type="button" class="file-chip-btn-download" 
                title="${dlTitle}" 
                ${!isReady ? "disabled" : ""} 
                data-exam-id="${escapeHtml(examId)}" 
                data-file-type="${cfg.key}">
          <span class="file-chip-icon">${cfg.icon}</span>
          <span class="file-chip-title">${titleLabel}</span>
          <span class="file-chip-status-icon">${isReady ? "⬇️" : "✕"}</span>
        </button>
        <span class="file-chip-divider"></span>
        <button type="button" class="file-chip-btn-replace" 
                title="${repTitle}" 
                data-exam-id="${escapeHtml(examId)}" 
                data-file-type="${cfg.key}">
          <span class="file-chip-rep-icon">${isReady ? "🔄" : "➕"}</span>
        </button>
      </div>
    `;
  });

  if (hasAnyFile) {
    chipsHtml += `
      <button type="button" class="btn-exam-zip-download" title="해당 시험지의 등록된 모든 원본 파일 일괄 다운로드 (ZIP)" data-exam-id="${escapeHtml(examId)}">
        📦 ZIP
      </button>
    `;
  }

  container.innerHTML = chipsHtml;

  container.querySelectorAll(".file-chip-btn-download").forEach((btn) => {
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      const eid = btn.dataset.examId;
      const fType = btn.dataset.fileType;
      downloadExamRawFile(eid, fType);
    });
  });

  container.querySelectorAll(".file-chip-btn-replace").forEach((btn) => {
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      const eid = btn.dataset.examId;
      const fType = btn.dataset.fileType;
      triggerSingleFileUpload(eid, fType, btn);
    });
  });

  const btnZip = container.querySelector(".btn-exam-zip-download");
  if (btnZip) {
    btnZip.addEventListener("click", (e) => {
      e.stopPropagation();
      const eid = btnZip.dataset.examId;
      downloadExamAllZip(eid);
    });
  }
}

/** 툴바 숨김 및 초기화 */
export function hideBreadcrumbExamFiles() {
  const container = breadcrumbExamFiles || document.getElementById("breadcrumbExamFiles");
  if (container) {
    container.style.display = "none";
    container.innerHTML = "";
  }
  currentLoadedExamRawFilesId = null;
}

/** 최하위 문항별 탭 생성 */
export function renderPassageTabs(items) {
  passageTabBar.innerHTML = "";
  if (passageTabCount) passageTabCount.textContent = items.length;

  if (items && items.length > 0 && items[0].exam_id && items[0].passage_text === undefined) {
    ensureExamPassagesLoaded(items[0].exam_id, (fresh) => {
      if (currentDetailPassage && currentDetailPassage.id === fresh.id) {
        loadPassageDetail(currentDetailPassage);
      }
    });
  }

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
  stopAllListeningAudio();
  if (getIsMemoDirty()) {
    clearMemoSaveTimer();
    savePassageMemo(true);
  }
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
export function applyPassageUpdate(fresh, focusId) {
  if (!fresh || !fresh.id) return;
  if (fresh.exam_id && examFullPassagesCache.has(fresh.exam_id)) {
    const map = examFullPassagesCache.get(fresh.exam_id);
    if (map.has(fresh.id)) {
      Object.assign(map.get(fresh.id), fresh);
    }
  }
  const flatten = (items) => items.flatMap((it) => (it.isGroup && it.subItems ? it.subItems : [it]));
  const replaceIn = (items) => flatten(items).map((it) => (it.id === fresh.id ? { ...it, ...fresh } : it));
  if (appState.passagesData && appState.passagesData.length) {
    appState.passagesData = groupPassageItems(replaceIn(appState.passagesData));
  }
  if (appState.rawPassagesData && appState.rawPassagesData.length) {
    appState.rawPassagesData = groupPassageItems(replaceIn(appState.rawPassagesData));
  }
  renderPassageView(appState.passagesData, focusId || fresh.id);
}

/**
 * 대본 또는 FELS 텍스트가 대화문(Dialogue)인지 여부 판별 (2중 교차 검증)
 */
export function isDialogueScript(text, title = "", qType = "") {
  const textClean = (text || "").trim();
  const titleClean = (title || "").trim();
  const qTypeClean = (qType || "").trim();

  const hasDialogueTitle = /(?:대화|두\s*사람)/i.test(titleClean);
  let hasMonologueTitle = /(?:다음을\s*듣고|하는\s*말|담화|안내\s*방송|안내문|설명을\s*듣고|이야기를\s*듣고)/i.test(titleClean);
  if (/담화/i.test(qTypeClean)) {
    hasMonologueTitle = true;
  }

  const speakerRegex = /(?:^|\n)\s*(?:[MW]|Man|Woman|Boy|Girl|Male|Female|Teacher|Student|Doctor|Father|Mother|Son|Daughter|Host|Officer)\s*[:：]/gi;
  const matches = textClean.match(speakerRegex);
  const speakerCount = matches ? matches.length : 0;

  if (hasDialogueTitle && speakerCount >= 2) return true;
  if (hasMonologueTitle && speakerCount <= 1) return false;
  if (hasDialogueTitle && !hasMonologueTitle) return true;
  if (hasMonologueTitle && !hasDialogueTitle) return false;
  return speakerCount >= 2;
}

/**
 * 담화문(Monologue) FELS 또는 대본 텍스트를 문장 단위로 분할
 */
export function splitFelsMonologueIntoSentences(felsText) {
  if (!felsText) return [];

  let body = felsText.trim();
  body = body.replace(/(?:^|\n)\s*(?:[MW]|Man|Woman|Boy|Girl|Host|Speaker|Teacher|Doctor|Officer|Male|Female|남|여)\d*\s*[:：]\s*/gi, " ").trim();

  let cleaned = body.replace(/[\r\n]+/g, " ").replace(/[ \t]+/g, " ").trim();

  cleaned = cleaned.replace(/(\d+)\.(\d+)/g, "$1<PERIOD>$2");
  const abbrRegex = /\b(mr|mrs|ms|dr|prof|sr|jr|e\.g|i\.e|etc|vs|u\.s|u\.k|no)\./gi;
  cleaned = cleaned.replace(abbrRegex, (m) => m.replace(/\./g, "<PERIOD>"));
  cleaned = cleaned.replace(/\b([A-Za-z])\.\s+/g, "$1<PERIOD> ");
  cleaned = cleaned.replace(/\.{2,}/g, "<ELLIPSIS>");

  const splitPattern = /([.?!]["')\]]?)\s+(?=[A-Z"'(0-9]|\[|<)/g;

  const rawSentences = [];
  let lastIndex = 0;
  let match;
  while ((match = splitPattern.exec(cleaned)) !== null) {
    const endPos = match.index + match[1].length;
    const sent = cleaned.slice(lastIndex, endPos).trim();
    if (sent) rawSentences.push(sent);
    lastIndex = match.index + match[0].length;
  }
  const remaining = cleaned.slice(lastIndex).trim();
  if (remaining) rawSentences.push(remaining);

  return rawSentences.map((s, idx) => {
    const restored = s.replace(/<PERIOD>/g, ".").replace(/<ELLIPSIS>/g, "...");
    return `${idx + 1}. ${restored}`;
  });
}

/**
 * 대화문(Dialogue) 텍스트의 각 턴에 화자별 순번(M1:, W1:, M2:, W2: ...) 부여
 */
export function numberDialogueTurns(text) {
  if (!text) return "";
  const lines = text.split("\n");
  let mCount = 0;
  let wCount = 0;
  const numberedLines = [];

  for (let line of lines) {
    const trimmed = line.trim();
    if (!trimmed) continue;

    const mMatch = trimmed.match(/^([MW]|Man|Woman|Boy|Girl|Male|Female|남|여)\d*\s*[:：]\s*(.*)$/i);
    if (mMatch) {
      const spk = mMatch[1];
      const rest = mMatch[2].trim();
      const isMale = /^(M|Man|Boy|Male|남)$/i.test(spk);
      let label = "";
      if (isMale) {
        mCount++;
        label = `M${mCount}:`;
      } else {
        wCount++;
        label = `W${wCount}:`;
      }
      numberedLines.push(`${label} ${rest}`);
    } else {
      numberedLines.push(trimmed);
    }
  }

  return numberedLines.join("\n");
}

/**
 * FELS 텍스트를 학생용(blank) 또는 교사용(answer) 규격으로 서식화
 */
export function formatFelsText(felsText, mode = "blank", title = "", qType = "") {
  if (!felsText) return "";

  const isDialogue = isDialogueScript(felsText, title, qType);

  let structuredText = "";
  if (isDialogue) {
    structuredText = numberDialogueTurns(felsText);
  } else {
    const sentences = splitFelsMonologueIntoSentences(felsText);
    structuredText = sentences.join("\n");
  }

  const matches = Array.from(felsText.matchAll(/<([^>]+?)>|\[([^\]]+?)\]/g));
  const words = matches
    .map((m) => (m[1] || m[2] || "").trim())
    .filter((w) => w.length > 0);
  let maxLen = 0;
  for (const w of words) {
    if (w.length > maxLen) maxLen = w.length;
  }
  if (maxLen === 0) maxLen = 5;

  if (mode === "blank") {
    const blankStr = `[${" ".repeat(maxLen)}]`;
    return structuredText.replace(/<([^>]+?)>|\[([^\]]+?)\]/g, (match, p1, p2) => {
      const content = (p1 || p2 || "").trim();
      return content ? blankStr : match;
    });
  } else {
    return structuredText.replace(/<([^>]+?)>/g, "[$1]");
  }
}

/** FELS 좌측 하단 패널 렌더링 */
export function renderFelsBottomLeftPanel(p, viewMode = currentFelsViewMode) {
  if (!p) return;
  currentFelsViewMode = viewMode;
  const isListening = p.area === "listening";
  if (!isListening) return;

  const rawFels = (p.fels_text || "FELS 데이터가 아직 생성되지 않았습니다.").trim();
  panelExplanation.dataset.rawFels = rawFels;

  if (viewMode === "blank") {
    if (panelTitleBottomLeft) panelTitleBottomLeft.textContent = "🎯 FELS (기능어 약형드랩)";
    if (badgeBottomLeftSource) badgeBottomLeftSource.textContent = "학생용 빈칸";
    if (btnToggleFelsAnswer) {
      btnToggleFelsAnswer.innerHTML = "👁️ 정답 보기";
      btnToggleFelsAnswer.className = "btn btn-outline-success btn-sm";
      btnToggleFelsAnswer.title = "교사용 정답([단어]) 화면 보기로 전환";
    }
  } else {
    if (panelTitleBottomLeft) panelTitleBottomLeft.textContent = "🎯 FELS (기능어 약형드랩)";
    if (badgeBottomLeftSource) badgeBottomLeftSource.textContent = "교사용 정답";
    if (btnToggleFelsAnswer) {
      btnToggleFelsAnswer.innerHTML = "🙈 정답 숨기기";
      btnToggleFelsAnswer.className = "btn btn-outline-warning btn-sm";
      btnToggleFelsAnswer.title = "학생용 빈칸([   ]) 화면 보기로 전환";
    }
  }

  const structuredText = formatFelsText(rawFels, viewMode, p.question_title || "", p.question_type || "");
  let formattedFels = escapeHtml(structuredText);

  formattedFels = formattedFels.replace(/\[(\s+)\]/g, '<span class="fels-blank-box">[$1]</span>');

  formattedFels = formattedFels.replace(/(?:&lt;|\[)([^&\]\n\s]+?)(?:&gt;|\])/g, (match, p1) => {
    const word = (p1 || "").trim();
    return word ? `<span class="fels-tag-word">[${word}]</span>` : match;
  });

  formattedFels = formattedFels.replace(/(^|\n)\s*(M\d*|W\d*|Man|Woman|Boy|Girl|남|여)\s*:\s*/g, (match, p1, speaker) => {
    const isMale = /^(M\d*|Man|Boy|남)$/i.test(speaker);
    const cls = isMale ? "speaker-tag speaker-male" : "speaker-tag speaker-female";
    return `${p1}<span class="${cls}">${speaker}:</span> `;
  });

  formattedFels = formattedFels.replace(/(^|\n)\s*(\d+\.)\s+/g, '$1<span class="fels-sent-num">$2</span> ');
  formattedFels = formattedFels.trim();

  const guideBannerHtml =
    viewMode === "blank"
      ? `<span><strong>FELS 기능어 약형드랩 (학생용):</strong> 7대 기능어가 최장 단어 글자수 기준 균일 빈칸([        ])으로 처리되었습니다. 상단의 <strong>[👁️ 정답 보기]</strong> 버튼으로 정답을 확인할 수 있습니다.</span>`
      : `<span><strong>FELS 기능어 약형드랩 (교사용):</strong> 7대 기능어가 [단어]로 추출되었습니다. 상단의 <strong>[🙈 정답 숨기기]</strong> 버튼으로 학생용 빈칸으로 전환할 수 있습니다.</span>`;

  panelExplanation.innerHTML = `
    <div class="listening-fels-container">
      <div class="fels-guide-banner" style="display: flex; align-items: center; gap: 8px; padding: 6px 12px; background: ${
        viewMode === "blank" ? "#f0f9ff" : "#f0fdf4"
      }; border-bottom: 1px solid ${viewMode === "blank" ? "#bae6fd" : "#bbf7d0"}; font-size: 0.8rem; color: ${
        viewMode === "blank" ? "#0369a1" : "#166534"
      };">
        <span class="fels-badge-icon">${viewMode === "blank" ? "📝" : "🎯"}</span>
        ${guideBannerHtml}
      </div>
      <div class="fels-content-box">${formattedFels}</div>
    </div>
  `;
}

/** 2x2 패널에 특정 지문 상세 정보 로드 */
export function loadPassageDetail(p) {
  if (!p) return;

  if (p.exam_id && examFullPassagesCache.has(p.exam_id)) {
    const cachedMap = examFullPassagesCache.get(p.exam_id);
    const cachedItem = cachedMap.get(p.id);
    if (cachedItem) {
      Object.assign(p, cachedItem);
    }
    if (p.subItems && p.subItems.length > 0) {
      p.subItems.forEach((sub) => {
        if (cachedMap.has(sub.id)) Object.assign(sub, cachedMap.get(sub.id));
      });
    }
  }

  stopAllListeningAudio();
  currentDetailPassage = p;
  appState.currentPassage = p;
  appState.currentPassageId = p.id;
  setHeaderSlotState("passage");

  // 유인물 보관함 선택 상태 동기화
  import("./handout-cart.js").then((m) => {
    if (m.syncCurrentPassageCheckbox) m.syncCurrentPassageCheckbox();
    if (m.syncExamToggleAllButton) m.syncExamToggleAllButton();
  }).catch(() => {});

  if (p.passage_text === undefined && p.exam_id) {
    ensureExamPassagesLoaded(p.exam_id, (fresh) => {
      if (currentDetailPassage && currentDetailPassage.id === fresh.id) {
        loadPassageDetail(currentDetailPassage);
      }
    });
  }

  const isListening = p.area === "listening";

  if (panelTitleTopLeft) panelTitleTopLeft.textContent = isListening ? "🖼️ 문제 + 📜 대본 캡처 (상하 수직 배열)" : "🖼️ PDF 문항 캡처 이미지";
  if (badgeTopLeftSource) badgeTopLeftSource.textContent = "고화질 원본";
  if (panelTitleTopRight) panelTitleTopRight.textContent = isListening ? "🎧 영문 대본 & 음성" : "📝 TXT 지문 본문 텍스트";

  const copyScriptBtn = document.getElementById("btnCopyScript") || btnCopyScript;
  if (isListening) {
    if (badgeTopRightSource) badgeTopRightSource.style.display = "none";
    if (copyScriptBtn) copyScriptBtn.style.display = "inline-flex";
    updateTtsEngineSwitcherState(appState.ttsEngine);
    updateListeningZipRangeBadge(p);
  } else {
    if (copyScriptBtn) copyScriptBtn.style.display = "none";
    if (badgeTopRightSource) {
      badgeTopRightSource.style.display = "inline-flex";
      badgeTopRightSource.textContent = "순수 영문";
      badgeTopRightSource.classList.remove("badge-engine");
    }
  }
  if (panelTitleBottomLeft) panelTitleBottomLeft.textContent = isListening ? "🎯 FELS (기능어 약형드랩)" : "📘 HWP 정답 및 해설";
  if (badgeBottomLeftSource) badgeBottomLeftSource.textContent = isListening ? "학생용 빈칸" : "공식 해설지";

  if (btnCopyPassage) btnCopyPassage.style.display = isListening ? "none" : "inline-flex";
  if (listeningTopRightActions) listeningTopRightActions.style.display = isListening ? "flex" : "none";

  if (btnCopyExplanation) btnCopyExplanation.style.display = isListening ? "none" : "inline-flex";
  if (listeningBottomLeftActions) listeningBottomLeftActions.style.display = isListening ? "flex" : "none";

  let rawImages =
    p.pdf_crop_images && p.pdf_crop_images.length > 0 ? p.pdf_crop_images : p.pdf_crop_image ? [p.pdf_crop_image] : [];
  rawImages = Array.from(new Set(rawImages.filter(Boolean)));

  const images = rawImages.map((url) => {
    if (!url) return "";
    const sep = url.includes("?") ? "&" : "?";
    return `${url}${sep}t=${Date.now()}`;
  });

  if (isListening) {
    let qCropHtml = "";
    if (images.length === 1) {
      qCropHtml = `<div class="listening-crop-img-wrapper"><img src="${images[0]}" class="pdf-crop-img listening-crop-img" alt="${escapeHtml(
        p.display_id || p.id
      )} 문제지 캡처" title="클릭 시 새 창에서 원본 크기 확대 보기"></div>`;
    } else if (images.length > 1) {
      qCropHtml = `
        <div class="listening-multi-crop-list" style="display: flex; flex-direction: column; gap: 12px; width: 100%;">
          ${images
            .map((imgUrl, i) => {
              const subQ = p.subItems && p.subItems[i] && p.subItems[i].q_num ? `${p.subItems[i].q_num}번 ` : `[${i + 1}] `;
              return `
              <div class="listening-crop-img-wrapper">
                <div style="font-size: 0.82rem; font-weight: 700; color: #334155; margin-bottom: 6px; display: flex; align-items: center; gap: 5px;">
                  <span style="display: inline-block; width: 7px; height: 7px; border-radius: 50%; background: #2563eb;"></span>
                  ${subQ}문제지 캡처
                </div>
                <img src="${imgUrl}" class="pdf-crop-img listening-crop-img" alt="${escapeHtml(p.display_id || p.id)} ${subQ}문제지 캡처" title="클릭 시 새 창에서 원본 크기 확대 보기">
              </div>
            `;
            })
            .join("")}
        </div>
      `;
    } else {
      qCropHtml = `<div class="pdf-placeholder" style="padding: 1.5rem 1rem; min-height: 100px;">🖼️ 문제지 캡처 이미지가 생성되지 않았습니다.</div>`;
    }

    let rawScriptImages = [];
    if (p.isGroup && p.subItems) {
      rawScriptImages = Array.from(new Set(p.subItems.map((si) => si.script_crop_image).filter(Boolean)));
    } else if (p.script_crop_image) {
      rawScriptImages = [p.script_crop_image];
    }
    const scriptImages = rawScriptImages.map((url) => {
      const sep = url.includes("?") ? "&" : "?";
      return `${url}${sep}t=${Date.now()}`;
    });

    let sCropHtml = "";
    if (scriptImages.length === 1) {
      sCropHtml = `<div class="listening-crop-img-wrapper"><img src="${scriptImages[0]}" class="pdf-crop-img listening-crop-img" alt="${escapeHtml(
        p.display_id || p.id
      )} 대본 캡처" title="클릭 시 새 창에서 원본 크기 확대 보기"></div>`;
    } else if (scriptImages.length > 1) {
      sCropHtml = `
        <div class="listening-multi-crop-list" style="display: flex; flex-direction: column; gap: 12px; width: 100%;">
          ${scriptImages
            .map(
              (imgUrl, i) => `
            <div class="listening-crop-img-wrapper">
              <img src="${imgUrl}" class="pdf-crop-img listening-crop-img" alt="${escapeHtml(p.display_id || p.id)} [${i + 1}] 대본 캡처" title="클릭 시 새 창에서 원본 크기 확대 보기">
            </div>
          `
            )
            .join("")}
        </div>
      `;
    } else {
      sCropHtml = `<div class="pdf-placeholder" style="padding: 1.25rem 1rem; min-height: 100px;">
           <div style="font-size: 0.88rem; font-weight: 600; color: #64748b;">📜 대본 크롭 이미지가 아직 등록되지 않았습니다.</div>
           <div style="font-size: 0.78rem; color: #94a3b8; margin-top: 4px;">대본 PDF 파일 또는 해설 PDF 파일을 업로드하면 대본 섹션이 자동 크롭됩니다.</div>
         </div>`;
    }

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
            ${images
              .map(
                (imgUrl, i) => `
              <div class="pdf-multi-item">
                <img src="${imgUrl}" class="pdf-crop-img" alt="${escapeHtml(p.display_id || p.id)} [${i + 1}] 문항 캡처" title="클릭 시 새 창에서 원본 크기 확대 보기">
              </div>
            `
              )
              .join("")}
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
            <button type="button" class="btn-inline-recapture" ${isRecapturingPdf ? "disabled" : ""}>
              ${isRecapturingPdf ? "⏳ 캡처 진행 중..." : "🔄 지금 다시 캡처 실행"}
            </button>
          </div>
        </div>
      `;
  }

  if (isListening) {
    const rawScript = (p.script_text || p.passage_text || "대본 정보가 등록되지 않았습니다.").trim();
    panelPassageText.dataset.rawText = rawScript;

    const currentQuery =
      (resultsSearchInput && resultsSearchInput.value.trim()) || (mainSearchInput && mainSearchInput.value.trim()) || "";

    // 1. 순수 텍스트에 검색어 하이라이트를 먼저 수행 (highlightTextKeyword 내부에서 escapeHtml 처리)
    let formattedScript = currentQuery
      ? highlightTextKeyword(rawScript, currentQuery, "passage-highlight")
      : escapeHtml(rawScript);

    // 2. 이미 이스케이프 및 하이라이트가 완료된 안전한 HTML에 화자 배지 태그(<span>) 적용
    formattedScript = formattedScript.replace(
      /(^|\n)\s*(?:<mark[^>]*>)?(M\d*|W\d*|Man|Woman|Boy|Girl|남|여)(?:<\/mark>)?\s*:\s*/gi,
      (match, p1, speaker) => {
        const isMale = /^(M\d*|Man|Boy|남)$/i.test(speaker);
        const cls = isMale ? "speaker-tag speaker-male" : "speaker-tag speaker-female";
        return `${p1}<span class="${cls}">${speaker.toUpperCase()}:</span> `;
      }
    );
    formattedScript = formattedScript.trim();

    const hasAudio = !!p.audio_file_path;
    const audioSrc = hasAudio ? `${p.audio_file_path}?t=${Date.now()}` : "";

    panelPassageText.innerHTML = `
      <div class="listening-top-right-wrapper">
        <div class="listening-audio-bar">
          <div class="audio-player-row">
            <audio id="listeningAudioPlayer" controls src="${audioSrc}" style="flex: 1; height: 38px; border-radius: 8px;"></audio>
            <span class="audio-status-chip ${hasAudio ? "ready" : "empty"}" id="audioStatusChip">
              ${hasAudio ? "🎙️ 음성 준비됨" : "🎙️ 음성 미생성"}
            </span>
          </div>
        </div>
        <div class="listening-script-text-box">${formattedScript}</div>
      </div>
    `;
    applyTtsUiState();
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
    const currentQuery =
      (resultsSearchInput && resultsSearchInput.value.trim()) || (mainSearchInput && mainSearchInput.value.trim()) || "";
    panelPassageText.innerHTML = highlightTextKeyword(rawPassageText, currentQuery, "passage-highlight");
  }

  if (isListening) {
    if (panelExplanation) panelExplanation.classList.add("fels-panel-content");
    currentFelsViewMode = "blank";
    renderFelsBottomLeftPanel(p, "blank");
  } else {
    if (panelExplanation) panelExplanation.classList.remove("fels-panel-content");
    let expText = p.explanation_text || "";
    if (p.isGroup && Array.isArray(p.subItems) && p.subItems.length > 1) {
      expText = combineGroupExplanations(p.subItems);
    }
    expText = (expText || "").replace(/\n{3,}/g, "\n\n").trim();
    panelExplanation.textContent = expText || "해설 정보가 등록되지 않았습니다.";
  }

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
  if (p && p.exam_id) {
    renderBreadcrumbExamFiles(p.exam_id);
  }
  if (btnRecapturePdf) btnRecapturePdf.disabled = false;
  if (btnEditAnswer) btnEditAnswer.style.display = "inline-flex";
  if (answerEditForm) answerEditForm.style.display = "none";
  if (metaQuestionTitle) metaQuestionTitle.textContent = p.question_title || "-";
  if (validationBadge) {
    if (p.remarks) {
      validationBadge.textContent = p.remarks;
    } else if (p.validation_ratio != null) {
      validationBadge.textContent = `일치율 ${(p.validation_ratio * 100).toFixed(1)}%`;
    } else {
      validationBadge.textContent = "비교 불가";
    }

    const isWarning =
      (p.validation_ratio != null && p.validation_ratio < 0.9) || (p.remarks && p.remarks.includes("검토 필요"));
    const isNone = p.validation_ratio == null && (!p.remarks || p.remarks.includes("비교 불가"));

    if (isWarning) {
      validationBadge.style.color = "var(--danger, #ef4444)";
    } else if (isNone) {
      validationBadge.style.color = "var(--text-muted, #64748b)";
    } else {
      validationBadge.style.color = "var(--success, #10b981)";
    }
  }

  if (selectQuestionType) {
    selectQuestionType.value = p.question_type || "글의목적";
    selectQuestionType.onchange = async () => {
      const newType = selectQuestionType.value;
      try {
        await updateQuestionTypeApi(appState.currentPassageId, newType);
        p.question_type = newType;
        const activeTab = passageTabBar.querySelector(`.passage-q-tab.active .tab-type-tag`);
        if (activeTab) {
          activeTab.textContent = newType;
        }
      } catch (err) {
        console.error(err);
      }
    };
  }

  renderPassageTags(p.tags || []);
  renderChoiceRates(p);
  bindPassageMemo(p);
}

export function getDifficultyInfo(rate) {
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
export function parseChoiceRatesObj(p) {
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
export function renderSingleQuestionBars(ratesObj, answerText) {
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
    const count = ratesObj.counts && ratesObj.counts[chStr] !== undefined ? ratesObj.counts[chStr] : null;

    const isCorrect = chStr === correctAnsNum;
    const isTrap = !isCorrect && chStr === attractiveChoice;

    let rowClass = "choice-bar-row";
    if (isCorrect) rowClass += " choice-correct";
    else if (isTrap) rowClass += " choice-trap";

    let tagHtml = "";
    if (isCorrect) {
      tagHtml = `<span class="choice-star">★ 정답</span>`;
    } else if (isTrap) {
      tagHtml = `<span class="choice-trap-tag">🚨 매력적 오답</span>`;
    }

    const countLabel = count !== null ? `<span class="choice-count-label">(${count.toLocaleString()}명)</span>` : "";

    rowsHtml += `
      <div class="${rowClass}">
        <div class="choice-label-badge">
          <span class="choice-num-circle">${circleSym}</span>
          ${tagHtml}
        </div>
        <div class="choice-progress-wrapper" title="${circleSym} 선택률: ${val.toFixed(1)}%${count !== null ? ` (${count.toLocaleString()}명)` : ""}">
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

  let targetP = p;
  if ((!p.isGroup || !p.subItems) && currentDetailPassage && currentDetailPassage.isGroup && Array.isArray(currentDetailPassage.subItems)) {
    currentDetailPassage.subItems = currentDetailPassage.subItems.map((si) => (si.id === p.id ? { ...si, ...p } : si));
    targetP = currentDetailPassage;
  }

  const isMultiQuestion = !!(targetP.isGroup && Array.isArray(targetP.subItems) && targetP.subItems.length > 1);

  if (metaCorrectRate) {
    if (isMultiQuestion) {
      metaCorrectRate.innerHTML = `
        <div class="meta-multi-rates-wrapper">
          ${targetP.subItems
            .map((si) => {
              const r = si.correct_rate !== null && si.correct_rate !== undefined ? parseFloat(si.correct_rate) : null;
              const d = getDifficultyInfo(r);
              const badgeHtml =
                r !== null
                  ? `<span class="${d.badgeClass}" title="${si.q_num}번 정답률 ${r.toFixed(1)}%">${r.toFixed(1)}%</span>`
                  : `<span class="badge-rate-none">미등록</span>`;
              return `<span class="meta-multi-rate-item">
              <strong style="color: #475569; font-size: 0.80rem;">${si.q_num}번:</strong> ${badgeHtml}
            </span>`;
            })
            .join("")}
        </div>
      `;
    } else {
      const rate = targetP.correct_rate !== null && targetP.correct_rate !== undefined ? parseFloat(targetP.correct_rate) : null;
      const diff = getDifficultyInfo(rate);
      if (rate !== null) {
        metaCorrectRate.innerHTML = `<span class="${diff.badgeClass}" title="정답률 ${rate.toFixed(1)}%">${rate.toFixed(1)}%</span>`;
      } else {
        metaCorrectRate.innerHTML = `<span class="badge-rate-none">미등록</span>`;
      }
    }
  }

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
      const tabsHtml = `
        <div class="choice-multi-q-tabs">
          <button type="button" class="btn-choice-q-pill active" data-q="all">전체 문항 (${subItems.length})</button>
          ${subItems.map((si) => `<button type="button" class="btn-choice-q-pill" data-q="${si.q_num}">${si.q_num}번 문항</button>`).join("")}
        </div>
      `;

      const cardsHtml = subItems
        .map((si) => {
          const ro = parseChoiceRatesObj(si);
          const r = si.correct_rate !== null && si.correct_rate !== undefined ? parseFloat(si.correct_rate) : null;
          const d = getDifficultyInfo(r);

          return `
          <div class="choice-multi-q-card" data-qnum="${si.q_num}">
            <div class="choice-multi-q-card-header">
              <div class="choice-multi-q-card-title">
                <span class="choice-multi-q-badge">📌 ${si.q_num}번 문항</span>
                <span class="choice-rates-difficulty-badge ${d.badgeClass}">${d.label}</span>
              </div>
              <div class="choice-multi-q-card-meta">
                <span class="choice-multi-rate-text">정답률 <strong style="color: ${
                  r !== null && r < 50 ? "#dc2626" : r !== null && r < 70 ? "#d97706" : "#059669"
                };">${r !== null ? r.toFixed(1) + "%" : "미등록"}</strong></span>
                <span class="choice-multi-sep">|</span>
                <span class="choice-multi-ans-text">정답 <strong style="color: #059669;">${si.answer_text || "-"}</strong></span>
              </div>
            </div>
            <div class="choice-multi-bars-body">
              ${renderSingleQuestionBars(ro, si.answer_text)}
            </div>
          </div>
        `;
        })
        .join("");

      choiceBarsList.innerHTML = tabsHtml + cardsHtml;

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

  const rate = targetP.correct_rate !== null && targetP.correct_rate !== undefined ? parseFloat(targetP.correct_rate) : null;
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

export function reset2x2ContentPanels() {
  stopAllListeningAudio();
  panelPdfImageContainer.innerHTML = `<div class="pdf-placeholder">탐색할 시험 및 문항을 선택하세요.</div>`;
  if (btnRecapturePdf) btnRecapturePdf.disabled = true;
  if (panelTitleTopLeft) panelTitleTopLeft.textContent = "🖼️ PDF 문항 캡처 이미지";
  if (badgeTopLeftSource) badgeTopLeftSource.textContent = "고화질 원본";
  if (panelTitleTopRight) panelTitleTopRight.textContent = "📝 TXT 지문 본문 텍스트";
  const copyScriptBtn = document.getElementById("btnCopyScript") || btnCopyScript;
  if (copyScriptBtn) copyScriptBtn.style.display = "none";
  if (badgeTopRightSource) {
    badgeTopRightSource.style.display = "inline-flex";
    badgeTopRightSource.textContent = "순수 영문";
    badgeTopRightSource.classList.remove("badge-engine");
  }
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

export function clear2x2Panels() {
  reset2x2ContentPanels();
  passageTabBar.innerHTML = "";
  if (treeStepSelector) treeStepSelector.innerHTML = "";
  if (breadcrumbTrail) breadcrumbTrail.innerHTML = "";
  if (btnTreeChangeExam) btnTreeChangeExam.style.display = "none";
  if (passageTabCount) passageTabCount.textContent = "0";
}

/** 지문 태그 목록 렌더링 */
export function renderPassageTags(tags) {
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
      await deletePassageTagAction(appState.currentPassageId, tag);
    });

    passageTagsList.appendChild(badge);
  });
}
