@echo off
rem P33: read-only probe of ESPN inactive lists (see src/probe_inactives.py).
rem Run every 15 minutes by Windows Task Scheduler as 'conhost.exe --headless cmd.exe /c probe_inactives.cmd'
rem (no console window; a wscript .vbs wrapper hung suspended under the scheduler, 9/30);
rem exits at once unless a game is within 3 h. Every run writes a start and an exit line:
rem a start with no exit line means the run was killed.
cd /d "%~dp0"
if not exist "data\inactives_probe" mkdir "data\inactives_probe"
echo %date% %time% start (user %USERNAME%, session %SESSIONNAME%) >> "data\inactives_probe\task.log"
python -m src.probe_inactives >> "data\inactives_probe\task.log" 2>&1
echo %date% %time% exit %errorlevel% >> "data\inactives_probe\task.log"
