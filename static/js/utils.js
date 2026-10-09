/**
 * 05-gichul_db: 클립보드 · 토스트 · HTML 이스케이프 헬퍼 (섹션 9) (utils.js)
 * - main.js 에서 분리
 */

// =========================================================================
// 9. 클립보드 복사 & 토스트 알림 헬퍼
// =========================================================================

export function copyToClipboard(text, successMsg) {
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

export function showToast(message, type = "info") {
  const toastContainer = document.getElementById("toastContainer");
  if (!toastContainer) return;

  const toast = document.createElement("div");
  toast.className = `toast ${type}`;

  // 메시지 앞단에 아이콘이 없는 경우 기본 상태 아이콘 부여
  const hasEmoji = /[\u{1F300}-\u{1F9FF}\u{2600}-\u{27BF}]/u.test(message);
  let iconPrefix = "";
  if (!hasEmoji) {
    if (type === "success") iconPrefix = "✅ ";
    else if (type === "error") iconPrefix = "❌ ";
    else if (type === "warning") iconPrefix = "⚠️ ";
    else iconPrefix = "ℹ️ ";
  }

  const span = document.createElement("span");
  span.textContent = `${iconPrefix}${message}`;
  toast.appendChild(span);
  toastContainer.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = "0";
    toast.style.transform = "translateY(-12px) scale(0.96)";
    toast.style.transition = "all 0.25s cubic-bezier(0.16, 1, 0.3, 1)";
    setTimeout(() => toast.remove(), 250);
  }, 2800);
}

// 유틸 함수
export function escapeHtml(text) {
  if (!text) return "";
  return String(text)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

export function cssSafeId(id) {
  return id.replace(/[^a-zA-Z0-9_-]/g, "_");
}
