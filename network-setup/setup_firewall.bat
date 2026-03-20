@echo off
REM ================================================================
REM AutoStock - Windows Firewall Setup
REM 모바일/외부 접속을 위한 방화벽 규칙 추가
REM ================================================================
REM 관리자 권한으로 실행하세요 (우클릭 -> 관리자 권한으로 실행)
REM ================================================================

SET PROJECT_NAME=AutoStock
SET FRONTEND_PORT=3001
SET BACKEND_PORT=8001

echo ================================================================
echo %PROJECT_NAME% - 방화벽 포트 개방
echo ================================================================
echo.
echo 개방할 포트:
echo   - %FRONTEND_PORT% : 프론트엔드 (Vue 개발 서버)
echo   - %BACKEND_PORT%  : 백엔드 API (FastAPI)
echo.
echo 주의: 반드시 관리자 권한으로 실행하세요!
echo.
pause

echo.
echo [1/2] 프론트엔드 포트 %FRONTEND_PORT% 개방 중...
netsh advfirewall firewall add rule name="%PROJECT_NAME% - Frontend" dir=in action=allow protocol=TCP localport=%FRONTEND_PORT%
if %errorlevel% neq 0 (
    echo 오류: 포트 %FRONTEND_PORT% 규칙 추가 실패
) else (
    echo 완료: 포트 %FRONTEND_PORT% 개방됨
)

echo.
echo [2/2] 백엔드 API 포트 %BACKEND_PORT% 개방 중...
netsh advfirewall firewall add rule name="%PROJECT_NAME% - Backend API" dir=in action=allow protocol=TCP localport=%BACKEND_PORT%
if %errorlevel% neq 0 (
    echo 오류: 포트 %BACKEND_PORT% 규칙 추가 실패
) else (
    echo 완료: 포트 %BACKEND_PORT% 개방됨
)

echo.
echo ================================================================
echo 방화벽 설정 완료!
echo ================================================================
echo.
echo 다음 단계:
echo.
echo 1. 공유기 포트포워딩 설정 (아래 두 포트)
echo    - 외부포트 %FRONTEND_PORT% -> 내부IP:10.240.6.181, 내부포트 %FRONTEND_PORT%
echo    - 외부포트 %BACKEND_PORT%  -> 내부IP:10.240.6.181, 내부포트 %BACKEND_PORT%
echo    - 공유기 관리 페이지: 브라우저에서 게이트웨이 주소 입력 (ipconfig 확인)
echo.
echo 2. 로컬 접속 테스트
echo    - 프론트엔드: http://localhost:%FRONTEND_PORT%
echo    - 백엔드:     http://localhost:%BACKEND_PORT%/docs
echo.
echo 3. 공인 IP 확인 후 모바일 접속 테스트
echo    - 공인 IP 확인: https://ipconfig.kr 또는 curl ifconfig.me
echo    - 모바일(데이터): http://[공인IP]:%FRONTEND_PORT%
echo.
echo 4. IP가 자주 바뀐다면 DDNS 설정 권장
echo    - 무료: DuckDNS (duckdns.org), ipTIME DDNS
echo.
pause
