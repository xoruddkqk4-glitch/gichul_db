@echo off
chcp 65001 > nul
title [05-gichul_db] 수능 영어 기출 데이터베이스 웹앱 실행
cls

echo =====================================================================
echo  🚀 [05-gichul_db] 수능 영어 기출 데이터베이스 웹서버 가동 중...
echo  - 브라우저가 자동으로 열립니다 (http://127.0.0.1:8000)
echo  - 서버를 종료하려면 이 창에서 Ctrl + C 를 누르거나 창을 닫으세요.
echo =====================================================================
echo.

set COQUI_TOS_AGREED=1
python run.py

if %errorlevel% neq 0 (
    echo.
    echo [오류] 서버 실행 중 문제가 발생했습니다.
    echo 'install.bat'을 먼저 실행해 필수 패키지가 모두 설치되었는지 확인하세요.
    pause
)
