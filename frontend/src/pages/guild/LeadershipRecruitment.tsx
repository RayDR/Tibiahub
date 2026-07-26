import {
  FormEvent,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { Link } from "react-router-dom";
import {
  AlertCircle,
  CalendarClock,
  ChevronRight,
  Plus,
  Search,
  Users,
  Vote,
} from "lucide-react";
import { useTranslation } from "react-i18next";
import { useAuth } from "../../context/AuthContext";
import {
  EmptyState,
  MobileSectionTabs,
  WorkspaceHeader,
} from "../../components/workspace/WorkspacePrimitives";
import {
  InlineError,
  LeadershipBreadcrumbs,
  LeadershipSkeleton,
  StatusChip,
} from "../../components/leadership/LeadershipPrimitives";
import {
  LeadershipApplication,
  LeadershipOpening,
  LeadershipSummary,
  leadershipApi,
} from "../../services/leadership";

const statuses = [
  "all",
  "applied",
  "under_review",
  "more_information_requested",
  "interview",
  "voting",
  "accepted",
  "rejected",
];
export default function LeadershipRecruitment({
  guildKey,
  guildName,
}: {
  guildKey?: string;
  guildName?: string;
}) {
  const { t } = useTranslation();
  const { user } = useAuth();
  const [summary, setSummary] = useState<LeadershipSummary | null>(null);
  const [openings, setOpenings] = useState<LeadershipOpening[]>([]);
  const [applications, setApplications] = useState<LeadershipApplication[]>([]);
  const [errors, setErrors] = useState({
    summary: false,
    openings: false,
    applications: false,
  });
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState("all");
  const [search, setSearch] = useState("");
  const [sort, setSort] = useState<"newest" | "oldest">("newest");
  const [showOpening, setShowOpening] = useState(false);
  const [applying, setApplying] = useState<LeadershipOpening | null>(null);
  const root = guildKey
    ? `/admin/guilds/${encodeURIComponent(guildKey)}/leadership`
    : "/guild/leadership";
  const load = useCallback(async () => {
    setLoading(true);
    const summaryResult = await Promise.allSettled([
      leadershipApi.summary(guildKey),
      leadershipApi.openings(guildKey),
    ]);
    const nextSummary =
      summaryResult[0].status === "fulfilled" ? summaryResult[0].value : null;
    if (nextSummary) setSummary(nextSummary);
    if (summaryResult[1].status === "fulfilled")
      setOpenings(summaryResult[1].value);
    const apps = nextSummary?.capabilities.review
      ? leadershipApi.applications(guildKey)
      : guildKey
        ? Promise.resolve([])
        : leadershipApi.mine();
    const appResult = await Promise.allSettled([apps]);
    if (appResult[0].status === "fulfilled")
      setApplications(appResult[0].value);
    setErrors({
      summary: summaryResult[0].status === "rejected",
      openings: summaryResult[1].status === "rejected",
      applications: appResult[0].status === "rejected",
    });
    setLoading(false);
  }, [guildKey]);
  useEffect(() => {
    void load();
  }, [load]);
  const visible = useMemo(
    () =>
      applications
        .filter(
          (item) =>
            (filter === "all" || item.status === filter) &&
            item.character_name
              .toLocaleLowerCase()
              .includes(search.trim().toLocaleLowerCase()),
        )
        .sort(
          (a, b) =>
            (sort === "newest" ? -1 : 1) *
            (new Date(a.submitted_at).getTime() -
              new Date(b.submitted_at).getTime()),
        ),
    [applications, filter, search, sort],
  );
  const counts = useMemo(
    () =>
      Object.fromEntries(
        statuses.map((status) => [
          status,
          status === "all"
            ? applications.length
            : applications.filter((item) => item.status === status).length,
        ]),
      ),
    [applications],
  );
  if (loading && !summary) return <LeadershipSkeleton cards={5} />;
  if (errors.summary && !summary)
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
  return (
    <div className="space-y-5">
      <LeadershipBreadcrumbs
        adminBase={
          guildKey ? `/admin/guilds/${encodeURIComponent(guildKey)}` : undefined
        }
      />
      <WorkspaceHeader
        title={t("leadership.recruitment.title")}
        subtitle={guildName || summary?.guild_name}
        action={
          summary?.capabilities.manage ? (
            <button
              onClick={() => setShowOpening((value) => !value)}
              className="inline-flex min-h-11 items-center justify-center gap-2 rounded-lg bg-primary px-4 font-semibold text-content-inverse"
            >
              <Plus className="h-4 w-4" />
              {t("leadership.openings.create")}
            </button>
          ) : undefined
        }
      />
      {showOpening && (
        <OpeningForm
          guildKey={guildKey}
          onDone={() => {
            setShowOpening(false);
            void load();
          }}
        />
      )}
      {errors.openings && <InlineError retry={() => void load()} />}
      <section
        aria-labelledby="leadership-openings-title"
        className="space-y-3"
      >
        <div className="flex items-end justify-between gap-3">
          <div>
            <h2
              id="leadership-openings-title"
              className="text-xl font-semibold"
            >
              {t("leadership.openings.sectionTitle")}
            </h2>
            <p className="text-sm text-content-secondary">
              {t("leadership.openings.sectionHelp")}
            </p>
          </div>
          <span className="rounded-full bg-primary-subtle px-3 py-1 text-sm font-semibold text-primary">
            {t("leadership.openings.countVisible", { count: openings.length })}
          </span>
        </div>
        <OpeningList
          openings={openings}
          applications={summary?.capabilities.review ? [] : applications}
          character={user?.tibia_character_name || ""}
          root={root}
          canManage={Boolean(summary?.capabilities.manage)}
          onApply={setApplying}
          onAction={async (id, action) => {
            await leadershipApi.openingAction(id, action, guildKey);
            await load();
          }}
        />
      </section>
      {summary?.capabilities.review && (
        <section
          aria-labelledby="leadership-applications-title"
          className="space-y-3"
        >
          <div>
            <h2
              id="leadership-applications-title"
              className="text-xl font-semibold"
            >
              {t("leadership.applications.sectionTitle")}
            </h2>
            <p className="text-sm text-content-secondary">
              {t("leadership.applications.sectionHelp")}
            </p>
          </div>
          <section className="sticky top-20 z-10 space-y-3 rounded-xl border border-line bg-surface-base/95 p-3 backdrop-blur">
            <div className="grid gap-2 sm:grid-cols-[1fr_auto]">
              <label className="relative">
                <span className="sr-only">
                  {t("leadership.pipeline.search")}
                </span>
                <Search
                  aria-hidden
                  className="absolute left-3 top-3.5 h-4 w-4 text-content-muted"
                />
                <input
                  value={search}
                  onChange={(event) => setSearch(event.target.value)}
                  placeholder={t("leadership.pipeline.search")}
                  className="min-h-11 w-full rounded-lg bg-surface-base pl-9 pr-3"
                />
              </label>
              <label className="flex items-center gap-2 text-sm">
                <span>{t("leadership.pipeline.sort")}</span>
                <select
                  value={sort}
                  onChange={(event) =>
                    setSort(event.target.value as "newest" | "oldest")
                  }
                  className="min-h-11 rounded-lg bg-surface-base px-3"
                >
                  <option value="newest">
                    {t("leadership.pipeline.newest")}
                  </option>
                  <option value="oldest">
                    {t("leadership.pipeline.oldest")}
                  </option>
                </select>
              </label>
            </div>
            <MobileSectionTabs
              active={filter}
              onChange={setFilter}
              tabs={statuses.map((id) => ({
                id,
                label: `${t(`leadership.status.${id}`)} (${counts[id] || 0})`,
              }))}
            />
          </section>
          {errors.applications ? (
            <InlineError retry={() => void load()} />
          ) : visible.length === 0 ? (
            <EmptyState
              title={t("leadership.pipeline.empty")}
              description={t("leadership.pipeline.emptyHelp")}
            />
          ) : (
            <div className="grid gap-3 lg:grid-cols-2">
              {visible.map((item) => (
                <CandidateCard
                  key={item.id}
                  item={item}
                  to={`${root}/recruitment/applications/${item.id}`}
                />
              ))}
            </div>
          )}
        </section>
      )}
      {applying && (
        <ApplicationForm
          opening={applying}
          character={user?.tibia_character_name || ""}
          onCancel={() => setApplying(null)}
          onDone={() => {
            setApplying(null);
            void load();
          }}
        />
      )}
    </div>
  );
}

function CandidateCard({
  item,
  to,
}: {
  item: LeadershipApplication;
  to: string;
}) {
  const { t } = useTranslation();
  const profile = item.profile || {};
  const next = item.valid_actions?.[0];
  return (
    <Link
      to={to}
      className="group flex min-h-32 items-start justify-between gap-3 rounded-xl border border-line p-4 focus:outline-none focus:ring-2 focus:ring-primary"
    >
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <h2 className="max-w-full truncate font-semibold">
            {item.character_name}
          </h2>
          <StatusChip status={item.status} />
        </div>
        <p className="mt-2 text-sm text-content-secondary">
          {profile.level ?? t("leadership.common.unknown")} ·{" "}
          {profile.vocation ?? t("leadership.common.unknown")}
        </p>
        <p className="mt-1 text-xs text-content-muted">
          {t("leadership.pipeline.submitted", {
            date: new Date(item.submitted_at).toLocaleDateString(),
          })}
        </p>
        <div className="mt-3 flex flex-wrap gap-2 text-xs">
          {item.messages.some(
            (message) => message.audience !== "reviewers",
          ) && (
            <span className="rounded-full bg-info-subtle px-2 py-1 text-info">
              {t("leadership.pipeline.applicantMessage")}
            </span>
          )}
          {item.status === "voting" && (
            <span className="inline-flex items-center gap-1 rounded-full bg-accent-subtle px-2 py-1 text-accent">
              <Vote className="h-3 w-3" />
              {t("leadership.pipeline.voteRequested")}
            </span>
          )}
          {next && (
            <span className="rounded-full bg-surface px-2 py-1">
              {t(`leadership.nextActions.${next}`)}
            </span>
          )}
        </div>
      </div>
      <ChevronRight aria-hidden className="mt-1 h-5 w-5 shrink-0" />
    </Link>
  );
}

function OpeningList({
  openings,
  applications,
  character,
  root,
  canManage,
  onApply,
  onAction,
}: {
  openings: LeadershipOpening[];
  applications: LeadershipApplication[];
  character: string;
  root: string;
  canManage: boolean;
  onApply: (opening: LeadershipOpening) => void;
  onAction: (
    id: number,
    action: "open" | "pause" | "close" | "archive",
  ) => Promise<void>;
}) {
  const { t } = useTranslation();
  const [busy, setBusy] = useState<number | null>(null);
  const items = canManage
    ? openings
    : openings.filter((item) => item.status === "open");
  const actions = (
    status: LeadershipOpening["status"],
  ): Array<"open" | "pause" | "close" | "archive"> =>
    status === "draft"
      ? ["open"]
      : status === "open"
        ? ["pause", "close"]
        : status === "paused"
          ? ["open", "close"]
          : status === "closed"
            ? ["archive"]
            : [];
  return (
    <div className="space-y-4">
      {applications.map((item) => (
        <Link
          key={item.id}
          to={`${root}/recruitment/applications/${item.id}`}
          className="block rounded-xl border border-info p-4"
        >
          <span className="text-xs text-info">
            {t("leadership.applications.yours")}
          </span>
          <div className="mt-1 flex items-center justify-between gap-3">
            <h2 className="truncate font-semibold">{item.character_name}</h2>
            <StatusChip status={item.status} />
          </div>
          {item.status === "more_information_requested" && (
            <p className="mt-2 text-sm text-primary">
              {t("leadership.applications.informationPending")}
            </p>
          )}
        </Link>
      ))}
      {items.map((item) => (
        <article
          key={item.id}
          className="rounded-2xl bg-surface-raised p-4 shadow-sm"
        >
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <p className="text-xs uppercase tracking-wide text-primary">
                  {t(`leadership.roles.${item.role_code}`)}
                </p>
                <StatusChip status={item.status} />
              </div>
              <h3 className="truncate text-lg font-semibold">{item.title}</h3>
              <p className="mt-1 text-sm text-content-secondary">
                {item.description}
              </p>
            </div>
            <Users className="h-5 w-5 shrink-0 text-primary" />
          </div>
          <dl className="mt-4 grid gap-3 text-sm sm:grid-cols-2">
            <div>
              <dt className="font-semibold">
                {t("leadership.openings.responsibilities")}
              </dt>
              <dd className="mt-1 whitespace-pre-line text-content-secondary">
                {item.responsibilities}
              </dd>
            </div>
            <div>
              <dt className="font-semibold">
                {t("leadership.openings.requirements")}
              </dt>
              <dd className="mt-1 whitespace-pre-line text-content-secondary">
                {item.requirements}
              </dd>
            </div>
          </dl>
          <div className="mt-4 grid gap-2 rounded-xl bg-surface-base p-3 text-xs text-content-secondary sm:grid-cols-3">
            <span>
              {t("leadership.openings.available", {
                count: Math.max(0, item.openings_count - item.filled_count),
              })}
            </span>
            <span>
              {item.application_deadline
                ? t("leadership.openings.deadline", {
                    date: new Date(item.application_deadline).toLocaleString(),
                  })
                : t("leadership.openings.noDeadline")}
            </span>
            <span>
              {item.voting_enabled
                ? t("leadership.openings.votingEnabled")
                : t("leadership.openings.votingDisabled")}
            </span>
          </div>
          <div className="mt-3 flex items-center gap-2 text-xs text-content-secondary">
            <CalendarClock className="h-4 w-4" />
            {t("leadership.openings.process")}
          </div>
          {canManage ? (
            <div className="mt-4 flex flex-wrap gap-2">
              {actions(item.status).map((action) => (
                <button
                  key={action}
                  disabled={busy === item.id}
                  onClick={async () => {
                    setBusy(item.id);
                    try {
                      await onAction(item.id, action);
                    } finally {
                      setBusy(null);
                    }
                  }}
                  className="min-h-11 rounded-lg border border-line px-4 font-semibold hover:border-primary"
                >
                  {t(`leadership.openings.actions.${action}`)}
                </button>
              ))}
            </div>
          ) : (
            <button
              disabled={
                !character ||
                applications.some(
                  (application) =>
                    application.opening_id === item.id &&
                    [
                      "applied",
                      "under_review",
                      "more_information_requested",
                      "interview",
                      "voting",
                    ].includes(application.status),
                )
              }
              onClick={() => onApply(item)}
              className="mt-4 min-h-11 w-full rounded-lg bg-primary font-semibold text-content-inverse disabled:cursor-not-allowed disabled:opacity-50"
            >
              {t("leadership.applications.apply")}
            </button>
          )}
        </article>
      ))}
      {items.length === 0 && applications.length === 0 && (
        <EmptyState
          title={t("leadership.openings.empty")}
          description={t("leadership.openings.emptyHelp")}
        />
      )}
    </div>
  );
}

function OpeningForm({
  guildKey,
  onDone,
}: {
  guildKey?: string;
  onDone: () => void;
}) {
  const { t } = useTranslation();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(false);
  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (busy) return;
    setBusy(true);
    setError(false);
    const form = new FormData(event.currentTarget);
    try {
      await leadershipApi.createOpening(
        {
          title: form.get("title"),
          description: form.get("description"),
          responsibilities: form.get("responsibilities"),
          requirements: form.get("requirements"),
          openings_count: Number(form.get("count")),
          allow_viceleader_review: form.get("review") === "on",
          voting_enabled: form.get("voting") === "on",
          votes_required: 1,
          target_count: 4,
        },
        guildKey,
      );
      onDone();
    } catch {
      setError(true);
      setBusy(false);
    }
  };
  return (
    <form
      onSubmit={submit}
      className="grid gap-3 rounded-xl border border-primary/20 p-4"
    >
      <h2 className="font-semibold">{t("leadership.openings.create")}</h2>
      {(
        ["title", "description", "responsibilities", "requirements"] as const
      ).map((key) => (
        <label key={key} className="grid gap-1 text-sm">
          <span>
            {t(`leadership.openings.${key === "title" ? "titleField" : key}`)}
          </span>
          {key === "title" ? (
            <input
              name="title"
              required
              minLength={3}
              className="min-h-11 rounded-lg bg-surface-base px-3"
            />
          ) : (
            <textarea
              name={key}
              required={key !== "description"}
              minLength={key === "description" ? undefined : 10}
              defaultValue={
                key === "responsibilities" || key === "requirements"
                  ? t(
                      `leadership.openings.default${key[0].toUpperCase()}${key.slice(1)}`,
                    )
                  : undefined
              }
              className="min-h-28 rounded-lg bg-surface-base p-3"
            />
          )}
        </label>
      ))}
      <label className="grid gap-1 text-sm">
        <span>{t("leadership.openings.count")}</span>
        <input
          name="count"
          type="number"
          min={1}
          max={20}
          defaultValue={1}
          className="min-h-11 rounded-lg bg-surface-base px-3"
        />
      </label>
      <label className="flex min-h-11 items-center gap-3">
        <input name="review" type="checkbox" defaultChecked />
        {t("leadership.openings.allowReview")}
      </label>
      <label className="flex min-h-11 items-center gap-3">
        <input name="voting" type="checkbox" />
        {t("leadership.openings.enableVoting")}
      </label>
      {error && (
        <p role="alert" className="text-sm text-danger">
          {t("leadership.errors.action")}
        </p>
      )}
      <button
        disabled={busy}
        className="min-h-11 rounded-lg bg-primary font-semibold text-content-inverse"
      >
        {busy ? t("leadership.actions.saving") : t("leadership.actions.save")}
      </button>
    </form>
  );
}

function ApplicationForm({
  opening,
  character,
  onCancel,
  onDone,
}: {
  opening: LeadershipOpening;
  character: string;
  onCancel: () => void;
  onDone: () => void;
}) {
  const { t } = useTranslation();
  const first = useRef<HTMLTextAreaElement>(null);
  const [answers, setAnswers] = useState({
    why_apply: "",
    contribution: "",
    availability: "",
    leadership_experience: "",
  });
  const [conduct, setConduct] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const dirty = Object.values(answers).some(Boolean) || conduct;
  useEffect(() => {
    first.current?.focus();
    const handler = (event: BeforeUnloadEvent) => {
      if (dirty) {
        event.preventDefault();
        event.returnValue = "";
      }
    };
    window.addEventListener("beforeunload", handler);
    return () => window.removeEventListener("beforeunload", handler);
  }, [dirty]);
  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (busy) return;
    setBusy(true);
    setError("");
    try {
      await leadershipApi.apply(opening.id, {
        character_name: character,
        ...answers,
        conduct_agreed: conduct,
      });
      onDone();
    } catch {
      setError(t("leadership.errors.submit"));
      setBusy(false);
    }
  };
  return (
    <div
      role="presentation"
      className="fixed inset-0 z-modal flex items-end bg-surface-base/70 sm:items-center sm:justify-center"
    >
      <form
        role="dialog"
        aria-modal="true"
        aria-labelledby="application-title"
        onSubmit={submit}
        className="max-h-[92dvh] w-full overflow-y-auto rounded-t-2xl bg-surface-base p-4 pb-[max(1rem,env(safe-area-inset-bottom))] sm:max-w-2xl sm:rounded-2xl"
      >
        <h2 id="application-title" className="text-lg font-semibold">
          {t("leadership.applications.formTitle")}
        </h2>
        <section className="mt-3 rounded-lg bg-surface-base p-3 text-sm">
          <h3 className="font-semibold">
            {t("leadership.applications.automaticProfile")}
          </h3>
          <p className="mt-1">
            <strong>{character}</strong>
          </p>
          <p className="text-content-secondary">
            {t("leadership.applications.profileNotice")}
          </p>
        </section>
        <section aria-labelledby="application-questions" className="mt-4">
          <h3 id="application-questions" className="font-semibold">
            {t("leadership.applications.questions")}
          </h3>
          {(
            [
              "why_apply",
              "contribution",
              "availability",
              "leadership_experience",
            ] as const
          ).map((key, index) => (
            <label key={key} className="mt-4 block text-sm">
              <span>{t(`leadership.questions.${key}`)}</span>
              <span className="mt-1 block text-xs text-content-muted">
                {t(`leadership.helpers.${key}`)}
              </span>
              <textarea
                ref={index === 0 ? first : undefined}
                value={answers[key]}
                onChange={(event) =>
                  setAnswers((value) => ({
                    ...value,
                    [key]: event.target.value,
                  }))
                }
                minLength={
                  key === "availability" || key === "leadership_experience"
                    ? 5
                    : 20
                }
                maxLength={2000}
                required
                aria-describedby={`${key}-count`}
                className="mt-2 min-h-28 w-full resize-y rounded-lg bg-surface-base p-3"
              />
              <span id={`${key}-count`} className="text-xs text-content-muted">
                {t("leadership.applications.characterCount", {
                  count: answers[key].length,
                  max: 2000,
                })}
              </span>
            </label>
          ))}
        </section>
        <label className="mt-4 flex items-start gap-3 rounded-lg border border-line p-3 text-sm">
          <input
            type="checkbox"
            checked={conduct}
            onChange={(event) => setConduct(event.target.checked)}
            required
            className="mt-1"
          />
          <span>{t("leadership.conduct.text")}</span>
        </label>
        {error && (
          <p role="alert" className="mt-3 text-sm text-danger">
            <AlertCircle className="mr-1 inline h-4 w-4" />
            {error}
          </p>
        )}
        <div className="sticky bottom-0 mt-4 flex gap-2 bg-surface-base py-2 pb-[env(safe-area-inset-bottom)]">
          <button
            type="button"
            onClick={onCancel}
            className="min-h-11 flex-1 rounded-lg border border-line"
          >
            {t("leadership.actions.cancel")}
          </button>
          <button
            disabled={busy}
            className="min-h-11 flex-1 rounded-lg bg-primary font-semibold text-content-inverse"
          >
            {busy
              ? t("leadership.actions.submitting")
              : t("leadership.actions.submit")}
          </button>
        </div>
      </form>
    </div>
  );
}
