/**
 * 05-gichul_db: 원본 파일 현황 탭 · 선택 삭제 모달 (섹션 10-X) (files-status.js)
 * - main.js 에서 분리
 */

import { appState } from "./state.js";
import {
  btnCancelSelectiveDelete,
  btnCloseFilesStatusModal,
  btnCloseSelectiveDeleteModal,
  btnDeleteSelectedExams,
  btnExecuteSelectiveDelete,
  btnPresetFullWipe,
  btnPresetMetaOnly,
  btnPresetRateOnly,
  btnPresetRawOnly,
  btnRefreshFilesStatus,
  btnSelectAllExams,
  chkAllExams,
  chkDelCoreCorpus,
  chkDelMetadata,
  chkDelRateData,
  chkDelRawFiles,
  chkFilterMissingFiles,
  filesStatusTableBody,
  filesTotalAnsCount,
  filesTotalCsvCount,
  filesTotalExamsCount,
  filesTotalHwpCount,
  filesTotalPdfCount,
  manageExamsTableBody,
  selDelCoreBadge,
  selDelMetaBadge,
  selDelRateBadge,
  selDelRawSizeBadge,
  selDelTargetText,
  selDelWarningMsg,
  selectedExamsCount,
  selectiveDeleteModal,
} from "./dom.js";
import { showHomeScreen } from "./navigation.js";
import { loadStats } from "./search.js";
import { renderChoiceRates } from "./results-passage.js";
import { escapeHtml, showToast } from "./utils.js";
import {
  closeUploadModal,
  compareExams,
  loadExamsManagerList,
  renderManageExamsTable,
  triggerSingleFileUpload,
  updateSortHeaders,
} from "./upload.js";

let pendingDeleteExamIds = [];

// 업로드 모달 테이블 정렬 상태 (기본: 연도 내림차순 최신순)
let filesStatusSort = { key: "year", order: "desc" };
// =========================================================================
// 10-X. 원본 파일 현황 전용 탭 (PDF / HWP / PNG / CSV 업로드 유무 테이블 및 개별 업로드)
// =========================================================================

let cachedFilesStatusItems = [];

export async function loadFilesStatusList() {
  if (!filesStatusTableBody) return;
  filesStatusTableBody.innerHTML = `<tr><td colspan="11" style="text-align: center; padding: 2.5rem; color: var(--text-muted);"><span style="display:inline-block; animation:spin 1s linear infinite; margin-right:6px;">⏳</span> 모의고사 세트별 원본 파일 현황을 불러오는 중...</td></tr>`;

  try {
    const res = await fetch("/api/exams");
    const data = await res.json();
    cachedFilesStatusItems = data.items || [];
    renderFilesStatusTable();
  } catch (err) {
    console.error(err);
    filesStatusTableBody.innerHTML = `<tr><td colspan="11" style="text-align: center; padding: 2rem; color: #dc2626;">파일 현황을 불러오지 못했습니다.</td></tr>`;
  }
}

function renderFilesStatusTable() {
  if (!filesStatusTableBody) return;
  const items = cachedFilesStatusItems || [];
  const totalCount = items.length;

  // 통계 계산
  const pdfCount = items.filter(e => e.file_status?.pdf?.exists).length;
  const hwpCount = items.filter(e => e.file_status?.hwp?.exists).length;
  const ansCount = items.filter(e => e.file_status?.ans?.exists || (e.file_status?.ans?.answered_count > 0)).length;
  const csvCount = items.filter(e => e.file_status?.csv?.exists || (e.file_status?.csv?.rated_count > 0)).length;

  if (filesTotalExamsCount) filesTotalExamsCount.textContent = totalCount;
  if (filesTotalPdfCount) filesTotalPdfCount.textContent = pdfCount;
  if (filesTotalHwpCount) filesTotalHwpCount.textContent = hwpCount;
  if (filesTotalAnsCount) filesTotalAnsCount.textContent = ansCount;
  if (filesTotalCsvCount) filesTotalCsvCount.textContent = csvCount;

  document.querySelectorAll(".stat-total-ref").forEach(el => {
    el.textContent = totalCount;
  });

  if (items.length === 0) {
    filesStatusTableBody.innerHTML = `<tr><td colspan="11" style="text-align: center; padding: 2.5rem; color: var(--text-muted);">등록된 시험지가 없습니다. [스마트 일괄 업로드] 탭에서 시험지를 등록해 주세요.</td></tr>`;
    return;
  }

  const filterMissing = chkFilterMissingFiles && chkFilterMissingFiles.checked;
  const displayItems = filterMissing
    ? items.filter(e => {
        const fs = e.file_status || {};
        const hasPdf = fs.pdf?.exists;
        const hasHwp = fs.hwp?.exists;
        const hasAns = fs.ans?.exists || (fs.ans?.answered_count > 0);
        const hasCsv = fs.csv?.exists || (fs.csv?.rated_count > 0);
        return !(hasPdf && hasHwp && hasAns && hasCsv);
      })
    : items;

  if (displayItems.length === 0) {
    filesStatusTableBody.innerHTML = `<tr><td colspan="11" style="text-align: center; padding: 2.5rem; color: #059669; font-weight: 600;">🎉 모든 세트의 원본 파일 및 정답률(4종)이 완비되었습니다!</td></tr>`;
    return;
  }

  const sortedItems = [...displayItems].sort((a, b) => compareExams(a, b, filesStatusSort.key, filesStatusSort.order));

  filesStatusTableBody.innerHTML = "";
  sortedItems.forEach((exam, index) => {
    const tr = document.createElement("tr");
    tr.style.borderBottom = "1px solid var(--border)";

    const instClass = (exam.exam_type === "평가원") ? "badge-inst-pyeong" : "badge-inst-gyo";
    const instIcon = (exam.exam_type === "평가원") ? "🏛️" : "🏫";

    const fStat = exam.file_status || {};
    const pdfStat = fStat.pdf || {};
    const hwpStat = fStat.hwp || {};
    const ansStat = fStat.ans || {};
    const csvStat = fStat.csv || {};

    // 1. PDF 문제지 버튼
    let pdfBtnHtml = "";
    if (pdfStat.exists) {
      pdfBtnHtml = `<button type="button" class="btn-file-chip chip-exists btn-upload-single-file" data-id="${escapeHtml(exam.id)}" data-type="pdf" title="${escapeHtml(pdfStat.filename)} (클릭 시 파일 교체)">📄 등록됨</button>`;
    } else {
      pdfBtnHtml = `<button type="button" class="btn-file-chip chip-empty btn-upload-single-file" data-id="${escapeHtml(exam.id)}" data-type="pdf" title="클릭하여 PDF 문제지 단독 업로드">➕ PDF 업로드</button>`;
    }

    // 2. HWP 해설지 버튼
    let hwpBtnHtml = "";
    if (hwpStat.exists) {
      hwpBtnHtml = `<button type="button" class="btn-file-chip chip-exists btn-upload-single-file" data-id="${escapeHtml(exam.id)}" data-type="hwp" title="${escapeHtml(hwpStat.filename)} (클릭 시 파일 교체)">📝 등록됨</button>`;
    } else {
      hwpBtnHtml = `<button type="button" class="btn-file-chip chip-empty btn-upload-single-file" data-id="${escapeHtml(exam.id)}" data-type="hwp" title="클릭하여 HWP 해설지 단독 업로드">➕ HWP 업로드</button>`;
    }

    // 3. 정답표 이미지 (-A) 버튼
    let ansBtnHtml = "";
    const answeredCount = ansStat.answered_count || 0;
    const totalCount = exam.passage_count || 28;
    if (ansStat.exists) {
      ansBtnHtml = `<button type="button" class="btn-file-chip chip-ans-done btn-upload-single-file" data-id="${escapeHtml(exam.id)}" data-type="ans" title="${escapeHtml(ansStat.filename)} (정답 ${answeredCount}/${totalCount}문항 반영됨, 클릭 시 새 정답표/JSON으로 교체)">🖼️ 등록됨 (${answeredCount}/${totalCount})</button>`;
    } else if (answeredCount > 0) {
      ansBtnHtml = `<button type="button" class="btn-file-chip chip-ans-done btn-upload-single-file" data-id="${escapeHtml(exam.id)}" data-type="ans" title="DB 정답 등록 완료 (${answeredCount}/${totalCount}문항), 클릭 시 정답표/JSON 추가 등록">🔵 정답 (${answeredCount}/${totalCount})</button>`;
    } else {
      ansBtnHtml = `<button type="button" class="btn-file-chip chip-ans-needed btn-upload-single-file" data-id="${escapeHtml(exam.id)}" data-type="ans" title="클릭하여 정답 JSON(.json) 또는 이미지 등록 (1순위 정답 반영 & PDF 형광펜 갱신)">➕ 정답표 업로드</button>`;
    }

    // 4. 정답률 CSV 버튼
    let csvBtnHtml = "";
    const ratedCount = csvStat.rated_count || 0;
    if (csvStat.exists) {
      const avgText = csvStat.avg_rate != null ? ` (평균 ${csvStat.avg_rate}%)` : ` (${ratedCount}/${totalCount})`;
      csvBtnHtml = `<button type="button" class="btn-file-chip chip-rate-done btn-upload-single-file" data-id="${escapeHtml(exam.id)}" data-type="csv" title="${escapeHtml(csvStat.filename)} (정답률 ${ratedCount}/${totalCount}문항 반영됨, 클릭 시 새 파일로 교체)">📊 등록됨${avgText}</button>`;
    } else if (ratedCount > 0) {
      const avgText = csvStat.avg_rate != null ? ` (평균 ${csvStat.avg_rate}%)` : ` (${ratedCount}/${totalCount})`;
      csvBtnHtml = `<button type="button" class="btn-file-chip chip-rate-done btn-upload-single-file" data-id="${escapeHtml(exam.id)}" data-type="csv" title="DB 정답률 등록 완료 (${ratedCount}/${totalCount}문항), 클릭 시 새 CSV 등록">📊 등록됨${avgText}</button>`;
    } else {
      csvBtnHtml = `<button type="button" class="btn-file-chip chip-rate-needed btn-upload-single-file" data-id="${escapeHtml(exam.id)}" data-type="csv" title="클릭하여 정답률 CSV 업로드">➕ 정답률 업로드</button>`;
    }

    // 5. 종합 상태 배지
    let overallStatusHtml = "";
    const hasPdf = pdfStat.exists;
    const hasHwp = hwpStat.exists;
    const hasAns = ansStat.exists || (answeredCount > 0);
    const hasCsv = csvStat.exists || (ratedCount > 0);

    if (hasPdf && hasHwp && hasAns && hasCsv) {
      overallStatusHtml = `<span style="font-size: 0.74rem; background: #ecfdf5; color: #065f46; border: 1px solid #a7f3d0; padding: 2px 8px; border-radius: 4px; font-weight: 700; white-space: nowrap;">🟢 4종 완비</span>`;
    } else if (hasPdf && hasHwp && hasAns && !hasCsv) {
      overallStatusHtml = `<span style="font-size: 0.74rem; background: #fffbeb; color: #b45309; border: 1px solid #fde68a; padding: 2px 8px; border-radius: 4px; font-weight: 700; white-space: nowrap;">🟡 정답률 필요</span>`;
    } else if (hasPdf && hasHwp && !hasAns) {
      overallStatusHtml = `<span style="font-size: 0.74rem; background: #faf5ff; color: #6b21a8; border: 1px solid #e9d5ff; padding: 2px 8px; border-radius: 4px; font-weight: 700; white-space: nowrap;">🟣 정답표 필요</span>`;
    } else {
      overallStatusHtml = `<span style="font-size: 0.74rem; background: #fef2f2; color: #991b1b; border: 1px solid #fecaca; padding: 2px 8px; border-radius: 4px; font-weight: 700; white-space: nowrap;">🔴 파일 누락</span>`;
    }

    // 학년 배지 스타일
    const gradeBadgeClass = exam.grade === "고3" ? "badge-grade-g3" : (exam.grade === "고2" ? "badge-grade-g2" : "badge-grade-g1");
    const gradeBadgeHtml = `<span class="badge-grade-sub ${gradeBadgeClass}">${escapeHtml(exam.grade)}</span>`;

    tr.innerHTML = `
        <td style="padding: 10px 8px; text-align: center; color: var(--text-muted); font-weight: 600;">${index + 1}</td>
        <td style="padding: 10px 12px; font-weight: 700; color: #1e293b; white-space: nowrap;">${escapeHtml(exam.id)}</td>
        <td style="padding: 10px 8px; text-align: center; white-space: nowrap;">${gradeBadgeHtml}</td>
        <td style="padding: 10px 8px; text-align: center; font-weight: 600; color: #334155; white-space: nowrap;">${exam.year}년</td>
        <td style="padding: 10px 8px; text-align: center; font-weight: 600; color: #334155; white-space: nowrap;">${exam.month}월</td>
        <td style="padding: 10px 10px; white-space: nowrap;">
          <span class="badge-inst ${instClass}" style="white-space: nowrap;">${instIcon} ${escapeHtml(exam.exam_type)}</span>
        </td>
        <td style="padding: 10px 10px; text-align: center; white-space: nowrap;">${pdfBtnHtml}</td>
        <td style="padding: 10px 10px; text-align: center; white-space: nowrap;">${hwpBtnHtml}</td>
        <td style="padding: 10px 10px; text-align: center; white-space: nowrap;">${ansBtnHtml}</td>
        <td style="padding: 10px 10px; text-align: center; white-space: nowrap;">${csvBtnHtml}</td>
        <td style="padding: 10px 12px; text-align: center; white-space: nowrap;">${overallStatusHtml}</td>
      `;
    filesStatusTableBody.appendChild(tr);
  });

  // 칩 버튼 클릭 시 파일 선택 트리거
  filesStatusTableBody.querySelectorAll(".btn-upload-single-file").forEach(btn => {
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      const targetExamId = btn.dataset.id;
      const targetFileType = btn.dataset.type;
      triggerSingleFileUpload(targetExamId, targetFileType, btn);
    });
  });

  updateSortHeaders("files", filesStatusSort.key, filesStatusSort.order);
}

export function updateExamsSelectionState() {
  const allCheckboxes = manageExamsTableBody ? manageExamsTableBody.querySelectorAll(".chk-exam-row") : [];
  const checkedBoxes = Array.from(allCheckboxes).filter(c => c.checked);

  if (selectedExamsCount) selectedExamsCount.textContent = checkedBoxes.length;
  if (btnDeleteSelectedExams) btnDeleteSelectedExams.disabled = (checkedBoxes.length === 0);
  if (chkAllExams) {
    chkAllExams.checked = (allCheckboxes.length > 0 && checkedBoxes.length === allCheckboxes.length);
    chkAllExams.indeterminate = (checkedBoxes.length > 0 && checkedBoxes.length < allCheckboxes.length);
  }
}

// --- 선택적 데이터 삭제 모달 제어 함수들 ---
export function openSelectiveDeleteModal(examIds) {
  if (!selectiveDeleteModal || !examIds || examIds.length === 0) return;
  pendingDeleteExamIds = examIds;

  // 대상 시험지 객체들 추출
  const targetExams = appState.loadedExamsCache.filter(e => examIds.includes(e.id));

  // 대상 요약 텍스트
  if (selDelTargetText) {
    if (examIds.length === 1) {
      selDelTargetText.textContent = examIds[0];
    } else {
      selDelTargetText.textContent = `${examIds[0]} 외 ${examIds.length - 1}개 시험지 (총 ${examIds.length}개 일괄 선택)`;
    }
  }

  // 대상들의 4대 영역 통계 집계
  let totalRawMb = 0;
  let totalRawCount = 0;
  let totalPassages = 0;
  let totalSentences = 0;
  let totalGrammar = 0;
  let totalRated = 0;

  targetExams.forEach(ex => {
    totalRawMb += (ex.raw_file_size_mb || 0);
    totalRawCount += (ex.raw_file_count || 0);
    totalPassages += (ex.passage_count || 0);
    totalSentences += (ex.sentence_count || 0);
    totalGrammar += (ex.grammar_count || 0);
    if (ex.file_status && ex.file_status.csv) {
      totalRated += (ex.file_status.csv.rated_count || 0);
    }
  });

  if (selDelRawSizeBadge) {
    selDelRawSizeBadge.textContent = (totalRawCount > 0)
      ? `총 ${totalRawCount}개 파일 (${totalRawMb.toFixed(1)}MB)`
      : "파일 없음";
  }
  if (selDelCoreBadge) {
    selDelCoreBadge.textContent = `총 ${totalPassages}지문 / ${totalSentences}문장`;
  }
  if (selDelMetaBadge) {
    selDelMetaBadge.textContent = `총 어법 ${totalGrammar}개 등록됨`;
  }
  if (selDelRateBadge) {
    selDelRateBadge.textContent = (totalRated > 0)
      ? `총 ${totalRated}문항 정답률 등록됨`
      : "정답률 데이터 없음";
  }

  // 기본값: 전체 완전 삭제 프리셋 적용
  applySelectiveDeletePreset("full");

  selectiveDeleteModal.classList.add("show");
}

function closeSelectiveDeleteModal() {
  if (selectiveDeleteModal) selectiveDeleteModal.classList.remove("show");
  pendingDeleteExamIds = [];
}

// 프리셋 적용 함수
function applySelectiveDeletePreset(preset) {
  if (!chkDelRawFiles || !chkDelCoreCorpus || !chkDelMetadata) return;

  if (preset === "full") {
    // 1) 전체 완전 삭제
    chkDelRawFiles.checked = true;
    chkDelCoreCorpus.checked = true;
    chkDelMetadata.checked = true;
    chkDelMetadata.disabled = true; // 코어 삭제 시 메타도 종속 삭제
    if (chkDelRateData) {
      chkDelRateData.checked = true;
      chkDelRateData.disabled = true; // 코어 삭제 시 정답률도 종속 삭제
    }
  } else if (preset === "raw_only") {
    // 2) 원본 파일만 삭제
    chkDelRawFiles.checked = true;
    chkDelCoreCorpus.checked = false;
    chkDelMetadata.checked = false;
    chkDelMetadata.disabled = false;
    if (chkDelRateData) {
      chkDelRateData.checked = false;
      chkDelRateData.disabled = false;
    }
  } else if (preset === "meta_only") {
    // 3) 메타데이터만 초기화
    chkDelRawFiles.checked = false;
    chkDelCoreCorpus.checked = false;
    chkDelMetadata.checked = true;
    chkDelMetadata.disabled = false;
    if (chkDelRateData) {
      chkDelRateData.checked = false;
      chkDelRateData.disabled = false;
    }
  } else if (preset === "rate_only") {
    // 4) 정답률 데이터만 초기화
    chkDelRawFiles.checked = false;
    chkDelCoreCorpus.checked = false;
    chkDelMetadata.checked = false;
    chkDelMetadata.disabled = false;
    if (chkDelRateData) {
      chkDelRateData.checked = true;
      chkDelRateData.disabled = false;
    }
  }

  validateSelectiveDeleteOptions();
}

function validateSelectiveDeleteOptions() {
  const hasRaw = chkDelRawFiles && chkDelRawFiles.checked;
  const hasCore = chkDelCoreCorpus && chkDelCoreCorpus.checked;
  const hasMeta = chkDelMetadata && chkDelMetadata.checked;
  const hasRate = chkDelRateData && chkDelRateData.checked;

  const anySelected = hasRaw || hasCore || hasMeta || hasRate;

  if (selDelWarningMsg) {
    selDelWarningMsg.style.display = anySelected ? "none" : "block";
  }
  if (btnExecuteSelectiveDelete) {
    btnExecuteSelectiveDelete.disabled = !anySelected;
  }
}

// ---- 이벤트 바인딩 및 초기화 (main.js 에서 원본 순서대로 호출) ----
export function init() {

  // 테이블 헤더 정렬 클릭 이벤트 (이벤트 위임 방식으로 견고하게 처리)
  document.addEventListener("click", (e) => {
    const th = e.target.closest(".sortable-th");
    if (!th) return;
    const tableType = th.dataset.table;
    const sortKey = th.dataset.sort;
    if (!tableType || !sortKey) return;

    if (tableType === "files") {
      if (filesStatusSort.key === sortKey) {
        filesStatusSort.order = filesStatusSort.order === "asc" ? "desc" : "asc";
      } else {
        filesStatusSort.key = sortKey;
        filesStatusSort.order = (sortKey === "grade") ? "asc" : "desc";
      }
      renderFilesStatusTable();
    } else if (tableType === "manage") {
      if (appState.manageExamsSort.key === sortKey) {
        appState.manageExamsSort.order = appState.manageExamsSort.order === "asc" ? "desc" : "asc";
      } else {
        appState.manageExamsSort.key = sortKey;
        appState.manageExamsSort.order = (sortKey === "grade") ? "asc" : "desc";
      }
      renderManageExamsTable();
    }
  });

  // 필터 토글 및 새로고침 이벤트 바인딩
  if (chkFilterMissingFiles) {
    chkFilterMissingFiles.addEventListener("change", renderFilesStatusTable);
  }
  if (btnRefreshFilesStatus) {
    btnRefreshFilesStatus.addEventListener("click", () => loadFilesStatusList());
  }
  if (btnCloseFilesStatusModal) {
    btnCloseFilesStatusModal.addEventListener("click", closeUploadModal);
  }

  if (chkAllExams) {
    chkAllExams.addEventListener("change", () => {
      const allCheckboxes = manageExamsTableBody ? manageExamsTableBody.querySelectorAll(".chk-exam-row") : [];
      allCheckboxes.forEach(c => { c.checked = chkAllExams.checked; });
      updateExamsSelectionState();
    });
  }

  if (btnSelectAllExams) {
    btnSelectAllExams.addEventListener("click", () => {
      const allCheckboxes = manageExamsTableBody ? manageExamsTableBody.querySelectorAll(".chk-exam-row") : [];
      const anyUnchecked = Array.from(allCheckboxes).some(c => !c.checked);
      allCheckboxes.forEach(c => { c.checked = anyUnchecked; });
      updateExamsSelectionState();
    });
  }

  // 상단 일괄 삭제 버튼 -> 선택적 삭제 모달 오픈
  if (btnDeleteSelectedExams) {
    btnDeleteSelectedExams.addEventListener("click", () => {
      const allCheckboxes = manageExamsTableBody ? manageExamsTableBody.querySelectorAll(".chk-exam-row") : [];
      const selectedIds = Array.from(allCheckboxes).filter(c => c.checked).map(c => c.dataset.id);
      if (selectedIds.length === 0) return;
      openSelectiveDeleteModal(selectedIds);
    });
  }

  if (btnCloseSelectiveDeleteModal) {
    btnCloseSelectiveDeleteModal.addEventListener("click", closeSelectiveDeleteModal);
  }
  if (btnCancelSelectiveDelete) {
    btnCancelSelectiveDelete.addEventListener("click", closeSelectiveDeleteModal);
  }

  // 모달 배경 클릭 시 닫기
  if (selectiveDeleteModal) {
    selectiveDeleteModal.addEventListener("click", (e) => {
      if (e.target === selectiveDeleteModal) {
        closeSelectiveDeleteModal();
      }
    });
  }

  // ESC 키 입력 시 모달 닫기
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && selectiveDeleteModal && selectiveDeleteModal.classList.contains("show")) {
      closeSelectiveDeleteModal();
    }
  });

  if (btnPresetFullWipe) {
    btnPresetFullWipe.addEventListener("click", () => applySelectiveDeletePreset("full"));
  }
  if (btnPresetRawOnly) {
    btnPresetRawOnly.addEventListener("click", () => applySelectiveDeletePreset("raw_only"));
  }
  if (btnPresetMetaOnly) {
    btnPresetMetaOnly.addEventListener("click", () => applySelectiveDeletePreset("meta_only"));
  }
  if (btnPresetRateOnly) {
    btnPresetRateOnly.addEventListener("click", () => applySelectiveDeletePreset("rate_only"));
  }

  // 코어 본문 체크 시 메타데이터/정답률 자동 체크 및 disabled 처리 (종속 관계)
  if (chkDelCoreCorpus) {
    chkDelCoreCorpus.addEventListener("change", () => {
      if (chkDelCoreCorpus.checked) {
        chkDelMetadata.checked = true;
        chkDelMetadata.disabled = true;
        if (chkDelRateData) {
          chkDelRateData.checked = true;
          chkDelRateData.disabled = true;
        }
      } else {
        chkDelMetadata.disabled = false;
        if (chkDelRateData) {
          chkDelRateData.disabled = false;
        }
      }
      validateSelectiveDeleteOptions();
    });
  }

  if (chkDelRawFiles) {
    chkDelRawFiles.addEventListener("change", validateSelectiveDeleteOptions);
  }
  if (chkDelMetadata) {
    chkDelMetadata.addEventListener("change", validateSelectiveDeleteOptions);
  }
  if (chkDelRateData) {
    chkDelRateData.addEventListener("change", validateSelectiveDeleteOptions);
  }

  // 선택적 삭제 실행 버튼 바인딩
  if (btnExecuteSelectiveDelete) {
    btnExecuteSelectiveDelete.addEventListener("click", async () => {
      if (!pendingDeleteExamIds || pendingDeleteExamIds.length === 0) return;

      const deleteRaw = chkDelRawFiles ? chkDelRawFiles.checked : false;
      const deleteCore = chkDelCoreCorpus ? chkDelCoreCorpus.checked : false;
      const deleteMeta = chkDelMetadata ? chkDelMetadata.checked : false;
      const deleteRate = chkDelRateData ? chkDelRateData.checked : false;

      if (!deleteRaw && !deleteCore && !deleteMeta && !deleteRate) {
        alert("최소 1개 이상의 데이터 영역을 선택해 주세요.");
        return;
      }

      const actions = [];
      if (deleteRaw) actions.push("📁 원본 파일");
      if (deleteCore) {
        actions.push("📄 코어 본문 데이터(지문·문장)");
      } else {
        if (deleteMeta) actions.push("🏷️ 부가 메타데이터(어법/태그)");
        if (deleteRate) actions.push("📊 정답률 데이터");
      }

      const msg = `선택한 ${pendingDeleteExamIds.length}개 시험지에서 [${actions.join(", ")}] 영역을 삭제하시겠습니까?`;
      if (!confirm(msg)) return;

      btnExecuteSelectiveDelete.disabled = true;
      btnExecuteSelectiveDelete.textContent = "삭제 진행 중...";

      try {
        const res = await fetch("/api/exams/selective-delete", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            exam_ids: pendingDeleteExamIds,
            delete_raw_files: deleteRaw,
            delete_core_corpus: deleteCore,
            delete_metadata: deleteMeta,
            delete_rate_data: deleteRate
          })
        });
        const data = await res.json();

        if (res.ok) {
          showToast(`선택한 ${data.processed_count || pendingDeleteExamIds.length}개 시험지의 지정된 데이터가 안전하게 처리되었습니다.`, "success");
          closeSelectiveDeleteModal();
          loadExamsManagerList();
          loadFilesStatusList();
          loadStats();

          // 코어 본문이 삭제되었거나 정답률이 삭제되었고 현재 보고 있던 지문이 해당 시험지인 경우
          if (appState.currentPassageId) {
            const affected = pendingDeleteExamIds.some(id => appState.currentPassageId.includes(id.replace(/[\[\]]/g, "")));
            if (affected) {
              if (deleteCore) {
                showHomeScreen();
              } else if (deleteRate) {
                try {
                  const pRes = await fetch(`/api/passages/${appState.currentPassageId}`);
                  if (pRes.ok) {
                    const updatedP = await pRes.json();
                    renderChoiceRates(updatedP);
                  }
                } catch (pErr) {
                  console.error("정답률 패널 갱신 오류:", pErr);
                }
              }
            }
          }
        } else {
          alert(`삭제 실패: ${data.detail || "오류가 발생했습니다."}`);
        }
      } catch (err) {
        console.error(err);
        alert("데이터 삭제 통신 중 오류가 발생했습니다.");
      } finally {
        btnExecuteSelectiveDelete.disabled = false;
        btnExecuteSelectiveDelete.textContent = "🗑️ 선택한 데이터 영역 삭제 실행";
      }
    });
  }
}
