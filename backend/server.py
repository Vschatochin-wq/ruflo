"""
8D-Opus Reklamationsmanagement - Emergent Platform Entry Point
===============================================================
Adapter for Emergent Platform (supervisor expects server:app on port 8001).
"""

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

mongo_client: AsyncIOMotorClient = None
db = None


async def get_current_user(request: Request) -> dict:
    """
    Auth dependency - reads user info from headers.
    For development, provides a default admin user if no headers are present.
    """
    user_id = request.headers.get("X-User-ID", "user-1")
    return {
        "id": user_id,
        "username": request.headers.get("X-User-Name", "Max Mustermann"),
        "full_name": request.headers.get("X-User-Name", "Max Mustermann"),
        "role": request.headers.get("X-User-Role", "admin"),
    }


@asynccontextmanager
async def lifespan(app: FastAPI):
    global mongo_client, db

    mongo_uri = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
    db_name = os.environ.get("DB_NAME", "reklamation_db")

    logger.info(f"Connecting to MongoDB: {mongo_uri}, DB: {db_name}")
    mongo_client = AsyncIOMotorClient(mongo_uri)
    db = mongo_client[db_name]

    from websocket_manager import WebSocketManager
    from websocket_endpoints import create_websocket_router

    ws_manager = WebSocketManager()
    app.state.ws_manager = ws_manager

    ws_router = create_websocket_router(ws_manager)
    app.include_router(ws_router, prefix="/api/v1")

    _register_routes(app, db, ws_manager)

    # Create indexes
    try:
        from complaint_service import ComplaintService
        from review_service import ReviewService
        from notification_service import NotificationService
        cs = ComplaintService(db)
        rs = ReviewService(db)
        ns = NotificationService(db)
        await cs.create_indexes()
        await rs.create_indexes()
        await ns.create_indexes()
        logger.info("Database indexes created")
    except Exception as e:
        logger.warning(f"Index creation warning: {e}")

    # Seed sample data if empty
    await _seed_sample_data(db)

    logger.info("8D-Opus Backend started successfully")
    yield

    if mongo_client:
        mongo_client.close()
        logger.info("MongoDB connection closed")


app = FastAPI(
    title="8D-Opus Reklamationsmanagement",
    description="Backend-API fuer das 8D-Report-Management mit KI-Qualitaetspruefung",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _register_routes(app: FastAPI, db, ws_manager=None):
    from complaint_service import ComplaintService
    from workflow_service import WorkflowService
    from review_service import ReviewService
    from notification_service import NotificationService
    from statistics_service import StatisticsService

    notification_service = NotificationService(db)
    workflow_service = WorkflowService(db, notification_service=notification_service)
    complaint_service = ComplaintService(db)
    review_service = ReviewService(db)
    statistics_service = StatisticsService(db)

    upload_service = None
    ocr_service = None
    try:
        from upload_service import UploadService
        from ocr_service import OcrService
        upload_service = UploadService(db)
        ocr_service = OcrService(db)
    except ImportError:
        logger.warning("Upload/OCR services not available")

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

    review_router = create_review_router(
        db=db,
        audit_service=notification_service,
        get_current_user=get_current_user,
        workflow_service=workflow_service,
    )
    app.include_router(review_router, prefix="/api/v1")

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
            logger.warning("Upload endpoints not available")

    # Notification endpoints
    from notification_endpoints import create_notification_routes
    notification_router = create_notification_routes(notification_service)
    app.include_router(notification_router, prefix="/api/v1")


@app.get("/api/health")
async def health_check():
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


async def _seed_sample_data(db):
    """Seed sample complaint data if DB is empty."""
    count = await db.complaints.count_documents({})
    if count > 0:
        return

    from datetime import datetime, timezone
    import uuid

    logger.info("Seeding sample complaint data...")

    samples = [
        {
            "id": str(uuid.uuid4()),
            "complaint_number": "RK-2026-0001",
            "status": "in_progress",
            "customer_name": "BMW AG",
            "customer_number": "K-10234",
            "problem_description": "Bohrer VHM 8.5mm zeigt vorzeitigen Verschleiss nach 200 Bohrungen statt erwarteter 500. Schneidkante bricht aus.",
            "message_type": "Q3",
            "report_type": "8D",
            "fa_code": "FA-2026-1234",
            "artikel_nummer": "5511-08500",
            "error_location": "Produktion - CNC Bearbeitungszentrum",
            "affected_quantity": 50,
            "delivered_quantity": 200,
            "detection_date": "2026-01-15",
            "created_by": "user-1",
            "created_by_name": "Max Mustermann",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "deleted": False,
            "team_members": [
                {"name": "Max Mustermann", "role": "Teamleiter", "department": "QM"},
                {"name": "Anna Schmidt", "role": "Bearbeiter", "department": "Produktion"},
            ],
            "errors": [
                {"code": "F-VER-001", "description": "Vorzeitiger Verschleiss der Schneidkante", "category": "Verschleiss"},
            ],
            "immediate_actions": [
                {"code": "SM-001", "description": "Betroffene Charge gesperrt", "responsible": "Lager", "status": "done", "deadline": "2026-01-16"},
            ],
            "causes": [
                {"code": "U-001", "description": "Haerteabweichung im Substrat", "category": "Material"},
            ],
            "corrective_actions": [
                {"code": "KM-001", "description": "Substratlieferant informiert und Nacharbeit angefordert", "responsible": "Einkauf", "status": "planned", "deadline": "2026-02-01"},
            ],
            "status_history": [
                {"from": None, "to": "draft", "changed_by": "user-1", "changed_at": datetime.now(timezone.utc).isoformat(), "reason": "Reklamation angelegt"},
                {"from": "draft", "to": "open", "changed_by": "user-1", "changed_at": datetime.now(timezone.utc).isoformat(), "reason": "Zur Bearbeitung freigegeben"},
                {"from": "open", "to": "in_progress", "changed_by": "user-1", "changed_at": datetime.now(timezone.utc).isoformat(), "reason": "Bearbeitung gestartet"},
            ],
            "update_history": [],
        },
        {
            "id": str(uuid.uuid4()),
            "complaint_number": "RK-2026-0002",
            "status": "draft",
            "customer_name": "Daimler AG",
            "customer_number": "K-20456",
            "problem_description": "Fraeser 12mm - Oberflaechenrauheit ausserhalb Toleranz Ra > 1.6um statt Ra 0.8um",
            "message_type": "Q1",
            "report_type": "8D",
            "fa_code": "FA-2026-2345",
            "artikel_nummer": "3021-12000",
            "error_location": "Wareneingang",
            "affected_quantity": 10,
            "delivered_quantity": 50,
            "detection_date": "2026-01-20",
            "created_by": "user-1",
            "created_by_name": "Max Mustermann",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "deleted": False,
            "status_history": [
                {"from": None, "to": "draft", "changed_by": "user-1", "changed_at": datetime.now(timezone.utc).isoformat(), "reason": "Reklamation angelegt"},
            ],
            "update_history": [],
        },
        {
            "id": str(uuid.uuid4()),
            "complaint_number": "RK-2026-0003",
            "status": "approved",
            "customer_name": "Volkswagen AG",
            "customer_number": "K-30789",
            "problem_description": "Stufenbohrer zeigt Masshaltigkeit-Abweichung: Durchmesser 10.05mm statt 10.00mm +/- 0.02mm",
            "message_type": "Q3",
            "report_type": "8D",
            "fa_code": "FA-2025-9876",
            "artikel_nummer": "5524-10000",
            "error_location": "Endkontrolle",
            "affected_quantity": 5,
            "delivered_quantity": 100,
            "detection_date": "2025-12-10",
            "created_by": "user-1",
            "created_by_name": "Max Mustermann",
            "created_at": "2025-12-10T08:00:00+00:00",
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "deleted": False,
            "team_members": [
                {"name": "Klaus Weber", "role": "Teamleiter", "department": "QM"},
                {"name": "Maria Mueller", "role": "Bearbeiter", "department": "Fertigung"},
                {"name": "Thomas Braun", "role": "Experte", "department": "Messtechnik"},
            ],
            "errors": [
                {"code": "F-MAS-001", "description": "Masshaltigkeit ausserhalb Toleranz", "category": "Massabweichung"},
            ],
            "immediate_actions": [
                {"code": "SM-001", "description": "Restbestand gesperrt und nachgemessen", "responsible": "QM", "status": "done", "deadline": "2025-12-11"},
                {"code": "SM-002", "description": "Kunde informiert und Ersatzlieferung veranlasst", "responsible": "Vertrieb", "status": "done", "deadline": "2025-12-12"},
            ],
            "causes": [
                {"code": "U-001", "description": "Werkzeugverschleiss an der Schleifscheibe", "category": "Maschine"},
                {"code": "U-002", "description": "Fehlende Zwischenkontrolle nach 50 Stueck", "category": "Methode"},
            ],
            "five_why": [
                {"question": "Warum weicht der Durchmesser ab?", "answer": "Die Schleifscheibe war abgenutzt"},
                {"question": "Warum war die Schleifscheibe abgenutzt?", "answer": "Der Wechselintervall wurde ueberschritten"},
                {"question": "Warum wurde der Wechselintervall ueberschritten?", "answer": "Kein automatisches Warnsystem vorhanden"},
                {"question": "Warum gibt es kein Warnsystem?", "answer": "Wurde bei Maschineneinrichtung nicht konfiguriert"},
                {"question": "Warum wurde es nicht konfiguriert?", "answer": "Fehlende Vorgabe in der Arbeitsanweisung"},
            ],
            "corrective_actions": [
                {"code": "KM-001", "description": "Schleifscheibe getauscht und Maschine neu kalibriert", "responsible": "Fertigung", "status": "done", "deadline": "2025-12-15"},
                {"code": "KM-002", "description": "Wechselintervall im MES-System hinterlegt", "responsible": "IT", "status": "done", "deadline": "2025-12-20"},
            ],
            "verification": {
                "method": "Stichprobenpruefung n=20 nach DIN ISO 2859",
                "result": "Alle Masse innerhalb Toleranz",
                "verified_by": "Thomas Braun",
                "date": "2025-12-22"
            },
            "preventive_actions": [
                {"code": "VM-001", "description": "Automatische Verschleisswarnung im MES fuer alle Schleifmaschinen", "responsible": "IT/Fertigung", "status": "done", "deadline": "2026-01-15"},
            ],
            "closure": {
                "lessons_learned": "Werkzeugverschleiss-Monitoring muss fuer alle kritischen Prozesse implementiert werden",
                "closed_by": "Klaus Weber",
                "closed_date": "2026-01-10"
            },
            "latest_opus_review": {
                "review_id": "review-sample-1",
                "score": 87,
                "recommendation": "approval_recommended",
                "reviewed_at": "2026-01-08T10:00:00+00:00",
                "action_items_count": 1
            },
            "approval": {
                "status": "approved",
                "approved_by": "user-1",
                "approved_by_name": "Max Mustermann",
                "approved_at": "2026-01-10T14:00:00+00:00",
                "comment": "Gute Arbeit, vollstaendiger 8D-Report"
            },
            "status_history": [
                {"from": None, "to": "draft", "changed_by": "user-1", "changed_at": "2025-12-10T08:00:00+00:00", "reason": "Reklamation angelegt"},
                {"from": "draft", "to": "open", "changed_by": "user-1", "changed_at": "2025-12-10T09:00:00+00:00", "reason": "Freigegeben"},
                {"from": "open", "to": "in_progress", "changed_by": "user-1", "changed_at": "2025-12-11T08:00:00+00:00", "reason": "Bearbeitung gestartet"},
                {"from": "in_progress", "to": "review_pending", "changed_by": "user-1", "changed_at": "2026-01-05T10:00:00+00:00", "reason": "Review angefordert"},
                {"from": "review_pending", "to": "approval_pending", "changed_by": "system", "changed_at": "2026-01-08T10:00:00+00:00", "reason": "Opus Score 87/100"},
                {"from": "approval_pending", "to": "approved", "changed_by": "user-1", "changed_at": "2026-01-10T14:00:00+00:00", "reason": "Freigabe erteilt"},
            ],
            "update_history": [],
        },
    ]

    try:
        await db.complaints.insert_many(samples)
        logger.info(f"Seeded {len(samples)} sample complaints")
    except Exception as e:
        logger.warning(f"Seeding failed: {e}")
