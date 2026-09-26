@echo off
setlocal EnableExtensions EnableDelayedExpansion

title HE THONG QUAN LY FACEBOOK TOOL - ARCHITECTURE V2

:: ========================================================
:: CAU HINH
:: ========================================================

set "BASE_PORT=9222"
set "ROOT=%~dp0"
set "PROFILE_ROOT=%~dp0profiles"
set "VENV=%~dp0venv"
set "BROWSER_PATH=%~dp0Ungoogled Chromium\app\chrome.exe"
set "SERVER_STARTED=0"

:: ========================================================
:: MENU
:: ========================================================

:MENU
cls

echo ========================================================
echo        HE THONG QUAN LY FACEBOOK TOOL - PROFILES
echo ========================================================
echo.

if not exist "%PROFILE_ROOT%" (
    mkdir "%PROFILE_ROOT%"

    if errorlevel 1 (
        echo [LOI] Khong the tao thu muc Profiles:
        echo %PROFILE_ROOT%
        pause
        exit /b 1
    )
)

set "COUNT=0"

echo Danh sach Profile hien co:
echo.

for /f "delims=" %%I in ('dir /b /ad "%PROFILE_ROOT%" 2^>nul') do (
    set /a COUNT+=1

    set "PROF_!COUNT!=%%I"

    set /a CURRENT_PORT=BASE_PORT + COUNT - 1
    set "PROF_PORT_!COUNT!=!CURRENT_PORT!"

    echo   [!COUNT!] %%I  ----^> [CDP Port: !CURRENT_PORT!]
)

if !COUNT! EQU 0 (
    echo   (Chua co Profile nao duoc tao)
)

echo.

set /a NEW_OPT=COUNT+1

echo   [!NEW_OPT!] Tao Profile moi
echo   [0] Thoat
echo.

echo ========================================================

set "CHOICE="
set /p "CHOICE=Nhap lua chon cua ban: "

if not defined CHOICE (
    goto MENU
)

if "!CHOICE!"=="0" (
    exit /b 0
)

if "!CHOICE!"=="!NEW_OPT!" (
    goto CREATE_PROFILE
)

:: ========================================================
:: TIM PROFILE DUOC CHON
:: ========================================================

set "SELECTED_PROFILE="
set "SELECTED_PORT="

for /l %%G in (1,1,!COUNT!) do (
    if "!CHOICE!"=="%%G" (
        set "SELECTED_PROFILE=!PROF_%%G!"

        set /a SELECTED_PORT=BASE_PORT + %%G - 1
    )
)

if defined SELECTED_PROFILE (
    goto START_SERVER_FOR_PROFILE
)

echo.
echo [LOI] Lua chon khong hop le!
echo Lua chon vua nhap: !CHOICE!
echo.
pause
goto MENU


:: ========================================================
:: TAO PROFILE
:: ========================================================

:CREATE_PROFILE

cls

echo ========================================================
echo                   TAO PROFILE MOI
echo ========================================================
echo.

set "NEW_NAME="

set /p "NEW_NAME=Nhap ten Profile moi (VD: DatVSA2): "

if not defined NEW_NAME (
    goto MENU
)

if exist "%PROFILE_ROOT%\!NEW_NAME!\" (
    echo.
    echo [LOI] Profile "!NEW_NAME!" da ton tai!
    echo Vui long chon ten khac.
    echo.
    pause
    goto CREATE_PROFILE
)

mkdir "%PROFILE_ROOT%\!NEW_NAME!"

if errorlevel 1 (
    echo.
    echo [LOI] Khong the tao Profile "!NEW_NAME!".
    echo Duong dan:
    echo "%PROFILE_ROOT%\!NEW_NAME!"
    echo.
    pause
    goto MENU
)

echo.
echo [OK] Da tao Profile: !NEW_NAME!
echo.

timeout /t 2 /nobreak >nul
goto MENU


:: ========================================================
:: KHOI DONG FASTAPI MOT LAN DUY NHAT
:: ========================================================

:START_SERVER_FOR_PROFILE

if "!SERVER_STARTED!"=="1" (
    goto LAUNCH_BROWSER
)

cls

echo ========================================================
echo               KHOI DONG FASTAPI SERVER
echo ========================================================
echo.

:: --------------------------------------------------------
:: Kiem tra Python
:: --------------------------------------------------------

set "PYTHON_CMD="

py --version >nul 2>&1

if not errorlevel 1 (
    set "PYTHON_CMD=py"
)

if not defined PYTHON_CMD (
    python --version >nul 2>&1

    if not errorlevel 1 (
        set "PYTHON_CMD=python"
    )
)

if not defined PYTHON_CMD (
    echo [LOI CRITICAL]
    echo.
    echo Khong tim thay Python hoac Python Launcher ^(py^)!
    echo.
    echo Hay cai Python va chon:
    echo.
    echo     Add Python to PATH
    echo.
    pause
    goto MENU
)

echo [OK] Python: !PYTHON_CMD!

:: --------------------------------------------------------
:: Tao VENV
:: --------------------------------------------------------

if not exist "%VENV%\Scripts\python.exe" (
    echo.
    echo [INFO] Dang tao Python Virtual Environment...
    echo.

    !PYTHON_CMD! -m venv "%VENV%"

    if errorlevel 1 (
        echo.
        echo [LOI] Tao venv that bai!
        echo Error Level: !errorlevel!
        echo.
        pause
        goto MENU
    )

    echo [OK] Tao venv thanh cong.
)

:: --------------------------------------------------------
:: Kiem tra requirements
:: --------------------------------------------------------

if not exist "%ROOT%requirements.txt" (
    echo.
    echo [LOI] Khong tim thay file:
    echo "%ROOT%requirements.txt"
    echo.
    pause
    goto MENU
)

set "NEED_INSTALL=0"

if not exist "%VENV%\requirements.installed" (
    set "NEED_INSTALL=1"
) else (
    fc /b "%ROOT%requirements.txt" "%VENV%\requirements.installed" >nul 2>&1

    if errorlevel 1 (
        set "NEED_INSTALL=1"
    )
)

:: --------------------------------------------------------
:: Cai thu vien
:: --------------------------------------------------------

if "!NEED_INSTALL!"=="1" (
    echo.
    echo [INFO] Dang cai/cap nhat dependencies...
    echo.

    "%VENV%\Scripts\python.exe" -m pip install -r "%ROOT%requirements.txt"

    if errorlevel 1 (
        echo.
        echo [LOI] pip install that bai!
        echo Error Level: !errorlevel!
        echo.
        echo File requirements:
        echo "%ROOT%requirements.txt"
        echo.
        pause
        goto MENU
    )

    copy /y "%ROOT%requirements.txt" "%VENV%\requirements.installed" >nul

    echo.
    echo [OK] Dependencies da dong bo.
) else (
    echo [OK] Dependencies da duoc dong bo.
)

:: --------------------------------------------------------
:: Kiem tra main.py
:: --------------------------------------------------------

if not exist "%ROOT%main.py" (
    echo.
    echo [LOI] Khong tim thay file:
    echo "%ROOT%main.py"
    echo.
    pause
    goto MENU
)

:: --------------------------------------------------------
:: Kiem tra FastAPI da chay tren port 8000 chua
:: --------------------------------------------------------

echo.
echo [INFO] Dang kiem tra FastAPI Server...

powershell -NoProfile -ExecutionPolicy Bypass -Command "$client = New-Object Net.Sockets.TcpClient; try { $client.Connect('127.0.0.1',8000); exit 0 } catch { exit 1 } finally { $client.Dispose() }" >nul 2>&1

if not errorlevel 1 (
    echo [OK] FastAPI Server dang chay tren port 8000.
    set "SERVER_STARTED=1"
    goto LAUNCH_BROWSER
)

:: --------------------------------------------------------
:: Khoi dong FastAPI
:: --------------------------------------------------------

echo.
echo [INFO] Dang khoi dong FastAPI Server...
echo [INFO] URL: http://127.0.0.1:8000/
echo.

start "" /b /d "%ROOT%" "%VENV%\Scripts\python.exe" -m uvicorn main:app --reload --host 127.0.0.1 --port 8000

if errorlevel 1 (
    echo.
    echo [LOI] Khong the khoi dong FastAPI Server!
    echo Error Level: !errorlevel!
    echo.
    echo Python:
    echo "%VENV%\Scripts\python.exe"
    echo.
    echo Root:
    echo "%ROOT%"
    echo.
    echo Port: 8000
    echo.
    pause
    goto MENU
)

set "SERVER_STARTED=1"

timeout /t 2 /nobreak >nul


:: ========================================================
:: KHOI DONG CHROMIUM
:: ========================================================

:LAUNCH_BROWSER

cls

set "PROFILE_DIR=%PROFILE_ROOT%\!SELECTED_PROFILE!"

echo ========================================================
echo       MO DASHBOARD VA FACEBOOK TRONG CUNG MOT CUA SO
echo ========================================================
echo.

echo Profile  : !SELECTED_PROFILE!
echo CDP Port : !SELECTED_PORT!
echo Dashboard: http://127.0.0.1:8000/
echo Facebook  : https://www.facebook.com
echo.

if not exist "!BROWSER_PATH!" (
    echo [LOI] Khong tim thay Chromium:
    echo.
    echo "!BROWSER_PATH!"
    echo.
    pause
    goto MENU
)

if not exist "!PROFILE_DIR!" (
    mkdir "!PROFILE_DIR!"

    if errorlevel 1 (
        echo.
        echo [LOI] Khong the tao Profile Directory:
        echo "!PROFILE_DIR!"
        echo.
        pause
        goto MENU
    )
)

echo [INFO] Dang khoi dong Chromium...
echo.

echo [DEBUG] Browser Path:
echo "!BROWSER_PATH!"

echo [DEBUG] Profile Directory:
echo "!PROFILE_DIR!"

echo [DEBUG] CDP Port:
echo !SELECTED_PORT!

echo.

start "" "!BROWSER_PATH!" ^
    --remote-debugging-port=!SELECTED_PORT! ^
    --user-data-dir="!PROFILE_DIR!" ^
    --profile-directory="Default" ^
    --disable-features=ProfilePicker ^
    --no-first-run ^
    --no-default-browser-check ^
    "http://127.0.0.1:8000/" ^
    "https://www.facebook.com"

if errorlevel 1 (
    echo.
    echo [LOI] Khong the khoi dong Chromium!
    echo Error Level: !errorlevel!
    echo.
    echo Browser Path:
    echo "!BROWSER_PATH!"
    echo.
    echo Profile Directory:
    echo "!PROFILE_DIR!"
    echo.
    echo CDP Port:
    echo !SELECTED_PORT!
    echo.
    pause
    goto MENU
)

echo.
echo [OK] Da mo Dashboard va Facebook.
echo [INFO] Hai URL duoc truyen vao cung mot cua so Chromium.
echo [INFO] CDP Port: !SELECTED_PORT!
echo.

timeout /t 2 /nobreak >nul
goto MENU