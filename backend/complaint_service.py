"""
Complaint CRUD Service
======================
Full lifecycle management for 8D complaints: create, read, update,
soft-delete, search, and completeness tracking.

Integration:
    from complaint_service import ComplaintService
    complaint_service = ComplaintService(db)
    result = await complaint_service.create_complaint(data, user_id, user_name)
"""

import logging
import math
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from motor.motor_asyncio import AsyncIOMotorDatabase

logger = logging.getLogger(__name__)

# Validierungsmuster
COMPLAINT_ID_PATTERN = re.compile(r'^[a-zA-Z0-9\-]{1,64}$')

# D-Schritte und deren Felder fuer Vollstaendigkeitspruefung
D_STEPS = {
    "D1_team": {"field": "team_members", "label": "Team", "required": True},
    "D2_fehler": {"field": "errors", "label": "Fehlerbeschreibung", "required": True},
    "D3_sofortmassnahmen": {"field": "immediate_actions", "label": "Sofortmassnahmen", "required": True},
    "D4_ursachen": {"field": "causes", "label": "Ursachenanalyse", "required": True},
    "D5_korrektur": {"field": "corrective_actions", "label": "Korrekturmassnahmen", "required": True},
    "D6_wirksamkeit": {"field": "verification", "label": "Wirksamkeitspruefung", "required": False},
    "D7_praevention": {"field": "preventive_actions", "label": "Vorbeugungsmassnahmen", "required": False},
    "D8_abschluss": {"field": "closure", "label": "Abschluss", "required": False},
}

# Felder, die bei Updates nicht ueberschrieben werden duerfen
INTERNAL_FIELDS = {
    "id", "complaint_number", "created_at", "created_by", "created_by_name",
    "deleted", "deleted_at", "deleted_by", "status", "status_history",
    "update_history", "latest_opus_review", "approval",
}


def _validate_complaint_id(complaint_id: str) -> str:
    """Reklamations-ID validieren."""
    if not complaint_id or not COMPLAINT_ID_PATTERN.match(complaint_id):
        raise ValueError(f"Ungueltige Reklamations-ID: {complaint_id}")
    return complaint_id


class ComplaintService:
    """
    CRUD-Service fuer Reklamationen mit Volltextsuche und
    Vollstaendigkeitspruefung.

    Usage:
        service = ComplaintService(db)
        complaint = await service.create_complaint(data, "user-1", "Max Mustermann")
        complaints = await service.list_complaints(filters={}, page=1, page_size=20)
    """

    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.collection = db.complaints

    async def create_indexes(self):
        """Datenbankindizes fuer Performance anlegen."""
        await self.collection.create_index("id", unique=True)
        await self.collection.create_index("complaint_number", unique=True)
        await self.collection.create_index("status")
        await self.collection.create_index("customer_name")
        await self.collection.create_index("created_at")
        await self.collection.create_index("deleted")
        await self.collection.create_index([
            ("customer_name", "text"),
            ("complaint_number", "text"),
            ("problem_description", "text"),
        ])

    # ─── COMPLAINT NUMBER GENERATION ─────────────────────────────────

    async def _generate_complaint_number(self) -> str:
        """
        Automatische Reklamationsnummer im Format RK-YYYY-NNNN generieren.
        Zaehler ist pro Jahr fortlaufend.
        """
        year = datetime.now(timezone.utc).year
        prefix = f"RK-{year}-"

        # Hoechste bestehende Nummer im aktuellen Jahr finden
        latest = await self.collection.find_one(
            {"complaint_number": {"$regex": f"^{prefix}"}},
            sort=[("complaint_number", -1)]
        )

        if latest:
            try:
                last_number = int(latest["complaint_number"].split("-")[-1])
                next_number = last_number + 1
            except (ValueError, IndexError):
                next_number = 1
        else:
            next_number = 1

        return f"{prefix}{next_number:04d}"

    # ─── CREATE ──────────────────────────────────────────────────────

    async def create_complaint(
        self,
        data: Dict[str, Any],
        user_id: str,
        user_name: str
    ) -> Dict[str, Any]:
        """
        Neue Reklamation anlegen.

        Args:
            data: Reklamationsdaten (customer_name, problem_description, etc.)
            user_id: ID des anlegenden Benutzers
            user_name: Anzeigename des Benutzers

        Returns:
            Angelegte Reklamation als Dict

        Raises:
            ValueError: Bei fehlenden Pflichtfeldern
        """
        # Pflichtfeldvalidierung
        customer_name = (data.get("customer_name") or "").strip()
        if not customer_name:
            raise ValueError("Kundenname ist ein Pflichtfeld")

        problem_description = (data.get("problem_description") or "").strip()
        if not problem_description:
            raise ValueError("Problembeschreibung ist ein Pflichtfeld")

        now = datetime.now(timezone.utc).isoformat()
        complaint_id = str(uuid.uuid4())
        complaint_number = await self._generate_complaint_number()

        complaint = {
            "id": complaint_id,
            "complaint_number": complaint_number,
            "status": "draft",
            "customer_name": customer_name,
            "customer_number": (data.get("customer_number") or "").strip(),
            "problem_description": problem_description,
            "message_type": data.get("message_type", "Q3"),
            "report_type": data.get("report_type", "8D"),
            "fa_code": data.get("fa_code", ""),
            "artikel_nummer": data.get("artikel_nummer", ""),
            "article_number": data.get("article_number", ""),
            "error_location": data.get("error_location", ""),
            "affected_quantity": data.get("affected_quantity", 0),
            "delivered_quantity": data.get("delivered_quantity", 0),
            "detection_date": data.get("detection_date", ""),
            "assigned_zqm": data.get("assigned_zqm"),
            "assigned_processor": data.get("assigned_processor"),
            "created_by": user_id,
            "created_by_name": user_name,
            "created_at": now,
            "updated_at": now,
            "deleted": False,
            "status_history": [{
                "from": None,
                "to": "draft",
                "changed_by": user_id,
                "changed_at": now,
                "reason": "Reklamation angelegt"
            }],
            "update_history": [],
        }

        await self.collection.insert_one(complaint)
        complaint.pop("_id", None)

        logger.info(
            f"Reklamation angelegt: {complaint_number} von {user_name} ({user_id})"
        )

        return complaint

    # ─── READ ────────────────────────────────────────────────────────

    async def get_complaint(self, complaint_id: str) -> Optional[Dict[str, Any]]:
        """
        Einzelne Reklamation anhand der ID laden.

        Raises:
            ValueError: Bei ungueltiger ID oder geloeschter Reklamation
        """
        _validate_complaint_id(complaint_id)

        complaint = await self.collection.find_one({"id": complaint_id})
        if not complaint:
            raise ValueError("Reklamation nicht gefunden")

        if complaint.get("deleted"):
            raise ValueError("Reklamation wurde geloescht")

        complaint.pop("_id", None)
        return complaint

    # ─── LIST (PAGINATED + FILTERED) ─────────────────────────────────

    async def list_complaints(
        self,
        filters: Optional[Dict[str, Any]] = None,
        page: int = 1,
        page_size: int = 20,
        sort_by: str = "created_at",
        sort_dir: str = "desc"
    ) -> Dict[str, Any]:
        """
        Paginierte und gefilterte Liste von Reklamationen.

        Args:
            filters: Optionale Filter (status, customer_name, complaint_number,
                     assigned_zqm, assigned_processor, date_from, date_to)
            page: Seitennummer (ab 1)
            page_size: Eintraege pro Seite (max 100)
            sort_by: Sortierfeld
            sort_dir: Sortierrichtung ("asc" oder "desc")

        Returns:
            Dict mit items, total, page, page_size, total_pages
        """
        filters = filters or {}
        page = max(1, page)
        page_size = max(1, min(100, page_size))

        # Basis-Query: nur nicht-geloeschte
        query: Dict[str, Any] = {"deleted": {"$ne": True}}

        # Filter aufbauen
        if filters.get("status"):
            query["status"] = filters["status"]

        if filters.get("customer_name"):
            # Teiltext-Suche (case-insensitive)
            query["customer_name"] = {
                "$regex": re.escape(filters["customer_name"]),
                "$options": "i"
            }

        if filters.get("complaint_number"):
            query["complaint_number"] = {
                "$regex": re.escape(filters["complaint_number"]),
                "$options": "i"
            }

        if filters.get("assigned_zqm"):
            query["assigned_zqm.user_id"] = filters["assigned_zqm"]

        if filters.get("assigned_processor"):
            query["assigned_processor.user_id"] = filters["assigned_processor"]

        if filters.get("date_from") or filters.get("date_to"):
            date_filter = {}
            if filters.get("date_from"):
                date_filter["$gte"] = filters["date_from"]
            if filters.get("date_to"):
                date_filter["$lte"] = filters["date_to"]
            query["created_at"] = date_filter

        # Sortierung
        sort_direction = -1 if sort_dir == "desc" else 1
        allowed_sort_fields = {
            "created_at", "updated_at", "complaint_number",
            "customer_name", "status"
        }
        if sort_by not in allowed_sort_fields:
            sort_by = "created_at"

        # Gesamtanzahl
        total = await self.collection.count_documents(query)
        total_pages = max(1, math.ceil(total / page_size))

        # Daten laden
        skip = (page - 1) * page_size
        cursor = self.collection.find(query).sort(
            sort_by, sort_direction
        ).skip(skip).limit(page_size)

        items = await cursor.to_list(length=page_size)
        for item in items:
            item.pop("_id", None)

        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
        }

    # ─── UPDATE ──────────────────────────────────────────────────────

    async def update_complaint(
        self,
        complaint_id: str,
        data: Dict[str, Any],
        user_id: str
    ) -> Dict[str, Any]:
        """
        Reklamation teilweise aktualisieren (Partial Update).
        Leere Werte werden ignoriert, interne Felder koennen nicht
        ueberschrieben werden.

        Args:
            complaint_id: ID der Reklamation
            data: Zu aktualisierende Felder
            user_id: ID des aendernden Benutzers

        Returns:
            Aktualisierte Reklamation

        Raises:
            ValueError: Bei ungueltiger ID oder geloeschter Reklamation
        """
        _validate_complaint_id(complaint_id)

        complaint = await self.collection.find_one({"id": complaint_id})
        if not complaint:
            raise ValueError("Reklamation nicht gefunden")

        if complaint.get("deleted"):
            raise ValueError("Geloeschte Reklamationen koennen nicht bearbeitet werden")

        now = datetime.now(timezone.utc).isoformat()

        # Nur nicht-leere, nicht-interne Felder uebernehmen
        update_fields = {}
        changed_fields = []

        for key, value in data.items():
            if key in INTERNAL_FIELDS:
                continue
            # Leere Strings und None ignorieren (Listen/Dicts erlauben)
            if value is None:
                continue
            if isinstance(value, str) and not value.strip():
                continue
            update_fields[key] = value
            changed_fields.append(key)

        if not update_fields:
            raise ValueError("Keine gueltigen Felder zum Aktualisieren angegeben")

        update_fields["updated_at"] = now

        # History-Eintrag
        history_entry = {
            "changed_by": user_id,
            "changed_at": now,
            "changed_fields": changed_fields,
        }

        await self.collection.update_one(
            {"id": complaint_id},
            {
                "$set": update_fields,
                "$push": {"update_history": history_entry}
            }
        )

        # Aktualisierte Reklamation zurueckgeben
        updated = await self.collection.find_one({"id": complaint_id})
        if updated:
            updated.pop("_id", None)
        return updated

    # ─── SOFT DELETE ─────────────────────────────────────────────────

    async def delete_complaint(
        self,
        complaint_id: str,
        user_id: str
    ) -> Dict[str, Any]:
        """
        Reklamation weich loeschen (Soft Delete).

        Raises:
            ValueError: Bei ungueltiger ID oder bereits geloeschter Reklamation
        """
        _validate_complaint_id(complaint_id)

        complaint = await self.collection.find_one({"id": complaint_id})
        if not complaint:
            raise ValueError("Reklamation nicht gefunden")

        if complaint.get("deleted"):
            raise ValueError("Reklamation ist bereits geloescht")

        now = datetime.now(timezone.utc).isoformat()

        await self.collection.update_one(
            {"id": complaint_id},
            {"$set": {
                "deleted": True,
                "deleted_at": now,
                "deleted_by": user_id,
                "updated_at": now,
            }}
        )

        logger.info(f"Reklamation {complaint_id} geloescht von {user_id}")

        return {
            "success": True,
            "complaint_id": complaint_id,
            "deleted_at": now,
        }

    # ─── COMPLETENESS / SUMMARY ──────────────────────────────────────

    async def get_complaint_summary(
        self,
        complaint_id: str
    ) -> Dict[str, Any]:
        """
        Vollstaendigkeitspruefung: welche D-Schritte sind ausgefuellt?

        Returns:
            Dict mit completeness_percentage, steps (je Schritt filled/label/required)
        """
        _validate_complaint_id(complaint_id)

        complaint = await self.collection.find_one({"id": complaint_id})
        if not complaint:
            raise ValueError("Reklamation nicht gefunden")

        steps = {}
        filled_count = 0
        total_count = len(D_STEPS)

        for step_key, step_info in D_STEPS.items():
            field_value = complaint.get(step_info["field"])
            is_filled = bool(field_value)

            # Leere Listen/Dicts als nicht ausgefuellt werten
            if isinstance(field_value, (list, dict)) and not field_value:
                is_filled = False

            steps[step_key] = {
                "label": step_info["label"],
                "required": step_info["required"],
                "filled": is_filled,
            }

            if is_filled:
                filled_count += 1

        return {
            "complaint_id": complaint_id,
            "complaint_number": complaint.get("complaint_number", ""),
            "status": complaint.get("status", ""),
            "completeness_percentage": round(filled_count / total_count * 100),
            "filled_steps": filled_count,
            "total_steps": total_count,
            "steps": steps,
        }

    # ─── FULL-TEXT SEARCH ────────────────────────────────────────────

    async def search_complaints(
        self,
        query: str,
        page: int = 1,
        page_size: int = 20
    ) -> Dict[str, Any]:
        """
        Volltextsuche ueber complaint_number, customer_name, problem_description.

        Args:
            query: Suchbegriff
            page: Seitennummer
            page_size: Eintraege pro Seite

        Returns:
            Paginierte Suchergebnisse
        """
        if not query or not query.strip():
            raise ValueError("Suchbegriff darf nicht leer sein")

        query = query.strip()
        page = max(1, page)
        page_size = max(1, min(100, page_size))

        # Regex-basierte Suche (fallback wenn kein Text-Index vorhanden)
        escaped = re.escape(query)
        search_query = {
            "deleted": {"$ne": True},
            "$or": [
                {"complaint_number": {"$regex": escaped, "$options": "i"}},
                {"customer_name": {"$regex": escaped, "$options": "i"}},
                {"problem_description": {"$regex": escaped, "$options": "i"}},
            ]
        }

        total = await self.collection.count_documents(search_query)
        total_pages = max(1, math.ceil(total / page_size))

        skip = (page - 1) * page_size
        cursor = self.collection.find(search_query).sort(
            "created_at", -1
        ).skip(skip).limit(page_size)

        items = await cursor.to_list(length=page_size)
        for item in items:
            item.pop("_id", None)

        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
            "query": query,
        }
