"""
05-gichul_db: 지문/문장 메타, 문제유형, 메모, 정답 정정, 크롭 재캡처, 태그 라우터 (gichul/routers/passages.py)
"""

import os
import time
from typing import Optional
from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel

from .. import database as db
from .. import paths
from .. import answer_resolver
from .. import answer_keys
from ..text_utils import normalize_bracket_id
from ..core.state import _ingest_serialized
from ..services.ingest import regenerate_exam_crops

router = APIRouter()


class TagRequest(BaseModel):
    tag_name: str


class QuestionTypeRequest(BaseModel):
    question_type: str


class PassageMemoRequest(BaseModel):
    memo: str


class AnswerRequest(BaseModel):
    answer: str
    note: Optional[str] = ""


class SentenceTextUpdateRequest(BaseModel):
    sentence_text: str


@router.patch("/api/passages/{passage_id}/question-type")
def api_update_question_type(passage_id: str, req: QuestionTypeRequest):
    """지문의 문제 유형 변경/저장"""
    clean_id = normalize_bracket_id(passage_id)
    success = db.update_passage_question_type(clean_id, req.question_type)
    return {"success": success, "question_type": req.question_type}


@router.put("/api/passages/{passage_id}/memo")
@router.patch("/api/passages/{passage_id}/memo")
def api_update_passage_memo(passage_id: str, req: PassageMemoRequest):
    """지문의 사용자 메모(수업/변형 노트) 저장"""
    clean_id = normalize_bracket_id(passage_id)
    res = db.update_passage_memo(clean_id, req.memo)
    if not res.get("success"):
        raise HTTPException(status_code=404, detail=f"지문 '{clean_id}'를 찾을 수 없거나 갱신하지 못했습니다.")
    return res


@router.patch("/api/passages/{passage_id}/answer")
@_ingest_serialized
def api_update_answer(passage_id: str, req: AnswerRequest):
    """교사가 확인한 정답으로 정정: DB 정답/해설 헤더/검증 상태 갱신 + 키 파일 기록 + 형광펜 크롭 재생성"""
    clean_id = normalize_bracket_id(passage_id)
    new_ans = answer_resolver.normalize_answer(req.answer)
    if not new_ans:
        raise HTTPException(status_code=400, detail="정답은 ①~⑤ 또는 1~5 로 입력해야 합니다.")

    passage = db.get_passage(clean_id)
    if not passage:
        raise HTTPException(status_code=404, detail=f"지문 '{clean_id}'를 찾을 수 없습니다.")
    exam_id = passage["exam_id"]
    q_num = int(passage["q_num"])
    old_ans = passage.get("answer_text") or ""

    with db.get_connection() as conn:
        exam = conn.execute(
            "SELECT grade, year, month, reading_start_q, reading_end_q FROM exams WHERE id = ?", (exam_id,)
        ).fetchone()
        exam_answers = {int(r["q_num"]): (r["answer_text"] or "") for r in conn.execute(
            "SELECT q_num, answer_text FROM passages WHERE exam_id = ?", (exam_id,))}
    if not exam:
        raise HTTPException(status_code=404, detail=f"시험지 '{exam_id}'를 찾을 수 없습니다.")

    db.update_passage_answers(exam_id, {q_num: new_ans}, source="manual", verified=1)
    answer_keys.record_manual_answer(exam["grade"], exam["year"], exam["month"], q_num, new_ans, old_ans, req.note or "")

    exam_answers[q_num] = new_ans
    pdf_highlighted = False
    if old_ans != new_ans:
        pdf_highlighted = regenerate_exam_crops(
            exam_id, exam["grade"], exam["year"], exam["month"],
            exam["reading_start_q"] or 18, exam["reading_end_q"] or 45, exam_answers
        )

    return {
        "success": True,
        "passage": db.get_passage(clean_id),
        "old_answer": old_ans,
        "new_answer": new_ans,
        "pdf_highlighted": pdf_highlighted,
        "message": f"{clean_id} 정답을 '{old_ans or '-'}' → '{new_ans}' 로 정정했습니다." + (" (형광펜 크롭 갱신)" if pdf_highlighted else "")
    }


@router.post("/api/passages/{passage_id:path}/recapture")
@_ingest_serialized
def api_recapture_passage_pdf(passage_id: str):
    """지문 PDF 크롭 이미지 다시 캡처 (원본 PDF로부터 형광펜 하이라이트 문항 크롭 재생성)"""
    clean_id = normalize_bracket_id(passage_id)

    passage = db.get_passage(clean_id)
    if not passage:
        raise HTTPException(status_code=404, detail=f"지문 '{clean_id}'를 찾을 수 없습니다.")
    exam_id = passage["exam_id"]

    with db.get_connection() as conn:
        exam = conn.execute(
            "SELECT grade, year, month, reading_start_q, reading_end_q, subtype FROM exams WHERE id = ?", (exam_id,)
        ).fetchone()
        exam_answers = {int(r["q_num"]): (r["answer_text"] or "") for r in conn.execute(
            "SELECT q_num, answer_text FROM passages WHERE exam_id = ?", (exam_id,))}
    if not exam:
        raise HTTPException(status_code=404, detail=f"시험지 '{exam_id}'를 찾을 수 없습니다.")

    success = regenerate_exam_crops(
        exam_id, exam["grade"], exam["year"], exam["month"],
        exam["reading_start_q"] or 18, exam["reading_end_q"] or 45, exam_answers,
        subtype=exam["subtype"]
    )

    with db.get_connection() as conn:
        exam_passages = [dict(r) for r in conn.execute(
            "SELECT * FROM passages WHERE exam_id = ? ORDER BY q_num ASC", (exam_id,)
        ).fetchall()]

    updated_passage = db.get_passage(clean_id)
    if not success or not (updated_passage and updated_passage.get("pdf_crop_image")):
        return {
            "success": False,
            "message": "PDF 원본 파일이 없거나 캡처 생성에 실패했습니다. uploads 폴더의 PDF 파일을 확인하세요.",
            "passage": updated_passage,
            "passages": exam_passages
        }

    return {
        "success": True,
        "message": f"{clean_id} PDF 문항 캡처를 성공적으로 다시 생성했습니다.",
        "passage": updated_passage,
        "passages": exam_passages
    }


@router.post("/api/passages/{passage_id:path}/upload-crop")
async def api_upload_passage_crop(passage_id: str, file: UploadFile = File(...)):
    """지문 PDF 크롭 이미지 수동 업로드 (업로드된 이미지가 해당 문항의 최신 이미지가 됨)"""
    clean_id = normalize_bracket_id(passage_id)
    passage = db.get_passage(clean_id)
    if not passage:
        raise HTTPException(status_code=404, detail=f"지문 '{clean_id}'를 찾을 수 없습니다.")

    # 파일 확장자 검증
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in (".png", ".jpg", ".jpeg", ".webp"):
        raise HTTPException(status_code=400, detail="이미지 파일(.png, .jpg, .jpeg, .webp)만 업로드 가능합니다.")

    os.makedirs(paths.CAPTURES_DIR, exist_ok=True)
    # 안전한 파일명 생성: manual_{clean_id}_{timestamp}.png
    safe_clean_id = clean_id.replace(" ", "_").replace("[", "").replace("]", "").replace("-", "_")
    target_filename = f"manual_{safe_clean_id}_{int(time.time())}{ext}"
    target_filepath = os.path.join(paths.CAPTURES_DIR, target_filename)

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="빈 파일입니다.")

    with open(target_filepath, "wb") as f:
        f.write(content)

    web_img_url = f"/static/captures/{target_filename}"
    with db.get_connection() as conn:
        conn.execute("UPDATE passages SET pdf_crop_image = ? WHERE id = ?", (web_img_url, clean_id))
        conn.commit()

    updated_passage = db.get_passage(clean_id)
    return {
        "success": True,
        "image_url": f"{web_img_url}?t={int(time.time())}",
        "passage": updated_passage,
        "message": f"{clean_id} 문항의 PDF 캡처 이미지가 성공적으로 최신 파일로 교체되었습니다."
    }


@router.post("/api/passages/{passage_id:path}/upload-audio")
async def api_upload_passage_audio(passage_id: str, file: UploadFile = File(...)):
    """듣기 문항 음성 파일 수동 업로드 (업로드된 오디오가 해당 문항의 최신 음성이 됨)"""
    clean_id = normalize_bracket_id(passage_id)
    passage = db.get_passage(clean_id)
    if not passage:
        raise HTTPException(status_code=404, detail=f"지문 '{clean_id}'를 찾을 수 없습니다.")

    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in (".mp3", ".wav", ".m4a"):
        raise HTTPException(status_code=400, detail="오디오 파일(.mp3, .wav, .m4a)만 업로드 가능합니다.")

    os.makedirs(paths.AUDIO_DIR, exist_ok=True)
    safe_clean_id = clean_id.replace(" ", "_").replace("[", "").replace("]", "").replace("-", "_")
    target_filename = f"manual_{safe_clean_id}_{int(time.time())}{ext}"
    target_filepath = os.path.join(paths.AUDIO_DIR, target_filename)

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="빈 파일입니다.")

    with open(target_filepath, "wb") as f:
        f.write(content)

    web_audio_url = f"/static/audio/{target_filename}"

    # audio_generations 테이블 또는 캐시 동기화
    with db.get_connection() as conn:
        # 혹시 passages 테이블에 오디오 경로 컬럼이 있거나 audio_generations가 있는 경우 안전 처리
        try:
            conn.execute(
                """
                INSERT INTO audio_generations (passage_id, engine, file_path, voice_name, created_at)
                VALUES (?, 'manual', ?, '수동 업로드', CURRENT_TIMESTAMP)
                """,
                (clean_id, target_filepath)
            )
            conn.commit()
        except Exception:
            pass

    return {
        "success": True,
        "audio_url": f"{web_audio_url}?t={int(time.time())}",
        "message": f"{clean_id} 문항의 오디오 파일이 성공적으로 최신 음성으로 교체되었습니다."
    }



@router.post("/api/passages/{passage_id}/tags")
def api_add_passage_tag(passage_id: str, req: TagRequest):
    """지문 태그 추가"""
    clean_id = normalize_bracket_id(passage_id)
    success = db.add_passage_tag(clean_id, req.tag_name)
    tags = db.get_passage_tags(clean_id)
    return {"success": success, "tags": tags}


@router.delete("/api/passages/{passage_id}/tags/{tag_name}")
def api_delete_passage_tag(passage_id: str, tag_name: str):
    """지문 태그 삭제"""
    clean_id = normalize_bracket_id(passage_id)
    success = db.remove_passage_tag(clean_id, tag_name)
    tags = db.get_passage_tags(clean_id)
    return {"success": success, "tags": tags}


@router.post("/api/sentences/{sentence_id}/tags")
def api_add_sentence_tag(sentence_id: str, req: TagRequest):
    """문장 태그 추가"""
    clean_id = normalize_bracket_id(sentence_id)
    success = db.add_sentence_tag(clean_id, req.tag_name)
    tags = db.get_sentence_tags(clean_id)
    return {"success": success, "tags": tags}


@router.delete("/api/sentences/{sentence_id}/tags/{tag_name}")
def api_delete_sentence_tag(sentence_id: str, tag_name: str):
    """문장 태그 삭제"""
    clean_id = normalize_bracket_id(sentence_id)
    success = db.remove_sentence_tag(clean_id, tag_name)
    tags = db.get_sentence_tags(clean_id)
    return {"success": success, "tags": tags}


@router.patch("/api/sentences/{sentence_id:path}/text")
@router.put("/api/sentences/{sentence_id:path}/text")
def api_update_sentence_text(sentence_id: str, req: SentenceTextUpdateRequest):
    """단일 문장의 본문 텍스트 수동 수정 업데이트"""
    clean_id = normalize_bracket_id(sentence_id)
    new_text = req.sentence_text.strip()
    if not new_text:
        raise HTTPException(status_code=400, detail="문장 텍스트는 비어 있을 수 없습니다.")

    # 문장 존재 확인
    with db.get_connection() as conn:
        sent = conn.execute("SELECT id, passage_id, sentence_text FROM sentences WHERE id = ?", (clean_id,)).fetchone()
        if not sent:
            raise HTTPException(status_code=404, detail=f"문장 '{clean_id}'를 찾을 수 없습니다.")

    success = db.update_sentence_text(clean_id, new_text)
    if not success:
        raise HTTPException(status_code=500, detail="문장 텍스트 업데이트에 실패했습니다.")

    # 업데이트된 문장 조회
    with db.get_connection() as conn:
        updated = conn.execute("SELECT id, passage_id, order_index, sentence_text, word_count FROM sentences WHERE id = ?", (clean_id,)).fetchone()

    return {
        "success": True,
        "sentence_id": clean_id,
        "sentence_text": updated["sentence_text"],
        "word_count": updated["word_count"],
        "message": f"{clean_id} 문장 텍스트가 성공적으로 수정되었습니다."
    }

