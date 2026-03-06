@echo off
title 🔧 Build Excel Tool (.EXE)
echo ===========================================
echo   🧰 BUILDING EXCEL TOOL TO EXE FILE
echo ===========================================
echo.

REM ============================================
REM 1️⃣ Kích hoạt môi trường ảo (venv)
REM ============================================
call "C:\Users\Admin Data\PycharmProjects\pythonProject1\venv\Scripts\activate"

REM ============================================
REM 2️⃣ Xóa thư mục build/dist cũ (nếu có)
REM ============================================
rmdir /s /q "C:\Users\Admin Data\PycharmProjects\pythonProject1\venv\visa\build" 2>nul
rmdir /s /q "C:\Users\Admin Data\PycharmProjects\pythonProject1\venv\visa\dist" 2>nul

REM ============================================
REM 3️⃣ Đóng gói file ExcelTool.py thành .exe
REM ============================================
pyinstaller --noconfirm --onefile --icon=icon.ico --name "Excel_Tool" "C:\Users\Admin Data\PycharmProjects\pythonProject1\venv\visa\ExcelTool.py"

REM ============================================
REM 4️⃣ Thông báo hoàn tất
REM ============================================
echo.
echo ✅ Build hoàn tất!
echo 📁 File EXE nằm trong:
echo    %CD%\dist\Excel_Tool.exe
echo.
pause
