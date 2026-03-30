"""
Shared test fixtures for 8D Opus Integration tests.
Uses mongomock for in-memory MongoDB simulation.
"""

import pytest
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch


# ─── SAMPLE DATA ──────────────────────────────────────────────────────

def make_complaint(
    status="in_progress",
    complaint_id=None,
    has_d_steps=True,
    created_by="user-1",
    assigned_zqm_id="zqm-1",
    assigned_processor_id="proc-1",
):
    """Create a sample complaint document for testing."""
    cid = complaint_id or str(uuid.uuid4())
    complaint = {
        "id": cid,
        "complaint_number": f"RK-2026-{cid[:4].upper()}",
        "status": status,
        "customer_name": "Test Kunde GmbH",
        "customer_number": "K-12345",
        "fa_code": "FA-001",
        "artikel_nummer": "ART-9876",
        "problem_description": "Bohrer zeigt Verschleiß nach 100 Zyklen",
        "affected_quantity": 50,
        "message_type": "Q3",
        "detection_date": "2026-03-01",
        "error_location": "Wareneingang",
        "created_by": created_by,
        "assigned_zqm": {"user_id": assigned_zqm_id, "name": "ZQM Tester"},
        "assigned_processor": {"user_id": assigned_processor_id, "name": "Bearbeiter Tester"},
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "status_history": [],
    }

    if has_d_steps:
        complaint.update({
            "team_members": [{"name": "Max Müller", "role": "Leiter"}],
            "errors": [{"code": "F-001", "description": "Verschleiß", "category": "Material"}],
            "immediate_actions": [{"code": "S-001", "description": "Los gesperrt", "responsible": "QM", "status": "done", "deadline": "2026-03-05"}],
            "causes": [{"code": "U-001", "description": "Härteprozess fehlerhaft", "category": "Methode"}],
            "five_why": [{"question": "Warum Verschleiß?", "answer": "Härtung unzureichend"}],
            "corrective_actions": [{"code": "K-001", "description": "Härteparameter anpassen", "responsible": "Produktion", "status": "planned", "deadline": "2026-04-01"}],
            "verification": {"method": "Stichprobenprüfung", "result": "Bestanden", "verified_by": "QM"},
            "preventive_actions": [{"code": "V-001", "description": "SPC einführen", "responsible": "QM", "status": "planned", "deadline": "2026-05-01"}],
            "closure": {"lessons_learned": "Härteparameter regelmäßig prüfen", "closed_by": ""},
        })

    return complaint


def make_user(role="bearbeiter", user_id=None):
    """Create a sample user dict."""
    uid = user_id or str(uuid.uuid4())
    return {
        "id": uid,
        "username": f"test_{role}",
        "full_name": f"Test {role.title()}",
        "role": role,
        "approved": True,
    }


def make_review(complaint_id, score=75, recommendation="minor_revision"):
    """Create a sample review record."""
    return {
        "id": str(uuid.uuid4()),
        "complaint_id": complaint_id,
        "complaint_number": f"RK-2026-TEST",
        "model": "claude-opus-4-6",
        "requested_by": "user-1",
        "requested_by_name": "Test User",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "review_data": {
            "overall_score": score,
            "recommendation": recommendation,
            "section_scores": {
                "D1_team": {"score": 80, "status": "gut", "assessment": "OK", "issues": [], "recommendations": []},
                "D4_root_cause": {"score": 60, "status": "akzeptabel", "assessment": "Kann verbessert werden", "issues": ["5-Why unvollständig"], "recommendations": ["Mehr Tiefe"]},
            },
            "consistency_check": {"d4_d5_alignment": True, "detail": "Konsistent"},
            "plausibility_check": {"passed": True, "detail": "Plausibel"},
            "overall_assessment": "Guter Report mit Verbesserungspotential",
            "action_items": ["5-Why vertiefen"],
            "strengths": ["Gute Teamzusammenstellung"],
        },
        "overall_score": score,
        "recommendation": recommendation,
        "action_items_count": 1,
        "review_number": 1,
    }


# ─── MOCK DB ──────────────────────────────────────────────────────────

class MockCollection:
    """In-memory MongoDB collection mock for testing."""

    def __init__(self, data=None):
        self._data = list(data or [])

    def _match(self, doc, query):
        for k, v in query.items():
            if isinstance(v, dict):
                # Handle $ne operator
                if "$ne" in v:
                    if doc.get(k) == v["$ne"]:
                        return False
                continue
            if doc.get(k) != v:
                return False
        return True

    async def find_one(self, query=None, projection=None, sort=None):
        query = query or {}
        matches = [d for d in self._data if self._match(d, query)]
        if sort and matches:
            for key, direction in reversed(sort):
                matches.sort(key=lambda d: d.get(key, ""), reverse=(direction == -1))
        if not matches:
            return None
        result = {k: v for k, v in matches[0].items() if k != "_id"}
        return result

    async def insert_one(self, doc):
        self._data.append(doc)
        return MagicMock(inserted_id="mock-id")

    async def update_one(self, query, update):
        for doc in self._data:
            if self._match(doc, query):
                if "$set" in update:
                    doc.update(update["$set"])
                if "$push" in update:
                    for field, value in update["$push"].items():
                        doc.setdefault(field, []).append(value)
                return MagicMock(modified_count=1)
        return MagicMock(modified_count=0)

    async def update_many(self, query, update):
        count = 0
        for doc in self._data:
            if self._match(doc, query):
                if "$set" in update:
                    doc.update(update["$set"])
                count += 1
        return MagicMock(modified_count=count)

    async def count_documents(self, query=None):
        query = query or {}
        count = 0
        for doc in self._data:
            if self._match(doc, query):
                count += 1
        return count

    async def delete_one(self, query):
        for i, doc in enumerate(self._data):
            if self._match(doc, query):
                self._data.pop(i)
                return MagicMock(deleted_count=1)
        return MagicMock(deleted_count=0)

    def find(self, query=None, projection=None):
        return MockCursor(self._data, query)

    async def create_index(self, *args, **kwargs):
        pass

    def aggregate(self, pipeline):
        return MockCursor(self._data)


class MockCursor:
    """Mock MongoDB cursor."""

    def __init__(self, data, query=None):
        if query:
            self._data = [d for d in data if self._match(d, query)]
        else:
            self._data = list(data)

    @staticmethod
    def _match(doc, query):
        for k, v in query.items():
            if isinstance(v, dict):
                if "$ne" in v and doc.get(k) == v["$ne"]:
                    return False
                continue
            if doc.get(k) != v:
                return False
        return True

    def sort(self, *args):
        return self

    def skip(self, n):
        self._data = self._data[n:]
        return self

    def limit(self, n):
        self._data = self._data[:n]
        return self

    async def to_list(self, length=100):
        return self._data[:length]


class MockDB:
    """Mock AsyncIOMotorDatabase."""

    def __init__(self):
        self.complaints = MockCollection()
        self.opus_reviews = MockCollection()
        self.notifications = MockCollection()
        self.users = MockCollection()
        self.ai_call_logs = MockCollection()
        self.documents = MockCollection()
        self.ocr_results = MockCollection()

    def add_complaint(self, complaint):
        self.complaints._data.append(complaint)

    def add_review(self, review):
        self.opus_reviews._data.append(review)

    def add_user(self, user):
        self.users._data.append(user)


@pytest.fixture
def mock_db():
    return MockDB()


@pytest.fixture
def sample_complaint():
    return make_complaint()


@pytest.fixture
def sample_complaint_incomplete():
    return make_complaint(has_d_steps=False)


@pytest.fixture
def sample_user_admin():
    return make_user("admin", "admin-1")


@pytest.fixture
def sample_user_zqm():
    return make_user("zqm", "zqm-1")


@pytest.fixture
def sample_user_bearbeiter():
    return make_user("bearbeiter", "proc-1")


@pytest.fixture
def sample_user_viewer():
    return make_user("viewer", "viewer-1")
