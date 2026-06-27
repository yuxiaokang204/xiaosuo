@echo off
set PYTHON_PATH=C:\Users\User\AppData\Local\Programs\Python\Python312
set PATH=%PYTHON_PATH%;%PYTHON_PATH%\Scripts;%PATH%
echo Installing Python dependencies...
pip install -e .
echo Done.
