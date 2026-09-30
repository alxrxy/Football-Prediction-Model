@echo off
rem P61: passive capture of Sportradar player-prop lines around kickoff (see src/capture_prop_closes.py).
rem Run every 15 minutes by Windows Task Scheduler through capture_prop_closes.vbs (no console window);
rem makes no call unless a game is at a checkpoint. Every run writes a start and an exit line:
rem a start with no exit line means the run was killed.
cd /d "%~dp0"
if not exist "data\prop_closes" mkdir "data\prop_closes"
echo %date% %time% start (user %USERNAME%, session %SESSIONNAME%) >> "data\prop_closes\task.log"
python -m src.capture_prop_closes >> "data\prop_closes\task.log" 2>&1
echo %date% %time% exit %errorlevel% >> "data\prop_closes\task.log"
