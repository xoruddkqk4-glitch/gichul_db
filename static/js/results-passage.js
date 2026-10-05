/**
 * 05-gichul_db: 지문 결과 모듈 통합 퍼사드 (results-passage.js)
 *
 * 기존 3,488줄의 대형 results-passage.js 모듈을 단일 책임 원칙(SRP)에 따라
 * 3개 도메인 모듈로 성공적으로 분리 완료:
 * 1. passage-api.js    - 서버 API 통신, 캐시(examFullPassagesCache), 파일 다운로드, TTS 폴링
 * 2. passage-render.js - 문항 탭 바, 트리 네비게이터, 2x2 그리드, 복합 지문 통합, FELS 서식화, 선지별 선택률
 * 3. passage-events.js - 오디오 재생/정지, TTS 생성 제어, FELS/지문 복사, 메모 자동저장, 이벤트 리스너
 *
 * 본 파일은 기존 호출자(search.js, results-sentence.js, upload.js, navigation.js, main.js, files-status.js)
 * 와의 100% 하위 호환성을 보장하는 Facade Re-export 모듈입니다.
 */

export * from "./passage-api.js";
export * from "./passage-render.js";
export * from "./passage-events.js";

import { initPassageEvents } from "./passage-events.js";

/** 기존 main.js 의 init_results_passage() 호출 호환 */
export function init() {
  initPassageEvents();
}
