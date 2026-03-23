@echo off
setlocal

set PYTHON_EXE=C:\Users\Admin Data\PycharmProjects\pythonProject1\github\venv\.venv\Scripts\python.exe
set SCRIPT_DIR=%~dp0

"%PYTHON_EXE%" -m PyInstaller ^
  --noconfirm ^
  --onefile ^
  --name check_polygon_delop ^
  --add-data "%SCRIPT_DIR%check_polygon_delop.py;." ^
  --hidden-import streamlit.web.cli ^
  "%SCRIPT_DIR%check_polygon_delop_exe.py"

endlocal
