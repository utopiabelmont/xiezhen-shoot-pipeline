@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist "%~dp0job.ps1" copy "%~dp0scripts\job.example.ps1" "%~dp0job.ps1" >nul
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0job.ps1"
