"""
Workflow State Machine for Complaint Lifecycle
===============================================
Defines valid status transitions with guards and side effects.
Prevents arbitrary status changes and enforces business rules.

Integration: Import in server.py and use for all status updates:
    from workflow_service import WorkflowService
    workflow = WorkflowService(db, notification_service, audit_service)
    await workflow.transition(complaint_id, "review_pending", user)
"""

import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List, Callable
from motor.motor_asyncio import AsyncIOMotorDatabase

logger = logging.getLogger(__name__)

# ─── STATUS DEFINITIONS ──────────────────────────────────────────────

STATUSES = {
    "draft":            {"label": "Entwurf",              "color": "gray"},
    "intake":           {"label": "Eingang",              "color": "blue"},
    "waiting_info":     {"label": "Warte auf Info",       "color": "yellow"},
    "open":             {"label": "Offen",                "color": "blue"},
    "in_progress":      {"label": "In Bearbeitung",       "color": "indigo"},
    "review_pending":   {"label": "Review angefordert",   "color": "purple"},
    "reviewed":         {"label": "Bewertet",             "color": "violet"},
    "revision_needed":  {"label": "Überarbeitung nötig",  "color": "orange"},
    "approval_pending": {"label": "Freigabe ausstehend",  "color": "amber"},
    "approved":         {"label": "Freigegeben",          "color": "green"},
    "rejected":         {"label": "Abgelehnt",            "color": "red"},
    "closed":           {"label": "Abgeschlossen",        "color": "green"},
    "archived":         {"label": "Archiviert",           "color": "slate"},
}

# ─── TRANSITION RULES ────────────────────────────────────────────────
# Format: "from_status": ["allowed_target_1", "allowed_target_2", ...]

TRANSITIONS = {
    "draft":            ["open", "intake"],
    "intake":           ["open", "waiting_info", "draft"],
    "waiting_info":     ["open", "intake"],
    "open":             ["in_progress", "closed"],
    "in_progress":      ["review_pending", "open", "closed"],
    "review_pending":   ["reviewed", "revision_needed", "approval_pending", "in_progress"],
    "reviewed":         ["approval_pending", "revision_needed", "in_progress"],
    "revision_needed":  ["in_progress"],
    "approval_pending": ["approved", "rejected", "in_progress"],
    "approved":         ["closed"],
    "rejected":         ["in_progress", "revision_needed"],
    "closed":           ["archived", "in_progress"],
    "archived":         [],  # Terminal state
}

# ─── ROLE PERMISSIONS FOR TRANSITIONS ────────────────────────────────

TRANSITION_ROLES = {
    # (from, to): [allowed_roles]
    ("in_progress", "review_pending"):   ["admin", "zqm", "bearbeiter"],
    ("review_pending", "reviewed"):      ["admin", "zqm", "system"],
    ("review_pending", "approval_pending"): ["admin", "zqm", "system"],
    ("reviewed", "approval_pending"):    ["admin", "zqm"],
    ("approval_pending", "approved"):    ["admin", "zqm"],
    ("approval_pending", "rejected"):    ["admin", "zqm"],
    ("approved", "closed"):             ["admin", "zqm"],
    ("closed", "archived"):             ["admin", "system"],
    ("closed", "in_progress"):          ["admin", "zqm"],  # Reopen
}

# ─── NOTIFICATION TRIGGERS ───────────────────────────────────────────

NOTIFICATION_EVENTS = {
    "open":             {"type": "new_complaint",    "priority": "normal", "target": "assigned_zqm"},
    "in_progress":      {"type": "status_change",    "priority": "low",    "target": "creator"},
    "review_pending":   {"type": "review_required",  "priority": "high",   "target": "assigned_zqm"},
    "reviewed":         {"type": "opus_result",      "priority": "high",   "target": "assigned_processor"},
    "revision_needed":  {"type": "revision_needed",  "priority": "high",   "target": "assigned_processor"},
    "approval_pending": {"type": "approval_needed",  "priority": "high",   "target": "assigned_zqm"},
    "approved":         {"type": "approval",         "priority": "normal", "target": "all_stakeholders"},
    "rejected":         {"type": "rejection",        "priority": "high",   "target": "assigned_processor"},
    "closed":           {"type": "complaint_closed", "priority": "normal", "target": "all_stakeholders"},
}


class WorkflowService:
    """
    Manages complaint status transitions with validation,
    role checks, audit logging, and notifications.
    """

    def __init__(self, db: AsyncIOMotorDatabase, notification_service=None, audit_service=None):
        self.db = db
        self.notification_service = notification_service
        self.audit_service = audit_service

    async def transition(
        self,
        complaint_id: str,
        target_status: str,
        user: Dict[str, Any],
        reason: str = "",
        metadata: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Transition a complaint to a new status with full validation.

        Args:
            complaint_id: Complaint document ID
            target_status: Desired new status
            user: Current user dict (id, username, role, full_name)
            reason: Optional reason for the transition
            metadata: Optional additional data

        Returns:
            Result dict with success status, old/new status

        Raises:
            ValueError: If transition is invalid
            PermissionError: If user lacks required role
        """
        # 1. Load complaint
        complaint = await self.db.complaints.find_one({"id": complaint_id})
        if not complaint:
            raise ValueError(f"Reklamation {complaint_id} nicht gefunden")

        current_status = complaint.get("status", "draft")

        # 2. Validate target status exists
        if target_status not in STATUSES:
            raise ValueError(
                f"Ungültiger Status: {target_status}. "
                f"Gültige Status: {', '.join(STATUSES.keys())}"
            )

        # 3. Check transition is allowed
        allowed = TRANSITIONS.get(current_status, [])
        if target_status not in allowed:
            raise ValueError(
                f"Übergang von '{STATUSES[current_status]['label']}' nach "
                f"'{STATUSES[target_status]['label']}' ist nicht erlaubt. "
                f"Erlaubte Übergänge: {', '.join(STATUSES[s]['label'] for s in allowed)}"
            )

        # 4. Check role permissions (deny-by-default)
        user_role = user.get("role", "viewer")
        transition_key = (current_status, target_status)
        if transition_key in TRANSITION_ROLES:
            allowed_roles = TRANSITION_ROLES[transition_key]
            if user_role not in allowed_roles:
                raise PermissionError(
                    f"Rolle '{user_role}' darf den Übergang "
                    f"'{current_status}' → '{target_status}' nicht durchführen. "
                    f"Erforderliche Rollen: {', '.join(allowed_roles)}"
                )
        else:
            # Deny-by-default: transitions not explicitly listed require admin
            if user_role not in ["admin", "zqm", "bearbeiter"]:
                raise PermissionError(
                    f"Rolle '{user_role}' hat keine Berechtigung für den Übergang "
                    f"'{current_status}' → '{target_status}'."
                )

        # 5. Run guards (pre-transition checks)
        guard_result = await self._run_guards(complaint, current_status, target_status)
        if not guard_result["passed"]:
            raise ValueError(f"Vorbedingung nicht erfüllt: {guard_result['reason']}")

        # 6. Execute transition
        now = datetime.now(timezone.utc).isoformat()
        update = {
            "$set": {
                "status": target_status,
                "updated_at": now
            },
            "$push": {
                "status_history": {
                    "from": current_status,
                    "to": target_status,
                    "changed_by": user.get("id", ""),
                    "changed_by_name": user.get("full_name", user.get("username", "")),
                    "changed_at": now,
                    "reason": reason,
                    "metadata": metadata
                }
            }
        }

        await self.db.complaints.update_one({"id": complaint_id}, update)

        # 7. Audit log
        if self.audit_service:
            await self.audit_service.log(
                action_type="STATUS_CHANGE",
                resource_type="complaint",
                resource_id=complaint_id,
                user_id=user.get("id"),
                username=user.get("username"),
                user_role=user_role,
                change_details={
                    "from_status": current_status,
                    "to_status": target_status,
                    "reason": reason
                }
            )

        # 8. Trigger notifications
        await self._trigger_notifications(complaint, current_status, target_status, user)

        logger.info(
            f"Workflow transition: {complaint.get('complaint_number', complaint_id)} "
            f"{current_status} → {target_status} by {user.get('username', '?')}"
        )

        return {
            "success": True,
            "complaint_id": complaint_id,
            "previous_status": current_status,
            "new_status": target_status,
            "changed_by": user.get("full_name", user.get("username")),
            "changed_at": now
        }

    async def get_allowed_transitions(
        self,
        complaint_id: str,
        user_role: str
    ) -> List[Dict[str, str]]:
        """Get list of allowed next statuses for a complaint and user role."""
        complaint = await self.db.complaints.find_one({"id": complaint_id})
        if not complaint:
            return []

        current = complaint.get("status", "draft")
        allowed = TRANSITIONS.get(current, [])

        result = []
        for target in allowed:
            transition_key = (current, target)
            if transition_key in TRANSITION_ROLES:
                if user_role not in TRANSITION_ROLES[transition_key]:
                    continue
            result.append({
                "status": target,
                "label": STATUSES[target]["label"],
                "color": STATUSES[target]["color"]
            })

        return result

    async def get_status_info(self, status: str) -> Dict[str, Any]:
        """Get metadata about a status."""
        if status not in STATUSES:
            return {"error": f"Unknown status: {status}"}
        info = STATUSES[status].copy()
        info["allowed_transitions"] = [
            {"status": s, "label": STATUSES[s]["label"]}
            for s in TRANSITIONS.get(status, [])
        ]
        return info

    async def _run_guards(
        self,
        complaint: Dict,
        from_status: str,
        to_status: str
    ) -> Dict[str, Any]:
        """Run pre-transition validation guards."""

        # Guard: review_pending requires minimum D-steps filled
        if to_status == "review_pending":
            required = ["team_members", "errors", "immediate_actions", "causes", "corrective_actions"]
            missing = [f for f in required if not complaint.get(f)]
            if missing:
                return {
                    "passed": False,
                    "reason": (
                        f"Für die Opus-Prüfung müssen folgende Abschnitte ausgefüllt sein: "
                        f"{', '.join(missing)}"
                    )
                }

        # Guard: approval requires at least one Opus review
        if to_status in ["approved", "approval_pending"] and from_status == "reviewed":
            if not complaint.get("latest_opus_review"):
                return {
                    "passed": False,
                    "reason": "Freigabe erfordert mindestens eine Opus-4.6-Bewertung"
                }

        # Guard: closing requires approval
        if to_status == "closed" and from_status == "approved":
            approval = complaint.get("approval", {})
            if approval.get("status") != "approved":
                return {
                    "passed": False,
                    "reason": "Abschluss erfordert eine vorherige Freigabe"
                }

        return {"passed": True, "reason": ""}

    async def _trigger_notifications(
        self,
        complaint: Dict,
        from_status: str,
        to_status: str,
        user: Dict
    ):
        """Create notifications based on status change."""
        if not self.notification_service:
            return

        event = NOTIFICATION_EVENTS.get(to_status)
        if not event:
            return

        complaint_number = complaint.get("complaint_number", complaint.get("id", "?"))
        from_label = STATUSES.get(from_status, {}).get("label", from_status)
        to_label = STATUSES.get(to_status, {}).get("label", to_status)

        notification_data = {
            "type": event["type"],
            "title": f"Reklamation {complaint_number}: {to_label}",
            "message": (
                f"Status geändert: {from_label} → {to_label} "
                f"von {user.get('full_name', user.get('username', ''))}"
            ),
            "complaint_id": complaint.get("id"),
            "priority": event["priority"],
            "action_url": f"/complaints/{complaint.get('id')}/view"
        }

        # Determine recipients
        target = event["target"]
        recipients = []

        if target == "assigned_zqm":
            zqm = complaint.get("assigned_zqm", {})
            if zqm.get("user_id"):
                recipients.append(zqm["user_id"])

        elif target == "assigned_processor":
            processor = complaint.get("assigned_processor", {})
            if processor.get("user_id"):
                recipients.append(processor["user_id"])

        elif target == "creator":
            if complaint.get("created_by"):
                recipients.append(complaint["created_by"])

        elif target == "all_stakeholders":
            for field in ["assigned_zqm", "assigned_processor"]:
                ref = complaint.get(field, {})
                if ref.get("user_id"):
                    recipients.append(ref["user_id"])
            if complaint.get("created_by"):
                recipients.append(complaint["created_by"])
            recipients = list(set(recipients))  # Deduplicate

        for user_id in recipients:
            await self.notification_service.create_notification(
                user_id=user_id,
                **notification_data
            )
