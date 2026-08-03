import { useEffect, useState, useRef, useCallback } from "react";
import { guildApi, Announcement } from "../../services/guild";
import { useAuth } from "../../context/AuthContext";
import { useToast } from "../../context/ToastContext";
import { useTranslation } from "react-i18next";

import {
  Plus,
  Megaphone,
  Loader2,
  Filter,
  X,
  CalendarClock,
  User,
} from "lucide-react";
import { useGuildContext } from "../../utils/guildContext";
import { useGuildCapability } from "../../hooks/useGuildCapability";

export default function Announcements() {
  const { user } = useAuth();
  const { t } = useTranslation();
  const toast = useToast();
  const guildName = useGuildContext(user);
  const { canManageGuild } = useGuildCapability("announcements.manage");

  const [announcements, setAnnouncements] = useState<Announcement[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [hasMore, setHasMore] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [detailModal, setDetailModal] = useState<Announcement | null>(null);
  const [formData, setFormData] = useState({
    title: "",
    content: "",
    type: "general",
  });
  const [creating, setCreating] = useState(false);

  // Filters
  const [filters, setFilters] = useState({
    type: "",
    author: "",
    dateFrom: "",
    dateTo: "",
  });
  const [showFilters, setShowFilters] = useState(false);
  const [skip, setSkip] = useState(0);
  const LIMIT = 10;

  // Infinite scroll
  const observer = useRef<IntersectionObserver | null>(null);
  const lastElementRef = useCallback(
    (node: HTMLDivElement | null) => {
      if (loadingMore) return;
      if (observer.current) observer.current.disconnect();
      observer.current = new IntersectionObserver((entries) => {
        if (entries[0].isIntersecting && hasMore) {
          loadMore();
        }
      });
      if (node) observer.current.observe(node);
    },
    [loadingMore, hasMore],
  );

  const canCreate = canManageGuild(guildName);

  const loadData = async (reset = false) => {
    try {
      const currentSkip = reset ? 0 : skip;
      if (reset) {
        setLoading(true);
        setSkip(0);
      } else {
        setLoadingMore(true);
      }

      if (!guildName) {
        setAnnouncements([]);
        return;
      }
      const data = await guildApi.getAnnouncements(
        currentSkip,
        LIMIT,
        guildName,
      );

      if (reset) {
        setAnnouncements(data);
      } else {
        setAnnouncements((prev) => [...prev, ...data]);
      }

      setHasMore(data.length === LIMIT);
      if (!reset) setSkip((prev) => prev + LIMIT);
    } catch (error) {
      console.error("Failed to load announcements", error);
    } finally {
      setLoading(false);
      setLoadingMore(false);
    }
  };

  const loadMore = () => {
    if (!loadingMore && hasMore) {
      loadData(false);
    }
  };

  useEffect(() => {
    loadData(true);
  }, [filters, guildName]);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    setCreating(true);
    try {
      if (!guildName) throw new Error("Missing guild context");
      await guildApi.createAnnouncement(formData, guildName);
      setShowModal(false);
      setFormData({ title: "", content: "", type: "general" });
      loadData(true);
      toast.success("Announcement created successfully!");
    } catch (error) {
      console.error("Failed to create announcement", error);
      toast.error("Failed to create announcement");
    } finally {
      setCreating(false);
    }
  };

  const applyFilters = (data: Announcement[]) => {
    return data.filter((ann) => {
      if (filters.type && ann.type !== filters.type) return false;
      if (
        filters.author &&
        !ann.author?.username
          .toLowerCase()
          .includes(filters.author.toLowerCase())
      )
        return false;
      if (
        filters.dateFrom &&
        new Date(ann.created_at) < new Date(filters.dateFrom)
      )
        return false;
      if (filters.dateTo && new Date(ann.created_at) > new Date(filters.dateTo))
        return false;
      return true;
    });
  };

  const clearFilters = () => {
    setFilters({ type: "", author: "", dateFrom: "", dateTo: "" });
  };

  const filteredAnnouncements = applyFilters(announcements);

  return (
    <div className="space-y-8">
      <div className="border-b border-primary/30 pb-6">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <h1 className="text-4xl lg:text-5xl font-bold text-content-primary flex items-center gap-3">
            <div className="p-3 bg-gradient-to-br from-primary/20 to-primary/20 rounded-lg">
              <Megaphone className="w-8 h-8 lg:w-10 lg:h-10 text-primary" />
            </div>
            {t("guild.announcements")}
          </h1>

          <div className="flex gap-3">
            <button
              onClick={() => setShowFilters(!showFilters)}
              className="flex items-center gap-2 bg-surface/80 hover:bg-surface-raised/80 border border-line hover:border-primary/40 text-content-primary px-4 py-3 rounded-lg transition-all font-semibold text-base"
            >
              <Filter className="w-5 h-5" />
              <span className="hidden xs:inline">{t("guild.filters")}</span>
            </button>

            {canCreate && (
              <button
                onClick={() => setShowModal(true)}
                className="flex items-center gap-2 rounded-lg bg-gradient-to-r from-primary to-primary-hover px-4 py-3 text-base font-semibold text-content-inverse shadow-sm transition-all hover:shadow-primary/30"
              >
                <Plus className="w-5 h-5" />
                <span className="hidden xs:inline">{t("guild.create")}</span>
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Filters Panel */}
      {showFilters && (
        <div className="rounded-xl bg-surface-raised p-6 shadow-sm">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
            <div>
              <label className="block text-xs font-bold text-content-secondary mb-2 uppercase tracking-wider">
                {t("guild.type")}
              </label>
              <select
                value={filters.type}
                onChange={(e) =>
                  setFilters({ ...filters, type: e.target.value })
                }
                className="w-full bg-surface-base/60 border-2 border-line/60 hover:border-line rounded-lg p-3 text-content-primary text-sm focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20 transition-all"
              >
                <option value="">{t("common.filter")}...</option>
                <option value="general">{t("guild.types.general")}</option>
                <option value="hunt">{t("guild.types.hunt")}</option>
                <option value="contest">{t("guild.types.contest")}</option>
              </select>
            </div>

            <div>
              <label className="block text-xs font-bold text-content-secondary mb-2 uppercase tracking-wider">
                {t("guild.author")}
              </label>
              <input
                type="text"
                value={filters.author}
                onChange={(e) =>
                  setFilters({ ...filters, author: e.target.value })
                }
                placeholder={t("common.search") + "..."}
                className="w-full rounded-lg bg-surface px-3 py-3 text-sm text-content-primary placeholder:text-content-muted focus:outline-none focus:ring-2 focus:ring-primary/20"
              />
            </div>

            <div>
              <label className="block text-xs font-bold text-content-secondary mb-2 uppercase tracking-wider">
                {t("guild.filterByDate")} (desde)
              </label>
              <input
                type="date"
                value={filters.dateFrom}
                onChange={(e) =>
                  setFilters({ ...filters, dateFrom: e.target.value })
                }
                className="w-full bg-surface-base/60 border-2 border-line/60 hover:border-line rounded-lg p-3 text-content-primary text-sm focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20 transition-all"
              />
            </div>

            <div>
              <label className="block text-xs font-bold text-content-secondary mb-2 uppercase tracking-wider">
                {t("guild.filterByDate")} (hasta)
              </label>
              <input
                type="date"
                value={filters.dateTo}
                onChange={(e) =>
                  setFilters({ ...filters, dateTo: e.target.value })
                }
                className="w-full bg-surface-base/60 border-2 border-line/60 hover:border-line rounded-lg p-3 text-content-primary text-sm focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20 transition-all"
              />
            </div>
          </div>

          <div className="mt-5 flex justify-end">
            <button
              onClick={clearFilters}
              className="text-sm text-content-secondary hover:text-primary hover:bg-surface/50 flex items-center gap-2 px-3 py-1.5 rounded-lg transition-all font-medium"
            >
              <X className="w-4 h-4" />
              {t("guild.clearFilters")}
            </button>
          </div>
        </div>
      )}

      {loading ? (
        <div className="flex justify-center p-12">
          <Loader2 className="w-8 h-8 animate-spin text-primary" />
        </div>
      ) : (
        <div className="space-y-6">
          {filteredAnnouncements.map((ann, index) => {
            const isLast = index === filteredAnnouncements.length - 1;
            return (
              <div
                key={ann.id}
                ref={isLast ? lastElementRef : null}
                onClick={() => setDetailModal(ann)}
                className="group cursor-pointer overflow-hidden rounded-xl bg-surface-raised shadow-sm transition-all duration-300 hover:-translate-y-0.5 hover:shadow-primary/20"
              >
                <div
                  className={`h-2 w-full transition-all duration-300 ${
                    ann.type === "contest"
                      ? "bg-gradient-to-r from-accent to-accent"
                      : ann.type === "hunt"
                        ? "bg-gradient-to-r from-danger to-danger"
                        : "bg-gradient-to-r from-primary to-primary-hover"
                  }`}
                />
                <div className="p-8">
                  <div className="flex flex-col lg:flex-row lg:items-start lg:justify-between gap-4 mb-6">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-3 mb-3">
                        <span
                          className={`inline-block px-3 py-1 rounded-full text-xs font-bold uppercase tracking-wider whitespace-nowrap ${
                            ann.type === "contest"
                              ? "bg-accent/15 text-accent ring-1 ring-accent/60"
                              : ann.type === "hunt"
                                ? "bg-danger/15 text-danger ring-1 ring-danger/60"
                                : "bg-primary/15 text-primary ring-1 ring-primary/60"
                          }`}
                        >
                          {t(`guild.types.${ann.type}`)}
                        </span>
                      </div>
                      <h2 className="text-2xl lg:text-3xl font-bold text-content-primary leading-tight group-hover:text-primary transition-colors break-words">
                        {ann.title}
                      </h2>
                    </div>
                    <div className="text-sm text-content-secondary flex flex-col gap-2 lg:text-right whitespace-nowrap">
                      <div className="flex items-center gap-2 lg:justify-end">
                        <CalendarClock className="w-4 h-4 flex-shrink-0 text-primary/70" />
                        <span className="font-medium">
                          {new Date(ann.created_at).toLocaleDateString()}
                        </span>
                      </div>
                      <div className="flex items-center gap-2 lg:justify-end">
                        <User className="w-4 h-4 flex-shrink-0 text-primary/70" />
                        <span className="text-content-secondary font-semibold">
                          {ann.author?.is_superuser
                            ? "👑 Ray On"
                            : ann.author?.username}
                        </span>
                      </div>
                    </div>
                  </div>

                  <div className="prose prose-invert prose-sm max-w-none text-content-secondary line-clamp-4 leading-relaxed text-base">
                    {ann.content}
                  </div>

                  <div className="mt-4 pt-4 border-t border-line/50 flex items-center justify-end">
                    <span className="text-xs text-content-muted group-hover:text-primary/70 transition-colors">
                      Click para ver más →
                    </span>
                  </div>
                </div>
              </div>
            );
          })}

          {loadingMore && (
            <div className="flex justify-center p-4">
              <Loader2 className="w-6 h-6 animate-spin text-primary" />
            </div>
          )}

          {!hasMore && announcements.length > 0 && (
            <div className="text-center py-8">
              <p className="text-sm text-content-muted font-medium">
                {t("guild.noMoreResults")}
              </p>
            </div>
          )}

          {!loading && announcements.length === 0 && (
            <div className="text-center py-16">
              <div className="flex justify-center mb-4">
                <Megaphone className="w-16 h-16 text-content-muted opacity-50" />
              </div>
              <p className="text-content-secondary text-lg font-medium">
                {t("guild.noAnnouncements")}
              </p>
              <p className="text-content-muted text-sm mt-2">
                Vuelve más tarde para nuevos anuncios
              </p>
            </div>
          )}
        </div>
      )}

      {/* Detail Modal */}
      {detailModal && (
        <div
          className="fixed inset-0 bg-surface-base/90 backdrop-blur-md z-modal flex items-center justify-center p-4"
          onClick={() => setDetailModal(null)}
        >
          <div
            className="bg-gradient-to-b from-surface to-surface-base border-2 border-line/80 rounded-2xl w-full max-w-4xl shadow-2xl max-h-[85vh] overflow-y-auto"
            onClick={(e) => e.stopPropagation()}
          >
            <div
              className={`h-3 w-full ${
                detailModal.type === "contest"
                  ? "bg-gradient-to-r from-accent to-accent"
                  : detailModal.type === "hunt"
                    ? "bg-gradient-to-r from-danger to-danger"
                    : "bg-gradient-to-r from-primary to-primary-hover"
              }`}
            />

            <div className="sticky top-0 bg-surface-base/95 backdrop-blur p-8 border-b-2 border-line/50 flex items-start justify-between">
              <div className="flex-1 pr-4">
                <div className="flex items-center gap-3 mb-4">
                  <span
                    className={`inline-block px-4 py-1.5 rounded-full text-xs font-bold uppercase tracking-wider ${
                      detailModal.type === "contest"
                        ? "bg-accent/15 text-accent ring-1 ring-accent/60"
                        : detailModal.type === "hunt"
                          ? "bg-danger/15 text-danger ring-1 ring-danger/60"
                          : "bg-primary/15 text-primary ring-1 ring-primary/60"
                    }`}
                  >
                    {t(`guild.types.${detailModal.type}`)}
                  </span>
                </div>
                <h3 className="text-3xl lg:text-4xl font-bold text-content-primary leading-tight break-words">
                  {detailModal.title}
                </h3>
                <div className="flex flex-col sm:flex-row sm:items-center gap-3 sm:gap-6 mt-4 text-sm">
                  <div className="flex items-center gap-2 text-content-secondary">
                    <User className="w-5 h-5 text-primary/70" />
                    <span className="font-semibold text-content-secondary">
                      {detailModal.author?.is_superuser
                        ? "👑 Ray On"
                        : detailModal.author?.username}
                    </span>
                  </div>
                  <div className="flex items-center gap-2 text-content-secondary">
                    <CalendarClock className="w-5 h-5 text-primary/70" />
                    <span className="font-medium">
                      {new Date(detailModal.created_at).toLocaleString()}
                    </span>
                  </div>
                </div>
              </div>
              <button
                onClick={() => setDetailModal(null)}
                className="text-content-secondary hover:text-content-primary hover:bg-surface p-2 rounded-lg transition-colors flex-shrink-0"
              >
                <X className="w-6 h-6" />
              </button>
            </div>

            <div className="p-8 lg:p-10">
              <div className="prose prose-invert prose-lg max-w-none text-content-secondary whitespace-pre-line leading-relaxed">
                {detailModal.content}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Create Modal */}
      {showModal && (
        <div className="fixed inset-0 bg-surface-base/90 backdrop-blur-md z-modal flex items-center justify-center p-4">
          <div className="bg-gradient-to-b from-surface to-surface-base border-2 border-line/80 rounded-2xl w-full max-w-2xl shadow-2xl">
            <div className="p-8 border-b-2 border-line/50">
              <div className="flex items-center gap-3 mb-2">
                <Megaphone className="w-6 h-6 text-primary" />
                <h3 className="text-2xl font-bold text-content-primary">
                  {t("guild.create")} {t("guild.announcements")}
                </h3>
              </div>
              <p className="text-content-secondary text-sm">
                {t("guild.announcements")} ({t("guild.create")})
              </p>
            </div>

            <form onSubmit={handleCreate} className="p-8 space-y-6">
              <div>
                <label className="block text-sm font-bold text-content-secondary mb-3 uppercase tracking-wider">
                  {t("guild.title")}
                </label>
                <input
                  type="text"
                  required
                  value={formData.title}
                  onChange={(e) =>
                    setFormData({ ...formData, title: e.target.value })
                  }
                  placeholder="Escribir el título del anuncio..."
                  className="w-full rounded-lg bg-surface px-4 py-3 text-base text-content-primary placeholder:text-content-muted focus:outline-none focus:ring-2 focus:ring-primary/20"
                />
              </div>

              <div>
                <label className="block text-sm font-bold text-content-secondary mb-3 uppercase tracking-wider">
                  {t("guild.type")}
                </label>
                <select
                  value={formData.type}
                  onChange={(e) =>
                    setFormData({ ...formData, type: e.target.value })
                  }
                  className="w-full bg-surface-base/80 border-2 border-line/60 rounded-lg px-4 py-3 text-content-primary focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20 transition-all text-base"
                >
                  <option value="general">{t("guild.types.general")}</option>
                  <option value="contest">{t("guild.types.contest")}</option>
                  <option value="hunt">{t("guild.types.hunt")}</option>
                </select>
              </div>

              <div>
                <label className="block text-sm font-bold text-content-secondary mb-3 uppercase tracking-wider">
                  {t("guild.content")}
                </label>
                <textarea
                  required
                  rows={8}
                  value={formData.content}
                  onChange={(e) =>
                    setFormData({ ...formData, content: e.target.value })
                  }
                  placeholder="Escribir el contenido del anuncio..."
                  className="w-full rounded-lg bg-surface px-4 py-3 font-mono text-sm leading-relaxed text-content-primary placeholder:text-content-muted focus:outline-none focus:ring-2 focus:ring-primary/20"
                />
              </div>

              <div className="flex justify-end gap-4 mt-8 pt-6 border-t border-line/50">
                <button
                  type="button"
                  onClick={() => setShowModal(false)}
                  className="px-6 py-2.5 text-content-secondary hover:text-content-primary hover:bg-surface/50 rounded-lg font-semibold transition-all text-base"
                >
                  {t("guild.cancel")}
                </button>
                <button
                  type="submit"
                  disabled={creating}
                  className="rounded-lg bg-gradient-to-r from-primary to-primary-hover px-6 py-2.5 text-base font-semibold text-content-inverse shadow-sm transition-all hover:shadow-primary/30 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {creating ? (
                    <span className="flex items-center gap-2">
                      <Loader2 className="w-4 h-4 animate-spin" />{" "}
                      {t("guild.loading")}
                    </span>
                  ) : (
                    t("guild.create")
                  )}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
