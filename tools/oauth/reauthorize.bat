@echo off
setlocal
cd /d "%~dp0\..\.."
call uv run uvicorn app.oauth_server:app --host 127.0.0.1 --port 8000
pause
