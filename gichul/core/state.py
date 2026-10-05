"""
05-gichul_db: 공통 런타임 상태, 캐시, 락 및 헬퍼 모듈 (gichul/core/state.py)
"""

import os
import json
import threading
import functools
from collections import OrderedDict
from typing import Optional, Any

from .. import paths
from .. import access

try:
    import orjson
    def fast_json_dumps(obj: Any) -> bytes:
        return orjson.dumps(obj)
except ImportError:
    def fast_json_dumps(obj: Any) -> bytes:
        return json.dumps(obj, ensure_ascii=False).encode("utf-8")


class FastSearchCache:
    """스레드 안전 인메모리 검색 결과 캐시 (동일 조건 쿼리 1ms 즉시 반환)"""
    def __init__(self, maxsize: int = 256):
        self._cache: OrderedDict = OrderedDict()
        self._maxsize = maxsize
        self._lock = threading.Lock()

    def get(self, key: str) -> Optional[bytes]:
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
                return self._cache[key]
            return None

    def set(self, key: str, value: bytes) -> None:
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
            self._cache[key] = value
            if len(self._cache) > self._maxsize:
                self._cache.popitem(last=False)

    def clear(self) -> None:
        with self._lock:
            self._cache.clear()


search_cache = FastSearchCache(maxsize=256)

INGEST_LOCK = threading.Lock()


def _ingest_serialized(fn):
    """PDF/HWP 처리 라우트를 INGEST_LOCK으로 직렬화하는 데코레이터 (FastAPI 시그니처는 functools.wraps로 유지)"""
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        with INGEST_LOCK:
            return fn(*args, **kwargs)
    return wrapper


def get_current_role() -> str:
    """요청한 사용자의 등급 (admin / member / guest). 조회 API가 Depends로 받아 DB 함수의 user_role로 넘긴다."""
    return access.DEFAULT_ROLE


_WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
_CACHE_SAFE_WRITE_PREFIXES = ("/api/settings/",)
