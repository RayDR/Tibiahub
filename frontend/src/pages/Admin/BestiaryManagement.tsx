import { Fragment, useEffect, useRef, useState } from 'react';
import { adminCreaturesApi } from '../../services/api';
import type { Creature } from '../../types';
import { useToast } from '../../context/ToastContext';
import { ChevronLeft, ChevronRight, Database, Loader2 } from 'lucide-react';
import { Alert, DegradedState, EmptyState, ErrorState, Input, Select } from '../../components/ui';
import { useTranslation } from 'react-i18next';

const PAGE_SIZE_KEY = 'admin_bestiary_page_size';
const PAGE_SIZES = [20, 50, 100];

function getInitialPageSize(): number {
    const stored = sessionStorage.getItem(PAGE_SIZE_KEY);
    const n = stored ? parseInt(stored, 10) : 50;
    return PAGE_SIZES.includes(n) ? n : 50;
}

export default function BestiaryManagement() {
    const { t } = useTranslation();
    const toast = useToast();
    const [pendingSearch, setPendingSearch] = useState('');
    const [creatureSearch, setCreatureSearch] = useState('');
    const [adminCreatures, setAdminCreatures] = useState<Creature[]>([]);
    const [total, setTotal] = useState(0);
    const [currentPage, setCurrentPage] = useState(1);
    const [pageSize, setPageSize] = useState<number>(getInitialPageSize);
    const [loadingCreatures, setLoadingCreatures] = useState(false);
    const [loadError, setLoadError] = useState(false);
    const [saving, setSaving] = useState(false);
    const [saveError, setSaveError] = useState(false);
    const [expandedCreatureId, setExpandedCreatureId] = useState<number | null>(null);
    const [editingCreatureDraft, setEditingCreatureDraft] = useState<Partial<Creature>>({});
    const abortRef = useRef<AbortController | null>(null);

    const loadPage = async (page: number, size: number, search: string) => {
        if (abortRef.current) abortRef.current.abort();
        abortRef.current = new AbortController();
        setLoadingCreatures(true);
        setLoadError(false);
        try {
            const result = await adminCreaturesApi.list({
                skip: (page - 1) * size,
                limit: size,
                search: search.trim() || undefined,
                include_hidden: true,
            }, abortRef.current.signal);
            setAdminCreatures(result.items);
            setTotal(result.total);
        } catch (error: any) {
            if (error?.name !== 'CanceledError' && error?.code !== 'ERR_CANCELED') {
                console.error('Failed to load admin creatures:', error);
                toast.error(t('adminBestiary.messages.loadError'));
                setLoadError(true);
            }
        } finally {
            setLoadingCreatures(false);
        }
    };

    useEffect(() => {
        void loadPage(1, pageSize, '');
    }, []);

    const handleSearch = () => {
        setCurrentPage(1);
        setCreatureSearch(pendingSearch);
        void loadPage(1, pageSize, pendingSearch);
    };

    const handlePageSizeChange = (newSize: number) => {
        sessionStorage.setItem(PAGE_SIZE_KEY, String(newSize));
        setPageSize(newSize);
        setCurrentPage(1);
        void loadPage(1, newSize, creatureSearch);
    };

    const handlePageChange = (newPage: number) => {
        setCurrentPage(newPage);
        void loadPage(newPage, pageSize, creatureSearch);
    };

    const totalPages = Math.max(1, Math.ceil(total / pageSize));
    const startEntry = total === 0 ? 0 : (currentPage - 1) * pageSize + 1;
    const endEntry = Math.min(currentPage * pageSize, total);

    const openCreatureEditor = (creature: Creature) => {
        setExpandedCreatureId((current) => (current === creature.id ? null : creature.id));
        setEditingCreatureDraft({
            id: creature.id,
            name: creature.name,
            classification: creature.classification || '',
            difficulty: creature.difficulty || '',
            is_hidden: !!creature.is_hidden,
            image_alias: creature.image_alias || '',
            image_url_override: creature.image_url_override || '',
            image_source_name: creature.image_source_name || '',
            image_locked: !!creature.image_locked,
        });
    };

    const saveCreatureEditor = async (creatureId: number, clearLocalCache: boolean = false) => {
        if (saving) return;
        setSaving(true);
        setSaveError(false);
        try {
            await adminCreaturesApi.patch(creatureId, {
                name: editingCreatureDraft.name?.trim() || undefined,
                classification: editingCreatureDraft.classification?.trim() || null,
                difficulty: editingCreatureDraft.difficulty?.trim() || null,
                is_hidden: !!editingCreatureDraft.is_hidden,
                image_alias: editingCreatureDraft.image_alias?.trim() || null,
                image_url_override: editingCreatureDraft.image_url_override?.trim() || null,
                image_source_name: editingCreatureDraft.image_source_name?.trim() || null,
                image_locked: !!editingCreatureDraft.image_locked,
                clear_local_cache: clearLocalCache,
            });

            setAdminCreatures((current) => current.map((row) => {
                if (row.id !== creatureId) return row;
                return {
                    ...row,
                    name: editingCreatureDraft.name?.trim() || row.name,
                    classification: editingCreatureDraft.classification?.trim() || undefined,
                    difficulty: editingCreatureDraft.difficulty?.trim() || undefined,
                    is_hidden: !!editingCreatureDraft.is_hidden,
                    image_alias: editingCreatureDraft.image_alias?.trim() || undefined,
                    image_url_override: editingCreatureDraft.image_url_override?.trim() || undefined,
                    image_source_name: editingCreatureDraft.image_source_name?.trim() || undefined,
                    image_locked: !!editingCreatureDraft.image_locked,
                };
            }));
            toast.success(t('adminBestiary.messages.updated'));
            if (clearLocalCache) {
                toast.success(t('adminBestiary.messages.cacheCleared'));
            }
        } catch (error) {
            console.error('Failed to save creature editor:', error);
            toast.error(t('adminBestiary.messages.updateError'));
            setSaveError(true);
        } finally {
            setSaving(false);
        }
    };

    return (
        <div className="space-y-4">
            <div className="bg-surface-base/50 border border-line rounded-lg p-4">
                <div className="flex items-center gap-3 mb-2">
                    <Database className="w-5 h-5 text-primary" />
                    <h1 className="text-xl font-semibold text-content-primary">{t('adminBestiary.title')}</h1>
                </div>
                <p className="text-sm text-content-secondary mb-4">{t('adminBestiary.subtitle')}</p>
                <div className="flex w-full gap-2 md:w-auto">
                    <Input
                        type="text"
                        value={pendingSearch}
                        onChange={(e) => setPendingSearch(e.target.value)}
                        onKeyDown={(e) => {
                            if (e.key === 'Enter') {
                                e.preventDefault();
                                handleSearch();
                            }
                        }}
                        placeholder={t('adminBestiary.searchPlaceholder')}
                        aria-label={t('adminBestiary.searchAria')}
                        className="w-full text-sm md:w-72"
                    />
                    <button
                        onClick={handleSearch}
                        className="rounded-md bg-primary px-3 py-2 text-sm font-medium text-content-on-primary hover:bg-primary-hover"
                    >
                        {t('common.search')}
                    </button>
                </div>
            </div>

            {loadError && adminCreatures.length === 0 ? (
                <ErrorState title={t('adminBestiary.states.error')} description={t('adminBestiary.states.errorHelp')} action={<button type="button" onClick={() => void loadPage(currentPage, pageSize, creatureSearch)} className="app-button-secondary">{t('common.retry')}</button>} />
            ) : loadError ? (
                <DegradedState title={t('adminBestiary.states.degraded')} description={t('adminBestiary.states.degradedHelp')} action={<button type="button" onClick={() => void loadPage(currentPage, pageSize, creatureSearch)} className="app-button-secondary app-button-sm">{t('common.retry')}</button>} />
            ) : null}

            {!(loadError && adminCreatures.length === 0) ? <div className="bg-surface-base/50 border border-line rounded-lg overflow-hidden">
                {/* Pagination header */}
                <div className="flex items-center justify-between gap-4 px-4 py-3 border-b border-line bg-surface-base/40">
                    <div className="text-sm text-content-secondary">
                        {loadingCreatures ? (
                            <span className="inline-flex items-center gap-1.5"><Loader2 className="w-3.5 h-3.5 animate-spin" /> {t('common.loading')}</span>
                        ) : (
                            <span>{total === 0 ? t('pagination.noResults') : t('adminBestiary.range', { start: startEntry, end: endEntry, total })}</span>
                        )}
                    </div>
                    <div className="flex items-center gap-3">
                        <div className="flex items-center gap-1.5 text-sm text-content-secondary">
                            <span>{t('pagination.perPage')}</span>
                            <Select
                                value={pageSize}
                                onChange={(e) => handlePageSizeChange(Number(e.target.value))}
                                className="text-xs"
                                aria-label={t('adminBestiary.perPageAria')}
                            >
                                {PAGE_SIZES.map((s) => (
                                    <option key={s} value={s}>{s}</option>
                                ))}
                            </Select>
                        </div>
                        <div className="flex items-center gap-1">
                            <button
                                onClick={() => handlePageChange(currentPage - 1)}
                                disabled={currentPage <= 1 || loadingCreatures}
                                className="rounded border border-line p-1 text-content-secondary hover:text-content-primary disabled:opacity-40"
                            >
                                <ChevronLeft className="w-4 h-4" />
                            </button>
                            <span className="text-xs text-content-secondary px-1">{t('pagination.pageShort', { page: currentPage, pageCount: totalPages })}</span>
                            <button
                                onClick={() => handlePageChange(currentPage + 1)}
                                disabled={currentPage >= totalPages || loadingCreatures}
                                className="rounded border border-line p-1 text-content-secondary hover:text-content-primary disabled:opacity-40"
                            >
                                <ChevronRight className="w-4 h-4" />
                            </button>
                        </div>
                    </div>
                </div>

                <div className="overflow-x-auto">
                    <table className="w-full">
                        <thead className="bg-surface-base/60">
                            <tr>
                                <th className="text-left p-3 text-xs font-semibold uppercase tracking-wide text-content-secondary">{t('adminBestiary.columns.creature')}</th>
                                <th className="text-left p-3 text-xs font-semibold uppercase tracking-wide text-content-secondary">{t('adminBestiary.columns.class')}</th>
                                <th className="text-left p-3 text-xs font-semibold uppercase tracking-wide text-content-secondary">{t('adminBestiary.columns.difficulty')}</th>
                                <th className="text-left p-3 text-xs font-semibold uppercase tracking-wide text-content-secondary">{t('adminBestiary.columns.status')}</th>
                                <th className="text-right p-3 text-xs font-semibold uppercase tracking-wide text-content-secondary">{t('adminBestiary.columns.action')}</th>
                            </tr>
                        </thead>
                        <tbody>
                            {loadingCreatures ? (
                                <tr>
                                    <td colSpan={5} className="p-6 text-center text-content-secondary">
                                        <span className="inline-flex items-center gap-2">
                                            <Loader2 className="w-4 h-4 animate-spin" />
                                            {t('adminBestiary.states.loading')}
                                        </span>
                                    </td>
                                </tr>
                            ) : adminCreatures.length === 0 ? (
                                <tr><td colSpan={5}><EmptyState title={t('adminBestiary.states.empty')} description={t('adminBestiary.states.emptyHelp')} /></td></tr>
                            ) : adminCreatures.map((creature) => {
                                const expanded = expandedCreatureId === creature.id;
                                return (
                                    <Fragment key={creature.id}>
                                        <tr className="border-t border-line">
                                            <td className="p-3 text-sm text-content-primary">{creature.name}</td>
                                            <td className="p-3 text-sm text-content-secondary">{creature.classification || t('common.notAvailable')}</td>
                                            <td className="p-3 text-sm text-content-secondary">{creature.difficulty || t('common.notAvailable')}</td>
                                            <td className="p-3 text-sm">
                                                {creature.is_hidden ? (
                                                    <span className="rounded bg-danger/15 px-2 py-1 text-xs text-danger">{t('adminBestiary.values.hidden')}</span>
                                                ) : (
                                                    <span className="rounded bg-success/15 px-2 py-1 text-xs text-success">{t('adminBestiary.values.visible')}</span>
                                                )}
                                            </td>
                                            <td className="p-3 text-right">
                                                <button
                                                    onClick={() => openCreatureEditor(creature)}
                                                    className="rounded border border-line px-3 py-1.5 text-xs text-content-secondary hover:border-primary/50 hover:text-primary"
                                                >
                                                    {expanded ? t('common.close') : t('adminBestiary.actions.edit')}
                                                </button>
                                            </td>
                                        </tr>
                                        {expanded && (
                                            <tr className="border-t border-line bg-surface-base/40">
                                                <td colSpan={5} className="p-4">
                                                    <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-4">
                                                        <Input
                                                            type="text"
                                                            value={editingCreatureDraft.name || ''}
                                                            onChange={(e) => setEditingCreatureDraft({ ...editingCreatureDraft, name: e.target.value })}
                                                            placeholder={t('adminBestiary.fields.name')}
                                                            aria-label={t('adminBestiary.fields.name')}
                                                            disabled={saving}
                                                        />
                                                        <Input
                                                            type="text"
                                                            value={editingCreatureDraft.classification || ''}
                                                            onChange={(e) => setEditingCreatureDraft({ ...editingCreatureDraft, classification: e.target.value })}
                                                            placeholder={t('adminBestiary.fields.classification')}
                                                            aria-label={t('adminBestiary.fields.classification')}
                                                            disabled={saving}
                                                        />
                                                        <Input
                                                            type="text"
                                                            value={editingCreatureDraft.difficulty || ''}
                                                            onChange={(e) => setEditingCreatureDraft({ ...editingCreatureDraft, difficulty: e.target.value })}
                                                            placeholder={t('adminBestiary.fields.difficulty')}
                                                            aria-label={t('adminBestiary.fields.difficulty')}
                                                            disabled={saving}
                                                        />
                                                        <label className="inline-flex items-center gap-2 text-sm text-content-secondary">
                                                            <input
                                                                type="checkbox"
                                                                checked={!!editingCreatureDraft.is_hidden}
                                                                onChange={(e) => setEditingCreatureDraft({ ...editingCreatureDraft, is_hidden: e.target.checked })}
                                                                disabled={saving}
                                                            />
                                                            {t('adminBestiary.fields.hide')}
                                                        </label>
                                                        <Input
                                                            type="text"
                                                            value={editingCreatureDraft.image_alias || ''}
                                                            onChange={(e) => setEditingCreatureDraft({ ...editingCreatureDraft, image_alias: e.target.value })}
                                                            placeholder={t('adminBestiary.fields.imageAlias')}
                                                            aria-label={t('adminBestiary.fields.imageAlias')}
                                                            disabled={saving}
                                                        />
                                                        <Input
                                                            type="text"
                                                            value={editingCreatureDraft.image_url_override || ''}
                                                            onChange={(e) => setEditingCreatureDraft({ ...editingCreatureDraft, image_url_override: e.target.value })}
                                                            placeholder={t('adminBestiary.fields.imageUrl')}
                                                            aria-label={t('adminBestiary.fields.imageUrl')}
                                                            disabled={saving}
                                                        />
                                                        <Input
                                                            type="text"
                                                            value={editingCreatureDraft.image_source_name || ''}
                                                            onChange={(e) => setEditingCreatureDraft({ ...editingCreatureDraft, image_source_name: e.target.value })}
                                                            placeholder={t('adminBestiary.fields.imageSource')}
                                                            aria-label={t('adminBestiary.fields.imageSource')}
                                                            disabled={saving}
                                                        />
                                                        <label className="inline-flex items-center gap-2 text-sm text-content-secondary">
                                                            <input
                                                                type="checkbox"
                                                                checked={!!editingCreatureDraft.image_locked}
                                                                onChange={(e) => setEditingCreatureDraft({ ...editingCreatureDraft, image_locked: e.target.checked })}
                                                                disabled={saving}
                                                            />
                                                            {t('adminBestiary.fields.lockImage')}
                                                        </label>
                                                    </div>
                                                    {saveError ? <Alert tone="danger" className="mt-3">{t('adminBestiary.states.saveError')}</Alert> : null}
                                                    <div className="mt-4 flex flex-wrap gap-2">
                                                        <button
                                                            onClick={() => void saveCreatureEditor(creature.id, false)}
                                                            disabled={saving}
                                                            className="rounded bg-success px-3 py-2 text-xs font-medium text-content-on-primary hover:bg-success-hover"
                                                        >
                                                            {saving ? t('adminBestiary.actions.saving') : t('adminBestiary.actions.save')}
                                                        </button>
                                                        <button
                                                            onClick={() => void saveCreatureEditor(creature.id, true)}
                                                            disabled={saving}
                                                            className="rounded bg-primary px-3 py-2 text-xs font-medium text-content-on-primary hover:bg-primary-hover"
                                                        >
                                                            {t('adminBestiary.actions.saveAndClear')}
                                                        </button>
                                                    </div>
                                                </td>
                                            </tr>
                                        )}
                                    </Fragment>
                                );
                            })}
                        </tbody>
                    </table>
                </div>

                {/* Pagination footer */}
                {totalPages > 1 && !loadingCreatures && (
                    <div className="flex items-center justify-center gap-1 px-4 py-3 border-t border-line bg-surface-base/40">
                        <button
                            onClick={() => handlePageChange(1)}
                            disabled={currentPage <= 1}
                            className="rounded border border-line px-2 py-1 text-xs text-content-secondary hover:text-content-primary disabled:opacity-40"
                        >«</button>
                        <button
                            onClick={() => handlePageChange(currentPage - 1)}
                            disabled={currentPage <= 1}
                            className="rounded border border-line p-1 text-content-secondary hover:text-content-primary disabled:opacity-40"
                        ><ChevronLeft className="w-4 h-4" /></button>
                        {Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
                            const half = 2;
                            let start = Math.max(1, currentPage - half);
                            const end = Math.min(totalPages, start + 4);
                            start = Math.max(1, end - 4);
                            return start + i;
                        }).map((page) => (
                            <button
                                key={page}
                                onClick={() => handlePageChange(page)}
                                className={`rounded border px-2.5 py-1 text-xs ${
                                    page === currentPage
                                        ? 'border-primary bg-primary/20 text-primary'
                                        : 'border-line text-content-secondary hover:text-content-primary'
                                }`}
                            >{page}</button>
                        ))}
                        <button
                            onClick={() => handlePageChange(currentPage + 1)}
                            disabled={currentPage >= totalPages}
                            className="rounded border border-line p-1 text-content-secondary hover:text-content-primary disabled:opacity-40"
                        ><ChevronRight className="w-4 h-4" /></button>
                        <button
                            onClick={() => handlePageChange(totalPages)}
                            disabled={currentPage >= totalPages}
                            className="rounded border border-line px-2 py-1 text-xs text-content-secondary hover:text-content-primary disabled:opacity-40"
                        >»</button>
                    </div>
                )}
            </div> : null}
        </div>
    );
}
