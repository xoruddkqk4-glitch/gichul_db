# Implementation Plan - 듣기 영역(1~17번) 정답 선지 번호 파스텔톤 노란색 형광펜 하이라이트 적용

## 1. 개요 및 배경
- **현상**:
  - 독해 영역(18~45번)은 PDF 원본 캡처 이미지 내 정답 선지 번호(①~⑤)에 눈이 편안한 파스텔톤 노란색(#FFE853) 형광펜 주석이 정상적으로 표시됨.
  - 반면 듣기 영역(1~17번)은 동일한 시험지 문제지 PDF에서 추출됨에도 불구하고, 정답 선지 번호에 형광펜 표시가 나타나지 않음.
- **원인 분석**:
  1. **`listening_parser.py`의 `extract_listening_question_crops` 정답 인자 누락**:
     - `extract_listening_question_crops` 함수는 내부적으로 `pdf_parser.extract_pdf_columns_and_questions`를 호출하며, `answers_dict` 매개변수를 지원하도록 설계되어 있었으나, 실제 호출부인 `sync_exam_listening`에서 `answers_dict`를 전달하지 않고 있었습니다.
     - 또한 정답 사전(`verified_key`)을 로드하는 로직이 크롭 생성 함수 호출 뒤에 위치하여, 크롭 시점에는 정답 기호(`answer_symbol`)가 항상 빈 문자열(`""`)로 전달되었습니다.
     - 이에 따라 `pdf_parser.py`의 `highlight_answer_choice`가 호출되지 못하고 원본 그대로 캡처되었습니다.
  2. **`app.py`의 `_regenerate_exam_crops` 범위 한정 (독해 영역만 실행)**:
     - 정답표 JSON/이미지 업로드, CSV 반영, 수동 정답 수정 시 실행되는 `_regenerate_exam_crops` 함수가 `start_q=reading_start, end_q=reading_end`(18~45번)로 독해 영역만 크롭을 다시 생성하도록 작성되어 있었습니다.
     - 따라서 정답이 확정되거나 갱신되어도 1~17번 듣기 문항은 크롭 재생성 대상에서 제외되어 형광펜이 적용되지 않았습니다.
  3. **`app.py`의 `/api/upload` 동기화 인자 미전달**:
     - 단일/일괄 업로드 처리 시 `listening_parser.sync_exam_listening`을 호출할 때 확정된 `answers_dict`를 넘겨주지 않고 있었습니다.

---

## 2. 변경 대상 파일 및 주요 변경점

### 1) `listening_parser.py`
- `sync_exam_listening` 함수 시그니처 개선:
  - `answers_dict: Optional[Dict[int, str]] = None`, `question_pdf_path: Optional[str] = None`, `**kwargs` 수용.
- 정답 사전 사전 구축:
  - `extract_listening_question_crops` 호출 전에 `verified_key`, `explanations` 및 인자로 전달된 `answers_dict`를 통합한 `listening_answers`를 먼저 생성.
- 크롭 함수 호출 시 `answers_dict=listening_answers` 전달:
  - `extract_listening_question_crops(..., answers_dict=listening_answers)` 호출을 통해 1~17번 선지 기호(①~⑤)에 `highlight_answer_choice`가 작동하도록 연결.

### 2) `app.py`
- `_regenerate_exam_crops` 함수 확장:
  - 독해 문항 크롭 생성(`reading_start` ~ `reading_end`)과 더불어, 듣기 문항(`start_q=1, end_q=listening_end`)도 동일한 `answers_dict`를 전달하여 형광펜 주석이 포함된 크롭 이미지를 함께 재생성하도록 개선.
- `/api/upload` 듣기 동기화 호출부:
  - `listening_parser.sync_exam_listening(..., answers_dict=answers_dict)`로 정답 데이터 전달.

---

## 3. 세부 구현 계획

### 3.1 `listening_parser.py` 변경 상세
```python
def sync_exam_listening(
    exam_id: str,
    script_pdf_path: Optional[str] = None,
    is_explanation_pdf: bool = False,
    question_pdf_path: Optional[str] = None,
    answers_dict: Optional[Dict[int, str]] = None,
    **kwargs
) -> Dict[str, Any]:
    ...
    # 1. HWP 해설 파싱 후, 정답표(answer_keys) 및 전달받은 answers_dict 사전 구축
    verified_key = answer_keys.load_answer_key(grade, year, month)
    listening_answers = {}
    for q in range(start_q, end_q + 1):
        ans_val = ""
        if answers_dict and q in answers_dict and answers_dict[q]:
            ans_val = str(answers_dict[q])
        elif q in verified_key and verified_key[q]:
            ans_val = str(verified_key[q])
        elif q in explanations and explanations[q].get("answer"):
            ans_val = str(explanations[q]["answer"])
        if ans_val:
            listening_answers[q] = ans_val

    # 2. PDF 문제지에서 듣기 문항 크롭 시 listening_answers 전달 -> 파스텔톤 노란색 형광펜 적용
    pdf_questions = {}
    target_prob_pdf = question_pdf_path if (question_pdf_path and os.path.exists(question_pdf_path)) else (pdf_files[0] if pdf_files else None)
    if target_prob_pdf:
        try:
            pdf_questions = extract_listening_question_crops(
                pdf_path=target_prob_pdf,
                grade=grade,
                year=year,
                month=month,
                listening_start_q=start_q,
                listening_end_q=end_q,
                answers_dict=listening_answers
            )
        except Exception as e:
            print(f"[Sync Listening Warning] PDF 듣기 크롭 실패: {e}")
```

### 3.2 `app.py` `_regenerate_exam_crops` 확장 상세
```python
        # 독해 문항 크롭 생성 (정답 형광펜 포함)
        crop_results = extract_pdf_columns_and_questions(
            pdf_path=target_pdf, grade=grade, year=year, month=month,
            start_q=reading_start, end_q=reading_end, answers_dict=answers_dict
        )

        # 듣기 문항(1~17번)도 정답 형광펜 포함하여 함께 재생성
        listening_end = (reading_start - 1) if (reading_start and reading_start > 1) else 17
        listening_crops = extract_pdf_columns_and_questions(
            pdf_path=target_pdf, grade=grade, year=year, month=month,
            start_q=1, end_q=listening_end, answers_dict=answers_dict
        )
        crop_results.update(listening_crops)

        with db.get_connection() as conn:
            cursor = conn.cursor()
            for q_n, q_data in crop_results.items():
                crop_url = q_data.get("pdf_crop_image", "")
                if crop_url:
                    cursor.execute(
                        "UPDATE passages SET pdf_crop_image = ? WHERE exam_id = ? AND q_num = ?",
                        (crop_url, exam_id, q_n)
                    )
            conn.commit()
```

---

## 4. 검증 계획
1. **정적 구문 검증**:
   - `python -m py_compile listening_parser.py app.py`
2. **단위 픽셀 분석 테스트**:
   - 대표 시험지(`고3-[2026-09]`, `고3-[2024-06]`)의 듣기 1번~17번 문항에 대해 정답 형광펜 재생성 실행 후, 생성된 PNG 이미지 내 파스텔톤 노란색(#FFE853, RGB: 255, 232, 83) 픽셀이 2,000개 이상 정상 검출되는지 자동 검증.
3. **UI 시각적 확인**:
   - 메인 화면에서 듣기 영역 모드로 진입 시, 좌상단 문항 캡처 패널의 정답 선지 번호 기호(①~⑤) 위에 독해 영역과 완전히 동일한 파스텔톤 노란색 형광펜이 칠해져 출력되는지 확인.

---

## 5. 실행 및 검증 완료 결과
- **코드 반영 완료**:
  1. `listening_parser.py`: `sync_exam_listening`에 `answers_dict` 사전 구축 및 `extract_listening_question_crops(..., answers_dict=listening_answers)` 연동 완료.
  2. `app.py`: `_regenerate_exam_crops`에서 독해뿐만 아니라 듣기(1~17번) 문항도 `answers_dict`를 전달하여 형광펜 주석 포함 재생성 완료. `/api/upload` 듣기 동기화 시 `answers_dict` 전달 완료.
- **정적 검증**:
  - `python -m py_compile listening_parser.py app.py` 문법 검사 통과 (Exit Code 0).
- **픽셀 분석 및 일괄 갱신 검증**:
  - 1번~17번 듣기 크롭 이미지 내 파스텔톤 노란색(#FFE853) 형광펜 픽셀 검출 확인 (예: 6번 문항 2,150개 픽셀 검출 완료).
  - 기존 등록 시험지 11종의 187개 듣기 문항 크롭 이미지에 대해 정답 형광펜 일괄 재생성 완료.
