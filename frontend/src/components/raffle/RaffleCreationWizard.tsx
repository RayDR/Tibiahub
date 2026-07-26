import { FormEvent, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { raffleApi, RaffleScope } from "../../services/raffle";
import { wallTimeToUtc } from "../../pages/guild/AutomaticRaffleOperations";

export default function RaffleCreationWizard({
  guildName,
  worldName,
  isGlobalAdmin,
  assistance = false,
  onCreated,
}: {
  guildName?: string;
  worldName?: string;
  isGlobalAdmin: boolean;
  assistance?: boolean;
  onCreated: () => void;
}) {
  const { t } = useTranslation();
  const permitted = useMemo<RaffleScope[]>(
    () =>
      assistance ? ["guild"] : isGlobalAdmin ? ["server", "global"] : ["guild"],
    [assistance, isGlobalAdmin],
  );
  const [step, setStep] = useState<1 | 2>(1);
  const [scope, setScope] = useState<RaffleScope>(permitted[0]);
  const [title, setTitle] = useState("");
  const [purpose, setPurpose] = useState<"test" | "real">("test");
  const [execution, setExecution] = useState<"manual" | "automatic" | "scheduled">("scheduled");
  const [secondAmount, setSecondAmount] = useState("100");
  const [firstAmount, setFirstAmount] = useState("250");
  const [currency, setCurrency] = useState("TC");
  const [schedule, setSchedule] = useState("");
  const [timezone, setTimezone] = useState(
    Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC",
  );
  const [world, setWorld] = useState(worldName || "");
  const [showParticipants, setShowParticipants] = useState(false);
  const [confirmed, setConfirmed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setError("");
    if (!confirmed) {
      setError(t("raffle.workspace.wizard.confirmRequired"));
      return;
    }
    let scheduled: string | undefined;
    if (scope === "guild" && execution === "scheduled") {
      try {
        scheduled = wallTimeToUtc(schedule, timezone);
      } catch {
        setError(t("raffle.workspace.wizard.invalidSchedule"));
        return;
      }
    }
    const second = Number(secondAmount);
    const first = Number(firstAmount);
    if (!(second > 0) || !(first > 0) || !currency.trim()) {
      setError(t("raffle.workspace.wizard.invalidPrizes"));
      return;
    }
    setBusy(true);
    try {
      const automatic = scope === "guild" && execution !== "manual";
      await raffleApi.create({
        title,
        guild_name: scope === "guild" ? (guildName || "") : scope === "server" ? `Server: ${world}` : "Global",
        scope_type: scope,
        world_name: scope === "global" ? undefined : world,
        access_mode:
          scope === "guild"
            ? "guild_only"
            : scope === "server"
              ? "world_only"
              : "public",
        purpose: automatic ? (execution === "scheduled" ? purpose : "real") : "legacy",
        run_mode: automatic ? "automatic" : "manual",
        scheduled_run_at: scheduled,
        timezone_name: timezone,
        eligibility_days: 5,
        show_participants: showParticipants,
        prizes: [
              {
                name: t("raffle.operations.secondPlace"),
                reward: `${second} ${currency.trim().toUpperCase()}`,
                order_index: 1,
                position: automatic ? "second" : undefined,
                amount: second,
                currency: currency.trim().toUpperCase(),
              },
              {
                name: t("raffle.operations.firstPlace"),
                reward: `${first} ${currency.trim().toUpperCase()}`,
                order_index: 2,
                position: automatic ? "first" : undefined,
                amount: first,
                currency: currency.trim().toUpperCase(),
              },
            ],
      });
      setTitle("");
      setSchedule("");
      setConfirmed(false);
      setStep(1);
      onCreated();
    } catch {
      setError(t("raffle.workspace.wizard.createError"));
    } finally {
      setBusy(false);
    }
  };
  return (
    <section className="rounded-2xl border border-primary/20 bg-surface-base/40 p-4 sm:p-5">
      <h2 className="text-lg font-semibold">
        {t("raffle.workspace.wizard.title")}
      </h2>
      <p className="mt-1 text-sm text-content-secondary">
        {t(`raffle.workspace.wizard.step${step}`)}
      </p>
      {error && (
        <p
          role="alert"
          className="mt-3 rounded-lg border border-danger/30 p-3 text-sm text-danger"
        >
          {error}
        </p>
      )}
      {step === 1 ? (
        <div className="mt-4 grid gap-3 sm:grid-cols-3">
          {permitted.map((option) => (
            <button
              key={option}
              type="button"
              onClick={() => setScope(option)}
              className={`min-h-11 rounded-xl border p-3 text-left ${scope === option ? "border-primary bg-primary/10" : "border-line"}`}
            >
              <strong>{t(`raffle.workspace.scopes.${option}.title`)}</strong>
              <span className="mt-1 block text-xs text-content-secondary">
                {t(`raffle.workspace.scopes.${option}.help`)}
              </span>
            </button>
          ))}
          <button
            type="button"
            onClick={() => setStep(2)}
            className="min-h-11 rounded-lg bg-primary px-4 font-semibold text-content-inverse sm:col-span-3"
          >
            {t("raffle.workspace.wizard.continue")}
          </button>
        </div>
      ) : (
        <form onSubmit={submit} className="mt-4 grid gap-4 sm:grid-cols-2">
          {scope === "guild" && (
            <>
              <label className="text-sm">
                {t("raffle.workspace.fields.guild")}
                <input
                  value={guildName || ""}
                  readOnly
                  className="mt-1 min-h-11 w-full rounded-lg border border-line bg-surface-base/60 px-3 text-content-secondary"
                />
              </label>
              <label className="text-sm">
                {t("raffle.workspace.fields.server")}
                <input
                  value={worldName || world}
                  readOnly
                  className="mt-1 min-h-11 w-full rounded-lg border border-line bg-surface-base/60 px-3 text-content-secondary"
                />
              </label>
            </>
          )}
          {scope === "server" && (
            <label className="text-sm sm:col-span-2">
              {t("raffle.workspace.fields.server")}
              <input
                value={world}
                onChange={(event) => setWorld(event.target.value)}
                required
                className="mt-1 min-h-11 w-full rounded-lg bg-surface-base px-3"
              />
            </label>
          )}
          <label className="text-sm sm:col-span-2">
            {t("raffle.workspace.fields.title")}
            <input
              value={title}
              onChange={(event) => setTitle(event.target.value)}
              required
              className="mt-1 min-h-11 w-full rounded-lg bg-surface-base px-3"
            />
          </label>
          {scope === "guild" && execution === "scheduled" && (
            <label className="text-sm">
              {t("raffle.workspace.fields.purpose")}
              <select
                value={purpose}
                onChange={(event) =>
                  setPurpose(event.target.value as "test" | "real")
                }
                className="mt-1 min-h-11 w-full rounded-lg bg-surface-base px-3"
              >
                <option value="test">{t("raffle.operations.test")}</option>
                <option value="real">{t("raffle.operations.real")}</option>
              </select>
            </label>
          )}
          {scope === "guild" && (
            <label className="text-sm">
              {t("raffle.workspace.fields.execution")}
              <select value={execution} onChange={(event) => setExecution(event.target.value as typeof execution)} className="mt-1 min-h-11 w-full rounded-lg bg-surface-base px-3">
                <option value="manual">{t("raffle.workspace.execution.manual")}</option>
                <option value="automatic">{t("raffle.workspace.execution.automatic")}</option>
                <option value="scheduled">{t("raffle.workspace.execution.scheduled")}</option>
              </select>
            </label>
          )}
          {scope === "guild" && execution === "scheduled" && <label className="text-sm">
            {t("raffle.workspace.fields.timezone")}
            <input
              value={timezone}
              onChange={(event) => setTimezone(event.target.value)}
              required
              className="mt-1 min-h-11 w-full rounded-lg bg-surface-base px-3"
            />
          </label>}
          {scope === "guild" && execution === "scheduled" && <label className="text-sm">
            {t("raffle.workspace.fields.schedule")}
            <input
              type="datetime-local"
              value={schedule}
              onChange={(event) => setSchedule(event.target.value)}
              required
              className="mt-1 min-h-11 w-full rounded-lg bg-surface-base px-3"
            />
          </label>}
          <label className="flex min-h-11 items-center gap-3 rounded-lg border border-line p-3 text-sm">
            <input
              type="checkbox"
              checked={showParticipants}
              onChange={(event) => setShowParticipants(event.target.checked)}
            />
            {t("raffle.workspace.fields.showParticipants")}
          </label>
          <div className="sm:col-span-2 grid gap-3 text-sm sm:grid-cols-[1fr_1fr_8rem]">
              <label>{t("raffle.operations.secondPlace")}<input type="number" min="0.01" step="0.01" value={secondAmount} onChange={(event)=>setSecondAmount(event.target.value)} required className="mt-1 min-h-11 w-full rounded-lg bg-surface-base px-3" /></label>
              <label>{t("raffle.operations.firstPlace")}<input type="number" min="0.01" step="0.01" value={firstAmount} onChange={(event)=>setFirstAmount(event.target.value)} required className="mt-1 min-h-11 w-full rounded-lg bg-surface-base px-3" /></label>
              <label>{t("raffle.workspace.fields.currency")}<input value={currency} onChange={(event)=>setCurrency(event.target.value)} required maxLength={20} className="mt-1 min-h-11 w-full rounded-lg bg-surface-base px-3 uppercase" /></label>
              {scope === "guild" && (
              <p className="text-content-secondary sm:col-span-2">
                {t("raffle.workspace.wizard.guildRules")}
              </p>
              )}
          </div>
          <label className="flex min-h-11 items-start gap-3 rounded-lg border border-primary/20 p-3 text-sm sm:col-span-2">
            <input
              className="mt-1"
              type="checkbox"
              checked={confirmed}
              onChange={(event) => setConfirmed(event.target.checked)}
            />
            {t("raffle.workspace.wizard.confirm")}
          </label>
          <div className="flex gap-2 sm:col-span-2">
            <button
              type="button"
              onClick={() => setStep(1)}
              className="min-h-11 flex-1 rounded-lg border border-line px-4"
            >
              {t("raffle.workspace.wizard.back")}
            </button>
            <button
              disabled={busy}
              className="min-h-11 flex-1 rounded-lg bg-primary px-4 font-semibold text-content-inverse"
            >
              {busy
                ? t("raffle.workspace.wizard.creating")
                : t("raffle.workspace.wizard.create")}
            </button>
          </div>
        </form>
      )}
    </section>
  );
}
