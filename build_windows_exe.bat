@echo off
setlocal
cd /d "%~dp0"

echo Building Windows onedir package. Run this on Windows.
call uv run --with pyinstaller pyinstaller --noconfirm --clean --paths app\src --paths app --onedir --name BuymaPriceManager --collect-all playwright --collect-all greenlet --collect-all pandas --collect-all gspread --collect-all google.auth --collect-all yaml buyma_price_manager.py
if errorlevel 1 goto fail
if not exist dist\BuymaPriceManager mkdir dist\BuymaPriceManager
if exist config.example.yaml copy /Y config.example.yaml dist\BuymaPriceManager\config.example.yaml >nul
if not exist dist\BuymaPriceManager\data mkdir dist\BuymaPriceManager\data
if not exist dist\BuymaPriceManager\secrets mkdir dist\BuymaPriceManager\secrets
echo.
echo Build complete: dist\BuymaPriceManager\BuymaPriceManager.exe
echo Copy config.example.yaml to config.yaml, then configure your own credentials and files.
echo Do NOT share tokens or service-account JSON files.
pause
exit /b 0
:fail
echo Build failed. Review the error above.
pause
exit /b 1
