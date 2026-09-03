export type SupportedLanguage = 'en' | 'es';

export function supportedLanguage(language?: string): SupportedLanguage {
  return language?.toLowerCase().startsWith('es') ? 'es' : 'en';
}

export function appLocale(language?: string): 'en-US' | 'es-MX' {
  return supportedLanguage(language) === 'es' ? 'es-MX' : 'en-US';
}

export function formatDate(
  value: string | number | Date,
  language?: string,
  options?: Intl.DateTimeFormatOptions,
): string {
  return new Intl.DateTimeFormat(appLocale(language), options).format(new Date(value));
}

export function formatDateTime(
  value: string | number | Date,
  language?: string,
  options: Intl.DateTimeFormatOptions = { dateStyle: 'medium', timeStyle: 'short' },
): string {
  return formatDate(value, language, options);
}

export function formatTime(
  value: string | number | Date,
  language?: string,
  options: Intl.DateTimeFormatOptions = { timeStyle: 'short' },
): string {
  return formatDate(value, language, options);
}

export function formatNumber(
  value: number,
  language?: string,
  options?: Intl.NumberFormatOptions,
): string {
  return new Intl.NumberFormat(appLocale(language), options).format(value);
}
