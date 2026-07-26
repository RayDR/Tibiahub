import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  AlertTriangle,
  CheckCircle2,
  ClipboardList,
  Clock3,
  ShieldCheck,
  UserCheck,
  Users,
  Vote,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { useTranslation } from "react-i18next";
import {
  EmptyState,
  WorkspaceHeader,
} from "../../components/workspace/WorkspacePrimitives";
import {
  InlineError,
  LeadershipBreadcrumbs,
  LeadershipSkeleton,
  StatusChip,
} from "../../components/leadership/LeadershipPrimitives";
import {
  LeadershipAssignment,
  LeadershipSummary,
  leadershipApi,
} from "../../services/leadership";
import { useConfirmation } from "../../context/ConfirmationContext";

export default function Leadership({
  guildKey,
  guildName,
}: {
  guildKey?: string;
  guildName?: string;
}) {
  const { t } = useTranslation();
  const confirmation = useConfirmation();
  const [data, setData] = useState<LeadershipSummary | null>(null);
  const [assignments, setAssignments] = useState<LeadershipAssignment[]>([]);
  const [summaryError, setSummaryError] = useState(false);
  const [assignmentError, setAssignmentError] = useState(false);
  const [loading, setLoading] = useState(true);
  const root = guildKey
    ? `/admin/guilds/${encodeURIComponent(guildKey)}/leadership`
    : "/guild/leadership";
  const load = useCallback(async () => {
    setLoading(true);
    const [summaryResult, assignmentResult] = await Promise.allSettled([
      leadershipApi.summary(guildKey),
      leadershipApi.assignments(guildKey),
    ]);
    if (summaryResult.status === "fulfilled") {
      setData(summaryResult.value);
      setSummaryError(false);
    } else setSummaryError(true);
    if (assignmentResult.status === "fulfilled") {
      setAssignments(assignmentResult.value);
      setAssignmentError(false);
    } else setAssignmentError(true);
    setLoading(false);
  }, [guildKey]);
  useEffect(() => {
    void load();
  }, [load]);
  if (loading && !data) return <LeadershipSkeleton cards={6} />;
  if (summaryError && !data)
    return (
      <EmptyState
        title={t("leadership.errors.load")}
        description={t("leadership.errors.offline")}
        action={
          <button
            onClick={() => void load()}
            className="min-h-11 rounded-lg border border-line px-4"
          >
            {t("leadership.actions.retry")}
          </button>
        }
      />
    );
  if (!data) return null;
  const cards: Array<[string, number, LucideIcon]> = [
    ["active", data.active_viceleaders, ShieldCheck],
    ["recommended", data.recommended_minimum, Users],
    ["target", data.target_count, UserCheck],
    ["positions", data.open_positions, ClipboardList],
  ];
  const attention: Array<[string, number, LucideIcon]> = data.capabilities
    .review
    ? [
        [
          "applicants",
          data.applications_requiring_attention ?? 0,
          ClipboardList,
        ],
        ["interviews", data.interviews_pending, Clock3],
        ["voting", data.applications_voting, Vote],
        ...(data.capabilities.manage
          ? ([
              ["promotions", data.pending_promotions ?? 0, CheckCircle2],
            ] as Array<[string, number, LucideIcon]>)
          : []),
      ]
    : [];
  const primaryLabel = data.capabilities.manage
    ? data.active_applicants
      ? t("leadership.actions.reviewCandidates")
      : t("leadership.actions.createRecruitment")
    : data.capabilities.review
      ? t("leadership.actions.reviewCandidates")
      : data.own_application_id
        ? t("leadership.actions.viewApplication")
        : t("leadership.actions.viewOpportunity");
  const primaryTo =
    data.own_application_id && !data.capabilities.review
      ? `${root}/recruitment/applications/${data.own_application_id}`
      : `${root}/recruitment`;
  const completePromotion = async (item: LeadershipAssignment) => {
    if (!(await confirmation.confirm(t("leadership.confirmations.promotion")))) return;
    await leadershipApi.promotion(item.id, true, undefined, guildKey);
    await load();
  };
  const endAssignment = async (item: LeadershipAssignment) => {
    const reason = await confirmation.prompt(
      t("leadership.confirmations.endAssignment"),
      { inputLabel: t("leadership.confirmations.endAssignmentReason"), minimumLength: 3, danger: true },
    );
    if (!reason) return;
    await leadershipApi.endAssignment(item.id, reason, guildKey);
    await load();
  };
  return (
    <div className="space-y-5">
      <LeadershipBreadcrumbs
        adminBase={
          guildKey ? `/admin/guilds/${encodeURIComponent(guildKey)}` : undefined
        }
      />
      <WorkspaceHeader
        title={t("leadership.title")}
        subtitle={guildName || data.guild_name}
        badge={t("leadership.roles.viceleader")}
        action={
          <Link
            to={primaryTo}
            className="inline-flex min-h-11 items-center justify-center rounded-lg bg-primary px-4 font-semibold text-content-inverse"
          >
            {primaryLabel}
          </Link>
        }
      />
      {summaryError && <InlineError retry={() => void load()} />}
      <section aria-labelledby="leadership-health">
        <h2 id="leadership-health" className="mb-3 text-lg font-semibold">
          {t("leadership.dashboard.health")}
        </h2>
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          {cards.map(([key, value, Icon]) => (
            <article key={key} className="rounded-xl border border-line p-4">
              <Icon aria-hidden className="h-5 w-5 text-primary" />
              <strong className="mt-3 block text-2xl">{value}</strong>
              <span className="text-xs text-content-secondary">
                {t(`leadership.summary.${key}`)}
              </span>
            </article>
          ))}
        </div>
      </section>
      {data.below_recommended && (
        <section className="rounded-xl border border-primary/30 bg-primary/10 p-4">
          <div className="flex gap-3">
            <AlertTriangle
              aria-hidden
              className="h-5 w-5 shrink-0 text-primary"
            />
            <div>
              <h2 className="font-semibold">{t("leadership.warning.title")}</h2>
              <p className="mt-1 text-sm text-content-secondary">
                {t("leadership.warning.explanation")}
              </p>
              <p className="mt-2 text-xs text-content-secondary">
                {t("leadership.warning.metrics", {
                  active: data.active_viceleaders,
                  recommended: data.recommended_minimum,
                  target: data.target_count,
                  positions: data.open_positions,
                })}
              </p>
              <Link
                to={`${root}/recruitment`}
                className="mt-3 inline-flex min-h-11 items-center rounded-lg border border-primary/40 px-4 text-sm text-primary"
              >
                {primaryLabel}
              </Link>
            </div>
          </div>
        </section>
      )}
      {attention.length > 0 && (
        <section aria-labelledby="leadership-attention">
          <div className="mb-3 flex items-center justify-between">
            <h2 id="leadership-attention" className="text-lg font-semibold">
              {t("leadership.dashboard.attention")}
            </h2>
            <Link className="text-sm text-primary" to={`${root}/recruitment`}>
              {t("leadership.actions.openPipeline")}
            </Link>
          </div>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {attention.map(([key, value, Icon]) => (
              <Link
                key={key}
                to={`${root}/recruitment`}
                className="flex min-h-24 items-center gap-3 rounded-xl border border-line p-4 focus:outline-none focus:ring-2 focus:ring-primary"
              >
                <Icon aria-hidden className="h-5 w-5 text-info" />
                <div>
                  <strong className="block text-xl">{value}</strong>
                  <span className="text-xs text-content-secondary">
                    {t(`leadership.summary.${key}`)}
                  </span>
                </div>
              </Link>
            ))}
          </div>
        </section>
      )}
      <section aria-labelledby="leadership-assignments">
        <h2 id="leadership-assignments" className="mb-3 text-lg font-semibold">
          {t("leadership.dashboard.assignments")}
        </h2>
        {assignmentError ? (
          <InlineError retry={() => void load()} />
        ) : assignments.length === 0 ? (
          <p className="rounded-xl border border-dashed border-line p-6 text-center text-sm text-content-secondary">
            {t("leadership.assignment.empty")}
          </p>
        ) : (
          <div className="grid gap-3 sm:grid-cols-2">
            {assignments.map((item) => (
              <article
                key={item.id}
                className="rounded-xl border border-line p-4"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <h3 className="truncate font-semibold">
                      {item.character_name}
                    </h3>
                    <p className="text-sm text-content-secondary">
                      {t(`leadership.roles.${item.role_code}`)}
                    </p>
                  </div>
                  <StatusChip status={item.is_active ? "active" : "ended"} />
                </div>
                <p className="mt-3 text-xs text-content-muted">
                  {t("leadership.assignment.started", {
                    date: new Date(item.started_at).toLocaleDateString(),
                  })}
                </p>
                <p className="mt-1 text-sm">
                  {t(`leadership.assignment.${item.in_game_promotion_status}`)}
                </p>
                {data.capabilities.manage && item.is_active && (
                  <div className="mt-3 flex flex-wrap gap-2">
                    {item.in_game_promotion_status === "pending" && (
                      <button
                        onClick={() => void completePromotion(item)}
                        className="min-h-11 rounded-lg border border-success px-3 text-sm text-success"
                      >
                        {t("leadership.assignment.markCompleted")}
                      </button>
                    )}
                    <button
                      onClick={() => void endAssignment(item)}
                      className="min-h-11 rounded-lg border border-line px-3 text-sm"
                    >
                      {t("leadership.assignment.end")}
                    </button>
                  </div>
                )}
              </article>
            ))}
          </div>
        )}
      </section>
      <section className="rounded-xl border border-line p-4">
        <h2 className="font-semibold">
          {t("leadership.assignment.manualTitle")}
        </h2>
        <p className="mt-2 text-sm text-content-secondary">
          {t("leadership.assignment.manualNotice")}
        </p>
      </section>
    </div>
  );
}
