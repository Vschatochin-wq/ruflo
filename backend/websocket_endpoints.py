"""
WebSocket Endpoints -- Real-time Connection Handler
====================================================
WebSocket-Endpunkt fuer Echtzeit-Dashboard-Updates.

Unterstuetzte Client-Nachrichten:
    {"type": "ping"}                                    -> Pong-Antwort
    {"type": "subscribe", "channel": "complaint.123"}   -> Kanal abonnieren
    {"type": "unsubscribe", "channel": "complaint.123"} -> Kanal abmelden

Integration in main.py:
    from websocket_manager import WebSocketManager
    from websocket_endpoints import create_websocket_router

    ws_manager = WebSocketManager()
    ws_router = create_websocket_router(ws_manager)
    app.include_router(ws_router, prefix="/api/v1")
"""

import json
import logging
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query

from websocket_manager import WebSocketManager

logger = logging.getLogger(__name__)

# Erlaubte Kanal-Praefix-Muster (Validierung)
ALLOWED_CHANNEL_PREFIXES = (
    "complaint.",
    "review.",
    "document.",
    "dashboard.",
)


def create_websocket_router(ws_manager: WebSocketManager) -> APIRouter:
    """
    Erstellt den WebSocket-Router mit Verbindungs- und Status-Endpunkten.

    Args:
        ws_manager: WebSocketManager-Instanz fuer Verbindungsverwaltung
    """
    router = APIRouter(tags=["websocket"])

    @router.websocket("/ws")
    async def websocket_endpoint(
        websocket: WebSocket,
        user_id: Optional[str] = Query(None),
        token: Optional[str] = Query(None),
    ):
        """
        Haupt-WebSocket-Endpunkt fuer Echtzeit-Updates.

        Query-Parameter:
            user_id: Benutzer-ID (Pflicht)
            token: Authentifizierungs-Token (optional, fuer spaetere JWT-Validierung)
        """
        # Benutzer-ID validieren
        if not user_id or not user_id.strip():
            await websocket.close(code=4001, reason="user_id ist erforderlich")
            return

        user_id = user_id.strip()

        # Verbindung registrieren
        await ws_manager.connect(websocket, user_id)

        try:
            # Keep-alive-Schleife: auf Client-Nachrichten warten
            while True:
                raw = await websocket.receive_text()
                await _handle_client_message(ws_manager, websocket, user_id, raw)

        except WebSocketDisconnect:
            logger.debug(f"Client getrennt: user={user_id}")
        except Exception as exc:
            logger.warning(f"WebSocket-Fehler fuer user={user_id}: {exc}")
        finally:
            await ws_manager.disconnect(websocket, user_id)

    @router.get("/ws/status")
    async def ws_status():
        """
        WebSocket-Verbindungsstatus abfragen.

        Returns:
            Anzahl aktiver Verbindungen und verbundene Benutzer.
        """
        return {
            "active_connections": ws_manager.active_connections,
            "connected_users": ws_manager.connected_users,
            "connected_user_count": len(ws_manager.connected_users),
        }

    return router


async def _handle_client_message(
    ws_manager: WebSocketManager,
    websocket: WebSocket,
    user_id: str,
    raw: str,
) -> None:
    """
    Eingehende Client-Nachricht verarbeiten.

    Unterstuetzte Nachrichtentypen:
        ping        -> Pong-Antwort
        subscribe   -> Kanal abonnieren
        unsubscribe -> Kanal abmelden
    """
    try:
        message = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        await _send_error(websocket, "Ungueltige JSON-Nachricht")
        return

    msg_type = message.get("type", "")

    if msg_type == "ping":
        await websocket.send_text(json.dumps({"type": "pong"}))

    elif msg_type == "subscribe":
        channel = message.get("channel", "")
        if _validate_channel(channel):
            await ws_manager.subscribe(websocket, channel)
            await websocket.send_text(json.dumps({
                "type": "subscribed",
                "channel": channel,
            }))
            logger.debug(f"user={user_id} abonniert: {channel}")
        else:
            await _send_error(websocket, f"Ungueltiger Kanal: {channel}")

    elif msg_type == "unsubscribe":
        channel = message.get("channel", "")
        if channel:
            await ws_manager.unsubscribe(websocket, channel)
            await websocket.send_text(json.dumps({
                "type": "unsubscribed",
                "channel": channel,
            }))
            logger.debug(f"user={user_id} abgemeldet: {channel}")

    elif msg_type == "auth":
        # Token-Authentifizierung (Platzhalter fuer spaetere JWT-Validierung)
        await websocket.send_text(json.dumps({
            "type": "auth_ack",
            "status": "ok",
        }))

    else:
        await _send_error(websocket, f"Unbekannter Nachrichtentyp: {msg_type}")


def _validate_channel(channel: str) -> bool:
    """Prueft, ob ein Kanal-Name einem erlaubten Muster entspricht."""
    if not channel or not isinstance(channel, str):
        return False
    return channel.startswith(ALLOWED_CHANNEL_PREFIXES)


async def _send_error(websocket: WebSocket, message: str) -> None:
    """Fehlernachricht an den Client senden."""
    try:
        await websocket.send_text(json.dumps({
            "type": "error",
            "message": message,
        }))
    except Exception:
        pass  # Verbindung moeglicherweise bereits getrennt
