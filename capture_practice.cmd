@echo off
rem P47: nightly capture of the nflverse injury file (see src/capture_practice.py).
rem Run by Windows Task Scheduler; output appended to data\practice_snapshots\task.log.
cd /d "%~dp0"
python -m src.capture_practice >> "data\practice_snapshots\task.log" 2>&1
