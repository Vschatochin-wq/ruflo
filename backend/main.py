"""
8D-Opus Reklamationsmanagement — FastAPI Application
=====================================================
Zentraler Einstiegspunkt fuer die Backend-API.

Startet die FastAPI-Anwendung mit allen Routen, Middleware,
Datenbankverbindung und Service-Initialisierung.

Usage:
    uvicorn main:app --reload --port 8000
"""

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient

logger = logging.getLogger(__name__)

# ─── GLOBALS ─────────────────────────────────────────────────────────

mongo_client: AsyncIOMotorClient = None
db = None


# ─── AUTH DEPENDENCY (PLACEHOLDER) ───────────────────────────────────

async def get_current_user(request: Request) -> dict:
    """
    Einfache Auth-Dependency als Platzhalter.
    Liest Benutzerinformationen aus HTTP-Headern.
    Wird spaeter durch JWT-basierte Authentifizierung ersetzt.

    Headers:
        X-User-ID: Benutzer-ID (Pflicht)
        X-User-Role: Benutzerrolle (Standard: "viewer")
        X-User-Name: Anzeigename (optional)
    """
    user_id = request.headers.get("X-User-ID", "")
    if not user_id:
        raise HTTPException(
            status_code=401,
            detail="Authentifizierung erforderlich — X-User-ID Header fehlt"
        )

    return {
        "id": user_id,
        "username": request.headers.get("X-User-Name", user_id),
        "full_name": request.headers.get("X-User-Name", ""),
        "role": request.headers.get("X-User-Role", "viewer"),
    }


# ─── LIFESPAN (STARTUP / SHUTDOWN) ──────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Datenbankverbindung beim Start herstellen und beim Beenden schliessen."""
    global mongo_client, db

    # Startup
    mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017")
    db_name = os.getenv("MONGO_DB_NAME", "reklamation_db")

    logger.info(f"Verbinde mit MongoDB: {mongo_uri}")
    mongo_client = AsyncIOMotorClient(mongo_uri)
    db = mongo_client[db_name]

    # WebSocket-Manager initialisieren
    from websocket_manager import WebSocketManager
    from websocket_endpoints import create_websocket_router

    ws_manager = WebSocketManager()
    app.state.ws_manager = ws_manager

    ws_router = create_websocket_router(ws_manager)
    app.include_router(ws_router, prefix="/api/v1")

    # Services initialisieren
    _register_routes(app, db, ws_manager)

    logger.info("8D-Opus Backend gestartet")
    yield

    # Shutdown
    if mongo_client:
        mongo_client.close()
        logger.info("MongoDB-Verbindung geschlossen")


# ─── APP CREATION ────────────────────────────────────────────────────

app = FastAPI(
    title="8D-Opus Reklamationsmanagement",
    description=(
        "Backend-API fuer das 8D-Report-Management mit Opus-4.6-Qualitaetspruefung. "
        "Verwaltet Reklamationen, Status-Workflows, Reviews, Dokumente und Statistiken."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# ─── CORS MIDDLEWARE ─────────────────────────────────────────────────

allowed_origins = os.getenv(
    "CORS_ORIGINS",
    "http://localhost:3000,http://localhost:5173,http://localhost:8080"
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in allowed_origins],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── ROUTE REGISTRATION ─────────────────────────────────────────────

def _register_routes(app: FastAPI, db, ws_manager=None):
    """Alle Router mit ihren Services registrieren."""

    # Services importieren und instanziieren
    from complaint_service import ComplaintService
    from workflow_service import WorkflowService
    from review_service import ReviewService
    from notification_service import NotificationService
    from statistics_service import StatisticsService

    notification_service = NotificationService(db)
    workflow_service = WorkflowService(
        db,
        notification_service=notification_service,
    )
    complaint_service = ComplaintService(db)
    review_service = ReviewService(db)
    statistics_service = StatisticsService(db)

    # Optionale Services (Upload, OCR) — nur laden wenn verfuegbar
    upload_service = None
    ocr_service = None
    try:
        from upload_service import UploadService
        from ocr_service import OcrService
        upload_service = UploadService(db)
        ocr_service = OcrService(db)
    except ImportError:
        logger.warning("Upload/OCR-Services nicht verfuegbar")

    # Router importieren und registrieren
    from complaint_endpoints import create_complaint_router
    from statistics_endpoints import create_statistics_router
    from review_endpoints import create_review_router

    complaint_router = create_complaint_router(
        db=db,
        complaint_service=complaint_service,
        workflow_service=workflow_service,
        get_current_user=get_current_user,
    )
    app.include_router(complaint_router, prefix="/api/v1")

    statistics_router = create_statistics_router(
        db=db,
        statistics_service=statistics_service,
        get_current_user=get_current_user,
    )
    app.include_router(statistics_router, prefix="/api/v1")

    # Review-Router braucht audit_service — verwende Notification als Fallback
    review_router = create_review_router(
        db=db,
        audit_service=notification_service,
        get_current_user=get_current_user,
        workflow_service=workflow_service,
    )
    app.include_router(review_router, prefix="/api/v1")

    # Upload-Router (optional)
    if upload_service and ocr_service:
        try:
            from upload_endpoints import create_upload_router
            upload_router = create_upload_router(
                db=db,
                upload_service=upload_service,
                ocr_service=ocr_service,
                get_current_user=get_current_user,
            )
            app.include_router(upload_router, prefix="/api/v1")
        except ImportError:
            logger.warning("Upload-Endpoints nicht verfuegbar")


# ─── HEALTH ENDPOINT ────────────────────────────────────────────────

@app.get("/health")
async def health_check():
    """System-Gesundheitspruefung."""
    db_status = "unknown"
    if db is not None:
        try:
            await db.command("ping")
            db_status = "connected"
        except Exception:
            db_status = "disconnected"

    return {
        "status": "ok",
        "service": "8D-Opus Reklamationsmanagement",
        "version": "1.0.0",
        "database": db_status,
    }
