@echo off
setlocal
cd /d "%~dp0"
echo ===============================================
echo  TikTok Box - listener baslatiliyor
echo ===============================================
call venv\Scripts\activate.bat
python main.py
pause
