@echo off
chcp 65001 >nul
title KHOI DONG FB TOOL BDS VA FASTAPI SERVER
color 0A

echo ========================================================
echo               KHOI DONG FASTAPI SERVER
echo ========================================================
echo.

set "ROOT_DIR=%~dp0"
set "VENV_DIR=%ROOT_DIR%venv"
set "VENV_PYTHON=%VENV_DIR%\Scripts\python.exe"
set "PROFILES_DIR=%ROOT_DIR%profiles"

:: 1. Kiem tra Python
if exist "%VENV_PYTHON%" (
    echo [OK] Python Venv: "%VENV_PYTHON%"
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

:: 2. Kiem tra va cai dat dependencies neu can
if exist "%ROOT_DIR%requirements.txt" (
    echo [INFO] Dang kiem tra dependencies...
    "%VENV_PYTHON%" -m pip install -q -r "%ROOT_DIR%requirements.txt"
    echo [OK] Dependencies da dong bo.
)

:: 3. Tim Ungoogled Chromium executable
set "CHROME_EXE="
if exist "%ROOT_DIR%Ungoogled Chromium\chrome.exe" (
    set "CHROME_EXE=%ROOT_DIR%Ungoogled Chromium\chrome.exe"
) else if exist "%ROOT_DIR%Ungoogled Chromium\chromium.exe" (
    set "CHROME_EXE=%ROOT_DIR%Ungoogled Chromium\chromium.exe"
) else (
    :: Tim de quy neu nam trong thu muc con
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

:: 4. Khoi dong FastAPI Server (Uvicorn) o cua so rieng biet
echo.
echo [INFO] Dang khoi dong FastAPI Server tai http://127.0.0.1:8000 ...
start "FastAPI Server (VSA2)" cmd /k "chcp 65001 >nul && title FastAPI Server (VSA2) && cd /d "%ROOT_DIR%" && "%VENV_PYTHON%" -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload"

:: 5. Cho server khoi dong va san sang
echo [INFO] Dang cho server khoi dong...
set /a ATTEMPTS=0
:WAIT_SERVER
set /a ATTEMPTS+=1
timeout /t 1 /nobreak >nul

:: Kiem tra port 8000 bang PowerShell (chinh xac va khong bi loi gia)
powershell -Command "$t = New-Object Net.Sockets.TcpClient; try { $t.Connect('127.0.0.1', 8000); $t.Close(); exit 0 } catch { exit 1 }" >nul 2>&1
if %errorlevel% equ 0 (
    echo [OK] FastAPI Server da hoat dong tai http://127.0.0.1:8000!
    goto LAUNCH_BROWSER
)

if %ATTEMPTS% geq 20 (
    echo [CANH BAO] Server mat nhieu thoi gian de khoi dong. Van se mo Chromium...
    goto LAUNCH_BROWSER
)

goto WAIT_SERVER

:LAUNCH_BROWSER
echo.
if defined CHROME_EXE (
    if exist "%CHROME_EXE%" (
        echo [OK] Tim thay Ungoogled Chromium: "%CHROME_EXE%"
        echo [INFO] Profile luu tai: "%PROFILES_DIR%"
        echo [INFO] Dang mo 2 tab: http://127.0.0.1:8000 va https://www.facebook.com ...
        start "" "%CHROME_EXE%" --user-data-dir="%PROFILES_DIR%" --no-first-run --no-default-browser-check "http://127.0.0.1:8000" "https://www.facebook.com"
        goto FINISH
    )
)

:: Neu khong tim thay Ungoogled Chromium trong thu muc du an, thu tim chrome hoac mo trinh duyet mac dinh
echo [CANH BAO] Khong tim thay chrome.exe trong thu muc 'Ungoogled Chromium'.
echo Dang tim tren he thong...
set "FALLBACK_CHROME="
if exist "%ProgramFiles%\Google\Chrome\Application\chrome.exe" set "FALLBACK_CHROME=%ProgramFiles%\Google\Chrome\Application\chrome.exe"
if exist "%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe" set "FALLBACK_CHROME=%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"
if exist "%LocalAppData%\Google\Chrome\Application\chrome.exe" set "FALLBACK_CHROME=%LocalAppData%\Google\Chrome\Application\chrome.exe"

if defined FALLBACK_CHROME (
    echo [INFO] Mo bang Chrome he thong voi profile: "%PROFILES_DIR%"
    start "" "%FALLBACK_CHROME%" --user-data-dir="%PROFILES_DIR%" --no-first-run "http://127.0.0.1:8000" "https://www.facebook.com"
) else (
    echo [INFO] Mo bang trinh duyet mac dinh...
    start http://127.0.0.1:8000
    start https://www.facebook.com
)

:FINISH
echo.
echo ========================================================
echo   HE THONG DA KHOI DONG THANH CONG!
echo   - FastAPI: http://127.0.0.1:8000
echo   - Profile: %PROFILES_DIR%
echo   Ban co the dong cua so nay hoac giu de theo doi.
echo ========================================================
timeout /t 5
