import logging
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import init_db
from app.api.webhook import router as webhook_router
from app.api.reviews import router as reviews_router

# Configure Logging
logging.basicConfig(
    level=logging.INFO if not settings.debug else logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("CodeSentinel")

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing CodeSentinel database tables...")
    init_db()
    logger.info("CodeSentinel startup complete.")
    yield

app = FastAPI(
    title=settings.app_name,
    description="CodeSentinel - AI-Powered Automated PR Review Agent with Multi-Agent Engine and AST Chunking",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# Enable CORS for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers
app.include_router(webhook_router, tags=["GitHub Webhook"])
app.include_router(reviews_router, prefix="/api", tags=["PR Reviews & Analytics"])

# Static Files & Dashboard UI
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.get("/", response_class=FileResponse)
def serve_dashboard():
    """Serves the CodeSentinel Web Dashboard UI."""
    index_file = os.path.join(static_dir, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return JSONResponse({"message": "CodeSentinel API is running.", "docs": "/docs"})

@app.get("/health")
def health_check():
    """Healthcheck status endpoint for Docker / K8s."""
    return {"status": "healthy", "app": settings.app_name, "version": "1.0.0"}
