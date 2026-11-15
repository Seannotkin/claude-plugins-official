@echo off
cd /d "%~dp0"
python -m pip install -q -r requirements.txt
python -m autoposter check || (pause & exit /b 1)
python -m autoposter run
pause
