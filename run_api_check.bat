@echo off
setlocal
cd /d %~dp0
call uv run python check_buyma_api_connection.py
pause
