/**
 * I18nProvider — React Context Provider for Internationalization
 * ===============================================================
 * Wraps the application in react-intl's IntlProvider and exposes a
 * convenience hook `useI18n()` for components to consume.
 *
 * Features:
 *   - Persists selected locale in localStorage ('app-locale')
 *   - Falls back to browser language if no stored preference
 *   - Provides `t(id, values?)` shorthand for formatMessage
 *   - Exposes full `intl` object via `formatMessage` for advanced use
 *
 * Usage:
 *   // In App.js — wrap the root:
 *   import { I18nProvider } from './i18n';
 *   <I18nProvider>
 *     <App />
 *   </I18nProvider>
 *
 *   // In any component:
 *   import { useI18n } from '../i18n';
 *   const { t, locale, setLocale } = useI18n();
 *   <h1>{t('dashboard.title')}</h1>
 *   <p>{t('complaints.page', { current: 1, total: 5 })}</p>
 */

import React, { createContext, useContext, useState, useCallback, useMemo } from 'react';
import { IntlProvider, useIntl } from 'react-intl';
import { messages, defaultLocale, supportedLocales } from './messages';

const LOCALE_STORAGE_KEY = 'app-locale';

// ─── Context ────────────────────────────────────────────────────────

const I18nContext = createContext({
  locale: defaultLocale,
  setLocale: () => {},
});

// ─── Detect initial locale ──────────────────────────────────────────

function getInitialLocale() {
  // 1. Check localStorage
  try {
    const stored = localStorage.getItem(LOCALE_STORAGE_KEY);
    if (stored && supportedLocales.includes(stored)) {
      return stored;
    }
  } catch {
    // localStorage may be unavailable (SSR, privacy mode)
  }

  // 2. Check browser language
  if (typeof navigator !== 'undefined') {
    const browserLang = (navigator.language || '').split('-')[0];
    if (supportedLocales.includes(browserLang)) {
      return browserLang;
    }
  }

  // 3. Fall back to default
  return defaultLocale;
}

// ─── Inner wrapper that provides `t()` via useIntl ──────────────────

function I18nInnerProvider({ children }) {
  const intl = useIntl();

  const t = useCallback(
    (id, values) => {
      return intl.formatMessage({ id, defaultMessage: id }, values);
    },
    [intl]
  );

  const contextValue = useMemo(
    () => ({ t, formatMessage: intl.formatMessage }),
    [t, intl.formatMessage]
  );

  return (
    <IntlContext.Provider value={contextValue}>
      {children}
    </IntlContext.Provider>
  );
}

// Separate context for intl-dependent values (t, formatMessage)
const IntlContext = createContext({
  t: (id) => id,
  formatMessage: () => '',
});

// ─── Main Provider ──────────────────────────────────────────────────

export function I18nProvider({ children }) {
  const [locale, setLocaleState] = useState(getInitialLocale);

  const setLocale = useCallback((newLocale) => {
    if (!supportedLocales.includes(newLocale)) {
      console.warn(`[i18n] Unsupported locale "${newLocale}". Supported: ${supportedLocales.join(', ')}`);
      return;
    }
    setLocaleState(newLocale);
    try {
      localStorage.setItem(LOCALE_STORAGE_KEY, newLocale);
    } catch {
      // localStorage may be unavailable
    }
  }, []);

  const i18nContextValue = useMemo(
    () => ({ locale, setLocale }),
    [locale, setLocale]
  );

  return (
    <I18nContext.Provider value={i18nContextValue}>
      <IntlProvider
        locale={locale}
        messages={messages[locale] || messages[defaultLocale]}
        defaultLocale={defaultLocale}
        onError={(err) => {
          // Suppress missing-translation warnings in development;
          // the defaultMessage (= the message ID) is shown instead.
          if (err.code === 'MISSING_TRANSLATION') return;
          console.error('[i18n]', err);
        }}
      >
        <I18nInnerProvider>
          {children}
        </I18nInnerProvider>
      </IntlProvider>
    </I18nContext.Provider>
  );
}

// ─── Hook ───────────────────────────────────────────────────────────

/**
 * useI18n — Access locale state and translation helpers.
 *
 * @returns {{
 *   locale: string,
 *   setLocale: (locale: string) => void,
 *   t: (id: string, values?: Record<string, any>) => string,
 *   formatMessage: import('react-intl').IntlShape['formatMessage']
 * }}
 */
export function useI18n() {
  const { locale, setLocale } = useContext(I18nContext);
  const { t, formatMessage } = useContext(IntlContext);

  return { locale, setLocale, t, formatMessage };
}
