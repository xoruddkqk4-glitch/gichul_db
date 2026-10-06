/**
 * 05-gichul_db: 교사용 유인물 장바구니 상태 관리 및 플로팅 배지 (handout-cart.js)
 * - 선택된 문항 ID 및 사용자 지정 번호(custom_q_num) localStorage 영구 저장
 * - 하단 플로팅 장바구니 UI 실시간 동기화
 */

import { appState } from "./state.js";

const STORAGE_KEY = "gichul_handout_cart";

/** 로컬스토리지에서 카트 목록 로드: Array<{ id: string, custom_q_num: string }> */
export function getCartItems() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const items = JSON.parse(raw);
    return Array.isArray(items) ? items : [];
  } catch (e) {
    console.warn("Failed to load handout cart from localStorage", e);
    return [];
  }
}

/** 카트 목록 저장 */
function saveCartItems(items) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(items));
    window.dispatchEvent(new CustomEvent("handout-cart-changed", { detail: items }));
    updateFloatingCartUI();
  } catch (e) {
    console.warn("Failed to save handout cart to localStorage", e);
  }
}

/** 특정 문항이 카트에 담겨있는지 확인 */
export function isInCart(passageId) {
  if (!passageId) return false;
  const items = getCartItems();
  return items.some((item) => item.id === passageId);
}

/** 카트에 문항 추가 (이미 있으면 무시) */
export function addToCart(passageId, customNum = null) {
  if (!passageId) return;
  const items = getCartItems();
  if (items.some((item) => item.id === passageId)) return;

  const nextNum = customNum || String(items.length + 1);
  items.push({ id: passageId, custom_q_num: String(nextNum) });
  saveCartItems(items);
}

/** 카트에서 문항 제거 */
export function removeFromCart(passageId) {
  if (!passageId) return;
  let items = getCartItems();
  items = items.filter((item) => item.id !== passageId);
  saveCartItems(items);
}

/** 카트 토글 (있으면 제거, 없으면 추가) */
export function toggleCart(passageId) {
  if (isInCart(passageId)) {
    removeFromCart(passageId);
    return false;
  } else {
    addToCart(passageId);
    return true;
  }
}

/** 카트 전체 비우기 */
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

/** 특정 문항의 사용자 지정 번호 수정 */
export function setCustomQNum(passageId, customNum) {
  const items = getCartItems();
  const target = items.find((item) => item.id === passageId);
  if (target) {
    target.custom_q_num = String(customNum).trim();
    saveCartItems(items);
  }
}

/** 전체 문항 번호 시작 번호부터 순차 재부여 */
export function renumberCart(startNum = 1) {
  const items = getCartItems();
  let cur = parseInt(startNum, 10) || 1;
  items.forEach((item) => {
    item.custom_q_num = String(cur++);
  });
  saveCartItems(items);
}

/** 하단 플로팅 장바구니 바 UI 갱신 */
export function updateFloatingCartUI() {
  const floatingBar = document.getElementById("handoutFloatingCart");
  const countBadge = document.getElementById("cartCountBadge");
  const items = getCartItems();

  if (countBadge) countBadge.textContent = `${items.length}문항`;

  // 유인물 제작소 화면이 열려있지 않고 문항이 1개 이상 담겨있을 때만 플로팅 바 표시
  const handoutView = document.getElementById("handoutViewContainer");
  const isHandoutViewActive = handoutView && handoutView.style.display !== "none";

  if (floatingBar) {
    if (items.length > 0 && !isHandoutViewActive) {
      floatingBar.style.display = "flex";
    } else {
      floatingBar.style.display = "none";
    }
  }

  // 지문 상세 화면 체크박스 동기화
  syncCurrentPassageCheckbox();
  syncExamToggleAllButton();
}

/** 현재 열람 중인 문항의 체크박스 상태 동기화 */
export function syncCurrentPassageCheckbox() {
  const chkCurrent = document.getElementById("chkHandoutSelectCurrent");
  const lblCurrent = document.getElementById("labelHandoutSelectCurrent");
  const curPid = appState.currentPassageId;

  if (chkCurrent) {
    const inCart = curPid ? isInCart(curPid) : false;
    chkCurrent.checked = inCart;
    if (lblCurrent) lblCurrent.classList.toggle("checked", inCart);
  }
}

/** 시험 전체 담기 버튼 상태 동기화 */
export function syncExamToggleAllButton() {
  const btnToggleAll = document.getElementById("btnHandoutToggleAllExam");
  const examQuestions = appState.currentExamQuestions || [];

  if (btnToggleAll) {
    if (examQuestions.length > 0) {
      const allSelected = examQuestions.every((q) => isInCart(q.id));
      btnToggleAll.textContent = allSelected ? "📑 시험 전체 제외" : "📑 시험 전체 담기";
      btnToggleAll.style.display = "inline-flex";
    } else {
      btnToggleAll.style.display = "none";
    }
  }
}

/** 초기 이벤트 바인딩 */
export function initHandoutCart() {
  const btnOpen = document.getElementById("btnOpenHandoutView");
  const btnClear = document.getElementById("btnClearFloatingCart");

  if (btnOpen) {
    btnOpen.addEventListener("click", () => {
      import("./navigation.js").then((m) => {
        if (m.switchToHandoutView) {
          m.switchToHandoutView();
        }
      });
    });
  }

  if (btnClear) {
    btnClear.addEventListener("click", (e) => {
      e.stopPropagation();
      if (confirm("유인물 보관함에 담긴 문항을 모두 비우시겠습니까?")) {
        clearCart();
      }
    });
  }

  // 현재 열람 문항 체크박스 토글
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

  // 현재 시험 전체 문항 담기/제외
  const btnToggleAll = document.getElementById("btnHandoutToggleAllExam");
  if (btnToggleAll) {
    btnToggleAll.addEventListener("click", () => {
      const examQuestions = appState.currentExamQuestions || [];
      if (examQuestions.length === 0) return;
      const allSelected = examQuestions.every((q) => isInCart(q.id));
      if (allSelected) {
        examQuestions.forEach((q) => removeFromCart(q.id));
      } else {
        examQuestions.forEach((q) => addToCart(q.id));
      }
    });
  }

  updateFloatingCartUI();
}

