@echo off
setlocal EnableDelayedExpansion
chcp 65001 >nul
title KHOI DONG FB TOOL BĐS & FASTAPI SERVER
color 0A

echo ========================================================
echo         KHOI DONG FB TOOL BĐS & FASTAPI SERVER
echo ========================================================
echo.

set "ROOT_DIR=%~dp0"
set "VENV_DIR=%ROOT_DIR%venv"
set "VENV_PYTHON=%VENV_DIR%\Scripts\python.exe"
set "PROFILES_DIR=%ROOT_DIR%profiles"

:: 1. Kiem tra Python
if exist "%VENV_PYTHON%" (
    echo [OK] Python Virtual Environment: "%VENV_PYTHON%"
) else (
    echo [INFO] Dang tao Python Virtual Environment...
    py -m venv "%VENV_DIR%" 2>nul || python -m venv "%VENV_DIR%"
    if exist "%VENV_PYTHON%" (
        echo [OK] Tao venv thanh cong.
    ) else (
        echo [LOI] Khong the tao virtual environment. Vui long cai dat Python 3.10+
        pause
        exit /b 1
    )
)

:: 2. Tim Ungoogled Chromium executable
set "CHROME_EXE="
if exist "%ROOT_DIR%Ungoogled Chromium\chrome.exe" (
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

if not exist "%PROFILES_DIR%" (
    mkdir "%PROFILES_DIR%" 2>nul
)

:: 3. Quet va chon Profile Ungoogled Chromium
echo.
echo ========================================================
echo         DANH SACH PROFILE UNGOOGLED CHROMIUM:
echo ========================================================
set /a PROF_COUNT=0
for /d %%D in ("%PROFILES_DIR%\*") do (
    set /a PROF_COUNT+=1
    set "PROF_!PROF_COUNT!=%%~nxD"
    echo   [!PROF_COUNT!] %%~nxD
)

set "SELECTED_PROFILE="
if !PROF_COUNT! equ 0 (
    echo   (Chua co profile nao trong thu muc profiles)
    echo.
    set /p NEW_PROF="Nhap ten profile moi muon tao (vi du: DATVSA00): "
    if "!NEW_PROF!"=="" set "NEW_PROF=DATVSA00"
    mkdir "%PROFILES_DIR%\!NEW_PROF!" 2>nul
    set "SELECTED_PROFILE=!NEW_PROF!"
) else (
    echo   [+] Tao Profile moi
    echo   [0] Chi chay server (khong mo trinh duyet)
    echo ========================================================
    set "CHOICE="
    set /p "CHOICE=Chon Profile muon mo [Mac dinh 1 - !PROF_1!]: "
    if "!CHOICE!"=="" set "CHOICE=1"
    
    if "!CHOICE!"=="0" (
        set "SELECTED_PROFILE=NONE"
    ) else if "!CHOICE!"=="+" (
        echo.
        set /p NEW_PROF="Nhap ten Profile moi (vi du: DATVSA04): "
        if "!NEW_PROF!"=="" set "NEW_PROF=DATVSA_NEW"
        mkdir "%PROFILES_DIR%\!NEW_PROF!" 2>nul
        set "SELECTED_PROFILE=!NEW_PROF!"
    ) else (
        set "SELECTED_PROFILE=!PROF_%CHOICE%!"
        if "!SELECTED_PROFILE!"=="" set "SELECTED_PROFILE=!PROF_1!"
    )
)

echo.
if "!SELECTED_PROFILE!"=="NONE" (
    echo [INFO] Che do: Chi khoi dong server, khong mo Chromium.
) else (
    echo [OK] Da chon Profile: "!SELECTED_PROFILE!"
    echo      Thu muc: "%PROFILES_DIR%\!SELECTED_PROFILE!"
)

:: 4. Khoi dong FastAPI Server o cua so rieng biet
echo.
echo [INFO] Dang khoi dong FastAPI Server tai http://127.0.0.1:8000 ...
start "FastAPI Server (VSA2)" cmd /k "chcp 65001 >nul && title FastAPI Server (VSA2) && cd /d "%ROOT_DIR%" && "%VENV_PYTHON%" -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload"

:: 5. Cho server khoi dong va san sang
echo [INFO] Dang kiem tra ket noi server...
set /a ATTEMPTS=0
:WAIT_SERVER
set /a ATTEMPTS+=1
timeout /t 1 /nobreak >nul

powershell -Command "$t = New-Object Net.Sockets.TcpClient; try { $t.Connect('127.0.0.1', 8000); $t.Close(); exit 0 } catch { exit 1 }" >nul 2>&1
if %errorlevel% equ 0 (
    echo [OK] FastAPI Server da san sang tai http://127.0.0.1:8000!
    goto LAUNCH_BROWSER
)

if %ATTEMPTS% geq 20 (
    echo [CANH BAO] Server mat nhieu thoi gian de khoi dong. Van se tiep tuc...
    goto LAUNCH_BROWSER
)

goto WAIT_SERVER

:LAUNCH_BROWSER
echo.
if "!SELECTED_PROFILE!"=="NONE" goto FINISH

set "TARGET_PROFILE_DIR=%PROFILES_DIR%\!SELECTED_PROFILE!"
if not exist "!TARGET_PROFILE_DIR!" mkdir "!TARGET_PROFILE_DIR!" 2>nul

if defined CHROME_EXE (
    if exist "%CHROME_EXE%" (
        echo [OK] Tim thay Ungoogled Chromium: "%CHROME_EXE%"
        echo [INFO] Dang mo Profile: "!SELECTED_PROFILE!" ...
        echo [INFO] Mo 2 tab: http://127.0.0.1:8000 va https://www.facebook.com
        start "" "%CHROME_EXE%" --user-data-dir="!TARGET_PROFILE_DIR!" --no-first-run --no-default-browser-check "http://127.0.0.1:8000" "https://www.facebook.com"
        goto FINISH
    )
)

echo [CANH BAO] Khong tim thay Ungoogled Chromium. Mo bang trinh duyet mac dinh...
start http://127.0.0.1:8000
start https://www.facebook.com

:FINISH
echo.
echo ========================================================
echo   HE THONG DA KHOI DONG THANH CONG!
echo   - FastAPI Server: http://127.0.0.1:8000
if not "!SELECTED_PROFILE!"=="NONE" (
    echo   - Active Profile: !SELECTED_PROFILE!
    echo   - Profile Path:   %PROFILES_DIR%\!SELECTED_PROFILE!
)
echo ========================================================
echo.
timeout /t 5
