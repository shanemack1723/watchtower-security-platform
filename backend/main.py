from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session


from backend import models
from backend.auth_security import get_current_user
from backend.database import create_database, get_database
from backend.routes.devices import router as devices_router
from backend.routes.events import router as events_router
from backend.routes.alerts import router as alerts_router
from backend.routes.auth import router as auth_router
from backend.routes.audit import router as audit_router

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
app.include_router(auth_router)
app.include_router(audit_router)

@app.get(
    "/login",
    include_in_schema=False,
)
def login_page():
    return FileResponse(
        DASHBOARD_DIRECTORY / "login.html"
    )

@app.get("/dashboard", include_in_schema=False)
def dashboard(
    request: Request,
    database: Session = Depends(get_database),
):
    try:
        get_current_user(request, database)
    except HTTPException:
        return RedirectResponse(url="/login", status_code=303)

    return FileResponse(DASHBOARD_DIRECTORY / "index.html")

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