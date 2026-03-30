/**
 * StatusBadge — Einheitliches Status-Badge fuer die gesamte App
 * ==============================================================
 * Zeigt den Status einer Reklamation als farbcodiertes Badge an.
 * Verwendet deutsche Bezeichnungen und konsistente Farben.
 *
 * Usage:
 *   <StatusBadge status="in_progress" />
 *   <StatusBadge status="approved" size="sm" />
 */

import React from 'react';
import { Badge } from './ui/badge';

const STATUS_CONFIG = {
  draft: {
    label: 'Entwurf',
    className: 'bg-gray-100 text-gray-700 border-gray-300',
  },
  open: {
    label: 'Offen',
    className: 'bg-blue-100 text-blue-700 border-blue-300',
  },
  in_progress: {
    label: 'In Bearbeitung',
    className: 'bg-yellow-100 text-yellow-800 border-yellow-300',
  },
  review_pending: {
    label: 'Review ausstehend',
    className: 'bg-orange-100 text-orange-700 border-orange-300',
  },
  approval_pending: {
    label: 'Freigabe ausstehend',
    className: 'bg-purple-100 text-purple-700 border-purple-300',
  },
  approved: {
    label: 'Freigegeben',
    className: 'bg-green-100 text-green-700 border-green-300',
  },
  closed: {
    label: 'Abgeschlossen',
    className: 'bg-emerald-100 text-emerald-800 border-emerald-400',
  },
  rejected: {
    label: 'Abgelehnt',
    className: 'bg-red-100 text-red-700 border-red-300',
  },
  archived: {
    label: 'Archiviert',
    className: 'bg-slate-200 text-slate-600 border-slate-400',
  },
};

export function getStatusLabel(status) {
  return STATUS_CONFIG[status]?.label || status || 'Unbekannt';
}

export function getStatusClassName(status) {
  return STATUS_CONFIG[status]?.className || 'bg-gray-100 text-gray-600 border-gray-300';
}

export default function StatusBadge({ status, size = 'default' }) {
  const config = STATUS_CONFIG[status];
  const label = config?.label || status || 'Unbekannt';
  const colorClass = config?.className || 'bg-gray-100 text-gray-600 border-gray-300';

  return (
    <Badge
      variant="outline"
      className={`${colorClass} ${size === 'sm' ? 'text-[10px] px-1.5 py-0' : 'text-xs px-2 py-0.5'}`}
    >
      {label}
    </Badge>
  );
}
