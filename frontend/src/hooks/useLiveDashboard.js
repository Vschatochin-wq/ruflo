/**
 * useLiveDashboard -- Live Dashboard Data Hook
 * ==============================================
 * Kombiniert WebSocket-Events mit periodischem Polling
 * fuer Echtzeit-Dashboard-Updates.
 *
 * Usage:
 *   const { isLive, connectionStatus, lastUpdate, triggerRefresh } =
 *     useLiveDashboard({
 *       userId: user.id,
 *       onRefresh: () => fetchDashboardData(),
 *     });
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import { useWebSocket } from './useWebSocket';

// -- Konfiguration -----------------------------------------------------------

/** Mindestabstand zwischen zwei Refreshes (Entprellung) */
const DEBOUNCE_INTERVAL_MS = 3000;

/** Fallback-Polling-Intervall wenn WebSocket getrennt */
const FALLBACK_POLLING_MS = 60000;

/** Event-Typen, die einen Dashboard-Refresh ausloesen */
const REFRESH_EVENTS = [
  'complaint.created',
  'complaint.updated',
  'complaint.status_changed',
  'complaint.deleted',
  'review.completed',
  'document.uploaded',
  'ocr.completed',
  'dashboard.refresh',
];

// -- Hook --------------------------------------------------------------------

/**
 * @param {Object} options
 * @param {string} options.userId - Aktueller Benutzer-ID
 * @param {Function} options.onRefresh - Callback zum Neuladen der Dashboard-Daten
 * @param {number} [options.debounceMs] - Entprellungsintervall (Standard: 3000)
 * @param {number} [options.pollingMs] - Fallback-Polling-Intervall (Standard: 60000)
 */
export function useLiveDashboard({
  userId,
  onRefresh,
  debounceMs = DEBOUNCE_INTERVAL_MS,
  pollingMs = FALLBACK_POLLING_MS,
} = {}) {
  const { isConnected, connectionStatus, subscribe } = useWebSocket(userId);
  const [lastUpdate, setLastUpdate] = useState(null);

  const onRefreshRef = useRef(onRefresh);
  const lastRefreshTimeRef = useRef(0);
  const pendingRefreshRef = useRef(null);
  const pollingTimerRef = useRef(null);
  const mountedRef = useRef(true);

  // onRefresh-Referenz aktuell halten
  useEffect(() => {
    onRefreshRef.current = onRefresh;
  }, [onRefresh]);

  // -- Entprellter Refresh ---------------------------------------------------

  const debouncedRefresh = useCallback(() => {
    if (!mountedRef.current) return;

    const now = Date.now();
    const elapsed = now - lastRefreshTimeRef.current;

    if (elapsed >= debounceMs) {
      // Direkt ausfuehren
      lastRefreshTimeRef.current = now;
      setLastUpdate(new Date());

      if (typeof onRefreshRef.current === 'function') {
        try {
          onRefreshRef.current();
        } catch (err) {
          console.error('[useLiveDashboard] Refresh-Fehler:', err);
        }
      }
    } else {
      // Verzoegert ausfuehren
      if (pendingRefreshRef.current) {
        clearTimeout(pendingRefreshRef.current);
      }
      pendingRefreshRef.current = setTimeout(() => {
        if (mountedRef.current) {
          lastRefreshTimeRef.current = Date.now();
          setLastUpdate(new Date());
          if (typeof onRefreshRef.current === 'function') {
            try {
              onRefreshRef.current();
            } catch (err) {
              console.error('[useLiveDashboard] Refresh-Fehler:', err);
            }
          }
        }
      }, debounceMs - elapsed);
    }
  }, [debounceMs]);

  // -- Manueller Refresh ----------------------------------------------------

  const triggerRefresh = useCallback(() => {
    lastRefreshTimeRef.current = 0; // Entprellung zuruecksetzen
    debouncedRefresh();
  }, [debouncedRefresh]);

  // -- WebSocket-Events abonnieren ------------------------------------------

  useEffect(() => {
    const unsubscribers = REFRESH_EVENTS.map((eventType) =>
      subscribe(eventType, () => {
        debouncedRefresh();
      })
    );

    return () => {
      unsubscribers.forEach((unsub) => {
        if (typeof unsub === 'function') unsub();
      });
    };
  }, [subscribe, debouncedRefresh]);

  // -- Fallback-Polling wenn WebSocket getrennt -----------------------------

  useEffect(() => {
    if (pollingTimerRef.current) {
      clearInterval(pollingTimerRef.current);
      pollingTimerRef.current = null;
    }

    if (!isConnected && userId) {
      pollingTimerRef.current = setInterval(() => {
        if (mountedRef.current && typeof onRefreshRef.current === 'function') {
          try {
            onRefreshRef.current();
            setLastUpdate(new Date());
          } catch (err) {
            console.error('[useLiveDashboard] Polling-Fehler:', err);
          }
        }
      }, pollingMs);
    }

    return () => {
      if (pollingTimerRef.current) {
        clearInterval(pollingTimerRef.current);
        pollingTimerRef.current = null;
      }
    };
  }, [isConnected, userId, pollingMs]);

  // -- Cleanup ---------------------------------------------------------------

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      if (pendingRefreshRef.current) {
        clearTimeout(pendingRefreshRef.current);
      }
    };
  }, []);

  return {
    /** true wenn WebSocket verbunden (Echtzeit-Updates aktiv) */
    isLive: isConnected,
    /** Verbindungsstatus: 'connecting' | 'connected' | 'disconnected' | 'reconnecting' */
    connectionStatus,
    /** Zeitpunkt des letzten erfolgreichen Updates */
    lastUpdate,
    /** Manuellen Refresh ausloesen */
    triggerRefresh,
  };
}

export default useLiveDashboard;
