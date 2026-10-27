@echo off
setlocal
cd /d %~dp0
call uv run python app\ngrok_tunnel.py
pause
