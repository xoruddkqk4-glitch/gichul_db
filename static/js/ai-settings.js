/**
 * 05-gichul_db: AI 설정 모달 (Multi-LLM / OpenRouter 앙상블) (섹션 13) (ai-settings.js)
 * - main.js 에서 분리
 */

import {
  aiSettingsModal,
  btnCancelAiSettings,
  btnCloseAiSettingsModal,
  btnOpenAiSettingsModal,
  btnRefreshAllOR,
  btnRefreshOpenRouter,
  btnSaveAiSettings,
  cbOREnsembleEl,
  openrouterInputEl,
  openrouterSelectEl,
  selectConsensusModeEl,
} from "./dom.js";
import { escapeHtml, showToast } from "./utils.js";

let openrouterTopModelsData = [];
let openrouterAllModelsData = [];
let currentEnsembleModels = [
  "deepseek/deepseek-chat",
  "openai/gpt-4o-mini",
  "anthropic/claude-sonnet-4.5"
];
// =========================================================================
// 13. AI 설정 모달 (Multi-LLM: Gemini / ChatGPT / Claude / OpenRouter)
// =========================================================================

const ALL_PROVIDERS = ["gemini", "openai", "claude", "openrouter"];

const providerDisplayNames = {
  gemini: "Google Gemini",
  openai: "OpenAI ChatGPT",
  claude: "Anthropic Claude",
  openrouter: "OpenRouter",
};

const providerShortNames = {
  gemini: "Gemini",
  openai: "GPT",
  claude: "Claude",
  openrouter: "OpenRouter",
};

function capitalize(str) {
  if (!str) return "";
  return str.charAt(0).toUpperCase() + str.slice(1);
}

/** OpenRouter 선택 모델 상세 정보 카드 렌더링 */
function renderOpenRouterModelCard(model) {
  const card = document.getElementById("openrouterModelInfoCard");
  if (!card) return;
  if (!model) {
    card.style.display = "none";
    return;
  }
  card.style.display = "flex";
  const badge = document.getElementById("infoModelBadge");
  const name = document.getElementById("infoModelName");
  const tag = document.getElementById("infoModelTag");
  const promptPrice = document.getElementById("infoModelPromptPrice");
  const compPrice = document.getElementById("infoModelCompletionPrice");

  if (badge) badge.textContent = model.badge || "추천";
  if (name) name.textContent = model.name || model.id;
  if (tag) tag.textContent = model.tag || "";
  if (promptPrice) promptPrice.textContent = model.prompt_price || "-";
  if (compPrice) compPrice.textContent = model.completion_price || "-";
}

/** OpenRouter Top 5 모델 드랍다운 옵션 생성 및 현재 입력값과 동기화 */
function renderOpenRouterModelSelectOptions() {
  const select = document.getElementById("openrouterModelSelect");
  const input = document.getElementById("modelInputOpenrouter");
  if (!select) return;
  select.innerHTML = "";

  const curModel = (input ? input.value.trim() : "") || "deepseek/deepseek-chat";
  let matched = false;

  openrouterTopModelsData.forEach((m) => {
    const opt = document.createElement("option");
    opt.value = m.id;
    opt.textContent = `${m.badge} ${m.name} [${m.tag} | ${m.prompt_price}]`;
    if (m.id === curModel) {
      opt.selected = true;
      matched = true;
      renderOpenRouterModelCard(m);
    }
    select.appendChild(opt);
  });

  const customOpt = document.createElement("option");
  customOpt.value = "custom";
  customOpt.textContent = "✏️ 직접 입력 (커스텀 모델명 지정)";
  if (!matched && curModel) {
    customOpt.selected = true;
    renderOpenRouterModelCard(null);
  }
  select.appendChild(customOpt);

  if (!matched && !curModel && openrouterTopModelsData.length > 0) {
    select.selectedIndex = 0;
    const firstM = openrouterTopModelsData[0];
    if (input) input.value = firstM.id;
    renderOpenRouterModelCard(firstM);
  }
}

/** OpenRouter Top 5 모델 목록 서버 조회 */
async function loadOpenRouterTopModels(force = false) {
  const btn = document.getElementById("btnRefreshOpenRouterModels");
  if (btn) {
    btn.disabled = true;
    btn.textContent = "⏳ 갱신 중...";
  }
  try {
    const res = await fetch(`/api/openrouter/top-models${force ? "?force_refresh=true" : ""}`);
    const data = await res.json();
    if (res.ok && data.models && data.models.length > 0) {
      openrouterTopModelsData = data.models;
      renderOpenRouterModelSelectOptions();
      if (force) {
        showToast("OpenRouter 최신 Top 5 모델 정보가 갱신되었습니다.", "success");
      }
    }
  } catch (err) {
    console.error("OpenRouter 모델 목록 로드 실패:", err);
    if (force) {
      showToast("OpenRouter 모델 정보를 불러오지 못했습니다.", "warning");
    }
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.textContent = "🔄 갱신";
    }
  }
}

function getModelDisplayShortName(id) {
  if (!id) return "";
  const map = {
    "deepseek/deepseek-chat": "DeepSeek V3",
    "deepseek/deepseek-r1": "DeepSeek R1",
    "openai/gpt-4o-mini": "GPT-4o-mini",
    "openai/gpt-4o": "GPT-4o",
    "anthropic/claude-sonnet-4.5": "Claude Sonnet 4.5",
    "anthropic/claude-3-5-haiku-20241022": "Claude 3.5 Haiku",
    "google/gemini-2.5-flash": "Gemini 2.5 Flash",
    "google/gemini-2.5-pro": "Gemini 2.5 Pro",
    "meta-llama/llama-3.3-70b-instruct": "Llama 3.3 70B",
    "mistralai/mistral-large-2411": "Mistral Large",
    "qwen/qwen-2.5-72b-instruct": "Qwen 2.5 72B"
  };
  if (map[id]) return map[id];
  const found = openrouterAllModelsData.find((m) => m.id === id);
  if (found && found.name) return found.name;
  return id.includes("/") ? id.split("/")[1] : id;
}

/** OpenRouter 전체 440+ 실시간 모델 목록 서버 조회 */
async function loadOpenRouterAllModels(force = false) {
  const btn = document.getElementById("btnRefreshOpenRouterAllModels");
  const countBadge = document.getElementById("ensembleModelsCountBadge");
  if (btn) {
    btn.disabled = true;
    btn.textContent = "⏳ 갱신 중...";
  }
  if (countBadge) {
    countBadge.textContent = "실시간 로딩 중...";
  }

  try {
    const res = await fetch(`/api/openrouter/models${force ? "?force_refresh=true" : ""}`);
    const data = await res.json();
    if (res.ok && data.models && data.models.length > 0) {
      openrouterAllModelsData = data.models;
      if (data.current_ensemble && data.current_ensemble.length >= 3 && !force) {
        currentEnsembleModels = data.current_ensemble.slice(0, 3);
      }
      if (countBadge) {
        countBadge.textContent = `${openrouterAllModelsData.length}개 모델 로드됨`;
      }
      renderOpenRouterEnsembleSlots();
      if (force) {
        showToast(`OpenRouter 전체 ${openrouterAllModelsData.length}개 모델 목록이 갱신되었습니다.`, "success");
      }
    }
  } catch (err) {
    console.error("OpenRouter 전체 모델 목록 로드 실패:", err);
    if (countBadge) {
      countBadge.textContent = "목록 로드 실패 (기본값 사용)";
    }
    if (force) {
      showToast("OpenRouter 모델 목록을 불러오지 못했습니다.", "warning");
    }
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.textContent = "🔄 모델 갱신";
    }
  }
}

/** OpenRouter 앙상블 3개 슬롯 옵션 및 선택값 렌더링 */
function renderOpenRouterEnsembleSlots() {
  const defaultModels = [
    "deepseek/deepseek-chat",
    "openai/gpt-4o-mini",
    "anthropic/claude-sonnet-4.5"
  ];

  const popularIds = [
    "deepseek/deepseek-chat",
    "openai/gpt-4o-mini",
    "anthropic/claude-sonnet-4.5",
    "openai/gpt-4o",
    "google/gemini-2.5-flash",
    "meta-llama/llama-3.3-70b-instruct",
    "mistralai/mistral-large-2411",
    "qwen/qwen-2.5-72b-instruct",
    "anthropic/claude-3-5-haiku-20241022",
    "deepseek/deepseek-r1"
  ];

  for (let slotIdx = 0; slotIdx < 3; slotIdx++) {
    const select = document.getElementById(`openrouterSlotSelect${slotIdx}`);
    const customInput = document.getElementById(`openrouterSlotCustom${slotIdx}`);
    if (!select) continue;

    select.innerHTML = "";
    const curVal = currentEnsembleModels[slotIdx] || defaultModels[slotIdx];
    let isMatchedInList = false;

    // 1. 추천/인기 모델 optgroup
    const grpPopular = document.createElement("optgroup");
    grpPopular.label = "⭐ 인기 & 추천 모델";

    // 2. 공급사별 optgroup
    const groups = {
      deepseek: document.createElement("optgroup"),
      openai: document.createElement("optgroup"),
      anthropic: document.createElement("optgroup"),
      google: document.createElement("optgroup"),
      "meta-llama": document.createElement("optgroup"),
      mistralai: document.createElement("optgroup"),
      qwen: document.createElement("optgroup"),
      other: document.createElement("optgroup")
    };
    groups.deepseek.label = "DeepSeek";
    groups.openai.label = "OpenAI";
    groups.anthropic.label = "Anthropic Claude";
    groups.google.label = "Google Gemini";
    groups["meta-llama"].label = "Meta Llama";
    groups.mistralai.label = "Mistral AI";
    groups.qwen.label = "Qwen";
    groups.other.label = "기타 제공사 모델";

    const sourceList = openrouterAllModelsData.length > 0 ? openrouterAllModelsData : [
      { id: "deepseek/deepseek-chat", name: "DeepSeek: DeepSeek V3", prompt_price: "$0.32/1M", provider: "deepseek", context_length: "160k" },
      { id: "openai/gpt-4o-mini", name: "OpenAI: GPT-4o-mini", prompt_price: "$0.15/1M", provider: "openai", context_length: "128k" },
      { id: "anthropic/claude-sonnet-4.5", name: "Anthropic: Claude Sonnet 4.5", prompt_price: "$3.00/1M", provider: "anthropic", context_length: "976k" },
      { id: "openai/gpt-4o", name: "OpenAI: GPT-4o", prompt_price: "$2.50/1M", provider: "openai", context_length: "128k" },
      { id: "google/gemini-2.5-flash", name: "Google: Gemini 2.5 Flash", prompt_price: "$0.07/1M", provider: "google", context_length: "1000k" },
      { id: "meta-llama/llama-3.3-70b-instruct", name: "Meta: Llama 3.3 70B Instruct", prompt_price: "$0.10/1M", provider: "meta-llama", context_length: "128k" }
    ];

    sourceList.forEach((m) => {
      if (popularIds.includes(m.id)) {
        const opt = document.createElement("option");
        opt.value = m.id;
        opt.textContent = `${m.name} (${m.prompt_price || ""})`;
        if (m.id === curVal) {
          opt.selected = true;
          isMatchedInList = true;
        }
        grpPopular.appendChild(opt);
      }
    });
    if (grpPopular.children.length > 0) {
      select.appendChild(grpPopular);
    }

    sourceList.forEach((m) => {
      const opt = document.createElement("option");
      opt.value = m.id;
      opt.textContent = `${m.name} (${m.prompt_price || ""})`;
      if (m.id === curVal && !isMatchedInList) {
        opt.selected = true;
        isMatchedInList = true;
      }
      const prov = m.provider ? m.provider.toLowerCase() : "other";
      const targetGrp = groups[prov] || groups.other;
      targetGrp.appendChild(opt);
    });

    Object.values(groups).forEach((grp) => {
      if (grp.children.length > 0) {
        select.appendChild(grp);
      }
    });

    const optCustom = document.createElement("option");
    optCustom.value = "__custom__";
    optCustom.textContent = "✏️ 직접 모델 ID 입력...";
    if (!isMatchedInList && curVal) {
      optCustom.selected = true;
    }
    select.appendChild(optCustom);

    if (customInput) {
      customInput.value = curVal;
      customInput.style.display = (!isMatchedInList && curVal) || select.value === "__custom__" ? "block" : "none";
    }
    updateSlotBadge(slotIdx, curVal);
  }
}

function updateSlotBadge(slotIdx, modelId) {
  const badge = document.getElementById(`openrouterSlotBadge${slotIdx}`);
  if (!badge) return;
  const found = openrouterAllModelsData.find((m) => m.id === modelId);
  if (found) {
    badge.textContent = `${found.prompt_price || ""} • ${found.context_length || ""}`;
  } else {
    badge.textContent = modelId.includes("/") ? modelId.split("/")[1] : modelId;
  }
}

function getSelectedOpenRouterEnsembleModels() {
  const res = [];
  const fallbacks = ["deepseek/deepseek-chat", "openai/gpt-4o-mini", "anthropic/claude-sonnet-4.5"];
  for (let slotIdx = 0; slotIdx < 3; slotIdx++) {
    const select = document.getElementById(`openrouterSlotSelect${slotIdx}`);
    const customInput = document.getElementById(`openrouterSlotCustom${slotIdx}`);
    let val = "";
    if (select && select.value !== "__custom__") {
      val = select.value;
    } else if (customInput) {
      val = customInput.value.trim();
    }
    if (!val) {
      val = currentEnsembleModels[slotIdx] || fallbacks[slotIdx];
    }
    res.push(val);
  }
  return res;
}

// AI 설정 상태 헤더 버튼 반영 (단일 모델 vs 복수 모델 교차 검증 디자인)
function updateAiHeaderButton(data) {
  if (!btnOpenAiSettingsModal) return;
  if (!data) {
    btnOpenAiSettingsModal.classList.remove("api-active");
    btnOpenAiSettingsModal.innerHTML = `🔑 AI 설정`;
    return;
  }

  const activeList = data.active_providers || (data.provider ? [data.provider] : []);
  const providers = data.providers || {};
  // 활성 모델 중 키가 등록된 모델들 필터링
  const activeWithKeys = activeList.filter((p) => {
    if (providers[p] && providers[p].has_key) return true;
    if (p === data.provider && data.has_key) return true;
    return false;
  });

  if (activeWithKeys.length === 0) {
    btnOpenAiSettingsModal.classList.remove("api-active");
    btnOpenAiSettingsModal.innerHTML = `🔑 AI 설정`;
    btnOpenAiSettingsModal.title = "AI 어법 분석기 및 ElevenLabs TTS 설정 (Gemini/ChatGPT/Claude/OpenRouter/ElevenLabs)";
  } else if (activeWithKeys.length === 1) {
    const p = activeWithKeys[0];
    const name = providerShortNames[p] || p;
    btnOpenAiSettingsModal.classList.add("api-active");
    if (p === "openrouter" && data.openrouter_ensemble) {
      const mNames = (data.openrouter_ensemble_models || currentEnsembleModels || []).map(m => getModelDisplayShortName(m)).join(", ");
      btnOpenAiSettingsModal.innerHTML = `<span class="ai-status-pulse-dot"></span>⚡ AI 설정 <span class="ai-active-badge">OpenRouter 3모델 합의</span>`;
      btnOpenAiSettingsModal.title = `AI 설정 (OpenRouter 3개 모델[${mNames}] 교차 검증 활성화됨) - 클릭하여 AI 설정 및 ElevenLabs 키 입력`;
    } else {
      btnOpenAiSettingsModal.innerHTML = `<span class="ai-status-pulse-dot"></span>⚡ AI 설정 <span class="ai-active-badge">${escapeHtml(name)}</span>`;
      btnOpenAiSettingsModal.title = `AI 설정 (${name} 활성화됨) - 클릭하여 AI 설정 및 ElevenLabs 키 입력`;
    }
  } else {
    const names = activeWithKeys.map((p) => providerShortNames[p] || p).join(" + ");
    btnOpenAiSettingsModal.classList.add("api-active");
    btnOpenAiSettingsModal.innerHTML = `<span class="ai-status-pulse-dot"></span>⚡ AI 설정 <span class="ai-active-badge">${escapeHtml(names)}</span>`;
    btnOpenAiSettingsModal.title = `AI 설정 (다수결 합의 [${names}] 활성화됨) - 클릭하여 AI 설정 및 ElevenLabs 키 입력`;
  }
}

export async function refreshAiStatusIndicator() {
  if (!btnOpenAiSettingsModal) return;
  try {
    const res = await fetch("/api/settings/ai");
    if (res.ok) {
      const data = await res.json();
      updateAiHeaderButton(data);
      return data;
    }
  } catch (e) {
    console.warn("AI 설정 상태 조회 실패:", e);
  }
}

/** 모달 하단 선택 현황 요약 텍스트 갱신 */
function updateAiModalSelectionSummary() {
  const summary = document.getElementById("aiModalSelectionSummary");
  const badge = document.getElementById("aiEnsembleModeBadge");
  const modeSelect = document.getElementById("selectConsensusMode");
  const mode = modeSelect ? modeSelect.value : "majority";
  if (!summary) return;

  const checkedBoxes = Array.from(document.querySelectorAll(".provider-checkbox:checked"));
  const count = checkedBoxes.length;

  let modeDesc = "다수결 합의";
  let badgeText = "🗳️ 다수결 합의 모드";
  if (mode === "strict") {
    modeDesc = "엄격 전원 일치";
    badgeText = `🛡️ 엄격 전원 일치 (${count}/${count})`;
  } else if (mode === "at_least_2") {
    modeDesc = "2개 이상 모델 합의";
    badgeText = `🤝 2개 모델 이상 합의`;
  } else {
    const needed = Math.max(2, Math.floor(count / 2) + 1);
    modeDesc = `과반수(${needed}개 이상) 찬성 합의`;
    badgeText = `🗳️ 다수결 합의 (${count}개 중 ${needed}개+ 찬성)`;
  }

  const cbOREnsemble = document.getElementById("cbOpenRouterEnsemble");
  const isOREnsemble = cbOREnsemble && cbOREnsemble.checked;

  if (count === 0) {
    summary.innerHTML = `<span style="color: #dc2626;">⚠️ 선택된 모델이 없습니다. 최소 1개 이상 선택해 주세요.</span>`;
    if (badge) badge.textContent = "비활성";
  } else if (count === 1) {
    const p = checkedBoxes[0].dataset.provider;
    const name = providerDisplayNames[p] || p;
    if (p === "openrouter" && isOREnsemble) {
      const shortNames = currentEnsembleModels.map(m => getModelDisplayShortName(m)).join(" + ");
      summary.innerHTML = `선택된 모델: <strong>OpenRouter 3개 모델 앙상블</strong> (${escapeHtml(shortNames)} 교차 검증)`;
      if (badge) {
        badge.textContent = "🔄 OpenRouter 3모델 합의";
        badge.className = "ai-ensemble-badge";
      }
    } else {
      summary.innerHTML = `선택된 모델: <strong>${escapeHtml(name)}</strong> (단독 분석 모드)`;
      if (badge) badge.textContent = "단독 실행 모드";
    }
  } else {
    const names = checkedBoxes.map((cb) => {
      const p = cb.dataset.provider;
      if (p === "openrouter" && isOREnsemble) return "OpenRouter(3모델)";
      return providerShortNames[p] || p;
    }).join(", ");
    summary.innerHTML = `선택된 모델: <strong>${escapeHtml(names)}</strong> (${count}개 모델 ${modeDesc})`;
    if (badge) badge.textContent = badgeText;
  }
}

async function openAiSettingsModal() {
  if (!aiSettingsModal) return;
  const statusDiv = document.getElementById("aiSettingsStatus");
  if (statusDiv) statusDiv.style.display = "none";

  try {
    const res = await fetch("/api/settings/ai");
    if (res.ok) {
      const data = await res.json();
      updateAiHeaderButton(data);

      const activeSet = new Set(data.active_providers || (data.provider ? [data.provider] : ["gemini"]));
      const providers = data.providers || {};

      ALL_PROVIDERS.forEach((p) => {
        const pCap = capitalize(p);
        const pData = providers[p] || {};
        const cb = document.getElementById(`cbProvider${pCap}`);
        const card = document.getElementById(`cardProvider${pCap}`);
        const badge = document.getElementById(`badgeProvider${pCap}`);
        const modelInput = document.getElementById(`modelInput${pCap}`);
        const keyStatus = document.getElementById(`keyStatus${pCap}`);
        const keyInput = document.getElementById(`keyInput${pCap}`);
        const testRes = document.getElementById(`testResult${pCap}`);

        const isActive = activeSet.has(p);
        if (cb) cb.checked = isActive;
        if (card) card.classList.toggle("active", isActive);
        if (badge) {
          badge.textContent = isActive ? "활성" : "비활성";
          badge.classList.toggle("active", isActive);
        }
        if (modelInput) {
          const retired = ["gemini-1.5-flash", "gemini-1.5-flash-latest", "gemini-2.0-flash", "gemini-2.5-flash"];
          if (p === "gemini" && (!pData.model || retired.includes(pData.model))) {
            modelInput.value = "gemini-3.6-flash";
          } else if (pData.model) {
            modelInput.value = pData.model;
          }
        }
        if (keyInput) keyInput.value = "";
        if (keyStatus) {
          if (pData.has_key) {
            keyStatus.textContent = `현재 키: ${pData.masked_key} (등록됨)`;
            keyStatus.style.color = "#059669";
          } else {
            keyStatus.textContent = "현재 키: 미등록";
            keyStatus.style.color = "#64748b";
          }
        }
        if (testRes) {
          if (pData.has_key) {
            testRes.className = "provider-test-result info visible";
            testRes.innerHTML = `<span>ℹ️ <strong>키 등록됨:</strong> [🧪 개별 연결 테스트]를 클릭하여 실시간 API 통신을 확인해 보세요.</span>`;
          } else {
            testRes.className = "provider-test-result info visible";
            testRes.innerHTML = `<span>⚠️ <strong>키 미등록:</strong> API Key를 입력한 후 [🧪 개별 연결 테스트]를 진행해 주세요.</span>`;
          }
        }
      });

      // 합의 방식 셀렉트 동기화
      const selectConsensusMode = document.getElementById("selectConsensusMode");
      if (selectConsensusMode && data.consensus_mode) {
        selectConsensusMode.value = data.consensus_mode;
      }

      // OpenRouter 앙상블 상태 및 단일 모델 잠금 UI 동기화
      if (data.openrouter_ensemble_models && data.openrouter_ensemble_models.length >= 3) {
        currentEnsembleModels = data.openrouter_ensemble_models.slice(0, 3);
      }
      applyOpenRouterEnsembleUI(Boolean(data.openrouter_ensemble));

      // OpenRouter 전체 모델 및 앙상블 슬롯 동기화
      if (openrouterAllModelsData.length === 0) {
        loadOpenRouterAllModels(false);
      } else {
        renderOpenRouterEnsembleSlots();
      }

      // OpenRouter Top 5 모델 동기화
      if (openrouterTopModelsData.length === 0) {
        loadOpenRouterTopModels(false);
      } else {
        renderOpenRouterModelSelectOptions();
      }

      // TTS 설정 동기화 (Edge-TTS 및 ElevenLabs)
      const ttsData = data.tts || {};
      const ttsEngine = ttsData.engine || "edge-tts";
      appState.ttsEngine = ttsEngine;
      const badgeTopRight = document.getElementById("badgeTopRightSource");
      if (badgeTopRight && (appState.currentArea === "listening" || (appState.passagesData[appState.currentPassageIndex]?.area === "listening"))) {
        badgeTopRight.textContent = (ttsEngine === "elevenlabs") ? "ElevenLabs TTS" : "Edge-TTS (무료)";
      }

      const radioEdge = document.getElementById("radioTtsEdge");
      const radioElevenlabs = document.getElementById("radioTtsElevenlabs");
      const cardEdge = document.getElementById("cardEdgeTts");
      const cardEleven = document.getElementById("cardElevenlabs");

      if (radioEdge && radioElevenlabs) {
        if (ttsEngine === "elevenlabs") {
          radioElevenlabs.checked = true;
          if (cardEdge) cardEdge.style.display = "none";
          if (cardEleven) cardEleven.style.display = "block";
        } else {
          radioEdge.checked = true;
          if (cardEdge) cardEdge.style.display = "block";
          if (cardEleven) cardEleven.style.display = "none";
        }
      }

      // Edge-TTS 설정 UI 반영
      const edgeCfg = ttsData.edge_tts || {};
      const selEdgeMale = document.getElementById("selectEdgeTtsVoiceMale");
      const selEdgeFemale = document.getElementById("selectEdgeTtsVoiceFemale");
      const selEdgeRate = document.getElementById("selectEdgeTtsRate");
      if (selEdgeMale && edgeCfg.voice_male) selEdgeMale.value = edgeCfg.voice_male;
      if (selEdgeFemale && edgeCfg.voice_female) selEdgeFemale.value = edgeCfg.voice_female;
      if (selEdgeRate && edgeCfg.rate) selEdgeRate.value = edgeCfg.rate;

      // ElevenLabs TTS 설정 동기화
      const elData = ttsData.elevenlabs || data.elevenlabs || {};
      const keyStatusEl = document.getElementById("keyStatusElevenlabs");
      const keyInputEl = document.getElementById("keyInputElevenlabs");
      const voiceMaleEl = document.getElementById("voiceInputElevenlabsMale");
      const voiceFemaleEl = document.getElementById("voiceInputElevenlabsFemale");
      const modelEl = document.getElementById("modelInputElevenlabs");
      const testResEl = document.getElementById("testResultElevenlabs");

      if (keyInputEl) keyInputEl.value = "";
      if (keyStatusEl) {
        if (elData.has_key) {
          keyStatusEl.textContent = `현재 키: ${elData.masked_key} (등록됨)`;
          keyStatusEl.style.color = "#059669";
        } else {
          keyStatusEl.textContent = "현재 키: 미등록";
          keyStatusEl.style.color = "#64748b";
        }
      }
      if (voiceMaleEl && elData.voice_male) voiceMaleEl.value = elData.voice_male;
      if (voiceFemaleEl && elData.voice_female) voiceFemaleEl.value = elData.voice_female;
      if (modelEl && elData.model_id) modelEl.value = elData.model_id;
      if (testResEl) {
        if (elData.has_key) {
          testResEl.className = "provider-test-result info visible";
          testResEl.innerHTML = `<span>ℹ️ <strong>ElevenLabs 키 등록됨:</strong> [🧪 개별 연결 테스트]를 클릭하여 실시간 API 통신 및 잔여 크레딧을 확인해 보세요.</span>`;
        } else {
          testResEl.className = "provider-test-result info visible";
          testResEl.innerHTML = `<span>⚠️ <strong>ElevenLabs 키 미등록:</strong> API Key를 입력한 후 저장하면 영어 듣기 TTS 생성이 활성화됩니다.</span>`;
        }
      }

      updateAiModalSelectionSummary();
    }
  } catch (e) {
    console.error(e);
  }
  aiSettingsModal.style.display = "flex";
}

function closeAiSettingsModal() {
  if (aiSettingsModal) aiSettingsModal.style.display = "none";
  ALL_PROVIDERS.forEach((p) => {
    const keyInput = document.getElementById(`keyInput${capitalize(p)}`);
    if (keyInput) keyInput.value = "";
  });
  const elKeyInput = document.getElementById("keyInputElevenlabs");
  if (elKeyInput) elKeyInput.value = "";
}

// OpenRouter 앙상블 모드 UI 반영 공통 함수 (3개 모델 앙상블 활성화 시 단일 모델 선택/직접입력 잠금)
function applyOpenRouterEnsembleUI(isEnabled) {
  const cbOREnsemble = document.getElementById("cbOpenRouterEnsemble");
  const containerOREnsemble = document.getElementById("openrouterEnsembleModelsContainer");
  const singleModelGroup = document.getElementById("openrouterSingleModelGroup");
  const lockNotice = document.getElementById("ensembleLockNotice");
  const modelInput = document.getElementById("modelInputOpenrouter");
  const modelSelect = document.getElementById("openrouterModelSelect");
  const btnRefresh = document.getElementById("btnRefreshOpenRouterModels");

  if (cbOREnsemble) cbOREnsemble.checked = Boolean(isEnabled);
  if (containerOREnsemble) {
    containerOREnsemble.style.display = isEnabled ? "block" : "none";
  }
  if (lockNotice) {
    lockNotice.style.display = isEnabled ? "flex" : "none";
  }
  if (singleModelGroup) {
    singleModelGroup.classList.toggle("is-disabled", Boolean(isEnabled));
  }
  if (modelInput) modelInput.disabled = Boolean(isEnabled);
  if (modelSelect) modelSelect.disabled = Boolean(isEnabled);
  if (btnRefresh) btnRefresh.disabled = Boolean(isEnabled);

  updateAiModalSelectionSummary();
}

// ---- 이벤트 바인딩 및 초기화 (main.js 에서 원본 순서대로 호출) ----
export function init() {
  if (openrouterSelectEl) {
    openrouterSelectEl.addEventListener("change", () => {
      const selectedVal = openrouterSelectEl.value;
      const input = document.getElementById("modelInputOpenrouter");
      if (selectedVal === "custom") {
        renderOpenRouterModelCard(null);
        if (input) input.focus();
      } else {
        const found = openrouterTopModelsData.find((m) => m.id === selectedVal);
        if (found) {
          if (input) input.value = found.id;
          renderOpenRouterModelCard(found);
        }
      }
    });
  }
  if (btnRefreshOpenRouter) {
    btnRefreshOpenRouter.addEventListener("click", () => {
      loadOpenRouterTopModels(true);
    });
  }
  if (openrouterInputEl) {
    openrouterInputEl.addEventListener("input", () => {
      const select = document.getElementById("openrouterModelSelect");
      if (!select) return;
      const val = openrouterInputEl.value.trim();
      const found = openrouterTopModelsData.find((m) => m.id === val);
      if (found) {
        select.value = found.id;
        renderOpenRouterModelCard(found);
      } else {
        select.value = "custom";
        renderOpenRouterModelCard(null);
      }
    });
  }
  if (cbOREnsembleEl) {
    cbOREnsembleEl.addEventListener("change", () => {
      applyOpenRouterEnsembleUI(cbOREnsembleEl.checked);
      if (cbOREnsembleEl.checked && openrouterAllModelsData.length === 0) {
        loadOpenRouterAllModels(false);
      }
    });
  }

  // 앙상블 3개 슬롯 변경 및 커스텀 입력 이벤트 바인딩
  for (let slotIdx = 0; slotIdx < 3; slotIdx++) {
    const select = document.getElementById(`openrouterSlotSelect${slotIdx}`);
    const customInput = document.getElementById(`openrouterSlotCustom${slotIdx}`);
    if (select) {
      select.addEventListener("change", () => {
        if (select.value === "__custom__") {
          if (customInput) {
            customInput.style.display = "block";
            customInput.focus();
          }
        } else {
          if (customInput) {
            customInput.style.display = "none";
            customInput.value = select.value;
          }
          currentEnsembleModels[slotIdx] = select.value;
          updateSlotBadge(slotIdx, select.value);
          updateAiModalSelectionSummary();
        }
      });
    }
    if (customInput) {
      customInput.addEventListener("input", () => {
        const val = customInput.value.trim();
        if (val) {
          currentEnsembleModels[slotIdx] = val;
          updateSlotBadge(slotIdx, val);
          updateAiModalSelectionSummary();
        }
      });
    }
  }

  // 앙상블 빠른 프리셋 버튼 이벤트
  document.querySelectorAll(".btn-preset-ensemble").forEach((btn) => {
    btn.addEventListener("click", () => {
      const preset = btn.dataset.preset;
      let targetModels = [];
      let label = "";
      if (preset === "default") {
        targetModels = ["deepseek/deepseek-chat", "openai/gpt-4o-mini", "anthropic/claude-sonnet-4.5"];
        label = "추천 기본 (DeepSeek V3 + GPT-4o-mini + Claude Sonnet 4.5)";
      } else if (preset === "budget") {
        targetModels = ["deepseek/deepseek-chat", "openai/gpt-4o-mini", "meta-llama/llama-3.3-70b-instruct"];
        label = "초가성비 (DeepSeek V3 + GPT-4o-mini + Llama 3.3 70B)";
      } else if (preset === "quality") {
        targetModels = ["anthropic/claude-sonnet-4.5", "openai/gpt-4o", "google/gemini-2.5-flash"];
        label = "최고정밀 (Claude Sonnet 4.5 + GPT-4o + Gemini 2.5 Flash)";
      }
      if (targetModels.length === 3) {
        currentEnsembleModels = [...targetModels];
        renderOpenRouterEnsembleSlots();
        showToast(`${label} 프리셋이 적용되었습니다.`, "info");
      }
    });
  });
  if (btnRefreshAllOR) {
    btnRefreshAllOR.addEventListener("click", () => {
      loadOpenRouterAllModels(true);
    });
  }

  // 체크박스 클릭 시 카드 스타일 및 요약 업데이트
  document.querySelectorAll(".provider-checkbox").forEach((cb) => {
    cb.addEventListener("change", () => {
      const p = cb.dataset.provider;
      const pCap = capitalize(p);
      const card = document.getElementById(`cardProvider${pCap}`);
      const badge = document.getElementById(`badgeProvider${pCap}`);
      if (card) card.classList.toggle("active", cb.checked);
      if (badge) {
        badge.textContent = cb.checked ? "활성" : "비활성";
        badge.classList.toggle("active", cb.checked);
      }
      updateAiModalSelectionSummary();
    });
  });

  // 키 표시/숨김 토글 버튼 바인딩
  document.querySelectorAll(".btn-toggle-key-vis").forEach((btn) => {
    btn.addEventListener("click", () => {
      const targetId = btn.dataset.target;
      const input = document.getElementById(targetId);
      if (input) {
        const isPwd = input.type === "password";
        input.type = isPwd ? "text" : "password";
        btn.textContent = isPwd ? "🙈" : "👁️";
      }
    });
  });

  // 개별 프로바이더 연결 테스트 버튼 바인딩
  document.querySelectorAll(".btn-test-provider").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const p = btn.dataset.provider;
      const pCap = capitalize(p);
      const keyInput = document.getElementById(`keyInput${pCap}`);
      const modelInput = document.getElementById(`modelInput${pCap}`);
      const testRes = document.getElementById(`testResult${pCap}`);
      const apiKey = keyInput ? keyInput.value.trim() : "";
      const model = modelInput ? modelInput.value.trim() : "";

      btn.disabled = true;
      btn.textContent = "⏳ 테스트 중...";
      if (testRes) {
        testRes.className = "provider-test-result loading visible";
        testRes.innerHTML = `
          <div class="test-loading-spinner"></div>
          <div>
            <strong>${providerDisplayNames[p]} 연결 확인 중...</strong>
            <div style="font-size: 0.71rem; color: #64748b; margin-top: 1px;">AI 서버로 핑 테스트 요청을 전송하고 있습니다. (약 2~5초 소요)</div>
          </div>
        `;
      }

      try {
        const res = await fetch("/api/settings/ai/test", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            provider: p,
            api_key: apiKey,
            model: model,
          }),
        });
        const resData = await res.json();
        const now = new Date();
        const timeStr = `${String(now.getHours()).padStart(2, "0")}:${String(now.getMinutes()).padStart(2, "0")}:${String(now.getSeconds()).padStart(2, "0")}`;

        if (res.ok && resData.success) {
          if (resData.model && modelInput) {
            modelInput.value = resData.model;
          }
          if (testRes) {
            testRes.className = "provider-test-result success visible";
            const isOREnsemble = (p === "openrouter" && document.getElementById("cbOpenRouterEnsemble")?.checked);
            const modelUsed = resData.model || model || "확인됨";
            testRes.innerHTML = `
              <div class="result-header">
                <span>✔ <strong>${providerDisplayNames[p]} 연결 성공!</strong></span>
                <span style="font-size: 0.7rem; font-weight: 600; opacity: 0.85;">${timeStr}</span>
              </div>
              <div class="result-body">
                <div>• <strong>응답 모델:</strong> <span class="result-model-badge">${escapeHtml(modelUsed)}</span></div>
                <div style="margin-top: 3px;">• <strong>상태:</strong> API Key 인증 완료 및 문법 분석 JSON 정상 통신 확인</div>
                ${isOREnsemble ? `<div style="margin-top: 4px; color: #4338ca; font-weight: 700; background: #e0e7ff; padding: 3px 6px; border-radius: 4px; border: 1px solid #c7d2fe;">🔄 3개 모델 앙상블(${escapeHtml(currentEnsembleModels.map(m => getModelDisplayShortName(m)).join(', '))}) 교차 검증 준비 완료</div>` : ""}
              </div>
            `;
          }
          showToast(`${providerDisplayNames[p]} 연결 성공! (${resData.model || '정상'})`, "success");
          const keyStatus = document.getElementById(`keyStatus${pCap}`);
          if (keyStatus && apiKey) {
            keyStatus.textContent = "현재 키: 새로 입력됨 (저장 필요)";
            keyStatus.style.color = "#2563eb";
          }
        } else {
          if (testRes) {
            testRes.className = "provider-test-result error visible";
            const errMsg = resData.message || resData.detail || "알 수 없는 오류가 발생했습니다.";
            testRes.innerHTML = `
              <div class="result-header">
                <span>❌ <strong>${providerDisplayNames[p]} 연결 실패</strong></span>
                <span style="font-size: 0.7rem; font-weight: 600; opacity: 0.85;">${timeStr}</span>
              </div>
              <div class="result-body">
                <div>• <strong>오류 내용:</strong> <span style="font-weight: 600;">${escapeHtml(errMsg)}</span></div>
                <div class="result-guide">
                  💡 <strong>확인 사항:</strong> API Key 철자가 올바른지, 사용량 잔액(Credit/Quota)이 남아 있는지, 모델명이 맞는지 확인해 주세요.
                </div>
              </div>
            `;
          }
          showToast(`${providerDisplayNames[p]} 연결 실패: ${resData.message || '오류'}`, "error");
        }
      } catch (err) {
        if (testRes) {
          testRes.className = "provider-test-result error visible";
          testRes.innerHTML = `
            <div class="result-header">
              <span>❌ <strong>통신 오류 (서버 응답 없음)</strong></span>
            </div>
            <div class="result-body">
              <div>• <strong>오류 내용:</strong> 네트워크 요청 타임아웃 또는 로컬 서버 응답 지연이 발생했습니다.</div>
              <div class="result-guide">💡 인터넷 연결을 확인하거나 잠시 후 다시 테스트해 주세요.</div>
            </div>
          `;
        }
        showToast(`${providerDisplayNames[p]} 연결 테스트 중 통신 오류가 발생했습니다.`, "error");
      } finally {
        btn.disabled = false;
        btn.textContent = "🧪 개별 연결 테스트";
      }
    });
  });

  // 키 또는 모델 입력 변경 시 테스트 안내 갱신
  ALL_PROVIDERS.forEach((p) => {
    const pCap = capitalize(p);
    const keyInput = document.getElementById(`keyInput${pCap}`);
    const modelInput = document.getElementById(`modelInput${pCap}`);
    const testRes = document.getElementById(`testResult${pCap}`);

    [keyInput, modelInput].forEach((inputEl) => {
      if (inputEl) {
        inputEl.addEventListener("input", () => {
          if (testRes && !testRes.classList.contains("loading")) {
            testRes.className = "provider-test-result info visible";
            testRes.innerHTML = `<span>✏️ <strong>설정 변경됨:</strong> [🧪 개별 연결 테스트]를 클릭하여 변경된 값의 유효성을 검증하세요.</span>`;
          }
        });
      }
    });
  });

  // 모델 추천 칩 클릭 시 해당 모델명 자동 입력
  document.querySelectorAll(".btn-model-tag").forEach((btn) => {
    btn.addEventListener("click", () => {
      const targetId = btn.dataset.target;
      const targetInput = document.getElementById(targetId);
      if (targetInput && btn.dataset.model) {
        targetInput.value = btn.dataset.model;
        targetInput.focus();
      }
    });
  });

  if (btnOpenAiSettingsModal) {
    btnOpenAiSettingsModal.addEventListener("click", openAiSettingsModal);
  }
  if (btnCloseAiSettingsModal) {
    btnCloseAiSettingsModal.addEventListener("click", closeAiSettingsModal);
  }
  if (btnCancelAiSettings) {
    btnCancelAiSettings.addEventListener("click", closeAiSettingsModal);
  }

  // 모달 배경 클릭 시 닫기
  if (aiSettingsModal) {
    aiSettingsModal.addEventListener("click", (e) => {
      if (e.target === aiSettingsModal) {
        closeAiSettingsModal();
      }
    });
  }

  // ESC 키 입력 시 모달 닫기
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && aiSettingsModal && aiSettingsModal.style.display !== "none") {
      closeAiSettingsModal();
    }
  });

  // 전체 AI 설정 저장 버튼 바인딩
  if (btnSaveAiSettings) {
    btnSaveAiSettings.addEventListener("click", async () => {
      const checkedBoxes = Array.from(document.querySelectorAll(".provider-checkbox:checked"));
      const checkedProviders = checkedBoxes.map((cb) => cb.dataset.provider);

      if (checkedProviders.length === 0) {
        showToast("최소 1개 이상의 AI 모델을 선택해 주세요.", "warning");
        return;
      }

      const providersPayload = {};
      ALL_PROVIDERS.forEach((p) => {
        const pCap = capitalize(p);
        const keyInput = document.getElementById(`keyInput${pCap}`);
        const modelInput = document.getElementById(`modelInput${pCap}`);
        providersPayload[p] = {
          api_key: keyInput ? keyInput.value.trim() : "",
          model: modelInput ? modelInput.value.trim() : "",
        };
      });

      const modeSelect = document.getElementById("selectConsensusMode");
      const consensusMode = modeSelect ? modeSelect.value : "majority";

      // TTS 엔진 및 설정 수집 (Edge-TTS / ElevenLabs)
      const radioElevenlabs = document.getElementById("radioTtsElevenlabs");
      const selectedTtsEngine = (radioElevenlabs && radioElevenlabs.checked) ? "elevenlabs" : "edge-tts";

      const selEdgeMale = document.getElementById("selectEdgeTtsVoiceMale");
      const selEdgeFemale = document.getElementById("selectEdgeTtsVoiceFemale");
      const selEdgeRate = document.getElementById("selectEdgeTtsRate");

      const elKeyInput = document.getElementById("keyInputElevenlabs");
      const elVoiceMale = document.getElementById("voiceInputElevenlabsMale");
      const elVoiceFemale = document.getElementById("voiceInputElevenlabsFemale");
      const elModel = document.getElementById("modelInputElevenlabs");

      const ttsPayload = {
        tts_engine: selectedTtsEngine,
        edge_tts_voice_male: selEdgeMale ? selEdgeMale.value : "en-US-GuyNeural",
        edge_tts_voice_female: selEdgeFemale ? selEdgeFemale.value : "en-US-JennyNeural",
        edge_tts_rate: selEdgeRate ? selEdgeRate.value : "+0%",
      };
      if (elKeyInput && elKeyInput.value.trim()) ttsPayload.elevenlabs_api_key = elKeyInput.value.trim();
      if (elVoiceMale) ttsPayload.elevenlabs_voice_male = elVoiceMale.value.trim();
      if (elVoiceFemale) ttsPayload.elevenlabs_voice_female = elVoiceFemale.value.trim();
      if (elModel) ttsPayload.elevenlabs_model_id = elModel.value.trim();

      btnSaveAiSettings.disabled = true;
      btnSaveAiSettings.textContent = "⏳ 저장 중...";

      try {
        const cbOREnsemble = document.getElementById("cbOpenRouterEnsemble");
        const res = await fetch("/api/settings/ai", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            active_providers: checkedProviders,
            consensus_mode: consensusMode,
            providers: providersPayload,
            openrouter_ensemble: cbOREnsemble ? cbOREnsemble.checked : false,
            openrouter_ensemble_models: getSelectedOpenRouterEnsembleModels(),
            ...ttsPayload,
          }),
        });
        const data = await res.json();
        if (res.ok && data.success) {
          appState.ttsEngine = selectedTtsEngine;
          const badgeTopRight = document.getElementById("badgeTopRightSource");
          if (badgeTopRight && (appState.currentArea === "listening" || (appState.passagesData[appState.currentPassageIndex]?.area === "listening"))) {
            badgeTopRight.textContent = (selectedTtsEngine === "elevenlabs") ? "ElevenLabs TTS" : "Edge-TTS (무료)";
          }
          showToast("AI 및 TTS 설정이 성공적으로 저장되었습니다.", "success");
          await refreshAiStatusIndicator();
          setTimeout(() => {
            closeAiSettingsModal();
          }, 600);
        } else {
          showToast(data.message || "설정 저장 실패", "error");
        }
      } catch (err) {
        console.error(err);
        showToast("설정 저장 중 통신 오류가 발생했습니다.", "error");
      } finally {
        btnSaveAiSettings.disabled = false;
        btnSaveAiSettings.textContent = "✔ 전체 설정 저장";
      }
    });
  }
  if (selectConsensusModeEl) {
    selectConsensusModeEl.addEventListener("change", updateAiModalSelectionSummary);
  }

  // TTS 엔진 라디오 토글 이벤트 바인딩 (Edge-TTS <-> ElevenLabs)
  const radioEdge = document.getElementById("radioTtsEdge");
  const radioElevenlabs = document.getElementById("radioTtsElevenlabs");
  const cardEdge = document.getElementById("cardEdgeTts");
  const cardEleven = document.getElementById("cardElevenlabs");

  const toggleTtsEngineCards = () => {
    const isEleven = radioElevenlabs && radioElevenlabs.checked;
    if (cardEdge) cardEdge.style.display = isEleven ? "none" : "block";
    if (cardEleven) cardEleven.style.display = isEleven ? "block" : "none";
    updateAiModalSelectionSummary();
  };

  if (radioEdge) radioEdge.addEventListener("change", toggleTtsEngineCards);
  if (radioElevenlabs) radioElevenlabs.addEventListener("change", toggleTtsEngineCards);

  // Edge-TTS 음성 샘플 미리듣기 핸들러
  const handleEdgeTtsPreview = async (gender) => {
    const voiceSelect = gender === "female"
      ? document.getElementById("selectEdgeTtsVoiceFemale")
      : document.getElementById("selectEdgeTtsVoiceMale");
    const rateSelect = document.getElementById("selectEdgeTtsRate");
    const resDiv = document.getElementById("testResultEdgeTts");

    const voice = voiceSelect ? voiceSelect.value : (gender === "female" ? "en-US-JennyNeural" : "en-US-GuyNeural");
    const rate = rateSelect ? rateSelect.value : "+0%";

    if (resDiv) {
      resDiv.className = "provider-test-result info visible";
      resDiv.textContent = `⏳ ${gender === "female" ? "여성" : "남성"}(${voice}) 음성 샘플 합성 중...`;
    }

    try {
      const res = await fetch("/api/settings/edge-tts/preview", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ voice, rate }),
      });
      const data = await res.json();
      if (res.ok && data.success && data.audio_url) {
        if (resDiv) {
          resDiv.className = "provider-test-result success visible";
          resDiv.textContent = `✔ 음성 합성 완료! 재생 중... (${voice})`;
        }
        const audio = new Audio(data.audio_url);
        audio.play().catch(e => console.warn("오디오 자동재생 차단:", e));
      } else {
        if (resDiv) {
          resDiv.className = "provider-test-result error visible";
          resDiv.textContent = `❌ 미리듣기 실패: ${data.message || "오류"}`;
        }
      }
    } catch (e) {
      if (resDiv) {
        resDiv.className = "provider-test-result error visible";
        resDiv.textContent = `❌ 통신 오류: ${e.message}`;
      }
    }
  };

  const btnPreviewMale = document.getElementById("btnPreviewEdgeTtsMale");
  if (btnPreviewMale) {
    btnPreviewMale.addEventListener("click", () => handleEdgeTtsPreview("male"));
  }
  const btnPreviewFemale = document.getElementById("btnPreviewEdgeTtsFemale");
  if (btnPreviewFemale) {
    btnPreviewFemale.addEventListener("click", () => handleEdgeTtsPreview("female"));
  }

  // ElevenLabs TTS 개별 연결 테스트 버튼 바인딩
  const btnTestElevenlabs = document.getElementById("btnTestElevenlabs");
  if (btnTestElevenlabs) {
    btnTestElevenlabs.addEventListener("click", async () => {
      const keyInput = document.getElementById("keyInputElevenlabs");
      const resDiv = document.getElementById("testResultElevenlabs");
      if (resDiv) {
        resDiv.className = "provider-test-result info visible";
        resDiv.textContent = "⏳ ElevenLabs 서버 연결 확인 중...";
      }
      try {
        const res = await fetch("/api/settings/elevenlabs/test", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ elevenlabs_api_key: keyInput ? keyInput.value.trim() : "" }),
        });
        const data = await res.json();
        if (res.ok && data.success) {
          if (resDiv) {
            resDiv.className = "provider-test-result success visible";
            resDiv.textContent = `✔ ${data.message}`;
          }
          showToast(data.message, "success");
        } else {
          if (resDiv) {
            resDiv.className = "provider-test-result error visible";
            resDiv.textContent = `❌ ${data.message || "연결 실패"}`;
          }
          showToast(data.message || "ElevenLabs 연결 실패", "error");
        }
      } catch (e) {
        if (resDiv) {
          resDiv.className = "provider-test-result error visible";
          resDiv.textContent = `❌ 통신 오류: ${e.message}`;
        }
      }
    });
  }
}
