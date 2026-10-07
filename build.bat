@echo off
REM One-click PyInstaller build (optional). Primary run path is: streamlit run Home.py
REM Safe flags only: no --collect-all plotly (WinError 1450). Pin pyinstaller==6.22.3 in venv.

setlocal
cd /d "%~dp0"

if exist venv\Scripts\python.exe (
  set PY=venv\Scripts\python.exe
) else (
  set PY=python
)

echo.
echo === CosmosBankDemo :: PyInstaller --onedir ===
echo EDUCATIONAL SIMULATION — fictional banks/cards/transactions only.
echo.

"%PY%" -m pip install -r requirements.txt
if errorlevel 1 (
  echo [ERROR] pip install failed. Use Python 3.10+ in a clean venv.
  exit /b 1
)

echo Generating architecture PNG (offline matplotlib)...
"%PY%" assets\generate_architecture.py

echo Building...
"%PY%" -m PyInstaller --noconfirm --clean --onedir --windowed --name CosmosBankDemo ^
  --hidden-import plotly --collect-data plotly --collect-data streamlit ^
  --add-data "core;core" --add-data "pages;pages" --add-data "assets;assets" ^
  Home.py

if errorlevel 1 (
  echo [ERROR] PyInstaller failed. Primary demo path remains: streamlit run Home.py
  exit /b 1
)

echo.
echo Build complete. Run: dist\CosmosBankDemo\CosmosBankDemo.exe
echo.
endlocal
