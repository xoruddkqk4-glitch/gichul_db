/**
 * 05-gichul_db: 메인 프론트엔드 자바스크립트 로직 (main.js)
 * - 구글 스타일 검색창 및 지문/문장 모드 제어
 * - 2x2 지문 그리드 뷰어 및 실시간 태그 관리
 * - 1행 테이블 문장 뷰어 및 클립보드 복사(Ctrl+V) 연동
 * - PDF+HWP 업로드 및 샘플 데이터 원클릭 주입
 */

document.addEventListener("DOMContentLoaded", () => {
  // 상태 변수
  let currentMode = "passage"; // 'passage' 또는 'sentence'
  let currentPassageId = null;
  let passagesData = [];
  let sentencesData = [];

  // DOM 요소 캐싱
  const heroSearchSection = document.getElementById("heroSearchSection");
  const tabModePassage = document.getElementById("tabModePassage");
  const tabModeSentence = document.getElementById("tabModeSentence");
  const mainSearchInput = document.getElementById("mainSearchInput");
  const btnSearch = document.getElementById("btnSearch");
  const btnGoHome = document.getElementById("btnGoHome");

  // 필터
  const filterGrade = document.getElementById("filterGrade");
  const filterYear = document.getElementById("filterYear");
  const filterMonth = document.getElementById("filterMonth");
  const filterTag = document.getElementById("filterTag");

  // 컨테이너
  const loadingIndicator = document.getElementById("loadingIndicator");
  const passageViewContainer = document.getElementById("passageViewContainer");
  const sentenceViewContainer = document.getElementById("sentenceViewContainer");

  // 지문 2x2 뷰 요소
  const passageList = document.getElementById("passageList");
  const passageMatchCount = document.getElementById("passageMatchCount");
  const panelExplanation = document.getElementById("panelExplanation");
  const panelPdfImageContainer = document.getElementById("panelPdfImageContainer");
  const panelPassageText = document.getElementById("panelPassageText");
  const metaPassageId = document.getElementById("metaPassageId");
  const metaQNum = document.getElementById("metaQNum");
  const metaAnswer = document.getElementById("metaAnswer");
  const metaQuestionTitle = document.getElementById("metaQuestionTitle");
  const validationBadge = document.getElementById("validationBadge");
  const passageTagsList = document.getElementById("passageTagsList");
  const inputPassageTag = document.getElementById("inputPassageTag");
  const btnAddPassageTag = document.getElementById("btnAddPassageTag");
  const btnCopyPassage = document.getElementById("btnCopyPassage");
  const btnCopyExplanation = document.getElementById("btnCopyExplanation");

  // 문장 테이블 뷰 요소
  const sentenceMatchCount = document.getElementById("sentenceMatchCount");
  const sentenceTableBody = document.getElementById("sentenceTableBody");

  // 업로드 모달 및 버튼
  const btnOpenUploadModal = document.getElementById("btnOpenUploadModal");
  const btnCloseUploadModal = document.getElementById("btnCloseUploadModal");
  const btnCancelUpload = document.getElementById("btnCancelUpload");
  const uploadModal = document.getElementById("uploadModal");
  const uploadForm = document.getElementById("uploadForm");
  const btnSeedSample = document.getElementById("btnSeedSample");

  // 통계 배지
  const statPassages = document.getElementById("statPassages");
  const statSentences = document.getElementById("statSentences");

  // --- 1. 초기화 및 통계 로드 ---
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

  // 홈 로고 클릭 시 첫 검색창으로 복귀
  btnGoHome.addEventListener("click", () => {
    heroSearchSection.classList.remove("compact");
    passageViewContainer.style.display = "none";
    sentenceViewContainer.style.display = "none";
    mainSearchInput.value = "";
    mainSearchInput.focus();
  });

  // --- 2. 모드 전환 (지문 검색 vs 문장 검색) ---
  tabModePassage.addEventListener("click", () => {
    currentMode = "passage";
    tabModePassage.classList.add("active");
    tabModeSentence.classList.remove("active");
    mainSearchInput.placeholder = "검색할 키워드, 지문 주제 또는 출처([고3-2024년...])를 입력하세요...";
    if (heroSearchSection.classList.contains("compact")) {
      executeSearch();
    }
  });

  tabModeSentence.addEventListener("click", () => {
    currentMode = "sentence";
    tabModeSentence.classList.add("active");
    tabModePassage.classList.remove("active");
    mainSearchInput.placeholder = "검색할 영어 문장 표현 또는 출처([고3-2024년...-1번째 문장])를 입력하세요...";
    if (heroSearchSection.classList.contains("compact")) {
      executeSearch();
    }
  });

  // 검색 트리거 (Enter 또는 버튼 클릭)
  btnSearch.addEventListener("click", executeSearch);
  mainSearchInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      executeSearch();
    }
  });

  // 필터 변경 시 자동 재검색
  [filterGrade, filterYear, filterMonth].forEach((el) => {
    el.addEventListener("change", () => {
      if (heroSearchSection.classList.contains("compact")) {
        executeSearch();
      }
    });
  });

  filterTag.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && heroSearchSection.classList.contains("compact")) {
      executeSearch();
    }
  });

  // --- 3. 검색 실행 함수 ---
  async function executeSearch() {
    const keyword = mainSearchInput.value.trim();
    const grade = filterGrade.value;
    const year = filterYear.value;
    const month = filterMonth.value;
    const tag = filterTag.value.trim();

    // 상단 검색 섹션을 컴팩트 모드로 축소
    heroSearchSection.classList.add("compact");

    // UI 가시성 처리
    loadingIndicator.style.display = "flex";
    passageViewContainer.style.display = "none";
    sentenceViewContainer.style.display = "none";

    const params = new URLSearchParams();
    if (keyword) params.append("keyword", keyword);
    if (grade) params.append("grade", grade);
    if (year) params.append("year", year);
    if (month) params.append("month", month);
    if (tag) params.append("tag", tag);

    try {
      if (currentMode === "passage") {
        const res = await fetch(`/api/search/passages?${params.toString()}`);
        const data = await res.json();
        passagesData = data.items || [];
        renderPassageView(passagesData);
      } else {
        const res = await fetch(`/api/search/sentences?${params.toString()}`);
        const data = await res.json();
        sentencesData = data.items || [];
        renderSentenceView(sentencesData);
      }
    } catch (err) {
      console.error("검색 오류:", err);
      showToast("검색 중 오류가 발생했습니다.", "error");
    } finally {
      loadingIndicator.style.display = "none";
    }
  }

  // --- 4. 화면 2: 지문 검색 결과 렌더링 (2x2 그리드) ---
  function renderPassageView(items) {
    passageViewContainer.style.display = "flex";
    passageMatchCount.textContent = `${items.length}건`;
    passageList.innerHTML = "";

    if (items.length === 0) {
      passageList.innerHTML = `<div style="text-align: center; padding: 2rem; color: var(--text-muted);">검색 결과가 없습니다.</div>`;
      clear2x2Panels();
      return;
    }

    // 좌측 지문 목록 생성
    items.forEach((p, idx) => {
      const itemEl = document.createElement("div");
      itemEl.className = `passage-list-item ${idx === 0 ? "active" : ""}`;
      itemEl.dataset.id = p.id;
      itemEl.innerHTML = `
        <div class="item-badge-row">
          <span class="item-q-id">${p.id}</span>
          <span class="item-ratio">정답 ${p.answer_text || "-"}</span>
        </div>
        <div class="item-snippet">${escapeHtml(p.question_title || p.passage_text)}</div>
      `;

      itemEl.addEventListener("click", () => {
        document.querySelectorAll(".passage-list-item").forEach((el) => el.classList.remove("active"));
        itemEl.classList.add("active");
        loadPassageDetail(p);
      });

      passageList.appendChild(itemEl);
    });

    // 첫 번째 지문 기본 선택 로드
    loadPassageDetail(items[0]);
  }

  function loadPassageDetail(p) {
    currentPassageId = p.id;

    // 1. [좌측 상단]: HWP 정답과 해설
    panelExplanation.textContent = p.explanation_text || "해설 정보가 등록되지 않았습니다.";

    // 2. [우측 상단]: PDF 해당 문항 캡처 이미지
    if (p.pdf_crop_image) {
      panelPdfImageContainer.innerHTML = `
        <img src="${p.pdf_crop_image}" class="pdf-crop-img" alt="${p.id} 문항 캡처" title="클릭 시 새 창에서 원본 크기 보기">
      `;
      panelPdfImageContainer.querySelector("img").addEventListener("click", () => {
        window.open(p.pdf_crop_image, "_blank");
      });
    } else {
      panelPdfImageContainer.innerHTML = `
        <div class="pdf-placeholder">
          🖼️ PDF 문항 캡처 이미지가 생성되지 않았거나 없습니다.<br>
          <small style="color: var(--text-light);">시험지 업로드 시 PDF 파일을 함께 등록하시면 원본 문항 이미지가 자동 크롭됩니다.</small>
        </div>
      `;
    }

    // 3. [좌측 하단]: 지문 정보 & 태그 관리
    metaPassageId.textContent = p.id;
    metaQNum.textContent = `${p.q_num}번`;
    metaAnswer.textContent = p.answer_text ? `${p.answer_text}번` : "-";
    metaQuestionTitle.textContent = p.question_title || "-";
    validationBadge.textContent = p.remarks || `일치율 ${(p.validation_ratio * 100).toFixed(1)}%`;

    renderPassageTags(p.tags || []);

    // 4. [우측 하단]: TXT 지문 본문
    panelPassageText.textContent = p.passage_text || "지문 본문이 비어 있습니다.";
  }

  function clear2x2Panels() {
    panelExplanation.textContent = "-";
    panelPdfImageContainer.innerHTML = `<div class="pdf-placeholder">지문을 선택하세요.</div>`;
    metaPassageId.textContent = "-";
    metaQNum.textContent = "-";
    metaAnswer.textContent = "-";
    metaQuestionTitle.textContent = "-";
    passageTagsList.innerHTML = "";
    panelPassageText.textContent = "-";
  }

  // 지문 태그 렌더링
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

  // 지문 태그 추가 API
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
    if (e.key === "Enter") {
      addPassageTagAction();
    }
  });

  // 지문 태그 삭제 API
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
    const text = panelPassageText.textContent;
    if (text && text !== "지문 본문이 여기에 표시됩니다.") {
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

  // --- 5. 화면 3: 문장 검색 결과 렌더링 (1행 테이블) ---
  function renderSentenceView(items) {
    sentenceViewContainer.style.display = "block";
    sentenceMatchCount.textContent = items.length;
    sentenceTableBody.innerHTML = "";

    if (items.length === 0) {
      sentenceTableBody.innerHTML = `
        <tr>
          <td colspan="6" style="text-align: center; padding: 3rem; color: var(--text-muted);">
            검색된 문장이 없습니다. 다른 검색어를 입력해 보세요.
          </td>
        </tr>
      `;
      return;
    }

    items.forEach((s) => {
      const tr = document.createElement("tr");

      // 태그 배지 HTML 생성
      const tagsHtml = (s.tags || [])
        .map(
          (t) =>
            `<span class="tag-badge" style="font-size: 0.72rem; padding: 0.15rem 0.45rem;">#${escapeHtml(t)}
             <button class="tag-remove-btn" style="font-size: 0.75rem;" data-sent-id="${escapeHtml(s.id)}" data-tag="${escapeHtml(t)}">&times;</button></span>`
        )
        .join(" ");

      tr.innerHTML = `
        <td class="col-num">${s.row_num}</td>
        <td class="col-source">${escapeHtml(s.id)}</td>
        <td class="col-sentence">${escapeHtml(s.sentence_text)}</td>
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
          <button class="copy-btn btn-copy-sentence" data-text="${escapeHtml(s.sentence_text)}">
            📋 복사
          </button>
        </td>
      `;

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
            executeSearch(); // 갱신
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
              executeSearch();
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

  // --- 6. 클립보드 복사 헬퍼 ---
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

  // --- 7. 토스트 알림 헬퍼 ---
  function showToast(message, type = "info") {
    const toastContainer = document.getElementById("toastContainer");
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

  // --- 8. 업로드 모달 제어 및 API 제출 ---
  btnOpenUploadModal.addEventListener("click", () => {
    uploadModal.classList.add("show");
  });

  const closeUploadModal = () => {
    uploadModal.classList.remove("show");
  };

  btnCloseUploadModal.addEventListener("click", closeUploadModal);
  btnCancelUpload.addEventListener("click", closeUploadModal);

  uploadForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const formData = new FormData(uploadForm);
    const submitBtn = document.getElementById("btnSubmitUpload");
    submitBtn.disabled = true;
    submitBtn.textContent = "⏳ 파싱 및 검증 중...";

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
        // 업로드된 시험지로 자동 검색
        mainSearchInput.value = data.exam_id || "";
        executeSearch();
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

  // --- 9. 샘플 데이터 즉시 주입 ---
  btnSeedSample.addEventListener("click", async () => {
    btnSeedSample.disabled = true;
    btnSeedSample.textContent = "주입 중...";
    try {
      const res = await fetch("/api/seed-sample-data", { method: "POST" });
      const data = await res.json();
      if (res.ok) {
        showToast(data.message, "success");
        loadStats();
        // 첫 검색 자동 실행
        mainSearchInput.value = "";
        executeSearch();
      }
    } catch (e) {
      console.error(e);
      showToast("샘플 주입 실패", "error");
    } finally {
      btnSeedSample.disabled = false;
      btnSeedSample.textContent = "⚡ 샘플 데이터 주입";
    }
  });

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
});
