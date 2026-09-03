import React, { useState, useEffect } from "react";
import { useTranslation } from "react-i18next";
import {
  Calendar,
  Trophy,
  Users,
  Ticket,
  Gift,
  Plus,
  Trash2,
  Loader2,
} from "lucide-react";
import { eventsApi, Event, EventCreate } from "../../services/events";
import { guildApi } from "../../services/guild";
import { useAuth } from "../../context/AuthContext";
import { useToast } from "../../context/ToastContext";
import { useConfirmation } from "../../context/ConfirmationContext";
import { useSearchParams } from "react-router-dom";
import { useGuildContext } from "../../utils/guildContext";
import { useGuildCapability } from "../../hooks/useGuildCapability";
import { WorkspaceContentHeader } from "../../components/workspace/WorkspacePrimitives";
import {
  Alert,
  DegradedState,
  Dialog,
  DialogBody,
  DialogFooter,
  DialogHeader,
  EmptyState,
  ErrorState,
  FormField,
  Input,
  LoadingState,
  Select,
  Textarea,
} from "../../components/ui";
import { formatDate, formatDateTime, formatTime } from "../../utils/locale";

export const Events: React.FC = () => {
  const { t, i18n } = useTranslation();
  const { user } = useAuth();
  const toast = useToast();
  const confirmation = useConfirmation();
  const [searchParams, setSearchParams] = useSearchParams();
  const [events, setEvents] = useState<Event[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(false);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showDetailModal, setShowDetailModal] = useState(false);
  const [selectedEvent, setSelectedEvent] = useState<Event | null>(null);
  const initialFilter =
    (searchParams.get("type") as
      "raffle" | "contest" | "hunt" | "quest" | null) || "all";
  const [filter, setFilter] = useState<
    "all" | "raffle" | "contest" | "hunt" | "quest"
  >(initialFilter);
  const [isDrawing, setIsDrawing] = useState(false);
  const [winnerNumber, setWinnerNumber] = useState<number | null>(null);
  const [winnerName, setWinnerName] = useState<string | null>(null);
  const [featureFlags, setFeatureFlags] = useState({
    guild_raffles_enabled: true,
    guild_contests_enabled: true,
  });
  const scopedGuild = useGuildContext(user);
  const { canManageGuild } = useGuildCapability("events.manage");
  const canManageEvents = canManageGuild(scopedGuild);

  useEffect(() => {
    const queryType =
      (searchParams.get("type") as
        "raffle" | "contest" | "hunt" | "quest" | null) || "all";
    if (queryType !== filter) {
      setFilter(queryType);
    }
  }, [searchParams]);

  useEffect(() => {
    loadEvents();
  }, [filter, scopedGuild]);

  useEffect(() => {
    const loadFlags = async () => {
      try {
        const flags = await guildApi.getFeatureFlags();
        setFeatureFlags(flags);
      } catch {
        setFeatureFlags({
          guild_raffles_enabled: true,
          guild_contests_enabled: true,
        });
      }
    };
    void loadFlags();
  }, []);

  useEffect(() => {
    if (!featureFlags.guild_contests_enabled && filter === "contest") {
      setFilter("all");
    }
    if (!featureFlags.guild_raffles_enabled && filter === "raffle") {
      setFilter("all");
    }
  }, [featureFlags, filter]);

  const loadEvents = async () => {
    try {
      setLoading(true);
      setLoadError(false);
      const data = await eventsApi.getEvents(
        "active",
        filter === "all" ? undefined : filter,
        scopedGuild,
      );
      setEvents(data);
    } catch (error) {
      console.error("Failed to load events:", error);
      setLoadError(true);
    } finally {
      setLoading(false);
    }
  };

  const handleCreateEvent = async (event: EventCreate): Promise<boolean> => {
    try {
      if (!scopedGuild) {
        toast.error(t("eventsUI.messages.selectGuild"));
        return false;
      }
      const payload: EventCreate = {
        ...event,
        guild_name: scopedGuild,
      };
      await eventsApi.createEvent(payload);
      await loadEvents();
      toast.success(t("eventsUI.messages.created"));
      return true;
    } catch (error) {
      console.error("Failed to create event:", error);
      toast.error(t("eventsUI.messages.createError"));
      return false;
    }
  };

  const handleJoinEvent = async (eventId: number) => {
    try {
      await eventsApi.joinEvent(eventId);
      loadEvents();
      if (selectedEvent && selectedEvent.id === eventId) {
        const updated = await eventsApi.getEvent(eventId);
        setSelectedEvent(updated);
      }
      toast.success(t("eventsUI.messages.joined"));
    } catch (error: any) {
      toast.error(t("eventsUI.messages.joinError"));
    }
  };

  const handleDrawWinner = async (eventId: number) => {
    try {
      setIsDrawing(true);
      setWinnerNumber(null);
      setWinnerName(null);

      // Simulate dice animation
      const animationDuration = 3000;
      const intervalTime = 100;
      const intervals = animationDuration / intervalTime;
      let count = 0;

      const event = events.find((e) => e.id === eventId);
      if (!event) return;

      const interval = setInterval(() => {
        const randomNum =
          Math.floor(Math.random() * (event.total_slots || 100)) + 1;
        setWinnerNumber(randomNum);
        count++;

        if (count >= intervals) {
          clearInterval(interval);
        }
      }, intervalTime);

      // Draw the actual winner
      setTimeout(async () => {
        try {
          const result = await eventsApi.drawWinner(eventId);
          setWinnerNumber(result.winner_number || null);
          setWinnerName(result.winner_name);
          loadEvents();
          if (selectedEvent && selectedEvent.id === eventId) {
            const updated = await eventsApi.getEvent(eventId);
            setSelectedEvent(updated);
          }
        } catch (error: any) {
          toast.error(t("eventsUI.messages.drawError"));
        } finally {
          setIsDrawing(false);
        }
      }, animationDuration);
    } catch (error) {
      setIsDrawing(false);
      console.error("Failed to draw winner:", error);
    }
  };

  const handleDeleteEvent = async (eventId: number) => {
    const confirmed = await confirmation.confirm(
      t("eventsUI.confirm.delete"),
      { title: t("eventsUI.actions.delete"), confirmLabel: t("eventsUI.actions.delete"), danger: true },
    );
    if (!confirmed) return;

    try {
      await eventsApi.deleteEvent(eventId);
      loadEvents();
      setShowDetailModal(false);
      setSelectedEvent(null);
      toast.success(t("eventsUI.messages.deleted"));
    } catch (error) {
      console.error("Failed to delete event:", error);
      toast.error(t("eventsUI.messages.deleteError"));
    }
  };

  const openEventDetail = async (event: Event) => {
    try {
      const detailed = await eventsApi.getEvent(event.id);
      setSelectedEvent(detailed);
      setShowDetailModal(true);
    } catch (error) {
      console.error("Failed to load event details:", error);
    }
  };

  const hasUserJoined = (event: Event) => {
    return event.participants.some((p) => p.user_id === user?.id);
  };

  const getTypeMeta = (type: string) => {
    switch (type) {
      case "raffle":
        return {
          label: t("eventsUI.types.raffle"),
          badge: "bg-primary/15 text-primary border-primary/50",
        };
      case "contest":
        return {
          label: t("eventsUI.types.contest"),
          badge: "bg-danger/15 text-danger border-danger/50",
        };
      case "hunt":
      case "hunt_event":
        return {
          label: t("eventsUI.types.hunt"),
          badge: "bg-success/15 text-success border-success/50",
        };
      case "quest":
        return {
          label: t("eventsUI.types.quest"),
          badge: "bg-accent/15 text-accent border-accent/50",
        };
      default:
        return {
          label: t("eventsUI.types.custom"),
          badge: "bg-surface text-content-secondary border-line",
        };
    }
  };

  return (
    <div className="workspace-page">
      <WorkspaceContentHeader
        title={filter === "contest" ? t("eventsUI.contestsTitle") : t("eventsUI.title")}
        description={scopedGuild}
        icon={<Trophy />}
        action={canManageEvents ? (
          <button
            onClick={() => setShowCreateModal(true)}
            className="app-button-primary"
          >
            <Plus className="size-4" />
            <span className="hidden xs:inline">{t("eventsUI.actions.create")}</span>
            <span className="xs:hidden">{t("guild.create")}</span>
          </button>
        ) : undefined}
      />

      <div className="flex flex-wrap gap-2 sm:gap-3">
        {[
          { key: "all", label: t("eventsUI.filters.all"), icon: null },
          ...(featureFlags.guild_raffles_enabled
            ? [{ key: "raffle", label: t("eventsUI.filters.raffles"), icon: <Ticket size={16} /> }]
            : []),
          ...(featureFlags.guild_contests_enabled
            ? [
                {
                  key: "contest",
                  label: t("eventsUI.filters.contests"),
                  icon: <Trophy size={16} />,
                },
              ]
            : []),
          { key: "hunt", label: t("eventsUI.filters.hunts"), icon: <Users size={16} /> },
          { key: "quest", label: t("eventsUI.filters.quests"), icon: <Calendar size={16} /> },
        ].map(({ key, label, icon }) => (
          <button
            key={key}
            className={`flex items-center gap-2 px-4 py-2 rounded-md transition-colors font-medium ${
              filter === key
                ? "bg-primary text-content-on-primary"
                : "bg-surface/50 text-content-secondary hover:bg-surface-raised/50 border border-line"
            }`}
            onClick={() => {
              setFilter(key as any);
              if (key === "all") {
                const nextParams = new URLSearchParams(searchParams);
                nextParams.delete("type");
                setSearchParams(nextParams, { replace: true });
              } else {
                setSearchParams({ type: key }, { replace: true });
              }
            }}
          >
            {icon}
            {label}
          </button>
        ))}
      </div>

      {loading && events.length === 0 ? (
        <LoadingState title={t("eventsUI.states.loading")} />
      ) : loadError && events.length === 0 ? (
        <ErrorState
          title={t("eventsUI.states.error")}
          description={t("eventsUI.states.errorHelp")}
          action={<button type="button" onClick={() => void loadEvents()} className="app-button-secondary">{t("common.retry")}</button>}
        />
      ) : events.length === 0 ? (
        <EmptyState icon={<Trophy />} title={t("eventsUI.states.empty")} description={t("eventsUI.states.emptyHelp")} />
      ) : (
        <>
          {loadError ? <DegradedState title={t("eventsUI.states.degraded")} description={t("eventsUI.states.degradedHelp")} action={<button type="button" onClick={() => void loadEvents()} className="app-button-secondary app-button-sm">{t("common.retry")}</button>} /> : null}
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4 sm:gap-6">
          {events.map((event) => (
            <div
              key={event.id}
              className={`bg-surface-base/80 border rounded-lg p-4 sm:p-6 hover:border-primary/50 transition-all ${
                getTypeMeta(event.type).badge?.includes("amber")
                  ? "border-primary/50"
                  : getTypeMeta(event.type).badge?.includes("red")
                    ? "border-danger/50"
                    : getTypeMeta(event.type).badge?.includes("green")
                      ? "border-success/50"
                      : getTypeMeta(event.type).badge?.includes("indigo")
                        ? "border-accent/50"
                        : "border-line"
              }`}
            >
              <div className="flex justify-between items-start mb-3 sm:mb-4">
                <h3 className="text-lg sm:text-xl font-bold text-content-primary">
                  {event.title}
                </h3>
                {(() => {
                  const meta = getTypeMeta(event.type);
                  return (
                    <span
                      className={`flex items-center gap-1 px-2 py-1 rounded text-xs font-bold uppercase border ${meta.badge}`}
                    >
                      {event.type === "raffle" ? (
                        <Ticket size={12} />
                      ) : (
                        <Trophy size={12} />
                      )}
                      {meta.label}
                    </span>
                  );
                })()}
              </div>

              {event.description && (
                <p className="text-content-secondary text-sm mb-4 leading-relaxed">
                  {event.description}
                </p>
              )}

              {event.reward && (
                <div className="flex items-center gap-2 p-3 bg-primary/20 border border-primary/30 rounded-md mb-4">
                  <Gift size={16} className="text-primary" />
                  <span className="text-primary font-medium text-sm">
                    {event.reward}
                  </span>
                </div>
              )}

              <div className="flex gap-4 mb-4 text-sm">
                <div className="flex items-center gap-2 text-content-secondary">
                  <Users size={16} />
                  <span>
                    {event.participant_count} / {event.total_slots || "∞"}
                  </span>
                </div>
                {event.draw_date && (
                  <div className="flex items-center gap-2 text-content-secondary">
                    <Calendar size={16} />
                    <span>
                      {formatDate(event.draw_date, i18n.resolvedLanguage || i18n.language)}
                    </span>
                  </div>
                )}
              </div>

              {event.is_drawn && event.winner_name && (
                <div className="flex items-center gap-2 p-3 bg-success/20 border border-success/30 rounded-md mb-4">
                  <Trophy size={16} className="text-success" />
                  <span className="text-success font-medium text-sm">
                    {t("eventsUI.winner", { name: event.winner_name })}
                    {event.winner_number && (
                      <span className="ml-2 text-success">
                        #{event.winner_number}
                      </span>
                    )}
                  </span>
                </div>
              )}

              <div className="flex gap-3">
                <button
                  className="flex-1 px-4 py-2 bg-surface hover:bg-surface-raised text-content-primary rounded-md transition-colors font-medium text-sm"
                  onClick={() => openEventDetail(event)}
                >
                  {t("eventsUI.actions.details")}
                </button>
                {!event.is_drawn && !hasUserJoined(event) && (
                  <button
                    className="flex-1 px-4 py-2 bg-success hover:bg-success-hover text-content-on-primary rounded-md transition-colors font-medium text-sm disabled:opacity-50 disabled:cursor-not-allowed"
                    onClick={() => handleJoinEvent(event.id)}
                    disabled={
                      event.participant_count >= (event.total_slots || Infinity)
                    }
                  >
                    {t("eventsUI.actions.join")}
                  </button>
                )}
                {hasUserJoined(event) && !event.is_drawn && (
                  <span className="flex-1 px-4 py-2 bg-success/15 text-success rounded-md text-center font-medium text-sm border border-success/50">
                    {t("eventsUI.actions.joined")} ✓
                  </span>
                )}
              </div>
            </div>
          ))}
          </div>
        </>
      )}

      {showCreateModal && (
        <CreateEventModal
          contestsEnabled={featureFlags.guild_contests_enabled}
          rafflesEnabled={featureFlags.guild_raffles_enabled}
          defaultType={
            filter === "contest"
              ? "contest"
              : filter === "raffle"
                ? "raffle"
                : "raffle"
          }
          onClose={() => setShowCreateModal(false)}
          onCreate={handleCreateEvent}
        />
      )}

      {showDetailModal && selectedEvent && (
        <EventDetailModal
          event={selectedEvent}
          onClose={() => {
            setShowDetailModal(false);
            setSelectedEvent(null);
            setWinnerNumber(null);
            setWinnerName(null);
          }}
          onDelete={handleDeleteEvent}
          onDrawWinner={handleDrawWinner}
          isDrawing={isDrawing}
          winnerNumber={winnerNumber}
          winnerName={winnerName}
          hasUserJoined={hasUserJoined(selectedEvent)}
          canManage={canManageEvents}
        />
      )}
    </div>
  );
};

interface CreateEventModalProps {
  contestsEnabled: boolean;
  rafflesEnabled: boolean;
  defaultType: "raffle" | "contest";
  onClose: () => void;
  onCreate: (event: EventCreate) => Promise<boolean>;
}

const CreateEventModal: React.FC<CreateEventModalProps> = ({
  contestsEnabled,
  rafflesEnabled,
  defaultType,
  onClose,
  onCreate,
}) => {
  const { t } = useTranslation();
  const [formData, setFormData] = useState<EventCreate>({
    type: defaultType,
    title: "",
    description: "",
    rules: "",
    reward: "",
    total_slots: 100,
    entry_cost: "",
    status: "active",
    start_date: new Date().toISOString(),
    end_date: "",
    draw_date: "",
    is_public: false,
    participant_mode: "manual",
    active_days_limit: 10,
    guild_name: "",
    guild_world: "",
  });
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (submitting) return;
    setSubmitting(true);
    setSubmitError(false);
    const created = await onCreate({
      ...formData,
      start_date: formData.start_date,
      end_date: formData.end_date || undefined,
      draw_date: formData.draw_date || undefined,
    });
    setSubmitting(false);
    if (created) onClose();
    else setSubmitError(true);
  };

  const toLocalInput = (value?: string) => {
    if (!value) return "";
    return new Date(value).toISOString().slice(0, 16);
  };

  return (
    <Dialog
      open
      onClose={() => { if (!submitting) onClose(); }}
      label={t("eventsUI.create.title")}
      className="ds-dialog-lg"
    >
      <form onSubmit={handleSubmit} className="contents">
        <DialogHeader>
          <h2 className="text-2xl font-bold text-content-primary">
            {t("eventsUI.create.title")}
          </h2>
        </DialogHeader>

        <DialogBody className="space-y-5">
          {submitError ? (
            <Alert tone="danger">
              {t("eventsUI.create.error")}
            </Alert>
          ) : null}

          <FormField label={t("eventsUI.fields.type")} required>
            <Select
              value={formData.type}
              onChange={(e) =>
                setFormData({ ...formData, type: e.target.value as any })
              }
              required
              disabled={submitting}
            >
              {rafflesEnabled && <option value="raffle">{t("eventsUI.types.raffle")}</option>}
              {contestsEnabled && <option value="contest">{t("eventsUI.types.contest")}</option>}
              <option value="hunt">{t("eventsUI.types.hunt")}</option>
              <option value="quest">{t("eventsUI.types.quest")}</option>
              <option value="custom">{t("eventsUI.types.custom")}</option>
            </Select>
          </FormField>

          <FormField label={t("eventsUI.fields.title")} required>
            <Input
              type="text"
              value={formData.title}
              onChange={(e) =>
                setFormData({ ...formData, title: e.target.value })
              }
              required
              disabled={submitting}
              placeholder={t("eventsUI.placeholders.title")}
            />
          </FormField>

          <FormField label={t("eventsUI.fields.description")}>
            <Textarea
              value={formData.description}
              onChange={(e) =>
                setFormData({ ...formData, description: e.target.value })
              }
              rows={3}
              disabled={submitting}
              className="resize-none"
              placeholder={t("eventsUI.placeholders.description")}
            />
          </FormField>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <FormField label={t("eventsUI.fields.startDate")} required>
              <Input
                type="datetime-local"
                required
                value={toLocalInput(formData.start_date)}
                onChange={(e) =>
                  setFormData({
                    ...formData,
                    start_date: new Date(e.target.value).toISOString(),
                  })
                }
                disabled={submitting}
              />
            </FormField>
            <FormField label={t("eventsUI.fields.endDate")}>
              <Input
                type="datetime-local"
                value={toLocalInput(formData.end_date)}
                onChange={(e) =>
                  setFormData({
                    ...formData,
                    end_date: e.target.value
                      ? new Date(e.target.value).toISOString()
                      : "",
                  })
                }
                disabled={submitting}
              />
            </FormField>
            <FormField label={t("eventsUI.fields.drawDate")}>
              <Input
                type="datetime-local"
                value={toLocalInput(formData.draw_date)}
                onChange={(e) =>
                  setFormData({
                    ...formData,
                    draw_date: e.target.value
                      ? new Date(e.target.value).toISOString()
                      : "",
                  })
                }
                disabled={submitting}
              />
            </FormField>
          </div>

          <FormField label={t("eventsUI.fields.rules")}>
            <Textarea
              value={formData.rules}
              onChange={(e) =>
                setFormData({ ...formData, rules: e.target.value })
              }
              rows={4}
              disabled={submitting}
              className="resize-none font-mono text-sm"
              placeholder={t("eventsUI.placeholders.rules")}
            />
          </FormField>

          <FormField label={t("eventsUI.fields.reward")}>
            <Input
              type="text"
              value={formData.reward}
              onChange={(e) =>
                setFormData({ ...formData, reward: e.target.value })
              }
              disabled={submitting}
              placeholder={t("eventsUI.placeholders.reward")}
            />
          </FormField>

          {formData.type === "raffle" && (
            <div className="grid grid-cols-2 gap-4">
              <FormField label={t("eventsUI.fields.totalSlots")}>
                <Input
                  type="number"
                  value={formData.total_slots}
                  onChange={(e) =>
                    setFormData({
                      ...formData,
                      total_slots: parseInt(e.target.value),
                    })
                  }
                  min="1"
                  disabled={submitting}
                />
              </FormField>

              <FormField label={t("eventsUI.fields.entryCost")}>
                <Input
                  type="text"
                  value={formData.entry_cost}
                  onChange={(e) =>
                    setFormData({ ...formData, entry_cost: e.target.value })
                  }
                  placeholder={t("eventsUI.placeholders.entryCost")}
                  disabled={submitting}
                />
              </FormField>
            </div>
          )}

          <FormField label={t("eventsUI.fields.drawDateOptional")}>
            <Input
              type="datetime-local"
              value={formData.draw_date}
              onChange={(e) =>
                setFormData({ ...formData, draw_date: e.target.value })
              }
              disabled={submitting}
            />
          </FormField>

          <div className="flex items-center gap-3 bg-surface-base/50 p-3 rounded-md border border-line">
            <input
              type="checkbox"
              id="is_public"
              checked={formData.is_public || false}
              onChange={(e) =>
                setFormData({ ...formData, is_public: e.target.checked })
              }
              className="w-5 h-5 rounded border-line bg-surface-base text-primary"
              disabled={submitting}
            />
            <label htmlFor="is_public" className="cursor-pointer">
              <span className="block text-sm font-medium text-content-primary">
                {t("eventsUI.fields.publicEvent")}
              </span>
              <span className="block text-xs text-content-secondary">
                {t("eventsUI.fields.publicEventHelp")}
              </span>
            </label>
          </div>

          {formData.is_public && (
            <div className="space-y-4 bg-surface-base/50 p-4 rounded-md border border-line">
              <h3 className="text-sm font-semibold text-primary">
                {t("eventsUI.create.publicConfiguration")}
              </h3>

              <FormField label={t("eventsUI.fields.participantMode")}>
                <Select
                  value={formData.participant_mode}
                  onChange={(e) =>
                    setFormData({
                      ...formData,
                      participant_mode: e.target.value,
                    })
                  }
                  disabled={submitting}
                >
                  <option value="manual">
                    {t("eventsUI.modes.manual")}
                  </option>
                  <option value="guild_auto">
                    {t("eventsUI.modes.guildAuto")}
                  </option>
                </Select>
              </FormField>

              {formData.participant_mode === "guild_auto" && (
                <>
                  <FormField label={t("eventsUI.fields.guildName")}>
                    <Input
                      type="text"
                      value={formData.guild_name}
                      onChange={(e) =>
                        setFormData({ ...formData, guild_name: e.target.value })
                      }
                      placeholder={t("eventsUI.fields.guildName")}
                      disabled={submitting}
                    />
                  </FormField>

                  <FormField
                    label={t("eventsUI.fields.activeDays")}
                    helpText={t("eventsUI.fields.activeDaysHelp")}
                  >
                    <Input
                      type="number"
                      value={formData.active_days_limit}
                      onChange={(e) =>
                        setFormData({
                          ...formData,
                          active_days_limit: parseInt(e.target.value) || 10,
                        })
                      }
                      min="1"
                      max="365"
                      disabled={submitting}
                    />
                  </FormField>

                  <FormField
                    label={t("eventsUI.fields.guildWorld")}
                    helpText={t("eventsUI.fields.guildWorldHelp")}
                  >
                    <Input
                      type="text"
                      value={formData.guild_world}
                      onChange={(e) =>
                        setFormData({
                          ...formData,
                          guild_world: e.target.value,
                        })
                      }
                      placeholder={t("eventsUI.fields.guildWorld")}
                      disabled={submitting}
                    />
                  </FormField>
                </>
              )}
            </div>
          )}
        </DialogBody>

        <DialogFooter>
            <button
              type="button"
              onClick={onClose}
              className="app-button-secondary"
              disabled={submitting}
            >
              {t("common.cancel")}
            </button>
            <button
              type="submit"
              className="app-button-primary"
              disabled={submitting}
            >
              {submitting ? t("eventsUI.actions.creating") : t("eventsUI.actions.create")}
            </button>
        </DialogFooter>
      </form>
    </Dialog>
  );
};

interface EventDetailModalProps {
  event: Event;
  onClose: () => void;
  onDelete: (id: number) => void;
  onDrawWinner: (id: number) => void;
  isDrawing: boolean;
  winnerNumber: number | null;
  winnerName: string | null;
  hasUserJoined: boolean;
  canManage: boolean;
}

const EventDetailModal: React.FC<EventDetailModalProps> = ({
  event,
  onClose,
  onDelete,
  onDrawWinner,
  isDrawing,
  winnerNumber,
  winnerName,
  canManage,
}) => {
  const { t, i18n } = useTranslation();
  const toast = useToast();
  const confirmation = useConfirmation();
  const [isPublicEdit, setIsPublicEdit] = useState(event.is_public);
  const [syncLoading, setSyncLoading] = useState(false);
  const [syncLog, setSyncLog] = useState<string[]>([]);
  const [showLog, setShowLog] = useState(false);
  const [manualCharName, setManualCharName] = useState("");
  const [addingManual, setAddingManual] = useState(false);
  const canManageEvent = canManage;
  const publicUrl =
    event.type === "contest" && event.public_code
      ? `https://tibiahub.domoforge.com/contests/${event.public_code}`
      : `https://tibiahub.domoforge.com/public/event/${event.uuid}`;

  const addLog = (message: string) => {
    setSyncLog((prev) => [
      ...prev,
      `[${formatTime(new Date(), i18n.resolvedLanguage || i18n.language)}] ${message}`,
    ]);
  };

  const handleTogglePublic = async () => {
    try {
      addLog(
        t("eventsUI.logs.visibilityChanging", { visibility: t(!isPublicEdit ? "eventsUI.visibility.public" : "eventsUI.visibility.private") }),
      );
      await eventsApi.updateEvent(event.id, { is_public: !isPublicEdit });
      setIsPublicEdit(!isPublicEdit);
      addLog(t("eventsUI.logs.visibilityChanged", { visibility: t(!isPublicEdit ? "eventsUI.visibility.public" : "eventsUI.visibility.private") }));
      toast.success?.(t("eventsUI.messages.visibilityChanged", { visibility: t(!isPublicEdit ? "eventsUI.visibility.public" : "eventsUI.visibility.private") }));
    } catch (err: any) {
      const errorMsg = err.message || err.toString();
      addLog(`❌ Error: ${errorMsg}`);
      toast.error?.(t("eventsUI.messages.visibilityError"));
      console.error("Toggle public error:", err);
    }
  };

  const handleSyncParticipants = async () => {
    if (!canManageEvent) return;
    setSyncLoading(true);
    addLog(t("eventsUI.logs.refreshing"));

    try {
      addLog(t("eventsUI.logs.loadingRoster"));
      addLog(t("eventsUI.logs.guild", { guild: event.guild_name || t("eventsUI.values.notConfigured") }));

      const result = await eventsApi.loadGuildParticipants(event.id, true);

      addLog(t("eventsUI.logs.updateCompleted"));
      addLog(t("eventsUI.logs.loaded", { count: result.loaded }));
      addLog(t("eventsUI.logs.updated", { count: result.updated }));
      addLog(t("eventsUI.logs.total", { count: result.total }));

      toast.success?.(
        t("eventsUI.messages.participantsUpdated", { count: result.total }),
      );

      // Refresh event data without full reload
      setTimeout(() => {
        window.location.reload();
      }, 1500);
    } catch (err: any) {
      const errorMsg = err.message || err.toString();
      addLog(`❌ Error: ${errorMsg}`);
      toast.error?.(t("eventsUI.messages.participantsError"));
      console.error("Sync error:", err);
    } finally {
      setSyncLoading(false);
    }
  };

  const handleAddManualParticipant = async () => {
    if (!manualCharName.trim() || !canManageEvent) return;
    setAddingManual(true);
    addLog(t("eventsUI.logs.adding", { name: manualCharName }));

    try {
      addLog(t("eventsUI.logs.validating"));
      const result = await eventsApi.addManualParticipant(event.id, {
        character_name: manualCharName,
      });

      addLog(t("eventsUI.logs.added"));
      addLog(t("eventsUI.logs.character", { name: result.character_name }));
      addLog(t("eventsUI.logs.level", { level: result.character_level }));
      addLog(t("eventsUI.logs.vocation", { vocation: result.character_vocation }));
      addLog(t("eventsUI.logs.number", { number: result.assigned_number }));

      toast.success?.(t("eventsUI.messages.participantAdded", { name: result.character_name }));
      setManualCharName("");

      // Refresh event data without immediate reload
      setTimeout(() => {
        window.location.reload();
      }, 1500);
    } catch (err: any) {
      const errorMsg = err.message || err.toString();
      addLog(`❌ Error: ${errorMsg}`);
      toast.error?.(t("eventsUI.messages.addError"));
      console.error("Add participant error:", err);
    } finally {
      setAddingManual(false);
    }
  };

  const handleExcludeParticipant = async (
    participantId: number,
    participantName: string,
  ) => {
    if (!canManageEvent) return;

    if (
      !(await confirmation.confirm(
        t("eventsUI.confirm.exclude", { name: participantName }),
        { danger: true },
      ))
    ) {
      return;
    }

    addLog(t("eventsUI.logs.excluding", { name: participantName }));

    try {
      await eventsApi.excludeParticipant(event.id, participantId);
      addLog(t("eventsUI.logs.excluded", { name: participantName }));
      toast.success?.(t("eventsUI.messages.excluded", { name: participantName }));

      setTimeout(() => {
        window.location.reload();
      }, 1000);
    } catch (err: any) {
      const errorMsg = err.message || err.toString();
      addLog(`❌ Error: ${errorMsg}`);
      toast.error?.(t("eventsUI.messages.excludeError"));
      console.error("Exclude error:", err);
    }
  };

  const handleDeleteParticipant = async (
    participantId: number,
    participantName: string,
  ) => {
    if (!canManageEvent) return;

    if (
      !(await confirmation.confirm(
        t("eventsUI.confirm.remove", { name: participantName }),
        { danger: true },
      ))
    ) {
      return;
    }

    addLog(t("eventsUI.logs.removing", { name: participantName }));

    try {
      await eventsApi.deleteParticipant(event.id, participantId);
      addLog(t("eventsUI.logs.removed", { name: participantName }));
      toast.success?.(t("eventsUI.messages.removed", { name: participantName }));

      setTimeout(() => {
        window.location.reload();
      }, 1000);
    } catch (err: any) {
      const errorMsg = err.message || err.toString();
      addLog(`❌ Error: ${errorMsg}`);
      toast.error?.(t("eventsUI.messages.removeError"));
      console.error("Delete error:", err);
    }
  };

  return (
    <Dialog open onClose={onClose} label={event.title} className="ds-dialog-lg">
        <DialogHeader className="flex justify-between items-start">
          <h2 className="text-2xl font-bold text-content-primary">
            {event.title}
          </h2>
          {canManageEvent && (
            <button
              onClick={() => onDelete(event.id)}
              className="p-2 bg-danger/15 hover:bg-danger/20 text-danger border border-danger/50 rounded-md transition-colors"
              aria-label={t("eventsUI.actions.delete")}
            >
              <Trash2 size={18} />
            </button>
          )}
        </DialogHeader>

        <DialogBody className="space-y-6">
          {event.description && (
            <div>
              <h3 className="text-lg font-semibold text-content-primary mb-2">
                {t("eventsUI.fields.description")}
              </h3>
              <p className="text-content-secondary leading-relaxed">
                {event.description}
              </p>
            </div>
          )}

          {event.rules && (
            <div className="bg-surface-base/50 border border-line rounded-lg p-4">
              <h3 className="text-lg font-semibold text-primary mb-3 flex items-center gap-2">
                <Trophy size={18} />
                {t("eventsUI.fields.rules")}
              </h3>
              <p className="text-content-secondary whitespace-pre-line leading-relaxed font-mono text-sm">
                {event.rules}
              </p>
            </div>
          )}

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <div className="text-sm text-content-secondary">{t("eventsUI.fields.starts")}</div>
              <div className="text-content-primary font-medium">
                {event.start_date
                  ? formatDateTime(event.start_date, i18n.resolvedLanguage || i18n.language)
                  : t("eventsUI.values.tbd")}
              </div>
            </div>
            {event.end_date && (
              <div>
                <div className="text-sm text-content-secondary">{t("eventsUI.fields.ends")}</div>
                <div className="text-content-primary font-medium">
                  {formatDateTime(event.end_date, i18n.resolvedLanguage || i18n.language)}
                </div>
              </div>
            )}
            {event.draw_date && (
              <div>
                <div className="text-sm text-content-secondary">{t("eventsUI.fields.draw")}</div>
                <div className="text-content-primary font-medium">
                  {formatDateTime(event.draw_date, i18n.resolvedLanguage || i18n.language)}
                </div>
              </div>
            )}
          </div>

          {event.reward && (
            <div className="bg-primary/20 border border-primary/30 rounded-lg p-4">
              <h3 className="text-lg font-semibold text-primary mb-3">
                {t("eventsUI.fields.reward")}
              </h3>
              <div className="flex items-center gap-3">
                <Gift size={24} className="text-primary" />
                <span className="text-primary font-medium text-lg">
                  {event.reward}
                </span>
              </div>
            </div>
          )}

          {/* Admin Controls */}
          {canManageEvent && (
            <div className="bg-gradient-to-br from-accent/20 to-surface-base border border-accent/50 rounded-lg p-6 space-y-4">
              <h3 className="text-lg font-semibold text-accent mb-3 flex items-center gap-2">
                <Users size={18} />
                {t("eventsUI.admin.title")}
              </h3>

              {/* Info Box for Public Events */}
              {isPublicEdit && (
                <div className="p-3 bg-info/20 border border-info/30 rounded-md text-sm text-info">
                  {t("eventsUI.admin.publicHelp")}
                </div>
              )}

              {/* Public/Private Toggle */}
              <div className="flex items-center justify-between p-3 bg-surface-base/50 rounded-md">
                <div>
                  <div className="font-medium text-content-primary">
                    {t("eventsUI.admin.visibility")}
                  </div>
                  <div className="text-xs text-content-secondary">
                    {isPublicEdit
                      ? t("eventsUI.visibility.publicHelp")
                      : t("eventsUI.visibility.privateHelp")}
                  </div>
                </div>
                <button
                  onClick={handleTogglePublic}
                  className={`px-4 py-2 rounded-md font-medium transition-colors ${
                    isPublicEdit
                      ? "bg-success hover:bg-success-hover text-content-on-primary"
                      : "bg-surface-raised hover:bg-surface-hover text-content-secondary"
                  }`}
                >
                  {t(isPublicEdit ? "eventsUI.visibility.public" : "eventsUI.visibility.private")}
                </button>
              </div>

              {/* Guild Participants */}
              {event.is_public && (
                <div className="space-y-3">
                  <div className="p-3 bg-surface-base/50 rounded-md">
                    <div className="text-sm text-content-secondary mb-2">
                      {t("eventsUI.admin.mode")}: {" "}
                      <span className="text-primary font-mono">
                        {event.participant_mode || "manual"}
                      </span>
                      {event.guild_name && (
                        <>
                          {" "}
                          | {t("eventsUI.admin.guild")}: {" "}
                          <span className="text-primary">
                            {event.guild_name}
                          </span>
                        </>
                      )}
                    </div>
                  </div>

                  <div className="grid grid-cols-1 gap-3">
                    <button
                      onClick={handleSyncParticipants}
                      disabled={syncLoading}
                      className="flex items-center justify-center gap-2 px-4 py-3 bg-info hover:bg-info-hover text-content-on-primary rounded-md font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      {syncLoading ? (
                        <>
                          <Loader2 className="animate-spin" size={16} />
                          {t("eventsUI.actions.refreshing")}
                        </>
                      ) : (
                        <>
                          <Users size={16} />
                          {t("eventsUI.actions.refreshParticipants")}
                        </>
                      )}
                    </button>

                    {/* Manual Add */}
                    <div className="flex flex-wrap gap-2">
                      <Input
                        type="text"
                        value={manualCharName}
                        onChange={(e) => setManualCharName(e.target.value)}
                        placeholder={t("eventsUI.placeholders.character")}
                        className="min-w-0 flex-1 text-sm"
                        aria-label={t("eventsUI.fields.character")}
                        disabled={addingManual}
                        onKeyDown={(e) =>
                          e.key === "Enter" && void handleAddManualParticipant()
                        }
                      />
                      <button
                        onClick={handleAddManualParticipant}
                        disabled={addingManual || !manualCharName.trim()}
                        className="px-4 py-2 bg-success hover:bg-success-hover text-content-on-primary rounded-md font-medium text-sm transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                      >
                        {addingManual ? (
                          <Loader2 className="animate-spin" size={16} />
                        ) : (
                          t("eventsUI.actions.add")
                        )}
                      </button>
                    </div>
                  </div>

                  {/* Log Toggle */}
                  <button
                    onClick={() => setShowLog(!showLog)}
                    className="w-full px-4 py-2 bg-surface hover:bg-surface-raised text-content-secondary rounded-md text-sm font-medium transition-colors"
                  >
                    {showLog ? t("eventsUI.actions.hideLogs") : t("eventsUI.actions.showLogs")}
                  </button>

                  {/* Log Display */}
                  {showLog && (
                    <div className="bg-surface-base border border-line rounded-md p-3 max-h-48 overflow-y-auto font-mono text-xs">
                      {syncLog.length === 0 ? (
                        <div className="text-content-muted">
                          {t("eventsUI.admin.noLogs")}
                        </div>
                      ) : (
                        syncLog.map((log, i) => (
                          <div key={i} className="text-content-secondary mb-1">
                            {log}
                          </div>
                        ))
                      )}
                    </div>
                  )}

                  {/* Public URL */}
                  {isPublicEdit && event.uuid && (
                    <div className="p-3 bg-success/20 border border-success/30 rounded-md">
                      <div className="text-xs text-success mb-1">
                        {t("eventsUI.admin.publicUrl")}
                      </div>
                      <div className="flex gap-2">
                        <Input
                          type="text"
                          value={publicUrl}
                          readOnly
                          aria-label={t("eventsUI.admin.publicUrl")}
                          className="min-w-0 flex-1 text-xs font-mono"
                        />
                        <button
                          onClick={() =>
                            navigator.clipboard.writeText(publicUrl)
                          }
                          className="px-3 py-2 bg-success hover:bg-success-hover text-content-on-primary rounded text-xs"
                        >
                          {t("eventsUI.actions.copy")}
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          )}

          {event.type === "raffle" &&
            !event.is_drawn &&
            !event.is_public &&
            canManageEvent && (
              <div className="bg-gradient-to-br from-surface to-surface-base border border-line rounded-lg p-6 text-center">
                <button
                  className="px-6 py-3 bg-primary hover:bg-primary-hover text-content-on-primary rounded-md font-bold text-lg transition-all disabled:opacity-50 disabled:cursor-not-allowed hover:scale-105 active:scale-95"
                  onClick={() => onDrawWinner(event.id)}
                  disabled={isDrawing || event.participants.length === 0}
                >
                  {isDrawing ? t("eventsUI.actions.drawing") : t("eventsUI.actions.draw")}
                </button>

                {isDrawing && winnerNumber && (
                  <div className="mt-6 flex justify-center">
                    <div className="animate-bounce">
                      <div className="flex h-32 w-32 items-center justify-center rounded-2xl bg-gradient-to-br from-primary to-primary-hover shadow-lg">
                        <div className="text-5xl font-bold text-content-primary">
                          {winnerNumber}
                        </div>
                      </div>
                    </div>
                  </div>
                )}

                {!isDrawing && winnerName && (
                  <div className="mt-6 bg-gradient-to-br from-primary/30 to-primary/30 border border-primary/50 rounded-lg p-6 animate-pulse">
                    <Trophy size={40} className="mx-auto text-primary mb-3" />
                    <h3 className="text-2xl font-bold text-primary mb-2">
                      🎉 {t("eventsUI.winner", { name: winnerName })} 🎉
                    </h3>
                    {winnerNumber && (
                      <p className="text-3xl font-bold text-primary">
                        #{winnerNumber}
                      </p>
                    )}
                  </div>
                )}
              </div>
            )}

          {event.is_drawn && event.winner_name && (
            <div className="bg-gradient-to-br from-success/30 to-success/30 border border-success/50 rounded-lg p-6 text-center">
              <Trophy size={40} className="mx-auto text-success mb-3" />
              <h3 className="text-2xl font-bold text-success mb-2">
                {t("eventsUI.winner", { name: event.winner_name })}
              </h3>
              {event.winner_number && (
                <p className="text-3xl font-bold text-success">
                  #{event.winner_number}
                </p>
              )}
            </div>
          )}

          <div>
            <h3 className="text-lg font-semibold text-content-primary mb-4">
              {t("eventsUI.participants", { count: event.participant_count })}
            </h3>
            <div className="bg-surface-base/50 border border-line rounded-lg p-4 max-h-64 overflow-y-auto">
              <div className="grid grid-cols-1 gap-3">
                {event.participants.map((p) => (
                  <div
                    key={p.id}
                    className="flex justify-between items-center bg-surface-base/50 border border-line rounded-md p-3"
                  >
                    <div className="flex items-center gap-2">
                      <span className="text-content-secondary text-sm truncate">
                        {p.username}
                      </span>
                      {p.assigned_number && (
                        <span className="px-2 py-1 bg-primary/20 text-primary rounded font-bold text-xs border border-primary/50">
                          #{p.assigned_number}
                        </span>
                      )}
                    </div>
                    {canManageEvent && event.is_public && (
                      <div className="flex gap-2">
                        <button
                          onClick={() =>
                            handleExcludeParticipant(
                              p.id,
                              p.username || t("eventsUI.values.unknownParticipant"),
                            )
                          }
                          className="px-2 py-1 bg-danger/15 hover:bg-danger/20 text-danger rounded text-xs border border-danger/50 transition-colors"
                          title={t("eventsUI.actions.exclude")}
                        >
                          🚫
                        </button>
                        <button
                          onClick={() =>
                            handleDeleteParticipant(
                              p.id,
                              p.username || t("eventsUI.values.unknownParticipant"),
                            )
                          }
                          className="px-2 py-1 bg-surface hover:bg-surface-raised text-content-secondary rounded text-xs border border-line transition-colors"
                          title={t("eventsUI.actions.remove")}
                        >
                          🗑️
                        </button>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          </div>
        </DialogBody>

        <DialogFooter>
          <button
            onClick={onClose}
            className="app-button-secondary"
          >
            {t("common.close")}
          </button>
        </DialogFooter>
    </Dialog>
  );
};

export default Events;
