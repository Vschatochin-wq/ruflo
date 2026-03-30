/**
 * LanguageSwitch — Locale Toggle for the Header Bar
 * ====================================================
 * Small dropdown button that lets the user switch between
 * German (DE) and English (EN). Designed to sit in the
 * application header alongside NotificationCenter.
 *
 * Usage:
 *   import LanguageSwitch from './components/LanguageSwitch';
 *   <header>
 *     <LanguageSwitch />
 *     <NotificationCenter />
 *   </header>
 */

import React, { useState, useRef, useEffect } from 'react';
import { useI18n } from '../i18n';

const LOCALE_OPTIONS = [
  { code: 'de', flag: '\uD83C\uDDE9\uD83C\uDDEA', label: 'Deutsch' },
  { code: 'en', flag: '\uD83C\uDDEC\uD83C\uDDE7', label: 'English' },
];

export default function LanguageSwitch() {
  const { locale, setLocale } = useI18n();
  const [open, setOpen] = useState(false);
  const dropdownRef = useRef(null);

  const current = LOCALE_OPTIONS.find((o) => o.code === locale) || LOCALE_OPTIONS[0];

  // Close dropdown on outside click
  useEffect(() => {
    function handleClickOutside(e) {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target)) {
        setOpen(false);
      }
    }
    document.addEventListener('pointerdown', handleClickOutside);
    return () => document.removeEventListener('pointerdown', handleClickOutside);
  }, []);

  function handleSelect(code) {
    setLocale(code);
    setOpen(false);
  }

  return (
    <div className="relative" ref={dropdownRef}>
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-1.5 px-2.5 py-1.5 text-sm font-medium text-gray-700
                   bg-white border border-gray-200 rounded-lg hover:bg-gray-50
                   transition-colors focus:outline-none focus:ring-2 focus:ring-purple-300"
        aria-label={`Language: ${current.label}`}
        aria-haspopup="listbox"
        aria-expanded={open}
      >
        <span className="text-base leading-none">{current.flag}</span>
        <span className="hidden sm:inline">{current.code.toUpperCase()}</span>
        <svg
          className={`w-3.5 h-3.5 text-gray-400 transition-transform ${open ? 'rotate-180' : ''}`}
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={2}
        >
          <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {open && (
        <div
          className="absolute right-0 mt-1 w-40 bg-white rounded-lg shadow-lg border border-gray-200
                     z-50 overflow-hidden"
          role="listbox"
          aria-label="Select language"
        >
          {LOCALE_OPTIONS.map((option) => (
            <button
              key={option.code}
              role="option"
              aria-selected={option.code === locale}
              onClick={() => handleSelect(option.code)}
              className={`
                w-full flex items-center gap-2.5 px-3 py-2 text-sm text-left
                transition-colors
                ${option.code === locale
                  ? 'bg-purple-50 text-purple-700 font-medium'
                  : 'text-gray-700 hover:bg-gray-50'
                }
              `}
            >
              <span className="text-base leading-none">{option.flag}</span>
              <span>{option.label}</span>
              {option.code === locale && (
                <svg className="w-4 h-4 ml-auto text-purple-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                </svg>
              )}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
