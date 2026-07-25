// Hunt Catalog Management Component
import { useEffect, useState } from 'react';
import { useAuth } from '../../context/AuthContext';
import { useToast } from '../../context/ToastContext';
import { huntCatalogApi, Hunt, HuntCreate } from '../../services/huntCatalog';
import {
    Compass, Plus, Edit2, Trash2, Save, X, Filter,
    TrendingUp, DollarSign, Users, MapPin, Loader2, Info
} from 'lucide-react';

export default function HuntCatalog() {
    const { user } = useAuth();
    const toast = useToast();

    const [hunts, setHunts] = useState<Hunt[]>([]);
    const [loading, setLoading] = useState(true);
    const [showModal, setShowModal] = useState(false);
    const [editingHunt, setEditingHunt] = useState<Hunt | null>(null);
    const [detailModal, setDetailModal] = useState<Hunt | null>(null);
    const [formData, setFormData] = useState<HuntCreate>({
        name: '',
        location: '',
        level_min: 0,
        level_max: 0,
        vocation: '',
        exp_per_hour: 0,
        profit_per_hour: 0,
        creatures: '',
        strategy: '',
        notes: '',
    });

    const [filters, setFilters] = useState({
        level_min: '',
        level_max: '',
        vocation: '',
        location: '',
    });
    const [showFilters, setShowFilters] = useState(false);

    const canManage = user?.is_superuser;

    useEffect(() => {
        loadHunts();
    }, [filters]);

    const loadHunts = async () => {
        setLoading(true);
        try {
            const filterParams: any = {};
            if (filters.level_min) filterParams.level_min = parseInt(filters.level_min);
            if (filters.level_max) filterParams.level_max = parseInt(filters.level_max);
            if (filters.vocation) filterParams.vocation = filters.vocation;
            if (filters.location) filterParams.location = filters.location;

            const data = await huntCatalogApi.getHunts(filterParams);
            setHunts(data);
        } catch (error) {
            console.error('Failed to load hunts:', error);
        } finally {
            setLoading(false);
        }
    };

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        try {
            if (editingHunt) {
                await huntCatalogApi.updateHunt(editingHunt.id, formData);
            } else {
                await huntCatalogApi.createHunt(formData);
            }
            setShowModal(false);
            setEditingHunt(null);
            resetForm();
            loadHunts();
            toast.success(editingHunt ? 'Hunt updated successfully!' : 'Hunt created successfully!');
        } catch (error) {
            console.error('Failed to save hunt:', error);
            toast.error('Failed to save hunt');
        }
    };

    const handleDelete = async (id: number, name: string) => {
        const confirmed = window.confirm(`Are you sure you want to delete "${name}"?`);
        if (!confirmed) return;

        try {
            await huntCatalogApi.deleteHunt(id);
            loadHunts();
            toast.success('Hunt deleted successfully');
        } catch (error) {
            console.error('Failed to delete hunt:', error);
            toast.error('Failed to delete hunt');
        }
    };

    const resetForm = () => {
        setFormData({
            name: '',
            location: '',
            level_min: 0,
            level_max: 0,
            vocation: '',
            exp_per_hour: 0,
            profit_per_hour: 0,
            creatures: '',
            strategy: '',
            notes: '',
        });
    };

    const openEditModal = (hunt: Hunt) => {
        setEditingHunt(hunt);
        setFormData({
            name: hunt.name,
            location: hunt.location,
            level_min: hunt.level_min,
            level_max: hunt.level_max,
            vocation: hunt.vocation || '',
            exp_per_hour: hunt.exp_per_hour || 0,
            profit_per_hour: hunt.profit_per_hour || 0,
            creatures: hunt.creatures,
            strategy: hunt.strategy || '',
            notes: hunt.notes || '',
        });
        setShowModal(true);
    };

    const clearFilters = () => {
        setFilters({ level_min: '', level_max: '', vocation: '', location: '' });
    };

    const formatNumber = (num: number | null) => {
        if (!num) return 'N/A';
        return num.toLocaleString();
    };

    return (
        <div className="space-y-4 sm:space-y-6">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 sm:gap-4">
                <h1 className="text-2xl sm:text-3xl font-serif text-content-primary flex items-center gap-2 sm:gap-3">
                    <Compass className="w-6 h-6 sm:w-8 sm:h-8 text-primary" />
                    Hunt Catalog
                </h1>

                <div className="flex gap-2">
                    <button
                        onClick={() => setShowFilters(!showFilters)}
                        className="flex items-center gap-2 bg-surface hover:bg-surface-raised text-content-primary px-3 sm:px-4 py-2 rounded-md transition-colors text-sm font-medium"
                    >
                        <Filter className="w-4 h-4" />
                        Filters
                    </button>

                    {canManage && (
                        <button
                            onClick={() => {
                                resetForm();
                                setEditingHunt(null);
                                setShowModal(true);
                            }}
                            className="flex items-center gap-2 bg-primary hover:bg-primary-hover text-content-on-primary px-4 py-2 rounded-md transition-colors text-sm font-medium"
                        >
                            <Plus className="w-4 h-4" />
                            Add Hunt
                        </button>
                    )}
                </div>
            </div>

            {/* Filters */}
            {showFilters && (
                <div className="bg-surface-base/50 border border-line rounded-lg p-4">
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                        <div>
                            <label className="block text-sm font-medium text-content-secondary mb-1">Min Level</label>
                            <input
                                type="number"
                                value={filters.level_min}
                                onChange={e => setFilters({ ...filters, level_min: e.target.value })}
                                placeholder="e.g. 50"
                                className="w-full bg-surface-base border border-line rounded p-2 text-content-primary text-sm"
                            />
                        </div>
                        <div>
                            <label className="block text-sm font-medium text-content-secondary mb-1">Max Level</label>
                            <input
                                type="number"
                                value={filters.level_max}
                                onChange={e => setFilters({ ...filters, level_max: e.target.value })}
                                placeholder="e.g. 150"
                                className="w-full bg-surface-base border border-line rounded p-2 text-content-primary text-sm"
                            />
                        </div>
                        <div>
                            <label className="block text-sm font-medium text-content-secondary mb-1">Vocation</label>
                            <select
                                value={filters.vocation}
                                onChange={e => setFilters({ ...filters, vocation: e.target.value })}
                                className="w-full bg-surface-base border border-line rounded p-2 text-content-primary text-sm"
                            >
                                <option value="">All</option>
                                <option value="EK">Knight</option>
                                <option value="MS">Sorcerer</option>
                                <option value="ED">Druid</option>
                                <option value="RP">Paladin</option>
                            </select>
                        </div>
                        <div>
                            <label className="block text-sm font-medium text-content-secondary mb-1">Location</label>
                            <input
                                type="text"
                                value={filters.location}
                                onChange={e => setFilters({ ...filters, location: e.target.value })}
                                placeholder="e.g. Edron"
                                className="w-full bg-surface-base border border-line rounded p-2 text-content-primary text-sm"
                            />
                        </div>
                    </div>
                    <div className="mt-3 flex justify-end">
                        <button
                            onClick={clearFilters}
                            className="text-sm text-content-secondary hover:text-content-primary flex items-center gap-1"
                        >
                            <X className="w-4 h-4" />
                            Clear filters
                        </button>
                    </div>
                </div>
            )}

            {/* Hunt Cards */}
            {loading ? (
                <div className="flex justify-center p-12">
                    <Loader2 className="w-8 h-8 animate-spin text-primary" />
                </div>
            ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                    {hunts.map(hunt => (
                        <div
                            key={hunt.id}
                            className="bg-surface-base/50 border border-line rounded-lg p-5 hover:border-primary/50 transition-all cursor-pointer"
                            onClick={() => setDetailModal(hunt)}
                        >
                            <div className="flex items-start justify-between mb-3">
                                <h3 className="text-lg font-bold text-content-primary">{hunt.name}</h3>
                                {canManage && (
                                    <div className="flex gap-1" onClick={e => e.stopPropagation()}>
                                        <button
                                            onClick={() => openEditModal(hunt)}
                                            className="p-1 text-info hover:bg-info/20 rounded"
                                        >
                                            <Edit2 className="w-4 h-4" />
                                        </button>
                                        <button
                                            onClick={() => handleDelete(hunt.id, hunt.name)}
                                            className="p-1 text-danger hover:bg-danger/20 rounded"
                                        >
                                            <Trash2 className="w-4 h-4" />
                                        </button>
                                    </div>
                                )}
                            </div>

                            <div className="flex items-center gap-2 text-sm text-content-secondary mb-3">
                                <MapPin className="w-4 h-4" />
                                {hunt.location}
                            </div>

                            <div className="space-y-2 text-sm">
                                <div className="flex justify-between">
                                    <span className="text-content-secondary">Level Range:</span>
                                    <span className="text-content-primary font-semibold">
                                        {hunt.level_min} - {hunt.level_max}
                                    </span>
                                </div>
                                {hunt.vocation && (
                                    <div className="flex justify-between">
                                        <span className="text-content-secondary">Vocation:</span>
                                        <span className="text-primary">{hunt.vocation}</span>
                                    </div>
                                )}
                                {hunt.exp_per_hour && (
                                    <div className="flex justify-between items-center">
                                        <span className="text-content-secondary flex items-center gap-1">
                                            <TrendingUp className="w-3 h-3" /> XP/hour:
                                        </span>
                                        <span className="text-success">{formatNumber(hunt.exp_per_hour)}</span>
                                    </div>
                                )}
                                {hunt.profit_per_hour && (
                                    <div className="flex justify-between items-center">
                                        <span className="text-content-secondary flex items-center gap-1">
                                            <DollarSign className="w-3 h-3" /> Profit/hour:
                                        </span>
                                        <span className="text-primary">{formatNumber(hunt.profit_per_hour)}k</span>
                                    </div>
                                )}
                            </div>

                            <div className="mt-3 pt-3 border-t border-line">
                                <div className="text-xs text-content-muted flex items-center gap-1">
                                    <Users className="w-3 h-3" />
                                    {hunt.creatures.split(',').length} creature types
                                </div>
                            </div>
                        </div>
                    ))}
                </div>
            )}

            {hunts.length === 0 && !loading && (
                <div className="text-center py-12 text-content-muted">
                    <Compass className="w-12 h-12 mx-auto mb-4 opacity-20" />
                    <p>No hunts found</p>
                </div>
            )}

            {/* Detail Modal */}
            {detailModal && (
                <div
                    className="fixed inset-0 bg-surface-base/80 backdrop-blur-sm z-50 flex items-center justify-center p-4"
                    onClick={() => setDetailModal(null)}
                >
                    <div
                        className="bg-surface-base border border-line rounded-lg w-full max-w-2xl shadow-2xl max-h-[80vh] overflow-y-auto"
                        onClick={e => e.stopPropagation()}
                    >
                        <div className="sticky top-0 bg-surface-base p-6 border-b border-line flex items-center justify-between">
                            <div>
                                <h3 className="text-2xl font-bold text-content-primary">{detailModal.name}</h3>
                                <div className="flex items-center gap-2 text-content-secondary mt-1">
                                    <MapPin className="w-4 h-4" />
                                    {detailModal.location}
                                </div>
                            </div>
                            <button onClick={() => setDetailModal(null)} className="text-content-secondary hover:text-content-primary">
                                <X className="w-6 h-6" />
                            </button>
                        </div>

                        <div className="p-6 space-y-4">
                            <div className="grid grid-cols-2 gap-4">
                                <div className="bg-surface-base/50 rounded p-3">
                                    <div className="text-sm text-content-secondary">Level Range</div>
                                    <div className="text-xl font-bold text-content-primary">
                                        {detailModal.level_min} - {detailModal.level_max}
                                    </div>
                                </div>
                                {detailModal.vocation && (
                                    <div className="bg-surface-base/50 rounded p-3">
                                        <div className="text-sm text-content-secondary">Recommended Vocation</div>
                                        <div className="text-xl font-bold text-primary">{detailModal.vocation}</div>
                                    </div>
                                )}
                                {detailModal.exp_per_hour && (
                                    <div className="bg-surface-base/50 rounded p-3">
                                        <div className="text-sm text-content-secondary flex items-center gap-1">
                                            <TrendingUp className="w-4 h-4" /> Experience/hour
                                        </div>
                                        <div className="text-xl font-bold text-success">
                                            {formatNumber(detailModal.exp_per_hour)}
                                        </div>
                                    </div>
                                )}
                                {detailModal.profit_per_hour && (
                                    <div className="bg-surface-base/50 rounded p-3">
                                        <div className="text-sm text-content-secondary flex items-center gap-1">
                                            <DollarSign className="w-4 h-4" /> Profit/hour
                                        </div>
                                        <div className="text-xl font-bold text-primary">
                                            {formatNumber(detailModal.profit_per_hour)}k
                                        </div>
                                    </div>
                                )}
                            </div>

                            <div>
                                <h4 className="text-sm font-semibold text-content-secondary mb-2 flex items-center gap-2">
                                    <Users className="w-4 h-4" /> Creatures
                                </h4>
                                <div className="bg-surface-base/50 rounded p-3 text-content-secondary">
                                    {detailModal.creatures}
                                </div>
                            </div>

                            {detailModal.strategy && (
                                <div>
                                    <h4 className="text-sm font-semibold text-content-secondary mb-2">Strategy</h4>
                                    <div className="bg-surface-base/50 rounded p-3 text-content-secondary whitespace-pre-line">
                                        {detailModal.strategy}
                                    </div>
                                </div>
                            )}

                            {detailModal.notes && (
                                <div>
                                    <h4 className="text-sm font-semibold text-content-secondary mb-2 flex items-center gap-2">
                                        <Info className="w-4 h-4" /> Additional Notes
                                    </h4>
                                    <div className="bg-primary/20 border border-primary/50 rounded p-3 text-content-secondary text-sm whitespace-pre-line">
                                        {detailModal.notes}
                                    </div>
                                </div>
                            )}
                        </div>
                    </div>
                </div>
            )}

            {/* Create/Edit Modal */}
            {showModal && (
                <div className="fixed inset-0 bg-surface-base/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
                    <div className="bg-surface-base border border-line rounded-lg w-full max-w-2xl shadow-2xl max-h-[90vh] overflow-y-auto">
                        <div className="p-6 border-b border-line">
                            <h3 className="text-xl font-bold text-content-primary">
                                {editingHunt ? 'Edit Hunt' : 'Add New Hunt'}
                            </h3>
                        </div>

                        <form onSubmit={handleSubmit} className="p-6 space-y-4">
                            <div className="grid grid-cols-2 gap-4">
                                <div className="col-span-2">
                                    <label className="block text-sm font-medium text-content-secondary mb-1">Hunt Name *</label>
                                    <input
                                        type="text"
                                        required
                                        value={formData.name}
                                        onChange={e => setFormData({ ...formData, name: e.target.value })}
                                        className="w-full bg-surface-base border border-line rounded p-2 text-content-primary"
                                    />
                                </div>

                                <div className="col-span-2">
                                    <label className="block text-sm font-medium text-content-secondary mb-1">Location *</label>
                                    <input
                                        type="text"
                                        required
                                        value={formData.location}
                                        onChange={e => setFormData({ ...formData, location: e.target.value })}
                                        className="w-full bg-surface-base border border-line rounded p-2 text-content-primary"
                                    />
                                </div>

                                <div>
                                    <label className="block text-sm font-medium text-content-secondary mb-1">Min Level *</label>
                                    <input
                                        type="number"
                                        required
                                        value={formData.level_min}
                                        onChange={e => setFormData({ ...formData, level_min: parseInt(e.target.value) })}
                                        className="w-full bg-surface-base border border-line rounded p-2 text-content-primary"
                                    />
                                </div>

                                <div>
                                    <label className="block text-sm font-medium text-content-secondary mb-1">Max Level *</label>
                                    <input
                                        type="number"
                                        required
                                        value={formData.level_max}
                                        onChange={e => setFormData({ ...formData, level_max: parseInt(e.target.value) })}
                                        className="w-full bg-surface-base border border-line rounded p-2 text-content-primary"
                                    />
                                </div>

                                <div>
                                    <label className="block text-sm font-medium text-content-secondary mb-1">Vocation</label>
                                    <input
                                        type="text"
                                        value={formData.vocation}
                                        onChange={e => setFormData({ ...formData, vocation: e.target.value })}
                                        placeholder="e.g., EK, MS, All"
                                        className="w-full bg-surface-base border border-line rounded p-2 text-content-primary"
                                    />
                                </div>

                                <div>
                                    <label className="block text-sm font-medium text-content-secondary mb-1">XP/hour</label>
                                    <input
                                        type="number"
                                        value={formData.exp_per_hour}
                                        onChange={e => setFormData({ ...formData, exp_per_hour: parseInt(e.target.value) })}
                                        className="w-full bg-surface-base border border-line rounded p-2 text-content-primary"
                                    />
                                </div>

                                <div className="col-span-2">
                                    <label className="block text-sm font-medium text-content-secondary mb-1">Profit/hour (k)</label>
                                    <input
                                        type="number"
                                        value={formData.profit_per_hour}
                                        onChange={e => setFormData({ ...formData, profit_per_hour: parseInt(e.target.value) })}
                                        className="w-full bg-surface-base border border-line rounded p-2 text-content-primary"
                                    />
                                </div>

                                <div className="col-span-2">
                                    <label className="block text-sm font-medium text-content-secondary mb-1">Creatures *</label>
                                    <textarea
                                        required
                                        rows={2}
                                        value={formData.creatures}
                                        onChange={e => setFormData({ ...formData, creatures: e.target.value })}
                                        placeholder="e.g., Dragon, Dragon Lord, Wyrm"
                                        className="w-full bg-surface-base border border-line rounded p-2 text-content-primary text-sm"
                                    />
                                </div>

                                <div className="col-span-2">
                                    <label className="block text-sm font-medium text-content-secondary mb-1">Strategy</label>
                                    <textarea
                                        rows={3}
                                        value={formData.strategy}
                                        onChange={e => setFormData({ ...formData, strategy: e.target.value })}
                                        className="w-full bg-surface-base border border-line rounded p-2 text-content-primary text-sm"
                                    />
                                </div>

                                <div className="col-span-2">
                                    <label className="block text-sm font-medium text-content-secondary mb-1">Notes</label>
                                    <textarea
                                        rows={2}
                                        value={formData.notes}
                                        onChange={e => setFormData({ ...formData, notes: e.target.value })}
                                        className="w-full bg-surface-base border border-line rounded p-2 text-content-primary text-sm"
                                    />
                                </div>
                            </div>

                            <div className="flex justify-end gap-3 mt-6">
                                <button
                                    type="button"
                                    onClick={() => {
                                        setShowModal(false);
                                        setEditingHunt(null);
                                        resetForm();
                                    }}
                                    className="px-4 py-2 text-content-secondary hover:text-content-primary font-medium"
                                >
                                    Cancel
                                </button>
                                <button
                                    type="submit"
                                    className="bg-primary hover:bg-primary-hover text-content-on-primary px-4 py-2 rounded-md font-medium flex items-center gap-2"
                                >
                                    <Save className="w-4 h-4" />
                                    {editingHunt ? 'Update' : 'Create'}
                                </button>
                            </div>
                        </form>
                    </div>
                </div>
            )}
        </div>
    );
}
