/**
 * 05-gichul_db: 교사용 유인물 프로젝트 및 장바구니 상태 관리 (handout-cart.js)
 * - 프로젝트별 독립된 출제 문항 목록(items), 사용자 지정 인쇄 번호(custom_q_num), 머리말 서식 설정 관리
 * - 프로젝트 생성(Create), 이름 수정(Rename), 삭제(Delete), 전환(Switch) 기능 지원
 * - 지문 결과 화면 내 [📄 유인물 담기] 체크박스 및 빠른 프로젝트 선택기 연동
 * - 하단 플로팅 장바구니 바 및 유인물 제작소 화면 실시간 반응형 동기화
 */

import { appState } from "./state.js";

const KEY_PROJECTS = "gichul_handout_projects";
const KEY_CURRENT_PROJECT_ID = "gichul_handout_current_project_id";
const OLD_STORAGE_KEY = "gichul_handout_cart";

/** 로컬스토리지에서 모든 프로젝트 목록 로드: Array<Project> */
export function getProjects() {
  try {
    const raw = localStorage.getItem(KEY_PROJECTS);
    if (raw) {
      const list = JSON.parse(raw);
      if (Array.isArray(list) && list.length > 0) {
        return list;
      }
    }
  } catch (e) {
    console.warn("Failed to parse handout projects", e);
  }

  // 이전 단일 카트 데이터가 있으면 '기본 프로젝트'로 자동 마이그레이션
  let initialItems = [];
  try {
    const oldRaw = localStorage.getItem(OLD_STORAGE_KEY);
    if (oldRaw) {
      const parsed = JSON.parse(oldRaw);
      if (Array.isArray(parsed)) initialItems = parsed;
    }
  } catch (e) {
    // 무시
  }

  const defaultProject = {
    id: "proj_default",
    name: "기본 프로젝트",
    createdAt: Date.now(),
    updatedAt: Date.now(),
    items: initialItems,
    settings: {},
  };

  const list = [defaultProject];
  saveProjects(list);
  return list;
}

/** 프로젝트 목록 저장 헬퍼 */
function saveProjects(projects) {
  try {
    localStorage.setItem(KEY_PROJECTS, JSON.stringify(projects));
  } catch (e) {
    console.warn("Failed to save handout projects", e);
  }
}

/** 현재 활성화된 프로젝트 ID 반환 */
export function getCurrentProjectId() {
  const projects = getProjects();
  let curId = localStorage.getItem(KEY_CURRENT_PROJECT_ID);
  if (!curId || !projects.some((p) => p.id === curId)) {
    curId = projects[0]?.id || "proj_default";
    localStorage.setItem(KEY_CURRENT_PROJECT_ID, curId);
  }
  return curId;
}

/** 현재 활성화된 프로젝트 객체 반환 */
export function getCurrentProject() {
  const projects = getProjects();
  const curId = getCurrentProjectId();
  return projects.find((p) => p.id === curId) || projects[0];
}

/** 활성 프로젝트 변경 (전환) */
export function setCurrentProject(projectId) {
  const projects = getProjects();
  if (!projects.some((p) => p.id === projectId)) return;

  localStorage.setItem(KEY_CURRENT_PROJECT_ID, projectId);
  window.dispatchEvent(new CustomEvent("handout-project-changed", { detail: { projectId } }));
  window.dispatchEvent(new CustomEvent("handout-cart-changed", { detail: getCartItems() }));
  updateFloatingCartUI();
  syncAllProjectDropdowns();
}

/** 새 프로젝트 생성 */
export function createProject(name) {
  const trimmed = (name || "").trim() || `새 프로젝트 ${new Date().toLocaleDateString()}`;
  const projects = getProjects();
  const newId = `proj_${Date.now()}`;
  const newProject = {
    id: newId,
    name: trimmed,
    createdAt: Date.now(),
    updatedAt: Date.now(),
    items: [],
    settings: {},
  };

  projects.push(newProject);
  saveProjects(projects);
  setCurrentProject(newId);
  return newProject;
}

/** 프로젝트 이름 변경 */
export function renameProject(projectId, newName) {
  const trimmed = (newName || "").trim();
  if (!trimmed) return false;

  const projects = getProjects();
  const proj = projects.find((p) => p.id === projectId);
  if (!proj) return false;

  proj.name = trimmed;
  proj.updatedAt = Date.now();
  saveProjects(projects);

  window.dispatchEvent(new CustomEvent("handout-project-changed", { detail: { projectId } }));
  updateFloatingCartUI();
  syncAllProjectDropdowns();
  return true;
}

/** 프로젝트 삭제 */
export function deleteProject(projectId) {
  let projects = getProjects();
  if (!projects.some((p) => p.id === projectId)) return false;

  projects = projects.filter((p) => p.id !== projectId);
  if (projects.length === 0) {
    projects = [{
      id: `proj_${Date.now()}`,
      name: "기본 프로젝트",
      createdAt: Date.now(),
      updatedAt: Date.now(),
      items: [],
      settings: {},
    }];
  }

  saveProjects(projects);
  const nextCurId = projects[0].id;
  localStorage.setItem(KEY_CURRENT_PROJECT_ID, nextCurId);

  window.dispatchEvent(new CustomEvent("handout-project-changed", { detail: { projectId: nextCurId } }));
  window.dispatchEvent(new CustomEvent("handout-cart-changed", { detail: projects[0].items }));
  updateFloatingCartUI();
  syncAllProjectDropdowns();
  return true;
}

/** 프로젝트별 서식 설정 조회 */
export function getProjectSettings(projectId = null) {
  const curProj = projectId ? getProjects().find((p) => p.id === projectId) : getCurrentProject();
  return (curProj && curProj.settings) || {};
}

/** 프로젝트별 서식 설정 저장 */
export function saveProjectSettings(projectId, settings) {
  const projects = getProjects();
  const proj = projects.find((p) => p.id === (projectId || getCurrentProjectId()));
  if (proj) {
    proj.settings = { ...proj.settings, ...settings };
    proj.updatedAt = Date.now();
    saveProjects(projects);
  }
}

// =========================================================================
// 활성 프로젝트 내 문항 목록(items) 관리 (기존 카트 인터페이스 호환)
// =========================================================================

/** 현재 활성 프로젝트의 카트 목록 로드: Array<{ id: string, custom_q_num: string }> */
export function getCartItems() {
  const proj = getCurrentProject();
  return Array.isArray(proj.items) ? proj.items : [];
}

/** 현재 활성 프로젝트의 카트 목록 저장 */
export function saveCartItems(items) {
  const projects = getProjects();
  const curId = getCurrentProjectId();
  const proj = projects.find((p) => p.id === curId);
  if (proj) {
    proj.items = items;
    proj.updatedAt = Date.now();
    saveProjects(projects);
  }
  window.dispatchEvent(new CustomEvent("handout-cart-changed", { detail: items }));
  updateFloatingCartUI();
}

/** 특정 문항이 현재 활성 프로젝트에 담겨있는지 확인 */
export function isInCart(passageId) {
  if (!passageId) return false;
  const items = getCartItems();
  return items.some((item) => item.id === passageId);
}

/** 현재 활성 프로젝트에 문항 추가 */
export function addToCart(passageId, customNum = null) {
  if (!passageId) return;
  const items = getCartItems();
  if (items.some((item) => item.id === passageId)) return;

  const nextNum = customNum || String(items.length + 1);
  items.push({ id: passageId, custom_q_num: String(nextNum) });
  saveCartItems(items);
}

/** 현재 활성 프로젝트에서 문항 제거 */
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

/** 현재 활성 프로젝트 문항 전체 비우기 */
export function clearCart() {
  saveCartItems([]);
}

/** 문항 순서 변경 (fromIdx -> toIdx) */
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
// UI 동기화 및 렌더링
// =========================================================================

/** 모든 화면의 프로젝트 드롭다운 셀렉트 박스 동기화 */
export function syncAllProjectDropdowns() {
  const projects = getProjects();
  const curId = getCurrentProjectId();

  const dropdowns = [
    document.getElementById("selectHandoutProject"),
    document.getElementById("selectFloatingHandoutProject"),
  ];

  dropdowns.forEach((select) => {
    if (!select) return;
    const currentVal = curId;
    let html = "";
    projects.forEach((p) => {
      const qCount = Array.isArray(p.items) ? p.items.length : 0;
      const isSel = p.id === currentVal ? "selected" : "";
      html += `<option value="${p.id}" ${isSel}>${escapeHtml(p.name)} (${qCount}문항)</option>`;
    });
    select.innerHTML = html;
  });

  // 제작소 화면 메타정보(생성일) 갱신
  const metaEl = document.getElementById("txtProjectMetaInfo");
  if (metaEl) {
    const curProj = getCurrentProject();
    if (curProj && curProj.createdAt) {
      const d = new Date(curProj.createdAt);
      metaEl.textContent = `생성일: ${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
    } else {
      metaEl.textContent = "";
    }
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

/** 하단 플로팅 장바구니 바 UI 갱신 */
export function updateFloatingCartUI() {
  const floatingBar = document.getElementById("handoutFloatingCart");
  const countBadge = document.getElementById("cartCountBadge");
  const projects = getProjects();
  const curProj = getCurrentProject();
  const items = getCartItems();

  if (countBadge) {
    countBadge.textContent = `${items.length}문항`;
  }

  // 유인물 제작소 화면이 열려있지 않고, 프로젝트 목록에 1개 이상의 문항이 담겨있거나 현재 프로젝트에 문항이 있을 때 플로팅 바 표시
  const handoutView = document.getElementById("handoutViewContainer");
  const isHandoutViewActive = handoutView && handoutView.style.display !== "none";
  const hasAnyItems = projects.some((p) => Array.isArray(p.items) && p.items.length > 0);

  if (floatingBar) {
    if ((items.length > 0 || hasAnyItems) && !isHandoutViewActive) {
      floatingBar.style.display = "flex";
    } else {
      floatingBar.style.display = "none";
    }
  }

  // 지문 상세 화면 체크박스 동기화
  syncCurrentPassageCheckbox();
  syncAllProjectDropdowns();
}

/** 현재 열람 중인 문항의 체크박스 상태 동기화 */
export function syncCurrentPassageCheckbox() {
  const chkCurrent = document.getElementById("chkHandoutSelectCurrent");
  const lblCurrent = document.getElementById("labelHandoutSelectCurrent");
  const txtLabel = document.getElementById("txtHandoutSelectLabel");
  const curPid = appState.currentPassageId;

  if (chkCurrent) {
    const inCart = curPid ? isInCart(curPid) : false;
    chkCurrent.checked = inCart;
    if (lblCurrent) {
      lblCurrent.classList.toggle("checked", inCart);
      lblCurrent.title = inCart ? "현재 프로젝트에서 제외합니다 (클릭 시 제외)" : "현재 프로젝트에 담습니다 (클릭 시 담기)";
    }
    if (txtLabel) {
      txtLabel.textContent = inCart ? "✔ 유인물 담김" : "📄 유인물 담기";
    }
  }
}

/** 전체 이벤트 초기화 */
export function initHandoutCart() {
  const btnOpen = document.getElementById("btnOpenHandoutView");
  const btnClear = document.getElementById("btnClearFloatingCart");

  if (btnOpen) {
    btnOpen.addEventListener("click", () => {
      import("./navigation.js").then((m) => {
        if (m.switchToHandoutView) m.switchToHandoutView();
      });
    });
  }

  if (btnClear) {
    btnClear.addEventListener("click", (e) => {
      e.stopPropagation();
      const curProj = getCurrentProject();
      if (confirm(`'${curProj.name}' 프로젝트의 모든 문항을 비우시겠습니까?`)) {
        clearCart();
      }
    });
  }

  // 지문 결과 화면 좌측 상단 패널: 체크박스 토글
  const chkCurrent = document.getElementById("chkHandoutSelectCurrent");
  if (chkCurrent) {
    chkCurrent.addEventListener("change", () => {
      if (appState.currentPassageId) {
        if (chkCurrent.checked) {
          addToCart(appState.currentPassageId);
        } else {
          removeFromCart(appState.currentPassageId);
        }
      }
    });
  }



  // 하단 플로팅 장바구니 바: 프로젝트 전환
  const selFloatingProj = document.getElementById("selectFloatingHandoutProject");
  if (selFloatingProj) {
    selFloatingProj.addEventListener("change", (e) => {
      setCurrentProject(e.target.value);
    });
  }

  // 하단 플로팅 장바구니 바: 새 프로젝트 생성
  const btnFloatingCreate = document.getElementById("btnFloatingCreateProject");
  if (btnFloatingCreate) {
    btnFloatingCreate.addEventListener("click", () => {
      const name = prompt("새 유인물 프로젝트 이름을 입력하세요:", "");
      if (name !== null) {
        createProject(name);
      }
    });
  }

  // 유인물 제작소 화면: 메인 프로젝트 선택 드롭다운
  const selMainProj = document.getElementById("selectHandoutProject");
  if (selMainProj) {
    selMainProj.addEventListener("change", (e) => {
      setCurrentProject(e.target.value);
    });
  }

  // 유인물 제작소: 새 프로젝트 생성
  const btnCreateNew = document.getElementById("btnCreateNewProject");
  if (btnCreateNew) {
    btnCreateNew.addEventListener("click", () => {
      const name = prompt("새 유인물 프로젝트 이름을 입력하세요:", "");
      if (name !== null) {
        createProject(name);
      }
    });
  }

  // 유인물 제작소: 프로젝트 이름 변경
  const btnRename = document.getElementById("btnRenameCurrentProject");
  if (btnRename) {
    btnRename.addEventListener("click", () => {
      const curProj = getCurrentProject();
      const newName = prompt("프로젝트의 새 이름을 입력하세요:", curProj.name);
      if (newName !== null && newName.trim()) {
        renameProject(curProj.id, newName);
      }
    });
  }

  // 유인물 제작소: 프로젝트 삭제
  const btnDelete = document.getElementById("btnDeleteCurrentProject");
  if (btnDelete) {
    btnDelete.addEventListener("click", () => {
      const curProj = getCurrentProject();
      if (confirm(`'${curProj.name}' 프로젝트를 삭제하시겠습니까?\n담긴 문항들도 함께 삭제됩니다.`)) {
        deleteProject(curProj.id);
      }
    });
  }

  updateFloatingCartUI();
}

