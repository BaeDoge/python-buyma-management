@echo off
setlocal
cd /d %~dp0
call uv run payload_migration.py
pause
