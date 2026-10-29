@echo off
setlocal
cd /d "%~dp0"
call uv run buyma_price_manager.py
pause
