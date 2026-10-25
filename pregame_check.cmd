@echo off
rem P71: reminder-only pregame check (see src/pregame_check.py). Alerts when a game is at T-4h or T-90m with no
rem stored prediction. Run every 15 minutes by Windows Task Scheduler as
rem 'conhost.exe --headless cmd.exe /c pregame_check.cmd'. Every run writes a start and an exit line.
cd /d "%~dp0"
if not exist "data\pregame_check" mkdir "data\pregame_check"
echo %date% %time% start (user %USERNAME%, session %SESSIONNAME%) >> "data\pregame_check\task.log"
python -m src.pregame_check >> "data\pregame_check\task.log" 2>&1
echo %date% %time% exit %errorlevel% >> "data\pregame_check\task.log"
