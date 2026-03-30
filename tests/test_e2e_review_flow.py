"""
E2E Test: Full Review Lifecycle
================================
Tests the complete flow: complaint -> Opus review -> approve/reject -> close.
"""

import pytest
from unittest.mock import AsyncMock, patch

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from conftest import MockDB, make_complaint, make_user
from review_service import ReviewService
from workflow_service import WorkflowService
from notification_service import NotificationService


@pytest.fixture
def services(mock_db):
    notification_svc = NotificationService(mock_db)
    audit_svc = AsyncMock()
    audit_svc.log = AsyncMock()
    workflow_svc = WorkflowService(mock_db, notification_svc, audit_svc)
    review_svc = ReviewService(mock_db)
    return {
        "db": mock_db,
        "review": review_svc,
        "workflow": workflow_svc,
        "notification": notification_svc,
        "audit": audit_svc,
    }


MOCK_OPUS_RESPONSE_HIGH = {
    "overall_score": 88,
    "recommendation": "approval_recommended",
    "section_scores": {
        "D1_team": {"score": 90, "status": "exzellent", "assessment": "OK", "issues": [], "recommendations": []},
        "D2_problem_description": {"score": 85, "status": "gut", "assessment": "OK", "issues": [], "recommendations": []},
        "D3_immediate_actions": {"score": 88, "status": "gut", "assessment": "OK", "issues": [], "recommendations": []},
        "D4_root_cause": {"score": 82, "status": "gut", "assessment": "OK", "issues": [], "recommendations": []},
        "D5_corrective_actions": {"score": 90, "status": "exzellent", "assessment": "OK", "issues": [], "recommendations": []},
    },
    "consistency_check": {"d4_d5_alignment": True, "detail": "D4 und D5 konsistent"},
    "plausibility_check": {"passed": True, "detail": "Plausibel"},
    "overall_assessment": "Exzellenter 8D-Report",
    "action_items": [],
    "strengths": ["Gute Ursachenanalyse", "Umfassende Maßnahmen"],
}

MOCK_OPUS_RESPONSE_LOW = {
    "overall_score": 42,
    "recommendation": "revision_needed",
    "section_scores": {
        "D1_team": {"score": 50, "status": "schwach", "assessment": "Unvollständig", "issues": ["Team zu klein"], "recommendations": ["Mehr Experten"]},
        "D4_root_cause": {"score": 30, "status": "unzureichend", "assessment": "5-Why fehlt", "issues": ["Keine Ursachenanalyse"], "recommendations": ["Ishikawa durchführen"]},
    },
    "consistency_check": {"d4_d5_alignment": False, "detail": "D4 und D5 inkonsistent"},
    "plausibility_check": {"passed": False, "detail": "Nicht plausibel"},
    "overall_assessment": "Report unvollständig — grundlegende Überarbeitung nötig",
    "action_items": ["Ursachenanalyse durchführen", "Team erweitern", "5-Why ergänzen"],
    "strengths": [],
}


class TestE2EApprovalFlow:
    """Happy path: complaint -> review (high score) -> approved -> closed."""

    @pytest.mark.asyncio
    async def test_full_approval_lifecycle(self, services):
        db = services["db"]
        review_svc = services["review"]
        workflow_svc = services["workflow"]

        # 1. Create complaint in draft
        complaint = make_complaint(status="draft")
        db.add_complaint(complaint)
        cid = complaint["id"]

        bearbeiter = make_user("bearbeiter", "proc-1")
        zqm = make_user("zqm", "zqm-1")
        admin = make_user("admin", "admin-1")

        # 2. Move through initial states
        await workflow_svc.transition(cid, "open", bearbeiter)
        await workflow_svc.transition(cid, "in_progress", bearbeiter)

        # 3. Request Opus review
        with patch.object(review_svc, '_call_opus', new_callable=AsyncMock) as mock_opus:
            mock_opus.return_value = MOCK_OPUS_RESPONSE_HIGH
            result = await review_svc.request_review(cid, "proc-1", "Bearbeiter", force=True)

        assert result["review"]["new_status"] == "approval_pending"
        assert result["review"]["overall_score"] == 88

        # 4. Approve via workflow
        await workflow_svc.transition(cid, "approved", zqm)

        # 5. Close
        # Set approval data for guard
        await db.complaints.update_one(
            {"id": cid},
            {"$set": {"approval": {"status": "approved"}}}
        )
        await workflow_svc.transition(cid, "closed", admin)

        # 6. Verify final state
        final = await db.complaints.find_one({"id": cid})
        assert final["status"] == "closed"


class TestE2ERejectionFlow:
    """Rejection path: complaint -> review (low score) -> revision -> re-review -> approved."""

    @pytest.mark.asyncio
    async def test_rejection_and_rework_lifecycle(self, services):
        db = services["db"]
        review_svc = services["review"]
        workflow_svc = services["workflow"]

        complaint = make_complaint(status="draft")
        db.add_complaint(complaint)
        cid = complaint["id"]

        bearbeiter = make_user("bearbeiter", "proc-1")
        zqm = make_user("zqm", "zqm-1")

        # Move to in_progress
        await workflow_svc.transition(cid, "open", bearbeiter)
        await workflow_svc.transition(cid, "in_progress", bearbeiter)

        # First review — low score → revision_needed
        with patch.object(review_svc, '_call_opus', new_callable=AsyncMock) as mock_opus:
            mock_opus.return_value = MOCK_OPUS_RESPONSE_LOW
            result = await review_svc.request_review(cid, "proc-1", "Bearbeiter", force=True)

        assert result["review"]["new_status"] == "revision_needed"
        assert result["review"]["overall_score"] == 42

        # Rework: revision_needed -> in_progress
        await workflow_svc.transition(cid, "in_progress", bearbeiter)

        # Second review — high score → approval_pending
        with patch.object(review_svc, '_call_opus', new_callable=AsyncMock) as mock_opus:
            mock_opus.return_value = MOCK_OPUS_RESPONSE_HIGH
            result = await review_svc.request_review(cid, "proc-1", "Bearbeiter", force=True)

        assert result["review"]["new_status"] == "approval_pending"

        # Approve
        await workflow_svc.transition(cid, "approved", zqm)

        final = await db.complaints.find_one({"id": cid})
        assert final["status"] == "approved"


class TestE2EIncompleteComplaint:
    """Edge case: review rejected for incomplete D-steps."""

    @pytest.mark.asyncio
    async def test_incomplete_complaint_review_blocked(self, services):
        db = services["db"]
        review_svc = services["review"]

        complaint = make_complaint(status="in_progress", has_d_steps=False)
        db.add_complaint(complaint)

        result = await review_svc.request_review(
            complaint["id"], "user-1", "Test", force=False
        )

        assert result["success"] is False
        assert "missing_sections" in result
        assert len(result["missing_sections"]) > 0


class TestE2EGuardEnforcement:
    """Workflow guards prevent invalid state transitions."""

    @pytest.mark.asyncio
    async def test_cannot_skip_to_approval_without_review(self, services):
        db = services["db"]
        workflow_svc = services["workflow"]

        complaint = make_complaint(status="reviewed")
        # No latest_opus_review → guard should block
        db.add_complaint(complaint)
        zqm = make_user("zqm", "zqm-1")

        with pytest.raises(ValueError, match="Opus-4.6-Bewertung"):
            await workflow_svc.transition(complaint["id"], "approval_pending", zqm)

    @pytest.mark.asyncio
    async def test_cannot_review_without_d_steps(self, services):
        db = services["db"]
        workflow_svc = services["workflow"]

        complaint = make_complaint(status="in_progress", has_d_steps=False)
        db.add_complaint(complaint)
        bearbeiter = make_user("bearbeiter", "proc-1")

        with pytest.raises(ValueError, match="Abschnitte ausgefüllt"):
            await workflow_svc.transition(complaint["id"], "review_pending", bearbeiter)
