@echo off
set PYTHON_PATH=C:\Users\User\AppData\Local\Programs\Python\Python312
set PATH=%PYTHON_PATH%;%PYTHON_PATH%\Scripts;%PATH%
echo Starting backend server on http://localhost:8080...
call python -c "import sys; sys.path.insert(0, '.'); from src.backend.main import app; import uvicorn; uvicorn.run(app, host='0.0.0.0', port=8080)"
