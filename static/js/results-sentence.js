/**
 * 05-gichul_db: 전체 문장 보기 · 문장 검색 결과 테이블 · 어법 팝오버 (섹션 7~8) (results-sentence.js)
 * - main.js 에서 분리
 */

import { appState } from "./state.js";
import {
  btnCloseGrammarPopover,
  btnHeaderFlow,
  btnSentenceBackToPassage,
  emptyResultsBox,
  grammarExplanationPopover,
  loadingIndicator,
  mainSearchInput,
  passageViewContainer,
  popoverBadge,
  popoverSource,
  popoverPath,
  popoverPhraseSection,
  popoverPhraseText,
  popoverExplanationText,
  popoverFooter,
  btnAdoptAiToUser,
  resultsSearchInput,
  resultsTabModePassage,
  resultsTabModeSentence,
  resultsTotalCount,
  sentenceEmptyGuidanceBox,
  sentenceMatchCount,
  sentenceTableBody,
  sentenceViewContainer,
  tabModePassage,
  tabModeSentence,
} from "./dom.js";
import { setHeaderSlotState, setMode, updateGrammarFiltersVisibility, updateResultsNavHeight } from "./navigation.js";
import { executeSearch, highlightSentenceKeyword, loadStats } from "./search.js";
import { groupPassageItems, renderPassageView, selectPassageTab, stopAllListeningAudio } from "./results-passage.js";
import { copyToClipboard, cssSafeId, escapeHtml, showToast } from "./utils.js";
import { openGrammarModalForSentence } from "./grammar.js";
import { openSentenceReportModal } from "./reports.js";
import { isInSentenceCart, toggleSentenceCart, addToSentenceCart } from "./handout-cart.js";

// =========================================================================
// 7. [전체 문장 보기] <-> [지문 결과창으로 돌아가기] 연동
// =========================================================================

/** 특정 지문의 전체 문장 결과창을 1행 테이블로 표시 */
export async function showSentencesForPassage(passageId) {
  stopAllListeningAudio();
  if (!passageId) {
    if (appState.currentPassageId) {
      passageId = appState.currentPassageId;
    } else if (appState.currentExamQuestions && appState.currentExamQuestions.length > 0) {
      passageId = appState.currentExamQuestions[appState.currentPassageIndex]?.id;
    }
  }
  if (!passageId) {
    showSentenceEmptyGuidance();
    return;
  }

  if (sentenceEmptyGuidanceBox) sentenceEmptyGuidanceBox.style.display = "none";
  appState.currentPassageId = passageId;
  appState.currentMode = "sentence";
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
    loadingIndicator.style.display = "none";
    appState.sentencesData = data.items || [];
    appState.rawSentencesData = appState.sentencesData;
    resultsTotalCount.textContent = appState.sentencesData.length;
    renderSentenceView(appState.sentencesData);

    // 상단 문장 건수 표시 커스텀 타이틀 반영
    if (sentenceMatchCount) {
      sentenceMatchCount.innerHTML = `<strong>${escapeHtml(passageId)}</strong> 문항 전체 문장 (${appState.sentencesData.length}개)`;
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
export function backToPassageView() {
  stopAllListeningAudio();
  if (sentenceEmptyGuidanceBox) sentenceEmptyGuidanceBox.style.display = "none";
  appState.currentMode = "passage";
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
  if (appState.passagesData && appState.passagesData.length > 0) {
    resultsTotalCount.textContent = appState.passagesData.length;
    let targetIndex = appState.currentPassageIndex;
    if (appState.currentPassageId) {
      const found = appState.passagesData.findIndex(p => p.id === appState.currentPassageId || (p.all_ids && p.all_ids.includes(appState.currentPassageId)));
      if (found >= 0) targetIndex = found;
    }
    if (targetIndex < 0 || targetIndex >= appState.passagesData.length) targetIndex = 0;
    selectPassageTab(targetIndex, appState.passagesData);
  } else if (appState.currentPassageId) {
    navigateToPassageView(appState.currentPassageId);
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
  stopAllListeningAudio();
  const pId = extractPassageId(targetPassageId);
  if (!pId) return;

  appState.currentPassageId = pId;
  appState.currentMode = "passage";
  if (resultsTabModePassage) resultsTabModePassage.classList.add("active");
  if (resultsTabModeSentence) resultsTabModeSentence.classList.remove("active");
  if (tabModePassage) tabModePassage.classList.add("active");
  if (tabModeSentence) tabModeSentence.classList.remove("active");

  sentenceViewContainer.style.display = "none";
  passageViewContainer.style.display = "flex";
  emptyResultsBox.style.display = "none";

  // 1. 현재 passagesData 목록에 해당 지문이 이미 존재하는지 확인
  let idx = -1;
  if (appState.passagesData && appState.passagesData.length > 0) {
    idx = appState.passagesData.findIndex(p => p.id === pId || (p.all_ids && p.all_ids.includes(pId)));
  }

  if (idx >= 0) {
    resultsTotalCount.textContent = appState.passagesData.length;
    setHeaderSlotState("passage");
    renderPassageView(appState.passagesData, pId);
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
      loadingIndicator.style.display = "none";
      if (data.items && data.items.length > 0) {
        appState.passagesData = groupPassageItems(data.items);
        resultsTotalCount.textContent = appState.passagesData.length;
        renderPassageView(appState.passagesData, pId);
        setHeaderSlotState("passage");
        showToast(`${pId} 지문 상세로 이동했습니다.`, "info");
        return;
      }
    }

    // 단일 지문 로드 폴백
    const singleRes = await fetch(`/api/passages/${encodeURIComponent(pId)}`);
    if (singleRes.ok) {
      const singleData = await singleRes.json();
      appState.passagesData = groupPassageItems([singleData]);
      resultsTotalCount.textContent = 1;
      renderPassageView(appState.passagesData, pId);
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
// =========================================================================
// 8. [문장 검색 결과] 1행 테이블 렌더링
// =========================================================================

// 문장 텍스트 형광펜 하이라이트는 상단 정의된 highlightSentenceKeyword(highlightTextKeyword 기반)를 활용

export function getGrammarBadgeClass(pos) {
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
        const isUser = a.source_type === "USER";
        const sourceClass = isUser ? "badge-source-user" : "badge-source-ai";
        const sourceIcon = isUser ? "👤" : "🤖";
        const sourceLabel = isUser ? "사용자 분석" : "AI 분석";
        const identifier = a.id || a.category_id || 0;
        const removeBtn = sentenceId
          ? `<button type="button" class="grammar-remove-btn" data-sent-id="${escapeHtml(sentenceId)}" data-id="${escapeHtml(String(identifier))}" data-source="${escapeHtml(a.source_type || 'AI')}" title="${sourceLabel} 삭제">&times;</button>`
          : "";
        const annoJson = escapeHtml(JSON.stringify(a));
        const tooltipTitle = isUser
          ? `[사용자 직접 분석] ${escapeHtml(a.full_path || '')} (클릭하여 상세 해설 보기)`
          : `[AI 자동 분석 - ${escapeHtml(a.ai_model || 'LLM')}] ${escapeHtml(a.full_path || '')} (클릭하여 상세 해설 보기)`;
        return `<span class="grammar-tag-badge ${badgeClass} ${sourceClass}" data-sent-id="${escapeHtml(sentenceId || '')}" data-idx="${idx}" data-source="${escapeHtml(a.source_type || 'AI')}" data-anno="${annoJson}" title="${tooltipTitle}"><span class="badge-source-icon">${sourceIcon}</span> ${escapeHtml(a.leaf_name || a.pos || "")}${removeBtn}</span>`;
      })
      .join(" ");
  }

  if (grammarAnalyzed === 1 || grammarAnalyzed === true) {
    const removeBtn = sentenceId
      ? `<button type="button" class="grammar-none-remove-btn" data-sent-id="${escapeHtml(sentenceId)}" title="해당사항 없음 초기화 (다시 분석 가능)">&times;</button>`
      : "";
    return `<span class="grammar-badge-none" title="AI 어법 분석이 완료되었으나 검출된 특이 어법 포인트가 없습니다.">✓ 해당사항 없음${removeBtn}</span>`;
  }

  return '<span class="empty-grammar-text" title="아직 AI 어법 분석이 수행되지 않은 문장입니다.">미분석</span>';
}

/** 어법 범주 상세 해설 플로팅 팝오버 닫기 */
function closeGrammarPopover() {
  if (grammarExplanationPopover) {
    grammarExplanationPopover.style.display = "none";
  }
  if (popoverFooter) {
    popoverFooter.style.display = "none";
  }
}

/** 어법 범주 배지 클릭 시 상세 해설 플로팅 팝오버 표시 */
export function showGrammarPopover(anno, targetElement, sentenceObj = null, onUpdateCallback = null) {
  if (!grammarExplanationPopover || !anno || !targetElement) return;

  if (popoverBadge) {
    popoverBadge.className = `grammar-popover-badge ${getGrammarBadgeClass(anno.pos)}`;
    popoverBadge.textContent = `🏷️ ${anno.leaf_name || anno.pos || '어법'}`;
  }

  if (popoverSource) {
    const isUser = anno.source_type === "USER";
    popoverSource.textContent = isUser ? "👤 사용자 분석" : `🤖 AI 분석 (${anno.ai_model || 'LLM'})`;
    popoverSource.style.background = isUser ? "rgba(16, 185, 129, 0.15)" : "rgba(139, 92, 246, 0.15)";
    popoverSource.style.color = isUser ? "#059669" : "#8b5cf6";
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

  // AI 분석 어법인 경우 "내 분석으로 채택(등록)" 버튼 활성화
  if (popoverFooter && btnAdoptAiToUser) {
    if (anno.source_type !== "USER" && sentenceObj && sentenceObj.id) {
      popoverFooter.style.display = "flex";
      btnAdoptAiToUser.onclick = async () => {
        btnAdoptAiToUser.disabled = true;
        btnAdoptAiToUser.textContent = "⏳ 채택 중...";
        try {
          const res = await fetch(`/api/sentences/${encodeURIComponent(sentenceObj.id)}/grammar-annotations`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              category_id: anno.category_id || 0,
              pos: anno.pos || "",
              full_path: anno.full_path || "",
              leaf_name: anno.leaf_name || "",
              target_expression: anno.target_expression || "",
              explanation: `사용자 채택: ${anno.explanation || anno.full_path || ''}`,
              source_type: "USER"
            })
          });
          const data = await res.json();
          if (res.ok && data.success) {
            sentenceObj.grammar_annotations = data.annotations || [];
            sentenceObj.grammar_analyzed = 1;
            if (typeof onUpdateCallback === "function") {
              onUpdateCallback();
            }
            showToast(`'${anno.leaf_name}' 어법이 내 분석으로 채택되었습니다.`, "success");
            closeGrammarPopover();
          } else {
            showToast(data.detail || "채택 등록 실패", "error");
          }
        } catch (err) {
          console.error("Adopt grammar error:", err);
          showToast("내 분석 채택 중 오류가 발생했습니다.", "error");
        } finally {
          btnAdoptAiToUser.disabled = false;
          btnAdoptAiToUser.textContent = "👤 내 분석으로 채택(등록)";
        }
      };
    } else {
      popoverFooter.style.display = "none";
    }
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

/** 단일 문장 결과 행(TR) 생성 및 모든 상호작용 이벤트 바인딩 */
function createSentenceRow(s, currentQuery) {
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

  // 문항 정답률 배지 생성 (문장 결과 테이블에서도 직관적 확인 지원)
  let rateBadgeHtml = "";
  if (s.correct_rate !== null && s.correct_rate !== undefined && s.correct_rate !== "") {
    const rVal = parseFloat(s.correct_rate);
    if (!isNaN(rVal)) {
      let badgeCls = "badge-rate-easy";
      let badgeIcon = "🟢";
      if (rVal < 40.0) { badgeCls = "badge-rate-killer"; badgeIcon = "🔴"; }
      else if (rVal < 60.0) { badgeCls = "badge-rate-hard"; badgeIcon = "🟠"; }
      else if (rVal < 80.0) { badgeCls = "badge-rate-medium"; badgeIcon = "🟡"; }
      rateBadgeHtml = `<span class="choice-rates-difficulty-badge ${badgeCls}" style="font-size: 0.72rem; padding: 0.12rem 0.45rem; line-height: 1.2; display: inline-flex; align-items: center; gap: 3px;" title="문항 정답률: ${rVal.toFixed(1)}%">${badgeIcon} 정답률 ${rVal.toFixed(1)}%</span>`;
    }
  }

  // 검색 표현 형광펜 하이라이트 적용
  const highlightedSentence = highlightSentenceKeyword(s.sentence_text, currentQuery);
  const isStarred = s.is_starred === 1 || s.is_starred === true;
  const inSentenceCart = isInSentenceCart(s.id);

  tr.innerHTML = `
      <td class="col-handout-select" style="text-align: center; vertical-align: middle;">
        <label class="handout-sentence-chk-label ${inSentenceCart ? "checked" : ""}" title="${inSentenceCart ? "현재 프로젝트에서 제외" : "유인물 보관함에 담기"}" style="cursor: pointer; display: inline-flex; align-items: center; justify-content: center;">
          <input type="checkbox" class="handout-sentence-chk" data-id="${escapeHtml(s.id)}" ${inSentenceCart ? "checked" : ""} style="cursor: pointer; width: 15px; height: 15px;">
        </label>
      </td>
      <td class="col-star" style="text-align: center;">
        <button type="button" class="btn-star ${isStarred ? "starred" : ""}" data-id="${escapeHtml(s.id)}" title="${isStarred ? "중요 문장 해제" : "중요 문장(⭐)으로 등록"}">
          ${isStarred ? "★" : "☆"}
        </button>
      </td>
      <td class="col-num">${s.row_num}</td>
      <td class="col-source">
        <div class="source-cell-wrapper">
          <button type="button" class="btn-source-link" data-passage-id="${escapeHtml(targetPassageId)}" title="클릭하여 ${escapeHtml(targetPassageId)} 지문 결과 화면으로 이동">
            🔗 ${escapeHtml(s.id)}
          </button>
          ${rateBadgeHtml}
        </div>
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
          <button class="copy-btn btn-copy-sentence" data-text="${escapeHtml((s.id ? (s.id.startsWith('[') && s.id.endsWith(']') ? s.id : `[${s.id}]`) + ' ' : '') + s.sentence_text)}" title="문장 및 출처 복사">
            📋 복사
          </button>
          <button type="button" class="btn-analyze-inline" data-id="${escapeHtml(s.id)}" title="AI로 어법 포인트 분석">
            🤖 분석
          </button>
          <button type="button" class="btn-edit-sentence-inline" data-id="${escapeHtml(s.id)}" title="이 문장의 텍스트를 직접 수정합니다">
            ✏️ 수정
          </button>
          <button type="button" class="btn-report-sentence-inline" data-id="${escapeHtml(s.id)}" title="이 문장의 오류 신고">
            🚨 신고
          </button>
        </div>
      </td>
    `;

  // 어법 셀 갱신 및 삭제/클릭 이벤트 바인딩
  const updateGrammarCell = () => {
    const container = tr.querySelector(".sentence-grammar-tags");
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
    const container = tr.querySelector(".sentence-grammar-tags");
    if (!container) return;
    container.querySelectorAll(".grammar-remove-btn").forEach((btn) => {
      btn.addEventListener("click", async (e) => {
        e.stopPropagation();
        const identifier = btn.dataset.id;
        if (!identifier) return;
        try {
          let delUrl = `/api/sentences/${encodeURIComponent(s.id)}/grammar-annotations/${encodeURIComponent(identifier)}`;
          if (btn.dataset.source) {
            delUrl += `?source_type=${encodeURIComponent(btn.dataset.source)}`;
          }
          const res = await fetch(delUrl, {
            method: "DELETE"
          });
          const data = await res.json();
          if (res.ok && data.success) {
            s.grammar_annotations = data.annotations || [];
            if (!s.grammar_annotations || s.grammar_annotations.length === 0) {
              s.grammar_analyzed = 0;
            }
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

    // '✓ 해당사항 없음' 배지의 x 버튼 클릭 시 분석 상태 초기화
    container.querySelectorAll(".grammar-none-remove-btn").forEach((btn) => {
      btn.addEventListener("click", async (e) => {
        e.stopPropagation();
        const sentId = btn.dataset.sentId || s.id;
        try {
          const res = await fetch(`/api/sentences/${encodeURIComponent(sentId)}/grammar`, {
            method: "DELETE"
          });
          const data = await res.json();
          if (res.ok && data.success) {
            s.grammar_annotations = [];
            s.grammar_analyzed = 0;
            updateGrammarCell();
            showToast("어법 분석이 초기화되었습니다. 다시 분석할 수 있습니다.", "info");
          } else {
            showToast(data.detail || "초기화 실패", "error");
          }
        } catch (err) {
          console.error("Reset grammar error:", err);
          showToast("어법 분석 초기화 중 오류가 발생했습니다.", "error");
        }
      });
    });
  };

  const bindGrammarBadgeClicks = () => {
    const container = tr.querySelector(".sentence-grammar-tags");
    if (!container) return;
    container.querySelectorAll(".grammar-tag-badge").forEach((badge) => {
      badge.addEventListener("click", (e) => {
        if (e.target.closest(".grammar-remove-btn")) return;
        e.stopPropagation();
        let anno = null;
        if (badge.dataset.anno) {
          try { anno = JSON.parse(badge.dataset.anno); } catch (err) {}
        }
        if (!anno) {
          const idx = parseInt(badge.dataset.idx, 10);
          anno = (s.grammar_annotations && s.grammar_annotations[idx]) ? s.grammar_annotations[idx] : null;
        }
        if (anno) {
          showGrammarPopover(anno, badge, s, () => updateGrammarCell());
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

  // 유인물 담기 체크박스 이벤트
  const chkHandout = tr.querySelector(".handout-sentence-chk");
  if (chkHandout) {
    chkHandout.addEventListener("change", (e) => {
      e.stopPropagation();
      const inCart = toggleSentenceCart(s.id);
      chkHandout.checked = inCart;
      const lbl = chkHandout.closest(".handout-sentence-chk-label");
      if (lbl) {
        lbl.classList.toggle("checked", inCart);
        lbl.title = inCart ? "현재 프로젝트에서 제외" : "유인물 보관함에 담기";
      }
      showToast(inCart ? "문장이 유인물 보관함에 담겼습니다." : "문장이 유인물 보관함에서 제외되었습니다.", inCart ? "success" : "info");
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
          if (data.sentence_text && data.sentence_text !== s.sentence_text) {
            s.sentence_text = data.sentence_text;
            const sentenceDiv = tr.querySelector(".col-sentence > div");
            if (sentenceDiv) {
              sentenceDiv.innerHTML = highlightSentenceKeyword(s.sentence_text, currentQuery);
            }
          }
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

  // 인라인 복사 이벤트 (출처 식별자 + 문장 본문 결합 복사)
  const copyBtn = tr.querySelector(".btn-copy-sentence");
  if (copyBtn) {
    copyBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      const sentId = (s.id || copyBtn.dataset.id || "").trim();
      let sourceText = "";
      if (sentId) {
        sourceText = sentId.startsWith("[") && sentId.endsWith("]") ? sentId : `[${sentId}]`;
      } else if (targetPassageId && s.order_index) {
        sourceText = `[${targetPassageId}-${s.order_index}번째 문장]`;
      }
      const cleanSent = (s.sentence_text || "").trim();
      const textToCopy = sourceText ? `${sourceText} ${cleanSent}` : cleanSent;
      copyToClipboard(textToCopy, `${sourceText ? sourceText + ' ' : ''}문장과 출처가 클립보드에 복사되었습니다! (Ctrl+V)`);
      copyBtn.textContent = "✔ 복사됨";
      copyBtn.classList.add("copied");
      setTimeout(() => {
        copyBtn.innerHTML = "📋 복사";
        copyBtn.classList.remove("copied");
      }, 1500);
    });
  }

  // 인라인 문장 오류 신고 이벤트
  const reportBtn = tr.querySelector(".btn-report-sentence-inline");
  if (reportBtn) {
    reportBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      openSentenceReportModal(s.id, s.sentence_text);
    });
  }

  // 인라인 문장 텍스트 직접 수정 이벤트
  const editBtn = tr.querySelector(".btn-edit-sentence-inline");
  const sentenceCell = tr.querySelector(".col-sentence");
  if (editBtn && sentenceCell) {
    editBtn.addEventListener("click", (e) => {
      e.stopPropagation();

      // 이미 편집 모드라면 내부 텍스트영역 포커스
      if (sentenceCell.querySelector(".sentence-inline-edit-wrapper")) {
        const ta = sentenceCell.querySelector(".sentence-inline-edit-textarea");
        if (ta) ta.focus();
        return;
      }

      const originalHtml = sentenceCell.innerHTML;
      sentenceCell.innerHTML = `
        <div class="sentence-inline-edit-wrapper">
          <textarea class="sentence-inline-edit-textarea" rows="3">${escapeHtml(s.sentence_text)}</textarea>
          <div class="sentence-inline-edit-actions">
            <button type="button" class="btn btn-primary btn-xs btn-save-sentence-edit">💾 저장</button>
            <button type="button" class="btn btn-secondary btn-xs btn-cancel-sentence-edit">취소</button>
            <span class="sentence-inline-edit-hint">Ctrl + Enter 로 저장 / ESC 로 취소</span>
          </div>
        </div>
      `;

      const textarea = sentenceCell.querySelector(".sentence-inline-edit-textarea");
      const saveBtn = sentenceCell.querySelector(".btn-save-sentence-edit");
      const cancelBtn = sentenceCell.querySelector(".btn-cancel-sentence-edit");

      if (textarea) {
        textarea.focus();
        textarea.setSelectionRange(textarea.value.length, textarea.value.length);
      }

      const restoreOriginal = () => {
        sentenceCell.innerHTML = originalHtml;
      };

      const doSave = async () => {
        const newText = (textarea ? textarea.value : "").trim();
        if (!newText) {
          showToast("문장 텍스트는 비워둘 수 없습니다.", "warning");
          if (textarea) textarea.focus();
          return;
        }

        if (newText === s.sentence_text) {
          restoreOriginal();
          return;
        }

        if (saveBtn) {
          saveBtn.disabled = true;
          saveBtn.textContent = "저장 중...";
        }

        try {
          const res = await fetch(`/api/sentences/${encodeURIComponent(s.id)}/text`, {
            method: "PATCH",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ sentence_text: newText }),
          });
          const data = await res.json();
          if (!res.ok || !data.success) {
            throw new Error(data.detail || data.message || "문장 수정에 실패했습니다.");
          }

          s.sentence_text = data.sentence_text;
          s.word_count = data.word_count;

          // 화면 갱신
          sentenceCell.innerHTML = `<div class="sentence-text-content">${highlightSentenceKeyword(s.sentence_text, currentQuery)}</div>`;

          // 복사 버튼 데이터 갱신
          const copyBtn = tr.querySelector(".btn-copy-sentence");
          if (copyBtn) {
            const prefix = s.id ? (s.id.startsWith("[") && s.id.endsWith("]") ? s.id : `[${s.id}]`) + " " : "";
            copyBtn.dataset.text = prefix + s.sentence_text;
          }

          if (s.grammar_analyzed || (s.grammar_annotations && s.grammar_annotations.length > 0)) {
            showToast("문장 텍스트가 수정되었습니다. 변경된 내용에 맞춰 🤖 분석 버튼으로 어법을 재분석할 수 있습니다.", "success");
          } else {
            showToast("문장 텍스트가 성공적으로 수정되었습니다.", "success");
          }
        } catch (err) {
          showToast(`수정 실패: ${err.message}`, "error");
          if (saveBtn) {
            saveBtn.disabled = false;
            saveBtn.textContent = "💾 저장";
          }
        }
      };

      if (saveBtn) saveBtn.addEventListener("click", doSave);
      if (cancelBtn) cancelBtn.addEventListener("click", restoreOriginal);

      if (textarea) {
        textarea.addEventListener("keydown", (keyEvent) => {
          if (keyEvent.key === "Enter" && (keyEvent.ctrlKey || keyEvent.metaKey)) {
            keyEvent.preventDefault();
            doSave();
          } else if (keyEvent.key === "Escape") {
            keyEvent.preventDefault();
            restoreOriginal();
          }
        });
      }
    });
  }

  // 인라인 태그 셀 갱신 및 삭제 이벤트 재바인딩
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

  return tr;
}

// 점진적 청크 렌더링 상태 변수
let _currentSentenceItems = [];
let _renderedSentenceCount = 0;
const SENTENCE_CHUNK_SIZE = 80;

function appendSentenceChunk() {
  if (_renderedSentenceCount >= _currentSentenceItems.length) return;
  const currentQuery = (resultsSearchInput && resultsSearchInput.value.trim()) || 
                       (mainSearchInput && mainSearchInput.value.trim()) || "";
  const fragment = document.createDocumentFragment();
  const nextLimit = Math.min(_renderedSentenceCount + SENTENCE_CHUNK_SIZE, _currentSentenceItems.length);
  for (let i = _renderedSentenceCount; i < nextLimit; i++) {
    const s = _currentSentenceItems[i];
    const tr = createSentenceRow(s, currentQuery);
    fragment.appendChild(tr);
  }
  _renderedSentenceCount = nextLimit;
  sentenceTableBody.appendChild(fragment);
  setTimeout(updateResultsNavHeight, 30);
}

function handleSentenceScroll() {
  if (appState.currentMode !== "sentence") return;
  if (_renderedSentenceCount >= _currentSentenceItems.length) return;
  const scrollBottom = window.innerHeight + window.scrollY;
  const threshold = document.documentElement.scrollHeight - 700;
  if (scrollBottom >= threshold) {
    appendSentenceChunk();
  }
}

let _sentenceScrollListenerBound = false;
function ensureSentenceScrollListener() {
  if (!_sentenceScrollListenerBound) {
    window.addEventListener("scroll", handleSentenceScroll, { passive: true });
    _sentenceScrollListenerBound = true;
  }
}

/** 문장 검색 안내 빈 화면 (검색어 없이 [문장] 탭 진입 시 표출) */
export function showSentenceEmptyGuidance() {
  stopAllListeningAudio();
  if (passageViewContainer) passageViewContainer.style.display = "none";
  if (sentenceViewContainer) sentenceViewContainer.style.display = "none";
  if (emptyResultsBox) emptyResultsBox.style.display = "none";
  if (loadingIndicator) loadingIndicator.style.display = "none";

  if (sentenceEmptyGuidanceBox) {
    sentenceEmptyGuidanceBox.style.display = "block";
  }

  appState.currentMode = "sentence";
  if (resultsTabModeSentence) resultsTabModeSentence.classList.add("active");
  if (resultsTabModePassage) resultsTabModePassage.classList.remove("active");
  if (tabModeSentence) tabModeSentence.classList.add("active");
  if (tabModePassage) tabModePassage.classList.remove("active");
  updateGrammarFiltersVisibility();

  setHeaderSlotState("sentence");
  if (resultsSearchInput) {
    resultsSearchInput.focus();
  }
}

export function renderSentenceView(items) {
  stopAllListeningAudio();
  if (sentenceEmptyGuidanceBox) sentenceEmptyGuidanceBox.style.display = "none";
  if (!items || items.length === 0) {
    emptyResultsBox.style.display = "flex";
    sentenceViewContainer.style.display = "none";
    _currentSentenceItems = [];
    _renderedSentenceCount = 0;
    return;
  }

  emptyResultsBox.style.display = "none";
  sentenceViewContainer.style.display = "block";
  sentenceMatchCount.textContent = items.length;
  sentenceTableBody.innerHTML = "";

  _currentSentenceItems = items;
  _renderedSentenceCount = 0;

  // 첫 80개 행을 즉시 생성하여 DOM에 추가 (5ms 초고속 렌더링)
  appendSentenceChunk();
  ensureSentenceScrollListener();
}

// ---- 이벤트 바인딩 및 초기화 (main.js 에서 원본 순서대로 호출) ----
export function init() {

  // 헤더 슬롯 버튼 클릭 시 상태에 따라 문장 보기 / 지문 복귀 수행
  if (btnHeaderFlow) {
    btnHeaderFlow.addEventListener("click", () => {
      if (btnHeaderFlow.classList.contains("mode-back")) {
        backToPassageView();
      } else {
        showSentencesForPassage(appState.currentPassageId);
      }
    });
  }

  // 문장 결과창 헤더의 '지문 결과창으로 돌아가기' 버튼
  if (btnSentenceBackToPassage) {
    btnSentenceBackToPassage.addEventListener("click", () => {
      backToPassageView();
    });
  }

  // 문장 결과창 헤더의 '📄 문장 유인물 담기' 일괄 담기 버튼
  const btnBatchAdd = document.getElementById("btnBatchAddSentenceHandout");
  if (btnBatchAdd) {
    btnBatchAdd.addEventListener("click", () => {
      const currentList = _currentSentenceItems || [];
      if (currentList.length === 0) {
        showToast("보관함에 담을 문장이 없습니다.", "warning");
        return;
      }
      let addedCount = 0;
      currentList.forEach((s) => {
        if (!isInSentenceCart(s.id)) {
          addToSentenceCart(s.id);
          addedCount++;
        }
      });
      showToast(`${currentList.length}개 중 신규 ${addedCount}개 문장이 유인물 보관함에 담겼습니다.`, "success");
    });
  }

  if (btnCloseGrammarPopover) {
    btnCloseGrammarPopover.addEventListener("click", closeGrammarPopover);
  }

  // 추천 검색어 칩 클릭 시 즉시 검색
  document.addEventListener("click", (e) => {
    const btnSample = e.target.closest(".btn-sample-keyword");
    if (btnSample && btnSample.dataset.keyword) {
      const kw = btnSample.dataset.keyword;
      if (resultsSearchInput) resultsSearchInput.value = kw;
      if (mainSearchInput) mainSearchInput.value = kw;
      executeSearch("results");
    }
  });

  // 전역 이벤트 위임: 어법 배지 클릭 시 상세 해설 팝오버 표시 및 바깥 클릭 시 닫기
  document.addEventListener("click", (e) => {
    const badge = e.target.closest(".grammar-tag-badge");
    if (badge) {
      // 배지 내 삭제(×) 버튼 클릭 시에는 해설 팝오버를 열지 않음
      if (e.target.closest(".grammar-remove-btn")) return;

      e.stopPropagation();
      let anno = null;
      if (badge.dataset.anno) {
        try {
          anno = JSON.parse(badge.dataset.anno);
        } catch (err) {
          console.error("Anno parse error:", err);
        }
      }
      if (anno) {
        showGrammarPopover(anno, badge);
      }
      return;
    }

    // 바깥 영역 클릭 시 팝오버 닫기
    if (grammarExplanationPopover && grammarExplanationPopover.style.display !== "none") {
      if (!grammarExplanationPopover.contains(e.target)) {
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
}
