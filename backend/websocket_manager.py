"""
WebSocketManager -- Real-time Event Broadcasting
=================================================
Manages WebSocket connections and broadcasts events to connected clients.
Supports: complaint updates, status changes, review completions, notifications.

Integration:
    from websocket_manager import WebSocketManager, EventTypes
    ws_manager = WebSocketManager()
    await ws_manager.broadcast(EventTypes.COMPLAINT_UPDATED, {"id": "123", ...})
"""

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Dict, Set, Optional, List, Any

from fastapi import WebSocket

logger = logging.getLogger(__name__)


# -- EVENT TYPE CONSTANTS ----------------------------------------------------

class EventTypes:
    """Alle unterstuetzten WebSocket-Event-Typen."""

    COMPLAINT_CREATED = "complaint.created"
    COMPLAINT_UPDATED = "complaint.updated"
    COMPLAINT_STATUS_CHANGED = "complaint.status_changed"
    COMPLAINT_DELETED = "complaint.deleted"
    REVIEW_COMPLETED = "review.completed"
    DOCUMENT_UPLOADED = "document.uploaded"
    OCR_COMPLETED = "ocr.completed"
    NOTIFICATION = "notification"
    DASHBOARD_REFRESH = "dashboard.refresh"


# -- WEBSOCKET MANAGER -------------------------------------------------------

class WebSocketManager:
    """
    Verwaltet WebSocket-Verbindungen und verteilt Echtzeit-Events
    an verbundene Clients.

    Jeder Benutzer kann mehrere Verbindungen haben (z.B. mehrere Tabs).
    Events koennen an alle Clients, bestimmte Benutzer oder
    rollenbasiert gesendet werden.
    """

    def __init__(self):
        # user_id -> set of active WebSocket connections
        self._connections: Dict[str, Set[WebSocket]] = {}
        # websocket -> set of subscribed channels (e.g. "complaint.123")
        self._subscriptions: Dict[WebSocket, Set[str]] = {}
        self._lock = asyncio.Lock()

    # -- Connection Lifecycle -------------------------------------------------

    async def connect(self, websocket: WebSocket, user_id: str) -> None:
        """
        WebSocket-Verbindung annehmen und registrieren.
        Sendet eine Willkommensnachricht mit Verbindungsstatus.
        """
        await websocket.accept()

        async with self._lock:
            if user_id not in self._connections:
                self._connections[user_id] = set()
            self._connections[user_id].add(websocket)
            self._subscriptions[websocket] = set()

        # Willkommensnachricht senden
        welcome = self._format_message("connection.established", {
            "user_id": user_id,
            "message": "Echtzeit-Verbindung hergestellt",
            "active_connections": self.active_connections,
        })
        await self._safe_send(websocket, welcome)

        logger.info(
            f"WebSocket verbunden: user={user_id}, "
            f"gesamt={self.active_connections} Verbindungen"
        )

    async def disconnect(self, websocket: WebSocket, user_id: str) -> None:
        """Verbindung entfernen und Ressourcen freigeben."""
        async with self._lock:
            if user_id in self._connections:
                self._connections[user_id].discard(websocket)
                if not self._connections[user_id]:
                    del self._connections[user_id]
            self._subscriptions.pop(websocket, None)

        logger.info(
            f"WebSocket getrennt: user={user_id}, "
            f"gesamt={self.active_connections} Verbindungen"
        )

    # -- Broadcasting ---------------------------------------------------------

    async def broadcast(
        self,
        event_type: str,
        data: Dict[str, Any],
        exclude_user: Optional[str] = None,
    ) -> int:
        """
        Event an ALLE verbundenen Clients senden.

        Args:
            event_type: Event-Typ (siehe EventTypes)
            data: Event-Daten
            exclude_user: Benutzer-ID, die ausgeschlossen werden soll

        Returns:
            Anzahl der erfolgreich benachrichtigten Verbindungen
        """
        message = self._format_message(event_type, data)
        sent_count = 0
        dead_connections: list = []

        async with self._lock:
            connections_snapshot = {
                uid: set(sockets)
                for uid, sockets in self._connections.items()
                if uid != exclude_user
            }

        for user_id, sockets in connections_snapshot.items():
            for ws in sockets:
                success = await self._safe_send(ws, message)
                if success:
                    sent_count += 1
                else:
                    dead_connections.append((user_id, ws))

        # Tote Verbindungen entfernen
        for user_id, ws in dead_connections:
            await self.disconnect(ws, user_id)

        logger.debug(
            f"Broadcast [{event_type}] an {sent_count} Verbindungen gesendet"
        )
        return sent_count

    async def send_to_user(
        self,
        user_id: str,
        event_type: str,
        data: Dict[str, Any],
    ) -> int:
        """
        Event an alle Verbindungen eines bestimmten Benutzers senden.

        Returns:
            Anzahl der erfolgreich benachrichtigten Verbindungen
        """
        async with self._lock:
            sockets = set(self._connections.get(user_id, set()))

        if not sockets:
            return 0

        message = self._format_message(event_type, data)
        sent_count = 0
        dead_connections: list = []

        for ws in sockets:
            success = await self._safe_send(ws, message)
            if success:
                sent_count += 1
            else:
                dead_connections.append(ws)

        for ws in dead_connections:
            await self.disconnect(ws, user_id)

        return sent_count

    async def send_to_roles(
        self,
        roles: List[str],
        event_type: str,
        data: Dict[str, Any],
        db,
    ) -> int:
        """
        Event an alle Benutzer mit bestimmten Rollen senden.
        Fragt die users-Collection in MongoDB ab.

        Args:
            roles: Liste von Rollen (z.B. ["zqm_manager", "admin"])
            event_type: Event-Typ
            data: Event-Daten
            db: Motor-Datenbankinstanz

        Returns:
            Anzahl der erfolgreich benachrichtigten Verbindungen
        """
        try:
            users_cursor = db.users.find(
                {"role": {"$in": roles}, "approved": True},
                {"id": 1},
            )
            users = await users_cursor.to_list(length=500)
        except Exception as exc:
            logger.error(f"Fehler beim Abfragen der Benutzer nach Rollen: {exc}")
            return 0

        sent_count = 0
        for user in users:
            uid = user.get("id", "")
            if uid:
                sent_count += await self.send_to_user(uid, event_type, data)

        return sent_count

    # -- Channel Subscriptions ------------------------------------------------

    async def subscribe(self, websocket: WebSocket, channel: str) -> None:
        """Client fuer einen bestimmten Kanal registrieren."""
        async with self._lock:
            if websocket in self._subscriptions:
                self._subscriptions[websocket].add(channel)
                logger.debug(f"WebSocket abonniert: {channel}")

    async def unsubscribe(self, websocket: WebSocket, channel: str) -> None:
        """Client von einem bestimmten Kanal abmelden."""
        async with self._lock:
            if websocket in self._subscriptions:
                self._subscriptions[websocket].discard(channel)
                logger.debug(f"WebSocket abgemeldet: {channel}")

    async def send_to_channel(
        self,
        channel: str,
        event_type: str,
        data: Dict[str, Any],
    ) -> int:
        """
        Event an alle Clients senden, die einen bestimmten Kanal
        abonniert haben.

        Returns:
            Anzahl der erfolgreich benachrichtigten Verbindungen
        """
        message = self._format_message(event_type, data)
        sent_count = 0
        dead_connections: list = []

        async with self._lock:
            subscribed = [
                ws for ws, channels in self._subscriptions.items()
                if channel in channels
            ]

        for ws in subscribed:
            success = await self._safe_send(ws, message)
            if success:
                sent_count += 1
            else:
                dead_connections.append(ws)

        # Finde user_ids fuer tote Verbindungen und raeume auf
        for ws in dead_connections:
            user_id = self._find_user_for_websocket(ws)
            if user_id:
                await self.disconnect(ws, user_id)

        return sent_count

    # -- Properties -----------------------------------------------------------

    @property
    def active_connections(self) -> int:
        """Gesamtanzahl aller aktiven WebSocket-Verbindungen."""
        return sum(len(sockets) for sockets in self._connections.values())

    @property
    def connected_users(self) -> List[str]:
        """Liste aller aktuell verbundenen Benutzer-IDs."""
        return list(self._connections.keys())

    # -- Internal Helpers -----------------------------------------------------

    def _format_message(
        self, event_type: str, data: Dict[str, Any]
    ) -> str:
        """Event-Nachricht im Standardformat erstellen."""
        return json.dumps({
            "type": event_type,
            "data": data,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    async def _safe_send(self, websocket: WebSocket, message: str) -> bool:
        """
        Nachricht sicher an eine WebSocket-Verbindung senden.
        Gibt False zurueck, wenn die Verbindung tot ist.
        """
        try:
            await websocket.send_text(message)
            return True
        except Exception:
            # Verbindung ist tot — wird vom Aufrufer bereinigt
            return False

    def _find_user_for_websocket(self, websocket: WebSocket) -> Optional[str]:
        """Benutzer-ID fuer eine WebSocket-Verbindung finden."""
        for user_id, sockets in self._connections.items():
            if websocket in sockets:
                return user_id
        return None
