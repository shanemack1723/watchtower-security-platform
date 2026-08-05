from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend import models
from backend.database import create_database
from backend.routes.devices import router as devices_router
from backend.routes.events import router as events_router
from backend.routes.alerts import router as alerts_router

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DASHBOARD_DIRECTORY = PROJECT_ROOT / "dashboard"

@asynccontextmanager
async def lifespan(app: FastAPI):
    create_database()
    yield


app = FastAPI(
    title="Watchtower Security Platform",
    description="A Windows security monitoring and incident-response platform.",
    version="0.1.0",
    lifespan=lifespan,
)

app.mount(
    "/static",
    StaticFiles(directory=DASHBOARD_DIRECTORY),
    name="static",
)


app.include_router(devices_router)
app.include_router(events_router)
app.include_router(alerts_router)

@app.get(
    "/dashboard",
    include_in_schema=False,
)
def dashboard():
    return FileResponse(
        DASHBOARD_DIRECTORY / "index.html"
    )

@app.get("/")
def root():
    return {
        "service": "Watchtower Security Platform",
        "status": "running",
        "version": "0.1.0",
    }


@app.get("/health")
def health_check():
    return {
        "status": "healthy",
    }