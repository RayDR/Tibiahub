import { useEffect, useState, useRef, useCallback } from "react";
import { guildApi, Announcement } from "../../services/guild";
import { useAuth } from "../../context/AuthContext";
import { useToast } from "../../context/ToastContext";
import { useTranslation } from "react-i18next";

import {
  AlertCircle,
  Plus,
  Megaphone,
  Loader2,
  Filter,
  X,
  CalendarClock,
  Trash2,
  User,
} from "lucide-react";
import { useGuildContext } from "../../utils/guildContext";
import { useGuildCapability } from "../../hooks/useGuildCapability";
import { useConfirmation } from "../../context/ConfirmationContext";
import {
  Alert,
  DegradedState,
  Dialog,
  DialogBody,
  DialogFooter,
  DialogHeader,
  ErrorState,
  FormField,
  Input,
  Select,
  Textarea,
} from "../../components/ui";
import { WorkspaceContentHeader } from "../../components/workspace/WorkspacePrimitives";
import {
  type AnnouncementPageState,
  emptyAnnouncementPage,
  loadAnnouncementWindow,
} from "./announcementPagination";
import { formatDate, formatDateTime } from "../../utils/locale";

const LIMIT = 10;

export default function Announcements() {
  const { user } = useAuth();
  const { t, i18n } = useTranslation();
  const toast = useToast();
  const confirmation = useConfirmation();
  const guildName = useGuildContext(user);
  const { canManageGuild } = useGuildCapability("announcements.manage");

  const [page, setPage] = useState(() =>
    emptyAnnouncementPage<Announcement>(),
  );
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [showModal, setShowModal] = useState(false);
  const [createError, setCreateError] = useState(false);
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
  const pageRef = useRef(page);
  const requestSequence = useRef(0);
  const requestInFlight = useRef(false);

  const commitPage = useCallback(
    (nextPage: AnnouncementPageState<Announcement>) => {
      pageRef.current = nextPage;
      setPage(nextPage);
    },
    [],
  );

  const loadData = useCallback(
    async (reset = false) => {
      if (!guildName) {
        requestSequence.current += 1;
        requestInFlight.current = false;
        commitPage(emptyAnnouncementPage<Announcement>());
        setLoading(false);
        setLoadingMore(false);
        return;
      }
      if (!reset && requestInFlight.current) return;

      const requestId = ++requestSequence.current;
      requestInFlight.current = true;
      const startingPage = reset
        ? emptyAnnouncementPage<Announcement>()
        : pageRef.current;
      if (reset) {
        commitPage(startingPage);
        setLoading(true);
      } else {
        if (startingPage.additionalError) {
          commitPage({ ...startingPage, additionalError: false });
        }
        setLoadingMore(true);
      }

      const result = await loadAnnouncementWindow({
        state: startingPage,
        reset,
        limit: LIMIT,
        guildName,
        request: guildApi.getAnnouncements,
      });
      if (requestId !== requestSequence.current) return;

      commitPage(result.state);
      if (result.error) {
        console.error("Failed to load announcements", result.error);
      }
      requestInFlight.current = false;
      setLoading(false);
      setLoadingMore(false);
    },
    [commitPage, guildName],
  );

  const loadMore = useCallback(() => {
    if (!loadingMore && page.hasMore && !page.additionalError) {
      void loadData(false);
    }
  }, [loadData, loadingMore, page.additionalError, page.hasMore]);

  // Infinite scroll
  const observer = useRef<IntersectionObserver | null>(null);
  const lastElementRef = useCallback(
    (node: HTMLDivElement | null) => {
      if (loadingMore) return;
      if (observer.current) observer.current.disconnect();
      observer.current = new IntersectionObserver((entries) => {
        if (entries[0].isIntersecting && page.hasMore && !page.additionalError) {
          loadMore();
        }
      });
      if (node) observer.current.observe(node);
    },
    [loadMore, loadingMore, page.additionalError, page.hasMore],
  );

  const canCreate = canManageGuild(guildName);

  useEffect(() => {
    void loadData(true);
    return () => {
      requestSequence.current += 1;
      requestInFlight.current = false;
    };
  }, [filters, guildName, loadData]);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (creating) return;
    setCreating(true);
    setCreateError(false);
    try {
      if (!guildName) throw new Error("Missing guild context");
      await guildApi.createAnnouncement(formData, guildName);
      setShowModal(false);
      setFormData({ title: "", content: "", type: "general" });
      void loadData(true);
      toast.success(t("announcementUI.created"));
    } catch (error) {
      console.error("Failed to create announcement", error);
      setCreateError(true);
      toast.error(t("announcementUI.errors.create"));
    } finally {
      setCreating(false);
    }
  };

  const handleDelete = async (announcement: Announcement) => {
    const confirmed = await confirmation.confirm(
      t("announcementUI.confirmDelete", { title: announcement.title }),
      {
        title: t("common.delete"),
        confirmLabel: t("common.delete"),
        danger: true,
      },
    );
    if (!confirmed) return;

    try {
      await guildApi.deleteAnnouncement(announcement.id);
      setDetailModal(null);
      await loadData(true);
      toast.success(t("announcementUI.deleted"));
    } catch {
      toast.error(t("announcementUI.errors.delete"));
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

  const announcements = page.items;
  const filteredAnnouncements = applyFilters(announcements);

  return (
    <div className="workspace-page">
      <WorkspaceContentHeader
        title={t("guild.announcements")}
        description={guildName}
        icon={<Megaphone />}
        action={
          <>
            <button
              onClick={() => setShowFilters(!showFilters)}
              className="app-button-secondary"
            >
              <Filter className="size-4" />
              <span className="hidden xs:inline">{t("guild.filters")}</span>
            </button>

            {canCreate && (
              <button
                onClick={() => setShowModal(true)}
                className="app-button-primary"
              >
                <Plus className="size-4" />
                <span className="hidden xs:inline">{t("guild.create")}</span>
              </button>
            )}
          </>
        }
      />

      {/* Filters Panel */}
      {showFilters && (
        <div className="rounded-xl bg-surface-raised p-6 shadow-sm">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
            <FormField label={t("guild.type")}>
              <Select
                value={filters.type}
                onChange={(e) =>
                  setFilters({ ...filters, type: e.target.value })
                }
              >
                <option value="">{t("common.filter")}...</option>
                <option value="general">{t("guild.types.general")}</option>
                <option value="hunt">{t("guild.types.hunt")}</option>
                <option value="contest">{t("guild.types.contest")}</option>
              </Select>
            </FormField>

            <FormField label={t("guild.author")}>
              <Input
                type="text"
                value={filters.author}
                onChange={(e) =>
                  setFilters({ ...filters, author: e.target.value })
                }
                placeholder={t("common.search") + "..."}
              />
            </FormField>

            <FormField label={`${t("guild.filterByDate")} (desde)`}>
              <Input
                type="date"
                value={filters.dateFrom}
                onChange={(e) =>
                  setFilters({ ...filters, dateFrom: e.target.value })
                }
              />
            </FormField>

            <FormField label={`${t("guild.filterByDate")} (hasta)`}>
              <Input
                type="date"
                value={filters.dateTo}
                onChange={(e) =>
                  setFilters({ ...filters, dateTo: e.target.value })
                }
              />
            </FormField>
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
      ) : page.initialError ? (
        <ErrorState
          icon={<AlertCircle className="mx-auto h-10 w-10" />}
          title={t("announcementUI.errors.initial")}
          description={t("announcementUI.errors.initialHelp")}
          action={
            <button
              onClick={() => void loadData(true)}
              className="min-h-11 rounded-lg border border-line px-4 font-semibold"
            >
              {t("common.retry")}
            </button>
          }
        />
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
                          {formatDate(ann.created_at, i18n.resolvedLanguage || i18n.language)}
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
                      {t("announcementUI.viewMore")} →
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

          {page.additionalError && (
            <DegradedState
              icon={<AlertCircle className="h-5 w-5" />}
              title={t("announcementUI.errors.more")}
              description={t("announcementUI.errors.moreHelp")}
              action={
                <button
                  onClick={() => void loadData(false)}
                  className="min-h-11 rounded-lg border border-line px-4 font-semibold"
                >
                  {t("announcementUI.retryMore")}
                </button>
              }
            />
          )}

          {!page.hasMore && announcements.length > 0 && (
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
                {t("announcementUI.emptyHelp")}
              </p>
            </div>
          )}
        </div>
      )}

      {/* Detail Modal */}
      {detailModal && (
        <Dialog open onClose={() => setDetailModal(null)} label={detailModal.title} className="ds-dialog-lg">
            <DialogHeader>
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
                <h2 className="text-2xl font-bold text-content-primary leading-tight break-words">
                  {detailModal.title}
                </h2>
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
                      {formatDateTime(detailModal.created_at, i18n.resolvedLanguage || i18n.language)}
                    </span>
                  </div>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setDetailModal(null)}
                className="app-button-ghost app-button-sm flex-shrink-0"
                aria-label={t("guild.cancel")}
              >
                <X className="size-4" />
              </button>
            </DialogHeader>

            <DialogBody>
              <div className="prose prose-invert prose-lg max-w-none text-content-secondary whitespace-pre-line leading-relaxed">
                {detailModal.content}
              </div>
            </DialogBody>
            {canCreate ? (
              <DialogFooter>
                <button
                  type="button"
                  onClick={() => void handleDelete(detailModal)}
                  className="app-button-danger"
                >
                  <Trash2 className="size-4" />
                  {t("common.delete")}
                </button>
              </DialogFooter>
            ) : null}
        </Dialog>
      )}

      {/* Create Modal */}
      <Dialog
        open={showModal}
        onClose={() => { if (!creating) setShowModal(false); }}
        label={`${t("guild.create")} ${t("guild.announcements")}`}
        descriptionId="announcement-create-description"
        className="ds-dialog-lg"
      >
            <form onSubmit={handleCreate} className="flex min-h-0 flex-1 flex-col">
            <DialogHeader>
              <div className="flex items-center gap-3 mb-2">
                <Megaphone className="size-5 text-primary" />
                <h2 className="text-xl font-semibold text-content-primary">
                  {t("guild.create")} {t("guild.announcements")}
                </h2>
              </div>
              <p id="announcement-create-description" className="text-content-secondary text-sm">
                {t("guild.announcements")} ({t("guild.create")})
              </p>
            </DialogHeader>

            <DialogBody className="space-y-5">
              {createError ? <Alert tone="danger">{t("announcementUI.errors.create")}</Alert> : null}
              <FormField label={t("guild.title")} required>
                <Input
                  type="text"
                  required
                  disabled={creating}
                  value={formData.title}
                  onChange={(e) =>
                    setFormData({ ...formData, title: e.target.value })
                  }
                  placeholder={t("announcementUI.titlePlaceholder")}
                />
              </FormField>

              <FormField label={t("guild.type")}>
                <Select
                  value={formData.type}
                  disabled={creating}
                  onChange={(e) =>
                    setFormData({ ...formData, type: e.target.value })
                  }
                >
                  <option value="general">{t("guild.types.general")}</option>
                  <option value="contest">{t("guild.types.contest")}</option>
                  <option value="hunt">{t("guild.types.hunt")}</option>
                </Select>
              </FormField>

              <FormField label={t("guild.content")} required>
                <Textarea
                  required
                  rows={8}
                  disabled={creating}
                  value={formData.content}
                  onChange={(e) =>
                    setFormData({ ...formData, content: e.target.value })
                  }
                  placeholder={t("announcementUI.contentPlaceholder")}
                  className="font-mono"
                />
              </FormField>
            </DialogBody>

              <DialogFooter>
                <button
                  type="button"
                  onClick={() => setShowModal(false)}
                  disabled={creating}
                  className="app-button-secondary"
                >
                  {t("guild.cancel")}
                </button>
                <button
                  type="submit"
                  disabled={creating}
                  className="app-button-primary"
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
              </DialogFooter>
            </form>
      </Dialog>
    </div>
  );
}
