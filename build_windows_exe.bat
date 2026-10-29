@echo off
setlocal
cd /d %~dp0

echo Building Windows onedir package. Run this on Windows.
call uv run --with pyinstaller pyinstaller --noconfirm --clean --paths app\src --onedir --name BuymaPriceUpdater --collect-all playwright --collect-all greenlet --collect-all pandas --collect-all gspread --collect-all google.auth --collect-all yaml refresh_prices.py
if errorlevel 1 goto fail
if not exist dist\BuymaPriceUpdater mkdir dist\BuymaPriceUpdater
if exist config.example.yaml copy /Y config.example.yaml dist\BuymaPriceUpdater\config.example.yaml >nul
if not exist dist\BuymaPriceUpdater\data mkdir dist\BuymaPriceUpdater\data
if not exist dist\BuymaPriceUpdater\secrets mkdir dist\BuymaPriceUpdater\secrets
echo.
echo Build complete: dist\BuymaPriceUpdater\BuymaPriceUpdater.exe
echo Copy config.example.yaml to config.yaml, then configure your own credentials and files.
echo Do NOT share tokens or service-account JSON files.
pause
exit /b 0
:fail
echo Build failed. Review the error above.
pause
exit /b 1
