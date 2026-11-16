@echo off
setlocal EnableDelayedExpansion
title J.A.R.V.I.S. Desktop Assistant Launcher
color 0B
cd /d "%~dp0"

echo ==============================================================================
echo             J.A.R.V.I.S. Personal AI Desktop Assistant Launcher
echo ==============================================================================
echo.

:: 1. Check Python
where python >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not installed or not in PATH!
    echo Please install Python 3.10+ from python.org and add to PATH.
    pause
    exit /b 1
)

:: 2. Check & Create .venv
if exist ".venv\Scripts\python.exe" goto VENV_EXISTS
echo [*] Setting up virtual environment...
python -m venv .venv
if errorlevel 1 (
    echo [ERROR] Could not create virtual environment.
    pause
    exit /b 1
)
echo [*] Installing dependencies into .venv...
call .venv\Scripts\activate.bat
pip install -r requirements.txt
echo [*] Virtual environment setup complete.

:VENV_EXISTS
:: 3. Check & Create .env
if exist ".env" goto ENV_EXISTS
echo [*] Initializing .env configuration...
copy .env.example .env >nul

:ENV_EXISTS
:: 4. Activate Virtual Environment
call .venv\Scripts\activate.bat

:: 5. Launch Assistant
echo.
echo ==============================================================================
echo [*] Starting J.A.R.V.I.S. Assistant...
echo ==============================================================================
echo.

python main.py

if errorlevel 1 (
    echo.
    echo [ERROR] Application exited with an error.
    pause
)
