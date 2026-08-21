from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from agent_hub.routes import admin, agents, auth, conversations, health, stream

app = FastAPI(title="Agent Hub", version="0.1.0")
app.include_router(health.router)
app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(agents.router)
app.include_router(conversations.router)
app.include_router(stream.router)

STATIC_DIR = Path(__file__).with_name("static")
if STATIC_DIR.is_dir():
    app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="assets")

    @app.get("/", include_in_schema=False)
    def frontend() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

    @app.get("/{path:path}", include_in_schema=False)
    def frontend_route(path: str) -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")


def run() -> None:
    uvicorn.run("agent_hub.api:app", host="0.0.0.0", port=8000)
