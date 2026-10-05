"""
pytest 공통 설정 및 테스트 픽스처 (tests/conftest.py)
- 프로젝트 루트 import 경로 자동 추가
- tmp_path 기반 격리된 임시 SQLite 데이터베이스 픽스처 (`tmp_db`)
- 격리된 테스트 데이터베이스 연동 FastAPI TestClient 픽스처 (`isolated_client`)
"""

import os
import sys
import pytest
from fastapi.testclient import TestClient

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


@pytest.fixture
def tmp_db(tmp_path, monkeypatch):
    """테스트마다 격리된 임시 SQLite DB를 생성하고 init_db()를 호출하는 픽스처"""
    from gichul import database as db
    from gichul.core.state import search_cache

    test_db_file = str(tmp_path / "test_gichul.db")
    monkeypatch.setenv("GICHUL_DB_PATH", test_db_file)
    monkeypatch.setattr(db, "DB_PATH", test_db_file)

    # 임시 DB 테이블 및 FTS5 초기화
    db.init_db()
    search_cache.clear()
    db.invalidate_exams_cache()

    yield db

    search_cache.clear()
    db.invalidate_exams_cache()


@pytest.fixture
def isolated_client(tmp_db):
    """격리된 임시 DB를 사용하는 FastAPI TestClient 픽스처"""
    from gichul.app import app
    return TestClient(app)
