"""
05-gichul_db: 통합 로깅 설정 모듈 (logging_config.py)
- 콘솔(stdout) + 파일 회전(logs/app.log, 5MB x 3개) 핸들러 제공
- 일관된 로그 포맷: [%(asctime)s] [%(levelname)s] [%(name)s] %(message)s
- FastAPI lifespan 또는 앱 기동 시 1회 호출
"""

import os
import sys
import logging
from logging.handlers import RotatingFileHandler
from typing import Optional

from .paths import LOGS_DIR, APP_LOG_PATH

_LOGGING_INITIALIZED = False


def setup_logging(level: Optional[str] = None) -> logging.Logger:
    """
    애플리케이션 전역 로깅 환경을 초기화하고 루트 로거를 반환합니다.
    이미 초기화된 경우 기존 로거를 반환합니다.
    """
    global _LOGGING_INITIALIZED
    root_logger = logging.getLogger()

    if _LOGGING_INITIALIZED:
        return root_logger

    os.makedirs(LOGS_DIR, exist_ok=True)

    log_level_str = (level or os.environ.get("GICHUL_LOG_LEVEL") or "INFO").upper()
    log_level = getattr(logging, log_level_str, logging.INFO)
    root_logger.setLevel(log_level)

    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # 1. 콘솔 핸들러 (stdout)
    has_console = any(isinstance(h, logging.StreamHandler) and not isinstance(h, RotatingFileHandler) for h in root_logger.handlers)
    if not has_console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(log_level)
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)

    # 2. 파일 회전 핸들러 (5MB x 3개, UTF-8)
    has_file = any(isinstance(h, RotatingFileHandler) for h in root_logger.handlers)
    if not has_file:
        try:
            file_handler = RotatingFileHandler(
                filename=APP_LOG_PATH,
                maxBytes=5 * 1024 * 1024,
                backupCount=3,
                encoding="utf-8"
            )
            file_handler.setLevel(log_level)
            file_handler.setFormatter(formatter)
            root_logger.addHandler(file_handler)
        except Exception as e:
            root_logger.warning(f"로그 파일 핸들러 생성 실패 ({APP_LOG_PATH}): {e}")

    _LOGGING_INITIALIZED = True
    return root_logger


def get_logger(name: str) -> logging.Logger:
    """모듈별 네임스페이스 로거를 반환합니다."""
    if not _LOGGING_INITIALIZED:
        setup_logging()
    return logging.getLogger(name)
