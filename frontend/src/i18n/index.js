/**
 * i18n — Public API re-exports
 * ==============================
 * Central entry point for the internationalization module.
 *
 * Usage:
 *   import { I18nProvider, useI18n, messages, supportedLocales } from './i18n';
 */

export { messages, defaultLocale, supportedLocales } from './messages';
export { I18nProvider, useI18n } from './I18nProvider';
