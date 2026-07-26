import { FormEvent, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import AutomaticRaffleDraw from "../../components/raffle/AutomaticRaffleDraw";
import TestRunChecklist, {
  TestChecklistKey,
} from "../../components/raffle/TestRunChecklist";
import { useAuth } from "../../context/AuthContext";
import { useConfirmation } from "../../context/ConfirmationContext";
import {
  AutomaticRun,
  EligibilityPreview,
  Raffle,
  raffleApi,
} from "../../services/raffle";
import {
  InternalNotification,
  notificationApi,
  SchedulerHealth,
} from "../../services/notifications";

export function wallTimeToUtc(value: string, timeZone: string): string {
  if (!value) return "";
  const [date, time] = value.split("T");
  const [year, month, day] = date.split("-").map(Number);
  const [hour, minute] = time.split(":").map(Number);
  const target = Date.UTC(year, month - 1, day, hour, minute);
  let guess = target;
  for (let iteration = 0; iteration < 2; iteration += 1) {
    const parts = new Intl.DateTimeFormat("en-US", {
      timeZone,
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      hourCycle: "h23",
    }).formatToParts(new Date(guess));
    const part = (type: Intl.DateTimeFormatPartTypes) =>
      Number(parts.find((entry) => entry.type === type)?.value);
    const represented = Date.UTC(
      part("year"),
      part("month") - 1,
      part("day"),
      part("hour"),
      part("minute"),
    );
    guess = target - (represented - guess);
  }
  return new Date(guess).toISOString();
}

export default function AutomaticRaffleOperations({
  guildName,
  compact = false,
}: {
  guildName?: string;
  compact?: boolean;
}) {
  const { t, i18n } = useTranslation();
  const { user } = useAuth();
  const confirmation = useConfirmation();
  const [raffles, setRaffles] = useState<Raffle[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [preview, setPreview] = useState<EligibilityPreview | null>(null);
  const [runs, setRuns] = useState<AutomaticRun[]>([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [purpose, setPurpose] = useState<"test" | "real">("test");
  const [title, setTitle] = useState("");
  const guild = (guildName || user?.guild_name || "").trim();
  const [timezone, setTimezone] = useState("America/Chicago");
  const [schedule, setSchedule] = useState("");
  const [confirmedReal, setConfirmedReal] = useState(false);
  const [confirmedCreation, setConfirmedCreation] = useState(false);
  const [eligibilityDays, setEligibilityDays] = useState(5);
  const [showParticipants, setShowParticipants] = useState(false);
  const [secondAmount, setSecondAmount] = useState(100);
  const [firstAmount, setFirstAmount] = useState(250);
  const [prizeCurrency, setPrizeCurrency] = useState("TC");
  const [rerunPositions, setRerunPositions] = useState<
    Array<"second" | "first">
  >([]);
  const [rerunReason, setRerunReason] = useState("");
  const [testCharacter, setTestCharacter] = useState("");
  const [overrideReason, setOverrideReason] = useState("");
  const [retryReason, setRetryReason] = useState("");
  const [cleanupReason, setCleanupReason] = useState("");
  const [cleanupSummary, setCleanupSummary] = useState<{
    participant_associations_removed: number;
    users_modified: number;
    guilds_modified: number;
    real_raffles_modified: number;
  } | null>(null);
  const [schedulerHealth, setSchedulerHealth] =
    useState<SchedulerHealth | null>(null);
  const [notifications, setNotifications] = useState<InternalNotification[]>(
    [],
  );
  const [rerunOverride, setRerunOverride] = useState(false);
  const [rerunOverrideReason, setRerunOverrideReason] = useState("");
  const [manualChecklist, setManualChecklist] = useState<
    Partial<Record<TestChecklistKey, boolean>>
  >({});

  const selected = raffles.find((raffle) => raffle.id === selectedId) || null;
  const successfulRuns = runs.filter((run) => run.state === "succeeded");
  const latestRun = successfulRuns[successfulRuns.length - 1];
  let scheduledUtc = "";
  try {
    scheduledUtc = wallTimeToUtc(schedule, timezone);
  } catch {
    scheduledUtc = "";
  }
  const scheduledLocal = scheduledUtc
    ? new Intl.DateTimeFormat(i18n.language, {
        dateStyle: "full",
        timeStyle: "short",
        timeZone: timezone,
      }).format(new Date(scheduledUtc))
    : "—";

  const load = async (target?: number) => {
    const data = (await raffleApi.list()).filter(
      (raffle) =>
        raffle.run_mode === "automatic" &&
        raffle.purpose !== "legacy" &&
        (!guild ||
          raffle.guild_name.toLocaleLowerCase() === guild.toLocaleLowerCase()),
    );
    setRaffles(data);
    setSelectedId(target ?? selectedId ?? data[0]?.id ?? null);
  };
  useEffect(() => {
    void load().catch(() => setError(t("raffle.operations.errors.load")));
  }, []);
  useEffect(() => {
    if (!selectedId) {
      setRuns([]);
      return;
    }
    void raffleApi
      .runs(selectedId)
      .then(setRuns)
      .catch(() => setError(t("raffle.operations.errors.load")));
  }, [selectedId, selected?.current_run_number]);
  useEffect(() => {
    if (!user?.is_superuser) return;
    let active = true;
    const refreshOperations = async () => {
      try {
        const [health, items] = await Promise.all([
          notificationApi.schedulerHealth(),
          notificationApi.list(),
        ]);
        if (active) {
          setSchedulerHealth(health);
          setNotifications(items);
        }
      } catch {
        /* operational status remains unavailable */
      }
    };
    void refreshOperations();
    const timer = window.setInterval(refreshOperations, 15000);
    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, [user?.is_superuser]);

  const create = async (event: FormEvent) => {
    event.preventDefault();
    setError("");
    if (!confirmedCreation) {
      setError(t("raffle.testRun.errors.confirmCreation"));
      return;
    }
    if (purpose === "real" && !confirmedReal) {
      setError(t("raffle.operations.errors.confirmReal"));
      return;
    }
    if (!scheduledUtc || new Date(scheduledUtc) <= new Date()) {
      setError(t("raffle.operations.errors.future"));
      return;
    }
    if (!(secondAmount > 0) || !(firstAmount > 0) || !prizeCurrency.trim()) {
      setError(t("raffle.workspace.wizard.invalidPrizes"));
      return;
    }
    setBusy(true);
    try {
      const prizes = [
        {
          name: t("raffle.operations.secondPlace"),
          reward: `${secondAmount} ${prizeCurrency.trim().toUpperCase()}`,
          order_index: 1,
          position: "second" as const,
          amount: secondAmount,
          currency: prizeCurrency.trim().toUpperCase(),
        },
        {
          name: t("raffle.operations.firstPlace"),
          reward: `${firstAmount} ${prizeCurrency.trim().toUpperCase()}`,
          order_index: 2,
          position: "first" as const,
          amount: firstAmount,
          currency: prizeCurrency.trim().toUpperCase(),
        },
      ];
      const created = await raffleApi.create({
        title,
        guild_name: guild,
        access_mode: "guild_only",
        show_participants: showParticipants,
        prizes,
        purpose,
        run_mode: "automatic",
        scheduled_run_at: scheduledUtc,
        timezone_name: timezone,
        eligibility_days: eligibilityDays,
      });
      await load(created.id);
      setTitle("");
      setSchedule("");
      setConfirmedReal(false);
      setConfirmedCreation(false);
    } catch {
      setError(t("raffle.operations.errors.create"));
    } finally {
      setBusy(false);
    }
  };

  const refreshSelected = async () => {
    if (!selectedId) return;
    const fresh = await raffleApi.get(selectedId);
    setRaffles((rows) =>
      rows.map((row) => (row.id === fresh.id ? fresh : row)),
    );
    setRuns(await raffleApi.runs(selectedId));
  };
  const performRerun = async () => {
    if (
      !selected ||
      rerunPositions.length === 0 ||
      rerunReason.trim().length < 3
    )
      return;
    setBusy(true);
    try {
      await raffleApi.rerunAutomatic(
        selected.id,
        rerunPositions,
        rerunReason,
        rerunOverride,
        rerunOverrideReason,
      );
      await refreshSelected();
      setRerunPositions([]);
      setRerunReason("");
      setRerunOverride(false);
      setRerunOverrideReason("");
      setManualChecklist((values) => ({ ...values, reruns: true }));
    } catch {
      setError(t("raffle.operations.errors.rerun"));
    } finally {
      setBusy(false);
    }
  };
  const canPublish = Boolean(
    user?.is_superuser ||
    ["leader", "guild leader"].includes((user?.guild_rank || "").toLowerCase()),
  );
  const stale =
    preview &&
    Date.now() - new Date(preview.cutoff_at).getTime() > 60 * 60 * 1000;
  const raffleNotifications = selected
    ? notifications.filter((item) => item.raffle_id === selected.id)
    : [];
  const checklist: Record<TestChecklistKey, boolean> = {
    schedulerHealthy: Boolean(
      schedulerHealth?.enabled &&
      schedulerHealth.heartbeat_at &&
      Date.now() - new Date(schedulerHealth.heartbeat_at).getTime() < 120000,
    ),
    snapshotFrozen: Boolean(preview?.persisted),
    participantsEligible: Boolean(preview && preview.eligible_count >= 2),
    drawOnce: successfulRuns.length === 1,
    secondReveal: Boolean(manualChecklist.secondReveal),
    firstReveal: Boolean(manualChecklist.firstReveal),
    reruns: Boolean(manualChecklist.reruns),
    delivery: Boolean(
      latestRun?.results.some((result) => result.delivery_status !== "pending"),
    ),
    publication: Boolean(
      manualChecklist.publication ||
      selected?.publication_status === "published",
    ),
    notifications: raffleNotifications.length > 0,
    cleanup: Boolean(cleanupSummary),
  };
  const toggleChecklist = (key: TestChecklistKey) =>
    setManualChecklist((values) => ({ ...values, [key]: !values[key] }));

  return (
    <div className="space-y-6">
      {!compact && (
        <header>
          <h1 className="text-2xl font-bold text-content-primary">
            {t("raffle.operations.title")}
          </h1>
          <p className="text-content-secondary">
            {t("raffle.operations.subtitle")}
          </p>
        </header>
      )}
      {error && (
        <div
          role="alert"
          className="rounded-xl border border-danger/40 bg-danger/15 p-3 text-danger"
        >
          {error}
        </div>
      )}
      {!compact && (
        <form
          onSubmit={create}
          className="grid gap-3 rounded-2xl border border-line bg-surface-base/70 p-5 md:grid-cols-2"
        >
          <h2 className="md:col-span-2 flex items-center gap-2 text-lg font-semibold">
            {t("raffle.operations.prepare")}{" "}
            {purpose === "test" && (
              <span className="rounded-full bg-accent/20 px-3 py-1 text-xs text-accent">
                {t("raffle.operations.testLabel")}
              </span>
            )}
          </h2>
          <label>
            {t("raffle.operations.purpose")}
            <select
              value={purpose}
              onChange={(e) => setPurpose(e.target.value as "test" | "real")}
              className="mt-1 w-full rounded-lg bg-surface-base p-2"
            >
              <option value="test">{t("raffle.operations.test")}</option>
              <option value="real">{t("raffle.operations.real")}</option>
            </select>
          </label>
          <label>
            {t("raffle.operations.guild")}
            <input
              value={guild}
              readOnly
              aria-readonly="true"
              className="mt-1 w-full rounded-lg border border-line bg-surface-base/60 p-2 text-content-secondary"
            />
          </label>
          <label>
            {t("raffle.operations.name")}
            <input
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              required
              className="mt-1 w-full rounded-lg bg-surface-base p-2"
            />
          </label>
          <label>
            {t("raffle.operations.timezone")}
            <input
              value={timezone}
              onChange={(e) => setTimezone(e.target.value)}
              required
              className="mt-1 w-full rounded-lg bg-surface-base p-2"
            />
          </label>
          <label>
            {t("raffle.operations.localSchedule")}
            <input
              type="datetime-local"
              value={schedule}
              onChange={(e) => setSchedule(e.target.value)}
              required
              className="mt-1 w-full rounded-lg bg-surface-base p-2"
            />
          </label>
          <label>
            {t("raffle.testRun.eligibilityDays")}
            <input
              type="number"
              min={1}
              max={30}
              value={eligibilityDays}
              onChange={(e) => setEligibilityDays(Number(e.target.value))}
              className="mt-1 w-full rounded-lg bg-surface-base p-2"
            />
          </label>
          <label className="flex items-center gap-2 rounded-lg border border-line p-3">
            <input
              type="checkbox"
              checked={showParticipants}
              onChange={(e) => setShowParticipants(e.target.checked)}
            />
            {t("raffle.testRun.participantVisibility")}
          </label>
          <div className="rounded-lg border border-line p-3 text-sm">
            <p>
              {t("raffle.operations.localEquivalent", {
                value: scheduledLocal,
              })}
            </p>
            <p>
              {t("raffle.operations.utcEquivalent", {
                value: scheduledUtc || "—",
              })}
            </p>
          </div>
          <div className="md:col-span-2 rounded-xl border border-primary/20 p-3 text-sm text-content-secondary">
            {t("raffle.operations.rules")}
          </div>
          <div className="md:col-span-2 grid gap-3 sm:grid-cols-[1fr_1fr_8rem]">
            <label>
              {t("raffle.operations.secondPlace")}
              <input
                type="number"
                min="0.01"
                step="0.01"
                value={secondAmount}
                onChange={(event) =>
                  setSecondAmount(Number(event.target.value))
                }
                required
                className="mt-1 w-full rounded-lg bg-surface-base p-2"
              />
            </label>
            <label>
              {t("raffle.operations.firstPlace")}
              <input
                type="number"
                min="0.01"
                step="0.01"
                value={firstAmount}
                onChange={(event) => setFirstAmount(Number(event.target.value))}
                required
                className="mt-1 w-full rounded-lg bg-surface-base p-2"
              />
            </label>
            <label>
              {t("raffle.workspace.fields.currency")}
              <input
                value={prizeCurrency}
                onChange={(event) => setPrizeCurrency(event.target.value)}
                required
                maxLength={20}
                className="mt-1 w-full rounded-lg bg-surface-base p-2 uppercase"
              />
            </label>
          </div>
          {purpose === "real" && (
            <label className="md:col-span-2 flex gap-2">
              <input
                type="checkbox"
                checked={confirmedReal}
                onChange={(e) => setConfirmedReal(e.target.checked)}
              />
              {t("raffle.operations.confirmReal")}
            </label>
          )}
          <label className="md:col-span-2 flex gap-2">
            <input
              type="checkbox"
              checked={confirmedCreation}
              onChange={(e) => setConfirmedCreation(e.target.checked)}
            />
            {t("raffle.testRun.confirmCreation")}
          </label>
          <p className="md:col-span-2 text-sm text-content-secondary">
            {t("raffle.testRun.deliveryNotice")}
          </p>
          <button
            disabled={busy}
            className="md:col-span-2 rounded-lg bg-primary p-2 font-bold text-content-inverse"
          >
            {t("raffle.operations.save")}
          </button>
          <p className="md:col-span-2 text-xs text-content-muted">
            {t("raffle.operations.fridayExample")}
          </p>
        </form>
      )}

      <section className="grid gap-4 lg:grid-cols-[280px_1fr]">
        <div className="space-y-2">
          {raffles.map((raffle) => (
            <button
              key={raffle.id}
              onClick={() => {
                setSelectedId(raffle.id);
                setPreview(null);
              }}
              className={`block w-full rounded-xl border p-3 text-left ${selectedId === raffle.id ? "border-primary" : "border-line"}`}
            >
              <span className="font-semibold">{raffle.title}</span>
              {raffle.purpose === "test" && (
                <span className="ml-2 rounded bg-accent/20 px-2 text-xs">
                  {t("raffle.operations.testLabel")}
                </span>
              )}
              <small className="block text-content-secondary">
                {t(`raffle.operations.execution.${raffle.execution_state}`)}
              </small>
            </button>
          ))}
        </div>
        {selected && (
          <div className="space-y-5 rounded-2xl border border-line p-5">
            <div className="grid gap-3 sm:grid-cols-3">
              <div>
                {t("raffle.operations.scheduledLocal")}
                <strong className="block">
                  {selected.scheduled_run_at
                    ? new Intl.DateTimeFormat(i18n.language, {
                        dateStyle: "medium",
                        timeStyle: "short",
                        timeZone: selected.timezone_name,
                      }).format(new Date(selected.scheduled_run_at))
                    : "—"}
                </strong>
              </div>
              <div>
                {t("raffle.operations.scheduledUtc")}
                <strong className="block">
                  {selected.scheduled_run_at || "—"}
                </strong>
              </div>
              <div>
                {t("raffle.operations.retryState")}
                <strong className="block">{selected.retry_count}</strong>
              </div>
            </div>
            {selected.purpose === "test" && (
              <div className="grid gap-2 rounded-xl border border-accent/30 p-3 text-sm sm:grid-cols-3">
                <div>
                  {t("raffle.testRun.scheduler")}
                  <strong className="block">
                    {schedulerHealth?.enabled
                      ? t("raffle.testRun.enabled")
                      : t("raffle.testRun.disabled")}
                  </strong>
                </div>
                <div>
                  {t("raffle.testRun.heartbeat")}
                  <strong className="block">
                    {schedulerHealth?.heartbeat_at
                      ? new Date(schedulerHealth.heartbeat_at).toLocaleString()
                      : t("raffle.testRun.unavailable")}
                  </strong>
                </div>
                <div>
                  {t("raffle.testRun.jobState")}
                  <strong className="block">
                    {t(
                      `raffle.operations.execution.${selected.execution_state}`,
                    )}
                  </strong>
                  <span className="text-xs text-content-muted">
                    {selected.scheduler_job_id ||
                      t("raffle.testRun.notClaimed")}
                  </span>
                </div>
              </div>
            )}
            {selected.purpose === "test" && (
              <div className="rounded-xl border border-line p-3 text-sm">
                <span>
                  {t("raffle.testRun.publicState")}:{" "}
                  <strong>
                    {t(
                      `raffle.testRun.${selected.publication_status === "published" ? "published" : "private"}`,
                    )}
                  </strong>
                </span>
                <a
                  className="ml-3 text-info underline"
                  href={`/raffles/${selected.public_code}`}
                  target="_blank"
                  rel="noreferrer"
                >
                  {t("raffle.testRun.publicLink")}
                </a>
              </div>
            )}
            {selected.last_error_summary && (
              <div className="rounded-lg border border-danger/30 p-3">
                {t("raffle.operations.lastFailure")}:{" "}
                {selected.last_error_summary}
              </div>
            )}
            {selected.purpose === "test" &&
              selected.execution_state === "failed" &&
              user?.is_superuser && (
                <div className="flex gap-2">
                  <input
                    value={retryReason}
                    onChange={(e) => setRetryReason(e.target.value)}
                    placeholder={t("raffle.testRun.retryReason")}
                    className="min-w-0 flex-1 rounded-lg bg-surface-base p-2"
                  />
                  <button
                    onClick={async () => {
                      if (retryReason.trim().length < 3) return;
                      await raffleApi.retryTest(selected.id, retryReason);
                      setRetryReason("");
                      await refreshSelected();
                    }}
                    className="rounded-lg border border-primary/50 px-3 py-2"
                  >
                    {t("raffle.testRun.retry")}
                  </button>
                </div>
              )}
            <div className="flex flex-wrap gap-2">
              <button
                onClick={async () =>
                  setPreview(await raffleApi.previewEligibility(selected.id))
                }
                className="rounded-lg border border-line px-3 py-2"
              >
                {t("raffle.operations.preview")}
              </button>
              <button
                onClick={async () =>
                  setPreview(await raffleApi.freezeEligibility(selected.id))
                }
                className="rounded-lg border border-line px-3 py-2"
              >
                {t("raffle.operations.freeze")}
              </button>
            </div>
            {selected.purpose === "test" && (
              <div className="flex gap-2">
                <input
                  value={testCharacter}
                  onChange={(e) => setTestCharacter(e.target.value)}
                  placeholder={t("raffle.operations.testCharacter")}
                  className="min-w-0 flex-1 rounded-lg bg-surface-base p-2"
                />
                <button
                  onClick={async () => {
                    if (!testCharacter.trim()) return;
                    await raffleApi.addManualParticipant(
                      selected.id,
                      testCharacter.trim(),
                    );
                    setTestCharacter("");
                    await refreshSelected();
                  }}
                  className="rounded-lg border border-accent/50 px-3 py-2"
                >
                  {t("raffle.operations.addTestParticipant")}
                </button>
              </div>
            )}
            {selected.purpose === "test" &&
              selected.participants.length > 0 && (
                <div className="space-y-2">
                  <h3 className="font-semibold">
                    {t("raffle.testRun.testParticipants")}
                  </h3>
                  <input
                    value={overrideReason}
                    onChange={(e) => setOverrideReason(e.target.value)}
                    placeholder={t("raffle.testRun.overrideReason")}
                    className="w-full rounded-lg bg-surface-base p-2"
                  />
                  {selected.participants.map((participant) => (
                    <div
                      key={participant.id}
                      className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-line p-3"
                    >
                      <div>
                        <strong>{participant.character_name}</strong>
                        <span className="ml-2 rounded bg-accent/20 px-2 text-xs text-accent">
                          {t("raffle.testRun.testParticipant")}
                        </span>
                        {participant.eligibility_override != null && (
                          <small className="block text-content-secondary">
                            {t("raffle.testRun.overrideActive", {
                              value: participant.eligibility_override
                                ? t("common.yes")
                                : t("common.no"),
                            })}
                          </small>
                        )}
                      </div>
                      <div className="flex gap-2">
                        {user?.is_superuser && !preview?.persisted && (
                          <>
                            <button
                              onClick={async () => {
                                if (overrideReason.trim().length < 3) return;
                                await raffleApi.overrideTestEligibility(
                                  selected.id,
                                  participant.id,
                                  true,
                                  overrideReason,
                                );
                                await refreshSelected();
                              }}
                              className="rounded border border-success/50 px-2 py-1 text-xs"
                            >
                              {t("raffle.testRun.forceEligible")}
                            </button>
                            <button
                              onClick={async () => {
                                if (overrideReason.trim().length < 3) return;
                                await raffleApi.overrideTestEligibility(
                                  selected.id,
                                  participant.id,
                                  false,
                                  overrideReason,
                                );
                                await refreshSelected();
                              }}
                              className="rounded border border-primary/50 px-2 py-1 text-xs"
                            >
                              {t("raffle.testRun.forceExcluded")}
                            </button>
                          </>
                        )}
                        <button
                          onClick={async () => {
                            if (
                              !(await confirmation.confirm(
                                t("raffle.testRun.removeParticipantConfirm"),
                                { danger: true },
                              ))
                            )
                              return;
                            await raffleApi.removeParticipant(
                              selected.id,
                              participant.id,
                            );
                            await refreshSelected();
                          }}
                          className="rounded border border-danger/50 px-2 py-1 text-xs"
                        >
                          {t("raffle.testRun.removeAssociation")}
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            {preview && (
              <div className="rounded-xl bg-surface-base p-4">
                <p>
                  {t("raffle.operations.eligibleCount", {
                    count: preview.eligible_count,
                  })}{" "}
                  ·{" "}
                  {t("raffle.operations.excludedCount", {
                    count: preview.excluded_count,
                  })}
                </p>
                <p className="text-xs text-content-secondary">
                  {t("raffle.operations.snapshotAt", {
                    value: preview.cutoff_at,
                  })}
                </p>
                {stale && (
                  <p className="text-primary">
                    {t("raffle.operations.staleWarning")}
                  </p>
                )}
                <ul className="mt-2 text-sm">
                  {preview.entries
                    .filter((entry) => !entry.is_eligible)
                    .map((entry, index) => (
                      <li key={`${entry.character_name}-${index}`}>
                        {entry.character_name || "—"} — {entry.exclusion_code}
                      </li>
                    ))}
                </ul>
              </div>
            )}
            {latestRun && (
              <>
                <div className="rounded-xl border border-info/30 p-3 text-info">
                  {t("raffle.operations.privateReview")}
                </div>
                <AutomaticRaffleDraw
                  results={latestRun.results}
                  participantNames={selected.participants.map(
                    (entry) => entry.character_name,
                  )}
                  testMode={selected.purpose === "test"}
                />
                <div className="space-y-2">
                  {latestRun.results.map((result) => {
                    const overdue =
                      result.delivery_status === "pending" &&
                      new Date(result.delivery_deadline_at) < new Date();
                    return (
                      <div
                        key={result.id}
                        className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-line p-3"
                      >
                        <div>
                          <span>
                            {result.character_name} · {result.amount}{" "}
                            {result.currency} ·{" "}
                            {t(
                              `raffle.operations.delivery.${result.delivery_status}`,
                            )}
                          </span>
                          {overdue && (
                            <strong className="ml-2 text-danger">
                              {t("raffle.testRun.overdue")}
                            </strong>
                          )}
                          <small className="block text-content-muted">
                            {t("raffle.testRun.deadline")}:{" "}
                            {new Date(
                              result.delivery_deadline_at,
                            ).toLocaleString()}
                          </small>
                          {result.delivered_at && (
                            <small className="block text-content-muted">
                              {t("raffle.testRun.deliveredAt")}:{" "}
                              {new Date(result.delivered_at).toLocaleString()} ·{" "}
                              {result.delivered_by_name}
                            </small>
                          )}
                          {result.delivery_note && (
                            <small className="block text-content-muted">
                              {t("raffle.testRun.note")}: {result.delivery_note}
                            </small>
                          )}
                          {result.delivery_history &&
                            result.delivery_history.length > 0 && (
                              <details className="mt-2 text-xs text-content-secondary">
                                <summary className="cursor-pointer">
                                  {t("raffle.workspace.deliveryHistory")}
                                </summary>
                                {result.delivery_history.map((entry, index) => (
                                  <p
                                    key={`${entry.created_at}-${index}`}
                                    className="mt-1"
                                  >
                                    {new Date(
                                      entry.created_at,
                                    ).toLocaleString()}{" "}
                                    · {entry.actor} ·{" "}
                                    {t(
                                      `raffle.operations.delivery.${entry.new_status}`,
                                    )}
                                    {entry.note ? ` · ${entry.note}` : ""}
                                  </p>
                                ))}
                              </details>
                            )}
                        </div>
                        <select
                          value={result.delivery_status}
                          onChange={async (e) => {
                            await raffleApi.updateDelivery(
                              selected.id,
                              result.id,
                              e.target.value as typeof result.delivery_status,
                              e.target.value === "disputed" ||
                                e.target.value === "cancelled"
                                ? t("raffle.operations.delivery.managerNote")
                                : undefined,
                            );
                            await refreshSelected();
                          }}
                          className="rounded bg-surface-base p-2"
                        >
                          <option value="pending">
                            {t("raffle.operations.delivery.pending")}
                          </option>
                          <option value="delivered">
                            {t("raffle.operations.delivery.delivered")}
                          </option>
                          <option value="disputed">
                            {t("raffle.operations.delivery.disputed")}
                          </option>
                          <option value="cancelled">
                            {t("raffle.operations.delivery.cancelled")}
                          </option>
                        </select>
                      </div>
                    );
                  })}
                </div>
                {canPublish && (
                  <div className="flex gap-2">
                    <button
                      onClick={async () => {
                        await raffleApi.publish(selected.id);
                        setManualChecklist((values) => ({
                          ...values,
                          publication: true,
                        }));
                        await refreshSelected();
                      }}
                      className="rounded-lg bg-success px-3 py-2"
                    >
                      {t("raffle.operations.publish")}
                    </button>
                    <button
                      onClick={async () => {
                        await raffleApi.unpublish(selected.id);
                        setManualChecklist((values) => ({
                          ...values,
                          publication: true,
                        }));
                        await refreshSelected();
                      }}
                      className="rounded-lg border border-line px-3 py-2"
                    >
                      {t("raffle.operations.unpublish")}
                    </button>
                  </div>
                )}
                <div className="space-y-2 rounded-xl border border-line p-4">
                  <h3>{t("raffle.operations.rerunTitle")}</h3>
                  {(["second", "first"] as const).map((position) => (
                    <label key={position} className="mr-4">
                      <input
                        type="checkbox"
                        checked={rerunPositions.includes(position)}
                        onChange={() =>
                          setRerunPositions((values) =>
                            values.includes(position)
                              ? values.filter((value) => value !== position)
                              : [...values, position],
                          )
                        }
                      />{" "}
                      {t(`raffle.operations.${position}Place`)}
                    </label>
                  ))}
                  <input
                    value={rerunReason}
                    onChange={(e) => setRerunReason(e.target.value)}
                    placeholder={t("raffle.operations.rerunReason")}
                    className="block w-full rounded bg-surface-base p-2"
                  />
                  {user?.is_superuser && (
                    <>
                      <label className="flex gap-2 text-sm">
                        <input
                          type="checkbox"
                          checked={rerunOverride}
                          onChange={(e) => setRerunOverride(e.target.checked)}
                        />
                        {t("raffle.testRun.deliveredOverride")}
                      </label>
                      {rerunOverride && (
                        <input
                          value={rerunOverrideReason}
                          onChange={(e) =>
                            setRerunOverrideReason(e.target.value)
                          }
                          placeholder={t(
                            "raffle.testRun.deliveredOverrideReason",
                          )}
                          className="block w-full rounded bg-surface-base p-2"
                        />
                      )}
                    </>
                  )}
                  <p className="text-sm text-primary">
                    {t("raffle.operations.rerunWarning")}
                  </p>
                  <button
                    disabled={busy}
                    onClick={performRerun}
                    className="rounded bg-primary px-3 py-2 text-content-inverse"
                  >
                    {t("raffle.operations.rerun")}
                  </button>
                </div>
              </>
            )}
            {selected.purpose === "test" && (
              <TestRunChecklist
                values={checklist}
                manualKeys={["secondReveal", "firstReveal"]}
                onToggle={toggleChecklist}
              />
            )}
            {selected.purpose === "test" && (
              <div className="space-y-2 rounded-xl border border-line p-4">
                <h3 className="font-semibold">
                  {t("raffle.testRun.notificationsTitle")}
                </h3>
                {raffleNotifications.length === 0 && (
                  <p className="text-sm text-content-secondary">
                    {t("raffle.testRun.notificationsEmpty")}
                  </p>
                )}
                {raffleNotifications.map((notification) => (
                  <div
                    key={notification.id}
                    className="flex items-start justify-between gap-3 rounded-lg bg-surface-base p-3 text-sm"
                  >
                    <div>
                      <strong>
                        {t(notification.title_key, notification.interpolation)}
                      </strong>
                      <p className="text-content-secondary">
                        {t(
                          notification.message_key,
                          notification.interpolation,
                        )}
                      </p>
                    </div>
                    {!notification.is_read && (
                      <button
                        onClick={async () => {
                          await notificationApi.markRead(notification.id);
                          setNotifications((items) =>
                            items.map((item) =>
                              item.id === notification.id
                                ? { ...item, is_read: true }
                                : item,
                            ),
                          );
                        }}
                        className="shrink-0 rounded border border-line px-2 py-1"
                      >
                        {t("raffle.testRun.markRead")}
                      </button>
                    )}
                  </div>
                ))}
              </div>
            )}
            {selected.purpose === "test" && (
              <div className="space-y-2 rounded-xl border border-danger/20 p-4">
                <h3 className="font-semibold">
                  {t("raffle.testRun.cleanupTitle")}
                </h3>
                <p className="text-sm text-content-secondary">
                  {t("raffle.testRun.cleanupWarning")}
                </p>
                <input
                  value={cleanupReason}
                  onChange={(e) => setCleanupReason(e.target.value)}
                  placeholder={t("raffle.testRun.cleanupReason")}
                  className="w-full rounded bg-surface-base p-2"
                />
                <button
                  onClick={async () => {
                    if (
                      cleanupReason.trim().length < 3 ||
                      !(await confirmation.confirm(
                        t("raffle.testRun.cleanupConfirm"),
                        { danger: true },
                      ))
                    )
                      return;
                    const summary = await raffleApi.cleanupTest(
                      selected.id,
                      cleanupReason,
                    );
                    setCleanupSummary(summary);
                    await refreshSelected();
                  }}
                  className="rounded border border-danger/50 px-3 py-2"
                >
                  {t("raffle.testRun.cleanup")}
                </button>
                {cleanupSummary && (
                  <p className="text-sm text-success">
                    {t("raffle.testRun.cleanupSummary", cleanupSummary)}
                  </p>
                )}
              </div>
            )}
          </div>
        )}
      </section>
    </div>
  );
}
