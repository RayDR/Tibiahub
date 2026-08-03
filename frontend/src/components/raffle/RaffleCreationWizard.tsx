import { FormEvent, useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { raffleApi, RaffleScope } from "../../services/raffle";
import { wallTimeToUtc } from "../../pages/guild/AutomaticRaffleOperations";

export default function RaffleCreationWizard({ guildName, worldName, isGlobalAdmin, assistance = false, onCreated }: {
  guildName?: string; worldName?: string; isGlobalAdmin: boolean; assistance?: boolean; onCreated: () => void;
}) {
  const { t } = useTranslation();
  const scopes = useMemo<RaffleScope[]>(() => assistance ? ["guild"] : isGlobalAdmin ? ["guild", "server", "global"] : ["guild"], [assistance, isGlobalAdmin]);
  const [scope, setScope] = useState<RaffleScope>("guild");
  const [guilds, setGuilds] = useState<string[]>(guildName ? [guildName] : []);
  const [guildWorlds, setGuildWorlds] = useState<Record<string, string | null>>({});
  const [guild, setGuild] = useState(guildName || "");
  const [title, setTitle] = useState("");
  const [purpose, setPurpose] = useState<"test" | "real">(isGlobalAdmin ? "test" : "real");
  const [execution, setExecution] = useState<"manual" | "automatic" | "scheduled">("scheduled");
  const [weightingMode, setWeightingMode] = useState<"equal" | "weighted">("equal");
  const [uniqueKnownAccount, setUniqueKnownAccount] = useState(true);
  const [secondAmount, setSecondAmount] = useState("100");
  const [firstAmount, setFirstAmount] = useState("250");
  const [currency, setCurrency] = useState("TC");
  const [schedule, setSchedule] = useState("");
  const [timezone, setTimezone] = useState(Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC");
  const [world, setWorld] = useState(worldName || "");
  const [showParticipants, setShowParticipants] = useState(false);
  const [confirmed, setConfirmed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    void raffleApi.manageableGuildContext().then(context => {
      const options = guildName ? [guildName] : context.guilds;
      setGuildWorlds(context.guild_worlds);
      setGuilds(options);
      setGuild(current => current || options[0] || "");
    }).catch(() => setGuilds(guildName ? [guildName] : []));
  }, [guildName]);

  const automatic = scope === "guild" && execution !== "manual";
  const effectivePurpose = isGlobalAdmin ? purpose : "real";
  const selectedGuildWorld = guildWorlds[guild] || worldName || world;

  const submit = async (event: FormEvent) => {
    event.preventDefault(); setError("");
    if (!confirmed) { setError(t("raffle.workspace.wizard.confirmRequired")); return; }
    if (scope === "guild" && !guild) { setError(t("raffle.workspace.wizard.guildRequired")); return; }
    if (effectivePurpose === "test" && execution !== "scheduled") { setError(t("raffle.workspace.wizard.testScheduleRequired")); return; }
    let scheduled: string | undefined;
    if (execution === "scheduled") {
      try { scheduled = wallTimeToUtc(schedule, timezone); }
      catch { setError(t("raffle.workspace.wizard.invalidSchedule")); return; }
    }
    const second = Number(secondAmount); const first = Number(firstAmount);
    if (!(second > 0) || !(first > 0) || !currency.trim()) { setError(t("raffle.workspace.wizard.invalidPrizes")); return; }
    setBusy(true);
    try {
      await raffleApi.create({
        title, guild_name: scope === "guild" ? guild : scope === "server" ? `Server: ${world}` : "Global",
        scope_type: scope, world_name: scope === "global" ? undefined : scope === "server" ? world : selectedGuildWorld,
        access_mode: scope === "guild" ? "guild_only" : scope === "server" ? "world_only" : "public",
        purpose: scope === "guild" ? effectivePurpose : "legacy", run_mode: automatic ? "automatic" : "manual",
        scheduled_run_at: scheduled, timezone_name: timezone, eligibility_days: 5,
        show_participants: showParticipants, unique_account_participation: uniqueKnownAccount,
        weighting_mode: weightingMode,
        prizes: [
          { name: t("raffle.operations.secondPlace"), reward: `${second} ${currency.trim().toUpperCase()}`, order_index: 1, position: automatic ? "second" : undefined, amount: second, currency: currency.trim().toUpperCase() },
          { name: t("raffle.operations.firstPlace"), reward: `${first} ${currency.trim().toUpperCase()}`, order_index: 2, position: automatic ? "first" : undefined, amount: first, currency: currency.trim().toUpperCase() },
        ],
      });
      onCreated();
    } catch { setError(t("raffle.workspace.wizard.createError")); }
    finally { setBusy(false); }
  };

  return <section className="rounded-2xl border border-primary/20 bg-surface-base/40 p-4 sm:p-5">
    <h2 className="text-lg font-semibold">{t("raffle.workspace.wizard.title")}</h2>
    <p className="mt-1 text-sm text-content-secondary">{t("raffle.workspace.wizard.roleHelp")}</p>
    {error ? <p role="alert" className="mt-3 rounded-lg border border-danger/30 p-3 text-sm text-danger">{error}</p> : null}
    <form onSubmit={submit} className="mt-4 grid gap-4 sm:grid-cols-2">
      {isGlobalAdmin && scopes.length > 1 ? <label className="grid gap-1 text-sm">{t("raffle.workspace.fields.scope")}<select value={scope} onChange={event => setScope(event.target.value as RaffleScope)} className="min-h-11 rounded-lg border border-line bg-surface px-3">{scopes.map(value => <option key={value} value={value}>{t(`raffle.workspace.scopes.${value}.title`)}</option>)}</select></label> : <FixedValue label={t("raffle.workspace.fields.scope")} value={t("raffle.workspace.scopes.guild.title")} />}
      {scope === "guild" ? guilds.length > 1 ? <label className="grid gap-1 text-sm">{t("raffle.workspace.fields.guild")}<select value={guild} onChange={event => setGuild(event.target.value)} className="min-h-11 rounded-lg border border-line bg-surface px-3">{guilds.map(value => <option key={value}>{value}</option>)}</select></label> : <FixedValue label={t("raffle.workspace.fields.guild")} value={guild || t("raffle.workspace.wizard.guildUnavailable")} /> : null}
      {scope === "guild" ? <FixedValue label={t("raffle.workspace.fields.server")} value={selectedGuildWorld || "—"} /> : scope === "server" ? <label className="grid gap-1 text-sm">{t("raffle.workspace.fields.server")}<input value={world} onChange={event => setWorld(event.target.value)} required className="min-h-11 rounded-lg border border-line bg-surface px-3" /></label> : null}
      {scope === "guild" && isGlobalAdmin ? <label className="grid gap-1 text-sm">{t("raffle.workspace.fields.purpose")}<select value={purpose} onChange={event => setPurpose(event.target.value as "test" | "real")} className="min-h-11 rounded-lg border border-line bg-surface px-3"><option value="test">{t("raffle.operations.test")}</option><option value="real">{t("raffle.operations.real")}</option></select></label> : scope === "guild" ? <FixedValue label={t("raffle.workspace.fields.purpose")} value={t("raffle.operations.real")} /> : null}
      <label className="grid gap-1 text-sm sm:col-span-2">{t("raffle.workspace.fields.title")}<input value={title} onChange={event => setTitle(event.target.value)} required minLength={3} maxLength={200} className="min-h-11 rounded-lg border border-line bg-surface px-3" /></label>
      {scope === "guild" ? <label className="grid gap-1 text-sm">{t("raffle.workspace.fields.execution")}<select value={execution} onChange={event => setExecution(event.target.value as typeof execution)} className="min-h-11 rounded-lg border border-line bg-surface px-3"><option value="manual">{t("raffle.workspace.execution.manual")}</option><option value="automatic">{t("raffle.workspace.execution.automatic")}</option><option value="scheduled">{t("raffle.workspace.execution.scheduled")}</option></select></label> : <FixedValue label={t("raffle.workspace.fields.execution")} value={t("raffle.workspace.execution.manual")} />}
      <label className="grid gap-1 text-sm">{t("raffle.participants.weightingMode")}<select value={weightingMode} onChange={event => setWeightingMode(event.target.value as "equal" | "weighted")} className="min-h-11 rounded-lg border border-line bg-surface px-3"><option value="equal">{t("raffle.participants.equal")}</option><option value="weighted">{t("raffle.participants.weighted")}</option></select></label>
      {execution === "scheduled" ? <><label className="grid gap-1 text-sm">{t("raffle.workspace.fields.timezone")}<input value={timezone} onChange={event => setTimezone(event.target.value)} required className="min-h-11 rounded-lg border border-line bg-surface px-3" /></label><label className="grid gap-1 text-sm">{t("raffle.workspace.fields.schedule")}<input type="datetime-local" value={schedule} onChange={event => setSchedule(event.target.value)} required className="min-h-11 rounded-lg border border-line bg-surface px-3" /></label></> : null}
      <label className="flex min-h-11 items-center gap-3 rounded-lg border border-line p-3 text-sm"><input type="checkbox" checked={uniqueKnownAccount} onChange={event => setUniqueKnownAccount(event.target.checked)} />{t("raffle.participants.uniqueKnownAccount")}</label>
      <label className="flex min-h-11 items-center gap-3 rounded-lg border border-line p-3 text-sm"><input type="checkbox" checked={showParticipants} onChange={event => setShowParticipants(event.target.checked)} />{t("raffle.workspace.fields.showParticipants")}</label>
      <div className="grid gap-3 text-sm sm:col-span-2 sm:grid-cols-[1fr_1fr_8rem]"><label>{t("raffle.operations.secondPlace")}<input type="number" min="0.01" step="0.01" value={secondAmount} onChange={event => setSecondAmount(event.target.value)} required className="mt-1 min-h-11 w-full rounded-lg border border-line bg-surface px-3" /></label><label>{t("raffle.operations.firstPlace")}<input type="number" min="0.01" step="0.01" value={firstAmount} onChange={event => setFirstAmount(event.target.value)} required className="mt-1 min-h-11 w-full rounded-lg border border-line bg-surface px-3" /></label><label>{t("raffle.workspace.fields.currency")}<input value={currency} onChange={event => setCurrency(event.target.value)} required maxLength={20} className="mt-1 min-h-11 w-full rounded-lg border border-line bg-surface px-3 uppercase" /></label></div>
      <label className="flex min-h-11 items-start gap-3 rounded-lg border border-primary/20 p-3 text-sm sm:col-span-2"><input className="mt-1" type="checkbox" checked={confirmed} onChange={event => setConfirmed(event.target.checked)} />{t("raffle.workspace.wizard.confirm")}</label>
      <button disabled={busy || (scope === "guild" && !guild)} className="min-h-11 rounded-lg bg-primary px-4 font-semibold text-content-inverse sm:col-span-2">{busy ? t("raffle.workspace.wizard.creating") : t("raffle.workspace.wizard.create")}</button>
    </form>
  </section>;
}

function FixedValue({ label, value }: { label: string; value: string }) {
  return <dl className="rounded-lg border border-line bg-surface-base/60 px-3 py-2"><dt className="text-xs text-content-muted">{label}</dt><dd className="mt-1 font-medium text-content-primary">{value}</dd></dl>;
}
