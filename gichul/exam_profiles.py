"""
05-gichul_db: 시험 체제별 프로파일 데이터 관리 모듈 (exam_profiles.py)

수능 및 교육청/평가원 모의고사 시기별 체제 규칙:
- 2006~2011년: 구 50문항 체제 (듣기 1~17번, 독해 18~50번)
- 2012년 6월~2013년: 수준별(A/B형) 체제 (듣기 1~22번, 독해 23~45번)
- 2014년 이후~현재: 현행 45문항 통합 체제 (듣기 1~17번, 독해 18~45번)
- 고3 2013년 9월: 벡터 곡선(Drawings) 전용 기하 레이아웃 크롭 ("crop_2013_09")
"""

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class ExamProfile:
    """시험 체제별 기본 문항 번호 범위 및 메타데이터 프로파일 (불변 객체)"""
    reading_start: int        # 독해 시작 문항 번호 (기본 18 또는 23)
    reading_end: int          # 독해 종료 문항 번호 (기본 45 또는 50)
    listening_end: int        # 듣기 종료 문항 번호 (기본 17 또는 22)
    is_50_questions: bool     # 50문항 체제 여부 (2006~2011)
    is_ab_period: bool        # A/B형 수준별 체제 여부 (2012-06~2013 또는 subtype 명시)
    special_crop: Optional[str] = None  # 특수 크롭 모듈 식별자 (예: "crop_2013_09")


def get_exam_profile(
    grade: Optional[str] = None,
    year: Optional[int] = None,
    month: Optional[int] = None,
    subtype: Optional[str] = None,
) -> ExamProfile:
    """
    시험지의 학년, 연도, 시행월, 유형(A/B형)으로부터 표준 시험 프로파일을 반환합니다.
    - 텍스트 기반 감지(`detect_listening_range`) 이전에 기본값을 제공하거나,
      PDF/HWP 텍스트 파싱 없이 기본 문항 범위를 결정할 때 사용됩니다.
    """
    try:
        year_int = int(year) if year is not None else None
    except (ValueError, TypeError):
        year_int = None

    try:
        month_int = int(month) if month is not None else None
    except (ValueError, TypeError):
        month_int = None

    grade_str = str(grade).strip() if grade is not None else ""
    sub_str = str(subtype).strip() if subtype is not None else ""

    # 1. 50문항 체제 판별 (2006 ~ 2011)
    is_50 = bool(year_int and 2006 <= year_int <= 2011)

    # 2. A/B형 수준별 체제 판별 (2012년 6월 이후 ~ 2013년, 또는 subtype에 A/B/형 명시)
    has_sub = bool(sub_str and any(k in sub_str for k in ("A", "B", "형")))
    is_ab = bool(
        (year_int == 2013)
        or (year_int == 2012 and month_int is not None and month_int >= 6)
        or has_sub
    )

    # 3. 기본 문항 번호 범위 결정
    reading_start = 23 if is_ab else 18
    listening_end = 22 if is_ab else 17
    reading_end = 50 if is_50 else 45

    # 4. 특수 크롭 대상 여부 (고3 2013년 9월 등 벡터 외곽선 변환 문서)
    is_g3 = grade_str in ("고3", "3학년", "3")
    special_crop: Optional[str] = None
    if is_g3 and year_int == 2013 and month_int == 9:
        special_crop = "crop_2013_09"

    return ExamProfile(
        reading_start=reading_start,
        reading_end=reading_end,
        listening_end=listening_end,
        is_50_questions=is_50,
        is_ab_period=is_ab,
        special_crop=special_crop,
    )


def run_special_crop(crop_name: str, exam_id: str, subtype: Optional[str] = None) -> bool:
    """특수 크롭 식별자에 해당하는 전용 크롭 함수를 동적으로 실행합니다."""
    if crop_name == "crop_2013_09":
        from .special_crops.crop_2013_09 import generate_crops_for_exam
        sub = subtype or ("A형" if "-A" in exam_id else "B형")
        return generate_crops_for_exam(exam_id, sub)
    return False
