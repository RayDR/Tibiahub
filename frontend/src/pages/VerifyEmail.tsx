import { useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { CheckCircle, Loader2, XCircle } from 'lucide-react';
import { useTranslation } from 'react-i18next';

import { Card, Page } from '../components/ui';
import api from '../services/api';

export default function VerifyEmail(){
  const {t}=useTranslation();const [params]=useSearchParams();const [state,setState]=useState<'loading'|'success'|'error'>('loading');
  useEffect(()=>{const token=params.get('token');if(!token){setState('error');return;}void api.post('/email-verification/confirm',{token}).then(()=>setState('success')).catch(()=>setState('error'));},[params]);
  return <Page className="grid min-h-[70vh] place-items-center py-8"><Card className="w-full max-w-md p-7 text-center">{state==='loading'?<Loader2 className="mx-auto size-10 animate-spin text-primary"/>:state==='success'?<CheckCircle className="mx-auto size-10 text-success"/>:<XCircle className="mx-auto size-10 text-danger"/>}<h1 className="mt-4 text-2xl font-semibold">{t(`emailVerification.${state}.title`)}</h1><p className="mt-2 text-content-secondary">{t(`emailVerification.${state}.help`)}</p><Link to="/login" className="mt-6 inline-flex min-h-11 items-center text-primary">{t('passwordRecovery.back')}</Link></Card></Page>;
}
