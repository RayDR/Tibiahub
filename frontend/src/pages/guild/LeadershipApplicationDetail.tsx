import { FormEvent, useCallback, useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import {
  CalendarClock,
  CheckCircle2,
  ClipboardCheck,
  Clock3,
  MessageSquare,
  ShieldCheck,
  Vote,
} from "lucide-react";
import {
  AssistanceBanner,
  EmptyState,
  WorkspaceHeader,
} from "../../components/workspace/WorkspacePrimitives";
import {
  InlineError,
  LeadershipBreadcrumbs,
  LeadershipSkeleton,
  LeadershipTimeline,
  SectionCard,
  StatusChip,
} from "../../components/leadership/LeadershipPrimitives";
import {
  LeadershipAction,
  LeadershipApplication,
  LeadershipSummary,
  leadershipApi,
} from "../../services/leadership";
import { useConfirmation } from "../../context/ConfirmationContext";

export default function LeadershipApplicationDetail({
  admin = false,
}: {
  admin?: boolean;
}) {
  const { t } = useTranslation();
  const confirmation = useConfirmation();
  const params = useParams();
  const guildKey = admin ? params.guildKey : undefined;
  const id = Number(params.applicationId);
  const [application, setApplication] = useState<LeadershipApplication | null>(
    null,
  );
  const [summary, setSummary] = useState<LeadershipSummary | null>(null);
  const [errors, setErrors] = useState({ application: false, summary: false });
  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState(false);
  const live = useRef<HTMLDivElement>(null);
  const adminBase = guildKey
    ? `/admin/guilds/${encodeURIComponent(guildKey)}`
    : undefined;
  const load = useCallback(async () => {
    const [appResult, summaryResult] = await Promise.allSettled([
      leadershipApi.application(id, guildKey),
      leadershipApi.summary(guildKey),
    ]);
    if (appResult.status === "fulfilled") setApplication(appResult.value);
    if (summaryResult.status === "fulfilled") setSummary(summaryResult.value);
    setErrors({
      application: appResult.status === "rejected",
      summary: summaryResult.status === "rejected",
    });
  }, [id, guildKey]);
  useEffect(() => {
    void load();
  }, [load]);
  const action = async (work: () => Promise<unknown>) => {
    if (busy) return;
    setBusy(true);
    setActionError(false);
    try {
      await work();
      await load();
      live.current?.focus();
    } catch {
      setActionError(true);
    } finally {
      setBusy(false);
    }
  };
  if (!application && !errors.application)
    return <LeadershipSkeleton cards={6} />;
  if (errors.application && !application)
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
  if (!application) return null;
  const reviewer = Boolean(application.answers);
  const manager = Boolean(summary?.capabilities.manage);
  const applicantActions = application.valid_actions || [];
  const reasonAction = async (target: "rejected" | "cancelled") => {
    const reason = await confirmation.prompt(t(`leadership.confirmations.${target}`), { inputLabel: t(`leadership.confirmations.${target}Reason`), minimumLength: 3, danger: true });
    if (!reason) return Promise.resolve();
    return action(() =>
      target === "rejected"
        ? leadershipApi.decision(application.id, "rejected", reason, guildKey)
        : leadershipApi.status(application.id, "cancelled", reason, guildKey),
    );
  };
  return (
    <div className="space-y-4 pb-24 sm:pb-4">
      {admin && summary && <AssistanceBanner guildName={summary.guild_name} />}
      <LeadershipBreadcrumbs
        candidate={application.character_name}
        adminBase={adminBase}
      />
      <WorkspaceHeader
        title={application.character_name}
        subtitle={application.opening_title}
        badge={t(`leadership.status.${application.status}`)}
        action={
          <Link
            to={`${adminBase || "/guild"}/leadership/recruitment`}
            className="inline-flex min-h-11 items-center rounded-lg border border-line px-4"
          >
            {t("leadership.actions.backToPipeline")}
          </Link>
        }
      />
      {errors.summary && <InlineError retry={() => void load()} />}
      <div ref={live} tabIndex={-1} aria-live="polite" className="sr-only">
        {busy
          ? t("leadership.actions.updating")
          : t(`leadership.status.${application.status}`)}
      </div>
      {actionError && (
        <p
          role="alert"
          className="rounded-lg border border-danger p-3 text-sm text-danger"
        >
          {t("leadership.errors.action")}
        </p>
      )}
      <div className="grid gap-4 xl:grid-cols-[minmax(0,2fr)_minmax(18rem,1fr)]">
        <main className="space-y-4">
          <SectionCard
            title={t("leadership.applications.summary")}
            icon={<ShieldCheck className="h-5 w-5" />}
          >
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {Object.entries(application.profile || {})
                .filter(([, value]) => value !== null && value !== "")
                .map(([key, value]) => (
                  <div key={key} className="min-w-0">
                    <span className="block text-xs text-content-muted">
                      {t(`leadership.fields.${key}`)}
                    </span>
                    <strong className="block truncate">{String(value)}</strong>
                  </div>
                ))}
            </div>
            <div className="flex flex-wrap gap-2">
              <StatusChip status={application.status} />
              <span className="rounded-full border border-line px-2.5 py-1 text-xs">
                {t("leadership.conduct.accepted")} ·{" "}
                {new Date(application.conduct_agreed_at).toLocaleDateString()}
              </span>
            </div>
          </SectionCard>
          {reviewer && application.answers && (
            <SectionCard
              title={t("leadership.applications.answers")}
              icon={<ClipboardCheck className="h-5 w-5" />}
            >
              {Object.entries(application.answers)
                .filter(([, value]) => value)
                .map(([key, value]) => (
                  <div key={key} className="rounded-lg bg-surface-base p-3">
                    <h3 className="text-sm font-semibold">
                      {t(`leadership.questions.${key}`)}
                    </h3>
                    <p className="mt-1 whitespace-pre-wrap text-sm text-content-secondary">
                      {value}
                    </p>
                  </div>
                ))}
            </SectionCard>
          )}
          <SectionCard
            title={t("leadership.applications.timeline")}
            icon={<Clock3 className="h-5 w-5" />}
          >
            <LeadershipTimeline history={application.history} />
          </SectionCard>
          <SectionCard
            title={t("leadership.applications.communication")}
            icon={<MessageSquare className="h-5 w-5" />}
          >
            {application.messages
              .filter((item) => item.audience !== "reviewers")
              .map((item) => (
                <Message key={item.id} item={item} />
              ))}
            {(applicantActions.includes("reply") || reviewer) && (
              <MessageForm
                busy={busy}
                onSubmit={(body) =>
                  action(() =>
                    leadershipApi.message(
                      application.id,
                      {
                        audience: reviewer ? "applicant" : "reviewers",
                        message_type: reviewer
                          ? "information_request"
                          : "applicant_reply",
                        body,
                      },
                      guildKey,
                    ),
                  )
                }
              />
            )}
          </SectionCard>
          {reviewer && (
            <SectionCard
              title={t("leadership.applications.internal")}
              icon={<ShieldCheck className="h-5 w-5" />}
            >
              {application.messages
                .filter((item) => item.audience === "reviewers")
                .map((item) => (
                  <Message key={item.id} item={item} />
                ))}
              <MessageForm
                busy={busy}
                onSubmit={(body) =>
                  action(() =>
                    leadershipApi.message(
                      application.id,
                      {
                        audience: "reviewers",
                        message_type: "internal_comment",
                        body,
                      },
                      guildKey,
                    ),
                  )
                }
              />
            </SectionCard>
          )}
          {(application.interview ||
            application.valid_actions.includes("schedule_interview")) && (
            <InterviewSection
              application={application}
              manager={manager}
              busy={busy}
              guildKey={guildKey}
              run={action}
            />
          )}
          {reviewer && application.vote_summary && (
            <VoteSection
              application={application}
              busy={busy}
              guildKey={guildKey}
              run={action}
            />
          )}
          {application.status === "accepted" && (
            <Onboarding
              application={application}
              manager={manager}
              busy={busy}
              guildKey={guildKey}
              run={action}
            />
          )}
        </main>
        <aside className="space-y-3 xl:sticky xl:top-24 xl:self-start">
          <SectionCard title={t("leadership.applications.nextActions")}>
            <ActionList
              actions={application.valid_actions}
              busy={busy}
              run={action}
              application={application}
              guildKey={guildKey}
              reasonAction={reasonAction}
            />
            {application.valid_actions.length === 0 && (
              <p className="text-sm text-content-secondary">
                {t("leadership.actions.noneAvailable")}
              </p>
            )}
          </SectionCard>
          {reviewer && !manager && (
            <p className="rounded-xl border border-line p-3 text-xs text-content-secondary">
              {t("leadership.votes.leaderAuthority")}
            </p>
          )}
        </aside>
      </div>
      <div className="fixed inset-x-0 bottom-0 z-20 border-t border-line bg-surface-base/95 p-2 pb-[max(.5rem,env(safe-area-inset-bottom))] xl:hidden">
        <div className="mx-auto flex max-w-3xl gap-2 overflow-x-auto">
          {application.valid_actions
            .filter((name) =>
              [
                "withdraw",
                "start_review",
                "request_information",
                "return_to_review",
                "start_voting",
                "accept",
                "reject",
                "cancel",
              ].includes(name),
            )
            .slice(0, 3)
            .map((actionName) => (
              <QuickAction
                key={actionName}
                name={actionName}
                disabled={busy}
                onClick={() =>
                  void executeSimple(
                    actionName,
                    application,
                    guildKey,
                    action,
                    reasonAction,
                    t,
                    confirmation.confirm,
                  )
                }
              />
            ))}
        </div>
      </div>
    </div>
  );
}

type Run = (work: () => Promise<unknown>) => Promise<void>;
async function executeSimple(
  name: LeadershipAction,
  app: LeadershipApplication,
  guildKey: string | undefined,
  run: Run,
  reasonAction: (target: "rejected" | "cancelled") => Promise<void>,
  t: (key: string) => string,
  askConfirm: (message: string) => Promise<boolean>,
) {
  if (name === "withdraw") return run(() => leadershipApi.withdraw(app.id));
  if (name === "start_review" || name === "return_to_review")
    return run(() =>
      leadershipApi.status(app.id, "under_review", undefined, guildKey),
    );
  if (name === "request_information")
    return run(() =>
      leadershipApi.status(
        app.id,
        "more_information_requested",
        undefined,
        guildKey,
      ),
    );
  if (name === "start_voting")
    return run(() =>
      leadershipApi.status(app.id, "voting", undefined, guildKey),
    );
  if (name === "accept") {
    if (!(await askConfirm(t("leadership.confirmations.accept"))))
      return Promise.resolve();
    return run(() =>
      leadershipApi.decision(app.id, "accepted", undefined, guildKey),
    );
  }
  if (name === "reject") return reasonAction("rejected");
  if (name === "cancel") return reasonAction("cancelled");
  return Promise.resolve();
}
function ActionList({
  actions,
  busy,
  run,
  application,
  guildKey,
  reasonAction,
}: {
  actions: LeadershipAction[];
  busy: boolean;
  run: Run;
  application: LeadershipApplication;
  guildKey?: string;
  reasonAction: (target: "rejected" | "cancelled") => Promise<void>;
}) {
  const { t } = useTranslation();
  const confirmation = useConfirmation();
  const direct = actions.filter((name) =>
    [
      "withdraw",
      "start_review",
      "request_information",
      "return_to_review",
      "start_voting",
      "accept",
      "reject",
      "cancel",
    ].includes(name),
  );
  return (
    <div className="grid gap-2">
      {direct.map((name) => (
        <button
          key={name}
          disabled={busy}
          onClick={() =>
            void executeSimple(
              name,
              application,
              guildKey,
              run,
              reasonAction,
              t,
              confirmation.confirm,
            )
          }
          className="min-h-11 rounded-lg border border-line px-3 text-left disabled:opacity-50"
        >
          {t(`leadership.nextActions.${name}`)}
        </button>
      ))}
    </div>
  );
}
function QuickAction({
  name,
  disabled,
  onClick,
}: {
  name: LeadershipAction;
  disabled: boolean;
  onClick: () => void;
}) {
  const { t } = useTranslation();
  return (
    <button
      disabled={disabled}
      onClick={onClick}
      className="min-h-11 shrink-0 rounded-lg bg-primary px-4 font-semibold text-content-inverse disabled:opacity-50"
    >
      {t(`leadership.nextActions.${name}`)}
    </button>
  );
}
function Message({
  item,
}: {
  item: LeadershipApplication["messages"][number];
}) {
  return (
    <article className="rounded-lg bg-surface-base p-3">
      <div className="flex flex-wrap justify-between gap-2 text-xs text-content-muted">
        <span>{item.author_name}</span>
        <time>{new Date(item.created_at).toLocaleString()}</time>
      </div>
      <p className="mt-1 whitespace-pre-wrap text-sm">{item.body}</p>
    </article>
  );
}
function MessageForm({
  onSubmit,
  busy,
}: {
  onSubmit: (body: string) => Promise<void>;
  busy: boolean;
}) {
  const { t } = useTranslation();
  const [body, setBody] = useState("");
  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (!body.trim() || busy) return;
    await onSubmit(body.trim());
    setBody("");
  };
  return (
    <form onSubmit={submit} className="grid gap-2 sm:grid-cols-[1fr_auto]">
      <label className="sr-only" htmlFor="leadership-message">
        {t("leadership.fields.message")}
      </label>
      <textarea
        id="leadership-message"
        value={body}
        onChange={(event) => setBody(event.target.value)}
        required
        minLength={2}
        maxLength={5000}
        className="min-h-24 resize-y rounded-lg bg-surface-base p-3"
      />
      <button
        disabled={busy}
        className="min-h-11 self-end rounded-lg bg-primary px-4 font-semibold text-content-inverse"
      >
        {t("leadership.actions.send")}
      </button>
    </form>
  );
}
function InterviewSection({
  application,
  manager,
  busy,
  guildKey,
  run,
}: {
  application: LeadershipApplication;
  manager: boolean;
  busy: boolean;
  guildKey?: string;
  run: Run;
}) {
  const { t } = useTranslation();
  const interview = application.interview;
  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    await run(() =>
      leadershipApi.interview(
        application.id,
        {
          scheduled_at: new Date(
            String(form.get("scheduled_at")),
          ).toISOString(),
          timezone: form.get("timezone"),
          meeting_location: form.get("location"),
          interview_notes: form.get("notes"),
          completed: false,
        },
        guildKey,
      ),
    );
  };
  return (
    <SectionCard
      title={t("leadership.applications.interview")}
      icon={<CalendarClock className="h-5 w-5" />}
    >
      {interview && (
        <div className="rounded-lg bg-surface-base p-3">
          <p className="font-medium">
            {new Date(interview.scheduled_at).toLocaleString()}
          </p>
          <p className="text-sm text-content-secondary">
            {interview.timezone} · {interview.meeting_location}
          </p>
          <p className="mt-1 text-xs text-content-muted">
            {interview.completed_at
              ? t("leadership.interview.completed")
              : t("leadership.interview.scheduled")}
            {interview.organizer ? ` · ${interview.organizer}` : ""}
          </p>
          {manager && interview.internal_notes && (
            <p className="mt-2 whitespace-pre-wrap text-sm">
              {interview.internal_notes}
            </p>
          )}
        </div>
      )}
      {manager && application.valid_actions.includes("schedule_interview") && (
        <form onSubmit={submit} className="grid gap-3">
          <label className="grid gap-1 text-sm">
            {t("leadership.fields.dateTime")}
            <input
              name="scheduled_at"
              type="datetime-local"
              required
              className="min-h-11 rounded-lg bg-surface-base px-3"
            />
          </label>
          <label className="grid gap-1 text-sm">
            {t("leadership.fields.timezone")}
            <input
              name="timezone"
              required
              defaultValue={Intl.DateTimeFormat().resolvedOptions().timeZone}
              className="min-h-11 rounded-lg bg-surface-base px-3"
            />
          </label>
          <label className="grid gap-1 text-sm">
            {t("leadership.fields.location")}
            <input
              name="location"
              required
              className="min-h-11 rounded-lg bg-surface-base px-3"
            />
          </label>
          <label className="grid gap-1 text-sm">
            {t("leadership.fields.notes")}
            <textarea
              name="notes"
              className="min-h-24 rounded-lg bg-surface-base p-3"
            />
          </label>
          <button
            disabled={busy}
            className="min-h-11 rounded-lg border border-primary px-4"
          >
            {interview
              ? t("leadership.interview.reschedule")
              : t("leadership.actions.scheduleInterview")}
          </button>
        </form>
      )}
    </SectionCard>
  );
}
function VoteSection({
  application,
  busy,
  guildKey,
  run,
}: {
  application: LeadershipApplication;
  busy: boolean;
  guildKey?: string;
  run: Run;
}) {
  const { t } = useTranslation();
  const [vote, setVote] = useState(application.current_vote || "neutral");
  const [comment, setComment] = useState(
    application.current_vote_comment || "",
  );
  return (
    <SectionCard
      title={t("leadership.applications.voting")}
      icon={<Vote className="h-5 w-5" />}
    >
      <div className="grid grid-cols-3 gap-2">
        {(["support", "neutral", "oppose"] as const).map((value) => (
          <label
            key={value}
            className={`flex min-h-16 cursor-pointer flex-col items-center justify-center rounded-lg border p-2 ${vote === value ? "border-primary bg-primary/20" : "border-line"}`}
          >
            <input
              className="sr-only"
              type="radio"
              name="vote"
              value={value}
              checked={vote === value}
              onChange={() => setVote(value)}
            />
            <strong>{application.vote_summary?.[value] ?? 0}</strong>
            <span className="text-xs">{t(`leadership.votes.${value}`)}</span>
          </label>
        ))}
      </div>
      <label className="grid gap-1 text-sm">
        {t("leadership.votes.comment")}
        <textarea
          value={comment}
          onChange={(event) => setComment(event.target.value)}
          maxLength={2000}
          className="min-h-20 rounded-lg bg-surface-base p-3"
        />
      </label>
      <button
        disabled={busy}
        onClick={() =>
          void run(() =>
            leadershipApi.vote(application.id, vote, comment, guildKey),
          )
        }
        className="min-h-11 w-full rounded-lg bg-primary font-semibold text-content-inverse"
      >
        {t("leadership.votes.save")}
      </button>
      <p className="text-xs text-content-muted">
        {t("leadership.votes.participation", {
          count: application.vote_participation || 0,
        })}
      </p>
    </SectionCard>
  );
}
function Onboarding({
  application,
  manager,
  busy,
  guildKey,
  run,
}: {
  application: LeadershipApplication;
  manager: boolean;
  busy: boolean;
  guildKey?: string;
  run: Run;
}) {
  const { t } = useTranslation();
  const confirmation = useConfirmation();
  const assignment = application.assignment;
  const [note, setNote] = useState("");
  return (
    <SectionCard
      title={t("leadership.onboarding.title")}
      icon={<CheckCircle2 className="h-5 w-5 text-success" />}
    >
      <p className="text-sm">{t("leadership.onboarding.message")}</p>
      <dl className="grid gap-2 text-sm sm:grid-cols-2">
        <div>
          <dt className="text-content-muted">
            {t("leadership.onboarding.role")}
          </dt>
          <dd>{t(`leadership.roles.${application.role_code}`)}</dd>
        </div>
        <div>
          <dt className="text-content-muted">
            {t("leadership.onboarding.acceptedAt")}
          </dt>
          <dd>
            {application.final_decision_at
              ? new Date(application.final_decision_at).toLocaleString()
              : t("leadership.common.unknown")}
          </dd>
        </div>
        <div>
          <dt className="text-content-muted">
            {t("leadership.onboarding.promotion")}
          </dt>
          <dd>
            {t(
              `leadership.assignment.${assignment?.in_game_promotion_status || "pending"}`,
            )}
          </dd>
        </div>
        {assignment?.in_game_promoted_at && (
          <div>
            <dt className="text-content-muted">
              {t("leadership.onboarding.completedAt")}
            </dt>
            <dd>{new Date(assignment.in_game_promoted_at).toLocaleString()}</dd>
          </div>
        )}
      </dl>
      {manager && assignment?.in_game_promotion_status === "pending" && (
        <div className="grid gap-2">
          <label className="grid gap-1 text-sm">
            {t("leadership.assignment.safeNote")}
            <textarea
              value={note}
              onChange={(event) => setNote(event.target.value)}
              maxLength={2000}
              className="min-h-20 rounded-lg bg-surface-base p-3"
            />
          </label>
          <button
            disabled={busy}
            onClick={async () => {
              if (await confirmation.confirm(t("leadership.confirmations.promotion")))
                void run(() =>
                  leadershipApi.promotion(assignment.id, true, note, guildKey),
                );
            }}
            className="min-h-11 rounded-lg bg-success px-4 font-semibold text-content-on-primary"
          >
            {t("leadership.assignment.markCompleted")}
          </button>
        </div>
      )}
    </SectionCard>
  );
}
