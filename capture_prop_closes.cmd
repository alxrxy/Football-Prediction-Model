@echo off
rem P61: passive capture of Sportradar player-prop lines around kickoff (see src/capture_prop_closes.py).
rem Run every 15 minutes by Windows Task Scheduler; makes no call unless a game is at a checkpoint.
cd /d "%~dp0"
if not exist "data\prop_closes" mkdir "data\prop_closes"
python -m src.capture_prop_closes >> "data\prop_closes\task.log" 2>&1
