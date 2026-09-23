/**
 * 05-gichul_db: 학년별 월 필터 동적 옵션 제어 모듈 (month-filter.js)
 *
 * 1, 2학년은 평가원(6, 9월) 및 수능(11월) 출제 없이 전 문항 교육청 모의고사임.
 * 3학년은 교육청(3, 4, 5, 7, 10월), 평가원 모평(6, 9월), 수능(11월)으로 명확히 구분됨.
 */

import { filterGrade, filterMonth, resultsFilterGrade, resultsFilterMonth } from "./dom.js";

export const GRADE_MONTHS = {
  "고1": [
    { value: "", label: "전체 월" },
    { value: "3", label: "3월 (교육청)" },
    { value: "6", label: "6월 (교육청)" },
    { value: "8", label: "8월 (교육청)" },
    { value: "9", label: "9월 (교육청)" },
    { value: "10", label: "10월 (교육청)" },
    { value: "11", label: "11월 (교육청)" },
    { value: "12", label: "12월 (교육청)" }
  ],
  "고2": [
    { value: "", label: "전체 월" },
    { value: "3", label: "3월 (교육청)" },
    { value: "6", label: "6월 (교육청)" },
    { value: "8", label: "8월 (교육청)" },
    { value: "9", label: "9월 (교육청)" },
    { value: "10", label: "10월 (교육청)" },
    { value: "11", label: "11월 (교육청)" },
    { value: "12", label: "12월 (교육청)" }
  ],
  "고3": [
    { value: "", label: "전체 월" },
    { value: "3", label: "3월 (교육청)" },
    { value: "4", label: "4월 (교육청)" },
    { value: "5", label: "5월 (교육청)" },
    { value: "6", label: "6월 (평가원)" },
    { value: "7", label: "7월 (교육청)" },
    { value: "9", label: "9월 (평가원)" },
    { value: "10", label: "10월 (교육청)" },
    { value: "11", label: "11월 (수능)" }
  ],
  "default": [
    { value: "", label: "전체 월" },
    { value: "3", label: "3월 (교육청)" },
    { value: "4", label: "4월 (고3 교육청)" },
    { value: "5", label: "5월 (고3 교육청)" },
    { value: "6", label: "6월 (평가원/교육청)" },
    { value: "7", label: "7월 (고3 교육청)" },
    { value: "8", label: "8월 (교육청)" },
    { value: "9", label: "9월 (평가원/교육청)" },
    { value: "10", label: "10월 (교육청)" },
    { value: "11", label: "11월 (수능/교육청)" },
    { value: "12", label: "12월 (교육청)" }
  ]
};

export function updateMonthOptionsByGrade(grade, preserveValue = true) {
  const options = GRADE_MONTHS[grade] || GRADE_MONTHS["default"];
  [filterMonth, resultsFilterMonth].forEach(selectEl => {
    if (!selectEl) return;
    const currentVal = selectEl.value;
    selectEl.innerHTML = "";
    options.forEach(opt => {
      const optEl = document.createElement("option");
      optEl.value = opt.value;
      optEl.textContent = opt.label;
      selectEl.appendChild(optEl);
    });
    if (preserveValue && currentVal && options.some(o => o.value === currentVal)) {
      selectEl.value = currentVal;
    } else {
      selectEl.value = "";
    }
  });
}

export function initMonthFilter() {
  if (filterGrade) {
    filterGrade.addEventListener("change", (e) => {
      updateMonthOptionsByGrade(e.target.value);
    });
  }
  if (resultsFilterGrade) {
    resultsFilterGrade.addEventListener("change", (e) => {
      updateMonthOptionsByGrade(e.target.value);
    });
  }
}
