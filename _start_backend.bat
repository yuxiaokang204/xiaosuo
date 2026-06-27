@echo off
set PYTHON_PATH=C:\Users\User\AppData\Local\Programs\Python\Python312
set PATH=%PYTHON_PATH%;%PYTHON_PATH%\Scripts;%PATH%
echo Starting backend server on http://localhost:8080...
python run.py
