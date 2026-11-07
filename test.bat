@echo off
REM Run the offline test suites (no keys needed)
setlocal
cd /d "%~dp0backend"
.venv\Scripts\python -m pytest -q || exit /b 1
cd ..\frontend
call npx tsc --noEmit || exit /b 1
call npx vitest run
