/**
 * 05-gichul_db: 여러 모듈이 공유하는 상태 (appState) (state.js)
 * - 두 개 이상의 모듈이 읽거나 대입하는 상태만 여기에 둔다 (단일 모듈 전용 상태는 해당 모듈의 let)
 * - 사용: import { appState } from "./state.js"; → appState.currentMode 처럼 접근
 */

export const appState = {
  // 상태 변수
  currentMode: "passage", // 'passage' 또는 'sentence'
  currentArea: "reading", // 'reading' 또는 'listening'
  currentPassageId: null,
  currentPassageIndex: 0,
  passagesData: [],
  sentencesData: [],
  rawPassagesData: [], // '결과 내 검색' 필터링용 원본 지문 목록 캐시
  rawSentencesData: [], // '결과 내 검색' 필터링용 원본 문장 목록 캐시
  isSearchWithinActive: false,
  // 트리 계층형 네비게이션 상태 ([학년] -> [년도] -> [월] -> [문항 1행 10개])
  treeNavState: {
    grade: null,
    year: null,
    month: null
  },
  currentExamQuestions: [], // 현재 선택된 시험의 문항 목록 (최하위 10열 그리드 렌더링용)
  isStarredFilterActive: false,
  isBatchCancelled: false,
  loadedExamsCache: [],
  manageExamsSort: { key: "year", order: "desc" },
};
