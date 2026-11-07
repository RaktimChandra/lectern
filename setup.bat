@echo off
REM Lectern setup for Windows: creates the Python environment, installs everything and builds the interface.
setlocal
cd /d "%~dp0"
where python >nul 2>nul || (echo Python 3.11+ is not on PATH. Install it from python.org and tick "Add to PATH". & exit /b 1)
where npm >nul 2>nul || (echo Node.js 20+ is not on PATH. Install it from nodejs.org. & exit /b 1)
if not exist .env (copy .env.example .env >nul & echo Created .env from .env.example. Add your API keys to it.)
if not exist backend\.venv python -m venv backend\.venv || exit /b 1
backend\.venv\Scripts\python -m pip install --upgrade pip >nul
backend\.venv\Scripts\python -m pip install -e ".\backend[dev]" || exit /b 1
pushd frontend
call npm install --no-audit --no-fund || (popd & exit /b 1)
call npm run build || (popd & exit /b 1)
popd
echo.
echo Setup complete. Add your keys to .env, then run run.bat
