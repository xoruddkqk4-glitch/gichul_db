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
  popoverExplanationText,
  popoverPath,
  popoverPhraseSection,
  popoverPhraseText,
  resultsSearchInput,
  resultsTabModePassage,
  resultsTabModeSentence,
  resultsTotalCount,
  sentenceMatchCount,
  sentenceTableBody,
  sentenceViewContainer,
  tabModePassage,
  tabModeSentence,
} from "./dom.js";
import { setHeaderSlotState, setMode, updateGrammarFiltersVisibility, updateResultsNavHeight } from "./navigation.js";
import { executeSearch, highlightSentenceKeyword, loadStats } from "./search.js";
import { groupPassageItems, renderPassageView, selectPassageTab } from "./results-passage.js";
import { copyToClipboard, cssSafeId, escapeHtml, showToast } from "./utils.js";
import { openGrammarModalForSentence } from "./grammar.js";

// =========================================================================
// 7. [전체 문장 보기] <-> [지문 결과창으로 돌아가기] 연동
// =========================================================================

/** 특정 지문의 전체 문장 결과창을 1행 테이블로 표시 */
export async function showSentencesForPassage(passageId) {
  if (!passageId) {
    if (appState.currentPassageId) {
      passageId = appState.currentPassageId;
    } else if (appState.currentExamQuestions && appState.currentExamQuestions.length > 0) {
      passageId = appState.currentExamQuestions[appState.currentPassageIndex]?.id;
    } else if (appState.passagesData && appState.passagesData.length > 0) {
      passageId = appState.passagesData[0].id;
    }
  }
  if (!passageId) {
    setMode("sentence", true);
    return;
  }

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
        const identifier = a.id || a.category_id || 0;
        const removeBtn = sentenceId
          ? `<button type="button" class="grammar-remove-btn" data-sent-id="${escapeHtml(sentenceId)}" data-id="${escapeHtml(String(identifier))}" title="어법 범주 삭제">&times;</button>`
          : "";
        const annoJson = escapeHtml(JSON.stringify(a));
        return `<span class="grammar-tag-badge ${badgeClass}" data-sent-id="${escapeHtml(sentenceId || '')}" data-idx="${idx}" data-anno="${annoJson}" title="클릭하여 상세 해설 보기">🏷️ ${escapeHtml(a.leaf_name || a.pos || "")}${removeBtn}</span>`;
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
}

/** 어법 범주 배지 클릭 시 상세 해설 플로팅 팝오버 표시 */
export function showGrammarPopover(anno, targetElement) {
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

export function renderSentenceView(items) {
  if (!items || items.length === 0) {
    emptyResultsBox.style.display = "flex";
    sentenceViewContainer.style.display = "none";
    return;
  }

  emptyResultsBox.style.display = "none";
  sentenceViewContainer.style.display = "block";
  sentenceMatchCount.textContent = items.length;
  sentenceTableBody.innerHTML = "";
  const fragment = document.createDocumentFragment();
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

    tr.innerHTML = `
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
            const res = await fetch(`/api/sentences/${encodeURIComponent(s.id)}/grammar-annotations/${encodeURIComponent(identifier)}`, {
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
          // 삭제 버튼(×)을 클릭한 경우는 팝오버를 열지 않음
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

    fragment.appendChild(tr);
  });
  sentenceTableBody.appendChild(fragment);
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

  if (btnCloseGrammarPopover) {
    btnCloseGrammarPopover.addEventListener("click", closeGrammarPopover);
  }

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
