@echo off
setlocal
cd /d "%~dp0"

echo ============================================================
echo BUYMA application build
echo  - BUYMA-Manager.exe   : manual menu
echo  - BUYMA-Scheduler.exe: always-on scheduled price runner
echo ============================================================

where uv >nul 2>nul
if errorlevel 1 (
    echo [ERROR] uv was not found. Install uv first.
    exit /b 1
)

echo.
echo [1/4] Syncing project dependencies...
uv sync
if errorlevel 1 goto :failed

echo.
echo [2/4] Building BUYMA-Manager.exe...
uv run --with pyinstaller pyinstaller --noconfirm --clean --onefile --console ^
  --name BUYMA-Manager ^
  --paths app --paths app/src ^
  --collect-all playwright ^
  --collect-submodules gspread ^
  --collect-submodules google.auth ^
  --collect-submodules google.oauth2 ^
  --distpath dist --workpath build/pyinstaller-manager --specpath build/spec-manager ^
  buyma_price_manager.py
if errorlevel 1 goto :failed

echo.
echo [3/4] Building BUYMA-Scheduler.exe...
uv run --with pyinstaller pyinstaller --noconfirm --clean --onefile --console ^
  --name BUYMA-Scheduler ^
  --paths app --paths app/src ^
  --collect-all playwright ^
  --collect-submodules gspread ^
  --collect-submodules google.auth ^
  --collect-submodules google.oauth2 ^
  --distpath dist --workpath build/pyinstaller-scheduler --specpath build/spec-scheduler ^
  buyma_price_scheduler.py
if errorlevel 1 goto :failed

echo.
echo [4/4] Preparing configuration examples...
if not exist "dist\config.yaml" copy "config.example.yaml" "dist\config.yaml" >nul
if not exist "dist\.env.example" copy ".env.example" "dist\.env.example" >nul
if not exist "dist\secrets" mkdir "dist\secrets"
if not exist "dist\data" mkdir "dist\data"
if not exist "dist\logs" mkdir "dist\logs"
if not exist "dist\reports" mkdir "dist\reports"

echo.
echo Build completed.
echo Output:
echo   dist\BUYMA-Manager.exe
echo   dist\BUYMA-Scheduler.exe
echo.
echo Before running, place config.yaml, .env, and these files beside the EXE:
echo   secrets\service_account.json
echo   secrets\tokens.json
echo Do not upload your real .env or secrets to GitHub.
exit /b 0

:failed
echo.
echo [ERROR] Build failed. Read the message above and fix the reported issue.
exit /b 1