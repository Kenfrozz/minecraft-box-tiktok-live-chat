@echo off
setlocal
cd /d "%~dp0"
echo ===============================================
echo  TikTok Box - Dashboard baslatiliyor
echo  http://127.0.0.1:5010
echo ===============================================
call venv\Scripts\activate.bat
python dashboard.py
pause
