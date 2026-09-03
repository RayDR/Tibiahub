import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import {
  AlertCircle,
  CalendarClock,
  CheckCircle2,
  Clock3,
  LockKeyhole,
  MoreVertical,
  Trophy,
  Users,
} from "lucide-react";
import { useTranslation } from "react-i18next";
import { useAuth } from "../../context/AuthContext";
import {
  EmptyState,
  MobileSectionTabs,
  WorkspaceContentHeader,
} from "../../components/workspace/WorkspacePrimitives";
import RaffleCreationWizard from "../../components/raffle/RaffleCreationWizard";
import { raffleApi, RaffleWorkspaceItem } from "../../services/raffle";
import { formatDate, formatDateTime } from "../../utils/locale";
import AutomaticRaffleOperations from "./AutomaticRaffleOperations";
import { useToast } from "../../context/ToastContext";
import { useConfirmation } from "../../context/ConfirmationContext";

const timeline = [
  "draft",
  "registration",
  "eligibility",
  "frozen",
  "scheduled",
  "running",
  "private",
  "published",
  "delivery",
  "completed",
];

function getErrorMessage(error: unknown): string | undefined {
  if (!error || typeof error !== "object") return undefined;
  const candidate = error as { message?: unknown; response?: { data?: { detail?: unknown } } };
  const detail = candidate.response?.data?.detail;
  if (typeof detail === "string") return detail;
  if (detail && typeof detail === "object" && "message" in detail) {
    const message = (detail as { message?: unknown }).message;
    if (typeof message === "string") return message;
  }
  return typeof candidate.message === "string" ? candidate.message : undefined;
}

function stageFor(item: RaffleWorkspaceItem): number {
  if (item.status === "completed") return 9;
  if (item.publication_status === "published")
    return item.winners.every((winner) => winner.delivery_status !== "pending")
      ? 9
      : 7;
  if (item.execution_state === "succeeded") return 6;
  if (item.execution_state === "running" || item.execution_state === "claimed")
    return 5;
  if (item.eligibility?.frozen) return 3;
  if (item.status === "open") return 1;
  return item.scheduled_run_at ? 4 : 0;
}

function Countdown({ value }: { value?: string }) {
  const { t } = useTranslation();
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, []);
  if (!value) return <span>{t("raffle.workspace.unscheduled")}</span>;
  const seconds = Math.max(
    0,
    Math.floor((new Date(value).getTime() - now) / 1000),
  );
  if (!seconds) return <span>{t("raffle.workspace.ready")}</span>;
  const days = Math.floor(seconds / 86400);
  const hours = Math.floor((seconds % 86400) / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  return (
    <span>{t("raffle.workspace.countdown", { days, hours, minutes })}</span>
  );
}

export default function RafflesWorkspace({
  guildName: fixedGuild,
  worldName: fixedWorld,
  assistance = false,
}: {
  guildName?: string;
  worldName?: string;
  assistance?: boolean;
}) {
  const { t, i18n } = useTranslation();
  const { user } = useAuth();
  const toast = useToast();
  const confirmation = useConfirmation();
  const [params, setParams] = useSearchParams();
  const navigate = useNavigate();
  const [authorizedGuilds, setAuthorizedGuilds] = useState<string[]>(fixedGuild ? [fixedGuild] : []);
  const [selectedGuild, setSelectedGuild] = useState(fixedGuild || "");
  const guildName = fixedGuild || selectedGuild || user?.guild_name || "";
  const worldName = fixedWorld || user?.world_name || "";
  const [items, setItems] = useState<RaffleWorkspaceItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [showCreate, setShowCreate] = useState(false);
  const load = useCallback(async () => {
    setError(false);
    try {
      setItems(await raffleApi.workspace());
    } catch {
      setError(true);
    } finally {
      setLoading(false);
    }
  }, []);
  useEffect(() => {
    void load();
  }, [load]);
  useEffect(() => {
    void raffleApi.manageableGuilds().then(names => {
      const options = fixedGuild ? [fixedGuild] : names;
      setAuthorizedGuilds(options);
      setSelectedGuild(current => current || options[0] || "");
    }).catch(() => setAuthorizedGuilds(fixedGuild ? [fixedGuild] : []));
  }, [fixedGuild]);
  const guildItems = useMemo(
    () =>
      items.filter(
        (item) =>
          item.scope_type === "guild" &&
          item.guild_name.toLocaleLowerCase() === guildName.toLocaleLowerCase(),
      ),
    [guildName, items],
  );
  const modern = guildItems.filter((item) => item.purpose !== "legacy");
  const requested = params.get("section") || "upcoming";
  const section = [
    "upcoming",
    "participants",
    "eligibility",
    "draw",
    "results",
    "history",
  ].includes(requested)
    ? requested
    : "upcoming";
  const tabs = [
    "upcoming",
    "participants",
    "eligibility",
    "draw",
    "results",
    "history",
  ].map((id) => ({ id, label: t(`workspace.raffles.tabs.${id}`) }));
  const canCreate = Boolean(user?.is_superuser || authorizedGuilds.length);
  const canManage =
    Boolean(user?.is_superuser && assistance) ||
    modern.some((item) => item.capabilities.manage);

  async function runCardAction(item: RaffleWorkspaceItem, action: "edit" | "cancel" | "delete") {
    try {
      if (action === "edit") {
        navigate(`/guild/raffles/manage?raffle=${item.id}`);
        return;
      }
      if (action === "cancel") {
        await raffleApi.softDelete(item.id, "Cancelled from workspace action menu");
        toast.success(t("raffle.workspace.actionArchived", "Raffle archived"));
      }
      if (action === "delete") {
        if (!(await confirmation.confirm(t("raffle.workspace.permanentDeleteConfirm", { title: item.title }), { danger: true, confirmLabel: t("raffle.workspace.permanentDelete") }))) return;
        await raffleApi.permanentDelete(
          item.id,
          "Permanent deletion requested from workspace action menu",
          `DELETE RAFFLE ${item.id}`,
        );
        toast.success(t("raffle.workspace.actionDeleted", "Raffle permanently deleted"));
      }
      await load();
    } catch (error: unknown) {
      toast.error(getErrorMessage(error) || t("raffle.workspace.actionFailed", "Action failed"));
    }
  }

  function disabledReason(item: RaffleWorkspaceItem, key: keyof NonNullable<RaffleWorkspaceItem["actions"]>) {
    if (!item.actions) return undefined;
    return item.actions[key]?.enabled ? undefined : item.actions[key]?.reason || t("raffle.workspace.actionUnavailable", "Action unavailable");
  }
  return (
    <div className="workspace-page">
      <WorkspaceContentHeader
        title={t("workspace.raffles.title")}
        description={t("workspace.raffles.subtitle")}
        icon={<Trophy />}
        action={
          <div className="flex items-center gap-2">
            {!fixedGuild && authorizedGuilds.length > 1 ? <label className="sr-only" htmlFor="raffle-guild-selector">{t("raffle.workspace.fields.guild")}</label> : null}
            {!fixedGuild && authorizedGuilds.length > 1 ? <select id="raffle-guild-selector" value={guildName} onChange={event => setSelectedGuild(event.target.value)} className="min-h-11 rounded-lg border border-line bg-surface px-3">{authorizedGuilds.map(name => <option key={name}>{name}</option>)}</select> : null}
            {canCreate && (
              <button
                type="button"
                onClick={() => setShowCreate((value) => !value)}
                className="app-button-primary min-h-11 rounded-lg px-4 font-semibold"
              >
                {t("raffle.workspace.create")}
              </button>
            )}
          </div>
        }
      />
      {showCreate && (
        <RaffleCreationWizard
          guildName={guildName}
          worldName={worldName}
          isGlobalAdmin={Boolean(user?.is_superuser)}
          assistance={assistance}
          onCreated={() => {
            setShowCreate(false);
            void load();
          }}
        />
      )}
      <MobileSectionTabs
        tabs={tabs}
        active={section}
        onChange={(value) => setParams({ section: value })}
      />
      {loading ? (
        <div className="grid gap-3 sm:grid-cols-2">
          {[0, 1].map((value) => (
            <div
              key={value}
              className="h-40 animate-pulse rounded-xl bg-surface-base"
            />
          ))}
        </div>
      ) : error ? (
        <EmptyState
          title={t("raffle.workspace.errors.title")}
          description={t("raffle.workspace.errors.help")}
          action={
            <button
              onClick={() => void load()}
              className="min-h-11 rounded-lg border border-line px-4"
            >
              {t("raffle.workspace.retry")}
            </button>
          }
        />
      ) : section === "history" ? (
        <div className="grid gap-3 sm:grid-cols-2">
          {guildItems
            .filter(
              (item) =>
                item.purpose === "legacy" || item.status === "completed",
            )
            .map((item) => (
              <article
                key={item.id}
                className="rounded-xl border border-line p-4"
              >
                <span className="text-xs uppercase text-content-muted">
                  {t("raffle.workspace.historyLabel")}
                </span>
                <h2 className="mt-1 font-semibold">{item.title}</h2>
                <p className="mt-2 text-sm text-content-secondary">
                  {item.scheduled_run_at
                    ? formatDate(item.scheduled_run_at, i18n.resolvedLanguage || i18n.language)
                    : t("raffle.workspace.unscheduled")}
                </p>
                {item.publication_status === "published" && (
                  <Link
                    to={`/raffles/${item.public_code}`}
                    className="mt-3 inline-flex min-h-11 items-center text-info"
                  >
                    {t("raffle.workspace.publicLink")}
                  </Link>
                )}
              </article>
            ))}
          {guildItems.filter(
            (item) => item.purpose === "legacy" || item.status === "completed",
          ).length === 0 && (
            <EmptyState
              title={t("raffle.workspace.empty.history")}
              description={t("raffle.workspace.empty.help")}
            />
          )}
        </div>
      ) : modern.length === 0 ? (
        <EmptyState
          title={t(`raffle.workspace.empty.${section}`)}
          description={t("raffle.workspace.empty.help")}
        />
      ) : (
        <>
          {section === "upcoming" && (
            <div className="grid gap-3 lg:grid-cols-2">
              {modern.map((item) => {
                const current = stageFor(item);
                return (
                  <article
                    key={item.id}
                    className="rounded-2xl border border-line bg-surface-base/40 p-4"
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <div className="flex flex-wrap items-center gap-2">
                          <h2 className="font-semibold">{item.title}</h2>
                          {item.purpose === "test" && (
                            <span className="rounded-full bg-accent/20 px-2 py-1 text-xs text-accent">
                              {t("raffle.operations.testLabel")}
                            </span>
                          )}
                        </div>
                        <p className="mt-1 flex items-center gap-2 text-sm text-content-secondary">
                          <CalendarClock className="h-4 w-4" />
                          <Countdown value={item.scheduled_run_at} />
                        </p>
                      </div>
                      <span className="rounded-full border border-line px-2 py-1 text-xs">
                        {t(`raffle.workspace.timeline.${timeline[current]}`)}
                      </span>
                    </div>
                    <div
                      className="mt-4 flex gap-1 overflow-hidden"
                      aria-label={t("raffle.workspace.timeline.label")}
                    >
                      {timeline.map((stage, index) => (
                        <span
                          key={stage}
                          title={t(`raffle.workspace.timeline.${stage}`)}
                          className={`h-2 min-w-3 flex-1 rounded ${index <= current ? "bg-primary" : "bg-surface"}`}
                        />
                      ))}
                    </div>
                    {item.last_error_summary && (
                      <p className="mt-3 flex gap-2 text-sm text-danger">
                        <AlertCircle className="h-4 w-4" />
                        {t("raffle.workspace.executionFailed")}
                      </p>
                    )}
                    {item.status === "open" && !item.capabilities.manage && (
                      <Link
                        to={`/raffles/${item.public_code}`}
                        className="mt-4 inline-flex min-h-11 items-center rounded-lg border border-success/40 px-4 text-sm text-success"
                      >
                        {t("raffle.workspace.register")}
                      </Link>
                    )}
                    {item.capabilities.manage && (
                      <details className="mt-4">
                        <summary className="inline-flex min-h-11 cursor-pointer items-center gap-2 rounded-lg border border-line px-3 text-sm text-content-secondary">
                          <MoreVertical className="h-4 w-4" />
                          {t("raffle.workspace.actions", "Actions")}
                        </summary>
                        <div className="mt-2 grid gap-2 rounded-lg border border-line bg-surface-base p-2 text-sm">
                          <button
                            type="button"
                            className="min-h-11 rounded-md border border-line px-3 text-left"
                            disabled={!item.actions?.edit?.enabled}
                            title={disabledReason(item, "edit")}
                            onClick={() => void runCardAction(item, "edit")}
                          >
                            {t("raffle.workspace.edit", "Edit raffle")}
                          </button>
                          <button
                            type="button"
                            className="min-h-11 rounded-md border border-line px-3 text-left"
                            disabled={!item.actions?.cancel_archive?.enabled}
                            title={disabledReason(item, "cancel_archive")}
                            onClick={() => void runCardAction(item, "cancel")}
                          >
                            {t("raffle.workspace.archive", "Cancel / archive")}
                          </button>
                          <button
                            type="button"
                            className="min-h-11 rounded-md border border-danger/50 px-3 text-left text-danger"
                            disabled={!item.actions?.permanent_delete?.enabled}
                            title={disabledReason(item, "permanent_delete")}
                            onClick={() => void runCardAction(item, "delete")}
                          >
                            {t("raffle.workspace.deletePermanent", "Permanent delete")}
                          </button>
                        </div>
                      </details>
                    )}
                  </article>
                );
              })}
            </div>
          )}
          {section === "participants" && (
            <div className="grid gap-3 sm:grid-cols-2">
              {modern.map((item) => (
                <article
                  key={item.id}
                  className="rounded-xl border border-line p-4"
                >
                  <Users className="h-5 w-5 text-info" />
                  <h2 className="mt-2 font-semibold">{item.title}</h2>
                  <strong className="mt-3 block text-3xl">
                    {item.participant_count}
                  </strong>
                  <span className="text-sm text-content-secondary">
                    {t("raffle.workspace.registered")}
                  </span>
                </article>
              ))}
            </div>
          )}
          {section === "eligibility" && (
            <div className="grid gap-3">
              {modern.map((item) => (
                <article
                  key={item.id}
                  className="rounded-xl border border-line p-4"
                >
                  <h2 className="font-semibold">{item.title}</h2>
                  {item.eligibility ? (
                    <div className="mt-3 grid grid-cols-3 gap-2 text-center">
                      <div>
                        <strong className="block text-2xl">
                          {item.eligibility.candidate_count}
                        </strong>
                        <span className="text-xs text-content-secondary">
                          {t("raffle.workspace.registered")}
                        </span>
                      </div>
                      <div>
                        <strong className="block text-2xl text-success">
                          {item.eligibility.eligible_count}
                        </strong>
                        <span className="text-xs text-content-secondary">
                          {t("raffle.workspace.eligible")}
                        </span>
                      </div>
                      <div>
                        <strong className="block text-2xl text-danger">
                          {item.eligibility.excluded_count}
                        </strong>
                        <span className="text-xs text-content-secondary">
                          {t("raffle.workspace.excluded")}
                        </span>
                      </div>
                      <p className="col-span-3 mt-2 flex items-center justify-center gap-2 text-xs text-content-secondary">
                        <LockKeyhole className="h-4 w-4" />
                        {t("raffle.workspace.frozenAt", {
                          value: formatDateTime(item.eligibility.cutoff_at, i18n.resolvedLanguage || i18n.language),
                        })}
                      </p>
                    </div>
                  ) : (
                    <p className="mt-3 text-sm text-content-secondary">
                      {t("raffle.workspace.snapshotPending")}
                    </p>
                  )}
                </article>
              ))}
            </div>
          )}
          {section === "draw" &&
            (canManage ? (
              <AutomaticRaffleOperations guildName={guildName} compact />
            ) : (
              <EmptyState
                title={t("raffle.workspace.privateDraw")}
                description={t("raffle.workspace.privateDrawHelp")}
              />
            ))}
          {section === "results" && (
            <div className="grid gap-3">
              {modern.map((item) => (
                <article
                  key={item.id}
                  className="rounded-xl border border-line p-4"
                >
                  <div className="flex items-center gap-2">
                    <Trophy className="h-5 w-5 text-primary" />
                    <h2 className="font-semibold">{item.title}</h2>
                  </div>
                  {item.publication_status === "private" ? (
                    <p className="mt-3 flex items-center gap-2 text-sm text-content-secondary">
                      <LockKeyhole className="h-4 w-4" />
                      {t("raffle.workspace.privateResult")}
                    </p>
                  ) : (
                    <div className="mt-3 grid gap-2 sm:grid-cols-2">
                      {item.winners.map((winner) => (
                        <div
                          key={winner.prize_position}
                          className="rounded-lg bg-surface-base p-3"
                        >
                          <span className="text-xs text-content-secondary">
                            {t(
                              `raffle.workspace.positions.${winner.prize_position}`,
                            )}
                          </span>
                          <strong className="block text-lg">
                            {winner.character_name}
                          </strong>
                          <span className="text-primary">
                            {winner.amount} {winner.currency}
                          </span>
                          <small className="mt-1 flex items-center gap-1 text-content-secondary">
                            {winner.delivery_status === "delivered" ? (
                              <CheckCircle2 className="h-3 w-3" />
                            ) : (
                              <Clock3 className="h-3 w-3" />
                            )}
                            {t(
                              `raffle.operations.delivery.${winner.delivery_status}`,
                            )}
                          </small>
                        </div>
                      ))}
                    </div>
                  )}
                  <Link
                    to={`/raffles/${item.public_code}`}
                    className="mt-3 inline-flex min-h-11 items-center text-sm text-info"
                  >
                    {t("raffle.workspace.publicLink")}
                  </Link>
                </article>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}
