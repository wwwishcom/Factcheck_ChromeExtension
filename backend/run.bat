@echo off
echo FF | Factcheck-Finger 백엔드 서버 시작 중...
echo.

REM 가상환경이 없으면 생성
if not exist "venv" (
    echo 가상환경 생성 중...
    python -m venv venv
)

REM 가상환경 활성화
call venv\Scripts\activate

REM 패키지 설치
echo 패키지 설치 중...
pip install -r requirements.txt -q

REM .env 파일 확인
if not exist ".env" (
    echo.
    echo [오류] .env 파일이 없습니다!
    echo .env.example 을 복사해서 .env 로 만들고 키를 채워넣으세요.
    pause
    exit
)

echo.
echo 서버 시작! http://localhost:8000
echo 종료하려면 Ctrl+C 를 누르세요.
echo.
uvicorn main:app --reload --port 8000
pause
