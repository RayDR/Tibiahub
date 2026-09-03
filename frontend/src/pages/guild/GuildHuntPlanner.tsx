import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import {
  BookOpen,
  CalendarDays,
  Check,
  ChevronLeft,
  ChevronRight,
  Clock3,
  MapPin,
  Map as MapIcon,
  MessageCircle,
  Plus,
  ShieldCheck,
  Swords,
  UserMinus,
  UserPlus,
  Users,
  X,
} from "lucide-react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { appLocale } from "../../utils/locale";

import {
  Alert,
  Badge,
  Dialog,
  DialogBody,
  DialogFooter,
  DialogHeader,
  DegradedState,
  EmptyState,
  ErrorState,
  FormField,
  Input,
  LoadingState,
  Textarea,
} from "../../components/ui";
import { WorkspaceContentHeader } from "../../components/workspace/WorkspacePrimitives";
import CanonicalHuntZonePicker, { type CanonicalHuntZoneValue } from "../../components/guild/CanonicalHuntZonePicker";
import { useAuth } from "../../context/AuthContext";
import { useToast } from "../../context/ToastContext";
import {
  GuildHunt,
  GuildHuntInput,
  HuntView,
  VocationCode,
  huntPlannerApi,
} from "../../services/huntPlanner";
import { useGuildContext } from "../../utils/guildContext";
import { useGuildCapability } from "../../hooks/useGuildCapability";
import { buildMapEntityUrl } from "../../services/tibiaMap";

const vocations: VocationCode[] = ["EK", "ED", "RP", "MS"];

export default function GuildHuntPlanner() {
  const { t, i18n } = useTranslation();
  const { user } = useAuth();
  const toast = useToast();
  const guildName = useGuildContext(user);
  const { canManageGuild } = useGuildCapability("hunts.manage");
  const canCreate = canManageGuild(guildName);
  const [hunts, setHunts] = useState<GuildHunt[]>([]);
  const [view, setView] = useState<HuntView>("upcoming");
  const [anchor, setAnchor] = useState(() => new Date());
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [editing, setEditing] = useState<GuildHunt | "new" | null>(null);
  const [cancelling, setCancelling] = useState<GuildHunt | null>(null);
  const [cancelReason, setCancelReason] = useState("");
  const [cancelBusy, setCancelBusy] = useState(false);
  const [busy, setBusy] = useState<number | null>(null);

  const load = useCallback(async () => {
    if (!guildName) return;
    setError(false);
    try {
      setHunts(await huntPlannerApi.list({ guild_name: guildName }));
    } catch {
      setError(true);
    } finally {
      setLoading(false);
    }
  }, [guildName]);

  useEffect(() => {
    void load();
  }, [load]);

  const range = useMemo(() => viewRange(view, anchor), [anchor, view]);
  const visible = useMemo(
    () =>
      hunts.filter((item) => {
        const date = new Date(item.scheduled_at);
        return (
          date >= range.start &&
          date < range.end &&
          (view !== "upcoming" || item.status !== "cancelled")
        );
      }),
    [hunts, range, view],
  );
  const grouped = useMemo(
    () =>
      visible.reduce((result, item) => {
        const key = new Date(item.scheduled_at).toLocaleDateString(
          appLocale(i18n.resolvedLanguage || i18n.language),
          { weekday: "long", month: "long", day: "numeric" },
        );
        result.set(key, [...(result.get(key) || []), item]);
        return result;
      }, new Map<string, GuildHunt[]>()),
    [i18n.language, i18n.resolvedLanguage, visible],
  );

  const action = async (
    hunt: GuildHunt,
    operation: "join" | "leave" | "start" | "finish" | "cancel",
  ) => {
    if (operation === "cancel") {
      setCancelReason("");
      setCancelling(hunt);
      return;
    }
    setBusy(hunt.id);
    try {
      await huntPlannerApi[operation](hunt.id);
      toast.success(t(`huntPlanner.feedback.${operation}`));
      await load();
    } catch {
      toast.error(t("huntPlanner.feedback.error"));
    } finally {
      setBusy(null);
    }
  };

  if (loading) return <LoadingState title={t("huntPlanner.loading")} />;
  return (
    <div className="workspace-page">
      <WorkspaceContentHeader
        eyebrow={t("huntPlanner.eyebrow")}
        title={t("huntPlanner.title")}
        description={t("huntPlanner.subtitle")}
        icon={<Swords />}
        action={
          canCreate ? (
            <button
              type="button"
              onClick={() => setEditing("new")}
              className="app-button-primary"
            >
              <Plus className="size-4" />
              {t("huntPlanner.actions.create")}
            </button>
          ) : undefined
        }
      />
      {error && hunts.length === 0 ? (
        <ErrorState
          title={t("huntPlanner.error.title")}
          action={<button type="button" onClick={() => void load()} className="app-button-secondary">{t("common.retry")}</button>}
        />
      ) : error ? (
        <DegradedState
          title={t("huntPlanner.error.title")}
          action={<button type="button" onClick={() => void load()} className="app-button-secondary app-button-sm">{t("common.retry")}</button>}
        />
      ) : null}
      <section
        className="flex flex-col gap-3 rounded-2xl bg-surface-raised p-3 shadow-sm sm:flex-row sm:items-center sm:justify-between"
        aria-label={t("huntPlanner.calendar.label")}
      >
        <div className="flex gap-1 overflow-x-auto">
          {(["upcoming", "week", "month"] as HuntView[]).map((option) => (
            <button
              key={option}
              type="button"
              onClick={() => setView(option)}
              className={`min-h-11 rounded-xl px-4 text-sm font-semibold ${view === option ? "bg-primary text-content-inverse" : "text-content-secondary hover:bg-surface"}`}
            >
              {t(`huntPlanner.views.${option}`)}
            </button>
          ))}
        </div>
        {view !== "upcoming" && (
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => setAnchor(shiftAnchor(anchor, view, -1))}
              className="app-button-ghost"
              aria-label={t("huntPlanner.calendar.previous")}
            >
              <ChevronLeft className="size-4" />
            </button>
            <p className="min-w-40 text-center text-sm font-semibold">
              {range.label.toLocaleDateString(appLocale(i18n.resolvedLanguage || i18n.language), {
                month: "long",
                day: "numeric",
                year: "numeric",
              })}
            </p>
            <button
              type="button"
              onClick={() => setAnchor(shiftAnchor(anchor, view, 1))}
              className="app-button-ghost"
              aria-label={t("huntPlanner.calendar.next")}
            >
              <ChevronRight className="size-4" />
            </button>
          </div>
        )}
      </section>
      {visible.length === 0 ? (error ? null : (
        <EmptyState
          title={t("huntPlanner.empty.title")}
          description={t("huntPlanner.empty.help")}
          action={
            canCreate ? (
              <button
                type="button"
                onClick={() => setEditing("new")}
                className="app-button-primary"
              >
                <Plus className="size-4" />
                {t("huntPlanner.actions.create")}
              </button>
            ) : undefined
          }
        />
      )) : (
        <div className="space-y-6">
          {Array.from(grouped.entries()).map(([date, items]) => (
            <section key={date} className="space-y-3">
              <h2 className="flex items-center gap-2 text-lg font-semibold">
                <CalendarDays className="size-5 text-primary" />
                {date}
              </h2>
              <div className="grid gap-4 xl:grid-cols-2">
                {items.map((hunt) => (
                  <HuntCard
                    key={hunt.id}
                    hunt={hunt}
                    busy={busy === hunt.id}
                    onEdit={() => setEditing(hunt)}
                    onAction={(operation) => void action(hunt, operation)}
                    onAttendance={async (participantId, status) => {
                      setBusy(hunt.id);
                      try {
                        await huntPlannerApi.attendance(
                          hunt.id,
                          participantId,
                          status,
                        );
                        await load();
                      } finally {
                        setBusy(null);
                      }
                    }}
                  />
                ))}
              </div>
            </section>
          ))}
        </div>
      )}
      <Dialog
        open={editing !== null}
        onClose={() => setEditing(null)}
        label={t(
          editing === "new"
            ? "huntPlanner.form.createTitle"
            : "huntPlanner.form.editTitle",
        )}
        className="ds-dialog-lg"
      >
        <HuntForm
          key={editing === "new" ? "new" : editing?.id || "closed"}
          hunt={editing === "new" ? undefined : editing || undefined}
          guildName={guildName || ""}
          onCancel={() => setEditing(null)}
          onSaved={() => {
            setEditing(null);
            void load();
          }}
        />
      </Dialog>
      <Dialog
        open={cancelling !== null}
        onClose={() => { if (!cancelBusy) setCancelling(null); }}
        label={t("huntPlanner.confirm.cancelTitle")}
        descriptionId="hunt-cancel-description"
      >
        <form
          onSubmit={async (event) => {
            event.preventDefault();
            if (!cancelling || cancelReason.trim().length < 3 || cancelBusy) return;
            const hunt = cancelling;
            setCancelBusy(true);
            setBusy(hunt.id);
            try {
              await huntPlannerApi.cancel(hunt.id, cancelReason.trim());
              toast.success(t("huntPlanner.feedback.cancel"));
              setCancelling(null);
              await load();
            } catch {
              toast.error(t("huntPlanner.feedback.error"));
            } finally {
              setCancelBusy(false);
              setBusy(null);
            }
          }}
          className="flex min-h-0 flex-1 flex-col"
        >
          <DialogHeader>
            <div>
              <h2 className="text-xl font-semibold">{t("huntPlanner.confirm.cancelTitle")}</h2>
              <p id="hunt-cancel-description" className="mt-1 text-sm text-content-secondary">
                {t("huntPlanner.confirm.cancelHelp", { target: cancelling?.target })}
              </p>
            </div>
          </DialogHeader>
          <DialogBody>
            <FormField label={t("huntPlanner.confirm.cancelReason")} required>
              <Textarea
              value={cancelReason}
              onChange={(event) => setCancelReason(event.target.value)}
              required
              minLength={3}
              maxLength={2000}
              disabled={cancelBusy}
              />
            </FormField>
          </DialogBody>
          <DialogFooter>
            <button
              type="button"
              onClick={() => setCancelling(null)}
              disabled={cancelBusy}
              className="app-button-secondary"
            >
              {t("common.cancel")}
            </button>
            <button
              disabled={cancelReason.trim().length < 3 || cancelBusy}
              className="app-button-danger"
            >
              {t("huntPlanner.actions.cancel")}
            </button>
          </DialogFooter>
        </form>
      </Dialog>
    </div>
  );
}

function HuntCard({
  hunt,
  busy,
  onEdit,
  onAction,
  onAttendance,
}: {
  hunt: GuildHunt;
  busy: boolean;
  onEdit: () => void;
  onAction: (
    operation: "join" | "leave" | "start" | "finish" | "cancel",
  ) => void;
  onAttendance: (
    participantId: number,
    status: "attended" | "absent",
  ) => Promise<void>;
}) {
  const { t, i18n } = useTranslation();
  const active = hunt.participants.filter(
    (item) => item.attendance_status !== "left",
  );
  const requirements = vocations.filter(
    (code) =>
      (hunt[
        `required_${code.toLocaleLowerCase()}` as keyof GuildHunt
      ] as number) > 0,
  );
  return (
    <article className="overflow-hidden rounded-2xl bg-surface-raised shadow-sm">
      <div className="bg-gradient-to-br from-primary-subtle via-surface-raised to-accent-subtle p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <Badge
                tone={
                  hunt.status === "cancelled"
                    ? "danger"
                    : hunt.status === "finished"
                      ? "success"
                      : hunt.status === "in_progress"
                        ? "warning"
                        : "info"
                }
              >
                {t(`huntPlanner.status.${hunt.status}`)}
              </Badge>
              <span className="text-sm text-content-muted">
                {hunt.server_name}
              </span>
            </div>
            <h3 className="mt-2 text-xl font-semibold">{hunt.target}</h3>
            <p className="mt-1 flex items-center gap-1 text-sm text-content-secondary">
              <MapPin className="size-4" />
              {hunt.location}
            </p>
          </div>
          <div className="text-right">
            <p className="font-semibold">
              {new Date(hunt.scheduled_at).toLocaleTimeString(appLocale(i18n.resolvedLanguage || i18n.language), {
                hour: "2-digit",
                minute: "2-digit",
              })}
            </p>
            <p className="text-xs text-content-muted">{hunt.timezone_name}</p>
          </div>
        </div>
      </div>
      <div className="space-y-4 p-5">
        {hunt.hunting_zone_summary ? <CanonicalZoneStrip hunt={hunt} /> : null}
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <Metric
            icon={<ShieldCheck />}
            label={t("huntPlanner.card.level")}
            value={`${hunt.recommended_level}+`}
          />
          <Metric
            icon={<Users />}
            label={t("huntPlanner.card.party")}
            value={`${hunt.registered_count}/${hunt.maximum_participants}`}
          />
          <Metric
            icon={<Swords />}
            label={t("huntPlanner.card.vocations")}
            value={
              hunt.recommended_vocations.join(" · ") ||
              t("huntPlanner.card.any")
            }
          />
          <Metric
            icon={<Clock3 />}
            label={t("huntPlanner.card.attendance")}
            value={String(
              active.filter((item) => item.attendance_status === "attended")
                .length,
            )}
          />
        </div>
        {requirements.length > 0 && (
          <p className="text-sm text-content-secondary">
            {t("huntPlanner.card.required")}:{" "}
            {requirements
              .map(
                (code) =>
                  `${code} ${hunt[`required_${code.toLocaleLowerCase()}` as keyof GuildHunt]}`,
              )
              .join(" · ")}
          </p>
        )}
        {hunt.description && (
          <p className="text-sm leading-relaxed text-content-secondary">
            {hunt.description}
          </p>
        )}
        {(hunt.discord_channel || hunt.voice_channel) && (
          <p className="flex items-center gap-2 text-sm text-content-muted">
            <MessageCircle className="size-4" />
            {[hunt.discord_channel, hunt.voice_channel]
              .filter(Boolean)
              .join(" · ")}
          </p>
        )}
        <div>
          <h4 className="font-semibold">
            {t("huntPlanner.participants.title")}
          </h4>
          {active.length ? (
            <div className="mt-2 grid gap-2 sm:grid-cols-2">
              {active.map((item) => (
                <div
                  key={item.id}
                  className="flex min-h-11 items-center justify-between gap-2 rounded-xl bg-surface px-3 text-sm"
                >
                  <span className="truncate">
                    <strong>{item.character_name}</strong>
                    {item.vocation ? ` · ${item.vocation}` : ""}
                  </span>
                  {hunt.capabilities.attendance ? (
                    <span className="flex gap-1">
                      <button
                        type="button"
                        disabled={busy}
                        onClick={() => void onAttendance(item.id, "attended")}
                        className={`rounded-lg p-2 ${item.attendance_status === "attended" ? "bg-success-subtle text-success" : "text-content-muted hover:bg-surface-raised"}`}
                        aria-label={t("huntPlanner.participants.attended")}
                      >
                        <Check className="size-4" />
                      </button>
                      <button
                        type="button"
                        disabled={busy}
                        onClick={() => void onAttendance(item.id, "absent")}
                        className={`rounded-lg p-2 ${item.attendance_status === "absent" ? "bg-danger-subtle text-danger" : "text-content-muted hover:bg-surface-raised"}`}
                        aria-label={t("huntPlanner.participants.absent")}
                      >
                        <X className="size-4" />
                      </button>
                    </span>
                  ) : (
                    <Badge>
                      {t(`huntPlanner.attendance.${item.attendance_status}`)}
                    </Badge>
                  )}
                </div>
              ))}
            </div>
          ) : (
            <p className="mt-1 text-sm text-content-muted">
              {t("huntPlanner.participants.empty")}
            </p>
          )}
        </div>
        <div className="flex flex-wrap gap-2">
          {hunt.status === "scheduled" &&
            (hunt.current_user_joined ? (
              <button
                type="button"
                disabled={busy}
                onClick={() => onAction("leave")}
                className="app-button-secondary"
              >
                <UserMinus className="size-4" />
                {t("huntPlanner.actions.leave")}
              </button>
            ) : (
              <button
                type="button"
                disabled={
                  busy || hunt.registered_count >= hunt.maximum_participants
                }
                onClick={() => onAction("join")}
                className="app-button-primary"
              >
                <UserPlus className="size-4" />
                {t("huntPlanner.actions.join")}
              </button>
            ))}
          {hunt.capabilities.manage && hunt.status === "scheduled" && (
            <>
              <button
                type="button"
                onClick={onEdit}
                className="app-button-secondary"
              >
                {t("huntPlanner.actions.edit")}
              </button>
              <button
                type="button"
                disabled={busy}
                onClick={() => onAction("start")}
                className="app-button-secondary"
              >
                {t("huntPlanner.actions.start")}
              </button>
              <button
                type="button"
                disabled={busy}
                onClick={() => onAction("cancel")}
                className="app-button-ghost text-danger"
              >
                {t("huntPlanner.actions.cancel")}
              </button>
            </>
          )}
          {hunt.capabilities.manage && hunt.status === "in_progress" && (
            <button
              type="button"
              disabled={busy}
              onClick={() => onAction("finish")}
              className="app-button-primary"
            >
              {t("huntPlanner.actions.finish")}
            </button>
          )}
        </div>
        {hunt.status === "cancelled" && hunt.cancellation_reason && (
          <p className="rounded-xl bg-danger-subtle p-3 text-sm text-danger">
            {hunt.cancellation_reason}
          </p>
        )}
      </div>
    </article>
  );
}

function CanonicalZoneStrip({ hunt }: { hunt: GuildHunt }) {
  const { t } = useTranslation();
  const zone = hunt.hunting_zone_summary;
  if (!zone) return null;
  const identifier = zone.slug || zone.domain_id;
  const mapUrl = buildMapEntityUrl({
    canonicalEntityId: zone.canonical_id,
    entityType: 'hunt_zone',
    name: zone.name,
    slug: zone.slug,
    floor: zone.map_floor,
  });
  return <div className="rounded-xl border border-primary/30 bg-primary-subtle p-3">
    <div className="flex flex-wrap items-start justify-between gap-3">
      <div className="min-w-0">
        <div className="flex flex-wrap items-center gap-2">
          <Badge tone="info">{t('huntPlanner.zone.canonicalBadge')}</Badge>
          {!zone.is_current ? <Badge tone="warning">{t('huntPlanner.zone.notCurrentShort')}</Badge> : null}
        </div>
        {identifier ? <Link to={`/hunt-zones/${identifier}`} className="mt-1 block truncate font-semibold text-content-primary hover:text-primary">{zone.name}</Link> : <p className="mt-1 font-semibold">{zone.name}</p>}
        <p className="mt-1 text-xs text-content-secondary">{zone.region || zone.city || t('huntPlanner.zone.locationUnknown')}</p>
      </div>
      <div className="flex flex-wrap gap-2">
        {zone.access_required === true ? <Badge tone="warning"><BookOpen className="mr-1 inline size-3" />{t('huntPlanner.zone.accessRequired')}</Badge> : null}
        {zone.map_available ? <Link to={mapUrl} className="app-button-secondary app-button-sm"><MapIcon className="size-4" />{t('huntPlanner.zone.viewMap')}</Link> : <span className="inline-flex items-center gap-1 text-xs text-content-muted"><MapIcon className="size-3" />{t('huntPlanner.zone.noGeometryShort')}</span>}
      </div>
    </div>
    {zone.creature_preview.length ? <div className="mt-3 flex flex-wrap gap-2" aria-label={t('huntPlanner.zone.creatures')}>
      {zone.creature_preview.slice(0, 4).map((creature) => <span key={creature.canonical_id || creature.id || creature.name} className="inline-flex items-center gap-1.5 rounded-lg bg-surface-raised px-2 py-1 text-xs text-content-secondary">
        {creature.image_url ? <img src={creature.image_url} alt="" className="size-6 object-contain [image-rendering:pixelated]" /> : null}
        {creature.name}{creature.is_boss ? <span className="font-semibold text-warning">· {t('huntPlanner.zone.boss')}</span> : null}
      </span>)}
      {zone.creature_count > 4 ? <span className="self-center text-xs text-content-muted">+{zone.creature_count - 4}</span> : null}
    </div> : null}
  </div>;
}

function Metric({
  icon,
  label,
  value,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
}) {
  return (
    <div className="rounded-xl bg-surface p-3">
      <span className="text-primary [&>svg]:size-4">{icon}</span>
      <p className="mt-2 text-xs text-content-muted">{label}</p>
      <p className="font-semibold">{value}</p>
    </div>
  );
}

function HuntForm({
  hunt,
  guildName,
  onCancel,
  onSaved,
}: {
  hunt?: GuildHunt;
  guildName: string;
  onCancel: () => void;
  onSaved: () => void;
}) {
  const { t } = useTranslation();
  const toast = useToast();
  const [busy, setBusy] = useState(false);
  const [submitError, setSubmitError] = useState(false);
  const [zoneMode, setZoneMode] = useState<'canonical' | 'custom'>(hunt?.hunting_zone_id ? 'canonical' : 'custom');
  const [selectedZone, setSelectedZone] = useState<CanonicalHuntZoneValue | null>(hunt?.hunting_zone_summary || null);
  const local = hunt ? toLocalInput(new Date(hunt.scheduled_at)) : "";
  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (busy) return;
    setBusy(true);
    setSubmitError(false);
    const data = new FormData(event.currentTarget);
    const required = (code: VocationCode) =>
      Number(data.get(`required_${code.toLocaleLowerCase()}`) || 0);
    const payload: GuildHuntInput = {
      guild_name: guildName,
      scheduled_at: new Date(String(data.get("scheduled_at"))).toISOString(),
      timezone_name: Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC",
      server_name: String(data.get("server_name")),
      location: String(data.get("location")),
      target: String(data.get("target")),
      hunting_zone_id: zoneMode === 'canonical' ? selectedZone?.canonical_id || null : null,
      recommended_level: Number(data.get("recommended_level")),
      recommended_vocations: vocations.filter(
        (code) => data.get(`vocation_${code}`) === "on",
      ),
      maximum_participants: Number(data.get("maximum_participants")),
      required_ek: required("EK"),
      required_ed: required("ED"),
      required_rp: required("RP"),
      required_ms: required("MS"),
      description: String(data.get("description") || "") || undefined,
      discord_channel: String(data.get("discord_channel") || "") || undefined,
      voice_channel: String(data.get("voice_channel") || "") || undefined,
    };
    try {
      hunt
        ? await huntPlannerApi.update(hunt.id, payload)
        : await huntPlannerApi.create(payload);
      toast.success(
        t(
          hunt
            ? "huntPlanner.feedback.updated"
            : "huntPlanner.feedback.created",
        ),
      );
      onSaved();
    } catch {
      toast.error(t("huntPlanner.feedback.error"));
      setSubmitError(true);
      setBusy(false);
    }
  };
  return (
    <form onSubmit={submit} className="flex min-h-0 flex-1 flex-col">
      <DialogHeader>
        <div>
          <h2 className="text-xl font-semibold">
            {t(hunt ? "huntPlanner.form.editTitle" : "huntPlanner.form.createTitle")}
          </h2>
          <p className="mt-1 text-sm text-content-secondary">{t("huntPlanner.subtitle")}</p>
        </div>
      </DialogHeader>
      <DialogBody className="space-y-5">
        {submitError ? <Alert tone="danger">{t("huntPlanner.feedback.error")}</Alert> : null}
        <CanonicalHuntZonePicker
          mode={zoneMode}
          value={selectedZone}
          disabled={busy}
          onModeChange={setZoneMode}
          onChange={setSelectedZone}
        />
        <div className="grid gap-4 sm:grid-cols-2">
        {(
          [
            ["scheduled_at", "datetime-local", local],
            ["server_name", "text", hunt?.server_name || ""],
            ["location", "text", hunt?.location || ""],
            ["target", "text", hunt?.target || ""],
            ["recommended_level", "number", hunt?.recommended_level || 100],
            ["maximum_participants", "number", hunt?.maximum_participants || 8],
          ] as const
        ).map(([name, type, value]) => (
          <FormField key={name} label={t(`huntPlanner.fields.${name}`)} required>
            <Input
              name={name}
              type={type}
              defaultValue={value}
              min={type === "number" ? 1 : undefined}
              required
              disabled={busy}
            />
          </FormField>
        ))}
        </div>
        <fieldset disabled={busy}>
        <legend className="text-sm font-semibold">
          {t("huntPlanner.fields.recommended_vocations")}
        </legend>
        <div className="mt-2 grid grid-cols-2 gap-2 sm:grid-cols-4">
          {vocations.map((code) => (
            <label
              key={code}
              className="flex min-h-11 items-center gap-2 rounded-xl bg-surface px-3"
            >
              <input
                name={`vocation_${code}`}
                type="checkbox"
                defaultChecked={hunt?.recommended_vocations.includes(code)}
              />
              {code}
            </label>
          ))}
        </div>
        </fieldset>
        <fieldset disabled={busy}>
        <legend className="text-sm font-semibold">
          {t("huntPlanner.fields.required_roles")}
        </legend>
        <div className="mt-2 grid grid-cols-2 gap-3 sm:grid-cols-4">
          {vocations.map((code) => (
            <FormField key={code} label={code}>
              <Input
                name={`required_${code.toLocaleLowerCase()}`}
                type="number"
                min={0}
                max={100}
                defaultValue={
                  (hunt?.[
                    `required_${code.toLocaleLowerCase()}` as keyof GuildHunt
                  ] as number) || 0
                }
              />
            </FormField>
          ))}
        </div>
        </fieldset>
        <FormField label={t("huntPlanner.fields.description")}>
          <Textarea
          name="description"
          defaultValue={hunt?.description || ""}
          maxLength={4000}
          disabled={busy}
        />
        </FormField>
        <div className="grid gap-4 sm:grid-cols-2">
          <FormField label={t("huntPlanner.fields.discord_channel")}>
            <Input
            name="discord_channel"
            defaultValue={hunt?.discord_channel || ""}
            disabled={busy}
          />
          </FormField>
          <FormField label={t("huntPlanner.fields.voice_channel")}>
            <Input
            name="voice_channel"
            defaultValue={hunt?.voice_channel || ""}
            disabled={busy}
          />
          </FormField>
        </div>
        <p className="text-xs text-content-muted">{t("huntPlanner.form.discordFuture")}</p>
      </DialogBody>
      <DialogFooter>
        <button
          type="button"
          onClick={onCancel}
          disabled={busy}
          className="app-button-secondary"
        >
          {t("common.cancel")}
        </button>
        <button disabled={busy} className="app-button-primary">
          {busy ? t("leadership.actions.saving") : t("common.save")}
        </button>
      </DialogFooter>
    </form>
  );
}

function toLocalInput(date: Date) {
  const offset = date.getTimezoneOffset() * 60000;
  return new Date(date.getTime() - offset).toISOString().slice(0, 16);
}
function viewRange(view: HuntView, anchor: Date) {
  const start = new Date(anchor);
  start.setHours(0, 0, 0, 0);
  if (view === "upcoming")
    return {
      start: new Date(),
      end: new Date(Date.now() + 1000 * 60 * 60 * 24 * 180),
      label: new Date(),
    };
  if (view === "week") {
    start.setDate(start.getDate() - ((start.getDay() + 6) % 7));
    const end = new Date(start);
    end.setDate(end.getDate() + 7);
    return { start, end, label: start };
  }
  start.setDate(1);
  const end = new Date(start);
  end.setMonth(end.getMonth() + 1);
  return { start, end, label: start };
}
function shiftAnchor(anchor: Date, view: HuntView, direction: number) {
  const next = new Date(anchor);
  if (view === "week") next.setDate(next.getDate() + direction * 7);
  else next.setMonth(next.getMonth() + direction);
  return next;
}
