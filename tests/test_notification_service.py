"""
Tests for NotificationService — In-App Notifications
=====================================================
Covers: create, read, mark, bulk notify, WebSocket push, priority validation.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from conftest import MockDB, make_complaint, make_user
from notification_service import NotificationService, NOTIFICATION_TYPES


@pytest.fixture
def svc(mock_db):
    return NotificationService(mock_db)


# ─── CREATE NOTIFICATION ─────────────────────────────────────────────

class TestCreateNotification:

    @pytest.mark.asyncio
    async def test_creates_with_all_fields(self, svc):
        result = await svc.create_notification(
            user_id="user-1",
            notification_type="new_complaint",
            title="Neue Reklamation",
            message="RK-2026-001 angelegt",
            complaint_id="comp-1",
            priority="high",
            action_url="/complaints/comp-1/view"
        )

        assert result["id"]
        assert result["user_id"] == "user-1"
        assert result["type"] == "new_complaint"
        assert result["title"] == "Neue Reklamation"
        assert result["read"] is False
        assert result["priority"] == "high"

    @pytest.mark.asyncio
    async def test_defaults_to_system_type(self, svc):
        result = await svc.create_notification(
            user_id="user-1",
            notification_type="unknown_type",
            title="Test"
        )
        # Should fallback to system type info without crashing
        assert result["type"] == "unknown_type"
        assert result["type_icon"] == "info"

    @pytest.mark.asyncio
    async def test_invalid_priority_defaults_to_normal(self, svc):
        result = await svc.create_notification(
            user_id="user-1",
            notification_type="system",
            title="Test",
            priority="invalid"
        )
        assert result["priority"] == "normal"

    @pytest.mark.asyncio
    async def test_backward_compat_type_kwarg(self, svc):
        """Support 'type' as kwarg for backward compatibility."""
        result = await svc.create_notification(
            user_id="user-1",
            title="Test",
            type="opus_result"
        )
        assert result["type"] == "opus_result"


# ─── READ / UNREAD ───────────────────────────────────────────────────

class TestReadUnread:

    @pytest.mark.asyncio
    async def test_get_unread_count(self, svc):
        await svc.create_notification("user-1", notification_type="system", title="N1")
        await svc.create_notification("user-1", notification_type="system", title="N2")

        count = await svc.get_unread_count("user-1")
        assert count == 2

    @pytest.mark.asyncio
    async def test_mark_as_read(self, svc):
        notif = await svc.create_notification("user-1", notification_type="system", title="Test")

        success = await svc.mark_as_read(notif["id"], "user-1")
        assert success is True

    @pytest.mark.asyncio
    async def test_mark_as_read_wrong_user_fails(self, svc):
        notif = await svc.create_notification("user-1", notification_type="system", title="Test")

        success = await svc.mark_as_read(notif["id"], "user-2")
        assert success is False

    @pytest.mark.asyncio
    async def test_mark_all_as_read(self, svc):
        await svc.create_notification("user-1", notification_type="system", title="N1")
        await svc.create_notification("user-1", notification_type="system", title="N2")

        count = await svc.mark_all_as_read("user-1")
        assert count == 2


# ─── WEBSOCKET ────────────────────────────────────────────────────────

class TestWebSocket:

    @pytest.mark.asyncio
    async def test_push_to_connected_websocket(self, svc):
        ws = AsyncMock()
        svc.register_websocket("user-1", ws)

        await svc.create_notification("user-1", notification_type="system", title="WS Test")

        ws.send_text.assert_called_once()
        import json
        payload = json.loads(ws.send_text.call_args[0][0])
        assert payload["type"] == "notification"
        assert payload["data"]["title"] == "WS Test"

    def test_register_and_unregister(self, svc):
        ws = MagicMock()
        svc.register_websocket("user-1", ws)
        assert "user-1" in svc._websocket_connections

        svc.unregister_websocket("user-1", ws)
        assert "user-1" not in svc._websocket_connections

    @pytest.mark.asyncio
    async def test_dead_websocket_cleaned_up(self, svc):
        ws = AsyncMock()
        ws.send_text.side_effect = Exception("Connection closed")
        svc.register_websocket("user-1", ws)

        await svc.create_notification("user-1", notification_type="system", title="Test")

        # Dead connection should be removed
        assert "user-1" not in svc._websocket_connections


# ─── BULK NOTIFICATIONS ──────────────────────────────────────────────

class TestBulkNotify:

    @pytest.mark.asyncio
    async def test_notify_role(self, svc, mock_db):
        mock_db.add_user({"id": "u1", "role": "zqm", "approved": True})
        mock_db.add_user({"id": "u2", "role": "zqm", "approved": True})
        mock_db.add_user({"id": "u3", "role": "bearbeiter", "approved": True})

        count = await svc.notify_role(
            role="zqm",
            notification_type="approval_needed",
            title="Review bereit",
            message="Neue Bewertung"
        )
        assert count == 2

    @pytest.mark.asyncio
    async def test_notify_complaint_stakeholders(self, svc):
        complaint = make_complaint()

        count = await svc.notify_complaint_stakeholders(
            complaint=complaint,
            notification_type="status_change",
            title="Status geändert",
            message="In Bearbeitung"
        )
        # created_by + assigned_zqm + assigned_processor (deduplicated)
        assert count >= 2

    @pytest.mark.asyncio
    async def test_notify_stakeholders_excludes_user(self, svc):
        complaint = make_complaint(created_by="user-1", assigned_zqm_id="user-1")

        count = await svc.notify_complaint_stakeholders(
            complaint=complaint,
            notification_type="status_change",
            title="Test",
            message="Test",
            exclude_user_id="user-1"
        )
        # user-1 excluded, only proc-1 should get notification
        assert count >= 1


# ─── NOTIFICATION TYPES ──────────────────────────────────────────────

class TestNotificationTypes:

    def test_all_types_have_required_fields(self):
        for type_key, type_info in NOTIFICATION_TYPES.items():
            assert "icon" in type_info, f"{type_key} missing icon"
            assert "color" in type_info, f"{type_key} missing color"
            assert "label" in type_info, f"{type_key} missing label"

    def test_expected_types_exist(self):
        expected = [
            "new_complaint", "missing_info", "response_received",
            "status_change", "review_required", "opus_result",
            "revision_needed", "approval_needed", "approval",
            "rejection", "escalation", "task_assigned",
            "task_overdue", "complaint_closed", "system"
        ]
        for t in expected:
            assert t in NOTIFICATION_TYPES, f"Missing type: {t}"
