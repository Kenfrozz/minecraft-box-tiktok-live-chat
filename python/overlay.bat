@echo off
setlocal
cd /d "%~dp0"
echo ===============================================
echo  TikTok Box - OBS Overlay server (standalone)
echo  http://127.0.0.1:5011
echo ===============================================
call venv\Scripts\activate.bat
python overlay_server.py
pause
