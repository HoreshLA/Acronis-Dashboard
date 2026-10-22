"""Local Acronis billing dashboard. Read-only.

Run: python -m uvicorn app:app --host 127.0.0.1 --port 8001
"""
from __future__ import annotations

import asyncio
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

import acronis_client

HERE = Path(__file__).parent


def _load_dotenv() -> None:
    env = HERE / ".env"
    if not env.exists():
        return
    for line in env.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())


_load_dotenv()

app = FastAPI(title="Acronis dashboard")
app.mount("/static", StaticFiles(directory=HERE / "static"), name="static")


@app.get("/api/acronis")
async def acronis_api(refresh: bool = False):
    try:
        return await asyncio.to_thread(acronis_client.dashboard, refresh)
    except RuntimeError as e:
        raise HTTPException(503, str(e))
    except Exception as e:
        raise HTTPException(502, f"שגיאת אקרוניס: {e}")


@app.get("/")
def index():
    return FileResponse(HERE / "static" / "index.html")
