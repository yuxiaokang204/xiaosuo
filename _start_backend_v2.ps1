$env:PYTHON_PATH = "C:\Users\User\AppData\Local\Programs\Python\Python312"
$env:PATH = "$env:PYTHON_PATH;$env:PYTHON_PATH\Scripts;$env:PATH"
Write-Host "Starting backend server directly with uvicorn on http://localhost:8080..."
& uvicorn "src.backend.main:app" --host "0.0.0.0" --port 8080 --loop asyncio
