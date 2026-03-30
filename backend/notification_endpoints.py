"""
Notification REST Endpoints
============================
CRUD endpoints for in-app notifications.

Routes (mounted under /api/v1):
    GET   /notifications              List notifications for current user
    GET   /notifications/unread-count  Unread count
    PATCH /notifications/{id}/read     Mark one notification as read
    PATCH /notifications/read-all      Mark all as read
    DELETE /notifications/{id}         Delete a notification
"""

import logging
from fastapi import APIRouter, HTTPException, Query
from typing import Optional

logger = logging.getLogger(__name__)


def create_notification_routes(notification_service):
    router = APIRouter(tags=["notifications"])

    # Default user for demo (no auth layer yet)
    def _current_user_id():
        return "admin-001"

    @router.get("/notifications")
    async def list_notifications(
        limit: int = Query(50, ge=1, le=200),
        offset: int = Query(0, ge=0),
        unread_only: bool = Query(False),
    ):
        user_id = _current_user_id()
        items = await notification_service.get_notifications(
            user_id=user_id,
            unread_only=unread_only,
            limit=limit,
            offset=offset,
        )
        return {"notifications": items, "count": len(items)}

    @router.get("/notifications/unread-count")
    async def unread_count():
        user_id = _current_user_id()
        count = await notification_service.get_unread_count(user_id)
        return {"unread_count": count}

    @router.patch("/notifications/{notification_id}/read")
    async def mark_read(notification_id: str):
        user_id = _current_user_id()
        success = await notification_service.mark_as_read(notification_id, user_id)
        if not success:
            raise HTTPException(404, "Benachrichtigung nicht gefunden")
        return {"success": True}

    @router.patch("/notifications/read-all")
    async def mark_all_read():
        user_id = _current_user_id()
        count = await notification_service.mark_all_as_read(user_id)
        return {"success": True, "marked_count": count}

    @router.delete("/notifications/{notification_id}")
    async def delete_notification(notification_id: str):
        user_id = _current_user_id()
        success = await notification_service.delete_notification(notification_id, user_id)
        if not success:
            raise HTTPException(404, "Benachrichtigung nicht gefunden")
        return {"success": True}

    return router
