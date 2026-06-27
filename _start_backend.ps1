$env:PYTHON_PATH = "C:\Users\User\AppData\Local\Programs\Python\Python312"
$env:PATH = "$env:PYTHON_PATH;$env:PYTHON_PATH\Scripts;$env:PATH"
Write-Host "Starting backend server on http://localhost:8080..."
& python run.py
