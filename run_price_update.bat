@echo off
setlocal
cd /d %~dp0
call uv run refresh_prices.py --price-delta 10 --max-change 100 %%*
pause
