@echo off
setlocal
cd /d %~dp0
echo WARNING: This sends real BUYMA product update requests.
set /p CONFIRM=Type APPLY to continue: 
if /I not "%%CONFIRM%%"=="APPLY" (echo Cancelled.& pause & exit /b 1)
call uv run refresh_prices.py --apply --price-delta 10 --max-change 100 %%*
pause
