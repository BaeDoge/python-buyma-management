@echo off
setlocal
cd /d "%~dp0"

echo Building BESTSHIP Price Manager for Windows...
if not exist config.yaml (
  echo ERROR: config.yaml is missing. Copy config.example.yaml and set the Google Sheet URL first.
  goto fail
)
if not exist secrets\tokens.json (
  echo ERROR: secrets\tokens.json is missing. Restore the already-approved BESTSHIP OAuth token.
  goto fail
)
if not exist secrets\service_account.json (
  echo ERROR: secrets\service_account.json is missing.
  goto fail
)

call uv run --with pyinstaller pyinstaller --noconfirm --clean --paths app\src --onedir --name BestShipPriceManager --collect-all playwright --collect-all greenlet --collect-all pandas --collect-all gspread --collect-all google.auth --collect-all yaml buyma_price_manager.py
if errorlevel 1 goto fail

if not exist dist\BestShipPriceManager mkdir dist\BestShipPriceManager
copy /Y config.yaml dist\BestShipPriceManager\config.yaml >nul
if not exist dist\BestShipPriceManager\secrets mkdir dist\BestShipPriceManager\secrets
if not exist dist\BestShipPriceManager\data mkdir dist\BestShipPriceManager\data
if not exist dist\BestShipPriceManager\logs mkdir dist\BestShipPriceManager\logs
if not exist dist\BestShipPriceManager\reports mkdir dist\BestShipPriceManager\reports

copy /Y secrets\tokens.json dist\BestShipPriceManager\secrets\tokens.json >nul
copy /Y secrets\service_account.json dist\BestShipPriceManager\secrets\service_account.json >nul
if exist data\buyma_products.json (
  copy /Y data\buyma_products.json dist\BestShipPriceManager\data\buyma_products.json >nul
) else (
  echo WARNING: data\buyma_products.json not found; real price updates will be skipped.
)

echo.
echo Build complete: dist\BestShipPriceManager\BestShipPriceManager.exe
echo IMPORTANT: the output folder contains BESTSHIP's OAuth token and Google key.
echo Send the whole folder only to BESTSHIP using a secure transfer method.
echo Do not commit dist/ or upload the output to a public repository.
pause
exit /b 0

:fail
echo Build stopped. Configure the required local files and retry.
pause
exit /b 1
