import { Fragment, useEffect, useRef, useState } from 'react';
import { adminCreaturesApi } from '../../services/api';
import type { Creature } from '../../types';
import { useToast } from '../../context/ToastContext';
import { ChevronLeft, ChevronRight, Database, Loader2 } from 'lucide-react';

const PAGE_SIZE_KEY = 'admin_bestiary_page_size';
const PAGE_SIZES = [20, 50, 100];

function getInitialPageSize(): number {
    const stored = sessionStorage.getItem(PAGE_SIZE_KEY);
    const n = stored ? parseInt(stored, 10) : 50;
    return PAGE_SIZES.includes(n) ? n : 50;
}

export default function BestiaryManagement() {
    const toast = useToast();
    const [pendingSearch, setPendingSearch] = useState('');
    const [creatureSearch, setCreatureSearch] = useState('');
    const [adminCreatures, setAdminCreatures] = useState<Creature[]>([]);
    const [total, setTotal] = useState(0);
    const [currentPage, setCurrentPage] = useState(1);
    const [pageSize, setPageSize] = useState<number>(getInitialPageSize);
    const [loadingCreatures, setLoadingCreatures] = useState(false);
    const [expandedCreatureId, setExpandedCreatureId] = useState<number | null>(null);
    const [editingCreatureDraft, setEditingCreatureDraft] = useState<Partial<Creature>>({});
    const abortRef = useRef<AbortController | null>(null);

    const loadPage = async (page: number, size: number, search: string) => {
        if (abortRef.current) abortRef.current.abort();
        abortRef.current = new AbortController();
        setLoadingCreatures(true);
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
                toast.error('Failed to load creatures');
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
            toast.success('Creature updated');
            if (clearLocalCache) {
                toast.success('Local image cache cleared for creature');
            }
        } catch (error) {
            console.error('Failed to save creature editor:', error);
            toast.error('Failed to update creature');
        }
    };

    return (
        <div className="space-y-4">
            <div className="bg-surface-base/50 border border-line rounded-lg p-4">
                <div className="flex items-center gap-3 mb-2">
                    <Database className="w-5 h-5 text-primary" />
                    <h1 className="text-xl font-semibold text-content-primary">Bestiary Management</h1>
                </div>
                <p className="text-sm text-content-secondary mb-4">Creature data and image fields. Search and paginate below.</p>
                <div className="flex w-full gap-2 md:w-auto">
                    <input
                        type="text"
                        value={pendingSearch}
                        onChange={(e) => setPendingSearch(e.target.value)}
                        onKeyDown={(e) => {
                            if (e.key === 'Enter') {
                                e.preventDefault();
                                handleSearch();
                            }
                        }}
                        placeholder="Search creature..."
                        className="w-full rounded-md border border-line bg-surface-base px-3 py-2 text-sm text-content-primary md:w-72"
                    />
                    <button
                        onClick={handleSearch}
                        className="rounded-md bg-primary px-3 py-2 text-sm font-medium text-content-on-primary hover:bg-primary-hover"
                    >
                        Search
                    </button>
                </div>
            </div>

            <div className="bg-surface-base/50 border border-line rounded-lg overflow-hidden">
                {/* Pagination header */}
                <div className="flex items-center justify-between gap-4 px-4 py-3 border-b border-line bg-surface-base/40">
                    <div className="text-sm text-content-secondary">
                        {loadingCreatures ? (
                            <span className="inline-flex items-center gap-1.5"><Loader2 className="w-3.5 h-3.5 animate-spin" /> Loading…</span>
                        ) : (
                            <span>{total === 0 ? 'No results' : `${startEntry}–${endEntry} of ${total} creatures`}</span>
                        )}
                    </div>
                    <div className="flex items-center gap-3">
                        <div className="flex items-center gap-1.5 text-sm text-content-secondary">
                            <span>Per page:</span>
                            <select
                                value={pageSize}
                                onChange={(e) => handlePageSizeChange(Number(e.target.value))}
                                className="rounded border border-line bg-surface-base px-2 py-1 text-content-primary text-xs"
                            >
                                {PAGE_SIZES.map((s) => (
                                    <option key={s} value={s}>{s}</option>
                                ))}
                            </select>
                        </div>
                        <div className="flex items-center gap-1">
                            <button
                                onClick={() => handlePageChange(currentPage - 1)}
                                disabled={currentPage <= 1 || loadingCreatures}
                                className="rounded border border-line p-1 text-content-secondary hover:text-content-primary disabled:opacity-40"
                            >
                                <ChevronLeft className="w-4 h-4" />
                            </button>
                            <span className="text-xs text-content-secondary px-1">{currentPage} / {totalPages}</span>
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
                                <th className="text-left p-3 text-xs font-semibold uppercase tracking-wide text-content-secondary">Creature</th>
                                <th className="text-left p-3 text-xs font-semibold uppercase tracking-wide text-content-secondary">Class</th>
                                <th className="text-left p-3 text-xs font-semibold uppercase tracking-wide text-content-secondary">Difficulty</th>
                                <th className="text-left p-3 text-xs font-semibold uppercase tracking-wide text-content-secondary">Status</th>
                                <th className="text-right p-3 text-xs font-semibold uppercase tracking-wide text-content-secondary">Action</th>
                            </tr>
                        </thead>
                        <tbody>
                            {loadingCreatures ? (
                                <tr>
                                    <td colSpan={5} className="p-6 text-center text-content-secondary">
                                        <span className="inline-flex items-center gap-2">
                                            <Loader2 className="w-4 h-4 animate-spin" />
                                            Loading creatures...
                                        </span>
                                    </td>
                                </tr>
                            ) : adminCreatures.length === 0 ? (
                                <tr>
                                    <td colSpan={5} className="p-6 text-center text-content-muted">No creatures found.</td>
                                </tr>
                            ) : adminCreatures.map((creature) => {
                                const expanded = expandedCreatureId === creature.id;
                                return (
                                    <Fragment key={creature.id}>
                                        <tr className="border-t border-line">
                                            <td className="p-3 text-sm text-content-primary">{creature.name}</td>
                                            <td className="p-3 text-sm text-content-secondary">{creature.classification || 'N/A'}</td>
                                            <td className="p-3 text-sm text-content-secondary">{creature.difficulty || 'N/A'}</td>
                                            <td className="p-3 text-sm">
                                                {creature.is_hidden ? (
                                                    <span className="rounded bg-danger/15 px-2 py-1 text-xs text-danger">Hidden</span>
                                                ) : (
                                                    <span className="rounded bg-success/15 px-2 py-1 text-xs text-success">Visible</span>
                                                )}
                                            </td>
                                            <td className="p-3 text-right">
                                                <button
                                                    onClick={() => openCreatureEditor(creature)}
                                                    className="rounded border border-line px-3 py-1.5 text-xs text-content-secondary hover:border-primary/50 hover:text-primary"
                                                >
                                                    {expanded ? 'Close' : 'Edit'}
                                                </button>
                                            </td>
                                        </tr>
                                        {expanded && (
                                            <tr className="border-t border-line bg-surface-base/40">
                                                <td colSpan={5} className="p-4">
                                                    <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-4">
                                                        <input
                                                            type="text"
                                                            value={editingCreatureDraft.name || ''}
                                                            onChange={(e) => setEditingCreatureDraft({ ...editingCreatureDraft, name: e.target.value })}
                                                            placeholder="Name"
                                                            className="rounded border border-line bg-surface-base px-3 py-2 text-sm text-content-primary"
                                                        />
                                                        <input
                                                            type="text"
                                                            value={editingCreatureDraft.classification || ''}
                                                            onChange={(e) => setEditingCreatureDraft({ ...editingCreatureDraft, classification: e.target.value })}
                                                            placeholder="Classification"
                                                            className="rounded border border-line bg-surface-base px-3 py-2 text-sm text-content-primary"
                                                        />
                                                        <input
                                                            type="text"
                                                            value={editingCreatureDraft.difficulty || ''}
                                                            onChange={(e) => setEditingCreatureDraft({ ...editingCreatureDraft, difficulty: e.target.value })}
                                                            placeholder="Difficulty"
                                                            className="rounded border border-line bg-surface-base px-3 py-2 text-sm text-content-primary"
                                                        />
                                                        <label className="inline-flex items-center gap-2 text-sm text-content-secondary">
                                                            <input
                                                                type="checkbox"
                                                                checked={!!editingCreatureDraft.is_hidden}
                                                                onChange={(e) => setEditingCreatureDraft({ ...editingCreatureDraft, is_hidden: e.target.checked })}
                                                            />
                                                            Hide creature
                                                        </label>
                                                        <input
                                                            type="text"
                                                            value={editingCreatureDraft.image_alias || ''}
                                                            onChange={(e) => setEditingCreatureDraft({ ...editingCreatureDraft, image_alias: e.target.value })}
                                                            placeholder="Image alias"
                                                            className="rounded border border-line bg-surface-base px-3 py-2 text-sm text-content-primary"
                                                        />
                                                        <input
                                                            type="text"
                                                            value={editingCreatureDraft.image_url_override || ''}
                                                            onChange={(e) => setEditingCreatureDraft({ ...editingCreatureDraft, image_url_override: e.target.value })}
                                                            placeholder="Image URL override"
                                                            className="rounded border border-line bg-surface-base px-3 py-2 text-sm text-content-primary"
                                                        />
                                                        <input
                                                            type="text"
                                                            value={editingCreatureDraft.image_source_name || ''}
                                                            onChange={(e) => setEditingCreatureDraft({ ...editingCreatureDraft, image_source_name: e.target.value })}
                                                            placeholder="Image source"
                                                            className="rounded border border-line bg-surface-base px-3 py-2 text-sm text-content-primary"
                                                        />
                                                        <label className="inline-flex items-center gap-2 text-sm text-content-secondary">
                                                            <input
                                                                type="checkbox"
                                                                checked={!!editingCreatureDraft.image_locked}
                                                                onChange={(e) => setEditingCreatureDraft({ ...editingCreatureDraft, image_locked: e.target.checked })}
                                                            />
                                                            Lock image fields
                                                        </label>
                                                    </div>
                                                    <div className="mt-4 flex flex-wrap gap-2">
                                                        <button
                                                            onClick={() => void saveCreatureEditor(creature.id, false)}
                                                            className="rounded bg-success px-3 py-2 text-xs font-medium text-content-on-primary hover:bg-success-hover"
                                                        >
                                                            Save changes
                                                        </button>
                                                        <button
                                                            onClick={() => void saveCreatureEditor(creature.id, true)}
                                                            className="rounded bg-primary px-3 py-2 text-xs font-medium text-content-on-primary hover:bg-primary-hover"
                                                        >
                                                            Save + Clear local image cache
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
            </div>
        </div>
    );
}
