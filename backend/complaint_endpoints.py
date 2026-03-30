"""
Complaint CRUD API Endpoints
==============================
FastAPI router for complaint lifecycle management: create, list,
update, soft-delete, search, and status transitions.

Integration:
    from complaint_endpoints import create_complaint_router
    complaint_router = create_complaint_router(db, complaint_service, workflow_service, get_current_user)
    app.include_router(complaint_router, prefix="/api/v1")
"""

import re

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime, timezone

COMPLAINT_ID_PATTERN = re.compile(r'^[a-zA-Z0-9\-]{1,64}$')

# Interne Felder, die aus Antworten entfernt werden
STRIP_FIELDS = {"_id", "deleted", "deleted_at", "deleted_by"}


def _validate_complaint_id(complaint_id: str) -> str:
    if not complaint_id or not COMPLAINT_ID_PATTERN.match(complaint_id):
        raise HTTPException(status_code=400, detail=f"Ungueltige Reklamations-ID: {complaint_id}")
    return complaint_id


def _strip_internal(doc: dict) -> dict:
    """Interne Felder aus der Antwort entfernen."""
    if not doc:
        return doc
    return {k: v for k, v in doc.items() if k not in STRIP_FIELDS}


async def _check_complaint_access(db, complaint_id: str, current_user: dict, require_stakeholder: bool = False):
    """
    Prueft ob die Reklamation existiert und der Benutzer Zugriff hat.
    IDOR-Schutz: Nur Stakeholder, Admins und ZQM duerfen zugreifen.
    """
    complaint = await db.complaints.find_one({"id": str(complaint_id)})
    if not complaint:
        raise HTTPException(status_code=404, detail="Reklamation nicht gefunden")

    if complaint.get("deleted"):
        raise HTTPException(status_code=404, detail="Reklamation nicht gefunden")

    if require_stakeholder and current_user.get("role") not in ["admin", "zqm"]:
        user_id = current_user.get("id", "")
        is_stakeholder = (
            complaint.get("created_by") == user_id
            or (complaint.get("assigned_processor", {}) or {}).get("user_id") == user_id
            or (complaint.get("assigned_zqm", {}) or {}).get("user_id") == user_id
        )
        if not is_stakeholder:
            raise HTTPException(
                status_code=403,
                detail="Kein Zugriff — Sie sind nicht an dieser Reklamation beteiligt"
            )

    return complaint


# ─── REQUEST / RESPONSE MODELS ──────────────────────────────────────

class CreateComplaintRequest(BaseModel):
    customer_name: str = Field(..., min_length=1, max_length=500)
    customer_number: Optional[str] = Field(default="", max_length=100)
    problem_description: str = Field(..., min_length=1, max_length=5000)
    message_type: Optional[str] = Field(default="Q3", max_length=20)
    report_type: Optional[str] = Field(default="8D", max_length=20)
    fa_code: Optional[str] = Field(default="", max_length=100)
    artikel_nummer: Optional[str] = Field(default="", max_length=100)
    article_number: Optional[str] = Field(default="", max_length=100)
    error_location: Optional[str] = Field(default="", max_length=500)
    affected_quantity: Optional[int] = Field(default=0, ge=0)
    delivered_quantity: Optional[int] = Field(default=0, ge=0)
    detection_date: Optional[str] = Field(default="", max_length=20)
    assigned_zqm: Optional[dict] = None
    assigned_processor: Optional[dict] = None


class UpdateComplaintRequest(BaseModel):
    customer_name: Optional[str] = Field(default=None, max_length=500)
    customer_number: Optional[str] = Field(default=None, max_length=100)
    problem_description: Optional[str] = Field(default=None, max_length=5000)
    message_type: Optional[str] = Field(default=None, max_length=20)
    report_type: Optional[str] = Field(default=None, max_length=20)
    fa_code: Optional[str] = Field(default=None, max_length=100)
    artikel_nummer: Optional[str] = Field(default=None, max_length=100)
    article_number: Optional[str] = Field(default=None, max_length=100)
    error_location: Optional[str] = Field(default=None, max_length=500)
    affected_quantity: Optional[int] = Field(default=None, ge=0)
    delivered_quantity: Optional[int] = Field(default=None, ge=0)
    detection_date: Optional[str] = Field(default=None, max_length=20)
    assigned_zqm: Optional[dict] = None
    assigned_processor: Optional[dict] = None
    team_members: Optional[list] = None
    errors: Optional[list] = None
    immediate_actions: Optional[list] = None
    causes: Optional[list] = None
    five_why: Optional[list] = None
    corrective_actions: Optional[list] = None
    verification: Optional[dict] = None
    preventive_actions: Optional[list] = None
    closure: Optional[dict] = None


class TransitionRequest(BaseModel):
    target_status: str = Field(..., min_length=1, max_length=50)
    reason: Optional[str] = Field(default="", max_length=2000)
    metadata: Optional[dict] = None


def create_complaint_router(db, complaint_service, workflow_service, get_current_user):
    """
    Factory-Funktion fuer den Reklamations-Router.

    Args:
        db: AsyncIOMotorDatabase Instanz
        complaint_service: ComplaintService Instanz
        workflow_service: WorkflowService Instanz
        get_current_user: FastAPI Dependency fuer Authentifizierung
    """
    router = APIRouter(tags=["Reklamationen"])

    # ─── CREATE ──────────────────────────────────────────────────

    @router.post("/complaints")
    async def create_complaint(
        body: CreateComplaintRequest,
        current_user: dict = Depends(get_current_user)
    ):
        """Neue Reklamation anlegen."""
        try:
            result = await complaint_service.create_complaint(
                data=body.model_dump(),
                user_id=current_user.get("id", ""),
                user_name=current_user.get("full_name", current_user.get("username", ""))
            )
            return _strip_internal(result)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    # ─── LIST ────────────────────────────────────────────────────

    @router.get("/complaints")
    async def list_complaints(
        status: Optional[str] = Query(default=None, max_length=50),
        customer: Optional[str] = Query(default=None, alias="customer", max_length=200),
        complaint_number: Optional[str] = Query(default=None, max_length=50),
        assigned_zqm: Optional[str] = Query(default=None, max_length=64),
        assigned_processor: Optional[str] = Query(default=None, max_length=64),
        date_from: Optional[str] = Query(default=None, max_length=30),
        date_to: Optional[str] = Query(default=None, max_length=30),
        search: Optional[str] = Query(default=None, max_length=200),
        page: int = Query(default=1, ge=1),
        page_size: int = Query(default=20, ge=1, le=100),
        sort_by: str = Query(default="created_at", max_length=30),
        sort_dir: str = Query(default="desc", pattern="^(asc|desc)$"),
        current_user: dict = Depends(get_current_user)
    ):
        """
        Paginierte Liste aller Reklamationen mit optionalen Filtern.
        Unterstuetzt Volltextsuche via 'search' Query-Parameter.
        """
        # Volltextsuche hat Vorrang
        if search and search.strip():
            try:
                result = await complaint_service.search_complaints(
                    query=search,
                    page=page,
                    page_size=page_size
                )
                result["items"] = [_strip_internal(i) for i in result["items"]]
                return result
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))

        filters = {}
        if status:
            filters["status"] = status
        if customer:
            filters["customer_name"] = customer
        if complaint_number:
            filters["complaint_number"] = complaint_number
        if assigned_zqm:
            filters["assigned_zqm"] = assigned_zqm
        if assigned_processor:
            filters["assigned_processor"] = assigned_processor
        if date_from:
            filters["date_from"] = date_from
        if date_to:
            filters["date_to"] = date_to

        result = await complaint_service.list_complaints(
            filters=filters,
            page=page,
            page_size=page_size,
            sort_by=sort_by,
            sort_dir=sort_dir
        )
        result["items"] = [_strip_internal(i) for i in result["items"]]
        return result

    # ─── GET DETAIL ──────────────────────────────────────────────

    @router.get("/complaints/{complaint_id}")
    async def get_complaint(
        complaint_id: str,
        current_user: dict = Depends(get_current_user)
    ):
        """Einzelne Reklamation laden."""
        _validate_complaint_id(complaint_id)
        await _check_complaint_access(db, complaint_id, current_user, require_stakeholder=True)

        try:
            complaint = await complaint_service.get_complaint(complaint_id)
            return _strip_internal(complaint)
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))

    # ─── UPDATE ──────────────────────────────────────────────────

    @router.patch("/complaints/{complaint_id}")
    async def update_complaint(
        complaint_id: str,
        body: UpdateComplaintRequest,
        current_user: dict = Depends(get_current_user)
    ):
        """Reklamation teilweise aktualisieren (Partial Update)."""
        _validate_complaint_id(complaint_id)
        await _check_complaint_access(db, complaint_id, current_user, require_stakeholder=True)

        try:
            # Nur gesetzte Felder senden (exclude_unset)
            update_data = body.model_dump(exclude_unset=True)
            result = await complaint_service.update_complaint(
                complaint_id=complaint_id,
                data=update_data,
                user_id=current_user.get("id", "")
            )
            return _strip_internal(result)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    # ─── DELETE (SOFT) ───────────────────────────────────────────

    @router.delete("/complaints/{complaint_id}")
    async def delete_complaint(
        complaint_id: str,
        current_user: dict = Depends(get_current_user)
    ):
        """Reklamation weich loeschen (Soft Delete). Nur Admin und ZQM."""
        _validate_complaint_id(complaint_id)

        if current_user.get("role") not in ["admin", "zqm"]:
            raise HTTPException(
                status_code=403,
                detail="Nur Admin oder ZQM koennen Reklamationen loeschen"
            )

        try:
            result = await complaint_service.delete_complaint(
                complaint_id=complaint_id,
                user_id=current_user.get("id", "")
            )
            return result
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))

    # ─── SUMMARY / COMPLETENESS ──────────────────────────────────

    @router.get("/complaints/{complaint_id}/summary")
    async def get_complaint_summary(
        complaint_id: str,
        current_user: dict = Depends(get_current_user)
    ):
        """Vollstaendigkeitspruefung: welche D-Schritte sind ausgefuellt?"""
        _validate_complaint_id(complaint_id)
        await _check_complaint_access(db, complaint_id, current_user, require_stakeholder=True)

        try:
            return await complaint_service.get_complaint_summary(complaint_id)
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))

    # ─── STATUS TRANSITION ───────────────────────────────────────

    @router.post("/complaints/{complaint_id}/transition")
    async def transition_complaint(
        complaint_id: str,
        body: TransitionRequest,
        current_user: dict = Depends(get_current_user)
    ):
        """
        Status-Uebergang ausfuehren (delegiert an WorkflowService).
        Prueft Guards, Rollenberechtigung und loest Benachrichtigungen aus.
        """
        _validate_complaint_id(complaint_id)
        await _check_complaint_access(db, complaint_id, current_user, require_stakeholder=True)

        try:
            result = await workflow_service.transition(
                complaint_id=complaint_id,
                target_status=body.target_status,
                user=current_user,
                reason=body.reason or "",
                metadata=body.metadata
            )
            return result
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except PermissionError as e:
            raise HTTPException(status_code=403, detail=str(e))

    # ─── ALLOWED TRANSITIONS ────────────────────────────────────

    @router.get("/complaints/{complaint_id}/allowed-transitions")
    async def get_allowed_transitions(
        complaint_id: str,
        current_user: dict = Depends(get_current_user)
    ):
        """Erlaubte Status-Uebergaenge fuer den aktuellen Benutzer."""
        _validate_complaint_id(complaint_id)
        await _check_complaint_access(db, complaint_id, current_user, require_stakeholder=True)

        transitions = await workflow_service.get_allowed_transitions(
            complaint_id=complaint_id,
            user_role=current_user.get("role", "viewer")
        )
        return {"complaint_id": complaint_id, "transitions": transitions}

    return router
