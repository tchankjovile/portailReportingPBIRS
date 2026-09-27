import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from app.config import settings
from app.db.database import init_db, AsyncSessionLocal
from app.services.report_service import report_service
from app.routers import pages, reports, api, admin

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Create tables & seed catalog if empty
    logger.info("Initializing BICEC PBIRS Portal Database...")
    await init_db()
    async with AsyncSessionLocal() as session:
        await report_service.sync_catalog_if_empty(session)
    logger.info("Database and PBIRS Catalog successfully initialized.")
    yield
    # Shutdown
    logger.info("Shutting down portal server.")

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    lifespan=lifespan,
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url=None
)

# Mount Static Files
os.makedirs("app/static/images", exist_ok=True)
os.makedirs("app/static/css", exist_ok=True)
os.makedirs("app/static/js", exist_ok=True)
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Register Application Routers
app.include_router(pages.router)
app.include_router(reports.router)
app.include_router(api.router)
app.include_router(admin.router)

# Middleware : redirection automatique 401 → /login
@app.middleware("http")
async def redirect_unauthenticated(request: Request, call_next):
    response = await call_next(request)
    if response.status_code == 401:
        return RedirectResponse(url="/login", status_code=302)
    return response

# Favicon - évite le 404 automatique du navigateur
@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return RedirectResponse(url="/static/images/bicec_logo.png")
