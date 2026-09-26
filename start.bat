@echo off
setlocal EnableDelayedExpansion
chcp 65001 >nul
title KHOI DONG FB TOOL BDS VA FASTAPI SERVER
color 0A

set "ROOT_DIR=%~dp0"
set "LOGS_DIR=%ROOT_DIR%logs"
if not exist "%LOGS_DIR%" mkdir "%LOGS_DIR%" 2>nul
set "DEBUG_LOG=%LOGS_DIR%\start_debug.log"

:: Bat dau ghi log
echo ======================================================== > "%DEBUG_LOG%"
echo [THOI GIAN] %DATE% %TIME% >> "%DEBUG_LOG%"
echo [THU MUC GOC] %ROOT_DIR% >> "%DEBUG_LOG%"

echo ========================================================
echo         KHOI DONG FB TOOL BDS VA FASTAPI SERVER
echo ========================================================
echo [LOG] Nhat ky khoi dong: logs\start_debug.log
echo.

set "VENV_DIR=%ROOT_DIR%venv"
set "VENV_PYTHON=%VENV_DIR%\Scripts\python.exe"
set "PROFILES_DIR=%ROOT_DIR%profiles"

:: 1. Kiem tra Python Virtual Environment
if exist "%VENV_PYTHON%" (
    echo [OK] Python Environment: "%VENV_PYTHON%"
    echo [OK] Python Environment: "%VENV_PYTHON%" >> "%DEBUG_LOG%"
) else (
    echo [INFO] Dang tao Python Virtual Environment...
    echo [INFO] Dang tao venv >> "%DEBUG_LOG%"
    py -m venv "%VENV_DIR%" 2>> "%DEBUG_LOG%" || python -m venv "%VENV_DIR%" 2>> "%DEBUG_LOG%"
    if exist "%VENV_PYTHON%" (
        echo [OK] Tao venv thanh cong.
        echo [OK] Tao venv thanh cong >> "%DEBUG_LOG%"
    ) else (
        echo [LOI] Khong the tao virtual environment. Vui long cai dat Python 3.10+
        echo [LOI] Khong tim thay Python >> "%DEBUG_LOG%"
        pause
        exit /b 1
    )
)

:: 2. Tim Ungoogled Chromium
set "CHROME_EXE="
if exist "%ROOT_DIR%Ungoogled Chromium\app\chrome.exe" (
    set "CHROME_EXE=%ROOT_DIR%Ungoogled Chromium\app\chrome.exe"
) else if exist "%ROOT_DIR%Ungoogled Chromium\chrome.exe" (
    set "CHROME_EXE=%ROOT_DIR%Ungoogled Chromium\chrome.exe"
) else if exist "%ROOT_DIR%Ungoogled Chromium\chromium.exe" (
    set "CHROME_EXE=%ROOT_DIR%Ungoogled Chromium\chromium.exe"
) else (
    for /f "delims=" %%I in ('dir /b /s "%ROOT_DIR%Ungoogled Chromium\chrome.exe" 2^>nul') do (
        if not defined CHROME_EXE set "CHROME_EXE=%%I"
    )
    if not defined CHROME_EXE (
        for /f "delims=" %%I in ('dir /b /s "%ROOT_DIR%Ungoogled Chromium\chromium.exe" 2^>nul') do (
            if not defined CHROME_EXE set "CHROME_EXE=%%I"
        )
    )
)

echo [CHROMIUM] %CHROME_EXE% >> "%DEBUG_LOG%"

if not exist "%PROFILES_DIR%" (
    mkdir "%PROFILES_DIR%" 2>nul
)

:: 3. Quet danh sach Profile Ungoogled Chromium
echo.
echo ========================================================
echo         DANH SACH PROFILE UNGOOGLED CHROMIUM:
echo ========================================================

set /a PROF_COUNT=0
for /d %%D in ("%PROFILES_DIR%\*") do (
    set /a PROF_COUNT+=1
    set "PROF_!PROF_COUNT!=%%~nxD"
    echo   [!PROF_COUNT!] %%~nxD
    echo   Profile [!PROF_COUNT!]: %%~nxD >> "%DEBUG_LOG%"
)

if !PROF_COUNT! gtr 0 goto SELECT_EXISTING

:NO_PROFILE_FOUND
echo   (Chua co profile nao trong thu muc profiles)
echo.
set "NEW_PROF="
set /p "NEW_PROF=Nhap ten profile muon tao (vi du: DATVSA00): "
if "!NEW_PROF!"=="" set "NEW_PROF=DATVSA00"
mkdir "%PROFILES_DIR%\!NEW_PROF!" 2>nul
set "SELECTED_PROFILE=!NEW_PROF!"
goto START_SERVER_STEP

:SELECT_EXISTING
set /a CREATE_OPT=!PROF_COUNT!+1
echo   [!CREATE_OPT!] Tao Profile moi
echo   [0] Chi chay server, khong mo trinh duyet
echo ========================================================
set "CHOICE="
set /p "CHOICE=Chon Profile muon mo [Mac dinh 1 - !PROF_1!]: "
if "!CHOICE!"=="" set "CHOICE=1"

echo [USER CHOICE] %CHOICE% >> "%DEBUG_LOG%"

if "!CHOICE!"=="0" (
    set "SELECTED_PROFILE=NONE"
    goto START_SERVER_STEP
)

if "!CHOICE!"=="!CREATE_OPT!" goto CREATE_PROFILE_STEP
if "!CHOICE!"=="+" goto CREATE_PROFILE_STEP

:: Lay ten profile truc tiep bang call set
set "SELECTED_PROFILE="
call set "SELECTED_PROFILE=%%PROF_!CHOICE!%%"

if "!SELECTED_PROFILE!"=="" (
    echo [CANH BAO] So chon khong dung, tu dong chon Profile 1: "!PROF_1!"
    set "SELECTED_PROFILE=!PROF_1!"
)
goto START_SERVER_STEP

:CREATE_PROFILE_STEP
echo.
set "NEW_PROF="
set /p "NEW_PROF=Nhap ten Profile moi (vi du: DATVSA04): "
if "!NEW_PROF!"=="" set "NEW_PROF=DATVSA_NEW"
mkdir "%PROFILES_DIR%\!NEW_PROF!" 2>nul
set "SELECTED_PROFILE=!NEW_PROF!"
goto START_SERVER_STEP

:START_SERVER_STEP
echo.
if "!SELECTED_PROFILE!"=="NONE" (
    echo [INFO] Che do: Chi khoi dong server, khong mo Chromium.
    echo [MODE] Server only >> "%DEBUG_LOG%"
) else (
    echo [OK] Profile duoc chon: "!SELECTED_PROFILE!"
    echo      Duong dan: "%PROFILES_DIR%\!SELECTED_PROFILE!"
    echo [PROFILE SELECTED] !SELECTED_PROFILE! >> "%DEBUG_LOG%"
)

:: 4. Tao launcher uvicorn rieng biet
echo.
echo [INFO] Dang khoi dong FastAPI Server tai http://127.0.0.1:8000 ...
echo [INFO] Dang khoi dong uvicorn >> "%DEBUG_LOG%"

set "SERVER_LAUNCHER=%LOGS_DIR%\run_server.bat"
echo @echo off > "%SERVER_LAUNCHER%"
echo chcp 65001 ^>nul >> "%SERVER_LAUNCHER%"
echo title FastAPI Server VSA2 >> "%SERVER_LAUNCHER%"
echo cd /d "%ROOT_DIR%" >> "%SERVER_LAUNCHER%"
echo echo ======================================================== >> "%SERVER_LAUNCHER%"
echo echo   FastAPI Server dang chay tai: http://127.0.0.1:8000 >> "%SERVER_LAUNCHER%"
echo echo ======================================================== >> "%SERVER_LAUNCHER%"
echo "%VENV_PYTHON%" -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload >> "%SERVER_LAUNCHER%"
echo pause >> "%SERVER_LAUNCHER%"

start "FastAPI Server VSA2" cmd /k "%SERVER_LAUNCHER%"

:: 5. Kiem tra ket noi server san sang bang vong lap khong dung goto trong block
echo [INFO] Dang kiem tra ket noi server...
set /a ATTEMPTS=0

:WAIT_SERVER_LOOP
set /a ATTEMPTS+=1
timeout /t 1 /nobreak >nul

powershell -Command "$t = New-Object Net.Sockets.TcpClient; try { $t.Connect('127.0.0.1', 8000); $t.Close(); exit 0 } catch { exit 1 }" >nul 2>&1
if %errorlevel% equ 0 goto SERVER_READY
if %ATTEMPTS% geq 10 goto SERVER_READY

goto WAIT_SERVER_LOOP

:SERVER_READY
echo [OK] FastAPI Server da san sang tai http://127.0.0.1:8000!
echo [SERVER READY] Ket noi thanh cong sau %ATTEMPTS% giay >> "%DEBUG_LOG%"

:OPEN_BROWSER_STEP
echo [STEP] Bat dau khoi chay trinh duyet... >> "%DEBUG_LOG%"
if "!SELECTED_PROFILE!"=="NONE" goto DONE_ALL

set "ACTIVE_PROFILE_DIR=%PROFILES_DIR%\!SELECTED_PROFILE!"
if not exist "!ACTIVE_PROFILE_DIR!" mkdir "!ACTIVE_PROFILE_DIR!" 2>nul

if not defined CHROME_EXE goto LAUNCH_DEFAULT_BROWSER
if not exist "%CHROME_EXE%" goto LAUNCH_DEFAULT_BROWSER

echo [OK] Ungoogled Chromium: "%CHROME_EXE%"
echo [INFO] Dang mo Profile "!SELECTED_PROFILE!" voi 2 tab va Remote Debugging (port 9222)...
echo [LAUNCH CHROMIUM] "%CHROME_EXE%" --user-data-dir="!ACTIVE_PROFILE_DIR!" >> "%DEBUG_LOG%"

start "" "%CHROME_EXE%" --user-data-dir="!ACTIVE_PROFILE_DIR!" --remote-debugging-port=9222 --no-first-run --no-default-browser-check "http://127.0.0.1:8000" "https://www.facebook.com"
goto DONE_ALL

:LAUNCH_DEFAULT_BROWSER
echo [CANH BAO] Khong tim thay Ungoogled Chromium, mo bang trinh duyet mac dinh...
echo [LAUNCH DEFAULT BROWSER] >> "%DEBUG_LOG%"
start http://127.0.0.1:8000
start https://www.facebook.com

:DONE_ALL
echo [STEP] Hoan tat quy trinh khoi dong >> "%DEBUG_LOG%"
echo.
echo ========================================================
echo   HE THONG DA KHOI DONG THANH CONG!
echo   - Web App: http://127.0.0.1:8000
if not "!SELECTED_PROFILE!"=="NONE" (
    echo   - Profile: !SELECTED_PROFILE!
    echo   - Duong dan: %PROFILES_DIR%\!SELECTED_PROFILE!
)
echo   - Debug Log: logs\start_debug.log
echo ========================================================
echo.
echo [HOAN TAT] Nhan phim bat ky de dong cua so nay...
pause
