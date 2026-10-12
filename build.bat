@echo off
cd /d %~dp0
C:\Python314\python.exe -m PyInstaller --noconfirm --onedir --windowed --name IQBench ^
  --hidden-import PySide6.QtSvg main.py
echo.
echo 构建完成: dist\IQBench\IQBench.exe  (onedir模式, 秒级启动)
pause
