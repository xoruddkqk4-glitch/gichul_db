/**
 * 05-gichul_db: 교사용 듣기 수업 진행 전용 대형 칠판 모달 & Audio Waveform 플레이어
 * (listening-classroom.js)
 *
 * - 전체화면(Fullscreen) 교사용 인터랙티브 수업 모드
 * - 문항별/문장별 분할 로딩 및 네온 민트 대칭 파형(Waveform) 시각화 (Web Audio API + Canvas)
 * - 마우스 드래그 앤 드롭 구간 선택 및 오버레이 박스
 * - A-B Looper 선택 구간 N회 반복 재생 엔진
 * - FELS 기능어 약형드랩 [  ] 빈칸 퀴즈 모드 및 우리말 해석 토글
 * - 키보드 단축키(Space, ←, →, R, F, Esc) 지원
 */

class ListeningClassroomController {
  constructor() {
    this.isOpen = false;
    this.classroomData = null; // { project_title, total_questions, questions: [...] }
    this.currentQIndex = 0;
    this.currentSIndex = 0;

    // Web Audio & 재생 상태
    this.audioCtx = null;
    this.audioBuffer = null;
    this.audioElement = new Audio();
    this.audioDuration = 0;
    this.isPlaying = false;
    this.animFrameId = null;

    // 드래그 구간 선택 & A-B Looper
    this.selectedRegion = null; // { startRatio, endRatio, startTime, endTime }
    this.isDragging = false;
    this.dragStartX = 0;
    this.isLoopMode = false;
    this.currentLoopCount = 0;
    this.targetLoopCount = 3;

    // 텍스트 모드 & 인터랙티브 FELS 빈칸 (디폴트: 약형드랩 먼저 표시)
    this.textMode = "fels"; // "fels" (약형드랩) | "script" (원문)
    this.showTrans = false; // 우리말 해석 표시 여부
    this.revealedSlots = new Set(); // 정답이 노출된 [ ] 슬롯 인덱스 번호

    // 캐시 & 설정
    this.audioBufferCache = new Map(); // url -> AudioBuffer
    this.currentAudioUrl = "";

    // DOM 요소 캐시
    this.dom = {};
  }

  /** 초기 DOM 참조 및 이벤트 바인딩 */
  init() {
    this.cacheDom();
    if (!this.dom.modal) return;
    this.bindEvents();
  }

  cacheDom() {
    this.dom = {
      modal: document.getElementById("listeningClassroomModal"),
      window: document.getElementById("classroomModalWindow"),
      projectTitle: document.getElementById("txtClassroomProjectTitle"),
      posBadge: document.getElementById("txtClassroomPosBadge"),
      selectQuestion: document.getElementById("selectClassroomQuestion"),
      btnFullscreen: document.getElementById("btnClassroomFullscreen"),
      txtFullscreenIcon: document.getElementById("txtFullscreenIcon"),
      btnClose: document.getElementById("btnCloseClassroomModal"),

      // 문장 텍스트 영역
      speakerBadge: document.getElementById("classroomSpeakerBadge"),
      qType: document.getElementById("classroomQType"),
      btnToggleMode: document.getElementById("btnToggleClassroomMode"),
      txtModeIcon: document.getElementById("txtClassroomModeIcon"),
      txtModeLabel: document.getElementById("txtClassroomModeLabel"),
      btnToggleTrans: document.getElementById("btnToggleClassroomTrans"),
      txtTransIcon: document.getElementById("txtClassroomTransIcon"),
      txtTransLabel: document.getElementById("txtClassroomTransLabel"),
      sentenceText: document.getElementById("classroomSentenceText"),
      koreanTrans: document.getElementById("classroomKoreanTrans"),

      // 파형 캔버스 영역
      waveContainer: document.getElementById("classroomWaveContainer"),
      waveFileName: document.getElementById("classroomWaveFileName"),
      canvas: document.getElementById("classroomWaveCanvas"),
      regionOverlay: document.getElementById("classroomRegionOverlay"),
      regionHighlightBox: document.getElementById("regionHighlightBox"),
      regionTimeLabel: document.getElementById("regionTimeLabel"),
      timecode: document.getElementById("classroomWaveTimecode"),

      // 하단 네비게이션 & 루프
      btnPrevSentence: document.getElementById("btnClassroomPrevSentence"),
      btnPlayPause: document.getElementById("btnClassroomPlayPause"),
      playIcon: document.getElementById("classroomPlayIcon"),
      playText: document.getElementById("classroomPlayText"),
      btnNextSentence: document.getElementById("btnClassroomNextSentence"),
      btnLoopRegion: document.getElementById("btnClassroomLoopRegion"),
      selectLoopCount: document.getElementById("selectClassroomLoopCount"),
      loopBadge: document.getElementById("classroomLoopBadge"),
      btnClearRegion: document.getElementById("btnClassroomClearRegion"),
      selectSpeed: document.getElementById("selectClassroomSpeed"),
      rangeVolume: document.getElementById("rangeClassroomVolume")
    };
  }

  bindEvents() {
    // 닫기 버튼
    this.dom.btnClose?.addEventListener("click", () => this.close());

    // 전체화면 토글
    this.dom.btnFullscreen?.addEventListener("click", () => this.toggleFullscreen());
    document.addEventListener("fullscreenchange", () => {
      this.handleFullscreenChange();
    });

    // 문항 드롭다운 변경
    this.dom.selectQuestion?.addEventListener("change", (e) => {
      const qIdx = parseInt(e.target.value, 10);
      if (!isNaN(qIdx)) {
        this.goToQuestion(qIdx);
      }
    });

    // [약형드랩 모드] <-> [Script 모드] 대형 토글 버튼
    this.dom.btnToggleMode?.addEventListener("click", () => {
      this.textMode = this.textMode === "fels" ? "script" : "fels";
      this.updateSentenceDisplay();
    });

    // [우리말 해석 보기/숨기기] 대형 토글 버튼
    this.dom.btnToggleTrans?.addEventListener("click", () => {
      this.showTrans = !this.showTrans;
      this.updateTranslationDisplay();
    });

    // 약형드랩 텍스트 모드에서 [ ] 클릭 시 해당 빈칸의 정답 보였다/안보였다 토글
    this.dom.sentenceText?.addEventListener("click", (e) => {
      const slotEl = e.target.closest(".fels-blank-slot");
      if (!slotEl) return;
      e.preventDefault();
      e.stopPropagation();

      const slotIdx = parseInt(slotEl.dataset.slotIndex, 10);
      const answer = slotEl.dataset.answer || "";
      if (isNaN(slotIdx)) return;

      if (this.revealedSlots.has(slotIdx)) {
        this.revealedSlots.delete(slotIdx);
        slotEl.classList.remove("revealed");
        slotEl.innerHTML = `[ &nbsp;&nbsp;&nbsp;&nbsp;&nbsp; ]`;
        slotEl.title = "클릭하여 정답 보기";
      } else {
        this.revealedSlots.add(slotIdx);
        slotEl.classList.add("revealed");
        slotEl.innerHTML = `[ ${this.escapeHtml(answer)} ]`;
        slotEl.title = "클릭하여 빈칸으로 가리기";
      }
    });

    // 재생 / 일시정지
    this.dom.btnPlayPause?.addEventListener("click", () => this.togglePlayPause());

    // 이전 / 다음 문장
    this.dom.btnPrevSentence?.addEventListener("click", () => this.prevSentence());
    this.dom.btnNextSentence?.addEventListener("click", () => this.nextSentence());

    // 구간 반복 재생 (A-B Looper)
    this.dom.btnLoopRegion?.addEventListener("click", () => this.startRegionLoop());
    this.dom.btnClearRegion?.addEventListener("click", () => this.clearSelectedRegion());
    this.dom.selectLoopCount?.addEventListener("change", (e) => {
      this.targetLoopCount = parseInt(e.target.value, 10) || 3;
    });

    // 속도 및 볼륨 조절
    this.dom.selectSpeed?.addEventListener("change", (e) => {
      const spd = parseFloat(e.target.value) || 1.0;
      this.audioElement.playbackRate = spd;
    });
    this.dom.rangeVolume?.addEventListener("input", (e) => {
      const vol = parseFloat(e.target.value);
      this.audioElement.volume = isNaN(vol) ? 1.0 : Math.max(0, Math.min(1, vol));
    });

    // 오디오 이벤트
    this.audioElement.addEventListener("ended", () => {
      if (this.isLoopMode) {
        this.handleLoopStep();
      } else {
        this.setPlayingState(false);
      }
    });

    this.audioElement.addEventListener("pause", () => {
      if (!this.isLoopMode) {
        this.setPlayingState(false);
      }
    });

    this.audioElement.addEventListener("play", () => {
      this.setPlayingState(true);
      this.startProgressTracker();
    });

    // 캔버스 마우스 드래그 이벤트 (구간 선택)
    this.bindCanvasDragEvents();

    // 창 리사이즈 시 캔버스 반응형 렌더링
    window.addEventListener("resize", () => {
      if (this.isOpen && this.audioBuffer) {
        this.renderWaveform();
        this.updateRegionOverlay();
      }
    });

    // 전역 단축키 이벤트
    window.addEventListener("keydown", (e) => {
      if (!this.isOpen) return;

      // input, select, textarea 내부 타이핑 중일 때는 단축키 비활성화
      const activeEl = document.activeElement;
      if (activeEl && (activeEl.tagName === "INPUT" || activeEl.tagName === "SELECT" || activeEl.tagName === "TEXTAREA")) {
        if (e.key === "Escape") {
          activeEl.blur();
        }
        return;
      }

      if (e.code === "Space") {
        e.preventDefault();
        this.togglePlayPause();
      } else if (e.code === "ArrowLeft") {
        e.preventDefault();
        this.prevSentence();
      } else if (e.code === "ArrowRight") {
        e.preventDefault();
        this.nextSentence();
      } else if (e.code === "KeyR") {
        e.preventDefault();
        this.startRegionLoop();
      } else if (e.code === "KeyS") {
        e.preventDefault();
        this.textMode = this.textMode === "fels" ? "script" : "fels";
        this.updateSentenceDisplay();
      } else if (e.code === "KeyT") {
        e.preventDefault();
        this.showTrans = !this.showTrans;
        this.updateTranslationDisplay();
      } else if (e.code === "KeyF") {
        e.preventDefault();
        this.toggleFullscreen();
      } else if (e.code === "Escape") {
        e.preventDefault();
        if (document.fullscreenElement) {
          document.exitFullscreen();
        } else {
          this.close();
        }
      }
    });
  }

  /** 캔버스 마우스 드래그 구간 선택 바인딩 */
  bindCanvasDragEvents() {
    const container = this.dom.waveContainer;
    if (!container) return;

    const getRatio = (clientX) => {
      const rect = container.getBoundingClientRect();
      const x = Math.max(0, Math.min(clientX - rect.left, rect.width));
      return rect.width > 0 ? x / rect.width : 0;
    };

    container.addEventListener("mousedown", (e) => {
      if (e.button !== 0) return; // 좌클릭만
      if (e.target.closest("#regionHandleStart") || e.target.closest("#regionHandleEnd")) {
        return; // 핸들 조작은 추후 확장
      }
      this.isDragging = true;
      this.dragStartX = e.clientX;
      this.dragStartRatio = getRatio(e.clientX);
      this.dragCurrentRatio = this.dragStartRatio;

      // 기존 반복 모드 중지
      if (this.isLoopMode) {
        this.stopRegionLoop();
      }
    });

    window.addEventListener("mousemove", (e) => {
      if (!this.isDragging) return;
      this.dragCurrentRatio = getRatio(e.clientX);

      const r1 = Math.min(this.dragStartRatio, this.dragCurrentRatio);
      const r2 = Math.max(this.dragStartRatio, this.dragCurrentRatio);

      // 드래그 중 실시간 오버레이 박스 업데이트
      const duration = this.audioDuration || 1;
      this.selectedRegion = {
        startRatio: r1,
        endRatio: r2,
        startTime: r1 * duration,
        endTime: r2 * duration
      };
      this.updateRegionOverlay();
    });

    window.addEventListener("mouseup", (e) => {
      if (!this.isDragging) return;
      this.isDragging = false;

      const dist = Math.abs(e.clientX - this.dragStartX);
      if (dist < 8) {
        // 단순 클릭: 해당 위치로 재생 위치 탐색(Seek)
        const clickRatio = getRatio(e.clientX);
        const targetTime = clickRatio * (this.audioDuration || 0);
        this.seekTo(targetTime);
        // 작은 클릭 시 선택 영역 해제하지 않고 유지
      } else {
        // 드래그 확정: 최소 0.2초 이상
        if (this.selectedRegion && (this.selectedRegion.endTime - this.selectedRegion.startTime >= 0.2)) {
          this.dom.btnClearRegion.style.display = "inline-flex";
          // 시각적 강조
          this.dom.btnLoopRegion?.classList.add("pulse-highlight");
          setTimeout(() => this.dom.btnLoopRegion?.classList.remove("pulse-highlight"), 1000);
        } else {
          this.clearSelectedRegion();
        }
      }
    });
  }

  /** 선택 영역 오버레이 갱신 */
  updateRegionOverlay() {
    if (!this.selectedRegion || !this.dom.regionOverlay || !this.dom.waveContainer) return;

    const containerWidth = this.dom.waveContainer.clientWidth;
    const leftPx = this.selectedRegion.startRatio * containerWidth;
    const widthPx = Math.max(2, (this.selectedRegion.endRatio - this.selectedRegion.startRatio) * containerWidth);

    this.dom.regionOverlay.style.display = "block";
    this.dom.regionOverlay.style.left = `${leftPx}px`;
    this.dom.regionOverlay.style.width = `${widthPx}px`;

    const sTime = this.formatTimecode(this.selectedRegion.startTime);
    const eTime = this.formatTimecode(this.selectedRegion.endTime);
    const diffSec = (this.selectedRegion.endTime - this.selectedRegion.startTime).toFixed(1);

    if (this.dom.regionTimeLabel) {
      this.dom.regionTimeLabel.textContent = `${sTime} ~ ${eTime} (${diffSec}s)`;
    }
  }

  /** 선택 영역 해제 */
  clearSelectedRegion() {
    this.selectedRegion = null;
    if (this.dom.regionOverlay) {
      this.dom.regionOverlay.style.display = "none";
    }
    if (this.dom.btnClearRegion) {
      this.dom.btnClearRegion.style.display = "none";
    }
    this.stopRegionLoop();
  }

  /** 수업 모달 열기 */
  async open(classroomData) {
    if (!classroomData || !classroomData.questions || classroomData.questions.length === 0) {
      alert("수업을 진행할 듣기 문항 데이터가 없습니다. 먼저 듣기 문항을 유인물 장바구니에 담아주세요.");
      return;
    }

    this.classroomData = classroomData;
    this.isOpen = true;
    this.currentQIndex = 0;
    this.currentSIndex = 0;

    // Web Audio Context 활성화 (사용자 제스처 내에서 활성화)
    if (!this.audioCtx) {
      const AudioCtxClass = window.AudioContext || window.webkitAudioContext;
      if (AudioCtxClass) {
        this.audioCtx = new AudioCtxClass();
      }
    }
    if (this.audioCtx && this.audioCtx.state === "suspended") {
      await this.audioCtx.resume();
    }

    // 헤더 프로젝트명 반영
    if (this.dom.projectTitle) {
      this.dom.projectTitle.textContent = classroomData.project_title || "듣기 프로젝트 수업";
    }

    // 문항 드롭다운 목록 채우기
    this.populateQuestionSelect();

    // 모달 표시
    if (this.dom.modal) {
      this.dom.modal.style.display = "flex";
      document.body.style.overflow = "hidden"; // 배경 스크롤 방지
    }

    // 첫 번째 문항/문장 로드
    await this.loadSentence(0, 0);
  }

  /** 수업 모달 닫기 */
  close() {
    this.isOpen = false;
    this.stopAudio();
    this.stopRegionLoop();

    if (document.fullscreenElement) {
      document.exitFullscreen().catch(() => {});
    }

    if (this.dom.modal) {
      this.dom.modal.style.display = "none";
      document.body.style.overflow = "";
    }
  }

  /** 전체화면 토글 */
  toggleFullscreen() {
    if (!document.fullscreenElement) {
      const target = this.dom.window || this.dom.modal || document.documentElement;
      if (target.requestFullscreen) {
        target.requestFullscreen().catch((err) => {
          console.warn("Fullscreen request failed:", err);
        });
      }
    } else {
      if (document.exitFullscreen) {
        document.exitFullscreen().catch(() => {});
      }
    }
  }

  handleFullscreenChange() {
    const isFull = !!document.fullscreenElement;
    if (this.dom.txtFullscreenIcon) {
      this.dom.txtFullscreenIcon.textContent = isFull ? "🗗" : "⛶";
    }
    setTimeout(() => {
      if (this.isOpen && this.audioBuffer) {
        this.renderWaveform();
        this.updateRegionOverlay();
      }
    }, 150);
  }

  /** 문항 드롭다운 생성 */
  populateQuestionSelect() {
    if (!this.dom.selectQuestion || !this.classroomData) return;
    this.dom.selectQuestion.innerHTML = "";

    this.classroomData.questions.forEach((q, idx) => {
      const opt = document.createElement("option");
      opt.value = idx;
      opt.textContent = `${q.custom_q_num || (idx + 1)}번 (${q.question_type || "듣기"}) - ${q.sentences?.length || 0}문장`;
      this.dom.selectQuestion.appendChild(opt);
    });
  }

  /** 특정 문항으로 점프 */
  async goToQuestion(qIdx) {
    if (qIdx < 0 || qIdx >= this.classroomData.questions.length) return;
    this.currentQIndex = qIdx;
    this.currentSIndex = 0;
    if (this.dom.selectQuestion) {
      this.dom.selectQuestion.value = qIdx;
    }
    await this.loadSentence(this.currentQIndex, this.currentSIndex);
  }

  /** 이전 문장 */
  async prevSentence() {
    if (this.currentSIndex > 0) {
      await this.loadSentence(this.currentQIndex, this.currentSIndex - 1);
    } else if (this.currentQIndex > 0) {
      // 이전 문항의 마지막 문장으로 이동
      const prevQ = this.classroomData.questions[this.currentQIndex - 1];
      const lastSIdx = Math.max(0, (prevQ.sentences?.length || 1) - 1);
      this.currentQIndex--;
      if (this.dom.selectQuestion) this.dom.selectQuestion.value = this.currentQIndex;
      await this.loadSentence(this.currentQIndex, lastSIdx);
    }
  }

  /** 다음 문장 */
  async nextSentence() {
    const currentQ = this.classroomData.questions[this.currentQIndex];
    const totalSentences = currentQ?.sentences?.length || 0;

    if (this.currentSIndex < totalSentences - 1) {
      await this.loadSentence(this.currentQIndex, this.currentSIndex + 1);
    } else if (this.currentQIndex < this.classroomData.questions.length - 1) {
      // 다음 문항의 1번 문장으로 이동
      this.currentQIndex++;
      if (this.dom.selectQuestion) this.dom.selectQuestion.value = this.currentQIndex;
      await this.loadSentence(this.currentQIndex, 0);
    }
  }

  /** 문장 로드 및 파형/오디오 셋업 */
  async loadSentence(qIdx, sIdx) {
    this.stopAudio();
    this.stopRegionLoop();
    this.clearSelectedRegion();
    this.revealedSlots.clear(); // 정답 공개 슬롯 초기화

    this.currentQIndex = qIdx;
    this.currentSIndex = sIdx;

    const q = this.classroomData.questions[qIdx];
    if (!q || !q.sentences || q.sentences.length === 0) {
      this.showEmptyState();
      return;
    }

    const s = q.sentences[sIdx] || q.sentences[0];
    const totalSentences = q.sentences.length;
    const totalQuestions = this.classroomData.questions.length;
    const qNum = q.custom_q_num || (qIdx + 1);

    // 1. 헤더 배지 업데이트
    if (this.dom.posBadge) {
      this.dom.posBadge.textContent = `문항 ${qIdx + 1}/${totalQuestions} (${qNum}번) · 문장 ${sIdx + 1}/${totalSentences}`;
    }

    // 2. 화자 배지 및 유형 업데이트 (W1, M1 등 발화 순번)
    const speaker = (s.speaker || "M").toUpperCase();
    const turnLabel = s.speaker_turn || `${speaker}1`;
    if (this.dom.speakerBadge) {
      this.dom.speakerBadge.textContent = turnLabel;
      this.dom.speakerBadge.className = `classroom-speaker-badge speaker-${speaker.toLowerCase()}`;
    }
    if (this.dom.qType) {
      this.dom.qType.textContent = q.question_type ? `(${q.question_type})` : "";
    }

    // 3. 문장 텍스트 디스플레이 업데이트 (디폴트: 약형드랩 텍스트 먼저 표시)
    this.updateSentenceDisplay();

    // 4. 우리말 해석 뷰 업데이트
    this.updateTranslationDisplay();

    // 5. 상단 라벨
    const projTitleClean = (this.classroomData.project_title || "듣기").replace(/\s+/g, "_");
    const fileName = `${projTitleClean}_${qNum}번_문장${sIdx + 1}.mp3`;
    if (this.dom.waveFileName) {
      this.dom.waveFileName.textContent = fileName;
    }

    // 6. 오디오 소스 결정 및 로드
    // 문장별 캐시 오디오 API 호출: GET /api/handouts/listening/sentence-audio
    const cleanText = s.clean_text || s.raw_text || "";
    const spd = parseFloat(this.dom.selectSpeed?.value || "1.0");
    const audioUrl = `/api/handouts/listening/sentence-audio?text=${encodeURIComponent(cleanText)}&speaker=${speaker}&speed=${spd}`;

    this.currentAudioUrl = audioUrl;
    this.audioElement.src = audioUrl;
    this.audioElement.playbackRate = spd;

    // 타임코드 초기화
    if (this.dom.timecode) {
      this.dom.timecode.textContent = "00:00.0 / 00:00.0";
    }

    // 7. 파형 PCM 데이터 디코딩 & 캔버스 렌더링
    await this.fetchAndRenderWave(audioUrl);
  }

  /** 문장 텍스트 표시 (약형드랩 모드 vs Script 원문 모드) */
  updateSentenceDisplay() {
    const q = this.classroomData?.questions[this.currentQIndex];
    const s = q?.sentences?.[this.currentSIndex];
    if (!s || !this.dom.sentenceText) return;

    const speaker = (s.speaker || "M").toUpperCase();
    const turnLabel = s.speaker_turn || `${speaker}1`;

    if (this.textMode === "fels") {
      // 🎯 약형드랩 모드 (디폴트): [ ] 클릭 시 해당 빈칸 정답 보였다/안보였다 토글
      this.dom.btnToggleMode?.classList.add("active-fels");
      this.dom.btnToggleMode?.classList.remove("active-script");
      if (this.dom.txtModeIcon) this.dom.txtModeIcon.textContent = "🎯";
      if (this.dom.txtModeLabel) this.dom.txtModeLabel.textContent = "약형드랩 모드";

      const sourceText = s.fels_answer_text || s.fels_blank_text || s.clean_text || "";
      let slotCounter = 0;

      // [단어] 또는 [   ] 형태 파싱
      const formatted = sourceText.replace(/\[([^\]]*)\]/g, (match, word) => {
        const slotIdx = slotCounter++;
        const isRevealed = this.revealedSlots.has(slotIdx);
        const ansWord = (word && word.trim()) ? word.trim() : (s.clean_text ? "word" : "");
        const safeAns = this.escapeHtml(ansWord);

        if (isRevealed) {
          return `<span class="fels-blank-slot revealed" data-slot-index="${slotIdx}" data-answer="${safeAns}" title="클릭하여 빈칸으로 숨기기">[ ${safeAns} ]</span>`;
        } else {
          return `<span class="fels-blank-slot" data-slot-index="${slotIdx}" data-answer="${safeAns}" title="클릭하여 정답 보기">[ &nbsp;&nbsp;&nbsp;&nbsp;&nbsp; ]</span>`;
        }
      });

      this.dom.sentenceText.innerHTML = `<span style="color: #60a5fa; font-weight: 800; margin-right: 8px;">${turnLabel}:</span> ${formatted}`;
    } else {
      // 📜 Script 원문 모드
      this.dom.btnToggleMode?.classList.remove("active-fels");
      this.dom.btnToggleMode?.classList.add("active-script");
      if (this.dom.txtModeIcon) this.dom.txtModeIcon.textContent = "📜";
      if (this.dom.txtModeLabel) this.dom.txtModeLabel.textContent = "Script 모드";

      const cleanText = s.clean_text || s.raw_text || "";
      this.dom.sentenceText.innerHTML = `<span style="color: #60a5fa; font-weight: 800; margin-right: 8px;">${turnLabel}:</span> ${this.escapeHtml(cleanText)}`;
    }
  }

  /** 우리말 해석 뷰 업데이트 */
  updateTranslationDisplay() {
    const q = this.classroomData?.questions[this.currentQIndex];
    const s = q?.sentences?.[this.currentSIndex];

    if (this.dom.koreanTrans) {
      this.dom.koreanTrans.style.display = this.showTrans ? "block" : "none";
      const trans = (s?.korean_translation || "").trim();
      this.dom.koreanTrans.textContent = trans || "우리말 해석을 준비 중입니다.";
    }

    if (this.showTrans) {
      this.dom.btnToggleTrans?.classList.add("active");
      if (this.dom.txtTransLabel) this.dom.txtTransLabel.textContent = "우리말 해석 숨기기";
    } else {
      this.dom.btnToggleTrans?.classList.remove("active");
      if (this.dom.txtTransLabel) this.dom.txtTransLabel.textContent = "우리말 해석 보기";
    }
  }

  /** 오디오 바이너리 취득 및 파형 캔버스 렌더링 */
  async fetchAndRenderWave(audioUrl) {
    // 캔버스 초기 로딩 애니메이션
    this.drawLoadingWave();

    try {
      let buffer = this.audioBufferCache.get(audioUrl);
      if (!buffer) {
        const response = await fetch(audioUrl);
        if (!response.ok) {
          throw new Error(`Audio fetch failed: ${response.status}`);
        }
        const arrayBuffer = await response.arrayBuffer();

        if (!this.audioCtx) {
          const AudioCtxClass = window.AudioContext || window.webkitAudioContext;
          this.audioCtx = new AudioCtxClass();
        }
        buffer = await this.audioCtx.decodeAudioData(arrayBuffer);
        this.audioBufferCache.set(audioUrl, buffer);
      }

      this.audioBuffer = buffer;
      this.audioDuration = buffer.duration;

      // 타임코드 전체 길이 갱신
      if (this.dom.timecode) {
        this.dom.timecode.textContent = `00:00.0 / ${this.formatTimecode(this.audioDuration)}`;
      }

      // 파형 렌더링 (첨부 이미지 규격: 딥블루 배경 + 네온 민트 대칭 파형)
      this.renderWaveform(0);
    } catch (err) {
      console.warn("Waveform decode error:", err);
      this.drawErrorWave();
    }
  }

  /** 캔버스 파형 렌더링 함수 (첨부 이미지 스타일 일치) */
  renderWaveform(playedRatio = 0) {
    const canvas = this.dom.canvas;
    const container = this.dom.waveContainer;
    if (!canvas || !container || !this.audioBuffer) return;

    // Retina DPR 보정
    const dpr = window.devicePixelRatio || 1;
    const width = container.clientWidth || 800;
    const height = container.clientHeight || 240;

    canvas.width = width * dpr;
    canvas.height = height * dpr;
    canvas.style.width = `${width}px`;
    canvas.style.height = `${height}px`;

    const ctx = canvas.getContext("2d");
    ctx.scale(dpr, dpr);

    // 1. 딥 블루 배경 그라디언트 (#072540 ~ #0b3b60)
    const bgGrad = ctx.createLinearGradient(0, 0, 0, height);
    bgGrad.addColorStop(0, "#072540");
    bgGrad.addColorStop(0.5, "#092f52");
    bgGrad.addColorStop(1, "#0b3b60");
    ctx.fillStyle = bgGrad;
    ctx.fillRect(0, 0, width, height);

    // 2. 미세 격자 가이드선 (고급 오디오 에디터 느낌)
    ctx.strokeStyle = "rgba(255, 255, 255, 0.05)";
    ctx.lineWidth = 1;
    const midY = height / 2;

    // 중심 수평선
    ctx.beginPath();
    ctx.moveTo(0, midY);
    ctx.lineTo(width, midY);
    ctx.stroke();

    // 3. PCM 데이터 추출 및 채널 샘플링
    const channelData = this.audioBuffer.getChannelData(0);
    const totalSamples = channelData.length;

    // 캔버스 가로 1픽셀 또는 2픽셀 단위로 파형 기둥(Bar) 렌더링
    const barWidth = 2;
    const barGap = 1;
    const totalBars = Math.floor(width / (barWidth + barGap));
    const samplesPerBar = Math.floor(totalSamples / totalBars);

    const playedPx = playedRatio * width;

    for (let i = 0; i < totalBars; i++) {
      const startSample = i * samplesPerBar;
      let min = 1.0;
      let max = -1.0;

      // 서브샘플링으로 min/max 피크 탐색
      const step = Math.max(1, Math.floor(samplesPerBar / 30));
      for (let j = 0; j < samplesPerBar; j += step) {
        const val = channelData[startSample + j];
        if (val < min) min = val;
        if (val > max) max = val;
      }

      if (min === 1.0 && max === -1.0) {
        min = 0;
        max = 0;
      }

      // 대칭 진폭 높이 계산 (중심선 기준)
      const amp = Math.max(0.04, Math.max(Math.abs(min), Math.abs(max)));
      const barHeight = Math.min(midY - 8, amp * (midY - 10));

      const x = i * (barWidth + barGap);
      const isPlayed = x <= playedPx;

      // 파형 색상: 진행된 부분은 선명한 네온 민트(#00ffcc), 미진행 부분은 어두운 틸(#00797b / #00a896 반투명)
      if (isPlayed) {
        ctx.fillStyle = "#00ffcc";
        ctx.shadowColor = "#00ffcc";
        ctx.shadowBlur = 4;
      } else {
        ctx.fillStyle = "rgba(0, 230, 185, 0.42)";
        ctx.shadowColor = "transparent";
        ctx.shadowBlur = 0;
      }

      // 상하 대칭 막대 그리기
      ctx.fillRect(x, midY - barHeight, barWidth, barHeight * 2);
    }

    ctx.shadowBlur = 0; // 리셋

    // 4. 흰색 수직선 플레이헤드 (Current Time Playhead)
    ctx.strokeStyle = "#ffffff";
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    ctx.moveTo(playedPx, 0);
    ctx.lineTo(playedPx, height);
    ctx.stroke();

    // 플레이헤드 상단 역삼각형 인디케이터
    ctx.fillStyle = "#ffffff";
    ctx.beginPath();
    ctx.moveTo(playedPx - 5, 0);
    ctx.lineTo(playedPx + 5, 0);
    ctx.lineTo(playedPx, 7);
    ctx.closePath();
    ctx.fill();
  }

  /** 캔버스 로딩 상태 표시 */
  drawLoadingWave() {
    const canvas = this.dom.canvas;
    const container = this.dom.waveContainer;
    if (!canvas || !container) return;

    const width = container.clientWidth || 800;
    const height = container.clientHeight || 240;
    canvas.width = width;
    canvas.height = height;
    const ctx = canvas.getContext("2d");

    ctx.fillStyle = "#072540";
    ctx.fillRect(0, 0, width, height);

    ctx.fillStyle = "rgba(0, 255, 204, 0.7)";
    ctx.font = "14px Pretendard, sans-serif";
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillText("🎧 오디오 파형 로딩 중...", width / 2, height / 2);
  }

  /** 캔버스 오류 상태 표시 */
  drawErrorWave() {
    const canvas = this.dom.canvas;
    const container = this.dom.waveContainer;
    if (!canvas || !container) return;

    const width = container.clientWidth || 800;
    const height = container.clientHeight || 240;
    const ctx = canvas.getContext("2d");

    ctx.fillStyle = "#072540";
    ctx.fillRect(0, 0, width, height);

    ctx.fillStyle = "rgba(248, 113, 113, 0.85)";
    ctx.font = "14px Pretendard, sans-serif";
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillText("⚠️ 문장 오디오 합성 및 파형 생성에 실패했습니다.", width / 2, height / 2);
  }

  /** 재생 위치 탐색 (Seek) */
  seekTo(seconds) {
    if (isNaN(seconds) || seconds < 0) seconds = 0;
    const duration = this.audioDuration || this.audioElement.duration || 1;
    this.audioElement.currentTime = Math.min(seconds, duration);

    const ratio = Math.min(1, Math.max(0, this.audioElement.currentTime / duration));
    this.renderWaveform(ratio);
    this.updateTimecode(this.audioElement.currentTime, duration);
  }

  /** 재생 / 일시정지 토글 */
  togglePlayPause() {
    if (this.isPlaying) {
      this.pauseAudio();
    } else {
      this.playAudio();
    }
  }

  playAudio() {
    this.audioElement.play().catch((err) => {
      console.warn("Audio play prevented:", err);
    });
  }

  pauseAudio() {
    this.audioElement.pause();
    this.setPlayingState(false);
  }

  stopAudio() {
    try {
      this.audioElement.pause();
      this.audioElement.currentTime = 0;
    } catch (e) {
      // 무시
    }
    this.setPlayingState(false);
    if (this.audioDuration) {
      this.renderWaveform(0);
      this.updateTimecode(0, this.audioDuration);
    }
  }

  setPlayingState(playing) {
    this.isPlaying = playing;
    if (this.dom.playIcon) {
      this.dom.playIcon.textContent = playing ? "⏸" : "▶";
    }
    if (this.dom.playText) {
      this.dom.playText.textContent = playing ? "일시정지" : "재생";
    }
    if (this.dom.btnPlayPause) {
      if (playing) {
        this.dom.btnPlayPause.classList.add("playing");
      } else {
        this.dom.btnPlayPause.classList.remove("playing");
      }
    }
  }

  /** 실시간 재생 진행률 추적 루프 */
  startProgressTracker() {
    if (this.animFrameId) {
      cancelAnimationFrame(this.animFrameId);
    }

    const step = () => {
      if (!this.isPlaying) return;

      const curTime = this.audioElement.currentTime;
      const duration = this.audioDuration || this.audioElement.duration || 1;

      // 1. A-B Looper 구간 반복 검사
      if (this.isLoopMode && this.selectedRegion) {
        if (curTime >= this.selectedRegion.endTime || curTime < this.selectedRegion.startTime - 0.1) {
          this.handleLoopStep();
          this.animFrameId = requestAnimationFrame(step);
          return;
        }
      }

      // 2. 파형 렌더링 갱신
      const ratio = Math.min(1, Math.max(0, curTime / duration));
      this.renderWaveform(ratio);

      // 3. 타임코드 갱신
      this.updateTimecode(curTime, duration);

      this.animFrameId = requestAnimationFrame(step);
    };

    this.animFrameId = requestAnimationFrame(step);
  }

  /** A-B Looper 구간 반복 실행 */
  startRegionLoop() {
    if (!this.selectedRegion) {
      // 선택 영역이 없는 경우 사용자 안내
      alert("먼저 마우스로 파형 창의 원하는 구간을 좌우로 드래그하여 선택해주세요.");
      return;
    }

    this.isLoopMode = true;
    this.currentLoopCount = 1;
    this.targetLoopCount = parseInt(this.dom.selectLoopCount?.value || "3", 10);

    if (this.dom.loopBadge) {
      this.dom.loopBadge.style.display = "inline-flex";
      this.dom.loopBadge.textContent = `반복 1/${this.targetLoopCount >= 999 ? "∞" : this.targetLoopCount}`;
    }
    this.dom.btnLoopRegion?.classList.add("loop-active");

    // 구간 시작점으로 이동 후 재생
    this.audioElement.currentTime = this.selectedRegion.startTime;
    this.playAudio();
  }

  handleLoopStep() {
    if (!this.isLoopMode || !this.selectedRegion) return;

    this.currentLoopCount++;
    if (this.currentLoopCount <= this.targetLoopCount) {
      // 다음 반복 재생
      if (this.dom.loopBadge) {
        this.dom.loopBadge.textContent = `반복 ${this.currentLoopCount}/${this.targetLoopCount >= 999 ? "∞" : this.targetLoopCount}`;
      }
      this.audioElement.currentTime = this.selectedRegion.startTime;
      this.playAudio();
    } else {
      // 목표 반복 횟수 완료
      this.stopRegionLoop();
      this.pauseAudio();
      if (this.dom.loopBadge) {
        this.dom.loopBadge.style.display = "inline-flex";
        this.dom.loopBadge.textContent = `반복 완료 (${this.targetLoopCount}회)`;
        setTimeout(() => {
          if (!this.isLoopMode && this.dom.loopBadge) {
            this.dom.loopBadge.style.display = "none";
          }
        }, 3000);
      }
    }
  }

  stopRegionLoop() {
    this.isLoopMode = false;
    this.dom.btnLoopRegion?.classList.remove("loop-active");
    if (this.dom.loopBadge && this.dom.loopBadge.textContent.indexOf("완료") === -1) {
      this.dom.loopBadge.style.display = "none";
    }
  }

  /** 타임코드 포맷팅 (03:57.1 / 04:12.8) */
  formatTimecode(seconds) {
    if (isNaN(seconds) || seconds < 0) seconds = 0;
    const m = Math.floor(seconds / 60);
    const s = Math.floor(seconds % 60);
    const ms = Math.floor((seconds % 1) * 10);
    const mm = String(m).padStart(2, "0");
    const ss = String(s).padStart(2, "0");
    return `${mm}:${ss}.${ms}`;
  }

  updateTimecode(cur, total) {
    if (this.dom.timecode) {
      this.dom.timecode.textContent = `${this.formatTimecode(cur)} / ${this.formatTimecode(total)}`;
    }
  }

  showEmptyState() {
    if (this.dom.sentenceText) {
      this.dom.sentenceText.textContent = "표시할 문장 데이터가 없습니다.";
    }
  }

  escapeHtml(str) {
    if (!str) return "";
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }
}

// 싱글톤 인스턴스 생성 및 export
export const listeningClassroom = new ListeningClassroomController();

/** 프론트엔드 모듈 초기화 */
export function initListeningClassroom() {
  listeningClassroom.init();
}
