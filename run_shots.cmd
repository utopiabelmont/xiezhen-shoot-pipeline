@echo off
chcp 65001 >nul
cd /d "%~dp0"
set "PYTHONUTF8=1"
".venv\Scripts\python.exe" run_shots.py > run_shots_log.txt 2>&1
echo done > run_shots_done.txt
