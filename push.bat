@echo off
chcp 65001 >nul
title DAY CODE LEN GITHUB - MORODAT1989/VSA2
color 0B

echo ========================================================
echo             DONG BO & DAY CODE LEN GITHUB
echo ========================================================
echo.

set "ROOT_DIR=%~dp0"
cd /d "%ROOT_DIR%"

:: 1. Kiem tra Git
where git >nul 2>&1
if %errorlevel% neq 0 (
    echo [LOI] Khong tim thay Git tren he thong!
    echo Vui long cai dat Git tai https://git-scm.com/
    pause
    exit /b 1
)

:: 2. Kiem tra xem da khoi tao git chua
if not exist ".git" (
    echo [INFO] Khoi tao Git repository...
    git init
    git branch -M main
    git remote add origin https://github.com/morodat1989/vsa2.git
)

:: 3. Kiem tra remote
git remote get-url origin >nul 2>&1
if %errorlevel% neq 0 (
    echo [INFO] Dang thiet lap remote origin...
    git remote add origin https://github.com/morodat1989/vsa2.git
)

:: 4. Kiem tra trang thai thay doi
echo [INFO] Trang thai cac file thay doi:
git status -s
echo.

:: 5. Nhap commit message hoac dung mac dinh
set /p COMMIT_MSG="Nhap noi dung commit (Nhan Enter de dung mac dinh): "
if "%COMMIT_MSG%"=="" (
    set "COMMIT_MSG=Cap nhat start.bat, fix loi mo Ungoogled Chromium voi 2 tab va profiles"
)

:: 6. Git Add & Commit
echo.
echo [INFO] Dang them file vao git...
git add -A

echo [INFO] Dang commit voi message: "%COMMIT_MSG%"...
git commit -m "%COMMIT_MSG%"

:: 7. Push len Github
echo.
echo [INFO] Dang day code len GitHub (morodat1989/vsa2)...

:: Lay ten branch hien tai
for /f "delims=" %%B in ('git rev-parse --abbrev-ref HEAD 2^>nul') do set "CURRENT_BRANCH=%%B"
if "%CURRENT_BRANCH%"=="" set "CURRENT_BRANCH=main"

git push -u origin %CURRENT_BRANCH%

if %errorlevel% equ 0 (
    echo.
    echo ========================================================
    echo   [THANH CONG] Code da duoc day len GitHub thanh cong!
    echo   Repo: https://github.com/morodat1989/vsa2
    echo   Branch: %CURRENT_BRANCH%
    echo ========================================================
) else (
    echo.
    echo [CANH BAO] Khong the day code truc tiep (co the can dang nhap hoac pull truoc).
    echo Thu chay: git pull origin %CURRENT_BRANCH% --rebase
    git pull origin %CURRENT_BRANCH% --rebase
    git push origin %CURRENT_BRANCH%
)

echo.
pause
