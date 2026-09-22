"""pytest 공통 설정: 프로젝트 루트를 import 경로에 추가 (어느 위치에서 pytest를 실행해도 모듈 import 가능)"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
