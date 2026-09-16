@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" call setup.cmd
if not exist ".venv\Scripts\python.exe" exit /b 1
set "rpg_resource=game.pyxres"
if "%~1"=="2" set "rpg_resource=area2.pyxres"
if "%~1"=="3" set "rpg_resource=area3.pyxres"
if not exist "%rpg_resource%" goto fail
".venv\Scripts\python.exe" -m pyxel edit "%rpg_resource%"
if errorlevel 1 goto fail
exit /b 0
:fail
pause
exit /b 1
