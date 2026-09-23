"""
05-gichul_db: ElevenLabs M/W 듀얼 보이스 TTS 서비스 모듈 (elevenlabs_service.py)

기능:
1. 일레븐랩스(ElevenLabs) API 연동 음성 합성
2. 남성(M) / 여성(W) 화자 분기 자동 감지 및 듀얼 보이스(M/W) 개별 합성
3. 다중 화자 음성 청크 결합 및 MP3 파일 저장 (/static/audio/[exam_id]_[q_num].mp3)
4. 단일 문항 음성 생성 및 시험지 전체(1~17번) 일괄 생성
5. 시험지 전체 듣기 문항 MP3 파일 ZIP 압축 다운로드 패키징
"""

import os
import re
import json
import zipfile
import requests
from typing import List, Dict, Any, Optional, Tuple
import database as db

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
AUDIO_DIR = os.path.join(BASE_DIR, "static", "audio")
os.makedirs(AUDIO_DIR, exist_ok=True)

# 기본 음성 ID 및 모델 설정
DEFAULT_VOICE_MALE = "pNInz6obpgDQGcFmaJgB"    # Adam (남성, Free API 지원)
DEFAULT_VOICE_FEMALE = "EXAVITQu4vr4xnSDxMaL"  # Sarah (여성, Free API 지원 - 구 Rachel(21m00Tcm4TlvDq8ikWAM) 유료 전환 대응)
DEFAULT_MODEL_ID = "eleven_multilingual_v2"

# 남성/여성 화자 식별 정규식 패턴
MALE_SPEAKER_PATTERN = re.compile(
    r"^(?:M|Man|Boy|Male|Father|Son|Dad|Mr\.\s*\w+|Teacher\s*\(M\)|Student\s*\(M\)|Doctor\s*\(M\)|Host\s*\(M\)|Officer\s*\(M\))\b",
    re.IGNORECASE
)
FEMALE_SPEAKER_PATTERN = re.compile(
    r"^(?:W|Woman|Girl|Female|Mother|Daughter|Mom|Ms\.\s*\w+|Mrs\.\s*\w+|Teacher\s*\(W\)|Student\s*\(W\)|Doctor\s*\(W\)|Host\s*\(W\)|Officer\s*\(W\))\b",
    re.IGNORECASE
)


def get_elevenlabs_config() -> Dict[str, str]:
    """저장된 ElevenLabs 설정값 조회 (DB app_settings 및 환경변수 폴백)"""
    api_key = db.get_setting("elevenlabs_api_key", os.environ.get("ELEVENLABS_API_KEY", "")).strip()
    voice_male = db.get_setting("elevenlabs_voice_male", DEFAULT_VOICE_MALE).strip() or DEFAULT_VOICE_MALE
    voice_female = db.get_setting("elevenlabs_voice_female", DEFAULT_VOICE_FEMALE).strip() or DEFAULT_VOICE_FEMALE
    model_id = db.get_setting("elevenlabs_model_id", DEFAULT_MODEL_ID).strip() or DEFAULT_MODEL_ID

    # ElevenLabs에서 무료 계정 API 접근이 차단된 구 Rachel ID가 설정되어 있는 경우 안전하게 Sarah로 자동 폴백
    if voice_female == "21m00Tcm4TlvDq8ikWAM":
        voice_female = DEFAULT_VOICE_FEMALE

    return {
        "api_key": api_key,
        "voice_male": voice_male,
        "voice_female": voice_female,
        "model_id": model_id
    }


def split_script_by_speaker(script_text: str) -> List[Dict[str, str]]:
    """
    대본 텍스트를 화자별 턴(Turn) 단위로 분할하여 남/여 화자 태그 매핑
    - 어휘 목록, 표현 설명, 한국어 해석 등 비문장 라인을 엄격 제외하고 순수 대화 문장 단위만 음성 합성 대상으로 추출
    반환 형식: [{"speaker": "male"|"female", "text": "화자 발화 텍스트"}, ...]
    """
    if not script_text:
        return []

    # 1. 어휘, 표현 설명 및 한국어 단어 등 비문장 라인 사전 필터링
    clean_lines = []
    dialogue_started = False
    for raw_l in script_text.splitlines():
        l_s = raw_l.strip()
        if not l_s:
            continue
        is_spk = bool(re.match(r"^(?:[MW]|Man|Woman|Girl|Boy|Teacher|Student|Clerk|Host|Doctor|Officer|남|여)\s*[:：]", l_s, re.IGNORECASE))
        if is_spk:
            dialogue_started = True
        # 한국어 포함 라인 (어휘 설명 등) 제외 (화자 태그 '남:', '여:' 제외)
        if re.search(r"[\uac00-\ud7a3]", l_s):
            if not re.match(r"^\s*(?:남|여|선생님|학생)\s*[:：]", l_s):
                continue
        # 대화 시작 후, 화자 태그 없고 구두점(. ? !)으로 끝나지 않으며 단어수가 적은 어휘 라인 제외
        if dialogue_started and not is_spk:
            if not re.search(r"[\.\?\!\"\'\)]$", l_s):
                if len(l_s.split()) <= 5:
                    continue
        clean_lines.append(l_s)

    turns = []
    current_speaker = "male"  # 기본 화자
    current_lines = []

    speaker_tag_regex = re.compile(r"^\s*([A-Za-z0-9\.\(\)\s가-힣]+)\s*[:：]\s*(.*)$")

    for line in clean_lines:
        m = speaker_tag_regex.match(line)
        if m:
            raw_speaker = m.group(1).strip()
            speech_text = m.group(2).strip()

            # 화자 성별 감지
            detected_gender = None
            if MALE_SPEAKER_PATTERN.search(raw_speaker) or re.search(r"^(?:남|남학생|선생님\(남\)|아빠|아버지)\b", raw_speaker):
                detected_gender = "male"
            elif FEMALE_SPEAKER_PATTERN.search(raw_speaker) or re.search(r"^(?:여|여학생|선생님\(여\)|엄마|어머니)\b", raw_speaker):
                detected_gender = "female"
            else:
                # 일반명칭인 경우 이전 화자의 반대로 교대
                detected_gender = "female" if current_speaker == "male" else "male"

            if current_lines:
                speech = " ".join(current_lines).strip()
                if speech:
                    turns.append({
                        "speaker": current_speaker,
                        "text": speech
                    })
                current_lines = []

            current_speaker = detected_gender
            if speech_text:
                current_lines.append(speech_text)
        else:
            # 화자 태그가 없는 연속 발화 줄
            current_lines.append(line)

    if current_lines:
        speech = " ".join(current_lines).strip()
        if speech:
            turns.append({
                "speaker": current_speaker,
                "text": speech
            })

    # 화자 구분이 전혀 없는 단일 담화문인 경우
    if not turns and clean_lines:
        turns.append({
            "speaker": "male",
            "text": " ".join(clean_lines).strip()
        })

    return turns


def synthesize_turn_speech(text: str, voice_id: str, api_key: str, model_id: str = DEFAULT_MODEL_ID) -> bytes:
    """단일 발화 텍스트를 ElevenLabs TTS API로 호출하여 MP3 바이너리 반환"""
    if not api_key:
        raise ValueError("ElevenLabs API Key가 설정되지 않았습니다. 상단 [AI 설정]에서 API Key를 입력해 주세요.")
    if not text.strip():
        return b""

    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
    headers = {
        "xi-api-key": api_key,
        "Content-Type": "application/json",
        "Accept": "audio/mpeg"
    }
    payload = {
        "text": text.strip(),
        "model_id": model_id,
        "voice_settings": {
            "stability": 0.5,
            "similarity_boost": 0.75
        }
    }

    resp = requests.post(url, json=payload, headers=headers, timeout=60)
    if resp.status_code != 200:
        err_msg = f"ElevenLabs API Error ({resp.status_code}): {resp.text}"
        try:
            err_json = resp.json()
            if "detail" in err_json:
                detail = err_json["detail"]
                if isinstance(detail, dict) and "message" in detail:
                    err_msg = f"ElevenLabs API Error: {detail['message']}"
                else:
                    err_msg = f"ElevenLabs API Error: {detail}"
        except Exception:
            pass
        raise RuntimeError(err_msg)

    return resp.content


def sanitize_filename(name: str) -> str:
    """파일명으로 사용 가능한 안전한 문자열로 치환"""
    return re.sub(r'[\\/*?:"<>|\[\]\s]', '_', name).strip('_')


def generate_passage_audio(passage_id: str) -> Dict[str, Any]:
    """
    단일 듣기 문항의 대본(script_text)을 기반으로 남/여 듀얼 보이스 합성 후 MP3 저장
    """
    passage = db.get_passage(passage_id)
    if not passage:
        raise ValueError(f"문항을 찾을 수 없습니다: {passage_id}")

    script_text = passage.get("script_text") or passage.get("passage_text") or ""
    if not script_text.strip():
        raise ValueError("합성할 대본(스크립트) 텍스트가 없습니다.")

    cfg = get_elevenlabs_config()
    if not cfg["api_key"]:
        raise ValueError("ElevenLabs API Key가 설정되지 않았습니다. [AI 설정] 모달에서 등록해 주세요.")

    turns = split_script_by_speaker(script_text)
    if not turns:
        raise ValueError("대본에서 추출된 발화가 없습니다.")

    # 각 턴별 오디오 합성 및 바이너리 결합
    combined_audio = bytearray()
    for idx, turn in enumerate(turns):
        voice_id = cfg["voice_female"] if turn["speaker"] == "female" else cfg["voice_male"]
        turn_bytes = synthesize_turn_speech(turn["text"], voice_id, cfg["api_key"], cfg["model_id"])
        if turn_bytes:
            combined_audio.extend(turn_bytes)

    if not combined_audio:
        raise RuntimeError("음성 데이터 생성에 실패했습니다.")

    # MP3 파일 저장
    safe_id = sanitize_filename(passage_id)
    filename = f"{safe_id}.mp3"
    save_path = os.path.join(AUDIO_DIR, filename)
    with open(save_path, "wb") as f:
        f.write(combined_audio)

    relative_url = f"/static/audio/{filename}"
    db.update_passage_audio(passage_id, relative_url)

    return {
        "success": True,
        "passage_id": passage_id,
        "audio_url": relative_url,
        "turns_count": len(turns),
        "file_size": len(combined_audio)
    }


def generate_exam_listening_audio(exam_id: str) -> Dict[str, Any]:
    """
    해당 시험지의 모든 듣기 문항(1~17번)에 대해 순차적으로 음성 합성 진행
    """
    passages = db.get_listening_passages_by_exam(exam_id)
    if not passages:
        raise ValueError(f"시험지 '{exam_id}'에 등록된 듣기 문항이 없습니다.")

    cfg = get_elevenlabs_config()
    if not cfg["api_key"]:
        raise ValueError("ElevenLabs API Key가 설정되지 않았습니다. [AI 설정] 모달에서 등록해 주세요.")

    results = []
    success_count = 0
    fail_count = 0

    for p in passages:
        p_id = p["id"]
        script_text = p.get("script_text") or p.get("passage_text") or ""
        if not script_text.strip():
            results.append({
                "passage_id": p_id,
                "q_num": p.get("q_num"),
                "success": False,
                "error": "대본 텍스트 없음"
            })
            fail_count += 1
            continue

        try:
            res = generate_passage_audio(p_id)
            results.append({
                "passage_id": p_id,
                "q_num": p.get("q_num"),
                "success": True,
                "audio_url": res["audio_url"]
            })
            success_count += 1
        except Exception as e:
            results.append({
                "passage_id": p_id,
                "q_num": p.get("q_num"),
                "success": False,
                "error": str(e)
            })
            fail_count += 1

    return {
        "exam_id": exam_id,
        "total": len(passages),
        "success_count": success_count,
        "fail_count": fail_count,
        "results": results
    }


def create_listening_zip(exam_id: str) -> Dict[str, Any]:
    """
    시험지의 생성된 듣기 MP3 파일들을 하나의 ZIP 파일로 패키징하여 다운로드 경로 반환
    """
    passages = db.get_listening_passages_by_exam(exam_id)
    if not passages:
        raise ValueError(f"시험지 '{exam_id}'의 듣기 문항을 찾을 수 없습니다.")

    safe_exam = sanitize_filename(exam_id)
    zip_filename = f"{safe_exam}_listening_all.zip"
    zip_path = os.path.join(AUDIO_DIR, zip_filename)

    included_count = 0
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in passages:
            q_num = p.get("q_num", 0)
            audio_url = p.get("audio_file_path")
            mp3_path = None

            if audio_url:
                local_rel = audio_url.replace("/static/audio/", "")
                cand = os.path.join(AUDIO_DIR, local_rel)
                if os.path.exists(cand):
                    mp3_path = cand

            if not mp3_path:
                safe_id = sanitize_filename(p["id"])
                cand = os.path.join(AUDIO_DIR, f"{safe_id}.mp3")
                if os.path.exists(cand):
                    mp3_path = cand

            if mp3_path and os.path.exists(mp3_path):
                arcname = f"{q_num:02d}번_듣기.mp3"
                zf.write(mp3_path, arcname=arcname)
                included_count += 1

    if included_count == 0:
        raise ValueError("다운로드할 수 있는 생성된 MP3 오디오 파일이 없습니다. 먼저 문항별 또는 전체 음성 생성을 진행해 주세요.")

    return {
        "success": True,
        "exam_id": exam_id,
        "zip_url": f"/static/audio/{zip_filename}",
        "zip_filename": zip_filename,
        "included_files_count": included_count
    }
