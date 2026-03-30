"""
Review API Endpoints for Opus 4.6 Quality Assessment
=====================================================
FastAPI router for 8D report reviews, approvals, and rejections.

Integration: Import and include in server.py:
    from review_endpoints import create_review_router
    review_router = create_review_router(db, audit_service, get_current_user, workflow_service)
    app.include_router(review_router, prefix="/api")
"""

import re

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
from datetime import datetime, timezone

COMPLAINT_ID_PATTERN = re.compile(r'^[a-zA-Z0-9\-]{1,64}$')


def _validate_complaint_id(complaint_id: str) -> str:
    if not complaint_id or not COMPLAINT_ID_PATTERN.match(complaint_id):
        raise HTTPException(status_code=400, detail=f"Ungültige Reklamations-ID: {complaint_id}")
    return complaint_id


async def _check_complaint_access(db, complaint_id: str, current_user: dict, require_stakeholder: bool = False):
    """
    Verify complaint exists and optionally check that user is a stakeholder.
    Returns the complaint document or raises HTTPException.
    """
    complaint = await db.complaints.find_one({"id": str(complaint_id)})
    if not complaint:
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


class ReviewRequest(BaseModel):
    force: bool = False


class ApprovalRequest(BaseModel):
    comment: Optional[str] = Field(default="", max_length=2000)


class RejectionRequest(BaseModel):
    reason: str = Field(..., min_length=1, max_length=2000)
    action_items: Optional[List[str]] = Field(default_factory=list, max_length=20)


def create_review_router(db, audit_service, get_current_user, workflow_service=None):
    """
    Factory function to create the review router with dependencies.

    Args:
        db: AsyncIOMotorDatabase instance
        audit_service: AuditService instance
        get_current_user: FastAPI dependency for authentication
        workflow_service: WorkflowService instance (for status transitions)
    """
    from review_service import ReviewService

    router = APIRouter(tags=["Reviews & Approvals"])
    review_service = ReviewService(db)

    # ─── OPUS 4.6 REVIEW ──────────────────────────────────────────────

    @router.post("/complaints/{complaint_id}/review")
    async def request_opus_review(
        complaint_id: str,
        body: ReviewRequest = ReviewRequest(),
        current_user: dict = Depends(get_current_user)
    ):
        """
        Trigger an Opus 4.6 quality review for a complaint's 8D report.

        Allowed roles: admin, zqm, bearbeiter
        """
        _validate_complaint_id(complaint_id)

        allowed_roles = ["admin", "zqm", "bearbeiter"]
        if current_user.get("role") not in allowed_roles:
            raise HTTPException(
                status_code=403,
                detail="Nur Admin, ZQM oder Bearbeiter können Reviews anfordern"
            )

        # IDOR check: bearbeiter must be a stakeholder
        await _check_complaint_access(db, complaint_id, current_user, require_stakeholder=True)

        try:
            result = await review_service.request_review(
                complaint_id=complaint_id,
                requested_by=current_user.get("id", ""),
                requested_by_name=current_user.get("full_name", current_user.get("username", "")),
                force=body.force
            )

            # Audit log
            await audit_service.log(
                action_type="REVIEW_REQUESTED",
                resource_type="complaint",
                resource_id=complaint_id,
                user_id=current_user.get("id"),
                username=current_user.get("username"),
                user_role=current_user.get("role"),
                change_details={
                    "action": "opus_review",
                    "score": result.get("review", {}).get("overall_score"),
                    "recommendation": result.get("review", {}).get("recommendation"),
                    "forced": body.force
                }
            )

            return result

        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))
        except RuntimeError:
            raise HTTPException(
                status_code=502,
                detail="Qualitätsprüfung fehlgeschlagen. Bitte versuchen Sie es später erneut."
            )

    @router.get("/complaints/{complaint_id}/reviews")
    async def get_complaint_reviews(
        complaint_id: str,
        limit: int = 10,
        current_user: dict = Depends(get_current_user)
    ):
        """Get all Opus 4.6 reviews for a specific complaint."""
        _validate_complaint_id(complaint_id)
        await _check_complaint_access(db, complaint_id, current_user, require_stakeholder=True)
        limit = max(1, min(limit, 100))
        reviews = await review_service.get_reviews(complaint_id, limit)
        return {"complaint_id": complaint_id, "reviews": reviews, "count": len(reviews)}

    @router.get("/complaints/{complaint_id}/review/latest")
    async def get_latest_review(
        complaint_id: str,
        current_user: dict = Depends(get_current_user)
    ):
        """Get the most recent Opus review for a complaint."""
        _validate_complaint_id(complaint_id)
        await _check_complaint_access(db, complaint_id, current_user, require_stakeholder=True)
        review = await review_service.get_latest_review(complaint_id)
        if not review:
            raise HTTPException(
                status_code=404,
                detail="Keine Opus-Bewertung für diese Reklamation vorhanden"
            )
        return review

    # ─── APPROVAL / REJECTION ─────────────────────────────────────────

    @router.post("/complaints/{complaint_id}/approve")
    async def approve_complaint(
        complaint_id: str,
        body: ApprovalRequest = ApprovalRequest(),
        current_user: dict = Depends(get_current_user)
    ):
        """
        Approve a complaint's 8D report after Opus review.
        Routes through WorkflowService for guards, notifications, and audit.

        Allowed roles: admin, zqm
        """
        _validate_complaint_id(complaint_id)

        if current_user.get("role") not in ["admin", "zqm"]:
            raise HTTPException(
                status_code=403,
                detail="Nur Admin oder ZQM können Reklamationen freigeben"
            )

        now = datetime.now(timezone.utc).isoformat()

        try:
            # Route through WorkflowService for guards + notifications + audit
            if workflow_service:
                result = await workflow_service.transition(
                    complaint_id=complaint_id,
                    target_status="approved",
                    user=current_user,
                    reason=f"Freigabe erteilt: {body.comment}" if body.comment else "Freigabe erteilt",
                    metadata={"approval_comment": body.comment}
                )
            else:
                # Fallback: direct DB update if WorkflowService not provided
                complaint = await db.complaints.find_one({"id": complaint_id})
                if not complaint:
                    raise HTTPException(status_code=404, detail="Reklamation nicht gefunden")
                allowed_statuses = ["reviewed", "approval_pending"]
                if complaint.get("status") not in allowed_statuses:
                    raise HTTPException(status_code=400, detail=f"Freigabe nur möglich bei Status: {', '.join(allowed_statuses)}")
                await db.complaints.update_one(
                    {"id": complaint_id},
                    {"$set": {"status": "approved", "updated_at": now},
                     "$push": {"status_history": {"from": complaint.get("status"), "to": "approved", "changed_by": current_user.get("id"), "changed_at": now, "reason": "Freigabe erteilt"}}}
                )
                result = {"success": True, "new_status": "approved"}

            # Store approval metadata on the complaint
            await db.complaints.update_one(
                {"id": complaint_id},
                {"$set": {
                    "approval": {
                        "status": "approved",
                        "approved_by": current_user.get("id"),
                        "approved_by_name": current_user.get("full_name", current_user.get("username")),
                        "approved_at": now,
                        "comment": body.comment
                    }
                }}
            )

            await audit_service.log(
                action_type="APPROVAL",
                resource_type="complaint",
                resource_id=complaint_id,
                user_id=current_user.get("id"),
                username=current_user.get("username"),
                user_role=current_user.get("role"),
                change_details={"action": "approve", "comment": body.comment}
            )

            return {
                "success": True,
                "complaint_id": complaint_id,
                "new_status": "approved",
                "approved_by": current_user.get("full_name", current_user.get("username")),
                "approved_at": now
            }

        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except PermissionError as e:
            raise HTTPException(status_code=403, detail=str(e))

    @router.post("/complaints/{complaint_id}/reject")
    async def reject_complaint(
        complaint_id: str,
        body: RejectionRequest,
        current_user: dict = Depends(get_current_user)
    ):
        """
        Reject a complaint's 8D report and send back for revision.
        Routes through WorkflowService for guards, notifications, and audit.

        Allowed roles: admin, zqm
        """
        _validate_complaint_id(complaint_id)

        if current_user.get("role") not in ["admin", "zqm"]:
            raise HTTPException(
                status_code=403,
                detail="Nur Admin oder ZQM können Reklamationen ablehnen"
            )

        if not body.reason:
            raise HTTPException(
                status_code=400,
                detail="Ablehnungsgrund ist erforderlich"
            )

        now = datetime.now(timezone.utc).isoformat()

        try:
            # Route through WorkflowService for guards + notifications + audit
            if workflow_service:
                result = await workflow_service.transition(
                    complaint_id=complaint_id,
                    target_status="revision_needed",
                    user=current_user,
                    reason=f"Freigabe abgelehnt: {body.reason}",
                    metadata={"rejection_reason": body.reason, "action_items": body.action_items or []}
                )
            else:
                # Fallback: direct DB update if WorkflowService not provided
                complaint = await db.complaints.find_one({"id": complaint_id})
                if not complaint:
                    raise HTTPException(status_code=404, detail="Reklamation nicht gefunden")
                await db.complaints.update_one(
                    {"id": complaint_id},
                    {"$set": {"status": "revision_needed", "updated_at": now},
                     "$push": {"status_history": {"from": complaint.get("status"), "to": "revision_needed", "changed_by": current_user.get("id"), "changed_at": now, "reason": f"Abgelehnt: {body.reason}"}}}
                )

            # Store rejection metadata on the complaint
            await db.complaints.update_one(
                {"id": complaint_id},
                {"$set": {
                    "approval": {
                        "status": "rejected",
                        "rejected_by": current_user.get("id"),
                        "rejected_by_name": current_user.get("full_name", current_user.get("username")),
                        "rejected_at": now,
                        "rejection_reason": body.reason,
                        "action_items": body.action_items or []
                    }
                }}
            )

            await audit_service.log(
                action_type="REJECTION",
                resource_type="complaint",
                resource_id=complaint_id,
                user_id=current_user.get("id"),
                username=current_user.get("username"),
                user_role=current_user.get("role"),
                change_details={"action": "reject", "reason": body.reason, "action_items": body.action_items}
            )

            return {
                "success": True,
                "complaint_id": complaint_id,
                "new_status": "revision_needed",
                "rejected_by": current_user.get("full_name", current_user.get("username")),
                "reason": body.reason
            }

        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except PermissionError as e:
            raise HTTPException(status_code=403, detail=str(e))

    # ─── REVIEW QUEUE & STATISTICS ────────────────────────────────────

    @router.get("/reviews/pending")
    async def get_pending_reviews(
        current_user: dict = Depends(get_current_user)
    ):
        """Get all complaints pending Opus review."""
        if current_user.get("role") not in ["admin", "zqm"]:
            raise HTTPException(status_code=403, detail="Keine Berechtigung")

        pending = await review_service.get_pending_reviews()
        return {"pending": pending, "count": len(pending)}

    @router.get("/reviews/statistics")
    async def get_review_statistics(
        current_user: dict = Depends(get_current_user)
    ):
        """Get aggregated review statistics."""
        if current_user.get("role") not in ["admin", "zqm", "analyst"]:
            raise HTTPException(status_code=403, detail="Keine Berechtigung")

        stats = await review_service.get_review_statistics()
        return stats

    @router.get("/reviews/queue")
    async def get_approval_queue(
        current_user: dict = Depends(get_current_user)
    ):
        """Get complaints waiting for approval (reviewed + approval_pending)."""
        if current_user.get("role") not in ["admin", "zqm"]:
            raise HTTPException(status_code=403, detail="Keine Berechtigung")

        # Use aggregation pipeline to join reviews in a single query (avoid N+1)
        # Explicit projection — only return fields needed for queue view (least privilege)
        pipeline = [
            {"$match": {"status": {"$in": ["reviewed", "approval_pending"]}}},
            {"$sort": {"updated_at": -1}},
            {"$limit": 100},
            {"$lookup": {
                "from": "opus_reviews",
                "let": {"cid": "$id"},
                "pipeline": [
                    {"$match": {"$expr": {"$eq": ["$complaint_id", "$$cid"]}}},
                    {"$sort": {"created_at": -1}},
                    {"$limit": 1},
                    {"$project": {
                        "_id": 0,
                        "score": "$overall_score",
                        "recommendation": 1,
                        "reviewed_at": "$created_at"
                    }}
                ],
                "as": "review_data"
            }},
            {"$addFields": {
                "latest_review": {"$arrayElemAt": ["$review_data", 0]}
            }},
            {"$project": {
                "_id": 0,
                "review_data": 0
            }}
        ]

        complaints = await db.complaints.aggregate(pipeline).to_list(length=100)

        return {"queue": complaints, "count": len(complaints)}

    return router
