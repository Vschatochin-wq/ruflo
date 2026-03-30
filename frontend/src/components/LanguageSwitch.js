/**
 * LanguageSwitch — Language Selector Component
 * =============================================
 * Simple language toggle for German/English.
 * Currently displays German only (DE) as the app is German-focused.
 */

import React from 'react';
import { Globe } from 'lucide-react';

export default function LanguageSwitch() {
  return (
    <div className="flex items-center gap-1.5 px-2 py-1 rounded-md text-xs font-medium text-gray-600 bg-gray-100">
      <Globe className="w-3.5 h-3.5" />
      <span>DE</span>
    </div>
  );
}
