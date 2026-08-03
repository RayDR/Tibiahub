import { useEffect, useMemo, useState } from 'react';
import { Check, Clipboard, Loader2, RefreshCw, X } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { AppButton, Badge, Dialog, Input } from '../ui';
import { OwnershipClaim, profileApi } from '../../services/profile';
import { useToast } from '../../context/ToastContext';

export default function OwnershipClaimDialog({ open, claims, onClose, onChange }: { open: boolean; claims: OwnershipClaim[]; onClose: () => void; onChange: (claims: OwnershipClaim[]) => void }) {
  const { t } = useTranslation(); const toast = useToast(); const [name, setName] = useState(''); const [selected, setSelected] = useState<OwnershipClaim>(); const [busy, setBusy] = useState(false); const [copied, setCopied] = useState(false); const [now, setNow] = useState(Date.now());
  useEffect(() => { if (!open) return undefined; const timer = window.setInterval(() => setNow(Date.now()), 1000); return () => clearInterval(timer); }, [open]);
  useEffect(() => { if (!selected) setSelected(claims.find(row => !row.incoming && ['pending','queued','processing'].includes(row.status))); }, [claims, selected]);
  const remaining = useMemo(() => selected ? Math.max(0, new Date(selected.expires_at).getTime() - now) : 0, [selected, now]);
  const replace = (row: OwnershipClaim) => { onChange(claims.map(item => item.id === row.id ? { ...item, ...row } : item)); setSelected(row); };
  const create = async () => { if (!name.trim()) return; setBusy(true); try { const row = await profileApi.claim(name.trim()); onChange([row, ...claims]); setSelected(row); setName(''); } catch { toast.error(t('identity.error')); } finally { setBusy(false); } };
  const refresh = async () => { if (!selected) return; setBusy(true); try { replace(await profileApi.getClaim(selected.id)); } catch { toast.error(t('identity.error')); } finally { setBusy(false); } };
  const verify = async () => { if (!selected) return; setBusy(true); try { replace(await profileApi.verifyClaim(selected.id)); } catch { toast.error(t('identity.error')); } finally { setBusy(false); } };
  const cancel = async () => { if (!selected) return; setBusy(true); try { replace(await profileApi.cancelClaim(selected.id)); } catch { toast.error(t('identity.error')); } finally { setBusy(false); } };
  const steps = Object.values(t('identity.claim.steps', { returnObjects: true }) as Record<string, string>);
  return <Dialog open={open} onClose={onClose} label={t('identity.claim.title')} className="max-h-[90vh] max-w-2xl overflow-y-auto p-5">
    <div className="flex items-start justify-between gap-3"><div><h2 className="text-xl font-semibold">{t('identity.claim.title')}</h2><p className="text-sm text-content-muted">{t('identity.claim.help')}</p></div><button onClick={onClose} aria-label={t('common.close')} className="app-button-ghost"><X className="size-5" /></button></div>
    <ol className="mt-4 list-decimal space-y-1 pl-6 text-sm text-content-secondary">{steps.map((step, index) => <li key={index}>{step}</li>)}</ol>
    {selected && <section className="mt-5 rounded-xl border border-line p-4"><div className="flex flex-wrap justify-between gap-2"><strong>{selected.character_name}</strong><Badge>{t(`identity.claim.status.${selected.status}`)}</Badge></div><p className="mt-2 text-xs text-content-muted">{t('identity.claim.created', { value: new Date(selected.created_at).toLocaleString() })} · {t('identity.claim.expires', { value: formatRemaining(remaining) })}</p>{selected.challenge && <div className="mt-3 rounded-lg bg-primary-subtle p-3"><code className="block break-all select-all">{selected.challenge}</code><AppButton size="sm" variant="ghost" className="mt-2" onClick={() => { void navigator.clipboard.writeText(selected.challenge || ''); setCopied(true); }}><Clipboard className="size-4" />{copied ? t('identity.claim.copied') : t('identity.claim.copy')}</AppButton></div>}{selected.safe_failure_code && <p className="mt-3 text-sm text-warning">{t(`identity.claim.failure.${selected.safe_failure_code}`, { defaultValue: selected.safe_failure_code })}</p>}<div className="mt-3 flex flex-wrap gap-2">{selected.status === 'pending' && remaining > 0 && <AppButton onClick={() => void verify()} disabled={busy}>{busy ? <Loader2 className="size-4 animate-spin" /> : <Check className="size-4" />}{t('identity.claim.verify')}</AppButton>}<AppButton variant="secondary" onClick={() => void refresh()} disabled={busy}><RefreshCw className="size-4" />{t('common.refresh')}</AppButton>{['pending','queued'].includes(selected.status) && <AppButton variant="ghost" onClick={() => void cancel()} disabled={busy}>{t('common.cancel')}</AppButton>}</div></section>}
    {(!selected || remaining === 0 || !['pending','queued','processing'].includes(selected.status)) && <div className="mt-5 flex flex-col gap-2 sm:flex-row"><Input value={name} maxLength={100} placeholder={t('identity.claim.placeholder')} onChange={event => setName(event.target.value)} /><AppButton disabled={busy || name.trim().length < 2} onClick={() => void create()}>{t('identity.claim.generate')}</AppButton></div>}
  </Dialog>;
}

function formatRemaining(ms: number) { const seconds = Math.floor(ms / 1000); const hours = Math.floor(seconds / 3600); const minutes = Math.floor((seconds % 3600) / 60); return `${hours}h ${minutes}m ${seconds % 60}s`; }
