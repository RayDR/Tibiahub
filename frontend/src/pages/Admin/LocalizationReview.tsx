import { useCallback, useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Check, Languages, Loader2, LockOpen, RefreshCw, Sparkles } from 'lucide-react';

import { PaginationControls } from '../../components/ui';
import { useConfirmation } from '../../context/ConfirmationContext';
import { useToast } from '../../context/ToastContext';
import {
  localizationAdminApi,
  type KnowledgeLocalization,
  type LocalizationDiagnostics,
  type LocalizationStatus,
} from '../../services/localization';

const PAGE_SIZE = 20;
const REVIEW_STATES: LocalizationStatus[] = ['generated', 'stale', 'reviewed', 'approved', 'failed'];
const RESOURCE_TYPES = ['creature', 'item', 'quest', 'npc', 'location', 'hunt_zone'] as const;

type ResourceType = (typeof RESOURCE_TYPES)[number];

function StatusBadge({ value }: { value: string }) {
  const tone = value === 'approved'
    ? 'bg-success/15 text-success'
    : value === 'stale' || value === 'failed'
      ? 'bg-danger/15 text-danger'
      : value === 'reviewed'
        ? 'bg-info/15 text-info'
        : 'bg-primary/15 text-primary';
  return <span className={`rounded-full px-2 py-1 text-xs font-medium ${tone}`}>{value}</span>;
}

export default function LocalizationReview() {
  const { t } = useTranslation();
  const toast = useToast();
  const confirmation = useConfirmation();
  const [diagnostics, setDiagnostics] = useState<LocalizationDiagnostics | null>(null);
  const [items, setItems] = useState<KnowledgeLocalization[]>([]);
  const [total, setTotal] = useState(0);
  const [skip, setSkip] = useState(0);
  const [statusFilter, setStatusFilter] = useState<LocalizationStatus>('generated');
  const [languageFilter, setLanguageFilter] = useState('es');
  const [resourceFilter, setResourceFilter] = useState('');
  const [selected, setSelected] = useState<KnowledgeLocalization | null>(null);
  const [draft, setDraft] = useState('');
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(false);
  const [backfillType, setBackfillType] = useState<ResourceType>('creature');
  const [backfillLimit, setBackfillLimit] = useState(20);
  const [authorResourceType, setAuthorResourceType] = useState<ResourceType>('creature');
  const [authorResourceKey, setAuthorResourceKey] = useState('');
  const [authorFieldPath, setAuthorFieldPath] = useState('description');
  const [authorSourceLanguage, setAuthorSourceLanguage] = useState('es');
  const [authorTargets, setAuthorTargets] = useState('en,pt-BR');
  const [authorProtectedTerms, setAuthorProtectedTerms] = useState('');
  const [authorText, setAuthorText] = useState('');

  const load = useCallback(async (nextSkip = skip) => {
    const controller = new AbortController();
    setLoading(true);
    setError(false);
    try {
      const [health, page] = await Promise.all([
        localizationAdminApi.diagnostics(controller.signal),
        localizationAdminApi.localizations({
          status: statusFilter,
          language: languageFilter || undefined,
          resource_type: resourceFilter || undefined,
          skip: nextSkip,
          limit: PAGE_SIZE,
        }, controller.signal),
      ]);
      setDiagnostics(health);
      setItems(page.items);
      setTotal(page.total);
      setSkip(page.skip);
      if (selected) {
        const refreshed = page.items.find((item) => item.id === selected.id) || null;
        setSelected(refreshed);
        if (refreshed) setDraft(refreshed.text);
      }
    } catch {
      setError(true);
    } finally {
      setLoading(false);
    }
  }, [languageFilter, resourceFilter, selected, skip, statusFilter]);

  useEffect(() => {
    void load(0);
    // selected is intentionally excluded; selecting a row must not refetch.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [languageFilter, resourceFilter, statusFilter]);

  const selectItem = (item: KnowledgeLocalization) => {
    setSelected(item);
    setDraft(item.text);
  };

  const replaceSelected = (item: KnowledgeLocalization) => {
    setSelected(item);
    setDraft(item.text);
    setItems((current) => current.map((entry) => entry.id === item.id ? item : entry));
  };

  const saveReview = async () => {
    if (!selected || !draft.trim()) return;
    setBusy(true);
    try {
      const updated = await localizationAdminApi.review(selected.id, { text: draft.trim() });
      replaceSelected(updated);
      toast.success(t('localization.reviewSaved', { defaultValue: 'Translation marked as reviewed.' }));
      await load(skip);
    } catch {
      toast.error(t('localization.reviewFailed', { defaultValue: 'The translation could not be reviewed.' }));
    } finally {
      setBusy(false);
    }
  };

  const approve = async () => {
    if (!selected || !draft.trim()) return;
    const accepted = await confirmation.confirm(
      t('localization.approveConfirm', { defaultValue: 'Approve and lock this translation? Future sync changes will mark it stale instead of overwriting it.' }),
      { title: t('localization.approve', { defaultValue: 'Approve translation' }), confirmLabel: t('localization.approve', { defaultValue: 'Approve' }) },
    );
    if (!accepted) return;
    setBusy(true);
    try {
      const updated = await localizationAdminApi.approve(selected.id, { text: draft.trim() });
      replaceSelected(updated);
      toast.success(t('localization.approved', { defaultValue: 'Translation approved and locked.' }));
      await load(skip);
    } catch {
      toast.error(t('localization.approveFailed', { defaultValue: 'The translation could not be approved.' }));
    } finally {
      setBusy(false);
    }
  };

  const unlock = async () => {
    if (!selected) return;
    const accepted = await confirmation.confirm(
      t('localization.unlockConfirm', { defaultValue: 'Unlock this translation so a future generation can replace it?' }),
      { title: t('localization.unlock', { defaultValue: 'Unlock translation' }) },
    );
    if (!accepted) return;
    setBusy(true);
    try {
      const updated = await localizationAdminApi.unlock(selected.id);
      replaceSelected(updated);
      toast.success(t('localization.unlocked', { defaultValue: 'Translation unlocked.' }));
    } catch {
      toast.error(t('localization.unlockFailed', { defaultValue: 'The translation could not be unlocked.' }));
    } finally {
      setBusy(false);
    }
  };

  const queueAuthoredText = async () => {
    const sourceText = authorText.trim();
    const resourceKey = authorResourceKey.trim();
    const fieldPath = authorFieldPath.trim();
    const sourceLanguage = authorSourceLanguage.trim();
    const targets = [...new Set(
      authorTargets.split(',').map((value) => value.trim()).filter((value) => value && value !== sourceLanguage),
    )];
    if (!sourceText || !resourceKey || !fieldPath || !sourceLanguage || targets.length === 0) return;

    const accepted = await confirmation.confirm(
      t('localization.authorConfirm', {
        defaultValue: `Queue this ${sourceLanguage} text for ${targets.join(', ')}? The source text remains untouched.`,
      }),
      { title: t('localization.authorTitle', { defaultValue: 'Translate reviewer-authored content' }), confirmLabel: t('localization.queue', { defaultValue: 'Queue' }) },
    );
    if (!accepted) return;

    setBusy(true);
    try {
      const protectedTerms = authorProtectedTerms.split(',').map((value) => value.trim()).filter(Boolean);
      await Promise.all(targets.map((targetLanguage) => localizationAdminApi.enqueueJob({
        resource_type: authorResourceType,
        resource_key: resourceKey,
        field_path: fieldPath,
        source_text: sourceText,
        source_language: sourceLanguage,
        target_language: targetLanguage,
        protected_terms: protectedTerms,
        context: `Reviewer-authored Tibia ${authorResourceType} content`,
      })));
      toast.success(t('localization.authorQueued', {
        defaultValue: `${targets.length} translation job(s) queued from reviewer-authored content.`,
      }));
      setAuthorText('');
      await load(0);
    } catch {
      toast.error(t('localization.authorFailed', { defaultValue: 'Reviewer-authored content could not be queued.' }));
    } finally {
      setBusy(false);
    }
  };

  const runBackfill = async () => {
    const accepted = await confirmation.confirm(
      t('localization.backfillConfirm', {
        defaultValue: `Queue translations for up to ${backfillLimit} existing ${backfillType} records? This only creates durable jobs; it does not modify canonical content.`,
      }),
      { title: t('localization.backfill', { defaultValue: 'Queue localization backfill' }), confirmLabel: t('localization.queue', { defaultValue: 'Queue' }) },
    );
    if (!accepted) return;
    setBusy(true);
    try {
      const result = await localizationAdminApi.backfill({
        resource_type: backfillType,
        limit: backfillLimit,
        source_language: 'auto',
        target_languages: diagnostics?.target_languages,
      });
      toast.success(t('localization.backfillQueued', {
        defaultValue: `${result.queued} new translation jobs queued from ${result.scanned} records.`,
      }));
      await load(0);
    } catch {
      toast.error(t('localization.backfillFailed', { defaultValue: 'Backfill could not be queued.' }));
    } finally {
      setBusy(false);
    }
  };

  const metrics = useMemo(() => [
    { label: t('localization.metricQueue', { defaultValue: 'Queue' }), value: diagnostics?.queue_depth ?? 0 },
    { label: t('localization.metricReview', { defaultValue: 'Needs review' }), value: diagnostics?.generated_pending_review ?? 0 },
    { label: t('localization.metricStale', { defaultValue: 'Stale' }), value: diagnostics?.stale ?? 0 },
    { label: t('localization.metricApproved', { defaultValue: 'Approved' }), value: diagnostics?.approved ?? 0 },
  ], [diagnostics, t]);

  return (
    <div className="space-y-6">
      <section className="rounded-xl border border-line bg-surface-base/60 p-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <div className="flex items-center gap-2">
              <Languages className="h-5 w-5 text-primary" />
              <h2 className="font-semibold text-content-primary">{t('localization.title', { defaultValue: 'Content localization' })}</h2>
            </div>
            <p className="mt-1 text-sm text-content-secondary">
              {t('localization.subtitle', { defaultValue: 'Review generated translations without changing TibiaHub canonical source content.' })}
            </p>
          </div>
          <button className="app-button-secondary app-button-sm" onClick={() => void load(skip)} disabled={loading}>
            <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
            {t('common.refresh')}
          </button>
        </div>

        {diagnostics && (
          <>
            <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
              {metrics.map((metric) => (
                <div key={metric.label} className="rounded-lg border border-line bg-surface-raised p-3">
                  <div className="text-xs text-content-muted">{metric.label}</div>
                  <div className="mt-1 text-2xl font-semibold text-content-primary">{metric.value}</div>
                </div>
              ))}
            </div>
            <p className="mt-3 text-xs text-content-muted">
              {diagnostics.enabled ? t('localization.enabled', { defaultValue: 'Localization enabled' }) : t('localization.disabled', { defaultValue: 'Localization disabled' })}
              {' · '}{diagnostics.provider}/{diagnostics.model}
              {' · '}{t('localization.targets', { defaultValue: 'Targets' })}: {diagnostics.target_languages.join(', ') || '—'}
              {' · '}{t('localization.worker', { defaultValue: 'Worker' })}: {diagnostics.worker?.state || 'offline'}
            </p>
          </>
        )}
      </section>

      <section className="rounded-xl border border-line bg-surface-base/60 p-4">
        <div className="flex flex-wrap items-end gap-2">
          <label className="grid gap-1 text-xs text-content-secondary">
            {t('localization.status', { defaultValue: 'Status' })}
            <select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value as LocalizationStatus)} className="min-h-11 rounded-lg border border-line bg-surface-base px-3 text-sm">
              {REVIEW_STATES.map((value) => <option key={value} value={value}>{value}</option>)}
            </select>
          </label>
          <label className="grid gap-1 text-xs text-content-secondary">
            {t('localization.language', { defaultValue: 'Language' })}
            <input value={languageFilter} onChange={(event) => setLanguageFilter(event.target.value)} className="min-h-11 w-28 rounded-lg border border-line bg-surface-base px-3 text-sm" />
          </label>
          <label className="grid gap-1 text-xs text-content-secondary">
            {t('localization.resource', { defaultValue: 'Resource' })}
            <select value={resourceFilter} onChange={(event) => setResourceFilter(event.target.value)} className="min-h-11 rounded-lg border border-line bg-surface-base px-3 text-sm">
              <option value="">{t('localization.allResources', { defaultValue: 'All' })}</option>
              {RESOURCE_TYPES.map((value) => <option key={value} value={value}>{value}</option>)}
            </select>
          </label>
        </div>

        {error ? (
          <p className="mt-4 rounded-lg bg-danger/10 p-3 text-sm text-danger">{t('localization.loadFailed', { defaultValue: 'Localization data could not be loaded.' })}</p>
        ) : loading && items.length === 0 ? (
          <div className="mt-5 flex items-center gap-2 text-sm text-content-secondary"><Loader2 className="h-4 w-4 animate-spin" />{t('common.loading')}</div>
        ) : items.length === 0 ? (
          <p className="mt-4 text-sm text-content-muted">{t('localization.empty', { defaultValue: 'No translations match these filters.' })}</p>
        ) : (
          <div className="mt-4 grid gap-4 xl:grid-cols-[minmax(18rem,0.8fr)_minmax(28rem,1.2fr)]">
            <div className="space-y-2">
              {items.map((item) => (
                <button
                  key={item.id}
                  type="button"
                  onClick={() => selectItem(item)}
                  className={`w-full rounded-lg border p-3 text-left ${selected?.id === item.id ? 'border-primary bg-primary/5' : 'border-line bg-surface-base/40'}`}
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0">
                      <div className="truncate text-sm font-medium text-content-primary">{item.resource_type} · {item.field_path}</div>
                      <div className="truncate text-xs text-content-muted">{item.resource_key}</div>
                    </div>
                    <StatusBadge value={item.status} />
                  </div>
                  <p className="mt-2 line-clamp-2 text-xs text-content-secondary">{item.text}</p>
                </button>
              ))}
              <PaginationControls skip={skip} limit={PAGE_SIZE} total={total} loading={loading} onPrevious={() => void load(Math.max(0, skip - PAGE_SIZE))} onNext={() => void load(skip + PAGE_SIZE)} />
            </div>

            {selected ? (
              <div className="rounded-xl border border-line bg-surface-raised p-4">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div>
                    <div className="font-medium text-content-primary">{selected.resource_type} · {selected.field_path}</div>
                    <div className="text-xs text-content-muted">{selected.source_language} → {selected.language} · {selected.origin}</div>
                  </div>
                  <StatusBadge value={selected.status} />
                </div>
                <div className="mt-4 grid gap-4 lg:grid-cols-2">
                  <label className="grid gap-1 text-xs text-content-secondary">
                    {t('localization.source', { defaultValue: 'Canonical/source snapshot' })}
                    <textarea readOnly value={selected.source_text || ''} className="min-h-52 resize-y rounded-lg border border-line bg-surface-base p-3 text-sm text-content-primary" />
                  </label>
                  <label className="grid gap-1 text-xs text-content-secondary">
                    {t('localization.translation', { defaultValue: 'Translation' })}
                    <textarea value={draft} onChange={(event) => setDraft(event.target.value)} className="min-h-52 resize-y rounded-lg border border-line bg-surface-base p-3 text-sm text-content-primary" />
                  </label>
                </div>
                <div className="mt-4 flex flex-wrap gap-2">
                  <button className="app-button-secondary" onClick={() => void saveReview()} disabled={busy || !draft.trim()}>
                    {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
                    {t('localization.markReviewed', { defaultValue: 'Save as reviewed' })}
                  </button>
                  <button className="app-button-primary" onClick={() => void approve()} disabled={busy || !draft.trim()}>
                    <Check className="h-4 w-4" />{t('localization.approve', { defaultValue: 'Approve & lock' })}
                  </button>
                  {selected.locked && (
                    <button className="app-button-secondary" onClick={() => void unlock()} disabled={busy}>
                      <LockOpen className="h-4 w-4" />{t('localization.unlock', { defaultValue: 'Unlock' })}
                    </button>
                  )}
                </div>
              </div>
            ) : (
              <div className="rounded-xl border border-dashed border-line p-8 text-center text-sm text-content-muted">
                {t('localization.selectPrompt', { defaultValue: 'Select a translation to compare source and target content.' })}
              </div>
            )}
          </div>
        )}
      </section>

      <section className="rounded-xl border border-line bg-surface-base/60 p-4">
        <h3 className="font-medium text-content-primary">{t('localization.authorTitle', { defaultValue: 'Author in any language' })}</h3>
        <p className="mt-1 text-xs text-content-muted">
          {t('localization.authorHelp', { defaultValue: 'A reviewer can write source text in Spanish, English, Portuguese, or another supported locale and queue durable translations without replacing canonical provider content.' })}
        </p>
        <div className="mt-3 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          <label className="grid gap-1 text-xs text-content-secondary">
            {t('localization.resource', { defaultValue: 'Resource' })}
            <select value={authorResourceType} onChange={(event) => setAuthorResourceType(event.target.value as ResourceType)} className="min-h-11 rounded-lg border border-line bg-surface-base px-3 text-sm">
              {RESOURCE_TYPES.map((value) => <option key={value} value={value}>{value}</option>)}
            </select>
          </label>
          <label className="grid gap-1 text-xs text-content-secondary">
            {t('localization.resourceKey', { defaultValue: 'Resource key / canonical ID' })}
            <input value={authorResourceKey} onChange={(event) => setAuthorResourceKey(event.target.value)} className="min-h-11 rounded-lg border border-line bg-surface-base px-3 text-sm" />
          </label>
          <label className="grid gap-1 text-xs text-content-secondary">
            {t('localization.fieldPath', { defaultValue: 'Field path' })}
            <input value={authorFieldPath} onChange={(event) => setAuthorFieldPath(event.target.value)} className="min-h-11 rounded-lg border border-line bg-surface-base px-3 text-sm" />
          </label>
          <label className="grid gap-1 text-xs text-content-secondary">
            {t('localization.sourceLanguage', { defaultValue: 'Source language' })}
            <input value={authorSourceLanguage} onChange={(event) => setAuthorSourceLanguage(event.target.value)} className="min-h-11 rounded-lg border border-line bg-surface-base px-3 text-sm" placeholder="es" />
          </label>
          <label className="grid gap-1 text-xs text-content-secondary">
            {t('localization.targetLanguages', { defaultValue: 'Target languages (comma separated)' })}
            <input value={authorTargets} onChange={(event) => setAuthorTargets(event.target.value)} className="min-h-11 rounded-lg border border-line bg-surface-base px-3 text-sm" placeholder="en,pt-BR" />
          </label>
          <label className="grid gap-1 text-xs text-content-secondary">
            {t('localization.protectedTerms', { defaultValue: 'Protected Tibia terms (comma separated)' })}
            <input value={authorProtectedTerms} onChange={(event) => setAuthorProtectedTerms(event.target.value)} className="min-h-11 rounded-lg border border-line bg-surface-base px-3 text-sm" placeholder="Demon, Edron" />
          </label>
        </div>
        <label className="mt-3 grid gap-1 text-xs text-content-secondary">
          {t('localization.sourceText', { defaultValue: 'Reviewer-authored source text' })}
          <textarea value={authorText} onChange={(event) => setAuthorText(event.target.value)} className="min-h-36 resize-y rounded-lg border border-line bg-surface-base p-3 text-sm text-content-primary" />
        </label>
        <button
          className="app-button-primary mt-3"
          onClick={() => void queueAuthoredText()}
          disabled={busy || !diagnostics?.enabled || !authorText.trim() || !authorResourceKey.trim() || !authorFieldPath.trim() || !authorSourceLanguage.trim()}
        >
          <Sparkles className="h-4 w-4" />
          {t('localization.translateAuthored', { defaultValue: 'Queue translations' })}
        </button>
      </section>

      <section className="rounded-xl border border-line bg-surface-base/60 p-4">
        <h3 className="font-medium text-content-primary">{t('localization.backfill', { defaultValue: 'Existing content backfill' })}</h3>
        <p className="mt-1 text-xs text-content-muted">{t('localization.backfillHelp', { defaultValue: 'Queue a small, idempotent batch first. Backfill never rewrites canonical content.' })}</p>
        <div className="mt-3 flex flex-wrap items-end gap-2">
          <label className="grid gap-1 text-xs text-content-secondary">
            {t('localization.resource', { defaultValue: 'Resource' })}
            <select value={backfillType} onChange={(event) => setBackfillType(event.target.value as ResourceType)} className="min-h-11 rounded-lg border border-line bg-surface-base px-3 text-sm">
              {RESOURCE_TYPES.map((value) => <option key={value} value={value}>{value}</option>)}
            </select>
          </label>
          <label className="grid gap-1 text-xs text-content-secondary">
            {t('localization.batchSize', { defaultValue: 'Batch size' })}
            <input type="number" min={1} max={500} value={backfillLimit} onChange={(event) => setBackfillLimit(Math.max(1, Math.min(500, Number(event.target.value) || 1)))} className="min-h-11 w-28 rounded-lg border border-line bg-surface-base px-3 text-sm" />
          </label>
          <button className="app-button-secondary" onClick={() => void runBackfill()} disabled={busy || !diagnostics?.enabled}>
            <Sparkles className="h-4 w-4" />{t('localization.queueBackfill', { defaultValue: 'Queue batch' })}
          </button>
        </div>
        {!diagnostics?.enabled && <p className="mt-2 text-xs text-primary">{t('localization.enableFirst', { defaultValue: 'Enable LOCALIZATION_ENABLED before queueing backfill jobs.' })}</p>}
      </section>
    </div>
  );
}
