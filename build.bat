@echo off
cd /d %~dp0
C:\Python314\python.exe -m PyInstaller --noconfirm --onefile --windowed --name IQBench ^
  --hidden-import PySide6.QtSvg main.py
echo.
echo 构建完成: dist\IQBench.exe
pause
