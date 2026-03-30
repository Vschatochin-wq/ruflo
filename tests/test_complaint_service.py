"""
Tests for ComplaintService -- Complaint CRUD & Completeness
============================================================
Covers: create, get, list, update, soft-delete, completeness summary, search.
"""

import pytest
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from conftest import MockDB, make_complaint, make_user
from complaint_service import ComplaintService


@pytest.fixture
def svc(mock_db):
    return ComplaintService(mock_db)


# ---- CREATE ----------------------------------------------------------------

class TestCreateComplaint:

    @pytest.mark.asyncio
    async def test_creates_with_auto_number(self, svc):
        data = {
            "customer_name": "Testkunde GmbH",
            "problem_description": "Bohrer defekt nach 50 Zyklen",
        }

        result = await svc.create_complaint(data, "user-1", "Test User")

        assert result.get("id"), "Created complaint must have an id"
        assert result["complaint_number"].startswith("RK-"), \
            "Complaint number must start with 'RK-'"
        assert result["status"] == "draft", \
            "New complaint must have status 'draft'"
        assert result.get("created_at"), "Must have created_at timestamp"
        assert result.get("updated_at"), "Must have updated_at timestamp"

    @pytest.mark.asyncio
    async def test_creates_with_all_fields(self, svc):
        data = {
            "customer_name": "Bosch Rexroth AG",
            "customer_number": "K-99999",
            "problem_description": "Oberflaechenrisse an Werkstueck",
            "fa_code": "FA-100",
            "artikel_nummer": "ART-5555",
            "message_type": "Q1",
            "error_location": "Warenausgang",
            "affected_quantity": 12,
        }

        result = await svc.create_complaint(data, "user-2", "Bearbeiter A")

        assert result["customer_name"] == "Bosch Rexroth AG", \
            "customer_name must be stored"
        assert result["customer_number"] == "K-99999", \
            "customer_number must be stored"
        assert result["problem_description"] == "Oberflaechenrisse an Werkstueck", \
            "problem_description must be stored"
        assert result["fa_code"] == "FA-100", "fa_code must be stored"
        assert result["artikel_nummer"] == "ART-5555", "artikel_nummer must be stored"
        assert result["message_type"] == "Q1", "message_type must be stored"
        assert result["error_location"] == "Warenausgang", "error_location must be stored"
        assert result["affected_quantity"] == 12, "affected_quantity must be stored"
        assert result["created_by"] == "user-2", "created_by must be stored"
        assert result["created_by_name"] == "Bearbeiter A", "created_by_name must be stored"

    @pytest.mark.asyncio
    async def test_requires_customer_name(self, svc):
        data = {
            "customer_name": "",
            "problem_description": "Some problem",
        }
        with pytest.raises(ValueError, match="Kundenname"):
            await svc.create_complaint(data, "user-1", "Test")

    @pytest.mark.asyncio
    async def test_requires_customer_name_missing_key(self, svc):
        data = {
            "problem_description": "Some problem",
        }
        with pytest.raises(ValueError, match="Kundenname"):
            await svc.create_complaint(data, "user-1", "Test")

    @pytest.mark.asyncio
    async def test_requires_problem_description(self, svc):
        data = {
            "customer_name": "Testkunde",
            "problem_description": "",
        }
        with pytest.raises(ValueError, match="Problembeschreibung"):
            await svc.create_complaint(data, "user-1", "Test")

    @pytest.mark.asyncio
    async def test_requires_problem_description_missing_key(self, svc):
        data = {
            "customer_name": "Testkunde",
        }
        with pytest.raises(ValueError, match="Problembeschreibung"):
            await svc.create_complaint(data, "user-1", "Test")


# ---- GET -------------------------------------------------------------------

class TestGetComplaint:

    @pytest.mark.asyncio
    async def test_returns_complaint(self, svc, mock_db):
        complaint = make_complaint(status="open", complaint_id="comp-abc1")
        mock_db.add_complaint(complaint)

        result = await svc.get_complaint("comp-abc1")

        assert result is not None, "Should return the complaint"
        assert result["id"] == "comp-abc1", "Returned complaint must match requested id"
        assert result["customer_name"] == complaint["customer_name"], \
            "Fields must match stored data"

    @pytest.mark.asyncio
    async def test_raises_for_nonexistent(self, svc):
        with pytest.raises(ValueError, match="nicht gefunden"):
            await svc.get_complaint("nonexistent-id")

    @pytest.mark.asyncio
    async def test_excludes_deleted(self, svc, mock_db):
        complaint = make_complaint(complaint_id="comp-del1")
        complaint["deleted"] = True
        mock_db.add_complaint(complaint)

        with pytest.raises(ValueError, match="geloescht"):
            await svc.get_complaint("comp-del1")


# ---- LIST ------------------------------------------------------------------

class TestListComplaints:

    @pytest.mark.asyncio
    async def test_returns_paginated(self, svc, mock_db):
        for i in range(15):
            c = make_complaint(complaint_id=f"list-{i:04d}")
            mock_db.add_complaint(c)

        result = await svc.list_complaints(page=1, page_size=10)

        assert len(result["items"]) == 10, "Page 1 should return 10 items"
        assert result["total"] == 15, "Total should reflect all complaints"
        assert result["total_pages"] == 2, "15 items / 10 per page = 2 pages"
        assert result["page"] == 1, "Should return requested page number"

    @pytest.mark.asyncio
    async def test_filters_by_status(self, svc, mock_db):
        for status in ["open", "open", "closed"]:
            c = make_complaint(status=status, complaint_id=str(uuid.uuid4()))
            mock_db.add_complaint(c)

        result = await svc.list_complaints(filters={"status": "open"})

        assert result["total"] == 2, "Should only count 'open' complaints"
        for item in result["items"]:
            assert item["status"] == "open", "All returned items must be 'open'"

    @pytest.mark.asyncio
    async def test_excludes_deleted(self, svc, mock_db):
        active = make_complaint(complaint_id="active-1")
        mock_db.add_complaint(active)

        deleted = make_complaint(complaint_id="deleted-1")
        deleted["deleted"] = True
        mock_db.add_complaint(deleted)

        result = await svc.list_complaints()

        assert result["total"] == 1, "Deleted complaints must be excluded"
        assert result["items"][0]["id"] == "active-1", \
            "Only active complaint should appear"

    @pytest.mark.asyncio
    async def test_second_page(self, svc, mock_db):
        for i in range(15):
            c = make_complaint(complaint_id=f"page-{i:04d}")
            mock_db.add_complaint(c)

        result = await svc.list_complaints(page=2, page_size=10)

        assert len(result["items"]) == 5, "Page 2 should return remaining 5 items"
        assert result["page"] == 2, "Should return requested page number"


# ---- UPDATE ----------------------------------------------------------------

class TestUpdateComplaint:

    @pytest.mark.asyncio
    async def test_updates_fields(self, svc, mock_db):
        complaint = make_complaint(complaint_id="upd-001")
        mock_db.add_complaint(complaint)

        result = await svc.update_complaint(
            "upd-001",
            {"customer_name": "Neuer Kundenname"},
            "user-1"
        )

        assert result["customer_name"] == "Neuer Kundenname", \
            "Updated field must reflect new value"

    @pytest.mark.asyncio
    async def test_does_not_clear_existing_with_empty_string(self, svc, mock_db):
        complaint = make_complaint(complaint_id="upd-002")
        complaint["fa_code"] = "FA-123"
        mock_db.add_complaint(complaint)

        result = await svc.update_complaint(
            "upd-002",
            {"fa_code": "", "customer_name": "Updated Name"},
            "user-1"
        )

        assert result["fa_code"] == "FA-123", \
            "Empty string values should not overwrite existing data"

    @pytest.mark.asyncio
    async def test_adds_history_entry(self, svc, mock_db):
        complaint = make_complaint(complaint_id="upd-003")
        complaint["update_history"] = []
        mock_db.add_complaint(complaint)

        await svc.update_complaint(
            "upd-003",
            {"customer_name": "History Test"},
            "user-99"
        )

        updated = await svc.get_complaint("upd-003")
        history = updated.get("update_history", [])
        assert len(history) >= 1, "Update must create a history entry"
        assert history[-1]["changed_by"] == "user-99", \
            "History entry must record who made the change"
        assert "customer_name" in history[-1]["changed_fields"], \
            "History entry must record which fields changed"

    @pytest.mark.asyncio
    async def test_nonexistent_raises(self, svc):
        with pytest.raises(ValueError, match="nicht gefunden"):
            await svc.update_complaint("nonexistent", {"customer_name": "X"}, "user-1")

    @pytest.mark.asyncio
    async def test_cannot_update_internal_fields(self, svc, mock_db):
        complaint = make_complaint(complaint_id="upd-004")
        mock_db.add_complaint(complaint)

        # Trying to update only internal fields should raise because
        # no valid fields remain after filtering
        with pytest.raises(ValueError, match="Keine gueltigen Felder"):
            await svc.update_complaint(
                "upd-004",
                {"id": "hacked", "status": "closed"},
                "user-1"
            )

    @pytest.mark.asyncio
    async def test_cannot_update_deleted(self, svc, mock_db):
        complaint = make_complaint(complaint_id="upd-005")
        complaint["deleted"] = True
        mock_db.add_complaint(complaint)

        with pytest.raises(ValueError, match="Geloescht"):
            await svc.update_complaint(
                "upd-005",
                {"customer_name": "Should fail"},
                "user-1"
            )


# ---- DELETE ----------------------------------------------------------------

class TestDeleteComplaint:

    @pytest.mark.asyncio
    async def test_soft_deletes(self, svc, mock_db):
        complaint = make_complaint(complaint_id="del-001")
        mock_db.add_complaint(complaint)

        result = await svc.delete_complaint("del-001", "user-1")

        assert result["success"] is True, "Soft delete must report success"
        assert result["complaint_id"] == "del-001"
        assert result.get("deleted_at"), "Must record deletion timestamp"

        # Verify the record is marked as deleted in the DB
        raw = await mock_db.complaints.find_one({"id": "del-001"})
        assert raw["deleted"] is True, "Record must be marked deleted=True"
        assert raw["deleted_by"] == "user-1", "Must record who deleted"

    @pytest.mark.asyncio
    async def test_nonexistent_raises(self, svc):
        with pytest.raises(ValueError, match="nicht gefunden"):
            await svc.delete_complaint("nonexistent", "user-1")

    @pytest.mark.asyncio
    async def test_already_deleted_raises(self, svc, mock_db):
        complaint = make_complaint(complaint_id="del-002")
        complaint["deleted"] = True
        mock_db.add_complaint(complaint)

        with pytest.raises(ValueError, match="bereits geloescht"):
            await svc.delete_complaint("del-002", "user-1")


# ---- COMPLETENESS / SUMMARY ------------------------------------------------

class TestComplaintSummary:

    @pytest.mark.asyncio
    async def test_complete_complaint(self, svc, mock_db):
        complaint = make_complaint(has_d_steps=True, complaint_id="sum-001")
        mock_db.add_complaint(complaint)

        result = await svc.get_complaint_summary("sum-001")

        assert result["completeness_percentage"] == 100, \
            "Complaint with all D-steps should be 100% complete"
        assert result["filled_steps"] == result["total_steps"], \
            "All steps should be marked as filled"
        assert result["complaint_id"] == "sum-001"

    @pytest.mark.asyncio
    async def test_empty_complaint(self, svc, mock_db):
        complaint = make_complaint(has_d_steps=False, complaint_id="sum-002")
        mock_db.add_complaint(complaint)

        result = await svc.get_complaint_summary("sum-002")

        assert result["completeness_percentage"] == 0, \
            "Complaint without D-steps should be 0% complete"
        assert result["filled_steps"] == 0, "No steps should be filled"

    @pytest.mark.asyncio
    async def test_partial_complaint(self, svc, mock_db):
        complaint = make_complaint(has_d_steps=False, complaint_id="sum-003")
        # Add only team_members and errors (D1 and D2)
        complaint["team_members"] = [{"name": "Max", "role": "Leiter"}]
        complaint["errors"] = [{"code": "F-001", "description": "Verschleiss"}]
        mock_db.add_complaint(complaint)

        result = await svc.get_complaint_summary("sum-003")

        assert 0 < result["completeness_percentage"] < 100, \
            "Partially filled complaint should have intermediate completeness"
        assert result["filled_steps"] == 2, \
            "Should count exactly the 2 filled D-steps"
        # Verify individual step status
        assert result["steps"]["D1_team"]["filled"] is True
        assert result["steps"]["D2_fehler"]["filled"] is True
        assert result["steps"]["D3_sofortmassnahmen"]["filled"] is False

    @pytest.mark.asyncio
    async def test_nonexistent_raises(self, svc):
        with pytest.raises(ValueError, match="nicht gefunden"):
            await svc.get_complaint_summary("nonexistent")


# ---- SEARCH ----------------------------------------------------------------

class TestSearchComplaints:

    @pytest.mark.asyncio
    async def test_search_empty_query_raises(self, svc):
        with pytest.raises(ValueError, match="Suchbegriff"):
            await svc.search_complaints("")

    @pytest.mark.asyncio
    async def test_search_whitespace_query_raises(self, svc):
        with pytest.raises(ValueError, match="Suchbegriff"):
            await svc.search_complaints("   ")
