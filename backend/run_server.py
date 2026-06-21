"""Start uvicorn with logging to file."""
import os
import sys

os.chdir(os.path.dirname(os.path.abspath(__file__)))

log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "server.log")
log_file = open(log_path, "w", encoding="utf-8", buffering=1)
sys.stderr = log_file

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        log_level="debug",
    )
