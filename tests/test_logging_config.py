"""
05-gichul_db: 로깅 설정 및 전역 예외 처리 테스트 (test_logging_config.py)
"""

import os
import logging
import pytest
from fastapi.testclient import TestClient

from gichul.logging_config import setup_logging, get_logger
from gichul.paths import APP_LOG_PATH
from gichul.app import app


def test_setup_logging_creates_log_file():
    setup_logging(level="DEBUG")
    logger = get_logger("gichul.test_logger")
    test_msg = "test_setup_logging_msg_unique_123"
    logger.info(test_msg)

    # Flush handlers
    for h in logging.getLogger().handlers:
        h.flush()

    assert os.path.exists(APP_LOG_PATH)
    with open(APP_LOG_PATH, "r", encoding="utf-8") as f:
        content = f.read()
    assert test_msg in content


def test_get_logger_hierarchy():
    logger = get_logger("gichul.database")
    assert logger.name == "gichul.database"
    assert isinstance(logger, logging.Logger)


def test_global_exception_handler():
    client = TestClient(app, raise_server_exceptions=False)

    # 정의된 라우트 중 의도적으로 에러를 일으키거나 에러 엔드포인트를 임시 등록하여 검증
    @app.get("/api/test-error-endpoint")
    def _faulty_endpoint():
        raise RuntimeError("Controlled crash for testing exception handler")

    resp = client.get("/api/test-error-endpoint")
    assert resp.status_code == 500
    data = resp.json()
    assert data["success"] is False
    assert "Controlled crash" in data["detail"]
