"""
In-App Notification Service
============================
Manages notifications within the system (no external email dependency).
Supports real-time delivery via WebSocket and persistent storage.

Integration:
    from notification_service import NotificationService
    notification_service = NotificationService(db)
    await notification_service.create_notification(user_id, type, title, message, ...)
"""

import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from motor.motor_asyncio import AsyncIOMotorDatabase
import uuid

logger = logging.getLogger(__name__)

# Notification type definitions
NOTIFICATION_TYPES = {
    "new_complaint":     {"icon": "file-plus",  "color": "blue",   "label": "Neue Reklamation"},
    "missing_info":      {"icon": "alert",      "color": "yellow", "label": "Fehlende Informationen"},
    "response_received": {"icon": "mail",       "color": "green",  "label": "Antwort eingegangen"},
    "status_change":     {"icon": "refresh",    "color": "indigo", "label": "Statusänderung"},
    "review_required":   {"icon": "eye",        "color": "purple", "label": "Review erforderlich"},
    "opus_result":       {"icon": "brain",      "color": "violet", "label": "Opus-Bewertung"},
    "revision_needed":   {"icon": "edit",       "color": "orange", "label": "Überarbeitung nötig"},
    "approval_needed":   {"icon": "check-circle","color": "amber", "label": "Freigabe ausstehend"},
    "approval":          {"icon": "check",      "color": "green",  "label": "Freigabe erteilt"},
    "rejection":         {"icon": "x-circle",   "color": "red",    "label": "Freigabe abgelehnt"},
    "escalation":        {"icon": "alert-triangle","color": "red", "label": "Eskalation"},
    "task_assigned":     {"icon": "user-plus",  "color": "blue",   "label": "Aufgabe zugewiesen"},
    "task_overdue":      {"icon": "clock",      "color": "red",    "label": "Aufgabe überfällig"},
    "complaint_closed":  {"icon": "archive",    "color": "green",  "label": "Reklamation abgeschlossen"},
    "system":            {"icon": "info",       "color": "gray",   "label": "Systemmeldung"},
}


class NotificationService:
    """
    In-app notification service with WebSocket support.

    All notifications are stored in MongoDB and can be
    delivered in real-time via WebSocket connections.
    """

    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.collection = db.notifications
        self._websocket_connections: Dict[str, list] = {}  # user_id -> [websockets]

    async def create_indexes(self):
        """Create database indexes."""
        await self.collection.create_index("user_id")
        await self.collection.create_index("read")
        await self.collection.create_index("created_at")
        await self.collection.create_index([("user_id", 1), ("read", 1)])
        await self.collection.create_index([("user_id", 1), ("created_at", -1)])

    VALID_PRIORITIES = {"low", "normal", "high", "urgent"}

    async def create_notification(
        self,
        user_id: str,
        notification_type: str = "",
        title: str = "",
        message: str = "",
        complaint_id: Optional[str] = None,
        priority: str = "normal",
        action_url: Optional[str] = None,
        metadata: Optional[Dict] = None,
        # Accept 'type' as kwarg for backward compatibility
        **kwargs
    ) -> Dict[str, Any]:
        """
        Create and store a new notification.

        Args:
            user_id: Target user ID
            notification_type: Notification type (see NOTIFICATION_TYPES)
            title: Notification title
            message: Notification body
            complaint_id: Related complaint ID
            priority: low, normal, high, urgent
            action_url: URL to navigate to on click
            metadata: Additional data
        """
        # Support 'type' kwarg for backward compat with callers
        notification_type = notification_type or kwargs.get("type", "system")
        if priority not in self.VALID_PRIORITIES:
            priority = "normal"
        type_info = NOTIFICATION_TYPES.get(notification_type, NOTIFICATION_TYPES["system"])

        notification = {
            "id": str(uuid.uuid4()),
            "user_id": user_id,
            "type": notification_type,
            "type_label": type_info["label"],
            "type_icon": type_info["icon"],
            "type_color": type_info["color"],
            "title": title,
            "message": message,
            "complaint_id": complaint_id,
            "priority": priority,
            "action_url": action_url or "",
            "read": False,
            "read_at": None,
            "metadata": metadata or {},
            "created_at": datetime.now(timezone.utc).isoformat()
        }

        await self.collection.insert_one(notification)

        # Attempt real-time delivery via WebSocket
        await self._push_to_websocket(user_id, notification)

        logger.info(f"Notification created: [{notification_type}] {title} → user {user_id}")
        return notification

    async def get_notifications(
        self,
        user_id: str,
        unread_only: bool = False,
        limit: int = 50,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Get notifications for a user."""
        query = {"user_id": user_id}
        if unread_only:
            query["read"] = False

        cursor = self.collection.find(query, {"_id": 0}).sort(
            "created_at", -1
        ).skip(offset).limit(limit)

        return await cursor.to_list(length=limit)

    async def get_unread_count(self, user_id: str) -> int:
        """Get count of unread notifications."""
        return await self.collection.count_documents(
            {"user_id": user_id, "read": False}
        )

    async def mark_as_read(self, notification_id: str, user_id: str) -> bool:
        """Mark a single notification as read."""
        result = await self.collection.update_one(
            {"id": notification_id, "user_id": user_id},
            {"$set": {"read": True, "read_at": datetime.now(timezone.utc).isoformat()}}
        )
        return result.modified_count > 0

    async def mark_all_as_read(self, user_id: str) -> int:
        """Mark all notifications as read for a user."""
        result = await self.collection.update_many(
            {"user_id": user_id, "read": False},
            {"$set": {"read": True, "read_at": datetime.now(timezone.utc).isoformat()}}
        )
        return result.modified_count

    async def delete_notification(self, notification_id: str, user_id: str) -> bool:
        """Delete a notification."""
        result = await self.collection.delete_one(
            {"id": notification_id, "user_id": user_id}
        )
        return result.deleted_count > 0

    async def delete_old_notifications(self, days: int = 90) -> int:
        """Delete notifications older than specified days."""
        from datetime import timedelta
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        result = await self.collection.delete_many(
            {"created_at": {"$lt": cutoff}, "read": True}
        )
        logger.info(f"Deleted {result.deleted_count} old notifications")
        return result.deleted_count

    # ─── WEBSOCKET MANAGEMENT ────────────────────────────────────────

    def register_websocket(self, user_id: str, websocket):
        """Register a WebSocket connection for real-time notifications."""
        if user_id not in self._websocket_connections:
            self._websocket_connections[user_id] = []
        self._websocket_connections[user_id].append(websocket)
        logger.info(f"WebSocket registered for user {user_id}")

    def unregister_websocket(self, user_id: str, websocket):
        """Remove a WebSocket connection."""
        if user_id in self._websocket_connections:
            self._websocket_connections[user_id] = [
                ws for ws in self._websocket_connections[user_id] if ws != websocket
            ]
            if not self._websocket_connections[user_id]:
                del self._websocket_connections[user_id]

    async def _push_to_websocket(self, user_id: str, notification: Dict):
        """Push notification to connected WebSocket clients."""
        if user_id not in self._websocket_connections:
            return

        import json
        payload = json.dumps({
            "type": "notification",
            "data": {k: v for k, v in notification.items() if k != "_id"}
        })

        dead_connections = []
        for ws in self._websocket_connections[user_id]:
            try:
                await ws.send_text(payload)
            except Exception:
                dead_connections.append(ws)

        # Clean up dead connections
        for ws in dead_connections:
            self.unregister_websocket(user_id, ws)

    # ─── BULK NOTIFICATION HELPERS ────────────────────────────────────

    async def notify_role(
        self,
        role: str,
        notification_type: str = "",
        title: str = "",
        message: str = "",
        **kwargs
    ) -> int:
        """Send notification to all users with a specific role."""
        # Support 'type' kwarg for backward compat
        notification_type = notification_type or kwargs.pop("type", "system")
        users = await self.db.users.find(
            {"role": role, "approved": True},
            {"id": 1}
        ).to_list(length=100)

        count = 0
        for user in users:
            try:
                await self.create_notification(
                    user_id=user.get("id", ""),
                    notification_type=notification_type,
                    title=title,
                    message=message,
                    **kwargs
                )
                count += 1
            except Exception as e:
                logger.warning(f"Failed to notify user {user.get('id')}: {e}")
        return count

    async def notify_complaint_stakeholders(
        self,
        complaint: Dict,
        notification_type: str = "",
        title: str = "",
        message: str = "",
        exclude_user_id: Optional[str] = None,
        **kwargs
    ) -> int:
        """Notify all stakeholders of a complaint."""
        # Support 'type' kwarg for backward compat
        notification_type = notification_type or kwargs.pop("type", "system")
        user_ids = set()

        for field in ["assigned_zqm", "assigned_processor"]:
            ref = complaint.get(field, {})
            if isinstance(ref, dict) and ref.get("user_id"):
                user_ids.add(ref["user_id"])

        if complaint.get("created_by"):
            user_ids.add(complaint["created_by"])

        if exclude_user_id:
            user_ids.discard(exclude_user_id)

        count = 0
        for uid in user_ids:
            try:
                await self.create_notification(
                    user_id=uid,
                    notification_type=notification_type,
                    title=title,
                    message=message,
                    complaint_id=complaint.get("id"),
                    **kwargs
                )
                count += 1
            except Exception as e:
                logger.warning(f"Failed to notify user {uid}: {e}")
        return count
