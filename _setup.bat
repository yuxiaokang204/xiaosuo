@echo off
setlocal

:: Set Python path
set PYTHON_PATH=C:\Users\User\AppData\Local\Programs\Python\Python312
set PYTHONPATH=%PYTHON_PATH%;%PYTHON_PATH%\DLLs;%PYTHON_PATH%\Lib;%PYTHON_PATH%\Scripts

:: Set Node.js path
set NODE_PATH=C:\Program Files\nodejs
set PATH=%NODE_PATH%;%PYTHON_PATH%;%PYTHON_PATH%\DLLs;%PYTHON_PATH%\Lib;%PYTHON_PATH%\Scripts;%PATH%

echo ========================================
echo Environment Setup
echo ========================================
call python --version
call node --version
call npm --version
echo.
echo ========================================
echo Installing Python dependencies...
echo ========================================
call python -m pip install --upgrade pip
call pip install -e .
echo.
echo ========================================
echo Installing npm dependencies...
echo ========================================
call npm install
echo.
echo ========================================
echo All dependencies installed!
echo ========================================
pause
