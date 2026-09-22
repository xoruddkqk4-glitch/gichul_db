/**
 * 05-gichul_db: 메인 프론트엔드 자바스크립트 로직 (main.js)
 * - 통계 배지 클릭 시 전체 지문 결과 표시
 * - 동일 위치(헤더 슬롯) '전체 문장' <-> '지문 결과창으로 돌아가기' 양방향 전환
 * - 검색창 화면과 결과창 화면의 완전한 분리 및 전환
 * - 상단 가로 문항별 탭 바(복수 결과 탭 전환) 및 전체 너비 2x2 그리드
 * - 1행 테이블 문장 뷰어 및 클립보드 원클릭 복사
 * - PDF+HWP 업로드 및 상호 검증 파이프라인
 *
 * ES 모듈 진입점: 기능별 모듈(navigation, search, results-passage, results-sentence, utils, upload,
 * files-status, grammar, ai-settings)과 공용 dom.js(요소 참조), state.js(공유 상태)를 import 하고
 * 각 모듈의 init() 을 원본 순서대로 호출한다.
 * <script type="module"> 로 로드되므로 DOMContentLoaded 래퍼 없이도 실행 시점에 DOM 이 준비되어 있다.
 */

import { init as init_navigation } from "./navigation.js";
import { init as init_search } from "./search.js";
import { init as init_results_passage } from "./results-passage.js";
import { init as init_results_sentence } from "./results-sentence.js";
import { init as init_upload } from "./upload.js";
import { init as init_files_status } from "./files-status.js";
import { init as init_grammar } from "./grammar.js";
import { init as init_ai_settings } from "./ai-settings.js";
import { setHeaderSlotState, updateGrammarFiltersVisibility } from "./navigation.js";
import { refreshAiStatusIndicator } from "./ai-settings.js";

// 모듈별 이벤트 바인딩 (원본 main.js 의 선언 순서와 동일)
init_navigation();
init_search();
init_results_passage();
init_results_sentence();
init_upload();
init_files_status();
init_grammar();
init_ai_settings();

// 초기 상태: 홈 검색 화면이 기본이므로 헤더 슬롯을 'home' 상태(통계 배지 노출, 해당 지문 버튼 숨김)로 명시 초기화
setHeaderSlotState("home");
updateGrammarFiltersVisibility();
refreshAiStatusIndicator();
