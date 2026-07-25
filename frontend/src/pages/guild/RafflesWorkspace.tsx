import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import {
  AlertCircle,
  CalendarClock,
  CheckCircle2,
  Clock3,
  LockKeyhole,
  Trophy,
  Users,
} from "lucide-react";
import { useTranslation } from "react-i18next";
import { useAuth } from "../../context/AuthContext";
import {
  EmptyState,
  MobileSectionTabs,
  RoleBadge,
  WorkspaceHeader,
} from "../../components/workspace/WorkspacePrimitives";
import RaffleCreationWizard from "../../components/raffle/RaffleCreationWizard";
import { raffleApi, RaffleWorkspaceItem } from "../../services/raffle";
import AutomaticRaffleOperations from "./AutomaticRaffleOperations";

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
  const { t } = useTranslation();
  const { user } = useAuth();
  const [params, setParams] = useSearchParams();
  const guildName = fixedGuild || user?.guild_name || "";
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
  const rank = (user?.guild_rank || "").toLocaleLowerCase();
  const leader = rank.includes("leader") || rank.includes("alpha");
  const canCreate = assistance ? Boolean(user?.is_superuser) : leader;
  const canManage =
    Boolean(user?.is_superuser && assistance) ||
    modern.some((item) => item.capabilities.manage);
  return (
    <div className="space-y-4">
      <WorkspaceHeader
        title={t("workspace.raffles.title")}
        subtitle={t("workspace.raffles.subtitle")}
        badge={assistance ? t("workspace.assistance.badge") : undefined}
        action={
          <div className="flex items-center gap-2">
            {user?.guild_rank && (
              <RoleBadge
                role={
                  leader
                    ? "guild_leader"
                    : rank.includes("vice")
                      ? "guild_viceleader"
                      : "guild_member"
                }
              />
            )}
            {canCreate && (
              <button
                type="button"
                onClick={() => setShowCreate((value) => !value)}
                className="min-h-11 rounded-lg bg-primary px-4 font-semibold text-content-inverse"
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
                    ? new Date(item.scheduled_run_at).toLocaleDateString()
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
                          value: new Date(
                            item.eligibility.cutoff_at,
                          ).toLocaleString(),
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
