$env:NODE_PATH = "C:\Program Files\nodejs"
$env:PATH = "$env:NODE_PATH;$env:PATH"
Write-Host "Starting frontend dev server on http://localhost:8080..."
npm run dev
