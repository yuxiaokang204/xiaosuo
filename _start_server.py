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
