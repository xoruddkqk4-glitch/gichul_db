"""
05-gichul_db: 수능 영어 듣기 성우 로컬 복제(XTTS-v2) & Edge-TTS 하이브리드 음성 서비스 모듈
(tts_service.py)

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
import time
import wave
from typing import List, Dict, Any, Optional, Tuple

import numpy as np
import edge_tts
from . import database as db
from . import paths
from .text_utils import normalize_bracket_id

logger = logging.getLogger(__name__)

# Windows 환경에서 torchaudio 2.11+가 torchcodec(FFmpeg DLL) 부재로 인해 발생하는 AudioDecoder 에러 완벽 방지 패치
# import 시점에 torch를 올리지 않도록, XTTS 모델을 처음 불러올 때(_get_or_load_xtts_model) 한 번만 적용한다
_TORCHAUDIO_PATCHED = False


def _patch_torchaudio_load() -> None:
    """torchaudio.load 를 soundfile 기반으로 교체 (1회만, 실패해도 경고만 남김)"""
    global _TORCHAUDIO_PATCHED
    if _TORCHAUDIO_PATCHED:
        return
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
        _TORCHAUDIO_PATCHED = True
        logger.info("[Audio] torchaudio.load patched with reliable soundfile backend.")
    except Exception as _patch_err:
        logger.warning(f"[Audio] torchaudio.load patch skipped: {_patch_err}")

BASE_DIR = paths.ROOT_DIR
AUDIO_DIR = paths.AUDIO_DIR
VOICES_DIR = paths.VOICES_DIR
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

# 듣기 평가 오디오 타이밍 및 MP3 변환 설정
MP3_BITRATE_KBPS = 128
BELL_POST_PAUSE_SEC = 0.6      # 시작 종소리 울린 뒤 발화 시작 전 무음 (초)
TURN_PAUSE_SEC = 0.6           # 화자 턴 사이 무음 길이 (초)
REPEAT_PAUSE_SEC = 8.0         # 1지문 2문항 반복 간 무음 길이 (초) - 요구사항: 8초
FINAL_SILENT_PAUSE_SEC = 8.0   # 마지막 발화 후 종료 종소리 전 무음 길이 (초) - 요구사항: 8초
FINAL_TAIL_SEC = 0.5           # 종료 종소리 후 끝마무리 여백 (초)
CHIME_BELL_PATH = paths.CHIME_BELL_PATH

LAMEENC_INSTALL_HINT = (
    "XTTS 음성을 MP3로 저장하려면 lameenc 패키지가 필요합니다.\n"
    "터미널에서 'pip install lameenc'를 실행해 주세요."
)


def _lameenc_available() -> bool:
    """lameenc(MP3 인코더) 설치 여부 (import 없이 확인)"""
    import importlib.util
    return importlib.util.find_spec("lameenc") is not None


_CHIME_BELL_PCM_CACHE: Dict[int, bytes] = {}


def generate_chime_bell_pcm(sample_rate: int = 24000) -> bytes:
    """수능 영어 듣기 평가 시작/종료용 청아한 차임벨 (딩동: B5 -> G5) 16비트 모노 PCM 생성"""
    duration = 2.0
    t = np.linspace(0, duration, int(sample_rate * duration), endpoint=False)
    audio = np.zeros_like(t)

    def add_tone(start_s: float, f0: float, amp: float):
        idx0 = int(start_s * sample_rate)
        sub_t = t[:len(audio) - idx0]
        # 차임벨 고유의 맑은 배음 (기음 및 배음 6개)
        partials = [
            (1.00, 1.00, 3.2),
            (2.00, 0.40, 4.5),
            (2.76, 0.28, 6.0),
            (4.07, 0.15, 7.5),
            (5.40, 0.08, 9.0),
            (6.80, 0.04, 11.0),
        ]
        sig = np.zeros_like(sub_t)
        for mult, p_amp, decay in partials:
            sig += p_amp * np.sin(2 * np.pi * f0 * mult * sub_t) * np.exp(-decay * sub_t)

        # 클릭 노이즈 방지용 4ms 부드러운 어택
        att_len = max(1, int(0.004 * sample_rate))
        sig[:att_len] *= np.linspace(0, 1, att_len)
        audio[idx0:] += amp * sig

    # 수능 듣기 특유의 2음 차임 (딩: ~987.8Hz B5, 동: ~784.0Hz G5)
    add_tone(0.02, 987.77, 0.45)
    add_tone(0.55, 783.99, 0.50)

    # 음량 정규화 (-3dBFS, 약 0.75)
    peak = np.max(np.abs(audio))
    if peak > 0:
        audio = (audio / peak) * 0.75

    return (audio * 32767).astype(np.int16).tobytes()


def get_or_create_chime_bell_pcm(sample_rate: int = 24000) -> bytes:
    """종소리 16비트 모노 PCM 바이트 반환 (메모리 캐싱 및 chime_bell.wav 파일 연동)"""
    global _CHIME_BELL_PCM_CACHE
    if sample_rate in _CHIME_BELL_PCM_CACHE:
        return _CHIME_BELL_PCM_CACHE[sample_rate]

    if os.path.exists(CHIME_BELL_PATH):
        try:
            with wave.open(CHIME_BELL_PATH, "rb") as w:
                if w.getframerate() == sample_rate and w.getnchannels() == 1 and w.getsampwidth() == 2:
                    pcm = w.readframes(w.getnframes())
                    _CHIME_BELL_PCM_CACHE[sample_rate] = pcm
                    return pcm
        except Exception as e:
            logger.warning(f"기존 chime_bell.wav 로드 실패: {e}")

    pcm = generate_chime_bell_pcm(sample_rate)
    try:
        os.makedirs(os.path.dirname(CHIME_BELL_PATH), exist_ok=True)
        with wave.open(CHIME_BELL_PATH, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(sample_rate)
            w.writeframes(pcm)
    except Exception as e:
        logger.warning(f"chime_bell.wav 저장 실패: {e}")

    _CHIME_BELL_PCM_CACHE[sample_rate] = pcm
    return pcm


def wav_to_pcm(wav_bytes: bytes) -> bytes:
    """16비트 WAV 파일 바이트에서 순수 PCM 데이터 바이트만 추출"""
    with wave.open(io.BytesIO(wav_bytes), "rb") as w:
        sampwidth = w.getsampwidth()
        if sampwidth != 2:
            raise RuntimeError(f"16비트 PCM WAV만 지원합니다 (현재 {sampwidth * 8}비트).")
        return w.readframes(w.getnframes())


def mp3_to_pcm(mp3_bytes: bytes, target_sr: int = 24000) -> bytes:
    """MP3 바이트를 24000Hz 16비트 모노 PCM 바이트로 변환"""
    try:
        import soundfile as sf
        audio_np, in_sr = sf.read(io.BytesIO(mp3_bytes), dtype="int16")
        if in_sr != target_sr:
            import scipy.signal
            num_samples = int(len(audio_np) * target_sr / in_sr)
            audio_np = scipy.signal.resample(audio_np, num_samples).astype(np.int16)
        if len(audio_np.shape) > 1 and audio_np.shape[1] > 1:
            audio_np = audio_np.mean(axis=1).astype(np.int16)
        return audio_np.tobytes()
    except Exception as e:
        logger.warning(f"[mp3_to_pcm] soundfile 변환 실패, ffmpeg fallback 시도: {e}")
        import subprocess
        cmd = [
            "ffmpeg", "-y", "-i", "pipe:0", "-f", "s16le", "-ar", str(target_sr), "-ac", "1", "pipe:1"
        ]
        res = subprocess.run(cmd, input=mp3_bytes, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if res.returncode == 0 and res.stdout:
            return res.stdout
        raise RuntimeError(f"MP3 -> PCM 디코딩 실패: {e}")


def encode_pcm_to_mp3(pcm_data: bytes, sample_rate: int = 24000, channels: int = 1, bitrate: int = MP3_BITRATE_KBPS) -> bytes:
    """16비트 PCM 데이터를 고품질 MP3로 인코딩 (lameenc 우선, ffmpeg 보조)"""
    if not pcm_data:
        return b""
    try:
        import lameenc
        encoder = lameenc.Encoder()
        encoder.set_bit_rate(bitrate)
        encoder.set_in_sample_rate(sample_rate)
        encoder.set_channels(channels)
        encoder.set_quality(2)
        return bytes(encoder.encode(pcm_data)) + bytes(encoder.flush())
    except Exception as e:
        import subprocess
        cmd = [
            "ffmpeg", "-y", "-f", "s16le", "-ar", str(sample_rate), "-ac", str(channels),
            "-i", "pipe:0", "-b:a", f"{bitrate}k", "-f", "mp3", "pipe:1"
        ]
        res = subprocess.run(cmd, input=pcm_data, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if res.returncode == 0 and res.stdout:
            return res.stdout
        raise RuntimeError(f"MP3 인코딩 실패: {e}")


def is_two_questions_passage(passage: Dict[str, Any]) -> bool:
    """1지문 2문항(1담화 2문항, 16~17번 등) 여부 판별"""
    q_type = str(passage.get("question_type") or "")
    if "1담화" in q_type or "2문항" in q_type:
        return True
    q_num = passage.get("q_num")
    if q_num in (16, 17, 21, 22, 23):
        return True
    p_id = str(passage.get("id") or "")
    m = re.search(r"-(\d+)번?\]?$", p_id)
    if m and int(m.group(1)) in (16, 17, 21, 22, 23):
        return True
    return False


def build_listening_mp3(
    turn_pcm_chunks: List[bytes],
    sample_rate: int = 24000,
    channels: int = 1,
    turn_pause_sec: float = TURN_PAUSE_SEC,
    is_two_questions: bool = False,
    include_chimes: bool = True
) -> bytes:
    """
    수능 듣기 표준 규격으로 대사 턴들을 하나의 완성된 MP3 파일로 조립 및 인코딩
    - include_chimes: 앞과 뒤(마지막 발화 후 8초 silent 후) 종소리 삽입
    - is_two_questions: 1지문 2문항의 경우 음성 2번 반복 (반복 간 8초 silent, 종소리는 맨 앞/뒤만)
    """
    if not turn_pcm_chunks:
        return b""

    pcm = bytearray()
    silence = lambda sec: b"\x00" * (int(sample_rate * sec) * channels * 2)

    # 1. 맨 앞 종소리 (시작 여백 0.6초)
    if include_chimes:
        chime_pcm = get_or_create_chime_bell_pcm(sample_rate)
        pcm.extend(chime_pcm)
        pcm.extend(silence(BELL_POST_PAUSE_SEC))

    # 2. 1회차 발화 재생
    for i, chunk in enumerate(turn_pcm_chunks):
        if not chunk:
            continue
        if i > 0:
            pcm.extend(silence(turn_pause_sec))
        pcm.extend(chunk)

    # 3. 1지문 2문항인 경우: 반복 간 8초 silent 후 2회차 발화 재생 (종소리는 들어가지 않음)
    if is_two_questions:
        pcm.extend(silence(REPEAT_PAUSE_SEC))
        for i, chunk in enumerate(turn_pcm_chunks):
            if not chunk:
                continue
            if i > 0:
                pcm.extend(silence(turn_pause_sec))
            pcm.extend(chunk)

    # 4. 마지막 발화 후 8초 silent
    pcm.extend(silence(FINAL_SILENT_PAUSE_SEC))

    # 5. 맨 뒤 종소리
    if include_chimes:
        chime_pcm = get_or_create_chime_bell_pcm(sample_rate)
        pcm.extend(chime_pcm)
        pcm.extend(silence(FINAL_TAIL_SEC))

    return encode_pcm_to_mp3(bytes(pcm), sample_rate=sample_rate, channels=channels)


def _wav_turns_to_mp3(
    wav_chunks: List[bytes],
    pause_sec: float = TURN_PAUSE_SEC,
    is_two_questions: bool = False,
    include_chimes: bool = True
) -> bytes:
    """XTTS 턴별 WAV 청크들을 하나의 완성된 MP3로 조립 (하위 호환성 유지)"""
    pcm_chunks = [wav_to_pcm(c) for c in wav_chunks if c]
    return build_listening_mp3(
        pcm_chunks,
        sample_rate=24000,
        channels=1,
        turn_pause_sec=pause_sec,
        is_two_questions=is_two_questions,
        include_chimes=include_chimes
    )


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
            "mp3_encoder_installed": _lameenc_available(),
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
            "mp3_encoder_installed": _lameenc_available(),
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

    # torchaudio 패치는 TTS 라이브러리 import 전에 적용한다 (예전 import 시점 패치와 같은 순서)
    _patch_torchaudio_load()
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


# --- 음성 합성 진행률 추적 ---
# 프론트가 만든 job_id별로 "끝난 단계 / 전체 단계"를 기록한다.
# 단계 = 대사(턴) 1개 합성. XTTS는 마지막에 MP3 인코딩 1단계가 더 붙는다.
# 합성은 이벤트 루프에서 갱신하고, 진행률 조회 라우트는 읽기만 하므로 별도 잠금은 두지 않는다.
_TTS_PROGRESS: Dict[str, Dict[str, Any]] = {}
_PROGRESS_KEEP_SEC = 600  # 끝난 작업 기록 보관 시간


class TtsProgress:
    """job_id 하나의 진행 상황. job_id가 없으면 아무것도 기록하지 않는다."""

    def __init__(self, job_id: Optional[str], total: int = 0):
        self.job_id = (job_id or "").strip() or None
        self.done = 0
        self.total = total
        if self.job_id:
            _prune_progress()
            now = time.time()
            _TTS_PROGRESS[self.job_id] = {
                "status": "running", "done": 0, "total": total, "label": "",
                "started_at": now, "last_step_at": now, "finished_at": None,
            }

    def _push(self, **extra):
        if not self.job_id:
            return
        st = _TTS_PROGRESS.get(self.job_id)
        if st is None:
            return
        st["done"] = min(self.done, self.total) if self.total else self.done
        st["total"] = self.total
        st.update(extra)

    def add_total(self, n: int):
        self.total += max(0, n)
        self._push()

    def step(self, label: str = ""):
        self.done += 1
        self._push(label=label, last_step_at=time.time())

    def jump_to(self, done: int):
        """실패한 문항의 남은 단계를 건너뛸 때 사용"""
        if done > self.done:
            self.done = done
            self._push(last_step_at=time.time())

    def finish(self, ok: bool = True, message: str = ""):
        if ok:
            self.done = self.total
        self._push(status="done" if ok else "error", label=message, finished_at=time.time())


def _prune_progress():
    now = time.time()
    for key in [k for k, v in _TTS_PROGRESS.items()
                if v.get("finished_at") and now - v["finished_at"] > _PROGRESS_KEEP_SEC]:
        _TTS_PROGRESS.pop(key, None)


def get_tts_progress(job_id: str) -> Dict[str, Any]:
    """진행률 조회. 프론트가 단계 사이를 부드럽게 채울 수 있도록 경과 시간도 함께 돌려준다."""
    st = _TTS_PROGRESS.get((job_id or "").strip())
    if not st:
        return {"found": False}
    now = time.time()
    total = st["total"] or 0
    done = st["done"] or 0
    percent = 100.0 if st["status"] == "done" else (round(done / total * 100, 1) if total else 0.0)
    return {
        "found": True,
        "status": st["status"],
        "done": done,
        "total": total,
        "percent": percent,
        "label": st.get("label", ""),
        "elapsed_sec": round(now - st["started_at"], 2),
        "steps_elapsed_sec": round(st["last_step_at"] - st["started_at"], 2),  # 끝난 단계들에 걸린 시간
        "since_step_sec": round(now - st["last_step_at"], 2),                  # 현재 단계 경과 시간
    }


def _count_progress_units(script_text: str, engine: str = "xtts") -> int:
    """문항 하나의 진행 단계 수 (대사 수 + MP3 인코딩 1)"""
    turns = split_script_by_speaker(script_text or "")
    if not turns:
        return 0
    return len(turns) + 1


async def generate_passage_audio(passage_id: str, job_id: Optional[str] = None,
                                 progress: Optional[TtsProgress] = None) -> Dict[str, Any]:
    """
    단일 듣기 문항의 대본(script_text)을 기반으로 남/여 듀얼 보이스 합성 후 MP3 저장
    (XTTS-v2 수능 성우 로컬 복제 기본 또는 Edge-TTS 무료 보조 하이브리드 지원)
    - job_id: 진행률 조회용 작업 ID (단일 생성)
    - progress: 일괄 생성에서 넘겨받는 공용 진행 상황 (이 경우 전체 단계 수는 호출 쪽이 관리)
    """
    owns_progress = progress is None
    if owns_progress:
        progress = TtsProgress(job_id)
    try:
        result = await _generate_passage_audio_impl(passage_id, progress, owns_progress)
    except Exception as e:
        if owns_progress:
            progress.finish(ok=False, message=str(e))
        raise
    if owns_progress:
        progress.finish(ok=True)
    return result


async def _generate_passage_audio_impl(passage_id: str, progress: TtsProgress, owns_progress: bool) -> Dict[str, Any]:
    """
    단일 듣기 문항의 대본(script_text)을 기반으로 남/여 듀얼 보이스 합성 후 MP3 저장
    (XTTS-v2 수능 성우 로컬 복제 기본 또는 Edge-TTS 무료 보조 하이브리드 지원)
    - 음성 앞뒤 종소리 및 마지막 발화 후 8초 무음 적용
    - 1지문 2문항인 경우 2회 반복 재생 (반복 간 8초 무음, 종소리는 맨 앞/뒤만)
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
    if owns_progress:
        progress.add_total(len(turns) + 1)

    # 1지문 2문항(16~17번 등) 여부 판별
    is_two_q = is_two_questions_passage(passage)
    loop = asyncio.get_running_loop()
    pcm_chunks: List[bytes] = []

    if engine == "xtts":
        hw = get_hardware_status()
        if not hw.get("ready"):
            raise RuntimeError(
                "수능 성우 로컬 복제(XTTS-v2) 구동을 위한 PyTorch/TTS 패키지가 설치되지 않았습니다.\n"
                "터미널에서 'pip install torch TTS'를 실행하거나, 상단 [AI 설정]에서 'Edge-TTS'를 선택해 주세요."
            )
        if not _lameenc_available():
            # 긴 합성을 시작하기 전에 MP3 인코더 유무부터 확인
            raise RuntimeError(LAMEENC_INSTALL_HINT)

        for t_idx, turn in enumerate(turns, 1):
            spk = turn["speaker"]
            turn_bytes = await loop.run_in_executor(None, synthesize_xtts_turn, turn["text"], spk)
            if turn_bytes:
                pcm_data = wav_to_pcm(turn_bytes)
                pcm_chunks.append(pcm_data)
            progress.step(f"{passage_id} 대사 {t_idx}/{len(turns)}")
    else:
        # Edge-TTS
        edge_cfg = tts_cfg.get("edge_tts", {})
        male_voice = edge_cfg.get("voice_male") or DEFAULT_EDGE_TTS_VOICE_MALE
        female_voice = edge_cfg.get("voice_female") or DEFAULT_EDGE_TTS_VOICE_FEMALE
        rate = edge_cfg.get("rate") or DEFAULT_EDGE_TTS_RATE

        for t_idx, turn in enumerate(turns, 1):
            voice = female_voice if turn["speaker"] == "female" else male_voice
            turn_bytes = await synthesize_edge_tts_turn(turn["text"], voice, rate=rate)
            if turn_bytes:
                pcm_data = await loop.run_in_executor(None, mp3_to_pcm, turn_bytes)
                pcm_chunks.append(pcm_data)
            progress.step(f"{passage_id} 대사 {t_idx}/{len(turns)}")

    if not pcm_chunks:
        raise RuntimeError("음성 데이터 생성에 실패했습니다.")

    # MP3 인코딩 (앞뒤 종소리, 턴 간 무음, 1지문 2문항 8초 silent 반복, 마지막 발화 후 8초 silent 적용)
    combined_mp3 = await loop.run_in_executor(
        None,
        build_listening_mp3,
        pcm_chunks,
        24000,
        1,
        TURN_PAUSE_SEC,
        is_two_q,
        True
    )
    progress.step(f"{passage_id} MP3 인코딩")

    if not combined_mp3:
        raise RuntimeError("MP3 오디오 인코딩에 실패했습니다.")

    # MP3 파일 저장
    safe_id = sanitize_filename(passage_id)
    filename = f"{safe_id}.mp3"
    save_path = os.path.join(AUDIO_DIR, filename)
    with open(save_path, "wb") as f:
        f.write(combined_mp3)

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
        "is_two_questions": is_two_q,
        "file_size": len(combined_mp3)
    }


async def generate_exam_listening_audio(exam_id: str, job_id: Optional[str] = None) -> Dict[str, Any]:
    """
    해당 시험지의 모든 듣기 문항(1~17번)에 대해 순차적으로 음성 합성 진행
    - job_id: 진행률 조회용 작업 ID (전체 문항의 대사 수를 미리 세어 하나의 진행률로 표시)
    """
    progress = TtsProgress(job_id)
    passages = db.get_listening_passages_by_exam(exam_id)
    if not passages:
        progress.finish(ok=False, message="듣기 문항 없음")
        raise ValueError(f"시험지 '{exam_id}'에 등록된 듣기 문항이 없습니다.")

    tts_cfg = get_tts_config()
    engine = tts_cfg.get("engine", "xtts")

    units_by_id = {
        p["id"]: _count_progress_units(p.get("script_text") or p.get("passage_text") or "", engine)
        for p in passages
    }
    progress.add_total(sum(units_by_id.values()))

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

        target_done = progress.done + units_by_id.get(p_id, 0)
        try:
            res = await generate_passage_audio(p_id, progress=progress)
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
        # 실패한 문항은 남은 단계를 건너뛰어 진행률이 멈추지 않게 한다
        progress.jump_to(target_done)

    progress.finish(ok=True, message=f"성공 {success_count} / 실패 {fail_count}")
    first_error = next((r.get("error") for r in results if not r.get("success")), "")
    return {
        # 프론트(results-passage.js)는 success 값으로 성공/실패를 판단한다
        "success": success_count > 0,
        "message": (f"성공 {success_count}개, 실패 {fail_count}개" if success_count > 0
                    else f"모든 문항 음성 생성에 실패했습니다: {first_error}"),
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


async def merge_listening_mp3s(passage_ids: List[str]) -> bytes:
    """
    선택된 듣기 문항들의 MP3 음원을 순서대로 로드(미생성 시 즉시 합성)하여,
    문항 간 2.0초의 무음(Silence)을 삽입한 단일 통합 MP3 오디오 바이너리를 생성하여 반환.
    """
    if not passage_ids:
        raise ValueError("통합할 듣기 문항이 지정되지 않았습니다.")

    sample_rate = 24000
    channels = 1
    pause_sec = 2.0
    silence_gap = b"\x00" * (int(sample_rate * pause_sec) * channels * 2)

    merged_pcm = bytearray()
    loop = asyncio.get_running_loop()

    for idx, pid in enumerate(passage_ids):
        clean_id = normalize_bracket_id(pid)
        passage = db.get_passage(pid) or db.get_passage(clean_id)
        if not passage:
            logger.warning(f"[merge_listening_mp3s] 지문을 찾을 수 없음: {pid}")
            continue

        # MP3 파일 경로 확인
        mp3_path = None
        audio_url = passage.get("audio_file_path") or passage.get("audio_url")
        if audio_url:
            local_rel = audio_url.replace("/static/audio/", "")
            cand = os.path.join(AUDIO_DIR, local_rel)
            if os.path.exists(cand):
                mp3_path = cand

        if not mp3_path:
            safe_id = sanitize_filename(passage["id"])
            cand = os.path.join(AUDIO_DIR, f"{safe_id}.mp3")
            if os.path.exists(cand):
                mp3_path = cand

        mp3_bytes = None
        if mp3_path and os.path.exists(mp3_path):
            with open(mp3_path, "rb") as f:
                mp3_bytes = f.read()
        else:
            # 음원이 아직 생성되지 않은 경우 즉시 합성 진행
            logger.info(f"[merge_listening_mp3s] 문항 {passage['id']} 음원 부재로 즉시 합성 진행")
            try:
                res = await generate_passage_audio(passage["id"])
                safe_id = sanitize_filename(passage["id"])
                cand = os.path.join(AUDIO_DIR, f"{safe_id}.mp3")
                if os.path.exists(cand):
                    with open(cand, "rb") as f:
                        mp3_bytes = f.read()
            except Exception as e:
                logger.error(f"[merge_listening_mp3s] 문항 {passage['id']} 음성 생성 실패: {e}")
                continue

        if not mp3_bytes:
            continue

        # MP3 -> PCM 디코딩
        try:
            pcm_chunk = await loop.run_in_executor(None, mp3_to_pcm, mp3_bytes, sample_rate)
            if pcm_chunk:
                if len(merged_pcm) > 0:
                    merged_pcm.extend(silence_gap)
                merged_pcm.extend(pcm_chunk)
        except Exception as e:
            logger.error(f"[merge_listening_mp3s] PCM 디코딩 실패 ({passage['id']}): {e}")

    if not merged_pcm:
        raise RuntimeError("통합할 오디오 데이터를 생성하거나 로드할 수 없습니다.")

    # 전체 통합 MP3 인코딩
    encoded_mp3 = await loop.run_in_executor(
        None,
        encode_pcm_to_mp3,
        bytes(merged_pcm),
        sample_rate,
        channels,
        MP3_BITRATE_KBPS
    )

    return encoded_mp3

