@echo off
chcp 65001 >nul
title Dong bo code len GitHub - Dat VSA

echo [INFO] Dang kiem tra thay đổi code...
git add .

set /p msg="Nhap noi dung commit (Enter de dung mac dinh 'Update code'): "
if "%msg%"=="" set msg=Update code

git commit -m "%msg%"
git push origin main

echo.
echo ========================================================
echo        DA DONG BO CODE LEN GITHUB THANH CONG!
echo ========================================================
pause