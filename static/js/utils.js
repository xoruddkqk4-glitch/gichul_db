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

/**
 * 유사 지문 검색 결과(고유명사, 연속 3·4단어 스팬, 표현, 핵심 단어)를
 * 원문 텍스트에서 겹침 없이 다색 <mark> 하이라이트 HTML로 변환한다.
 */
export function highlightSimilarMatches(rawText, matchInfo) {
  if (!rawText) return "";
  if (!matchInfo) return escapeHtml(rawText);

  const escapeRe = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const buildTokenSeqPattern = (phrase) => {
    const toks = String(phrase || "").toLowerCase().match(/[a-z0-9']+/g);
    if (!toks || toks.length === 0) return null;
    return `(?<![A-Za-z0-9'])${toks.map(escapeRe).join("[^A-Za-z0-9']+")}(?![A-Za-z0-9'])`;
  };
  const buildKeywordPattern = (kw) => {
    const w = String(kw || "").trim().toLowerCase();
    if (!w || !/^[a-z0-9'-]+$/.test(w)) return null;
    if (w.length >= 5 && w.endsWith("y")) {
      const stem = escapeRe(w.slice(0, -1));
      return `(?<![A-Za-z0-9'])${stem}(?:y|ies|ied)(?![A-Za-z0-9'])`;
    }
    if (w.length >= 4) {
      return `(?<![A-Za-z0-9'])${escapeRe(w)}(?:s|es|ed|ing)?(?![A-Za-z0-9'])`;
    }
    return `(?<![A-Za-z0-9'])${escapeRe(w)}(?![A-Za-z0-9'])`;
  };

  const groups = [
    {
      cls: "sim-hl-ngram",
      terms: [
        ...(matchInfo.merged_matched_spans || []),
        ...(matchInfo.matched_ngrams_4 || []),
        ...(matchInfo.matched_ngrams_3 || []),
      ],
      multiWord: true,
    },
    {
      cls: "sim-hl-entity",
      terms: matchInfo.matched_proper_nouns || [],
      multiWord: true,
    },
    {
      cls: "sim-hl-phrase",
      terms: matchInfo.matched_phrases || [],
      multiWord: true,
    },
    {
      cls: "sim-hl-keyword",
      terms: matchInfo.matched_keywords || [],
      multiWord: false,
    },
  ];

  // 우선순위(그룹 순서 -> 긴 문자열 우선) 순으로 비겹침 매칭 구간 수집
  const intervals = [];
  const overlaps = (s, e) => intervals.some((iv) => !(e <= iv.s || s >= iv.e));

  for (const grp of groups) {
    const uniqueTerms = Array.from(new Set((grp.terms || []).filter(Boolean)))
      .sort((a, b) => String(b).length - String(a).length);
    for (const term of uniqueTerms) {
      const pat = grp.multiWord ? buildTokenSeqPattern(term) : buildKeywordPattern(term);
      if (!pat) continue;
      let re;
      try {
        re = new RegExp(pat, "gi");
      } catch (_err) {
        continue;
      }
      let m;
      while ((m = re.exec(rawText)) !== null) {
        const s = m.index;
        const e = s + m[0].length;
        if (e > s && !overlaps(s, e)) {
          intervals.push({ s, e, cls: grp.cls });
        }
      }
    }
  }

  if (intervals.length === 0) return escapeHtml(rawText);
  intervals.sort((a, b) => a.s - b.s);

  let out = "";
  let cursor = 0;
  for (const iv of intervals) {
    if (iv.s > cursor) {
      out += escapeHtml(rawText.slice(cursor, iv.s));
    }
    out += `<mark class="${iv.cls}">${escapeHtml(rawText.slice(iv.s, iv.e))}</mark>`;
    cursor = iv.e;
  }
  if (cursor < rawText.length) {
    out += escapeHtml(rawText.slice(cursor));
  }
  return out;
}
