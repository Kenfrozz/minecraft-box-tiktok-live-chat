@echo off
setlocal
cd /d "%~dp0"
echo ===============================================
echo  TikTok Box - Hepsi bir arada baslatici
echo   [1] Paper sunucu      (ayri pencere)
echo   [2] TikTok listener   (ayri pencere, overlay dahil)
echo   [3] Dashboard         (ayri pencere)
echo ===============================================
call venv\Scripts\activate.bat
python launch.py
pause
