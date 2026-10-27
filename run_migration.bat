@echo off
setlocal
cd /d %~dp0
call uv run migration.py
pause
