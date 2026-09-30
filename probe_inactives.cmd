@echo off
rem P33: read-only probe of ESPN inactive lists (see src/probe_inactives.py).
rem Run every 15 minutes by Windows Task Scheduler; exits at once unless a game is within 3 h.
cd /d "%~dp0"
if not exist "data\inactives_probe" mkdir "data\inactives_probe"
python -m src.probe_inactives >> "data\inactives_probe\task.log" 2>&1
