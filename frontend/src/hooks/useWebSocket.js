/**
 * useWebSocket -- Real-time WebSocket Connection Hook
 * ====================================================
 * Verwaltet die WebSocket-Verbindung mit automatischer Wiederverbindung,
 * Heartbeat und Event-Abonnements.
 *
 * Usage:
 *   const { isConnected, connectionStatus, lastEvent, subscribe, unsubscribe, send } =
 *     useWebSocket(userId);
 *
 *   // Event abonnieren
 *   useEffect(() => {
 *     const unsub = subscribe('complaint.updated', (data) => {
 *       console.log('Reklamation aktualisiert:', data);
 *     });
 *     return unsub;
 *   }, [subscribe]);
 */

import { useState, useEffect, useCallback, useRef } from 'react';

// -- Konfiguration -----------------------------------------------------------

const WS_URL =
  process.env.REACT_APP_WS_URL ||
  `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}/api/v1/ws`;

const HEARTBEAT_INTERVAL_MS = 30000;
const MAX_RECONNECT_ATTEMPTS = 10;
const BASE_RECONNECT_DELAY_MS = 1000;
const MAX_RECONNECT_DELAY_MS = 30000;

// -- Status-Konstanten -------------------------------------------------------

const STATUS = {
  CONNECTING: 'connecting',
  CONNECTED: 'connected',
  DISCONNECTED: 'disconnected',
  RECONNECTING: 'reconnecting',
};

// -- Hook --------------------------------------------------------------------

export function useWebSocket(userId) {
  const [connectionStatus, setConnectionStatus] = useState(STATUS.DISCONNECTED);
  const [lastEvent, setLastEvent] = useState(null);

  const wsRef = useRef(null);
  const handlersRef = useRef(new Map()); // eventType -> Set<callback>
  const reconnectAttemptRef = useRef(0);
  const reconnectTimerRef = useRef(null);
  const heartbeatTimerRef = useRef(null);
  const mountedRef = useRef(true);
  const userIdRef = useRef(userId);

  // Benutzer-ID aktuell halten
  useEffect(() => {
    userIdRef.current = userId;
  }, [userId]);

  // -- Heartbeat -------------------------------------------------------------

  const startHeartbeat = useCallback(() => {
    stopHeartbeat();
    heartbeatTimerRef.current = setInterval(() => {
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify({ type: 'ping' }));
      }
    }, HEARTBEAT_INTERVAL_MS);
  }, []);

  const stopHeartbeat = useCallback(() => {
    if (heartbeatTimerRef.current) {
      clearInterval(heartbeatTimerRef.current);
      heartbeatTimerRef.current = null;
    }
  }, []);

  // -- Event-Handler aufrufen ------------------------------------------------

  const dispatchEvent = useCallback((eventType, data, fullMessage) => {
    setLastEvent(fullMessage);

    const handlers = handlersRef.current.get(eventType);
    if (handlers) {
      handlers.forEach((cb) => {
        try {
          cb(data, fullMessage);
        } catch (err) {
          console.error(`[useWebSocket] Handler-Fehler fuer "${eventType}":`, err);
        }
      });
    }

    // Wildcard-Handler ("*") erhalten alle Events
    const wildcardHandlers = handlersRef.current.get('*');
    if (wildcardHandlers) {
      wildcardHandlers.forEach((cb) => {
        try {
          cb(data, fullMessage);
        } catch (err) {
          console.error('[useWebSocket] Wildcard-Handler-Fehler:', err);
        }
      });
    }
  }, []);

  // -- Verbindung herstellen ------------------------------------------------

  const connect = useCallback(() => {
    if (!userIdRef.current || !mountedRef.current) return;

    // Bestehende Verbindung schliessen
    if (wsRef.current) {
      wsRef.current.onclose = null;
      wsRef.current.close();
      wsRef.current = null;
    }

    setConnectionStatus(
      reconnectAttemptRef.current > 0 ? STATUS.RECONNECTING : STATUS.CONNECTING
    );

    try {
      const url = `${WS_URL}?user_id=${encodeURIComponent(userIdRef.current)}`;
      const ws = new WebSocket(url);
      wsRef.current = ws;

      ws.onopen = () => {
        if (!mountedRef.current) return;
        reconnectAttemptRef.current = 0;
        setConnectionStatus(STATUS.CONNECTED);
        startHeartbeat();
      };

      ws.onmessage = (event) => {
        if (!mountedRef.current) return;
        try {
          const message = JSON.parse(event.data);
          const eventType = message.type || '';
          const data = message.data || {};
          dispatchEvent(eventType, data, message);
        } catch {
          // Ungueltige Nachricht ignorieren
        }
      };

      ws.onclose = () => {
        if (!mountedRef.current) return;
        wsRef.current = null;
        stopHeartbeat();
        setConnectionStatus(STATUS.DISCONNECTED);

        // Automatische Wiederverbindung mit exponentiellem Backoff
        if (
          userIdRef.current &&
          reconnectAttemptRef.current < MAX_RECONNECT_ATTEMPTS
        ) {
          reconnectAttemptRef.current += 1;
          const delay = Math.min(
            BASE_RECONNECT_DELAY_MS *
              Math.pow(2, reconnectAttemptRef.current) +
              Math.random() * 1000,
            MAX_RECONNECT_DELAY_MS
          );
          setConnectionStatus(STATUS.RECONNECTING);
          reconnectTimerRef.current = setTimeout(connect, delay);
        }
      };

      ws.onerror = () => {
        // onclose wird nach onerror ausgeloest
      };
    } catch {
      setConnectionStatus(STATUS.DISCONNECTED);
    }
  }, [startHeartbeat, stopHeartbeat, dispatchEvent]);

  // -- Oeffentliche API ------------------------------------------------------

  /**
   * Event-Typ abonnieren. Gibt eine Unsubscribe-Funktion zurueck.
   *
   * @param {string} eventType - z.B. "complaint.updated" oder "*" fuer alle
   * @param {Function} callback - Wird mit (data, fullMessage) aufgerufen
   * @returns {Function} Unsubscribe-Funktion
   */
  const subscribe = useCallback((eventType, callback) => {
    if (!handlersRef.current.has(eventType)) {
      handlersRef.current.set(eventType, new Set());
    }
    handlersRef.current.get(eventType).add(callback);

    // Unsubscribe-Funktion zurueckgeben
    return () => {
      const handlers = handlersRef.current.get(eventType);
      if (handlers) {
        handlers.delete(callback);
        if (handlers.size === 0) {
          handlersRef.current.delete(eventType);
        }
      }
    };
  }, []);

  /**
   * Alle Handler fuer einen Event-Typ entfernen.
   *
   * @param {string} eventType
   */
  const unsubscribe = useCallback((eventType) => {
    handlersRef.current.delete(eventType);
  }, []);

  /**
   * Nachricht an den Server senden.
   *
   * @param {Object} message - JSON-serialisierbares Objekt
   * @returns {boolean} true wenn erfolgreich gesendet
   */
  const send = useCallback((message) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(message));
      return true;
    }
    return false;
  }, []);

  // -- Lifecycle -------------------------------------------------------------

  useEffect(() => {
    mountedRef.current = true;

    if (userId) {
      connect();
    }

    return () => {
      mountedRef.current = false;

      if (reconnectTimerRef.current) {
        clearTimeout(reconnectTimerRef.current);
        reconnectTimerRef.current = null;
      }

      stopHeartbeat();

      if (wsRef.current) {
        wsRef.current.onclose = null;
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, [userId, connect, stopHeartbeat]);

  return {
    isConnected: connectionStatus === STATUS.CONNECTED,
    connectionStatus,
    lastEvent,
    subscribe,
    unsubscribe,
    send,
  };
}

export default useWebSocket;
