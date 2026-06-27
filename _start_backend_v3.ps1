$env:PYTHON_PATH = "C:\Users\User\AppData\Local\Programs\Python\Python312"
$env:PATH = "$env:PYTHON_PATH;$env:PYTHON_PATH\Scripts;$env:PATH"

# Write a startup script that avoids asyncio import issues
$startup_code = @'
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Set Windows event loop policy BEFORE any asyncio import
if sys.platform == 'win32':
    try:
        import asyncio
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    except Exception as e:
        print(f"[WARNING] Could not set event loop policy: {e}", file=sys.stderr)

# Now import uvicorn
import uvicorn

if __name__ == "__main__":
    print("Starting backend server...")
    uvicorn.run(
        "src.backend.main:app",
        host="0.0.0.0",
        port=8080,
        reload=False,
        log_level="info",
    )
'@

Set-Content -Path "d:\trae\novel-agent-system-v1.1.0\_start_server.py" -Value $startup_code -Encoding UTF8

Write-Host "Starting backend server via direct Python execution..."
& python "d:\trae\novel-agent-system-v1.1.0\_start_server.py"
