@echo off
setlocal
cd /d "%~dp0"

echo Building BESTSHIP Price Manager (Windows onedir).
call uv run --with pyinstaller pyinstaller --noconfirm --clean --paths app\src --onedir --name BestShipPriceManager --collect-all playwright --collect-all greenlet --collect-all pandas --collect-all gspread --collect-all google.auth --collect-all yaml buyma_price_manager.py
if errorlevel 1 goto fail

if not exist dist\BestShipPriceManager mkdir dist\BestShipPriceManager
if exist config.example.yaml copy /Y config.example.yaml dist\BestShipPriceManager\config.example.yaml >nul
if not exist dist\BestShipPriceManager\data mkdir dist\BestShipPriceManager\data
if not exist dist\BestShipPriceManager\secrets mkdir dist\BestShipPriceManager\secrets

echo.
echo Build complete: dist\BestShipPriceManager\BestShipPriceManager.exe
echo Create config.yaml from config.example.yaml and place BESTSHIP's own OAuth token,
echo Google service-account key, and validated product payloads beside the executable.
echo Never include .env, tokens.json, service-account JSON, or product data in the distributed package.
pause
exit /b 0

:fail
echo Build failed. Review the error above.
pause
exit /b 1
