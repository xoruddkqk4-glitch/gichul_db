/**
 * 05-gichul_db: 교사용 유인물 프로젝트 및 장바구니 상태 관리 (handout-cart.js)
 * - 지문 유인물 프로젝트(passage_projects)와 문장 유인물 프로젝트(sentence_projects)의 완전 분리
 * - 각 프로젝트별 독립된 출제 문항 목록(items / sentence_items), 인쇄 번호(custom_q_num / custom_num), 머리말 서식 설정 관리
 * - 프로젝트 생성(Create), 이름 수정(Rename), 삭제(Delete), 전환(Switch) 기능 지원
 * - 지문/문장 결과 화면 내 [📄 유인물 담기] 체크박스 및 빠른 프로젝트 선택기 연동
 * - 하단 플로팅 장바구니 바 및 유인물 제작소 화면 실시간 반응형 동기화
 */

import { appState } from "./state.js";

// 로컬스토리지 키 (독해용 / 문장용 / 듣기용 3대 영역 완전 분리)
const KEY_PASSAGE_PROJECTS = "gichul_handout_passage_projects";
const KEY_CURRENT_PASSAGE_PROJECT_ID = "gichul_handout_cur_passage_proj_id";

const KEY_SENTENCE_PROJECTS = "gichul_handout_sentence_projects";
const KEY_CURRENT_SENTENCE_PROJECT_ID = "gichul_handout_cur_sentence_proj_id";

const KEY_LISTENING_PROJECTS = "gichul_handout_listening_projects";
const KEY_CURRENT_LISTENING_PROJECT_ID = "gichul_handout_cur_listening_proj_id";

// 레거시 통합 키 (자동 마이그레이션 대상)
const LEGACY_PROJECTS_KEY = "gichul_handout_projects";
const LEGACY_CURRENT_PROJECT_ID = "gichul_handout_current_project_id";
const OLD_CART_STORAGE_KEY = "gichul_handout_cart";

/** 이전 단일/통합 프로젝트 데이터를 지문/문장/듣기 프로젝트로 자동 마이그레이션 및 초기화 */
function ensureMigration() {
  const hasPassage = localStorage.getItem(KEY_PASSAGE_PROJECTS);
  const hasSentence = localStorage.getItem(KEY_SENTENCE_PROJECTS);
  const hasListening = localStorage.getItem(KEY_LISTENING_PROJECTS);

  const legacyRaw = localStorage.getItem(LEGACY_PROJECTS_KEY);
  if (legacyRaw && (!hasPassage || !hasSentence)) {
    try {
      const legacyProjects = JSON.parse(legacyRaw);
      if (Array.isArray(legacyProjects) && legacyProjects.length > 0) {
        if (!hasPassage) {
          const passageProjects = legacyProjects.map((p) => ({
            id: p.id,
            name: p.name,
            createdAt: p.createdAt || Date.now(),
            updatedAt: p.updatedAt || Date.now(),
            items: Array.isArray(p.items) ? p.items : [],
            settings: p.settings || {},
          }));
          localStorage.setItem(KEY_PASSAGE_PROJECTS, JSON.stringify(passageProjects));
          const curId = localStorage.getItem(LEGACY_CURRENT_PROJECT_ID);
          if (curId) localStorage.setItem(KEY_CURRENT_PASSAGE_PROJECT_ID, curId);
        }
        if (!hasSentence) {
          const sentenceProjects = legacyProjects.map((p) => ({
            id: p.id.startsWith("proj_sent_") ? p.id : `proj_sent_${p.id.replace("proj_", "")}`,
            name: p.name.includes("문장") ? p.name : `${p.name} (문장)`,
            createdAt: p.createdAt || Date.now(),
            updatedAt: p.updatedAt || Date.now(),
            sentence_items: Array.isArray(p.sentence_items) ? p.sentence_items : [],
            settings: p.sentence_settings || {},
          }));
          localStorage.setItem(KEY_SENTENCE_PROJECTS, JSON.stringify(sentenceProjects));
          const curId = localStorage.getItem(LEGACY_CURRENT_PROJECT_ID);
          if (curId) {
            const sentCurId = curId.startsWith("proj_sent_") ? curId : `proj_sent_${curId.replace("proj_", "")}`;
            localStorage.setItem(KEY_CURRENT_SENTENCE_PROJECT_ID, sentCurId);
          }
        }
      }
    } catch (e) {
      console.warn("Handout migration error", e);
    }
  }

  // 1) 신규 기본 독해 프로젝트 초기화
  if (!localStorage.getItem(KEY_PASSAGE_PROJECTS)) {
    let initialItems = [];
    try {
      const oldCartRaw = localStorage.getItem(OLD_CART_STORAGE_KEY);
      if (oldCartRaw) {
        const parsed = JSON.parse(oldCartRaw);
        if (Array.isArray(parsed)) initialItems = parsed;
      }
    } catch (e) {
      // 무시
    }
    const defaultPassageProj = [{
      id: "proj_passage_default",
      name: "기본 독해 프로젝트",
      createdAt: Date.now(),
      updatedAt: Date.now(),
      items: initialItems,
      settings: {},
    }];
    localStorage.setItem(KEY_PASSAGE_PROJECTS, JSON.stringify(defaultPassageProj));
    localStorage.setItem(KEY_CURRENT_PASSAGE_PROJECT_ID, defaultPassageProj[0].id);
  }

  // 2) 신규 기본 문장 프로젝트 초기화
  if (!localStorage.getItem(KEY_SENTENCE_PROJECTS)) {
    const defaultSentenceProj = [{
      id: "proj_sentence_default",
      name: "기본 문장 프로젝트",
      createdAt: Date.now(),
      updatedAt: Date.now(),
      sentence_items: [],
      settings: {},
    }];
    localStorage.setItem(KEY_SENTENCE_PROJECTS, JSON.stringify(defaultSentenceProj));
    localStorage.setItem(KEY_CURRENT_SENTENCE_PROJECT_ID, defaultSentenceProj[0].id);
  }

  // 3) 신규 기본 듣기 프로젝트 초기화
  if (!hasListening) {
    const defaultListeningProj = [{
      id: "proj_listening_default",
      name: "기본 듣기 프로젝트",
      createdAt: Date.now(),
      updatedAt: Date.now(),
      items: [],
      settings: {},
    }];
    localStorage.setItem(KEY_LISTENING_PROJECTS, JSON.stringify(defaultListeningProj));
    localStorage.setItem(KEY_CURRENT_LISTENING_PROJECT_ID, defaultListeningProj[0].id);
  }
}

ensureMigration();

// =========================================================================
// 1. 지문 유인물 프로젝트 관리 (Passage Projects)
// =========================================================================

/** 지문 프로젝트 목록 조회 */
export function getPassageProjects() {
  try {
    const raw = localStorage.getItem(KEY_PASSAGE_PROJECTS);
    if (raw) {
      const list = JSON.parse(raw);
      if (Array.isArray(list) && list.length > 0) return list;
    }
  } catch (e) {
    console.warn("Failed to parse passage projects", e);
  }
  const defaultProj = [{
    id: "proj_passage_default",
    name: "기본 지문 프로젝트",
    createdAt: Date.now(),
    updatedAt: Date.now(),
    items: [],
    settings: {},
  }];
  savePassageProjects(defaultProj);
  return defaultProj;
}

/** 지문 프로젝트 목록 저장 */
export function savePassageProjects(projects) {
  try {
    localStorage.setItem(KEY_PASSAGE_PROJECTS, JSON.stringify(projects));
  } catch (e) {
    console.warn("Failed to save passage projects", e);
  }
}

/** 현재 활성화된 지문 프로젝트 ID */
export function getCurrentPassageProjectId() {
  const projects = getPassageProjects();
  let curId = localStorage.getItem(KEY_CURRENT_PASSAGE_PROJECT_ID);
  if (!curId || !projects.some((p) => p.id === curId)) {
    curId = projects[0]?.id || "proj_passage_default";
    localStorage.setItem(KEY_CURRENT_PASSAGE_PROJECT_ID, curId);
  }
  return curId;
}

/** 현재 활성화된 지문 프로젝트 객체 */
export function getCurrentPassageProject() {
  const projects = getPassageProjects();
  const curId = getCurrentPassageProjectId();
  return projects.find((p) => p.id === curId) || projects[0];
}

// 현재 하단 플로팅 바에서 활성화된 프로젝트 유형 ('passage' | 'sentence')
let currentFloatingTargetType = "passage";

export function getCurrentFloatingTargetType() {
  return currentFloatingTargetType;
}

export function setCurrentFloatingTargetType(type) {
  if (type === "sentence" || type === "passage" || type === "listening") {
    currentFloatingTargetType = type;
    updateFloatingCartUI();
  }
}

/** 활성 지문 프로젝트 전환 */
export function setCurrentPassageProject(projectId) {
  const projects = getPassageProjects();
  if (!projects.some((p) => p.id === projectId)) return;

  currentFloatingTargetType = "passage";
  localStorage.setItem(KEY_CURRENT_PASSAGE_PROJECT_ID, projectId);
  window.dispatchEvent(new CustomEvent("handout-passage-project-changed", { detail: { projectId } }));
  window.dispatchEvent(new CustomEvent("handout-project-changed", { detail: { projectId } }));
  window.dispatchEvent(new CustomEvent("handout-cart-changed", { detail: getCartItems() }));
  updateFloatingCartUI();
  syncAllProjectDropdowns();
}

/** 새 지문 프로젝트 생성 */
export function createPassageProject(name) {
  const trimmed = (name || "").trim() || `지문 프로젝트 ${new Date().toLocaleDateString()}`;
  const projects = getPassageProjects();
  const newId = `proj_passage_${Date.now()}`;
  const newProj = {
    id: newId,
    name: trimmed,
    createdAt: Date.now(),
    updatedAt: Date.now(),
    items: [],
    settings: {},
  };
  projects.push(newProj);
  savePassageProjects(projects);
  setCurrentPassageProject(newId);
  return newProj;
}

/** 지문 프로젝트 이름 변경 */
export function renamePassageProject(projectId, newName) {
  const trimmed = (newName || "").trim();
  if (!trimmed) return false;
  const projects = getPassageProjects();
  const proj = projects.find((p) => p.id === projectId);
  if (!proj) return false;

  proj.name = trimmed;
  proj.updatedAt = Date.now();
  savePassageProjects(projects);
  window.dispatchEvent(new CustomEvent("handout-passage-project-changed", { detail: { projectId } }));
  window.dispatchEvent(new CustomEvent("handout-project-changed", { detail: { projectId } }));
  updateFloatingCartUI();
  syncAllProjectDropdowns();
  return true;
}

/** 지문 프로젝트 삭제 */
export function deletePassageProject(projectId) {
  let projects = getPassageProjects();
  if (!projects.some((p) => p.id === projectId)) return false;

  projects = projects.filter((p) => p.id !== projectId);
  if (projects.length === 0) {
    projects = [{
      id: `proj_passage_${Date.now()}`,
      name: "기본 지문 프로젝트",
      createdAt: Date.now(),
      updatedAt: Date.now(),
      items: [],
      settings: {},
    }];
  }
  savePassageProjects(projects);
  const nextCurId = projects[0].id;
  localStorage.setItem(KEY_CURRENT_PASSAGE_PROJECT_ID, nextCurId);

  window.dispatchEvent(new CustomEvent("handout-passage-project-changed", { detail: { projectId: nextCurId } }));
  window.dispatchEvent(new CustomEvent("handout-project-changed", { detail: { projectId: nextCurId } }));
  window.dispatchEvent(new CustomEvent("handout-cart-changed", { detail: projects[0].items }));
  updateFloatingCartUI();
  syncAllProjectDropdowns();
  return true;
}

/** 지문 프로젝트 서식 설정 조회 */
export function getPassageProjectSettings(projectId = null) {
  const proj = projectId ? getPassageProjects().find((p) => p.id === projectId) : getCurrentPassageProject();
  return (proj && proj.settings) || {};
}

/** 지문 프로젝트 서식 설정 저장 */
export function savePassageProjectSettings(projectId, settings) {
  const projects = getPassageProjects();
  const proj = projects.find((p) => p.id === (projectId || getCurrentPassageProjectId()));
  if (proj) {
    proj.settings = { ...proj.settings, ...settings };
    proj.updatedAt = Date.now();
    savePassageProjects(projects);
  }
}

// 기존 handout-passage.js 호환용 별칭(Aliases)
export const getProjects = getPassageProjects;
export const saveProjects = savePassageProjects;
export const getCurrentProjectId = getCurrentPassageProjectId;
export const getCurrentProject = getCurrentPassageProject;
export const setCurrentProject = setCurrentPassageProject;
export const createProject = createPassageProject;
export const renameProject = renamePassageProject;
export const deleteProject = deletePassageProject;
export const getProjectSettings = getPassageProjectSettings;
export const saveProjectSettings = savePassageProjectSettings;

// =========================================================================
// 2. 활성 지문 프로젝트 내 문항 목록(items) 관리
// =========================================================================

/** 현재 활성 지문 프로젝트의 문항 목록 조회 */
export function getCartItems() {
  const proj = getCurrentPassageProject();
  return Array.isArray(proj.items) ? proj.items : [];
}

/** 현재 활성 지문 프로젝트의 문항 목록 저장 */
export function saveCartItems(items) {
  const projects = getPassageProjects();
  const curId = getCurrentPassageProjectId();
  const proj = projects.find((p) => p.id === curId);
  if (proj) {
    proj.items = items;
    proj.updatedAt = Date.now();
    savePassageProjects(projects);
  }
  window.dispatchEvent(new CustomEvent("handout-cart-changed", { detail: items }));
  updateFloatingCartUI();
}

/** 특정 문항이 현재 활성 지문 프로젝트에 담겨있는지 확인 */
export function isInCart(passageId) {
  if (!passageId) return false;
  return getCartItems().some((item) => item.id === passageId);
}

/** 현재 활성 지문 프로젝트에 문항 추가 */
export function addToCart(passageId, customNum = null) {
  if (!passageId) return;
  currentFloatingTargetType = "passage";
  const items = getCartItems();
  if (items.some((item) => item.id === passageId)) return;

  const nextNum = customNum || String(items.length + 1);
  items.push({ id: passageId, custom_q_num: String(nextNum) });
  saveCartItems(items);
}

/** 현재 활성 지문 프로젝트에서 문항 제거 */
export function removeFromCart(passageId) {
  if (!passageId) return;
  let items = getCartItems();
  items = items.filter((item) => item.id !== passageId);
  saveCartItems(items);
}

/** 문항 담기/제외 토글 */
export function toggleCart(passageId) {
  if (isInCart(passageId)) {
    removeFromCart(passageId);
    return false;
  } else {
    addToCart(passageId);
    return true;
  }
}

/** 지문 프로젝트 문항 전체 비우기 */
export function clearCart() {
  saveCartItems([]);
}

/** 지문 순서 변경 */
export function reorderCart(fromIdx, toIdx) {
  const items = getCartItems();
  if (fromIdx < 0 || fromIdx >= items.length || toIdx < 0 || toIdx >= items.length) return;
  const [moved] = items.splice(fromIdx, 1);
  items.splice(toIdx, 0, moved);
  saveCartItems(items);
}

/** 특정 문항의 사용자 지정 인쇄 번호 수정 */
export function setCustomQNum(passageId, customNum) {
  const items = getCartItems();
  const target = items.find((item) => item.id === passageId);
  if (target) {
    target.custom_q_num = String(customNum).trim();
    saveCartItems(items);
  }
}

/** 전체 문항 번호 순차 재부여 */
export function renumberCart(startNum = 1) {
  const items = getCartItems();
  let cur = parseInt(startNum, 10) || 1;
  items.forEach((item) => {
    item.custom_q_num = String(cur++);
  });
  saveCartItems(items);
}

// =========================================================================
// 3. 문장 유인물 프로젝트 관리 (Sentence Projects)
// =========================================================================

/** 문장 프로젝트 목록 조회 */
export function getSentenceProjects() {
  try {
    const raw = localStorage.getItem(KEY_SENTENCE_PROJECTS);
    if (raw) {
      const list = JSON.parse(raw);
      if (Array.isArray(list) && list.length > 0) return list;
    }
  } catch (e) {
    console.warn("Failed to parse sentence projects", e);
  }
  const defaultProj = [{
    id: "proj_sentence_default",
    name: "기본 문장 프로젝트",
    createdAt: Date.now(),
    updatedAt: Date.now(),
    sentence_items: [],
    settings: {},
  }];
  saveSentenceProjects(defaultProj);
  return defaultProj;
}

/** 문장 프로젝트 목록 저장 */
export function saveSentenceProjects(projects) {
  try {
    localStorage.setItem(KEY_SENTENCE_PROJECTS, JSON.stringify(projects));
  } catch (e) {
    console.warn("Failed to save sentence projects", e);
  }
}

/** 현재 활성화된 문장 프로젝트 ID */
export function getCurrentSentenceProjectId() {
  const projects = getSentenceProjects();
  let curId = localStorage.getItem(KEY_CURRENT_SENTENCE_PROJECT_ID);
  if (!curId || !projects.some((p) => p.id === curId)) {
    curId = projects[0]?.id || "proj_sentence_default";
    localStorage.setItem(KEY_CURRENT_SENTENCE_PROJECT_ID, curId);
  }
  return curId;
}

/** 현재 활성화된 문장 프로젝트 객체 */
export function getCurrentSentenceProject() {
  const projects = getSentenceProjects();
  const curId = getCurrentSentenceProjectId();
  return projects.find((p) => p.id === curId) || projects[0];
}

/** 활성 문장 프로젝트 전환 */
export function setCurrentSentenceProject(projectId) {
  const projects = getSentenceProjects();
  if (!projects.some((p) => p.id === projectId)) return;

  currentFloatingTargetType = "sentence";
  localStorage.setItem(KEY_CURRENT_SENTENCE_PROJECT_ID, projectId);
  window.dispatchEvent(new CustomEvent("handout-sentence-project-changed", { detail: { projectId } }));
  window.dispatchEvent(new CustomEvent("handout-sentence-cart-changed", { detail: getSentenceCartItems() }));
  updateFloatingCartUI();
  syncAllProjectDropdowns();
}

/** 새 문장 프로젝트 생성 */
export function createSentenceProject(name) {
  const trimmed = (name || "").trim() || `문장 프로젝트 ${new Date().toLocaleDateString()}`;
  const projects = getSentenceProjects();
  const newId = `proj_sentence_${Date.now()}`;
  const newProj = {
    id: newId,
    name: trimmed,
    createdAt: Date.now(),
    updatedAt: Date.now(),
    sentence_items: [],
    settings: {},
  };
  projects.push(newProj);
  saveSentenceProjects(projects);
  setCurrentSentenceProject(newId);
  return newProj;
}

/** 문장 프로젝트 이름 변경 */
export function renameSentenceProject(projectId, newName) {
  const trimmed = (newName || "").trim();
  if (!trimmed) return false;
  const projects = getSentenceProjects();
  const proj = projects.find((p) => p.id === projectId);
  if (!proj) return false;

  proj.name = trimmed;
  proj.updatedAt = Date.now();
  saveSentenceProjects(projects);
  window.dispatchEvent(new CustomEvent("handout-sentence-project-changed", { detail: { projectId } }));
  updateFloatingCartUI();
  syncAllProjectDropdowns();
  return true;
}

/** 문장 프로젝트 삭제 */
export function deleteSentenceProject(projectId) {
  let projects = getSentenceProjects();
  if (!projects.some((p) => p.id === projectId)) return false;

  projects = projects.filter((p) => p.id !== projectId);
  if (projects.length === 0) {
    projects = [{
      id: `proj_sentence_${Date.now()}`,
      name: "기본 문장 프로젝트",
      createdAt: Date.now(),
      updatedAt: Date.now(),
      sentence_items: [],
      settings: {},
    }];
  }
  saveSentenceProjects(projects);
  const nextCurId = projects[0].id;
  localStorage.setItem(KEY_CURRENT_SENTENCE_PROJECT_ID, nextCurId);

  window.dispatchEvent(new CustomEvent("handout-sentence-project-changed", { detail: { projectId: nextCurId } }));
  window.dispatchEvent(new CustomEvent("handout-sentence-cart-changed", { detail: projects[0].sentence_items }));
  updateFloatingCartUI();
  syncAllProjectDropdowns();
  return true;
}

/** 문장 프로젝트 서식 설정 조회 */
export function getSentenceProjectSettings(projectId = null) {
  const proj = projectId ? getSentenceProjects().find((p) => p.id === projectId) : getCurrentSentenceProject();
  return (proj && proj.settings) || {};
}

/** 문장 프로젝트 서식 설정 저장 */
export function saveSentenceProjectSettings(projectId, settings) {
  const projects = getSentenceProjects();
  const proj = projects.find((p) => p.id === (projectId || getCurrentSentenceProjectId()));
  if (proj) {
    proj.settings = { ...proj.settings, ...settings };
    proj.updatedAt = Date.now();
    saveSentenceProjects(projects);
  }
}

// =========================================================================
// 4. 활성 문장 프로젝트 내 문장 목록(sentence_items) 관리
// =========================================================================

/** 현재 활성 문장 프로젝트의 문장 카트 목록: Array<{ id: string, custom_num: string } */
export function getSentenceCartItems() {
  const proj = getCurrentSentenceProject();
  const rawList = Array.isArray(proj.sentence_items) ? proj.sentence_items : [];
  // 번호 필드 정규화
  return rawList.map((item, idx) => {
    if (typeof item === "string") {
      return { id: item, custom_num: String(idx + 1) };
    }
    return {
      id: item.id,
      custom_num: item.custom_num ? String(item.custom_num) : String(idx + 1),
    };
  });
}

/** 현재 활성 문장 프로젝트의 문장 카트 목록 저장 */
export function saveSentenceCartItems(items) {
  const projects = getSentenceProjects();
  const curId = getCurrentSentenceProjectId();
  const proj = projects.find((p) => p.id === curId);
  if (proj) {
    proj.sentence_items = items;
    proj.updatedAt = Date.now();
    saveSentenceProjects(projects);
  }
  window.dispatchEvent(new CustomEvent("handout-sentence-cart-changed", { detail: items }));
  updateFloatingCartUI();
  syncAllSentenceCheckboxes();
}

/** 특정 문장이 현재 활성 문장 프로젝트에 담겨있는지 확인 */
export function isInSentenceCart(sentenceId) {
  if (!sentenceId) return false;
  return getSentenceCartItems().some((item) => item.id === sentenceId);
}

/** 현재 활성 문장 프로젝트에 문장 추가 (기본 순차 번호 부여) */
export function addToSentenceCart(sentenceId, customNum = null) {
  if (!sentenceId) return;
  currentFloatingTargetType = "sentence";
  const items = getSentenceCartItems();
  if (items.some((item) => item.id === sentenceId)) return;

  const nextNum = customNum || String(items.length + 1);
  items.push({ id: sentenceId, custom_num: String(nextNum) });
  saveSentenceCartItems(items);
}

/** 현재 활성 문장 프로젝트에서 문장 제거 */
export function removeFromSentenceCart(sentenceId) {
  if (!sentenceId) return;
  let items = getSentenceCartItems();
  items = items.filter((item) => item.id !== sentenceId);
  saveSentenceCartItems(items);
}

/** 문장 담기/제외 토글 */
export function toggleSentenceCart(sentenceId) {
  if (isInSentenceCart(sentenceId)) {
    removeFromSentenceCart(sentenceId);
    return false;
  } else {
    addToSentenceCart(sentenceId);
    return true;
  }
}

/** 현재 활성 문장 프로젝트 비우기 */
export function clearSentenceCart() {
  saveSentenceCartItems([]);
}

/** 문장 순서 변경 */
export function reorderSentenceCart(fromIdx, toIdx) {
  const items = getSentenceCartItems();
  if (fromIdx < 0 || fromIdx >= items.length || toIdx < 0 || toIdx >= items.length) return;
  const [moved] = items.splice(fromIdx, 1);
  items.splice(toIdx, 0, moved);
  saveSentenceCartItems(items);
}

/** 특정 문장의 사용자 지정 번호 수정 */
export function setCustomSentenceNum(sentenceId, customNum) {
  const items = getSentenceCartItems();
  const target = items.find((item) => item.id === sentenceId);
  if (target) {
    target.custom_num = String(customNum).trim();
    saveSentenceCartItems(items);
  }
}

/** 전체 문장 번호 순차 재부여 */
export function renumberSentenceCart(startNum = 1) {
  const items = getSentenceCartItems();
  let cur = parseInt(startNum, 10) || 1;
  items.forEach((item) => {
    item.custom_num = String(cur++);
  });
  saveSentenceCartItems(items);
}

/** 화면에 렌더링된 모든 문장 체크박스 UI 동기화 */
export function syncAllSentenceCheckboxes() {
  const chks = document.querySelectorAll(".handout-sentence-chk");
  chks.forEach((chk) => {
    const sid = chk.dataset.id;
    if (sid) {
      const inCart = isInSentenceCart(sid);
      chk.checked = inCart;
      const lbl = chk.closest(".handout-sentence-chk-label");
      if (lbl) {
        lbl.classList.toggle("checked", inCart);
        lbl.title = inCart ? "현재 문장 프로젝트에서 제외 (클릭 시 제외)" : "문장 유인물 보관함에 담기 (클릭 시 담기)";
      }
    }
  });
}

// =========================================================================
// 4. 듣기 유인물 프로젝트 관리 (Listening Projects)
// =========================================================================

/** 문항이 영어 듣기 영역인지 판별 (1~17번 또는 area === 'listening') */
export function isListeningPassage(passageId = null) {
  const pid = passageId || appState.currentPassageId;
  if (!pid) return false;
  if (appState.currentPassage && appState.currentPassage.area === "listening") {
    return true;
  }
  const m = pid.match(/-(\d{1,2})번?\]?$/);
  if (m) {
    const qNum = parseInt(m[1], 10);
    if (qNum >= 1 && qNum <= 17) return true;
  }
  return false;
}

/** 듣기 프로젝트 목록 조회 */
export function getListeningProjects() {
  try {
    const raw = localStorage.getItem(KEY_LISTENING_PROJECTS);
    if (raw) {
      const list = JSON.parse(raw);
      if (Array.isArray(list) && list.length > 0) return list;
    }
  } catch (e) {
    console.warn("Failed to parse listening projects", e);
  }
  const defaultProj = [{
    id: "proj_listening_default",
    name: "기본 듣기 프로젝트",
    createdAt: Date.now(),
    updatedAt: Date.now(),
    items: [],
    settings: {},
  }];
  saveListeningProjects(defaultProj);
  return defaultProj;
}

/** 듣기 프로젝트 목록 저장 */
export function saveListeningProjects(projects) {
  try {
    localStorage.setItem(KEY_LISTENING_PROJECTS, JSON.stringify(projects));
  } catch (e) {
    console.warn("Failed to save listening projects", e);
  }
}

/** 현재 활성화된 듣기 프로젝트 ID */
export function getCurrentListeningProjectId() {
  const projects = getListeningProjects();
  let curId = localStorage.getItem(KEY_CURRENT_LISTENING_PROJECT_ID);
  if (!curId || !projects.some((p) => p.id === curId)) {
    curId = projects[0]?.id || "proj_listening_default";
    localStorage.setItem(KEY_CURRENT_LISTENING_PROJECT_ID, curId);
  }
  return curId;
}

/** 현재 활성화된 듣기 프로젝트 객체 */
export function getCurrentListeningProject() {
  const projects = getListeningProjects();
  const curId = getCurrentListeningProjectId();
  return projects.find((p) => p.id === curId) || projects[0];
}

/** 활성 듣기 프로젝트 전환 */
export function setCurrentListeningProject(projectId) {
  const projects = getListeningProjects();
  if (!projects.some((p) => p.id === projectId)) return;

  currentFloatingTargetType = "listening";
  localStorage.setItem(KEY_CURRENT_LISTENING_PROJECT_ID, projectId);
  window.dispatchEvent(new CustomEvent("handout-listening-project-changed", { detail: { projectId } }));
  window.dispatchEvent(new CustomEvent("handout-listening-cart-changed", { detail: getListeningCartItems() }));
  updateFloatingCartUI();
  syncAllProjectDropdowns();
}

/** 새 듣기 프로젝트 생성 */
export function createListeningProject(name) {
  const trimmed = (name || "").trim() || `듣기 프로젝트 ${new Date().toLocaleDateString()}`;
  const projects = getListeningProjects();
  const newId = `proj_listening_${Date.now()}`;
  const newProj = {
    id: newId,
    name: trimmed,
    createdAt: Date.now(),
    updatedAt: Date.now(),
    items: [],
    settings: {},
  };
  projects.push(newProj);
  saveListeningProjects(projects);
  setCurrentListeningProject(newId);
  return newProj;
}

/** 듣기 프로젝트 이름 변경 */
export function renameListeningProject(projectId, newName) {
  const trimmed = (newName || "").trim();
  if (!trimmed) return false;
  const projects = getListeningProjects();
  const proj = projects.find((p) => p.id === projectId);
  if (!proj) return false;

  proj.name = trimmed;
  proj.updatedAt = Date.now();
  saveListeningProjects(projects);
  window.dispatchEvent(new CustomEvent("handout-listening-project-changed", { detail: { projectId } }));
  updateFloatingCartUI();
  syncAllProjectDropdowns();
  return true;
}

/** 듣기 프로젝트 삭제 */
export function deleteListeningProject(projectId) {
  let projects = getListeningProjects();
  if (!projects.some((p) => p.id === projectId)) return false;

  projects = projects.filter((p) => p.id !== projectId);
  if (projects.length === 0) {
    projects = [{
      id: `proj_listening_${Date.now()}`,
      name: "기본 듣기 프로젝트",
      createdAt: Date.now(),
      updatedAt: Date.now(),
      items: [],
      settings: {},
    }];
  }
  saveListeningProjects(projects);
  const nextCurId = projects[0].id;
  localStorage.setItem(KEY_CURRENT_LISTENING_PROJECT_ID, nextCurId);

  window.dispatchEvent(new CustomEvent("handout-listening-project-changed", { detail: { projectId: nextCurId } }));
  window.dispatchEvent(new CustomEvent("handout-listening-cart-changed", { detail: projects[0].items }));
  updateFloatingCartUI();
  syncAllProjectDropdowns();
  return true;
}

/** 듣기 프로젝트 서식 설정 조회 */
export function getListeningProjectSettings(projectId = null) {
  const proj = projectId ? getListeningProjects().find((p) => p.id === projectId) : getCurrentListeningProject();
  return (proj && proj.settings) || {};
}

/** 듣기 프로젝트 서식 설정 저장 */
export function saveListeningProjectSettings(projectId, settings) {
  const projects = getListeningProjects();
  const proj = projects.find((p) => p.id === (projectId || getCurrentListeningProjectId()));
  if (proj) {
    proj.settings = { ...proj.settings, ...settings };
    proj.updatedAt = Date.now();
    saveListeningProjects(projects);
  }
}

/** 현재 활성 듣기 프로젝트의 문항 목록 조회 */
export function getListeningCartItems() {
  const proj = getCurrentListeningProject();
  return Array.isArray(proj.items) ? proj.items : [];
}

/** 현재 활성 듣기 프로젝트의 문항 목록 저장 */
export function saveListeningCartItems(items) {
  const projects = getListeningProjects();
  const curId = getCurrentListeningProjectId();
  const proj = projects.find((p) => p.id === curId);
  if (proj) {
    proj.items = items;
    proj.updatedAt = Date.now();
    saveListeningProjects(projects);
  }
  window.dispatchEvent(new CustomEvent("handout-listening-cart-changed", { detail: items }));
  updateFloatingCartUI();
}

/** 특정 문항이 현재 활성 듣기 프로젝트에 담겨있는지 확인 */
export function isInListeningCart(passageId) {
  if (!passageId) return false;
  return getListeningCartItems().some((item) => item.id === passageId);
}

/** 현재 활성 듣기 프로젝트에 문항 추가 */
export function addToListeningCart(passageId, customNum = null) {
  if (!passageId) return;
  currentFloatingTargetType = "listening";
  const items = getListeningCartItems();
  if (items.some((item) => item.id === passageId)) return;

  const nextNum = customNum || String(items.length + 1);
  items.push({ id: passageId, custom_q_num: String(nextNum) });
  saveListeningCartItems(items);
}

/** 현재 활성 듣기 프로젝트에서 문항 제거 */
export function removeFromListeningCart(passageId) {
  if (!passageId) return;
  let items = getListeningCartItems();
  items = items.filter((item) => item.id !== passageId);
  saveListeningCartItems(items);
}

/** 듣기 문항 담기/제외 토글 */
export function toggleListeningCart(passageId) {
  if (isInListeningCart(passageId)) {
    removeFromListeningCart(passageId);
    return false;
  } else {
    addToListeningCart(passageId);
    return true;
  }
}

/** 듣기 프로젝트 문항 전체 비우기 */
export function clearListeningCart() {
  saveListeningCartItems([]);
}

/** 듣기 문항 순서 변경 */
export function reorderListeningCart(fromIdx, toIdx) {
  const items = getListeningCartItems();
  if (fromIdx < 0 || fromIdx >= items.length || toIdx < 0 || toIdx >= items.length) return;
  const [moved] = items.splice(fromIdx, 1);
  items.splice(toIdx, 0, moved);
  saveListeningCartItems(items);
}

/** 특정 듣기 문항의 사용자 지정 인쇄 번호 수정 */
export function setListeningCustomQNum(passageId, customNum) {
  const items = getListeningCartItems();
  const target = items.find((item) => item.id === passageId);
  if (target) {
    target.custom_q_num = String(customNum).trim();
    saveListeningCartItems(items);
  }
}

/** 전체 듣기 문항 번호 순차 재부여 */
export function renumberListeningCart(startNum = 1) {
  const items = getListeningCartItems();
  let cur = parseInt(startNum, 10) || 1;
  items.forEach((item) => {
    item.custom_q_num = String(cur++);
  });
  saveListeningCartItems(items);
}

// =========================================================================
// 5. UI 드롭다운 및 플로팅 카트 바 동기화
// =========================================================================

/** 모든 화면의 프로젝트 드롭다운 셀렉트 박스 동기화 */
export function syncAllProjectDropdowns() {
  // 1) 지문 유인물 프로젝트 셀렉트 박스
  const passageDropdowns = [
    document.getElementById("selectHandoutPassageProject"),
    document.getElementById("selectHandoutProject"), // 하위 호환
  ];
  const pProjects = getPassageProjects();
  const curPId = getCurrentPassageProjectId();

  passageDropdowns.forEach((select) => {
    if (!select) return;
    let html = "";
    pProjects.forEach((p) => {
      const qCount = Array.isArray(p.items) ? p.items.length : 0;
      const isSel = p.id === curPId ? "selected" : "";
      html += `<option value="${p.id}" ${isSel}>${escapeHtml(p.name)} (${qCount}문항)</option>`;
    });
    select.innerHTML = html;
  });

  // 지문 제작소 생성일 메타 정보
  const pMetaEl = document.getElementById("txtPassageProjectMetaInfo") || document.getElementById("txtProjectMetaInfo");
  if (pMetaEl) {
    const curPProj = getCurrentPassageProject();
    if (curPProj && curPProj.createdAt) {
      const d = new Date(curPProj.createdAt);
      pMetaEl.textContent = `생성일: ${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
    } else {
      pMetaEl.textContent = "";
    }
  }

  // 2) 문장 유인물 프로젝트 셀렉트 박스
  const selectSentenceProj = document.getElementById("selectHandoutSentenceProject");
  const sProjects = getSentenceProjects();
  const curSId = getCurrentSentenceProjectId();

  if (selectSentenceProj) {
    let html = "";
    sProjects.forEach((p) => {
      const sCount = Array.isArray(p.sentence_items) ? p.sentence_items.length : 0;
      const isSel = p.id === curSId ? "selected" : "";
      html += `<option value="${p.id}" ${isSel}>${escapeHtml(p.name)} (${sCount}문장)</option>`;
    });
    selectSentenceProj.innerHTML = html;
  }

  // 문장 제작소 생성일 메타 정보
  const sMetaEl = document.getElementById("txtSentenceProjectMetaInfo");
  if (sMetaEl) {
    const curSProj = getCurrentSentenceProject();
    if (curSProj && curSProj.createdAt) {
      const d = new Date(curSProj.createdAt);
      sMetaEl.textContent = `생성일: ${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
    } else {
      sMetaEl.textContent = "";
    }
  }

  // 3) 듣기 유인물 프로젝트 셀렉트 박스
  const selectListeningProj = document.getElementById("selectHandoutListeningProject");
  const lProjects = getListeningProjects();
  const curLId = getCurrentListeningProjectId();

  if (selectListeningProj) {
    let html = "";
    lProjects.forEach((p) => {
      const lCount = Array.isArray(p.items) ? p.items.length : 0;
      const isSel = p.id === curLId ? "selected" : "";
      html += `<option value="${p.id}" ${isSel}>${escapeHtml(p.name)} (${lCount}문항)</option>`;
    });
    selectListeningProj.innerHTML = html;
  }

  // 듣기 제작소 생성일 메타 정보
  const lMetaEl = document.getElementById("txtListeningProjectMetaInfo");
  if (lMetaEl) {
    const curLProj = getCurrentListeningProject();
    if (curLProj && curLProj.createdAt) {
      const d = new Date(curLProj.createdAt);
      lMetaEl.textContent = `생성일: ${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
    } else {
      lMetaEl.textContent = "";
    }
  }

  // 4) 하단 플로팅 카트 바 프로젝트 셀렉트 박스 (독해 / 문장 / 듣기 프로젝트 그룹화)
  const selFloating = document.getElementById("selectFloatingHandoutProject");
  if (selFloating) {
    let html = "";

    // 1) 독해 프로젝트 그룹
    html += `<optgroup label="📄 독해 프로젝트">`;
    pProjects.forEach((p) => {
      const cnt = Array.isArray(p.items) ? p.items.length : 0;
      const isSel = (currentFloatingTargetType === "passage" && p.id === curPId) ? "selected" : "";
      html += `<option value="${p.id}" ${isSel}>${escapeHtml(p.name)} (${cnt}문항)</option>`;
    });
    html += `</optgroup>`;

    // 2) 문장 프로젝트 그룹
    html += `<optgroup label="📝 문장 프로젝트">`;
    sProjects.forEach((p) => {
      const cnt = Array.isArray(p.sentence_items) ? p.sentence_items.length : 0;
      const isSel = (currentFloatingTargetType === "sentence" && p.id === curSId) ? "selected" : "";
      html += `<option value="${p.id}" ${isSel}>${escapeHtml(p.name)} (${cnt}문장)</option>`;
    });
    html += `</optgroup>`;

    // 3) 듣기 프로젝트 그룹
    html += `<optgroup label="🎧 듣기 프로젝트">`;
    lProjects.forEach((p) => {
      const cnt = Array.isArray(p.items) ? p.items.length : 0;
      const isSel = (currentFloatingTargetType === "listening" && p.id === curLId) ? "selected" : "";
      html += `<option value="${p.id}" ${isSel}>${escapeHtml(p.name)} (${cnt}문항)</option>`;
    });
    html += `</optgroup>`;

    selFloating.innerHTML = html;
  }
}

/** HTML 특수문자 이스케이프 헬퍼 */
function escapeHtml(str) {
  if (!str) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

/** 하단 플로팅 장바구니 바 UI 갱신 (선택된 프로젝트 영역의 정보만 콤팩트하게 노출) */
export function updateFloatingCartUI() {
  const floatingBar = document.getElementById("handoutFloatingCart");
  const countBadge = document.getElementById("cartCountBadge");
  const btnOpenPassage = document.getElementById("btnOpenPassageHandoutView");
  const btnOpenSentence = document.getElementById("btnOpenSentenceHandoutView");
  const btnOpenListening = document.getElementById("btnOpenListeningHandoutView");
  const btnFloatingCreate = document.getElementById("btnFloatingCreateProject");
  const btnClearFloating = document.getElementById("btnClearFloatingCart");
  const cntPassageEl = document.getElementById("floatingPassageCount");
  const cntSentenceEl = document.getElementById("floatingSentenceCount");
  const cntListeningEl = document.getElementById("floatingListeningCount");

  const pItems = getCartItems();
  const sItems = getSentenceCartItems();
  const lItems = getListeningCartItems();

  const pProjects = getPassageProjects();
  const sProjects = getSentenceProjects();
  const lProjects = getListeningProjects();

  // 각각의 버튼 내부 카운트 배지 갱신
  if (cntPassageEl) cntPassageEl.textContent = pItems.length;
  if (cntSentenceEl) cntSentenceEl.textContent = sItems.length;
  if (cntListeningEl) cntListeningEl.textContent = lItems.length;

  // 선택된 프로젝트 영역에 맞춰 배지 텍스트/스타일 및 이동 버튼을 전환하여 패널 너비 축소
  if (currentFloatingTargetType === "sentence") {
    if (countBadge) {
      countBadge.textContent = `문장 ${sItems.length}개`;
      countBadge.className = "cart-count-badge badge-sentence";
    }
    if (btnOpenSentence) btnOpenSentence.style.display = "inline-flex";
    if (btnOpenPassage) btnOpenPassage.style.display = "none";
    if (btnOpenListening) btnOpenListening.style.display = "none";
    if (btnFloatingCreate) btnFloatingCreate.title = "새 문장 프로젝트 생성";
    if (btnClearFloating) btnClearFloating.title = "현재 문장 프로젝트 보관함 비우기";
  } else if (currentFloatingTargetType === "listening") {
    if (countBadge) {
      countBadge.textContent = `듣기 ${lItems.length}문항`;
      countBadge.className = "cart-count-badge badge-listening";
    }
    if (btnOpenListening) btnOpenListening.style.display = "inline-flex";
    if (btnOpenPassage) btnOpenPassage.style.display = "none";
    if (btnOpenSentence) btnOpenSentence.style.display = "none";
    if (btnFloatingCreate) btnFloatingCreate.title = "새 듣기 프로젝트 생성";
    if (btnClearFloating) btnClearFloating.title = "현재 듣기 프로젝트 보관함 비우기";
  } else {
    if (countBadge) {
      countBadge.textContent = `독해 ${pItems.length}문항`;
      countBadge.className = "cart-count-badge badge-passage";
    }
    if (btnOpenPassage) btnOpenPassage.style.display = "inline-flex";
    if (btnOpenSentence) btnOpenSentence.style.display = "none";
    if (btnOpenListening) btnOpenListening.style.display = "none";
    if (btnFloatingCreate) btnFloatingCreate.title = "새 독해 프로젝트 생성";
    if (btnClearFloating) btnClearFloating.title = "현재 독해 프로젝트 보관함 비우기";
  }

  // 제작소 화면이 열려있지 않을 때만 플로팅 바 표시
  const handoutView = document.getElementById("handoutViewContainer");
  const isHandoutViewActive = handoutView && handoutView.style.display !== "none";

  const hasAnyPassage = pProjects.some((p) => Array.isArray(p.items) && p.items.length > 0);
  const hasAnySentence = sProjects.some((p) => Array.isArray(p.sentence_items) && p.sentence_items.length > 0);
  const hasAnyListening = lProjects.some((p) => Array.isArray(p.items) && p.items.length > 0);
  const shouldShow = (pItems.length > 0 || sItems.length > 0 || lItems.length > 0 || hasAnyPassage || hasAnySentence || hasAnyListening);

  if (floatingBar) {
    if (shouldShow && !isHandoutViewActive) {
      floatingBar.style.display = "flex";
    } else {
      floatingBar.style.display = "none";
    }
  }

  // 체크박스 및 드롭다운 동기화
  syncCurrentPassageCheckbox();
  syncAllSentenceCheckboxes();
  syncAllProjectDropdowns();
}

/** 현재 열람 중인 지문의 체크박스 상태 동기화 (독해 vs 듣기 스마트 분기) */
export function syncCurrentPassageCheckbox() {
  const chkCurrent = document.getElementById("chkHandoutSelectCurrent");
  const lblCurrent = document.getElementById("labelHandoutSelectCurrent");
  const txtLabel = document.getElementById("txtHandoutSelectLabel");
  const curPid = appState.currentPassageId;

  if (chkCurrent) {
    const isListening = isListeningPassage(curPid);
    const inCart = curPid ? (isListening ? isInListeningCart(curPid) : isInCart(curPid)) : false;
    chkCurrent.checked = inCart;
    if (lblCurrent) {
      lblCurrent.classList.toggle("checked", inCart);
      if (isListening) {
        lblCurrent.title = inCart ? "현재 듣기 프로젝트에서 제외합니다 (클릭 시 제외)" : "현재 듣기 프로젝트에 담습니다 (클릭 시 담기)";
      } else {
        lblCurrent.title = inCart ? "현재 독해 프로젝트에서 제외합니다 (클릭 시 제외)" : "현재 독해 프로젝트에 담습니다 (클릭 시 담기)";
      }
    }
    if (txtLabel) {
      if (isListening) {
        txtLabel.textContent = inCart ? "✔ 듣기 담김" : "🎧 듣기 유인물 담기";
      } else {
        txtLabel.textContent = inCart ? "✔ 독해 담김" : "📄 독해 유인물 담기";
      }
    }
  }
}

/** 전체 이벤트 초기화 */
export function initHandoutCart() {
  const btnOpenPassage = document.getElementById("btnOpenPassageHandoutView");
  const btnOpenSentence = document.getElementById("btnOpenSentenceHandoutView");
  const btnOpenListening = document.getElementById("btnOpenListeningHandoutView");
  const btnOpen = document.getElementById("btnOpenHandoutView");
  const btnClear = document.getElementById("btnClearFloatingCart");

  if (btnOpenPassage) {
    btnOpenPassage.addEventListener("click", () => {
      import("./navigation.js").then((m) => {
        if (m.switchToHandoutView) m.switchToHandoutView("passage");
      });
    });
  }

  if (btnOpenSentence) {
    btnOpenSentence.addEventListener("click", () => {
      import("./navigation.js").then((m) => {
        if (m.switchToHandoutView) m.switchToHandoutView("sentence");
      });
    });
  }

  if (btnOpenListening) {
    btnOpenListening.addEventListener("click", () => {
      import("./navigation.js").then((m) => {
        if (m.switchToHandoutView) m.switchToHandoutView("listening");
      });
    });
  }

  if (btnOpen) {
    btnOpen.addEventListener("click", () => {
      import("./navigation.js").then((m) => {
        const targetTab = (appState.currentMode === "sentence") ? "sentence" : "passage";
        if (m.switchToHandoutView) m.switchToHandoutView(targetTab);
      });
    });
  }

  if (btnClear) {
    btnClear.addEventListener("click", (e) => {
      e.stopPropagation();
      if (currentFloatingTargetType === "sentence") {
        const curSProj = getCurrentSentenceProject();
        const sItems = getSentenceCartItems();
        if (sItems.length === 0) {
          alert("현재 선택된 문장 프로젝트에 담긴 문장이 없습니다.");
          return;
        }
        if (confirm(`'${curSProj.name}' 문장 프로젝트의 모든 문장(${sItems.length}개)을 비우시겠습니까?`)) {
          clearSentenceCart();
        }
      } else if (currentFloatingTargetType === "listening") {
        const curLProj = getCurrentListeningProject();
        const lItems = getListeningCartItems();
        if (lItems.length === 0) {
          alert("현재 선택된 듣기 프로젝트에 담긴 문항이 없습니다.");
          return;
        }
        if (confirm(`'${curLProj.name}' 듣기 프로젝트의 모든 문항(${lItems.length}개)을 비우시겠습니까?`)) {
          clearListeningCart();
        }
      } else {
        const curPProj = getCurrentPassageProject();
        const pItems = getCartItems();
        if (pItems.length === 0) {
          alert("현재 선택된 독해 프로젝트에 담긴 문항이 없습니다.");
          return;
        }
        if (confirm(`'${curPProj.name}' 독해 프로젝트의 모든 문항(${pItems.length}개)을 비우시겠습니까?`)) {
          clearCart();
        }
      }
    });
  }

  // 지문 결과 화면 좌측 상단 패널: 체크박스 토글 (독해 vs 듣기 스마트 분기)
  const chkCurrent = document.getElementById("chkHandoutSelectCurrent");
  if (chkCurrent) {
    chkCurrent.addEventListener("change", () => {
      if (appState.currentPassageId) {
        const isListening = isListeningPassage(appState.currentPassageId);
        if (chkCurrent.checked) {
          if (isListening) {
            addToListeningCart(appState.currentPassageId);
          } else {
            addToCart(appState.currentPassageId);
          }
        } else {
          if (isListening) {
            removeFromListeningCart(appState.currentPassageId);
          } else {
            removeFromCart(appState.currentPassageId);
          }
        }
      }
    });
  }

  // 하단 플로팅 장바구니 바: 프로젝트 전환 (선택한 프로젝트 영역으로 즉시 전환 및 컴팩트화)
  const selFloatingProj = document.getElementById("selectFloatingHandoutProject");
  if (selFloatingProj) {
    selFloatingProj.addEventListener("change", (e) => {
      const val = e.target.value;
      const sProjects = getSentenceProjects();
      const lProjects = getListeningProjects();
      const isSentProj = sProjects.some((p) => p.id === val);
      const isListProj = lProjects.some((p) => p.id === val);

      if (isSentProj) {
        currentFloatingTargetType = "sentence";
        setCurrentSentenceProject(val);
      } else if (isListProj) {
        currentFloatingTargetType = "listening";
        setCurrentListeningProject(val);
      } else {
        currentFloatingTargetType = "passage";
        setCurrentPassageProject(val);
      }
      updateFloatingCartUI();
    });
  }

  // 하단 플로팅 장바구니 바: 새 프로젝트 생성 (선택된 프로젝트 영역에 맞춤)
  const btnFloatingCreate = document.getElementById("btnFloatingCreateProject");
  if (btnFloatingCreate) {
    btnFloatingCreate.addEventListener("click", () => {
      let areaLabel = "독해";
      if (currentFloatingTargetType === "sentence") areaLabel = "문장";
      else if (currentFloatingTargetType === "listening") areaLabel = "듣기";

      const defaultName = `새 ${areaLabel} 프로젝트`;
      const name = prompt(`새 ${areaLabel} 프로젝트 이름을 입력하세요:`, defaultName);
      if (name !== null) {
        if (currentFloatingTargetType === "sentence") {
          createSentenceProject(name);
        } else if (currentFloatingTargetType === "listening") {
          createListeningProject(name);
        } else {
          createPassageProject(name);
        }
        updateFloatingCartUI();
      }
    });
  }

  // 독해 제작소: 프로젝트 드롭다운 및 버튼
  const selPassageProj = document.getElementById("selectHandoutPassageProject") || document.getElementById("selectHandoutProject");
  if (selPassageProj) {
    selPassageProj.addEventListener("change", (e) => {
      setCurrentPassageProject(e.target.value);
    });
  }

  const btnCreatePassage = document.getElementById("btnCreatePassageProject") || document.getElementById("btnCreateNewProject");
  if (btnCreatePassage) {
    btnCreatePassage.addEventListener("click", () => {
      const name = prompt("새 독해 유인물 프로젝트 이름을 입력하세요:", "");
      if (name !== null) {
        createPassageProject(name);
      }
    });
  }

  const btnRenamePassage = document.getElementById("btnRenamePassageProject") || document.getElementById("btnRenameCurrentProject");
  if (btnRenamePassage) {
    btnRenamePassage.addEventListener("click", () => {
      const curProj = getCurrentPassageProject();
      const newName = prompt("독해 프로젝트의 새 이름을 입력하세요:", curProj.name);
      if (newName !== null && newName.trim()) {
        renamePassageProject(curProj.id, newName);
      }
    });
  }

  const btnDeletePassage = document.getElementById("btnDeletePassageProject") || document.getElementById("btnDeleteCurrentProject");
  if (btnDeletePassage) {
    btnDeletePassage.addEventListener("click", () => {
      const curProj = getCurrentPassageProject();
      if (confirm(`'${curProj.name}' 독해 프로젝트를 삭제하시겠습니까?\n담긴 문항들도 함께 삭제됩니다.`)) {
        deletePassageProject(curProj.id);
      }
    });
  }

  // 문장 제작소: 프로젝트 드롭다운 및 버튼
  const selSentenceProj = document.getElementById("selectHandoutSentenceProject");
  if (selSentenceProj) {
    selSentenceProj.addEventListener("change", (e) => {
      setCurrentSentenceProject(e.target.value);
    });
  }

  const btnCreateSentence = document.getElementById("btnCreateSentenceProject");
  if (btnCreateSentence) {
    btnCreateSentence.addEventListener("click", () => {
      const name = prompt("새 문장 유인물 프로젝트 이름을 입력하세요:", "");
      if (name !== null) {
        createSentenceProject(name);
      }
    });
  }

  const btnRenameSentence = document.getElementById("btnRenameSentenceProject");
  if (btnRenameSentence) {
    btnRenameSentence.addEventListener("click", () => {
      const curProj = getCurrentSentenceProject();
      const newName = prompt("문장 프로젝트의 새 이름을 입력하세요:", curProj.name);
      if (newName !== null && newName.trim()) {
        renameSentenceProject(curProj.id, newName);
      }
    });
  }

  const btnDeleteSentence = document.getElementById("btnDeleteSentenceProject");
  if (btnDeleteSentence) {
    btnDeleteSentence.addEventListener("click", () => {
      const curProj = getCurrentSentenceProject();
      if (confirm(`'${curProj.name}' 문장 프로젝트를 삭제하시겠습니까?\n담긴 문장들도 함께 삭제됩니다.`)) {
        deleteSentenceProject(curProj.id);
      }
    });
  }

  // 듣기 제작소: 프로젝트 드롭다운 및 버튼
  const selListeningProj = document.getElementById("selectHandoutListeningProject");
  if (selListeningProj) {
    selListeningProj.addEventListener("change", (e) => {
      setCurrentListeningProject(e.target.value);
    });
  }

  const btnCreateListening = document.getElementById("btnCreateListeningProject");
  if (btnCreateListening) {
    btnCreateListening.addEventListener("click", () => {
      const name = prompt("새 듣기 유인물 프로젝트 이름을 입력하세요:", "");
      if (name !== null) {
        createListeningProject(name);
      }
    });
  }

  const btnRenameListening = document.getElementById("btnRenameListeningProject");
  if (btnRenameListening) {
    btnRenameListening.addEventListener("click", () => {
      const curProj = getCurrentListeningProject();
      const newName = prompt("듣기 프로젝트의 새 이름을 입력하세요:", curProj.name);
      if (newName !== null && newName.trim()) {
        renameListeningProject(curProj.id, newName);
      }
    });
  }

  const btnDeleteListening = document.getElementById("btnDeleteListeningProject");
  if (btnDeleteListening) {
    btnDeleteListening.addEventListener("click", () => {
      const curProj = getCurrentListeningProject();
      if (confirm(`'${curProj.name}' 듣기 프로젝트를 삭제하시겠습니까?\n담긴 문항들도 함께 삭제됩니다.`)) {
        deleteListeningProject(curProj.id);
      }
    });
  }

  updateFloatingCartUI();
}
