/**
 * LiveIndicator -- Real-time Connection Status
 * =============================================
 * Zeigt einen kleinen Punkt mit Statustext an, der den
 * WebSocket-Verbindungsstatus darstellt.
 * Gedacht fuer die Dashboard-Kopfzeile.
 *
 * Usage:
 *   import LiveIndicator from './components/LiveIndicator';
 *   <LiveIndicator connectionStatus="connected" lastUpdate={new Date()} />
 */

import React, { useMemo } from 'react';

// -- Status-Konfiguration ----------------------------------------------------

const STATUS_CONFIG = {
  connected: {
    dotClass: 'bg-green-500',
    pulse: true,
    label: 'Live',
  },
  connecting: {
    dotClass: 'bg-yellow-400',
    pulse: false,
    label: 'Verbinde...',
  },
  reconnecting: {
    dotClass: 'bg-yellow-400',
    pulse: true,
    label: 'Verbinde...',
  },
  disconnected: {
    dotClass: 'bg-gray-400',
    pulse: false,
    label: 'Offline',
  },
};

// -- Hilfsfunktionen ---------------------------------------------------------

function formatLastUpdate(date) {
  if (!date) return 'Kein Update empfangen';
  const now = new Date();
  const diffMs = now - date;
  const diffSec = Math.floor(diffMs / 1000);
  const diffMin = Math.floor(diffMs / 60000);

  if (diffSec < 10) return 'Gerade eben aktualisiert';
  if (diffSec < 60) return `Vor ${diffSec} Sek. aktualisiert`;
  if (diffMin < 60) return `Vor ${diffMin} Min. aktualisiert`;
  return `Aktualisiert um ${date.toLocaleTimeString('de-DE', {
    hour: '2-digit',
    minute: '2-digit',
  })}`;
}

// -- Komponente --------------------------------------------------------------

/**
 * @param {Object} props
 * @param {'connecting'|'connected'|'disconnected'|'reconnecting'} props.connectionStatus
 * @param {Date|null} [props.lastUpdate] - Zeitpunkt des letzten Updates
 * @param {string} [props.className] - Zusaetzliche CSS-Klassen
 */
export default function LiveIndicator({
  connectionStatus = 'disconnected',
  lastUpdate = null,
  className = '',
}) {
  const config = STATUS_CONFIG[connectionStatus] || STATUS_CONFIG.disconnected;
  const tooltipText = useMemo(
    () => formatLastUpdate(lastUpdate),
    [lastUpdate]
  );

  return (
    <div
      className={`inline-flex items-center gap-1.5 px-2 py-1 rounded-full text-xs font-medium select-none ${className}`}
      title={tooltipText}
      role="status"
      aria-label={`Verbindungsstatus: ${config.label}`}
    >
      {/* Status-Punkt */}
      <span className="relative flex h-2 w-2">
        {config.pulse && (
          <span
            className={`absolute inline-flex h-full w-full rounded-full opacity-75 motion-safe:animate-ping ${config.dotClass}`}
          />
        )}
        <span
          className={`relative inline-flex rounded-full h-2 w-2 ${config.dotClass}`}
        />
      </span>

      {/* Status-Text */}
      <span
        className={
          connectionStatus === 'connected'
            ? 'text-green-700'
            : connectionStatus === 'disconnected'
            ? 'text-gray-500'
            : 'text-yellow-700'
        }
      >
        {config.label}
      </span>
    </div>
  );
}
