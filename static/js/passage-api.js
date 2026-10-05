/**
 * 05-gichul_db: 지문 관련 서버 API 통신 및 데이터 캐시 모듈 (passage-api.js)
 * - 시험 단위 지문 상세 목록 캐시 및 프리페치
 * - 지문 메모(노트) 저장 API
 * - 문제 유형 및 정답 수동 수정 API
 * - 지문 태그 추가 및 삭제 API
 * - PDF 문항 캡처 재생성 API
 * - 시험지 5종 원본 파일 다운로드 (PDF, HWP, Script, Ans, CSV, All ZIP)
 * - TTS 음성 합성 작업 상태(Active Job), 진행률 폴링 및 생성 API
 */

import { appState } from "./state.js";

// 시험 단위 지문 상세 데이터 로드 캐시 (시험 ID -> Map<문항ID, 상세데이터>)
export const examFullPassagesCache = new Map();
export const loadingExamsMap = new Map(); // examId -> Promise

/**
 * 캐시 데이터를 appState의 지문 목록(passagesData, rawPassagesData, currentExamQuestions)에 병합
 */
export function mergePassagesWithCache(freshMap) {
  if (!freshMap) return;
  const updateList = (list) => {
    if (!list) return;
    list.forEach((p) => {
      if (freshMap.has(p.id)) {
        Object.assign(p, freshMap.get(p.id));
      }
      if (p.subItems && p.subItems.length > 0) {
        p.subItems.forEach((sub) => {
          if (freshMap.has(sub.id)) Object.assign(sub, freshMap.get(sub.id));
        });
      }
    });
  };

  updateList(appState.passagesData);
  updateList(appState.rawPassagesData);
  updateList(appState.currentExamQuestions);
}

/**
 * 특정 시험지의 모든 문항 상세 데이터를 비동기 로드하고 캐시에 보관
 * @param {string} examId - 시험지 고유 ID (예: [고3-2026년-09월])
 * @param {Function} [onPassageUpdated] - 현재 보고 있는 문항이 갱신되었을 때 호출할 콜백 (p => void)
 */
export async function ensureExamPassagesLoaded(examId, onPassageUpdated = null) {
  if (!examId) return;

  // 이미 캐시되어 있는 경우: 네트워크 요청 없이 즉시 메모리 동기 병합 (0ms)
  if (examFullPassagesCache.has(examId)) {
    const cachedMap = examFullPassagesCache.get(examId);
    mergePassagesWithCache(cachedMap);

    const cur = appState.currentPassage;
    if (cur && cachedMap.has(cur.id)) {
      const merged = cachedMap.get(cur.id);
      Object.assign(cur, merged);
      if (typeof onPassageUpdated === "function") {
        onPassageUpdated(cur);
      }
    }
    return;
  }

  if (loadingExamsMap.has(examId)) return loadingExamsMap.get(examId);

  const fetchPromise = (async () => {
    try {
      const res = await fetch(`/api/exams/${encodeURIComponent(examId)}/passages`);
      if (res.ok) {
        const data = await res.json();
        const freshItems = data.items || [];
        const freshMap = new Map(freshItems.map((it) => [it.id, it]));

        // 캐시 저장
        examFullPassagesCache.set(examId, freshMap);

        // 데이터 목록에 병합
        mergePassagesWithCache(freshMap);

        // 현재 보고 있는 지문이 해당 시험에 속해있다면 화면 즉시 갱신
        const cur = appState.currentPassage;
        if (cur && freshMap.has(cur.id)) {
          const merged = freshMap.get(cur.id);
          Object.assign(cur, merged);
          if (typeof onPassageUpdated === "function") {
            onPassageUpdated(cur);
          }
        }
      }
    } catch (e) {
      console.error("Exam passages load error:", e);
    } finally {
      loadingExamsMap.delete(examId);
    }
  })();

  loadingExamsMap.set(examId, fetchPromise);
  return fetchPromise;
}

/** 지문 메모 저장 API */
export async function savePassageMemoApi(passageId, text) {
  const res = await fetch(`/api/passages/${encodeURIComponent(passageId)}/memo`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ memo: text }),
  });
  const data = await res.json();
  if (!res.ok || !data.success) {
    throw new Error(data.detail || data.message || "메모 저장 실패");
  }
  return data;
}

/** 문제 유형 변경 PATCH API */
export async function updateQuestionTypeApi(passageId, newType) {
  const res = await fetch(`/api/passages/${encodeURIComponent(passageId)}/question-type`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question_type: newType }),
  });
  const data = await res.json();
  if (!res.ok) {
    throw new Error(data.detail || data.message || "문제 유형 변경 실패");
  }
  return data;
}

/** 정답 수정 PATCH API */
export async function updateAnswerApi(passageId, newAns) {
  const res = await fetch(`/api/passages/${encodeURIComponent(passageId)}/answer`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ answer: newAns }),
  });
  const data = await res.json();
  if (!res.ok) {
    throw new Error(data.detail || data.message || "정답 정정 실패");
  }
  return data;
}

/** 지문 태그 추가 POST API */
export async function addPassageTagApi(passageId, tagName) {
  const res = await fetch(`/api/passages/${encodeURIComponent(passageId)}/tags`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ tag_name: tagName }),
  });
  const data = await res.json();
  if (!res.ok) {
    throw new Error(data.detail || data.message || "태그 추가 실패");
  }
  return data;
}

/** 지문 태그 삭제 DELETE API */
export async function deletePassageTagApi(passageId, tagName) {
  const res = await fetch(
    `/api/passages/${encodeURIComponent(passageId)}/tags/${encodeURIComponent(tagName)}`,
    { method: "DELETE" }
  );
  const data = await res.json();
  if (!res.ok) {
    throw new Error(data.detail || data.message || "태그 삭제 실패");
  }
  return data;
}

/** PDF 문항 캡처 다시 실행 POST API */
export async function recapturePassagePdfApi(passageId) {
  const res = await fetch(`/api/passages/${encodeURIComponent(passageId)}/recapture`, {
    method: "POST",
  });
  const data = await res.json();
  if (!res.ok || !data.success) {
    throw new Error(data.message || data.detail || "PDF 문항 다시 캡처 실패");
  }
  return data;
}

/** 시험지 5종 원본 파일 상태 조회 API */
export async function fetchExamRawFilesApi(examId) {
  let res = await fetch(`/api/exams/${encodeURIComponent(examId)}/raw-files`);
  if (!res.ok) {
    const altId = examId.startsWith("[") ? examId.slice(1, -1) : `[${examId}]`;
    const resAlt = await fetch(`/api/exams/${encodeURIComponent(altId)}/raw-files`);
    if (resAlt.ok) {
      return await resAlt.json();
    }
    throw new Error(`파일 정보 조회 실패 (Status: ${res.status})`);
  }
  return await res.json();
}

/** 단일 파일 다운로드 트리거 */
export function downloadExamRawFile(examId, fileType) {
  const url = `/api/exams/${encodeURIComponent(examId)}/download-file?file_type=${encodeURIComponent(fileType)}`;
  const a = document.createElement("a");
  a.href = url;
  a.download = "";
  document.body.appendChild(a);
  a.click();
  setTimeout(() => a.remove(), 1000);
}

/** 전체 파일 ZIP 일괄 다운로드 트리거 */
export function downloadExamAllZip(examId) {
  const url = `/api/exams/${encodeURIComponent(examId)}/download-zip`;
  const a = document.createElement("a");
  a.href = url;
  a.download = "";
  document.body.appendChild(a);
  a.click();
  setTimeout(() => a.remove(), 1000);
}

/** 시험지 세트 전체 듣기 MP3 ZIP 일괄 다운로드 URL 열기 */
export function downloadExamListeningZip(examId) {
  const url = `/api/exams/${encodeURIComponent(examId)}/download-listening-zip`;
  window.open(url, "_blank");
}

// ---------------------------------------------------------------------------
// 음성 합성(TTS) 작업 상태 및 API
// ---------------------------------------------------------------------------
export const TTS_POLL_MS = 600;
export let activeTtsJob = null; // { jobId, kind: "single"|"batch", examId, targetIds:Set, percent, info, timer, polling }

export function getActiveTtsJob() {
  return activeTtsJob;
}

export function setActiveTtsJob(job) {
  activeTtsJob = job;
}

/** TTS 진행률 조회 API */
export async function pollTtsProgressApi(jobId) {
  const res = await fetch(`/api/tts/progress/${encodeURIComponent(jobId)}`);
  if (!res.ok) return null;
  return await res.json();
}

/** 단일 문항 음성 생성 POST API */
export async function generateSingleAudioApi(targetId, jobId) {
  const res = await fetch(
    `/api/passages/${encodeURIComponent(targetId)}/generate-audio?job_id=${encodeURIComponent(jobId)}`,
    { method: "POST" }
  );
  const contentType = res.headers.get("content-type") || "";
  if (contentType.includes("application/json")) {
    const data = await res.json();
    if (!res.ok || !data.success) {
      throw new Error(data.detail || data.message || "음성 합성 실패");
    }
    return data;
  }
  const rawText = await res.text();
  throw new Error(rawText || `서버 오류 (${res.status})`);
}

/** 전체 듣기 문항 일괄 음성 생성 POST API */
export async function generateAllAudioApi(examId, jobId) {
  const res = await fetch(
    `/api/exams/${encodeURIComponent(examId)}/generate-listening-audio?job_id=${encodeURIComponent(jobId)}`,
    { method: "POST" }
  );
  const contentType = res.headers.get("content-type") || "";
  if (contentType.includes("application/json")) {
    const data = await res.json();
    if (!res.ok || !data.success) {
      throw new Error(data.detail || data.message || "일괄 합성 실패");
    }
    return data;
  }
  const rawText = await res.text();
  throw new Error(rawText || `서버 오류 (${res.status})`);
}

/** 인라인 TTS 엔진 전환 POST API */
export async function switchTtsEngineApi(targetEngine) {
  const res = await fetch("/api/settings/tts-engine", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ engine: targetEngine }),
  });
  if (!res.ok) {
    throw new Error(`서버 응답 오류 (${res.status})`);
  }
  return await res.json();
}

/** 단일 지문 최신 데이터 새로고침 GET API */
export async function fetchPassageByIdApi(passageId) {
  const res = await fetch(`/api/passages/${encodeURIComponent(passageId)}`);
  if (!res.ok) {
    throw new Error(`지문 정보 조회 실패 (${res.status})`);
  }
  return await res.json();
}
