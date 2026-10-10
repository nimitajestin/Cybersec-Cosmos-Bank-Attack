@echo off
REM One-click PyInstaller build for the Cosmos Bank SOC educational demo.
REM Prefer --onedir so the zip stays closer to the 100 MB budget.
REM --onefile often lands at 100-150 MB because Streamlit+Plotly are bundled.

setlocal
cd /d "%~dp0"

echo.
echo === Cosmos Bank SOC Demo :: PyInstaller build ===
echo Building Cosmos Bank SOC...
echo.

python -m pip install -r requirements.txt
if errorlevel 1 (
  echo [ERROR] pip install failed. Install Python 3.10+ and retry.
  exit /b 1
)

echo.
echo Generating architecture PNG ^(offline matplotlib^)...
python assets\generate_architecture.py

echo.
echo Building --onedir windowed executable...
echo (No --collect-all plotly: Plotly's validator tree can exhaust Windows file handles.)
python -m PyInstaller --noconfirm --clean --onedir --windowed --name CosmosBankSOC ^
  --add-data "app.py;." ^
  --add-data "pages;pages" ^
  --add-data "core;core" ^
  --add-data "assets;assets" ^
  --add-data ".streamlit;.streamlit" ^
  --add-data "sample_data.sql;." ^
  --hidden-import streamlit ^
  --hidden-import streamlit.web.cli ^
  --hidden-import streamlit.runtime.scriptrunner.magic_funcs ^
  --hidden-import plotly ^
  --hidden-import plotly.express ^
  --hidden-import plotly.graph_objects ^
  --hidden-import pandas ^
  --hidden-import matplotlib ^
  --hidden-import matplotlib.backends.backend_agg ^
  --copy-metadata streamlit ^
  --collect-data streamlit ^
  --collect-submodules core ^
  launcher.py

if errorlevel 1 (
  echo [ERROR] PyInstaller failed.
  exit /b 1
)

echo.
echo Build complete.
echo Run: dist\CosmosBankSOC\CosmosBankSOC.exe
echo Zip the dist\CosmosBankSOC folder for submission ^(usually under 150 MB^).
echo If you must have a single .exe, re-run this script after changing --onedir to --onefile
echo ^(expect 100-150 MB; may exceed a 100 MB zip cap^).
echo.
endlocal
