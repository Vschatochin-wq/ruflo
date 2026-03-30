"""
Tests for WorkflowService — Status State Machine
=================================================
Covers: transition validation, role guards, guards, notifications, audit.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from conftest import MockDB, make_complaint, make_user
from workflow_service import WorkflowService, TRANSITIONS, TRANSITION_ROLES, STATUSES


@pytest.fixture
def workflow(mock_db):
    notification_svc = AsyncMock()
    notification_svc.create_notification = AsyncMock()
    audit_svc = AsyncMock()
    audit_svc.log = AsyncMock()
    return WorkflowService(mock_db, notification_svc, audit_svc)


# ─── VALID TRANSITIONS ───────────────────────────────────────────────

class TestValidTransitions:

    @pytest.mark.asyncio
    async def test_draft_to_open(self, workflow, mock_db):
        complaint = make_complaint(status="draft")
        mock_db.add_complaint(complaint)
        user = make_user("bearbeiter")

        result = await workflow.transition(complaint["id"], "open", user)

        assert result["success"] is True
        assert result["previous_status"] == "draft"
        assert result["new_status"] == "open"

    @pytest.mark.asyncio
    async def test_in_progress_to_review_pending(self, workflow, mock_db):
        complaint = make_complaint(status="in_progress")
        mock_db.add_complaint(complaint)
        user = make_user("bearbeiter")

        result = await workflow.transition(complaint["id"], "review_pending", user)
        assert result["success"] is True
        assert result["new_status"] == "review_pending"

    @pytest.mark.asyncio
    async def test_approval_pending_to_approved_by_zqm(self, workflow, mock_db):
        complaint = make_complaint(status="approval_pending")
        complaint["latest_opus_review"] = {"score": 85}
        mock_db.add_complaint(complaint)
        user = make_user("zqm", "zqm-1")

        result = await workflow.transition(complaint["id"], "approved", user)
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_approved_to_closed(self, workflow, mock_db):
        complaint = make_complaint(status="approved")
        complaint["approval"] = {"status": "approved"}
        mock_db.add_complaint(complaint)
        user = make_user("admin")

        result = await workflow.transition(complaint["id"], "closed", user)
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_full_happy_path(self, workflow, mock_db):
        """E2E: draft -> open -> in_progress -> review_pending -> reviewed -> approval_pending -> approved -> closed -> archived"""
        complaint = make_complaint(status="draft")
        complaint["latest_opus_review"] = {"score": 90}
        complaint["approval"] = {"status": "approved"}
        mock_db.add_complaint(complaint)

        admin = make_user("admin")
        zqm = make_user("zqm", "zqm-1")
        bearbeiter = make_user("bearbeiter")

        path = [
            ("open", bearbeiter),
            ("in_progress", bearbeiter),
            ("review_pending", bearbeiter),
            ("reviewed", zqm),
            ("approval_pending", zqm),
            ("approved", zqm),
            ("closed", admin),
            ("archived", admin),
        ]

        for target, user in path:
            result = await workflow.transition(complaint["id"], target, user)
            assert result["success"] is True, f"Failed at {target}"


# ─── INVALID TRANSITIONS ─────────────────────────────────────────────

class TestInvalidTransitions:

    @pytest.mark.asyncio
    async def test_draft_to_approved_blocked(self, workflow, mock_db):
        complaint = make_complaint(status="draft")
        mock_db.add_complaint(complaint)
        user = make_user("admin")

        with pytest.raises(ValueError, match="nicht erlaubt"):
            await workflow.transition(complaint["id"], "approved", user)

    @pytest.mark.asyncio
    async def test_archived_is_terminal(self, workflow, mock_db):
        complaint = make_complaint(status="archived")
        mock_db.add_complaint(complaint)
        user = make_user("admin")

        with pytest.raises(ValueError, match="nicht erlaubt"):
            await workflow.transition(complaint["id"], "open", user)

    @pytest.mark.asyncio
    async def test_invalid_status_name(self, workflow, mock_db):
        complaint = make_complaint(status="draft")
        mock_db.add_complaint(complaint)
        user = make_user("admin")

        with pytest.raises(ValueError, match="Ungültiger Status"):
            await workflow.transition(complaint["id"], "nonexistent", user)

    @pytest.mark.asyncio
    async def test_complaint_not_found(self, workflow):
        user = make_user("admin")
        with pytest.raises(ValueError, match="nicht gefunden"):
            await workflow.transition("nonexistent-id", "open", user)


# ─── ROLE PERMISSIONS ─────────────────────────────────────────────────

class TestRolePermissions:

    @pytest.mark.asyncio
    async def test_viewer_cannot_approve(self, workflow, mock_db):
        complaint = make_complaint(status="approval_pending")
        mock_db.add_complaint(complaint)
        viewer = make_user("viewer")

        with pytest.raises(PermissionError):
            await workflow.transition(complaint["id"], "approved", viewer)

    @pytest.mark.asyncio
    async def test_bearbeiter_cannot_approve(self, workflow, mock_db):
        complaint = make_complaint(status="approval_pending")
        mock_db.add_complaint(complaint)
        bearbeiter = make_user("bearbeiter")

        with pytest.raises(PermissionError):
            await workflow.transition(complaint["id"], "approved", bearbeiter)

    @pytest.mark.asyncio
    async def test_viewer_blocked_on_unlisted_transition(self, workflow, mock_db):
        """Deny-by-default: transitions not in TRANSITION_ROLES block viewer."""
        complaint = make_complaint(status="draft")
        mock_db.add_complaint(complaint)
        viewer = make_user("viewer")

        with pytest.raises(PermissionError):
            await workflow.transition(complaint["id"], "open", viewer)

    @pytest.mark.asyncio
    async def test_admin_allowed_on_unlisted_transition(self, workflow, mock_db):
        """Admin can perform transitions not explicitly listed."""
        complaint = make_complaint(status="draft")
        mock_db.add_complaint(complaint)
        admin = make_user("admin")

        result = await workflow.transition(complaint["id"], "open", admin)
        assert result["success"] is True


# ─── GUARDS ───────────────────────────────────────────────────────────

class TestGuards:

    @pytest.mark.asyncio
    async def test_review_pending_requires_d_steps(self, workflow, mock_db):
        complaint = make_complaint(status="in_progress", has_d_steps=False)
        mock_db.add_complaint(complaint)
        user = make_user("bearbeiter")

        with pytest.raises(ValueError, match="Abschnitte ausgefüllt"):
            await workflow.transition(complaint["id"], "review_pending", user)

    @pytest.mark.asyncio
    async def test_approval_requires_opus_review(self, workflow, mock_db):
        complaint = make_complaint(status="reviewed")
        # No latest_opus_review field
        mock_db.add_complaint(complaint)
        user = make_user("zqm", "zqm-1")

        with pytest.raises(ValueError, match="Opus-4.6-Bewertung"):
            await workflow.transition(complaint["id"], "approval_pending", user)


# ─── NOTIFICATIONS ────────────────────────────────────────────────────

class TestNotifications:

    @pytest.mark.asyncio
    async def test_transition_triggers_notification(self, workflow, mock_db):
        complaint = make_complaint(status="in_progress")
        mock_db.add_complaint(complaint)
        user = make_user("bearbeiter")

        await workflow.transition(complaint["id"], "review_pending", user)

        workflow.notification_service.create_notification.assert_called()

    @pytest.mark.asyncio
    async def test_no_notification_service_doesnt_crash(self, mock_db):
        wf = WorkflowService(mock_db, notification_service=None, audit_service=None)
        complaint = make_complaint(status="draft")
        mock_db.add_complaint(complaint)
        user = make_user("bearbeiter")

        result = await wf.transition(complaint["id"], "open", user)
        assert result["success"] is True


# ─── AUDIT LOGGING ────────────────────────────────────────────────────

class TestAuditLogging:

    @pytest.mark.asyncio
    async def test_transition_creates_audit_log(self, workflow, mock_db):
        complaint = make_complaint(status="draft")
        mock_db.add_complaint(complaint)
        user = make_user("bearbeiter")

        await workflow.transition(complaint["id"], "open", user)

        workflow.audit_service.log.assert_called_once()
        call_kwargs = workflow.audit_service.log.call_args[1]
        assert call_kwargs["action_type"] == "STATUS_CHANGE"
        assert call_kwargs["resource_id"] == complaint["id"]


# ─── ALLOWED TRANSITIONS ─────────────────────────────────────────────

class TestAllowedTransitions:

    @pytest.mark.asyncio
    async def test_get_allowed_transitions_for_admin(self, workflow, mock_db):
        complaint = make_complaint(status="approval_pending")
        mock_db.add_complaint(complaint)

        transitions = await workflow.get_allowed_transitions(complaint["id"], "admin")
        statuses = [t["status"] for t in transitions]
        assert "approved" in statuses
        assert "rejected" in statuses

    @pytest.mark.asyncio
    async def test_get_allowed_transitions_for_viewer(self, workflow, mock_db):
        complaint = make_complaint(status="approval_pending")
        mock_db.add_complaint(complaint)

        transitions = await workflow.get_allowed_transitions(complaint["id"], "viewer")
        statuses = [t["status"] for t in transitions]
        # Viewer should not see approve/reject
        assert "approved" not in statuses

    @pytest.mark.asyncio
    async def test_nonexistent_complaint_returns_empty(self, workflow):
        transitions = await workflow.get_allowed_transitions("nonexistent", "admin")
        assert transitions == []


# ─── TRANSITION MAP INTEGRITY ─────────────────────────────────────────

class TestTransitionMapIntegrity:

    def test_all_transition_targets_are_valid_statuses(self):
        for source, targets in TRANSITIONS.items():
            assert source in STATUSES, f"{source} not in STATUSES"
            for target in targets:
                assert target in STATUSES, f"{target} (from {source}) not in STATUSES"

    def test_all_role_transitions_exist_in_transition_map(self):
        for (source, target), roles in TRANSITION_ROLES.items():
            assert source in TRANSITIONS, f"{source} not in TRANSITIONS"
            assert target in TRANSITIONS[source], f"{target} not in TRANSITIONS[{source}]"

    def test_archived_is_terminal(self):
        assert TRANSITIONS["archived"] == []
