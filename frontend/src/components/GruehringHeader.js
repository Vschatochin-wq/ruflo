/**
 * GruehringHeader — Page Header with GÜHRING Branding
 * =====================================================
 * Reusable page header component with title and optional actions.
 */

import React from 'react';

export default function GruehringHeader({ title, subtitle, children }) {
  return (
    <div className="flex items-center justify-between mb-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-800">{title}</h1>
        {subtitle && <p className="text-sm text-gray-500 mt-0.5">{subtitle}</p>}
      </div>
      {children && <div className="flex items-center gap-2">{children}</div>}
    </div>
  );
}
