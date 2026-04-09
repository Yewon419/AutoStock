@echo off
REM AutoStock - Windows Firewall Setup
REM Run as Administrator (Right-click -> Run as administrator)

SET PROJECT_NAME=AutoStock
SET PORT1=3001
SET SERVICE1=Frontend
SET PORT2=8001
SET SERVICE2=Backend API

SET LOCAL_IP=192.168.68.64

echo ================================
echo %PROJECT_NAME% - Firewall Setup
echo ================================
echo.
echo Ports to open:
echo   %PORT1% : %SERVICE1%
echo   %PORT2% : %SERVICE2%
echo.
echo Local IP: %LOCAL_IP%
echo.
pause

echo.
echo [1/2] Opening port %PORT1% (%SERVICE1%)...
netsh advfirewall firewall add rule name="%PROJECT_NAME% - %SERVICE1%" dir=in action=allow protocol=TCP localport=%PORT1%
if %errorlevel% neq 0 (
    echo ERROR: Port %PORT1% failed
) else (
    echo OK: Port %PORT1% opened
)

echo.
echo [2/2] Opening port %PORT2% (%SERVICE2%)...
netsh advfirewall firewall add rule name="%PROJECT_NAME% - %SERVICE2%" dir=in action=allow protocol=TCP localport=%PORT2%
if %errorlevel% neq 0 (
    echo ERROR: Port %PORT2% failed
) else (
    echo OK: Port %PORT2% opened
)

echo.
echo ================================
echo Done!
echo ================================
echo.
echo Next steps:
echo 1. docker compose up -d
echo 2. cd frontend ^&^& npm run dev -- --host --port 3001
echo 3. Set port forwarding on router:
echo    %PORT1% -^> %LOCAL_IP%:%PORT1%
echo    %PORT2% -^> %LOCAL_IP%:%PORT2%
echo 4. Check public IP: https://ipconfig.kr
echo 5. Test from mobile data: http://[PUBLIC_IP]:%PORT1%
echo.
pause
