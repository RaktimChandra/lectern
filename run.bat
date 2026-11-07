@echo off
REM Start Lectern on http://localhost:8000
setlocal
cd /d "%~dp0backend"
if not exist .venv\Scripts\uvicorn.exe (echo Run setup.bat first. & exit /b 1)
echo Lectern is starting at http://localhost:8000  (Ctrl+C to stop)
.venv\Scripts\uvicorn lectern.main:app --port 8000
