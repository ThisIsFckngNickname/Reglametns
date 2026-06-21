"""Start server in-process, test login, dump traceback on error."""
import asyncio
import logging
import sys
import json
import urllib.request
import urllib.error

# Configure logging to stderr
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stderr,
)

# Monkey-patch sys.excepthook to ensure we see tracebacks
def excepthook(typ, val, tb):
    import traceback
    traceback.print_exception(typ, val, tb)
sys.excepthook = excepthook

async def main():
    # Import and start uvicorn
    import uvicorn
    config = uvicorn.Config("app.main:app", host="0.0.0.0", port=8000, log_level="debug")
    server = uvicorn.Server(config)
    
    # Start server in background task
    server_task = asyncio.create_task(server.serve())
    
    # Wait for server to start
    await asyncio.sleep(4)
    
    # Test login
    data = json.dumps({"email": "admin@gmail.com", "password": "Admin12+"}).encode()
    req = urllib.request.Request(
        "http://localhost:8000/api/v1/auth/login",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    try:
        resp = urllib.request.urlopen(req)
        print("LOGIN SUCCESS:", resp.read().decode(), flush=True)
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f"LOGIN FAILED ({e.code}): {body}", flush=True)
    except Exception as e:
        import traceback
        print(f"LOGIN ERROR: {e}", flush=True)
        traceback.print_exc()
    
    # Stop server
    server.should_exit = True
    await asyncio.sleep(1)

if __name__ == "__main__":
    asyncio.run(main())
