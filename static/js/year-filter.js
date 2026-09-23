/**
 * 05-gichul_db: 연도 5대 그룹 및 2006~2026 복수 선택 필터 모듈 (year-filter.js)
 *
 * 5개 교육과정 / 수능 체제 그룹:
 * 1) 2024~2026년 : 통합형 영어 · 절대평가 · 킬러 문항 배제 방침 적용 [2026, 2025, 2024]
 * 2) 2018~2023년 : 통합형 영어 · 절대평가 [2023, 2022, 2021, 2020, 2019, 2018]
 * 3) 2015~2017년 : 통합형 영어 · 상대평가 [2017, 2016, 2015]
 * 4) 2014년 : A·B형 수준별 영어 · 상대평가 [2014]
 * 5) 2006~2013년 : 외국어(영어) 영역 · 상대평가 [2013, 2012, 2011, 2010, 2009, 2008, 2007, 2006]
 */

export const YEAR_GROUPS = [
  {
    id: "g5",
    label: "2024~2026년",
    badge: "킬러문항 배제",
    desc: "통합형 영어 · 절대평가 · 킬러 문항 배제 방침 적용",
    years: [2026, 2025, 2024]
  },
  {
    id: "g4",
    label: "2018~2023년",
    badge: "절대평가",
    desc: "통합형 영어 · 절대평가",
    years: [2023, 2022, 2021, 2020, 2019, 2018]
  },
  {
    id: "g3",
    label: "2015~2017년",
    badge: "상대평가",
    desc: "통합형 영어 · 상대평가",
    years: [2017, 2016, 2015]
  },
  {
    id: "g2",
    label: "2014년",
    badge: "A·B형 수준별",
    desc: "A·B형 수준별 영어 · 상대평가",
    years: [2014]
  },
  {
    id: "g1",
    label: "2006~2013년",
    badge: "외국어 영역",
    desc: "외국어(영어) 영역 · 상대평가",
    years: [2013, 2012, 2011, 2010, 2009, 2008, 2007, 2006]
  }
];

export const ALL_YEARS = [
  2026, 2025, 2024, 2023, 2022, 2021, 2020, 2019, 2018, 2017,
  2016, 2015, 2014, 2013, 2012, 2011, 2010, 2009, 2008, 2007, 2006
];

// 현재 선택된 연도 Set (비어있으면 전체 연도 검색)
let selectedYears = new Set();
let onYearChangeCallback = null;

/** 선택된 연도 배열 (내림차순 정렬) */
export function getSelectedYears() {
  return Array.from(selectedYears).sort((a, b) => b - a);
}

/** 검색 쿼리 파라미터용 연도 문자열 반환 (콤마 구분, 전체 선택 또는 미선택 시 빈 문자열) */
export function getYearsQueryParam() {
  if (selectedYears.size === 0 || selectedYears.size === ALL_YEARS.length) {
    return "";
  }
  return getSelectedYears().join(",");
}

/** 전체 연도인지 여부 */
export function isAllYearsSelected() {
  return selectedYears.size === 0 || selectedYears.size === ALL_YEARS.length;
}

/** 트리거 버튼 표시용 요약 텍스트 계산 */
export function getYearTriggerLabel() {
  if (selectedYears.size === 0 || selectedYears.size === ALL_YEARS.length) {
    return "전체 연도";
  }

  // 정확히 하나의 그룹 전체와 일치하는 경우
  for (const g of YEAR_GROUPS) {
    const allInGroup = g.years.every(y => selectedYears.has(y));
    if (allInGroup && selectedYears.size === g.years.length) {
      return `${g.label} (${g.years.length}개년)`;
    }
  }

  // 그룹 1개 전체 + 추가 개별 연도 조합
  const fullGroups = YEAR_GROUPS.filter(g => g.years.every(y => selectedYears.has(y)));
  if (fullGroups.length === 1) {
    const g = fullGroups[0];
    const extra = selectedYears.size - g.years.length;
    if (extra > 0) {
      return `${g.label} 외 ${extra}개 (${selectedYears.size}개년)`;
    }
  }

  // 복수 그룹 전체 선택
  if (fullGroups.length > 1) {
    const fullGroupYearsCount = fullGroups.reduce((acc, g) => acc + g.years.length, 0);
    const gNames = fullGroups.map(g => g.label.replace("년", "")).join(", ");
    const remaining = selectedYears.size - fullGroupYearsCount;
    if (remaining === 0) {
      return `${gNames} (${selectedYears.size}개년)`;
    }
    return `${gNames} 외 ${remaining}개 (${selectedYears.size}개년)`;
  }

  // 단일 연도 선택
  if (selectedYears.size === 1) {
    return `${Array.from(selectedYears)[0]}년`;
  }

  // 기타 복수 선택
  const sorted = getSelectedYears();
  return `${sorted[0]}년 외 ${selectedYears.size - 1}개 (${selectedYears.size}개년)`;
}

/** 팝오버 내부 HTML 렌더링 */
function renderPopoverContent(prefix) {
  let html = `
    <div class="year-popover-header">
      <div class="popover-title-row">
        <span class="popover-title">📅 연도 선택 (복수 선택 가능)</span>
        <span class="popover-count-badge" id="${prefix}SelectedCountBadge">전체 (21개년)</span>
      </div>
      <div class="popover-quick-actions">
        <button type="button" class="btn-popover-action" data-action="all">전체 선택</button>
        <button type="button" class="btn-popover-action" data-action="clear">선택 초기화</button>
      </div>
    </div>

    <div class="year-popover-body">
      <!-- 5개 교육과정 / 수능 체제 그룹 -->
      <div class="year-group-section">
        <div class="year-section-title">5대 교육과정 체제별 그룹 (일괄 선택)</div>
        <div class="year-groups-list">
  `;

  YEAR_GROUPS.forEach(g => {
    html += `
      <label class="year-group-item" data-group-id="${g.id}">
        <div class="year-group-left">
          <input type="checkbox" class="year-group-checkbox" data-prefix="${prefix}" data-group-id="${g.id}">
          <div class="year-group-text">
            <div class="year-group-name">
              <strong>${g.label}</strong>
              <span class="year-era-badge">${g.badge}</span>
            </div>
            <div class="year-group-desc">${g.desc}</div>
          </div>
        </div>
        <span class="year-group-years-badge">${g.years.length}개년</span>
      </label>
    `;
  });

  html += `
        </div>
      </div>

      <!-- 개별 연도 선택 (2006 ~ 2026) -->
      <div class="year-individual-section">
        <div class="year-section-title">개별 연도 선택 (그룹과 조합 가능)</div>
        <div class="year-chips-by-era">
  `;

  YEAR_GROUPS.forEach(g => {
    html += `
      <div class="era-year-chips-group">
        <div class="era-mini-label">${g.label}</div>
        <div class="year-chips-grid">
    `;
    g.years.forEach(y => {
      html += `
        <label class="year-chip-item">
          <input type="checkbox" class="year-single-checkbox" data-prefix="${prefix}" data-year="${y}">
          <span class="year-chip-text">${y}년</span>
        </label>
      `;
    });
    html += `
        </div>
      </div>
    `;
  });

  html += `
        </div>
      </div>
    </div>

    <div class="year-popover-footer">
      <span class="year-footer-hint" id="${prefix}FooterHint">체크 시 즉시 검색 조건에 반영됩니다.</span>
      <button type="button" class="btn btn-primary btn-sm btn-popover-apply" data-prefix="${prefix}">적용 및 닫기</button>
    </div>
  `;

  return html;
}

/** 모든 팝오버의 UI 상태(체크박스, 인디터미네이트, 요약 라벨 등) 동기화 */
export function updateAllYearUI() {
  const labelText = getYearTriggerLabel();
  const yearsParam = getYearsQueryParam();

  // 트리거 버튼 라벨 갱신
  ["labelYearHome", "labelYearResults"].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.textContent = labelText;
  });

  // 숨겨진 입력값 갱신
  ["filterYear", "resultsFilterYear"].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.value = yearsParam;
  });

  // 카운트 배지 갱신
  const countText = selectedYears.size === 0 || selectedYears.size === ALL_YEARS.length
    ? "전체 (21개년)"
    : `${selectedYears.size}개년 선택`;
  ["homeSelectedCountBadge", "resultsSelectedCountBadge"].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.textContent = countText;
  });

  // 1) 개별 연도 체크박스 상태 갱신
  document.querySelectorAll(".year-single-checkbox").forEach(cb => {
    const y = parseInt(cb.dataset.year, 10);
    cb.checked = selectedYears.has(y);
    const chipLabel = cb.closest(".year-chip-item");
    if (chipLabel) {
      chipLabel.classList.toggle("selected", cb.checked);
    }
  });

  // 2) 그룹 체크박스 상태 (checked / indeterminate) 갱신
  YEAR_GROUPS.forEach(g => {
    const total = g.years.length;
    const selectedCount = g.years.filter(y => selectedYears.has(y)).length;

    document.querySelectorAll(`.year-group-checkbox[data-group-id="${g.id}"]`).forEach(gCb => {
      if (selectedCount === total) {
        gCb.checked = true;
        gCb.indeterminate = false;
      } else if (selectedCount > 0) {
        gCb.checked = false;
        gCb.indeterminate = true;
      } else {
        gCb.checked = false;
        gCb.indeterminate = false;
      }
      const groupItem = gCb.closest(".year-group-item");
      if (groupItem) {
        groupItem.classList.toggle("active-group", selectedCount === total);
        groupItem.classList.toggle("partial-group", selectedCount > 0 && selectedCount < total);
      }
    });
  });
}

/** 팝오버 닫기 */
export function closeAllYearPopovers() {
  document.querySelectorAll(".year-popover-menu").forEach(menu => {
    menu.style.display = "none";
    menu.style.left = "0";
    menu.style.right = "auto";
  });
  document.querySelectorAll(".year-multiselect-trigger").forEach(btn => {
    btn.setAttribute("aria-expanded", "false");
  });
}

/** 팝오버 열기/토글 */
function toggleYearPopover(menuId, triggerBtn) {
  const menu = document.getElementById(menuId);
  if (!menu) return;
  const isCurrentlyOpen = menu.style.display === "block";

  closeAllYearPopovers();

  if (!isCurrentlyOpen) {
    menu.style.display = "block";
    menu.style.left = "0";
    menu.style.right = "auto";
    triggerBtn.setAttribute("aria-expanded", "true");

    // 화면 밖으로 잘리지 않도록 뷰포트 경계 자동 안전 보정
    requestAnimationFrame(() => {
      const rect = menu.getBoundingClientRect();
      const viewportWidth = window.innerWidth;
      if (rect.left < 16) {
        menu.style.left = `${16 - rect.left}px`;
        menu.style.right = "auto";
      } else if (rect.right > viewportWidth - 16) {
        const overflow = rect.right - (viewportWidth - 16);
        if (rect.left - overflow < 16) {
          menu.style.left = `${16 - rect.left}px`;
        } else {
          menu.style.left = `-${overflow}px`;
        }
        menu.style.right = "auto";
      }
    });
  }
}

/** 연도 필터 초기화 (전체 연도 상태로) */
export function resetYearFilter() {
  selectedYears.clear();
  updateAllYearUI();
}

/** 특정 연도 목록으로 강제 설정 */
export function setYearSelection(yearsList) {
  selectedYears.clear();
  if (Array.isArray(yearsList)) {
    yearsList.forEach(y => {
      const num = parseInt(y, 10);
      if (ALL_YEARS.includes(num)) {
        selectedYears.add(num);
      }
    });
  }
  updateAllYearUI();
}

/** 연도 복수 선택 모듈 초기화 */
export function initYearFilter(onChangeCallback) {
  onYearChangeCallback = onChangeCallback;

  // 1. 홈 팝오버 내용 주입
  const menuHome = document.getElementById("menuYearHome");
  if (menuHome) {
    menuHome.innerHTML = renderPopoverContent("home");
  }

  // 2. 결과창 팝오버 내용 주입
  const menuResults = document.getElementById("menuYearResults");
  if (menuResults) {
    menuResults.innerHTML = renderPopoverContent("results");
  }

  // 3. 트리거 버튼 이벤트 바인딩
  const btnHome = document.getElementById("btnYearMultiSelectHome");
  if (btnHome) {
    btnHome.addEventListener("click", (e) => {
      e.stopPropagation();
      toggleYearPopover("menuYearHome", btnHome);
    });
  }

  const btnResults = document.getElementById("btnYearMultiSelectResults");
  if (btnResults) {
    btnResults.addEventListener("click", (e) => {
      e.stopPropagation();
      toggleYearPopover("menuYearResults", btnResults);
    });
  }

  // 4. 외부 클릭 시 팝오버 닫기
  document.addEventListener("click", (e) => {
    if (!e.target.closest(".year-multiselect-dropdown")) {
      closeAllYearPopovers();
    }
  });

  // 5. 팝오버 내부 클릭 시 이벤트 버블링 차단 (팝오버 닫힘 방지)
  [menuHome, menuResults].forEach(menu => {
    if (menu) {
      menu.addEventListener("click", (e) => {
        e.stopPropagation();
      });
    }
  });

  // 6. 개별 연도 체크박스 변경 핸들러
  document.addEventListener("change", (e) => {
    if (e.target.classList.contains("year-single-checkbox")) {
      const year = parseInt(e.target.dataset.year, 10);
      if (e.target.checked) {
        selectedYears.add(year);
      } else {
        selectedYears.delete(year);
      }
      updateAllYearUI();
      if (typeof onYearChangeCallback === "function") {
        onYearChangeCallback(e.target.dataset.prefix);
      }
    }
  });

  // 7. 그룹 체크박스 변경 핸들러 (그룹 소속 연도 일괄 선택/해제)
  document.addEventListener("change", (e) => {
    if (e.target.classList.contains("year-group-checkbox")) {
      const groupId = e.target.dataset.groupId;
      const group = YEAR_GROUPS.find(g => g.id === groupId);
      if (!group) return;

      const isChecked = e.target.checked;
      group.years.forEach(y => {
        if (isChecked) {
          selectedYears.add(y);
        } else {
          selectedYears.delete(y);
        }
      });

      updateAllYearUI();
      if (typeof onYearChangeCallback === "function") {
        onYearChangeCallback(e.target.dataset.prefix);
      }
    }
  });

  // 8. 팝오버 상단 액션 버튼 (전체 선택 / 선택 초기화)
  document.addEventListener("click", (e) => {
    const actionBtn = e.target.closest(".btn-popover-action");
    if (!actionBtn) return;
    const action = actionBtn.dataset.action;
    if (action === "all") {
      ALL_YEARS.forEach(y => selectedYears.add(y));
    } else if (action === "clear") {
      selectedYears.clear();
    }
    updateAllYearUI();
    if (typeof onYearChangeCallback === "function") {
      onYearChangeCallback("action");
    }
  });

  // 9. 팝오버 하단 적용 및 닫기 버튼
  document.addEventListener("click", (e) => {
    const applyBtn = e.target.closest(".btn-popover-apply");
    if (applyBtn) {
      closeAllYearPopovers();
    }
  });

  // 초기 상태 UI 동기화
  updateAllYearUI();
}
