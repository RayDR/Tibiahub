import { FormEvent, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { CheckCircle, Loader2, Mail, Shield } from 'lucide-react';
import { useTranslation } from 'react-i18next';

import { AppButton, Card, FormField, Input, Page } from '../components/ui';
import api from '../services/api';
import { isValidPassword } from '../utils/passwordPolicy';

export default function PasswordReset() {
  const { t, i18n } = useTranslation();
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const token = params.get('token');
  const [step, setStep] = useState<'request'|'reset'|'success'>(token ? 'reset' : 'request');
  const [identifierType, setIdentifierType] = useState<'email'|'character'>('email');
  const [identifier, setIdentifier] = useState('');
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  const requestReset = async (event: FormEvent) => {
    event.preventDefault(); setBusy(true); setError('');
    try {
      await api.post('/password/request-reset', {
        [identifierType === 'email' ? 'email' : 'character_name']: identifier.trim(),
        locale: i18n.language.startsWith('es') ? 'es' : 'en',
      });
      setStep('success');
    } catch { setError(t('passwordRecovery.errors.request')); }
    finally { setBusy(false); }
  };
  const reset = async (event: FormEvent) => {
    event.preventDefault(); setError('');
    if (password !== confirm) { setError(t('passwordRecovery.errors.match')); return; }
    if (!isValidPassword(password)) { setError(t('passwordRecovery.errors.policy')); return; }
    setBusy(true);
    try {
      await api.post('/password/reset-password', { token, new_password: password });
      setStep('success'); window.setTimeout(() => navigate('/login'), 1500);
    } catch { setError(t('passwordRecovery.errors.invalid')); }
    finally { setBusy(false); }
  };

  return <Page className="grid min-h-[70vh] place-items-center"><Card className="w-full max-w-md p-5 sm:p-7">
    <header className="text-center"><Shield className="mx-auto size-10 text-primary"/><h1 className="mt-3 text-2xl font-semibold">{t(`passwordRecovery.${step}.title`)}</h1><p className="mt-1 text-sm text-content-muted">{t(`passwordRecovery.${step}.help`)}</p></header>
    {error ? <p role="alert" className="mt-4 rounded-lg border border-danger/30 p-3 text-sm text-danger">{error}</p> : null}
    {step === 'request' ? <form onSubmit={requestReset} className="mt-6 space-y-4">
      <div className="grid grid-cols-2 gap-2" role="group" aria-label={t('passwordRecovery.identifier')}>
        {(['email','character'] as const).map(value=><button type="button" key={value} onClick={()=>setIdentifierType(value)} className={`min-h-11 rounded-lg border px-3 ${identifierType===value?'border-primary bg-primary-subtle':'border-line'}`}>{t(`passwordRecovery.${value}`)}</button>)}
      </div>
      <FormField label={t(`passwordRecovery.${identifierType}`)}><Input type={identifierType==='email'?'email':'text'} value={identifier} onChange={event=>setIdentifier(event.target.value)} required minLength={2} autoComplete={identifierType==='email'?'email':'off'} /></FormField>
      <AppButton className="w-full" type="submit" disabled={busy}>{busy?<Loader2 className="size-4 animate-spin"/>:<Mail className="size-4"/>}{t('passwordRecovery.request.action')}</AppButton>
    </form> : null}
    {step === 'reset' ? <form onSubmit={reset} className="mt-6 space-y-4">
      <FormField label={t('passwordRecovery.newPassword')} helpText={t('passwordRecovery.passwordHelp')}><Input type="password" minLength={8} maxLength={128} autoComplete="new-password" value={password} onChange={event=>setPassword(event.target.value)} required /></FormField>
      <FormField label={t('passwordRecovery.confirmPassword')}><Input type="password" minLength={8} maxLength={128} autoComplete="new-password" value={confirm} onChange={event=>setConfirm(event.target.value)} required /></FormField>
      <AppButton className="w-full" type="submit" disabled={busy}>{busy?<Loader2 className="size-4 animate-spin"/>:null}{t('passwordRecovery.reset.action')}</AppButton>
    </form> : null}
    {step === 'success' ? <div className="mt-6 text-center"><CheckCircle className="mx-auto size-12 text-success"/><p className="mt-3 text-content-secondary">{t(token?'passwordRecovery.success.reset':'passwordRecovery.success.request')}</p></div> : null}
    <Link to="/login" className="mt-6 block min-h-11 text-center text-sm text-primary">{t('passwordRecovery.back')}</Link>
  </Card></Page>;
}
