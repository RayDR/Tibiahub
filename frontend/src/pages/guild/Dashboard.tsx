import {
  Activity,
  Bell,
  CalendarClock,
  Coins,
  Megaphone,
  Shield,
  Sparkles,
  Swords,
  UserPlus,
  Users,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { appLocale } from "../../utils/locale";

import { Badge, Card, DegradedState, ErrorState, LoadingState } from "../../components/ui";
import { WorkspaceContentHeader } from "../../components/workspace/WorkspacePrimitives";
import { useAuth } from "../../context/AuthContext";
import { UserActivityEntry, activityApi } from "../../services/activity";
import {
  Announcement,
  Event,
  GuildMember,
  guildApi,
} from "../../services/guild";
import { GuildHunt, huntPlannerApi } from "../../services/huntPlanner";
import {
  LeadershipOpening,
  LeadershipSummary,
  leadershipApi,
} from "../../services/leadership";
import {
  InternalNotification,
  notificationApi,
} from "../../services/notifications";
import { RaffleWorkspaceItem, raffleApi } from "../../services/raffle";
import { useGuildContext } from "../../utils/guildContext";

export default function Dashboard() {
  const { t, i18n } = useTranslation();
  const { user } = useAuth();
  const guildName = useGuildContext(user);
  const [loading, setLoading] = useState(true);
  const [partial, setPartial] = useState(false);
  const [failed, setFailed] = useState(false);
  const [announcements, setAnnouncements] = useState<Announcement[]>([]);
  const [events, setEvents] = useState<Event[]>([]);
  const [hunts, setHunts] = useState<GuildHunt[]>([]);
  const [leadership, setLeadership] = useState<LeadershipSummary | null>(null);
  const [openings, setOpenings] = useState<LeadershipOpening[]>([]);
  const [raffles, setRaffles] = useState<RaffleWorkspaceItem[]>([]);
  const [notifications, setNotifications] = useState<InternalNotification[]>(
    [],
  );
  const [members, setMembers] = useState<GuildMember[]>([]);
  const [activity, setActivity] = useState<UserActivityEntry[]>([]);
  const load = useCallback(async () => {
    if (!guildName) return;
    setLoading(true);
    const results = await Promise.allSettled([
      guildApi.getAnnouncements(0, 4, guildName),
      guildApi.getEvents(0, 4, guildName),
      huntPlannerApi.list({ guild_name: guildName }),
      leadershipApi.summary({ guildName }),
      leadershipApi.openings({ guildName }),
      raffleApi.workspace(),
      notificationApi.list(),
      guildApi.getGuildMembers(guildName),
      activityApi.getMine(6),
    ]);
    setFailed(results.every((item) => item.status === "rejected"));
    setPartial(results.some((item) => item.status === "rejected"));
    if (results[0].status === "fulfilled") setAnnouncements(results[0].value);
    if (results[1].status === "fulfilled") setEvents(results[1].value);
    if (results[2].status === "fulfilled") setHunts(results[2].value);
    if (results[3].status === "fulfilled") setLeadership(results[3].value);
    if (results[4].status === "fulfilled") setOpenings(results[4].value);
    if (results[5].status === "fulfilled")
      setRaffles(
        results[5].value.filter(
          (item) =>
            item.guild_name.toLocaleLowerCase() ===
            guildName.toLocaleLowerCase(),
        ),
      );
    if (results[6].status === "fulfilled") setNotifications(results[6].value);
    if (results[7].status === "fulfilled")
      setMembers(results[7].value.members.slice(0, 6));
    if (results[8].status === "fulfilled") setActivity(results[8].value);
    setLoading(false);
  }, [guildName]);
  useEffect(() => {
    void load();
  }, [load]);
  const today = useMemo(
    () =>
      hunts.filter(
        (item) =>
          new Date(item.scheduled_at).toDateString() ===
            new Date().toDateString() && item.status !== "cancelled",
      ),
    [hunts],
  );
  const upcoming = useMemo(
    () =>
      hunts
        .filter(
          (item) =>
            new Date(item.scheduled_at) > new Date() &&
            item.status === "scheduled",
        )
        .slice(0, 4),
    [hunts],
  );
  const recentRaffles = useMemo(
    () => [...raffles].sort((a, b) => b.id - a.id).slice(0, 4),
    [raffles],
  );
  const unread = notifications.filter((item) => !item.is_read).slice(0, 5);
  const pending =
    (leadership?.applications_requiring_attention || 0) +
    (leadership?.interviews_pending || 0) +
    (leadership?.applications_voting || 0);
  if (loading) return <LoadingState title={t("guildDashboard.loading")} />;
  if (failed) return <ErrorState title={t("guildDashboard.partialError")} action={<button type="button" onClick={() => void load()} className="app-button-secondary">{t("common.retry")}</button>} />;
  return (
    <div className="workspace-page">
      <WorkspaceContentHeader
        eyebrow={t("guildDashboard.eyebrow")}
        title={t("guildDashboard.title")}
        description={t("guildDashboard.commandSubtitle", { guild: guildName })}
        icon={<Swords />}
        action={
          <>
            <Link to="/guild/members" className="app-button-secondary">
              <Users className="size-4" />
              {t("guildDashboard.actions.members")}
            </Link>
            <Link to="/guild/hunts" className="app-button-primary">
              <Swords className="size-4" />
              {t("guildDashboard.actions.planHunt")}
            </Link>
          </>
        }
      />
      {partial && (
        <DegradedState title={t("guildDashboard.partialError")} action={<button type="button" onClick={() => void load()} className="app-button-secondary app-button-sm">{t("common.retry")}</button>} />
      )}
      <section
        className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4"
        aria-label={t("guildDashboard.statusLabel")}
      >
        <Signal
          icon={<Swords />}
          label={t("guildDashboard.signals.todayHunts")}
          value={today.length}
        />
        <Signal
          icon={<UserPlus />}
          label={t("guildDashboard.signals.openRecruitment")}
          value={openings.filter((item) => item.status === "open").length}
        />
        <Signal
          icon={<Shield />}
          label={t("guildDashboard.signals.pendingReviews")}
          value={pending}
        />
        <Signal
          icon={<Bell />}
          label={t("guildDashboard.signals.notifications")}
          value={unread.length}
        />
      </section>
      <div className="grid gap-4 xl:grid-cols-2">
        <CommandCard
          icon={<Swords />}
          title={t("guildDashboard.sections.todayHunts")}
          to="/guild/hunts"
          items={today.map((item) => (
            <HuntRow key={item.id} item={item} />
          ))}
          empty={t("guildDashboard.empty.todayHunts")}
        />
        <CommandCard
          icon={<CalendarClock />}
          title={t("guildDashboard.sections.upcomingHunts")}
          to="/guild/hunts"
          items={upcoming.map((item) => (
            <HuntRow key={item.id} item={item} />
          ))}
          empty={t("guildDashboard.empty.upcomingHunts")}
        />
        <CommandCard
          icon={<Shield />}
          title={t("guildDashboard.sections.leadershipStatus")}
          to="/guild/leadership"
          items={
            leadership
              ? [
                  <div
                    key="leadership"
                    className="rounded-xl bg-primary-subtle p-4"
                  >
                    <div className="flex items-center justify-between gap-3">
                      <strong>
                        {t("guildDashboard.leadershipSummary", {
                          active: leadership.active_viceleaders,
                          openings: leadership.open_positions,
                        })}
                      </strong>
                      <Badge
                        tone={
                          leadership.below_recommended ? "warning" : "success"
                        }
                      >
                        {leadership.below_recommended
                          ? t("leadership.dashboard.attention")
                          : t("workspace.setup.ready")}
                      </Badge>
                    </div>
                  </div>,
                ]
              : []
          }
          empty={t("guildDashboard.empty.leadership")}
        />
        <CommandCard
          icon={<UserPlus />}
          title={t("guildDashboard.sections.openRecruitment")}
          to="/guild/leadership/recruitment"
          items={openings
            .filter((item) => item.status === "open")
            .map((item) => (
              <Row
                key={item.id}
                title={item.title}
                meta={t("leadership.openings.available", {
                  count: Math.max(0, item.openings_count - item.filled_count),
                })}
              />
            ))}
          empty={t("guildDashboard.empty.recruitment")}
        />
        <CommandCard
          icon={<Megaphone />}
          title={t("guildDashboard.sections.guildNews")}
          to="/guild/announcements"
          items={announcements.map((item) => (
            <Row
              key={item.id}
              title={item.title}
              meta={new Date(item.created_at).toLocaleDateString(appLocale(i18n.resolvedLanguage || i18n.language))}
            />
          ))}
          empty={t("guildDashboard.empty.news")}
        />
        <CommandCard
          icon={<CalendarClock />}
          title={t("guildDashboard.sections.recentEvents")}
          to="/guild/events"
          items={events.map((item) => (
            <Row
              key={item.id}
              title={item.title}
              meta={new Date(item.start_time).toLocaleString(appLocale(i18n.resolvedLanguage || i18n.language))}
            />
          ))}
          empty={t("guildDashboard.empty.events")}
        />
        <CommandCard
          icon={<Coins />}
          title={t("guildDashboard.sections.recentRaffles")}
          to="/guild/raffles"
          items={recentRaffles.map((item) => (
            <Row
              key={item.id}
              title={item.title}
              meta={t(`raffle.operations.status.${item.status}`, item.status)}
            />
          ))}
          empty={t("guildDashboard.empty.raffles")}
        />
        <CommandCard
          icon={<Bell />}
          title={t("guildDashboard.sections.notifications")}
          to="/guild/notifications"
          items={unread.map((item) => (
            <Row
              key={item.id}
              title={t(item.title_key, item.interpolation)}
              meta={new Date(item.created_at).toLocaleString(appLocale(i18n.resolvedLanguage || i18n.language))}
            />
          ))}
          empty={t("guildDashboard.empty.notifications")}
        />
        <CommandCard
          icon={<Users />}
          title={t("guildDashboard.sections.recentMembers")}
          to="/guild/members"
          items={members.map((item) => (
            <Row
              key={item.character_name}
              title={item.character_name}
              meta={`${item.vocation || t("common.unknown")} · ${item.level || t("common.notAvailable")}`}
            />
          ))}
          empty={t("guildDashboard.empty.members")}
        />
        <CommandCard
          icon={<Activity />}
          title={t("guildDashboard.sections.recentActivity")}
          to="/profile"
          items={activity.map((item) => (
            <Row
              key={item.id}
              title={
                item.query ||
                item.entity_id ||
                t(
                  `guildDashboard.activity.${item.activity_type}`,
                  item.activity_type,
                )
              }
              meta={new Date(item.created_at).toLocaleString(appLocale(i18n.resolvedLanguage || i18n.language))}
            />
          ))}
          empty={t("guildDashboard.empty.activity")}
        />
      </div>
    </div>
  );
}

function Signal({
  icon,
  label,
  value,
}: {
  icon: React.ReactNode;
  label: string;
  value: number;
}) {
  return (
    <Card className="flex items-center gap-3 p-4">
      <span className="grid size-10 place-items-center rounded-xl bg-primary-subtle text-primary [&>svg]:size-5">
        {icon}
      </span>
      <div>
        <p className="text-2xl font-semibold">{value}</p>
        <p className="text-xs text-content-muted">{label}</p>
      </div>
    </Card>
  );
}
function CommandCard({
  icon,
  title,
  to,
  items,
  empty,
}: {
  icon: React.ReactNode;
  title: string;
  to: string;
  items: React.ReactNode[];
  empty: string;
}) {
  const { t } = useTranslation();
  return (
    <section className="rounded-2xl bg-surface-raised p-4 shadow-sm">
      <div className="mb-3 flex items-center justify-between gap-3">
        <h2 className="flex items-center gap-2 font-semibold">
          <span className="text-primary [&>svg]:size-5">{icon}</span>
          {title}
        </h2>
        <Link to={to} className="app-button-ghost app-button-sm">
          {t("guild.viewAll")}
        </Link>
      </div>
      {items.length ? (
        <div className="space-y-2">{items.slice(0, 5)}</div>
      ) : (
        <div className="rounded-xl bg-surface p-4 text-sm text-content-muted">
          <Sparkles className="mb-2 size-5 text-primary" />
          {empty}
        </div>
      )}
    </section>
  );
}
function Row({ title, meta }: { title: string; meta: string }) {
  return (
    <div className="flex items-center justify-between gap-3 rounded-xl bg-surface px-3 py-2">
      <strong className="min-w-0 truncate text-sm">{title}</strong>
      <span className="shrink-0 text-xs text-content-muted">{meta}</span>
    </div>
  );
}
function HuntRow({ item }: { item: GuildHunt }) {
  const { i18n } = useTranslation();
  return (
    <Row
      title={`${item.target} · ${item.location}`}
      meta={new Date(item.scheduled_at).toLocaleString(appLocale(i18n.resolvedLanguage || i18n.language), {
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      })}
    />
  );
}
