@echo off
cd /d "%~dp0"
if exist "%LOCALAPPDATA%\Programs\Python\Python38\pythonw.exe" (
    start "" "%LOCALAPPDATA%\Programs\Python\Python38\pythonw.exe" main.py
) else if exist "C:\Python38\pythonw.exe" (
    start "" "C:\Python38\pythonw.exe" main.py
) else if exist "%LOCALAPPDATA%\Programs\Python\Python312\pythonw.exe" (
    start "" "%LOCALAPPDATA%\Programs\Python\Python312\pythonw.exe" main.py
) else (
    start "" pythonw.exe main.py
)
