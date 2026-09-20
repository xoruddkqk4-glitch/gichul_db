"""
05-gichul_db: HWP vs PDF 상호 교차 검증 및 데이터 무결성 검사 모듈 (validator.py)
- difflib 기반 유사도(일치율: 0.0 ~ 1.0) 계산
- 공백/줄바꿈/특수기호 정규화 후 비교
- 상호 검증 결과 및 문장 토큰화 종합 파이프라인 제공
"""

import re
import difflib
from typing import Dict, List, Tuple
from sentence_tokenizer import create_sentence_records


def normalize_for_comparison(text: str) -> str:
    """비교를 위한 텍스트 정규화 (공백, 줄바꿈, 특수 하이픈 통일)"""
    if not text:
        return ""
    # 유니코드 하이픈/대시 통일
    t = re.sub(r"[\u2010-\u2015]", "-", text)
    # 인용부호 통일
    t = re.sub(r"[\u2018\u2019]", "'", t)
    t = re.sub(r"[\u201C\u201D]", '"', t)
    # 연속 공백 및 줄바꿈을 공백 하나로 치환
    t = re.sub(r"\s+", " ", t)
    return t.strip()


def calculate_similarity(text1: str, text2: str) -> float:
    """두 텍스트 간의 문자열 유사도(0.0 ~ 1.0) 계산"""
    n1 = normalize_for_comparison(text1)
    n2 = normalize_for_comparison(text2)
    if not n1 and not n2:
        return 1.0
    if not n1 or not n2:
        return 0.0
    matcher = difflib.SequenceMatcher(None, n1, n2)
    return round(matcher.ratio(), 4)


def cross_validate_and_merge(
    hwp_data: Dict[int, Dict],
    pdf_data: Dict[int, Dict],
    explanations: Dict[int, Dict[str, str]],
    grade: str,
    year: int,
    month: int
) -> List[Dict]:
    """
    HWP 데이터와 PDF 데이터를 문항별로 교차 검증하고,
    정답/해설 및 문장 분할 레코드를 결합하여 최종 DB 저장 패키지 생성
    """
    all_q_nums = sorted(list(set(list(hwp_data.keys()) + list(pdf_data.keys()))))
    merged_results = []

    for q_num in all_q_nums:
        hwp_item = hwp_data.get(q_num, {})
        pdf_item = pdf_data.get(q_num, {})
        exp_item = explanations.get(q_num, {})
        passage_id = f"[{grade}-{year}년-{month:02d}월-{q_num:02d}번]"

        # 문제 발문
        question_title = (
            hwp_item.get("question_title") or
            pdf_item.get("question_title") or
            f"{q_num}. 문항"
        )

        hwp_body = hwp_item.get("passage_body", "")
        pdf_body = pdf_item.get("passage_body", "")
        hwp_text = hwp_item.get("passage_text", "")
        pdf_text = pdf_item.get("passage_text", "") or pdf_body

        # 상호 유사도 계산 (순수 본문 기준)
        ratio = calculate_similarity(hwp_body, pdf_body) if hwp_body and pdf_body else 1.0

        # 지문 본문 결정 (HWP 서식/단락 우선, 없으면 PDF)
        chosen_text = hwp_text if hwp_text else pdf_text

        # TXT 지문 본문 텍스트: 문항 번호와 발문 포함 보장
        if question_title and not chosen_text.startswith(question_title):
            final_passage_text = f"{question_title}\n\n{chosen_text}"
        else:
            final_passage_text = chosen_text

        # PDF 크롭 이미지
        crop_img = pdf_item.get("pdf_crop_image", "")

        # 정답 및 해설
        ans_text = exp_item.get("answer", "")
        exp_text = exp_item.get("explanation", "")

        # 문장 단위 분할 (선지, 발문, 각주 배제된 순수 영어 문장만 생성)
        sentence_records = create_sentence_records(passage_id, final_passage_text)

        # 밑줄/빈칸에 정답 선지 자동 채움 및 선지 기호 정제 적용 (온전한 문장 완성)
        try:
            from grammar_analyzer import prepare_sentence_for_analysis
            for sr in sentence_records:
                completed = prepare_sentence_for_analysis(
                    sr["sentence_text"],
                    passage_id=passage_id,
                    passage_text=final_passage_text,
                    answer_text=ans_text,
                    explanation_text=exp_text
                )
                if completed and completed != sr["sentence_text"]:
                    sr["sentence_text"] = completed
                    words = re.findall(r"\b[\w'-]+\b", completed)
                    sr["word_count"] = len(words)
        except Exception as e:
            print(f"[Sentence Prep Error in validator] {passage_id}: {e}")

        merged_results.append({
            "passage_data": {
                "id": passage_id,
                "exam_id": f"[{grade}-{year}년-{month:02d}월]",
                "q_num": q_num,
                "question_title": question_title,
                "question_type": hwp_item.get("question_type", ""),
                "passage_text": final_passage_text,
                "answer_text": ans_text,
                "explanation_text": exp_text,
                "pdf_crop_image": crop_img,
                "validation_ratio": ratio,
                "remarks": f"일치율: {ratio*100:.1f}%"
            },
            "sentences": sentence_records
        })

    return merged_results
