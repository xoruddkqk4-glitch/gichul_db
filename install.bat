@echo off
chcp 65001 > nul
title [05-gichul_db] 환경 설정 및 패키지 설치 (install.bat)
cls

echo =====================================================================
echo  🚀 [05-gichul_db] 자동 패키지 설치 마법사
echo =====================================================================
echo.
echo [1/4] Python 확인 중...
python --version > nul 2>&1
if %errorlevel% neq 0 (
    echo [오류] Python이 설치되어 있지 않거나 환경 변수(PATH)에 등록되지 않았습니다.
    echo Python 3.10 또는 3.11을 먼저 설치해 주세요.
    pause
    exit /b
)
python --version
echo.

echo [2/4] 기본 웹서버 및 프로젝트 필수 패키지 설치 중...
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo [경고] requirements.txt 설치 중 일부 오류가 발생했을 수 있습니다.
)
echo.

echo [3/4] PyTorch (GPU 가속 지원) 설치 중...
echo NVIDIA GPU(RTX 등) CUDA 12.4 가속 버전을 설치합니다.
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124
echo.

echo [4/4] 수능 성우 복제 XTTS-v2 패키지 설치 중...
if exist "dist" (
    echo 미리 준비된 dist 폴더의 패키지들로 초고속 설치를 진행합니다 (C++ 컴파일 불필요).
    pip install --find-links=dist coqui-tts torchcodec
) else (
    echo dist 폴더가 없어 인터넷에서 직접 설치를 시도합니다...
    pip install coqui-tts torchcodec
)
echo.

echo =====================================================================
echo  🎉 모든 설치 및 환경 설정이 완료되었습니다!
echo  이제 'start.bat' 파일을 더블클릭하여 프로그램을 실행하세요.
echo =====================================================================
echo.
pause
