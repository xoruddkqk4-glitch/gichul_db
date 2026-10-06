"""
05-gichul_db: 경로 상수 모음 (paths.py)
- 프로젝트의 모든 파일/폴더 경로는 이 모듈에서만 계산합니다.
- 다른 모듈은 os.path.dirname(__file__) 로 경로를 직접 계산하지 말고 여기 상수를 import 해서 씁니다.
- 기존 코드가 문자열 경로(os.path.join 등)를 쓰므로 모든 상수는 str 로 제공합니다.
"""

import os

# 프로젝트 루트 (gichul/ 의 상위 폴더)
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 실데이터 SQLite DB (테스트용 임시 DB를 쓰려면 GICHUL_DB_PATH 환경변수로 덮어쓰기)
DB_PATH = os.path.abspath(os.environ.get("GICHUL_DB_PATH") or os.path.join(ROOT_DIR, "gichul.db"))

# 웹 정적 파일 / 템플릿
STATIC_DIR = os.path.join(ROOT_DIR, "static")
TEMPLATES_DIR = os.path.join(ROOT_DIR, "templates")

# 업로드된 원본 PDF/HWP/CSV
UPLOADS_DIR = os.path.join(ROOT_DIR, "uploads")

# static/ 하위 생성물
CAPTURES_DIR = os.path.join(STATIC_DIR, "captures")
AUDIO_DIR = os.path.join(STATIC_DIR, "audio")
VOICES_DIR = os.path.join(STATIC_DIR, "voices")

# 데이터 파일
KEYS_DIR = os.path.join(ROOT_DIR, "data", "answer_keys")
GRAMMAR_CATEGORIES_JSON = os.path.join(STATIC_DIR, "data", "grammar_categories.json")

# 유인물 HWPX 템플릿 디렉토리 (기본 내장 템플릿: static/data/templates, 사용자 업로드 템플릿: uploads/templates)
HANDOUT_TEMPLATES_DIR = os.path.join(STATIC_DIR, "data", "templates")
CUSTOM_TEMPLATES_DIR = os.path.join(UPLOADS_DIR, "templates")

# 로그 파일 디렉토리 및 경로
LOGS_DIR = os.path.join(ROOT_DIR, "logs")
APP_LOG_PATH = os.path.join(LOGS_DIR, "app.log")
