import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import {
  CalendarDays,
  Check,
  ChevronLeft,
  ChevronRight,
  Clock3,
  MapPin,
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

import {
  Badge,
  Dialog,
  EmptyState,
  LoadingState,
  PageHeader,
} from "../../components/ui";
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

const vocations: VocationCode[] = ["EK", "ED", "RP", "MS"];

export default function GuildHuntPlanner() {
  const { t, i18n } = useTranslation();
  const { user } = useAuth();
  const toast = useToast();
  const guildName = useGuildContext(user);
  const rank = (user?.guild_rank || "").toLocaleLowerCase();
  const canCreate = Boolean(
    user?.is_superuser || rank.includes("leader") || rank.includes("alpha"),
  );
  const [hunts, setHunts] = useState<GuildHunt[]>([]);
  const [view, setView] = useState<HuntView>("upcoming");
  const [anchor, setAnchor] = useState(() => new Date());
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [editing, setEditing] = useState<GuildHunt | "new" | null>(null);
  const [cancelling, setCancelling] = useState<GuildHunt | null>(null);
  const [cancelReason, setCancelReason] = useState("");
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
          i18n.language,
          { weekday: "long", month: "long", day: "numeric" },
        );
        result.set(key, [...(result.get(key) || []), item]);
        return result;
      }, new Map<string, GuildHunt[]>()),
    [i18n.language, visible],
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
    <div className="space-y-6">
      <PageHeader
        size="lg"
        eyebrow={t("huntPlanner.eyebrow")}
        title={t("huntPlanner.title")}
        subtitle={t("huntPlanner.subtitle")}
        primaryAction={
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
      {error && (
        <div
          role="alert"
          className="rounded-xl bg-danger-subtle p-4 text-danger"
        >
          <p className="font-semibold">{t("huntPlanner.error.title")}</p>
          <button
            type="button"
            onClick={() => void load()}
            className="mt-2 underline"
          >
            {t("common.retry")}
          </button>
        </div>
      )}
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
              {range.label.toLocaleDateString(i18n.language, {
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
      {visible.length === 0 ? (
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
      ) : (
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
        className="max-h-[92dvh] overflow-y-auto p-5 sm:max-w-3xl"
      >
        <HuntForm
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
        onClose={() => setCancelling(null)}
        label={t("huntPlanner.confirm.cancelTitle")}
        className="p-5 sm:max-w-lg"
      >
        <form
          onSubmit={(event) => {
            event.preventDefault();
            if (!cancelling || !cancelReason.trim()) return;
            const hunt = cancelling;
            setCancelling(null);
            setBusy(hunt.id);
            void huntPlannerApi
              .cancel(hunt.id, cancelReason.trim())
              .then(() => {
                toast.success(t("huntPlanner.feedback.cancel"));
                return load();
              })
              .catch(() => toast.error(t("huntPlanner.feedback.error")))
              .finally(() => setBusy(null));
          }}
          className="space-y-4"
        >
          <h2 className="text-xl font-semibold">
            {t("huntPlanner.confirm.cancelTitle")}
          </h2>
          <p className="text-sm text-content-secondary">
            {t("huntPlanner.confirm.cancelHelp", {
              target: cancelling?.target,
            })}
          </p>
          <label className="grid gap-1 text-sm">
            <span>{t("huntPlanner.confirm.cancelReason")}</span>
            <textarea
              autoFocus
              value={cancelReason}
              onChange={(event) => setCancelReason(event.target.value)}
              required
              minLength={3}
              maxLength={2000}
              className="min-h-28 rounded-xl bg-surface p-3"
            />
          </label>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => setCancelling(null)}
              className="app-button-secondary flex-1"
            >
              {t("common.cancel")}
            </button>
            <button
              disabled={cancelReason.trim().length < 3}
              className="app-button-danger flex-1"
            >
              {t("huntPlanner.actions.cancel")}
            </button>
          </div>
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
              {new Date(hunt.scheduled_at).toLocaleTimeString(i18n.language, {
                hour: "2-digit",
                minute: "2-digit",
              })}
            </p>
            <p className="text-xs text-content-muted">{hunt.timezone_name}</p>
          </div>
        </div>
      </div>
      <div className="space-y-4 p-5">
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
  const local = hunt ? toLocalInput(new Date(hunt.scheduled_at)) : "";
  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setBusy(true);
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
      setBusy(false);
    }
  };
  return (
    <form onSubmit={submit} className="space-y-5">
      <h2 className="text-xl font-semibold">
        {t(
          hunt ? "huntPlanner.form.editTitle" : "huntPlanner.form.createTitle",
        )}
      </h2>
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
          <label key={name} className="grid gap-1 text-sm">
            <span>{t(`huntPlanner.fields.${name}`)}</span>
            <input
              name={name}
              type={type}
              defaultValue={value}
              min={type === "number" ? 1 : undefined}
              required
              className="min-h-11 rounded-xl bg-surface px-3"
            />
          </label>
        ))}
      </div>
      <fieldset>
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
      <fieldset>
        <legend className="text-sm font-semibold">
          {t("huntPlanner.fields.required_roles")}
        </legend>
        <div className="mt-2 grid grid-cols-2 gap-3 sm:grid-cols-4">
          {vocations.map((code) => (
            <label key={code} className="grid gap-1 text-sm">
              <span>{code}</span>
              <input
                name={`required_${code.toLocaleLowerCase()}`}
                type="number"
                min={0}
                max={100}
                defaultValue={
                  (hunt?.[
                    `required_${code.toLocaleLowerCase()}` as keyof GuildHunt
                  ] as number) || 0
                }
                className="min-h-11 rounded-xl bg-surface px-3"
              />
            </label>
          ))}
        </div>
      </fieldset>
      <label className="grid gap-1 text-sm">
        <span>{t("huntPlanner.fields.description")}</span>
        <textarea
          name="description"
          defaultValue={hunt?.description || ""}
          maxLength={4000}
          className="min-h-28 rounded-xl bg-surface p-3"
        />
      </label>
      <div className="grid gap-4 sm:grid-cols-2">
        <label className="grid gap-1 text-sm">
          <span>{t("huntPlanner.fields.discord_channel")}</span>
          <input
            name="discord_channel"
            defaultValue={hunt?.discord_channel || ""}
            className="min-h-11 rounded-xl bg-surface px-3"
          />
        </label>
        <label className="grid gap-1 text-sm">
          <span>{t("huntPlanner.fields.voice_channel")}</span>
          <input
            name="voice_channel"
            defaultValue={hunt?.voice_channel || ""}
            className="min-h-11 rounded-xl bg-surface px-3"
          />
        </label>
      </div>
      <p className="text-xs text-content-muted">
        {t("huntPlanner.form.discordFuture")}
      </p>
      <div className="sticky bottom-0 flex gap-2 bg-surface-base py-3">
        <button
          type="button"
          onClick={onCancel}
          className="app-button-secondary flex-1"
        >
          {t("common.cancel")}
        </button>
        <button disabled={busy} className="app-button-primary flex-1">
          {t("common.save")}
        </button>
      </div>
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
