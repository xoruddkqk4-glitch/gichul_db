"""
05-gichul_db: 수능 영어 듣기 성우 로컬 복제(XTTS-v2) & Edge-TTS 하이브리드 음성 서비스 모듈
(elevenlabs_service.py)

기능:
1. 수능 평가원(KICE) 남/여 성우 목소리 1:1 로컬 복제 (Zero-shot Voice Cloning with XTTS-v2)
   - static/voices/kice_male_reference.wav (수능 남자 성우 레퍼런스)
   - static/voices/kice_female_reference.wav (수능 여자 성우 레퍼런스)
   - GPU(RTX 5060) 자동 감지 및 초고속 가속, CPU 자동 폴백 지원
2. Microsoft Neural 고품질 무료 Edge-TTS (경량 보조 엔진)
3. 남성(M) / 여성(W) 화자 분기 자동 감지 및 듀얼 보이스 턴 분할 합성
4. 다중 화자 음성 청크 결합 및 MP3 파일 저장 (/static/audio/[exam_id]_[q_num].mp3)
5. 단일 문항 음성 생성 및 시험지 전체(1~17번) 일괄 생성
6. 시험지 전체 듣기 문항 MP3 파일 ZIP 압축 다운로드 패키징
"""

import os
os.environ["COQUI_TOS_AGREED"] = "1"
import re
import io
import json
import asyncio
import zipfile
import tempfile
import logging
from typing import List, Dict, Any, Optional, Tuple

import edge_tts
import database as db

logger = logging.getLogger(__name__)

# Windows 환경에서 torchaudio 2.11+가 torchcodec(FFmpeg DLL) 부재로 인해 발생하는 AudioDecoder 에러 완벽 방지 패치
try:
    import torch
    import torchaudio
    import soundfile as sf

    def _safe_torchaudio_load(filepath, *args, **kwargs):
        data, sr = sf.read(filepath, dtype="float32")
        tensor = torch.from_numpy(data)
        if tensor.ndim == 1:
            tensor = tensor.unsqueeze(0)
        else:
            tensor = tensor.t()
        return tensor, sr

    torchaudio.load = _safe_torchaudio_load
    logger.info("[Audio] torchaudio.load patched with reliable soundfile backend.")
except Exception as _patch_err:
    logger.warning(f"[Audio] torchaudio.load patch skipped: {_patch_err}")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
AUDIO_DIR = os.path.join(BASE_DIR, "static", "audio")
VOICES_DIR = os.path.join(BASE_DIR, "static", "voices")
os.makedirs(AUDIO_DIR, exist_ok=True)
os.makedirs(VOICES_DIR, exist_ok=True)

# 수능 평가원 성우 기준 음원 파일 경로
KICE_MALE_REF = os.path.join(VOICES_DIR, "kice_male_reference.wav")
KICE_FEMALE_REF = os.path.join(VOICES_DIR, "kice_female_reference.wav")

# Edge-TTS 기본 음성 및 속도 설정 (무료 Microsoft Neural)
DEFAULT_EDGE_TTS_VOICE_MALE = "en-US-GuyNeural"
DEFAULT_EDGE_TTS_VOICE_FEMALE = "en-US-JennyNeural"
DEFAULT_EDGE_TTS_RATE = "+0%"

# 남성/여성 화자 식별 정규식 패턴
MALE_SPEAKER_PATTERN = re.compile(
    r"^(?:M|Man|Boy|Male|Father|Son|Dad|Mr\.\s*\w+|Teacher\s*\(M\)|Student\s*\(M\)|Doctor\s*\(M\)|Host\s*\(M\)|Officer\s*\(M\))\b",
    re.IGNORECASE
)
FEMALE_SPEAKER_PATTERN = re.compile(
    r"^(?:W|Woman|Girl|Female|Mother|Daughter|Mom|Ms\.\s*\w+|Mrs\.\s*\w+|Teacher\s*\(W\)|Student\s*\(W\)|Doctor\s*\(W\)|Host\s*\(W\)|Officer\s*\(W\))\b",
    re.IGNORECASE
)

# 전역 XTTS 싱글톤 인스턴스 캐시 및 하드웨어 상태 캐시
_GLOBAL_XTTS_MODEL = None
_HARDWARE_STATUS_CACHE: Optional[Dict[str, Any]] = None


def get_hardware_status() -> Dict[str, Any]:
    """
    현재 머신의 PyTorch 및 CUDA(NVIDIA GPU) 하드웨어 가속 상태 감지 (싱글톤 캐싱 및 0ms find_spec 적용)
    """
    global _HARDWARE_STATUS_CACHE
    if _HARDWARE_STATUS_CACHE is not None:
        return _HARDWARE_STATUS_CACHE

    try:
        import importlib.util
        import torch
        cuda_ok = torch.cuda.is_available()
        dev_name = torch.cuda.get_device_name(0) if cuda_ok else "CPU"
        
        # TTS 라이브러리를 통째로 import하지 않고 find_spec으로 0.00ms에 설치 여부만 감지 (10초 이상 지연 원천 제거)
        tts_installed = importlib.util.find_spec("TTS") is not None

        _HARDWARE_STATUS_CACHE = {
            "torch_available": True,
            "cuda_available": cuda_ok,
            "device": "cuda" if cuda_ok else "cpu",
            "device_name": dev_name,
            "tts_installed": tts_installed,
            "status_text": f"NVIDIA GPU 가속 활성화 ({dev_name})" if cuda_ok else "CPU 모드 구동 (외장 GPU 미검출)",
            "ready": tts_installed
        }
    except ImportError:
        _HARDWARE_STATUS_CACHE = {
            "torch_available": False,
            "cuda_available": False,
            "device": "cpu",
            "device_name": "미설치",
            "tts_installed": False,
            "status_text": "PyTorch / TTS 패키지 미설치 (터미널에서 'pip install torch TTS' 설치 시 활성화)",
            "ready": False
        }
    return _HARDWARE_STATUS_CACHE


def get_tts_config() -> Dict[str, Any]:
    """저장된 전체 TTS 설정값 조회 (기본값: 수능 성우 복제 xtts)"""
    engine = db.get_setting("tts_engine", "xtts").strip() or "xtts"
    edge_male = db.get_setting("edge_tts_voice_male", DEFAULT_EDGE_TTS_VOICE_MALE).strip() or DEFAULT_EDGE_TTS_VOICE_MALE
    edge_female = db.get_setting("edge_tts_voice_female", DEFAULT_EDGE_TTS_VOICE_FEMALE).strip() or DEFAULT_EDGE_TTS_VOICE_FEMALE
    edge_rate = db.get_setting("edge_tts_rate", DEFAULT_EDGE_TTS_RATE).strip() or DEFAULT_EDGE_TTS_RATE

    hw_info = get_hardware_status()

    return {
        "engine": engine,
        "hardware": hw_info,
        "edge_tts": {
            "voice_male": edge_male,
            "voice_female": edge_female,
            "rate": edge_rate,
        },
        "voices": {
            "male_ref_exists": os.path.exists(KICE_MALE_REF),
            "female_ref_exists": os.path.exists(KICE_FEMALE_REF),
            "male_ref_url": "/static/voices/kice_male_reference.wav",
            "female_ref_url": "/static/voices/kice_female_reference.wav",
        }
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

        # 어휘 목록이나 해설 구역이 시작되면 대본 수집 즉시 중단
        if re.search(r"^(?:\[?Words\s*&?\s*Phrases\]?|\[?어휘\]?|Words\b|Vocabulary\b|\[해설\]|\[정답\])", l_s, re.IGNORECASE):
            break

        # 첫 화자 태그(M:, W: 등) 이전의 안내글 필터링
        has_spk = re.match(r"^(?:[MW]|Man|Woman|Boy|Girl|Male|Female|Teacher|Student|Doctor|Father|Mother|Son|Daughter)\s*[:：]", l_s, re.IGNORECASE)
        if has_spk:
            dialogue_started = True

        # 대화가 시작된 이후라도 완전한 한글 설명줄(화자 태그 없는 순수 한글 해석)은 대본 제외
        if dialogue_started and not has_spk:
            ko_cnt = len(re.findall(r"[\uac00-\ud7a3]", l_s))
            en_cnt = len(re.findall(r"[A-Za-z]", l_s))
            if ko_cnt > 3 and en_cnt == 0:
                continue

        clean_lines.append(l_s)

    full_clean_script = "\n".join(clean_lines).strip()
    if not full_clean_script:
        return []

    # 2. 화자 턴 단위 분할 정규식
    pattern = re.compile(
        r"(?=(?:^|\n)\s*(?:M|W|Man|Woman|Boy|Girl|Male|Female|Father|Mother|Son|Daughter|Dad|Mom|Mr\.\s*\w+|Ms\.\s*\w+|Mrs\.\s*\w+|Teacher(?:\s*\([MW]\))?|Student(?:\s*\([MW]\))?|Doctor(?:\s*\([MW]\))?|Host(?:\s*\([MW]\))?|Officer(?:\s*\([MW]\))?)\s*[:：])",
        re.IGNORECASE
    )

    raw_turns = pattern.split(full_clean_script)
    turns = []
    default_speaker = "female"

    for t in raw_turns:
        t = t.strip()
        if not t:
            continue

        m_spk = re.match(
            r"^((?:M|W|Man|Woman|Boy|Girl|Male|Female|Father|Mother|Son|Daughter|Dad|Mom|Mr\.\s*\w+|Ms\.\s*\w+|Mrs\.\s*\w+|Teacher(?:\s*\([MW]\))?|Student(?:\s*\([MW]\))?|Doctor(?:\s*\([MW]\))?|Host(?:\s*\([MW]\))?|Officer(?:\s*\([MW]\))?))\s*[:：]\s*(.*)$",
            t,
            re.IGNORECASE | re.DOTALL
        )

        if m_spk:
            spk_label = m_spk.group(1).strip()
            body_text = m_spk.group(2).strip()

            if MALE_SPEAKER_PATTERN.match(spk_label):
                current_speaker = "male"
            elif FEMALE_SPEAKER_PATTERN.match(spk_label):
                current_speaker = "female"
            else:
                current_speaker = default_speaker

            # 턴 교대 준비
            default_speaker = "female" if current_speaker == "male" else "male"
        else:
            current_speaker = default_speaker
            body_text = t

        # 한국어 단독 라인 및 괄호 번역문 최종 정제
        cleaned_body_lines = []
        for line in body_text.splitlines():
            line_s = line.strip()
            if not line_s:
                continue
            ko_count = len(re.findall(r"[\uac00-\ud7a3]", line_s))
            en_count = len(re.findall(r"[A-Za-z]", line_s))
            if ko_count > 0 and en_count == 0:
                continue
            cleaned_line = re.sub(r"[\(\[\{][^\)\]\}]*[\uac00-\ud7a3]+[^\)\]\}]*[\)\]\}]", "", line_s).strip()
            if cleaned_line:
                cleaned_body_lines.append(cleaned_line)

        final_text = " ".join(cleaned_body_lines).strip()
        final_text = re.sub(r"\s+", " ", final_text)

        # 영문/숫자 유효 발화가 있는 경우에만 턴 추가
        if final_text and re.search(r"[A-Za-z0-9]", final_text):
            turns.append({
                "speaker": current_speaker,
                "text": final_text
            })

    # 화자 분기가 전혀 없는 경우(독백 등)
    if not turns and full_clean_script:
        clean_lines = [l.strip() for l in full_clean_script.splitlines() if l.strip() and not (len(re.findall(r"[\uac00-\ud7a3]", l)) > 0 and len(re.findall(r"[A-Za-z]", l)) == 0)]
        turns.append({
            "speaker": "female",
            "text": " ".join(clean_lines).strip()
        })

    return turns


def _get_or_load_xtts_model():
    """XTTS-v2 모델 싱글톤 로더 (GPU/CUDA 자동 활용)"""
    global _GLOBAL_XTTS_MODEL
    if _GLOBAL_XTTS_MODEL is not None:
        return _GLOBAL_XTTS_MODEL

    try:
        import torch
        from TTS.api import TTS
    except ImportError as e:
        raise RuntimeError(
            "수능 성우 로컬 복제(XTTS-v2)를 구동하려면 PyTorch와 TTS 패키지가 필요합니다.\n"
            "터미널에서 'pip install torch TTS'를 실행해 주세요.\n"
            "(설치 전에는 설정에서 [Edge-TTS]를 선택하시면 즉시 음성을 생성하실 수 있습니다.)"
        ) from e

    device = "cuda" if torch.cuda.is_available() else "cpu"
    logger.info(f"[XTTS-v2] Loading model on device: {device}...")
    _GLOBAL_XTTS_MODEL = TTS("tts_models/multilingual/multi-dataset/xtts_v2").to(device)
    logger.info("[XTTS-v2] Model successfully loaded.")
    return _GLOBAL_XTTS_MODEL


def synthesize_xtts_turn(text: str, speaker_gender: str = "male") -> bytes:
    """
    수능 평가원 실제 남/여 성우 음성 샘플(WAV)을 레퍼런스로 하여
    XTTS-v2로 해당 성우의 목소리를 1:1 복제(Zero-shot Voice Cloning) 합성
    """
    clean_text = text.strip()
    if not clean_text or not re.search(r"[A-Za-z0-9]", clean_text):
        return b""

    ref_wav = KICE_MALE_REF if speaker_gender == "male" else KICE_FEMALE_REF
    if not os.path.exists(ref_wav):
        # 만약 해당 레퍼런스 음원이 없으면 다른 성별 레퍼런스 폴백
        fallback = KICE_FEMALE_REF if speaker_gender == "male" else KICE_MALE_REF
        if os.path.exists(fallback):
            ref_wav = fallback
        else:
            raise FileNotFoundError(f"수능 성우 기준 음원 파일({ref_wav})을 찾을 수 없습니다. static/voices 폴더를 확인해 주세요.")

    tts = _get_or_load_xtts_model()

    # 임시 WAV 파일로 합성 후 바이너리 읽기
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_f:
        tmp_path = tmp_f.name

    try:
        tts.tts_to_file(
            text=clean_text,
            speaker_wav=ref_wav,
            language="en",
            file_path=tmp_path
        )
        with open(tmp_path, "rb") as f:
            audio_bytes = f.read()
        return audio_bytes
    finally:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception:
                pass


async def synthesize_edge_tts_turn(text: str, voice: str, rate: str = "+0%") -> bytes:
    """Edge-TTS를 이용한 단일 턴 음성 비동기 합성 (Microsoft Neural 무료 고품질 음성)"""
    clean_text = text.strip()
    if not clean_text or not re.search(r"[A-Za-z0-9]", clean_text):
        return b""
    communicate = edge_tts.Communicate(clean_text, voice, rate=rate)
    audio_data = bytearray()
    try:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_data.extend(chunk["data"])
    except edge_tts.exceptions.NoAudioReceived:
        logger.warning(f"[Edge-TTS Warning] No audio received for turn: {clean_text[:40]}")
        return b""
    except Exception as e:
        logger.error(f"[Edge-TTS Error] {e} for turn: {clean_text[:40]}")
        return b""
    return bytes(audio_data)


async def generate_tts_preview(engine: str = "xtts", gender: str = "male", rate: str = "+0%") -> str:
    """
    선택된 TTS 엔진 및 성별 목소리 샘플 미리듣기 파일 생성
    (/static/audio/preview_tts.mp3)
    """
    sample_text = (
        "Hello! This is a test of the official CSAT English listening voice for high school examinations."
        if gender == "female" else
        "Good morning, students. This is a sample recording of the English listening test narrator."
    )

    if engine == "xtts":
        # 수능 성우(W/M) 평가원 실전 톤 기준 음원(kice_female_reference.wav 등)을 0ms 즉시 반환하여 3GB 모델 다운로드/로딩 대기 완전 제거
        ref_path = KICE_FEMALE_REF if gender == "female" else KICE_MALE_REF
        if os.path.exists(ref_path):
            return f"/static/voices/{os.path.basename(ref_path)}?t={int(os.path.getmtime(ref_path))}"
        raise RuntimeError(f"수능 {'여성' if gender == 'female' else '남성'} 성우 샘플 음원 파일이 아직 등록되지 않았습니다.")
    else:
        # Edge-TTS
        voice = DEFAULT_EDGE_TTS_VOICE_MALE if gender == "male" else DEFAULT_EDGE_TTS_VOICE_FEMALE
        audio_bytes = await synthesize_edge_tts_turn(sample_text, voice, rate=rate)

    if not audio_bytes:
        raise RuntimeError("샘플 음성 생성 실패")

    preview_filename = "preview_tts.mp3"
    preview_path = os.path.join(AUDIO_DIR, preview_filename)
    with open(preview_path, "wb") as f:
        f.write(audio_bytes)
    return f"/static/audio/{preview_filename}?t={int(os.path.getmtime(preview_path))}"


def sanitize_filename(name: str) -> str:
    """파일명으로 사용 가능한 안전한 문자열로 치환"""
    return re.sub(r'[\\/*?:"<>|\[\]\s]', '_', name).strip('_')


async def generate_passage_audio(passage_id: str) -> Dict[str, Any]:
    """
    단일 듣기 문항의 대본(script_text)을 기반으로 남/여 듀얼 보이스 합성 후 MP3 저장
    (XTTS-v2 수능 성우 로컬 복제 기본 또는 Edge-TTS 무료 보조 하이브리드 지원)
    """
    passage = db.get_passage(passage_id)
    if not passage:
        raise ValueError(f"문항을 찾을 수 없습니다: {passage_id}")

    script_text = passage.get("script_text") or passage.get("passage_text") or ""
    if not script_text.strip():
        raise ValueError("합성할 대본(스크립트) 텍스트가 없습니다.")

    tts_cfg = get_tts_config()
    engine = tts_cfg.get("engine", "xtts")

    turns = split_script_by_speaker(script_text)
    if not turns:
        raise ValueError("대본에서 추출된 발화가 없습니다.")

    combined_audio = bytearray()

    if engine == "xtts":
        hw = get_hardware_status()
        if not hw.get("ready"):
            raise RuntimeError(
                "수능 성우 로컬 복제(XTTS-v2) 구동을 위한 PyTorch/TTS 패키지가 설치되지 않았습니다.\n"
                "터미널에서 'pip install torch TTS'를 실행하거나, 상단 [AI 설정]에서 'Edge-TTS'를 선택해 주세요."
            )
        loop = asyncio.get_event_loop()
        for turn in turns:
            spk = turn["speaker"]
            turn_bytes = await loop.run_in_executor(None, synthesize_xtts_turn, turn["text"], spk)
            if turn_bytes:
                combined_audio.extend(turn_bytes)
    else:
        # Edge-TTS
        edge_cfg = tts_cfg.get("edge_tts", {})
        male_voice = edge_cfg.get("voice_male") or DEFAULT_EDGE_TTS_VOICE_MALE
        female_voice = edge_cfg.get("voice_female") or DEFAULT_EDGE_TTS_VOICE_FEMALE
        rate = edge_cfg.get("rate") or DEFAULT_EDGE_TTS_RATE

        for turn in turns:
            voice = female_voice if turn["speaker"] == "female" else male_voice
            turn_bytes = await synthesize_edge_tts_turn(turn["text"], voice, rate=rate)
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

    # 1담화 2문항(16~17번, 22~23번 등) 자매 문항에도 동일 오디오 URL 동기화
    try:
        m = re.match(r"^\[?(.+?)-(\d+)번?\]?$", passage_id)
        if m:
            exam_pfx, q_val = m.group(1), int(m.group(2))
            sib_q = None
            if q_val == 16:
                sib_q = 17
            elif q_val == 17:
                sib_q = 16
            elif q_val == 22:
                sib_q = 23
            elif q_val == 23:
                sib_q = 22
            if sib_q:
                sib_id = f"[{exam_pfx}-{sib_q}번]"
                db.update_passage_audio(sib_id, relative_url)
    except Exception as sib_err:
        logger.warning(f"자매 문항 오디오 동기화 실패: {sib_err}")

    return {
        "success": True,
        "passage_id": passage_id,
        "audio_url": relative_url,
        "engine": engine,
        "turns_count": len(turns),
        "file_size": len(combined_audio)
    }


async def generate_exam_listening_audio(exam_id: str) -> Dict[str, Any]:
    """
    해당 시험지의 모든 듣기 문항(1~17번)에 대해 순차적으로 음성 합성 진행
    """
    passages = db.get_listening_passages_by_exam(exam_id)
    if not passages:
        raise ValueError(f"시험지 '{exam_id}'에 등록된 듣기 문항이 없습니다.")

    tts_cfg = get_tts_config()
    engine = tts_cfg.get("engine", "xtts")

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
            res = await generate_passage_audio(p_id)
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
        "engine": engine,
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
