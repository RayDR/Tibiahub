import api from './api';

export interface EmailDiagnostics {
  configured: boolean; host?: string; port: number; mode: string; from_address?: string;
  last_successful_delivery_at?: string; last_failure_category?: string; queue_depth: number;
  worker?: { worker_id: string; state: string; last_seen_at: string; version: string; enabled: boolean };
}

export const adminEmailApi = {
  diagnostics: async (): Promise<EmailDiagnostics> => (await api.get('/password/email-diagnostics')).data,
  test: async (email: string, locale: 'en'|'es'): Promise<void> => { await api.post('/password/test-email', { email, locale }); },
  reset: async (userId: number, locale: 'en'|'es'): Promise<void> => { await api.post('/password/admin/send-reset-email', { user_id: userId, locale }); },
  verify: async (userId: number, locale: 'en'|'es'): Promise<void> => { await api.post('/email-verification/admin/resend', { user_id: userId, locale }); },
};
