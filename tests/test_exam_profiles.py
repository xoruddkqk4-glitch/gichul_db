"""
tests/test_exam_profiles.py: gichul.exam_profiles 단위 테스트
- 2008, 2012-06, 2013, 2013-09, 2020 프로파일 기대값 검증
- dataclass 불변성 검증
- run_special_crop 디스패치 검증
"""

import pytest
from dataclasses import FrozenInstanceError
from gichul.exam_profiles import ExamProfile, get_exam_profile, run_special_crop


def test_profile_2008_50_questions():
    """2008년: 구 50문항 체제 (듣기 1~17, 독해 18~50)"""
    p = get_exam_profile(grade="고3", year=2008, month=6)
    assert p.is_50_questions is True
    assert p.is_ab_period is False
    assert p.reading_start == 18
    assert p.reading_end == 50
    assert p.listening_end == 17
    assert p.special_crop is None


def test_profile_2012_06_ab_period():
    """2012년 6월: 수준별 A/B형 체제 시작 (듣기 1~22, 독해 23~45)"""
    p = get_exam_profile(grade="고3", year=2012, month=6)
    assert p.is_50_questions is False
    assert p.is_ab_period is True
    assert p.reading_start == 23
    assert p.reading_end == 45
    assert p.listening_end == 22
    assert p.special_crop is None


def test_profile_2012_early_month_no_sub():
    """2012년 3월 (subtype 없음): 기존 체제 (독해 18~45)"""
    p = get_exam_profile(grade="고3", year=2012, month=3)
    assert p.is_ab_period is False
    assert p.reading_start == 18
    assert p.listening_end == 17


def test_profile_2012_early_month_with_sub():
    """2012년 3월 (subtype 'A형' 명시): A/B형 처리 (독해 23~45)"""
    p = get_exam_profile(grade="고3", year=2012, month=3, subtype="A형")
    assert p.is_ab_period is True
    assert p.reading_start == 23
    assert p.listening_end == 22


def test_profile_2013_full_ab_year():
    """2013년 전체: 수준별 체제 (듣기 1~22, 독해 23~45)"""
    p = get_exam_profile(grade="고3", year=2013, month=6)
    assert p.is_50_questions is False
    assert p.is_ab_period is True
    assert p.reading_start == 23
    assert p.reading_end == 45
    assert p.listening_end == 22
    assert p.special_crop is None


def test_profile_2013_09_special_crop():
    """2013년 9월 고3: 벡터 폰트 외곽선 특수 크롭 모듈 지정"""
    p = get_exam_profile(grade="고3", year=2013, month=9)
    assert p.is_50_questions is False
    assert p.is_ab_period is True
    assert p.reading_start == 23
    assert p.reading_end == 45
    assert p.listening_end == 22
    assert p.special_crop == "crop_2013_09"

    # 고1/고2는 2013년 9월이어도 특수 크롭 아님
    p_g2 = get_exam_profile(grade="고2", year=2013, month=9)
    assert p_g2.special_crop is None


def test_profile_2020_standard():
    """2020년: 현행 표준 45문항 체제 (듣기 1~17, 독해 18~45)"""
    p = get_exam_profile(grade="고3", year=2020, month=11)
    assert p.is_50_questions is False
    assert p.is_ab_period is False
    assert p.reading_start == 18
    assert p.reading_end == 45
    assert p.listening_end == 17
    assert p.special_crop is None


def test_profile_immutability():
    """ExamProfile은 frozen dataclass이므로 속성 변경 시 예외 발생"""
    p = get_exam_profile(grade="고3", year=2024, month=6)
    with pytest.raises(FrozenInstanceError):
        p.reading_start = 99


def test_run_special_crop_unknown():
    """알 수 없는 특수 크롭 식별자는 False 반환"""
    assert run_special_crop("unknown_crop", "test_id") is False
    assert run_special_crop("", "test_id") is False
