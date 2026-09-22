/**
 * 05-gichul_db: 시험지 업로드/DB 관리 모달 · 샘플 데이터 주입 (섹션 10~11) (upload.js)
 * - main.js 에서 분리
 */

import { appState } from "./state.js";
import {
  batchDropzone,
  batchFileInput,
  batchPreviewContainer,
  batchProgressBarFill,
  batchProgressBox,
  batchProgressCount,
  batchProgressSubtext,
  batchProgressTitle,
  batchSetsCount,
  batchSetsTableBody,
  btnCancelBatchModal,
  btnCancelUpload,
  btnClearBatchFiles,
  btnCloseManageModal,
  btnCloseUploadModal,
  btnOpenUploadModal,
  btnSeedSample,
  btnStartBatchUpload,
  examSingleFileInput,
  homeSearchView,
  mainSearchInput,
  manageExamsTableBody,
  manageExamsTotalCount,
  modalExamType,
  modalMonth,
  paneBatchUpload,
  paneFilesStatus,
  paneManageExams,
  paneSingleUpload,
  resultsView,
  tabBtnBatchUpload,
  tabBtnFilesStatus,
  tabBtnManageExams,
  tabBtnSingleUpload,
  uploadForm,
  uploadModal,
} from "./dom.js";
import { setHeaderSlotState, showHomeScreen } from "./navigation.js";
import { executeSearch, loadStats } from "./search.js";
import { renderChoiceRates } from "./results-passage.js";
import { escapeHtml, showToast } from "./utils.js";
import { loadFilesStatusList, openSelectiveDeleteModal, updateExamsSelectionState } from "./files-status.js";

// =========================================================================
// 10. 시험지 업로드 모달 제어 (월 자동 가이드 및 파이프라인 제출)
// =========================================================================
// =========================================================================
// 10. 시험지 업로드 및 DB 관리 모달 제어 (3개 탭 & 스마트 일괄 업로드 & 시험지 관리)
// =========================================================================

// 10-1. 모달 탭 전환 로직
function switchUploadTab(tabName) {
  [tabBtnBatchUpload, tabBtnFilesStatus, tabBtnSingleUpload, tabBtnManageExams].forEach(btn => {
    if (btn) btn.classList.toggle("active", btn.dataset.tab === tabName);
  });
  if (paneBatchUpload) paneBatchUpload.style.display = (tabName === "batch") ? "block" : "none";
  if (paneFilesStatus) paneFilesStatus.style.display = (tabName === "files") ? "block" : "none";
  if (paneSingleUpload) paneSingleUpload.style.display = (tabName === "single") ? "block" : "none";
  if (paneManageExams) paneManageExams.style.display = (tabName === "manage") ? "block" : "none";

  if (tabName === "files") {
    loadFilesStatusList();
  } else if (tabName === "manage") {
    loadExamsManagerList();
  }
}

export const closeUploadModal = () => {
  uploadModal.classList.remove("show");
  // 홈 검색 화면이 표시 중일 때 헤더 액션 슬롯을 확실하게 홈 상태(통계 배지)로 복원
  if (homeSearchView && homeSearchView.style.display !== "none") {
    setHeaderSlotState("home");
  }
  // 완료된 상태에서 닫히는 경우 배치 업로드 상태 정리
  if (btnStartBatchUpload && btnStartBatchUpload.dataset.state === "finished") {
    batchSetsMap = {};
    if (batchFileInput) batchFileInput.value = "";
    if (batchProgressBox) batchProgressBox.style.display = "none";
    btnStartBatchUpload.dataset.state = "";
    btnStartBatchUpload.textContent = "🚀 일괄 업로드 및 상호 검증 시작";
    btnStartBatchUpload.disabled = true;
    btnStartBatchUpload.style.background = "";
    btnStartBatchUpload.style.borderColor = "";
    if (btnCancelBatchModal) {
      btnCancelBatchModal.disabled = false;
      btnCancelBatchModal.textContent = "취소";
    }
    renderBatchSetsTable();
  }
};

// 10-2. 스마트 파일명 메타데이터 파서 및 출제기관 판별 규칙 (정답표 -A 접미사 지원)
function parseExamMetadataFromFilename(filename) {
  if (!filename) return null;
  const nameWithoutExt = filename.replace(/\.[^/.]+$/, "");
  const is_ans = /[\s\-_]?(A|ans|정답)$/i.test(nameWithoutExt);
  const cleanName = nameWithoutExt.replace(/[\s\-_]?(A|ans|정답)$/i, "");

  // 지원 패턴 예: 고3-[2026-07], 고3-[2026-7], 고3-2026-07, 고3_2026_07, 고3 2026년 7월 등
  const match = cleanName.match(/(고[1-3]|[1-3]학년)[\s\-_]?\[?(\d{4})[년\s\-_]+(\d{1,2})월?\]?/i);
  if (!match) return null;

  const rawGrade = match[1];
  const grade = rawGrade.includes("3") ? "고3" : (rawGrade.includes("2") ? "고2" : "고1");
  const year = parseInt(match[2], 10);
  const month = parseInt(match[3], 10);

  // 출제기관 규칙: 3학년의 6월, 9월, 11월만 '평가원' 출제. 3학년의 나머지 월과 1,2학년은 무조건 '교육청'
  const exam_type = (grade === "고3" && [6, 9, 11].includes(month)) ? "평가원" : "교육청";
  const set_key = `${grade}-[${year}-${String(month).padStart(2, "0")}]`;

  return { set_key, grade, year, month, exam_type, is_ans };
}

// 10-3. 스마트 일괄 업로드 (복수 세트) 드롭존 & 페어링 (PDF + HWP + 정답 이미지 3종)
let batchSetsMap = {}; // { set_key: { set_key, grade, year, month, exam_type, pdfFile, hwpFile, ansFile } }

async function handleBatchFilesSelected(fileList) {
  if (!fileList || fileList.length === 0) return;
  await fetchRegisteredExamsSet();

  for (let i = 0; i < fileList.length; i++) {
    const file = fileList[i];
    const meta = parseExamMetadataFromFilename(file.name);
    if (!meta) continue;

    const key = meta.set_key;
    if (!batchSetsMap[key]) {
      batchSetsMap[key] = {
        set_key: key,
        grade: meta.grade,
        year: meta.year,
        month: meta.month,
        exam_type: meta.exam_type,
        pdfFile: null,
        hwpFile: null,
        ansFile: null,
        csvFile: null,
      };
    }

    const lowerName = file.name.toLowerCase();
    if (lowerName.endsWith(".pdf")) {
      batchSetsMap[key].pdfFile = file;
    } else if (lowerName.endsWith(".hwp") || lowerName.endsWith(".hwpx")) {
      batchSetsMap[key].hwpFile = file;
    } else if (lowerName.endsWith(".csv")) {
      batchSetsMap[key].csvFile = file;
    } else if (lowerName.endsWith(".png") || lowerName.endsWith(".jpg") || lowerName.endsWith(".jpeg") || meta.is_ans) {
      batchSetsMap[key].ansFile = file;
    }
  }

  renderBatchSetsTable();
}

let registeredExamsSet = new Set();

async function fetchRegisteredExamsSet() {
  try {
    const res = await fetch("/api/exams");
    const data = await res.json();
    const items = data.items || [];
    registeredExamsSet = new Set(items.map(e => e.id));
  } catch (e) {
    console.error(e);
  }
}

function renderBatchSetsTable() {
  if (!batchSetsTableBody) return;
  batchSetsTableBody.innerHTML = "";
  const sets = Object.values(batchSetsMap);

  if (sets.length === 0) {
    if (batchPreviewContainer) batchPreviewContainer.style.display = "none";
    if (btnStartBatchUpload) btnStartBatchUpload.disabled = true;
    return;
  }

  if (batchPreviewContainer) batchPreviewContainer.style.display = "block";
  if (batchSetsCount) batchSetsCount.textContent = sets.length;

  let readyCount = 0;
  let ansOnlyCount = 0;
  let csvOnlyCount = 0;
  let fullUploadCount = 0;

  sets.forEach(set => {
    const examId = `[${set.grade}-${set.year}년-${String(set.month).padStart(2, "0")}월]`;
    set.exam_id = examId;

    const hasPdf = Boolean(set.pdfFile);
    const hasHwp = Boolean(set.hwpFile);
    const hasAns = Boolean(set.ansFile);
    const hasCsv = Boolean(set.csvFile);
    const isAlreadyRegistered = registeredExamsSet.has(examId);

    let isReady = false;
    let mode = ""; // "full" | "ans_only" | "csv_only" | "ans_and_csv" | "incomplete"
    let statusHtml = "";

    if (hasPdf && hasHwp) {
      isReady = true;
      mode = "full";
      fullUploadCount++;
      const extras = [];
      if (hasAns) extras.push("정답표");
      if (hasCsv) extras.push("정답률");
      const extraText = extras.length > 0 ? ` (${extras.join("·")} 포함)` : "";
      statusHtml = `<span class="badge-match-ready" style="background: #ecfdf5; color: #065f46; border: 1px solid #a7f3d0;">✅ 준비 완료${extraText}</span>`;
    } else if (hasAns && hasCsv && isAlreadyRegistered) {
      isReady = true;
      mode = "ans_and_csv";
      statusHtml = `<span class="badge-match-ready" style="background: #eff6ff; color: #1d4ed8; border: 1px solid #bfdbfe; font-weight: 700;">🔄 정답표+정답률 갱신 (준비 완료)</span>`;
    } else if (hasAns && isAlreadyRegistered) {
      // PDF/HWP가 없더라도 이미 DB에 등록된 시험지라면 정답표 단독 갱신 모드로 준비 완료!
      isReady = true;
      mode = "ans_only";
      ansOnlyCount++;
      statusHtml = `<span class="badge-match-ready" style="background: #faf5ff; color: #7e22ce; border: 1px solid #d8b4fe; font-weight: 700;">🔄 정답표 갱신 (준비 완료)</span>`;
    } else if (hasCsv && isAlreadyRegistered) {
      // PDF/HWP가 없더라도 이미 DB에 등록된 시험지라면 정답률 CSV 단독 갱신 모드로 준비 완료!
      isReady = true;
      mode = "csv_only";
      csvOnlyCount++;
      statusHtml = `<span class="badge-match-ready" style="background: #f0fdf4; color: #15803d; border: 1px solid #bbf7d0; font-weight: 700;">📊 정답률 갱신 (준비 완료)</span>`;
    } else {
      isReady = false;
      mode = "incomplete";
      statusHtml = (hasAns || hasCsv)
        ? `<span class="badge-match-warn" style="color: #dc2626; border-color: #fecaca; background: #fef2f2;">⚠️ 미등록 시험지 (PDF/HWP 필요)</span>`
        : `<span class="badge-match-warn">⚠️ HWP/PDF 누락</span>`;
    }

    set.isReady = isReady;
    set.mode = mode;
    if (isReady) readyCount++;

    const tr = document.createElement("tr");
    tr.id = `batch-row-${set.set_key.replace(/[\[\]\-]/g, "_")}`;

    const instClass = (set.exam_type === "평가원") ? "badge-inst-pyeong" : "badge-inst-gyo";
    const instIcon = (set.exam_type === "평가원") ? "🏛️" : "🏫";

    const pdfCellHtml = hasPdf 
      ? `<span style="color: #059669; font-weight: 600;">✅ ${escapeHtml(set.pdfFile.name)}</span>` 
      : (isAlreadyRegistered ? `<span style="color: #64748b;">💾 기존 DB 보관</span>` : `<span style="color: #dc2626;">❌ 누락</span>`);

    const hwpCellHtml = hasHwp 
      ? `<span style="color: #059669; font-weight: 600;">✅ ${escapeHtml(set.hwpFile.name)}</span>` 
      : (isAlreadyRegistered ? `<span style="color: #64748b;">💾 기존 DB 보관</span>` : `<span style="color: #dc2626;">❌ 누락</span>`);

    const ansCellHtml = hasAns
      ? `<span style="color: #7e22ce; font-weight: 700;">🖼️ ${escapeHtml(set.ansFile.name)}</span>`
      : `<span style="color: #94a3b8;">⚪ 미포함 (HWP 사용)</span>`;

    const csvCellHtml = hasCsv
      ? `<span style="color: #15803d; font-weight: 700;">📊 ${escapeHtml(set.csvFile.name)}</span>`
      : `<span style="color: #94a3b8;">⚪ 미포함 (선택)</span>`;

    tr.innerHTML = `
        <td style="padding: 8px 12px; font-weight: 700; color: #1e293b; white-space: nowrap;">
          ${escapeHtml(set.set_key)}
          ${isAlreadyRegistered ? `<span style="font-size: 0.72rem; color: #0284c7; background: #e0f2fe; padding: 1px 5px; border-radius: 4px; margin-left: 4px;">등록됨</span>` : ''}
        </td>
        <td style="padding: 8px 10px; white-space: nowrap;">${escapeHtml(set.grade)}</td>
        <td style="padding: 8px 10px; white-space: nowrap;">${set.year}년 ${set.month}월</td>
        <td style="padding: 8px 10px; white-space: nowrap;">
          <span class="badge-inst ${instClass}">${instIcon} ${escapeHtml(set.exam_type)}</span>
        </td>
        <td style="padding: 8px 10px; white-space: nowrap;">${pdfCellHtml}</td>
        <td style="padding: 8px 10px; white-space: nowrap;">${hwpCellHtml}</td>
        <td style="padding: 8px 10px; white-space: nowrap;">${ansCellHtml}</td>
        <td style="padding: 8px 10px; white-space: nowrap;">${csvCellHtml}</td>
        <td style="padding: 8px 10px; text-align: center; white-space: nowrap;" class="batch-row-status">${statusHtml}</td>
      `;
    batchSetsTableBody.appendChild(tr);
  });

  if (btnStartBatchUpload) {
    btnStartBatchUpload.disabled = (readyCount === 0);
    if (readyCount === 0) {
      btnStartBatchUpload.textContent = "🚀 일괄 업로드 및 상호 검증 시작";
    } else if (ansOnlyCount > 0 && fullUploadCount === 0 && csvOnlyCount === 0) {
      btnStartBatchUpload.textContent = `🔄 정답표 ${ansOnlyCount}개 세트 일괄 분석 및 반영 시작`;
    } else if (csvOnlyCount > 0 && fullUploadCount === 0 && ansOnlyCount === 0) {
      btnStartBatchUpload.textContent = `📊 정답률 CSV ${csvOnlyCount}개 세트 일괄 반영 시작`;
    } else {
      btnStartBatchUpload.textContent = `🚀 ${readyCount}개 세트 일괄 업로드/갱신 시작`;
    }
  }
}

// 공통 시험지 정렬 비교 함수 (학년 고1<고2<고3, 연도 숫자, 월 숫자, 보조 정렬)
export function compareExams(a, b, key, order) {
  let result = 0;
  if (key === "grade") {
    const gradeOrder = { "고1": 1, "고2": 2, "고3": 3 };
    const rA = gradeOrder[a.grade] || 9;
    const rB = gradeOrder[b.grade] || 9;
    result = rA - rB;
  } else if (key === "year") {
    result = (parseInt(a.year, 10) || 0) - (parseInt(b.year, 10) || 0);
  } else if (key === "month") {
    result = (parseInt(a.month, 10) || 0) - (parseInt(b.month, 10) || 0);
  } else if (key === "id") {
    result = (a.id || "").localeCompare(b.id || "");
  }

  // 기본 보조 정렬: 연도 내림차순 -> 월 내림차순 -> 학년 내림차순 -> id 오름차순
  if (result === 0) {
    const yDiff = (parseInt(b.year, 10) || 0) - (parseInt(a.year, 10) || 0);
    if (yDiff !== 0) return yDiff;
    const mDiff = (parseInt(b.month, 10) || 0) - (parseInt(a.month, 10) || 0);
    if (mDiff !== 0) return mDiff;
    const gradeOrder = { "고1": 1, "고2": 2, "고3": 3 };
    const gDiff = (gradeOrder[b.grade] || 9) - (gradeOrder[a.grade] || 9);
    if (gDiff !== 0) return gDiff;
    return (a.id || "").localeCompare(b.id || "");
  }

  return order === "desc" ? -result : result;
}

// 테이블 헤더 정렬 아이콘(▲/▼/⇅) 및 활성 클래스 갱신
export function updateSortHeaders(tableType, currentKey, currentOrder) {
  const selector = `.sortable-th[data-table="${tableType}"]`;
  document.querySelectorAll(selector).forEach(th => {
    const sortKey = th.dataset.sort;
    const iconSpan = th.querySelector(".sort-icon");
    if (sortKey === currentKey) {
      th.classList.add("active-sort");
      if (iconSpan) {
        iconSpan.textContent = currentOrder === "asc" ? "▲" : "▼";
      }
    } else {
      th.classList.remove("active-sort");
      if (iconSpan) {
        iconSpan.textContent = "⇅";
      }
    }
  });
}

export async function loadExamsManagerList() {
  if (!manageExamsTableBody) return;
  manageExamsTableBody.innerHTML = `<tr><td colspan="12" style="text-align: center; padding: 2rem; color: var(--text-muted);">시험지 목록 및 4대 데이터 영역 통계를 불러오는 중...</td></tr>`;

  try {
    const res = await fetch("/api/exams");
    const data = await res.json();
    const items = data.items || [];
    appState.loadedExamsCache = items;

    if (manageExamsTotalCount) manageExamsTotalCount.textContent = items.length;

    renderManageExamsTable();
  } catch (err) {
    console.error(err);
    manageExamsTableBody.innerHTML = `<tr><td colspan="12" style="text-align: center; padding: 2rem; color: #dc2626;">시험지 목록을 불러오지 못했습니다.</td></tr>`;
  }
}

export function renderManageExamsTable() {
  if (!manageExamsTableBody) return;

  if (!appState.loadedExamsCache || appState.loadedExamsCache.length === 0) {
    manageExamsTableBody.innerHTML = `<tr><td colspan="12" style="text-align: center; padding: 2rem; color: var(--text-muted);">등록된 시험지가 없습니다.</td></tr>`;
    updateExamsSelectionState();
    return;
  }

  // 이전에 체크되어 있던 exam.id 보존 (정렬 전환 시에도 체크 유지)
  const previouslyChecked = new Set(
    Array.from(manageExamsTableBody.querySelectorAll(".chk-exam-row:checked")).map(c => c.dataset.id)
  );

  const sortedItems = [...appState.loadedExamsCache].sort((a, b) => compareExams(a, b, appState.manageExamsSort.key, appState.manageExamsSort.order));

  manageExamsTableBody.innerHTML = "";
  sortedItems.forEach(exam => {
    const tr = document.createElement("tr");
    tr.style.borderBottom = "1px solid var(--border)";

    const instClass = (exam.exam_type === "평가원") ? "badge-inst-pyeong" : "badge-inst-gyo";
    const instIcon = (exam.exam_type === "평가원") ? "🏛️" : "🏫";

    const fStat = exam.file_status || {};
    const pdfStat = fStat.pdf || {};
    const hwpStat = fStat.hwp || {};
    const ansStat = fStat.ans || {};
    const csvStat = fStat.csv || {};

    // 1. PDF 문제지 칩 버튼
    let pdfBtnHtml = "";
    if (pdfStat.exists) {
      pdfBtnHtml = `<button type="button" class="btn-file-chip chip-exists btn-upload-single-file" data-id="${escapeHtml(exam.id)}" data-type="pdf" title="${escapeHtml(pdfStat.filename)} (클릭 시 파일 교체)">📄 등록됨</button>`;
    } else {
      pdfBtnHtml = `<button type="button" class="btn-file-chip chip-empty btn-upload-single-file" data-id="${escapeHtml(exam.id)}" data-type="pdf" title="클릭하여 PDF 문제지 단독 업로드">➕ PDF 등록</button>`;
    }

    // 2. HWP 해설지 칩 버튼
    let hwpBtnHtml = "";
    if (hwpStat.exists) {
      hwpBtnHtml = `<button type="button" class="btn-file-chip chip-exists btn-upload-single-file" data-id="${escapeHtml(exam.id)}" data-type="hwp" title="${escapeHtml(hwpStat.filename)} (클릭 시 파일 교체)">📝 등록됨</button>`;
    } else {
      hwpBtnHtml = `<button type="button" class="btn-file-chip chip-empty btn-upload-single-file" data-id="${escapeHtml(exam.id)}" data-type="hwp" title="클릭하여 HWP 해설지 단독 업로드">➕ HWP 등록</button>`;
    }

    // 3. 정답표 이미지 (-A) 칩 버튼
    let ansBtnHtml = "";
    const answeredCount = ansStat.answered_count || 0;
    const totalCount = ansStat.total_count || exam.passage_count || 28;
    if (ansStat.exists) {
      ansBtnHtml = `<button type="button" class="btn-file-chip chip-ans-done btn-upload-single-file" data-id="${escapeHtml(exam.id)}" data-type="ans" title="${escapeHtml(ansStat.filename)} (정답 ${answeredCount}/${totalCount}문항 반영됨, 클릭 시 새 이미지로 교체)">🖼️ 등록됨 (${answeredCount}/${totalCount})</button>`;
    } else if (answeredCount > 0) {
      ansBtnHtml = `<button type="button" class="btn-file-chip chip-ans-done btn-upload-single-file" data-id="${escapeHtml(exam.id)}" data-type="ans" title="DB 정답 등록 완료 (${answeredCount}/${totalCount}문항), 클릭 시 정답표 이미지 추가 등록">🔵 정답 (${answeredCount}/${totalCount})</button>`;
    } else {
      ansBtnHtml = `<button type="button" class="btn-file-chip chip-ans-needed btn-upload-single-file" data-id="${escapeHtml(exam.id)}" data-type="ans" title="클릭하여 정답표 이미지(-A.png) 등록 (Vision AI 정답 자동 추출 & PDF 형광펜 갱신)">➕ 정답표 등록</button>`;
    }

    // 4. 정답률 CSV 칩 버튼
    let csvBtnHtml = "";
    const ratedCount = csvStat.rated_count || 0;
    if (csvStat.exists) {
      const avgText = csvStat.avg_rate != null ? ` (평균 ${csvStat.avg_rate}%)` : ` (${ratedCount}/${totalCount})`;
      csvBtnHtml = `<button type="button" class="btn-file-chip chip-rate-done btn-upload-single-file" data-id="${escapeHtml(exam.id)}" data-type="csv" title="${escapeHtml(csvStat.filename)} (정답률 ${ratedCount}/${totalCount}문항 반영됨, 클릭 시 새 파일로 교체)">📊 등록됨${avgText}</button>`;
    } else if (ratedCount > 0) {
      const avgText = csvStat.avg_rate != null ? ` (평균 ${csvStat.avg_rate}%)` : ` (${ratedCount}/${totalCount})`;
      csvBtnHtml = `<button type="button" class="btn-file-chip chip-rate-done btn-upload-single-file" data-id="${escapeHtml(exam.id)}" data-type="csv" title="DB 정답률 등록 완료 (${ratedCount}/${totalCount}문항), 클릭 시 새 CSV 등록">📊 등록됨${avgText}</button>`;
    } else {
      csvBtnHtml = `<button type="button" class="btn-file-chip chip-rate-needed btn-upload-single-file" data-id="${escapeHtml(exam.id)}" data-type="csv" title="클릭하여 정답률 CSV 업로드">➕ CSV 등록</button>`;
    }

    // 5. 코어 본문 / 메타데이터 요약 배지
    const coreMetaHtml = `
        <div style="display: flex; flex-direction: column; gap: 3px;">
          <span class="badge-tier badge-tier-core" style="font-size: 0.72rem; padding: 2px 6px;">📄 ${exam.passage_count}지문 / ${exam.sentence_count}문장</span>
          <span class="badge-tier ${exam.grammar_count > 0 ? 'badge-tier-meta' : 'badge-tier-empty'}" style="font-size: 0.72rem; padding: 2px 6px;">🏷️ 어법 ${exam.grammar_count} / 태그 ${exam.tag_count}</span>
        </div>
      `;

    // 학년 배지 스타일
    const gradeBadgeClass = exam.grade === "고3" ? "badge-grade-g3" : (exam.grade === "고2" ? "badge-grade-g2" : "badge-grade-g1");
    const gradeBadgeHtml = `<span class="badge-grade-sub ${gradeBadgeClass}">${escapeHtml(exam.grade)}</span>`;

    const isChecked = previouslyChecked.has(exam.id) ? "checked" : "";

    tr.innerHTML = `
        <td style="padding: 10px 10px; text-align: center; white-space: nowrap;">
          <input type="checkbox" class="chk-exam-row" data-id="${escapeHtml(exam.id)}" ${isChecked} style="cursor: pointer;">
        </td>
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
        <td style="padding: 10px 10px; white-space: nowrap;">${coreMetaHtml}</td>
        <td style="padding: 10px 12px; text-align: center; white-space: nowrap;">
          <button type="button" class="btn-icon-delete btn-single-delete-exam" data-id="${escapeHtml(exam.id)}" title="해당 시험지 데이터 선택 삭제" style="white-space: nowrap;">
            🗑️ 삭제
          </button>
        </td>
      `;
    manageExamsTableBody.appendChild(tr);
  });

  // 개별 체크박스 변경 리스너
  manageExamsTableBody.querySelectorAll(".chk-exam-row").forEach(chk => {
    chk.addEventListener("change", updateExamsSelectionState);
  });

  // 개별 삭제 버튼 리스너 -> 선택적 삭제 모달 오픈
  manageExamsTableBody.querySelectorAll(".btn-single-delete-exam").forEach(btn => {
    btn.addEventListener("click", () => {
      const examId = btn.dataset.id;
      if (!examId) return;
      openSelectiveDeleteModal([examId]);
    });
  });

  // 파일 단독 등록/교체 칩 버튼 클릭 리스너 연결
  manageExamsTableBody.querySelectorAll(".btn-upload-single-file").forEach(btn => {
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      const targetExamId = btn.dataset.id;
      const targetFileType = btn.dataset.type;
      triggerSingleFileUpload(targetExamId, targetFileType, btn);
    });
  });

  updateSortHeaders("manage", appState.manageExamsSort.key, appState.manageExamsSort.order);
  updateExamsSelectionState();
}
let activeSingleTargetExamId = null;
let activeSingleTargetType = null;
let activeSingleTargetBtn = null;

export function triggerSingleFileUpload(examId, fileType, btnElement) {
  if (!examSingleFileInput) return;
  activeSingleTargetExamId = examId;
  activeSingleTargetType = fileType;
  activeSingleTargetBtn = btnElement;

  if (fileType === "ans") {
    examSingleFileInput.accept = ".png,.jpg,.jpeg";
  } else if (fileType === "csv") {
    examSingleFileInput.accept = ".csv";
  } else if (fileType === "pdf") {
    examSingleFileInput.accept = ".pdf";
  } else if (fileType === "hwp") {
    examSingleFileInput.accept = ".hwp,.hwpx";
  }

  examSingleFileInput.value = "";
  examSingleFileInput.click();
}
// =========================================================================
// 11. 샘플 데이터 즉시 주입
// =========================================================================

// ---- 이벤트 바인딩 및 초기화 (main.js 에서 원본 순서대로 호출) ----
export function init() {

  if (tabBtnBatchUpload) tabBtnBatchUpload.addEventListener("click", () => switchUploadTab("batch"));
  if (tabBtnFilesStatus) tabBtnFilesStatus.addEventListener("click", () => switchUploadTab("files"));
  if (tabBtnSingleUpload) tabBtnSingleUpload.addEventListener("click", () => switchUploadTab("single"));
  if (tabBtnManageExams) tabBtnManageExams.addEventListener("click", () => switchUploadTab("manage"));

  btnOpenUploadModal.addEventListener("click", () => {
    uploadModal.classList.add("show");
    fetchRegisteredExamsSet();
    switchUploadTab("batch");
  });

  btnCloseUploadModal.addEventListener("click", closeUploadModal);
  btnCancelUpload.addEventListener("click", closeUploadModal);
  if (btnCancelBatchModal) btnCancelBatchModal.addEventListener("click", closeUploadModal);
  if (btnCloseManageModal) btnCloseManageModal.addEventListener("click", closeUploadModal);

  // 드롭존 이벤트 바인딩
  if (batchDropzone) {
    ["dragenter", "dragover"].forEach(evt => {
      batchDropzone.addEventListener(evt, (e) => {
        e.preventDefault();
        e.stopPropagation();
        batchDropzone.classList.add("dragover");
      });
    });

    ["dragleave", "dragend"].forEach(evt => {
      batchDropzone.addEventListener(evt, (e) => {
        e.preventDefault();
        e.stopPropagation();
        batchDropzone.classList.remove("dragover");
      });
    });

    batchDropzone.addEventListener("drop", (e) => {
      e.preventDefault();
      e.stopPropagation();
      batchDropzone.classList.remove("dragover");
      if (e.dataTransfer && e.dataTransfer.files) {
        handleBatchFilesSelected(e.dataTransfer.files);
      }
    });
  }

  if (batchFileInput) {
    batchFileInput.addEventListener("change", (e) => {
      if (e.target.files) {
        handleBatchFilesSelected(e.target.files);
      }
    });
  }

  if (btnClearBatchFiles) {
    btnClearBatchFiles.addEventListener("click", () => {
      batchSetsMap = {};
      if (batchFileInput) batchFileInput.value = "";
      renderBatchSetsTable();
    });
  }

  // 일괄 업로드 순차 실행
  if (btnStartBatchUpload) {
    btnStartBatchUpload.addEventListener("click", async () => {
      // 이미 처리가 완료된 상태에서 버튼을 누른 경우 -> 모달을 닫고 홈 검색 갱신
      if (btnStartBatchUpload.dataset.state === "finished") {
        closeUploadModal();
        if (resultsView && resultsView.style.display !== "none") {
          executeSearch("results");
        } else {
          showHomeScreen();
        }
        return;
      }

      const sets = Object.values(batchSetsMap).filter(s => s.isReady);
      if (sets.length === 0) return;

      btnStartBatchUpload.disabled = true;
      if (btnCancelBatchModal) btnCancelBatchModal.disabled = true;
      if (batchProgressBox) batchProgressBox.style.display = "block";

      let successCount = 0;
      let failCount = 0;

      for (let i = 0; i < sets.length; i++) {
        const set = sets[i];
        const rowId = `batch-row-${set.set_key.replace(/[\[\]\-]/g, "_")}`;
        const row = document.getElementById(rowId);
        const statusCell = row ? row.querySelector(".batch-row-status") : null;

        if (statusCell) {
          statusCell.innerHTML = `<span style="color: var(--primary); font-weight: 600;">⏳ 처리 중...</span>`;
        }

        const pct = Math.round(((i + 1) / sets.length) * 100);
        if (batchProgressBarFill) {
          batchProgressBarFill.style.width = `${pct}%`;
          batchProgressBarFill.classList.add("progress-bar-animated");
        }
        if (batchProgressCount) batchProgressCount.textContent = `${i + 1} / ${sets.length}`;
        if (batchProgressTitle) {
          batchProgressTitle.innerHTML = `<span style="display:inline-block; animation:spin 1s linear infinite; margin-right:6px;">⏳</span> [${escapeHtml(set.set_key)}] 처리 중...`;
        }
        if (batchProgressSubtext) {
          if (set.mode === "ans_only") {
            batchProgressSubtext.textContent = `🖼️ 정답표 Vision AI 분석 및 PDF 정답 형광펜 갱신 중 (${i + 1}/${sets.length})`;
          } else if (set.mode === "csv_only") {
            batchProgressSubtext.textContent = `📊 정답률 CSV 파싱 및 문항별 선택률 반영 중 (${i + 1}/${sets.length})`;
          } else if (set.mode === "ans_and_csv") {
            batchProgressSubtext.textContent = `🖼️ 정답표 AI 분석 및 📊 정답률 CSV 동시 반영 중 (${i + 1}/${sets.length})`;
          } else {
            const hasAns = !!set.ansFile;
            const hasCsv = !!set.csvFile;
            const extra = (hasAns && hasCsv) ? " + 🖼️정답표AI + 📊정답률" : (hasAns ? " + 🖼️정답표AI" : (hasCsv ? " + 📊정답률" : ""));
            batchProgressSubtext.textContent = `📄 PDF 2단 분할 & HWP 교차 검증${extra} 진행 중 (약 10~25초)... (${i + 1}/${sets.length})`;
          }
        }

        try {
          if (set.mode === "csv_only") {
            // 기존 등록 시험지에 대한 정답률 CSV 단독 일괄 갱신
            const formData = new FormData();
            formData.append("file_type", "csv");
            formData.append("file", set.csvFile);

            const res = await fetch(`/api/exams/${encodeURIComponent(set.exam_id)}/upload-file`, {
              method: "POST",
              body: formData
            });
            const resData = await res.json();
            if (!res.ok && statusCell) {
              statusCell.title = resData.detail || "";
            }
            if (res.ok) {
              successCount++;
              if (statusCell) {
                statusCell.innerHTML = `<span style="color: #059669; font-weight: 700;">✅ 정답률 (${resData.updated_count || resData.parsed_count || 0}문항)</span>`
                  + ((resData.warnings || []).length ? ` <span style="color: #d97706; font-weight: 700;" title="${resData.warnings.join('\n')}">⚠ ${resData.corrections ? Object.keys(resData.corrections).length : 0}건 정정</span>` : "");
              }
            } else {
              failCount++;
              if (statusCell) {
                statusCell.innerHTML = `<span style="color: #dc2626; font-weight: 700;">❌ 실패</span>`;
              }
            }
          } else if (set.mode === "ans_and_csv") {
            // 정답표와 정답률 CSV를 순차적으로 단독 갱신
            let ok1 = false;
            let ok2 = false;
            let cntAns = 0;
            let cntCsv = 0;
            if (set.ansFile) {
              const fdAns = new FormData();
              fdAns.append("file_type", "ans");
              fdAns.append("file", set.ansFile);
              const r1 = await fetch(`/api/exams/${encodeURIComponent(set.exam_id)}/upload-file`, { method: "POST", body: fdAns });
              const d1 = await r1.json();
              if (r1.ok) { ok1 = true; cntAns = d1.extracted_count || 45; }
            }
            if (set.csvFile) {
              const fdCsv = new FormData();
              fdCsv.append("file_type", "csv");
              fdCsv.append("file", set.csvFile);
              const r2 = await fetch(`/api/exams/${encodeURIComponent(set.exam_id)}/upload-file`, { method: "POST", body: fdCsv });
              const d2 = await r2.json();
              if (r2.ok) { ok2 = true; cntCsv = d2.updated_count || 0; }
            }
            if (ok1 || ok2) {
              successCount++;
              if (statusCell) {
                statusCell.innerHTML = `<span style="color: #059669; font-weight: 700;">✅ 정답+정답률 (${cntCsv || cntAns}문항)</span>`;
              }
            } else {
              failCount++;
              if (statusCell) {
                statusCell.innerHTML = `<span style="color: #dc2626; font-weight: 700;">❌ 실패</span>`;
              }
            }
          } else if (set.mode === "ans_only") {
            // 기존 등록 시험지에 대한 정답표 단독 일괄 갱신
            const formData = new FormData();
            formData.append("file_type", "ans");
            formData.append("file", set.ansFile);

            const res = await fetch(`/api/exams/${encodeURIComponent(set.exam_id)}/upload-file`, {
              method: "POST",
              body: formData
            });
            const resData = await res.json();
            if (res.ok) {
              successCount++;
              if (statusCell) {
                statusCell.innerHTML = `<span style="color: #059669; font-weight: 700;">✅ 정답 갱신 (${resData.extracted_count || 0}문항)</span>`
                  + ((resData.warnings || []).length ? ` <span style="color: #d97706; font-weight: 700;" title="${resData.warnings.join('\n')}">⚠ ${resData.image_status}</span>` : "");
              }
            } else {
              failCount++;
              if (statusCell) {
                statusCell.innerHTML = `<span style="color: #dc2626; font-weight: 700;">❌ 실패</span>`;
              }
            }
          } else {
            // 신규/전체 모의고사 세트 일괄 업로드 파이프라인
            const formData = new FormData();
            formData.append("grade", set.grade);
            formData.append("year", set.year);
            formData.append("month", set.month);
            formData.append("exam_type", set.exam_type);
            formData.append("reading_start", 18);
            formData.append("reading_end", 45);
            formData.append("pdf_file", set.pdfFile);
            formData.append("hwp_file", set.hwpFile);
            if (set.ansFile) {
              formData.append("ans_file", set.ansFile);
            }
            if (set.csvFile) {
              formData.append("csv_file", set.csvFile);
            }

            const res = await fetch("/api/upload", { method: "POST", body: formData });
            const resData = await res.json();
            if (res.ok) {
              successCount++;
              if (statusCell) {
                const unv = (resData.answer_report && resData.answer_report.unverified_questions) || [];
                statusCell.innerHTML = `<span style="color: #059669; font-weight: 700;">✅ 완료 (${resData.passages_count || 28}문항)</span>`
                  + (unv.length ? ` <span style="color: #d97706; font-weight: 700;" title="${(resData.answer_report.warnings || []).join('\n')}">⚠ 정답 미검증 ${unv.length}</span>` : "");
              }
            } else {
              failCount++;
              if (statusCell) {
                statusCell.innerHTML = `<span style="color: #dc2626; font-weight: 700;">❌ 실패</span>`;
              }
            }
          }
        } catch (err) {
          console.error(err);
          failCount++;
          if (statusCell) {
            statusCell.innerHTML = `<span style="color: #dc2626; font-weight: 700;">❌ 오류</span>`;
          }
        }
      }

      if (batchProgressBarFill) {
        batchProgressBarFill.style.width = "100%";
        batchProgressBarFill.classList.remove("progress-bar-animated");
      }
      if (batchProgressTitle) batchProgressTitle.innerHTML = "🎉 일괄 처리 완료!";
      if (batchProgressSubtext) {
        batchProgressSubtext.textContent = `총 ${sets.length}개 세트 중 ${successCount}개 성공, ${failCount}개 실패`;
      }
      showToast(`총 ${successCount}개 세트 처리가 완료되었습니다!`, "success");

      loadStats();
      await fetchRegisteredExamsSet();
      if (typeof loadFilesStatusList === 'function') await loadFilesStatusList();
      if (typeof loadExamsManagerList === 'function') await loadExamsManagerList();
      if (resultsView && resultsView.style.display !== "none") {
        executeSearch("results");
      }

      // 지문 뷰어에 띄워져 있는 이미지 캐시 버스팅
      const activePanelImgs = document.querySelectorAll("#panelPdfImageContainer img");
      activePanelImgs.forEach(img => {
        if (img && img.src) {
          const cleanSrc = img.src.split("?")[0];
          img.src = `${cleanSrc}?t=${Date.now()}`;
        }
      });

      if (btnCancelBatchModal) {
        btnCancelBatchModal.disabled = false;
        btnCancelBatchModal.textContent = "닫기";
      }

      // 처리 완료 상태로 변경 및 활성화 (클릭 시 모달 닫기 수행)
      btnStartBatchUpload.disabled = false;
      btnStartBatchUpload.dataset.state = "finished";
      btnStartBatchUpload.textContent = "✔ 처리 완료 (닫기)";
      btnStartBatchUpload.style.background = "#059669";
      btnStartBatchUpload.style.borderColor = "#059669";
    });
  }

  // 10-4. 단일 세트 수동 업로드 (기존 폼 유지)
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
        const rep = data.answer_report;
        if (rep && rep.unverified_questions && rep.unverified_questions.length) {
          alert(`⚠ 정답 검증 경고 [${data.exam_id}]\n\n${(rep.warnings || []).join("\n")}`);
        }
        showToast(data.message || "시험지가 성공적으로 등록되었습니다!", rep && rep.unverified_questions && rep.unverified_questions.length ? "warning" : "success");
        closeUploadModal();
        uploadForm.reset();
        loadStats();
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
      submitBtn.textContent = "🚀 단일 세트 상호 검증 및 DB 저장";
    }
  });

  if (examSingleFileInput) {
    examSingleFileInput.addEventListener("change", async () => {
      const file = examSingleFileInput.files[0];
      if (!file || !activeSingleTargetExamId || !activeSingleTargetType) return;

      const targetBtn = activeSingleTargetBtn;
      const originalBtnHtml = targetBtn ? targetBtn.innerHTML : "";
      if (targetBtn) {
        targetBtn.disabled = true;
        targetBtn.innerHTML = activeSingleTargetType === "ans"
          ? `<span style="display:inline-block; animation:spin 1s linear infinite;">⏳</span> AI 분석 중...`
          : (activeSingleTargetType === "csv"
            ? `<span style="display:inline-block; animation:spin 1s linear infinite;">⏳</span> 파싱 중...`
            : `⏳ 업로드 중...`);
      }

      const formData = new FormData();
      formData.append("file_type", activeSingleTargetType);
      formData.append("file", file);

      try {
        const res = await fetch(`/api/exams/${encodeURIComponent(activeSingleTargetExamId)}/upload-file`, {
          method: "POST",
          body: formData
        });
        const data = await res.json();
        if (res.ok) {
          alert(`🎉 [${activeSingleTargetExamId}] ${data.message || '성공적으로 반영되었습니다.'}`);
          await loadExamsManagerList();
          await loadFilesStatusList();
          if (resultsView && resultsView.style.display !== "none") {
            executeSearch("results");
          }

          // 현재 열려있는 지문이 있다면 실시간 갱신 (정답률 시각화 등)
          if (appState.currentPassageId) {
            try {
              const pRes = await fetch(`/api/passages/${appState.currentPassageId}`);
              if (pRes.ok) {
                const updatedP = await pRes.json();
                renderChoiceRates(updatedP);
              }
            } catch (pErr) {
              console.error("지문 상세 갱신 실패:", pErr);
            }
          }

          // 지문 뷰어에 띄워져 있는 이미지 캐시 버스팅
          const activePanelImgs = document.querySelectorAll("#panelPdfImageContainer img");
          activePanelImgs.forEach(img => {
            if (img && img.src) {
              const cleanSrc = img.src.split("?")[0];
              img.src = `${cleanSrc}?t=${Date.now()}`;
            }
          });
        } else {
          alert(`❌ 업로드 실패: ${data.detail || '오류가 발생했습니다.'}`);
          if (targetBtn) {
            targetBtn.disabled = false;
            targetBtn.innerHTML = originalBtnHtml;
          }
        }
      } catch (err) {
        console.error(err);
        alert(`❌ 통신 오류가 발생했습니다: ${err.message}`);
        if (targetBtn) {
          targetBtn.disabled = false;
          targetBtn.innerHTML = originalBtnHtml;
        }
      } finally {
        examSingleFileInput.value = "";
      }
    });
  }

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
}
