"""
05-gichul_db: 원클릭 로컬 웹 애플리케이션 실행 스크립트 (run.py)
- 실행: python run.py
- 로컬 웹서버 (http://127.0.0.1:8000) 구동
"""

import uvicorn
import os
import webbrowser
import threading
import time

def open_browser_later():
    time.sleep(1.2)
    webbrowser.open("http://127.0.0.1:8000")

if __name__ == "__main__":
    print("\n" + "=" * 65)
    print(" 🚀 [05-gichul_db] 수능·모의고사 영어 기출 데이터베이스 웹앱")
    print(" - 로컬 접속 주소: http://127.0.0.1:8000")
    print(" - 종료하려면 터미널에서 Ctrl + C 를 누르세요.")
    print("=" * 65 + "\n")

    # 브라우저 자동 오픈 스레드 실행
    threading.Thread(target=open_browser_later, daemon=True).start()

    # Uvicorn 서버 구동
    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=True)
