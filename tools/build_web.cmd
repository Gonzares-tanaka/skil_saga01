@echo off
cd /d "%~dp0.."
if not exist ".venv\Scripts\python.exe" call setup.cmd
if not exist ".venv\Scripts\python.exe" exit /b 1
".venv\Scripts\python.exe" tools\build_web.py
if errorlevel 1 pause
