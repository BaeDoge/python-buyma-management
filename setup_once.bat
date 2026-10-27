@echo off
setlocal
cd /d %~dp0
call uv run setup_once.py
pause
