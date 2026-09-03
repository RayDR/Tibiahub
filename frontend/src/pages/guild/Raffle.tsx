import { FormEvent, useEffect, useState } from "react";
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome";
import {
  faDice,
  faFlask,
  faFloppyDisk,
  faGift,
  faLock,
  faPen,
  faRotate,
  faRotateLeft,
  faShareNodes,
  faSpinner,
  faTrash,
  faTriangleExclamation,
  faTrophy,
  faUserMinus,
  faUserPlus,
  faUsers,
} from "@fortawesome/free-solid-svg-icons";
import { useTranslation } from "react-i18next";
import { useSearchParams } from "react-router-dom";

import { useAuth } from "../../context/AuthContext";
import { useToast } from "../../context/ToastContext";
import { useConfirmation } from "../../context/ConfirmationContext";
import { WorkspaceContentHeader } from "../../components/workspace/WorkspacePrimitives";
import { formatDate } from "../../utils/locale";
import { guildApi } from "../../services/guild";
import {
  Raffle,
  RaffleCandidate,
  RaffleSimulation,
  RaffleStatus,
  raffleApi,
} from "../../services/raffle";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

type Tab = "overview" | "participants" | "prizes" | "winners" | "admin";

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

const STATUS_COLORS: Record<string, string> = {
  draft: "bg-surface-hover/15 text-content-secondary border-line/30",
  open: "bg-success/15 text-success border-success/30",
  closed: "bg-primary/15 text-primary border-primary/30",
  completed: "bg-primary/15 text-primary border-primary/30",
  cancelled: "bg-danger/15 text-danger border-danger/30",
  deleted: "bg-danger/15 text-danger border-danger/30",
};

const ACCESS_MODE_COLORS: Record<string, string> = {
  guild_only: "bg-danger/15 text-danger border-danger/30",
  world_only: "bg-info/15 text-info border-info/30",
  public: "bg-accent/15 text-accent border-accent/30",
};

interface TooltipButtonProps {
  onClick?: () => void;
  tooltip: string;
  disabled?: boolean;
  danger?: boolean;
  primary?: boolean;
  children: React.ReactNode;
  type?: "button" | "submit";
  "aria-label"?: string;
}

function IconBtn({
  onClick,
  tooltip,
  disabled,
  danger,
  primary,
  children,
  type = "button",
  "aria-label": ariaLabel,
}: TooltipButtonProps) {
  const base =
    "group relative inline-flex items-center justify-center rounded-xl border p-2 transition disabled:opacity-40";
  const variant = danger
    ? "border-danger/40 text-danger hover:bg-danger/10"
    : primary
      ? "border-primary bg-primary text-content-inverse hover:bg-primary-hover"
      : "border-line text-content-secondary hover:border-line hover:text-content-primary";

  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      aria-label={ariaLabel ?? tooltip}
      className={`${base} ${variant}`}
    >
      {children}
      <span className="pointer-events-none absolute -top-9 left-1/2 -translate-x-1/2 whitespace-nowrap rounded-lg bg-surface px-2 py-1 text-xs text-content-primary opacity-0 shadow-lg transition-opacity group-hover:opacity-100">
        {tooltip}
      </span>
    </button>
  );
}

function StatusBadge({ status }: { status: string }) {
  const { t } = useTranslation();
  const color = STATUS_COLORS[status] ?? STATUS_COLORS.draft;
  return (
    <span
      className={`inline-flex rounded-full border px-2 py-0.5 text-xs font-medium ${color}`}
    >
      {t(`raffle.statusBadge.${status}`, status)}
    </span>
  );
}

function AccessModeBadge({ accessMode }: { accessMode: string }) {
  const { t } = useTranslation();
  const color = ACCESS_MODE_COLORS[accessMode] ?? ACCESS_MODE_COLORS.guild_only;
  return (
    <span
      className={`inline-flex rounded-full border px-2 py-0.5 text-xs font-medium ${color}`}
    >
      {t(`raffle.accessModes.${accessMode}`, accessMode)}
    </span>
  );
}

const emptyPrize = { name: "", reward: "" };

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export default function RafflePage() {
  const { user } = useAuth();
  const toast = useToast();
  const confirmation = useConfirmation();
  const { t, i18n } = useTranslation();
  const [searchParams] = useSearchParams();

  const [raffles, setRaffles] = useState<Raffle[]>([]);
  const [selectedRaffleId, setSelectedRaffleId] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [busyAction, setBusyAction] = useState<string | null>(null);
  const [rafflesEnabled, setRafflesEnabled] = useState(true);
  const [activeTab, setActiveTab] = useState<Tab>("overview");
  const [simulation, setSimulation] = useState<RaffleSimulation | null>(null);

  const [createForm, setCreateForm] = useState<{
    title: string;
    description: string;
    guild_name: string;
    show_participants: boolean;
    prizes: Array<{ name: string; reward: string }>;
  }>({
    title: "",
    description: "",
    guild_name: "",
    show_participants: true,
    prizes: [
      { name: "", reward: "" },
      { name: "", reward: "" },
      { name: "", reward: "" },
    ],
  });
  const [newPrize, setNewPrize] = useState(emptyPrize);
  const [rerunReason, setRerunReason] = useState("");
  const [manualCharacter, setManualCharacter] = useState("");
  const [editMode, setEditMode] = useState(false);
  const [manageableGuilds, setManageableGuilds] = useState<string[]>([]);
  const [manageableGuildWorlds, setManageableGuildWorlds] = useState<Record<string, string | null>>({});
  const [candidates, setCandidates] = useState<RaffleCandidate[]>([]);
  const [activityDays, setActivityDays] = useState<7 | 15 | 30>(30);
  const [candidateSearch, setCandidateSearch] = useState("");
  const [selectedCandidates, setSelectedCandidates] = useState<number[]>([]);
  const [selectedParticipants, setSelectedParticipants] = useState<number[]>([]);
  const [replaceParticipants, setReplaceParticipants] = useState(false);

  const canManage = Boolean(user?.is_superuser || manageableGuilds.length);

  useEffect(() => {
    const requested = Number(searchParams.get("raffle") || "");
    void loadRaffles(Number.isFinite(requested) && requested > 0 ? requested : undefined);
  }, []);
  useEffect(() => {
    void raffleApi.manageableGuildContext().then(context => {
      setManageableGuilds(context.guilds);
      setManageableGuildWorlds(context.guild_worlds);
    }).catch(() => {
      setManageableGuilds([]);
      setManageableGuildWorlds({});
    });
  }, []);
  useEffect(() => {
    void (async () => {
      try {
        const flags = await guildApi.getFeatureFlags();
        setRafflesEnabled(flags.guild_raffles_enabled);
      } catch {
        setRafflesEnabled(true);
      }
    })();
  }, []);
  useEffect(() => {
    if (!createForm.guild_name && (manageableGuilds[0] || user?.guild_name)) {
      setCreateForm((c) => ({ ...c, guild_name: manageableGuilds[0] || user?.guild_name || "" }));
    }
  }, [user?.guild_name, createForm.guild_name, manageableGuilds]);

  const selectedRaffle = raffles.find((r) => r.id === selectedRaffleId) ?? null;

  async function loadCandidates(raffleId: number, days = activityDays, search = candidateSearch) {
    try { setCandidates(await raffleApi.candidates(raffleId, days, search)); }
    catch { setCandidates([]); }
  }

  useEffect(() => {
    if (selectedRaffleId && activeTab === "participants") void loadCandidates(selectedRaffleId);
  }, [selectedRaffleId, activeTab, activityDays]);

  async function loadRaffles(targetId?: number) {
    setLoading(true);
    try {
      const data = await raffleApi.list();
      setRaffles(data);
      if (data.length > 0) {
        setSelectedRaffleId(targetId ?? selectedRaffleId ?? data[0].id);
      } else {
        setSelectedRaffleId(null);
      }
    } catch (err: unknown) {
      toast.error(getErrorMessage(err) || t("raffle.publicPage.loadError"));
    } finally {
      setLoading(false);
    }
  }

  async function refreshSelectedRaffle(raffleId: number) {
    const updated = await raffleApi.get(raffleId);
    setRaffles((curr) => curr.map((r) => (r.id === raffleId ? updated : r)));
    setSelectedRaffleId(raffleId);
  }

  async function handleCreateRaffle(event: FormEvent) {
    event.preventDefault();
    setBusyAction("create");
    try {
      const raffle = await raffleApi.create({
        title: createForm.title,
        description: createForm.description || undefined,
        guild_name: createForm.guild_name,
        scope_type: "guild",
        access_mode: "guild_only",
        purpose: "real",
        run_mode: "manual",
        show_participants: createForm.show_participants,
        prizes: createForm.prizes.filter((p) => p.name && p.reward),
      });
      toast.success(t("raffle.create.success"));
      setCreateForm({
        title: "",
        description: "",
        guild_name: "",
        show_participants: true,
        prizes: [
          { name: "", reward: "" },
          { name: "", reward: "" },
          { name: "", reward: "" },
        ],
      });
      await loadRaffles(raffle.id);
    } catch (err: unknown) {
      toast.error(
        getErrorMessage(err) || t("raffle.create.error"),
      );
    } finally {
      setBusyAction(null);
    }
  }

  async function handleSyncParticipants() {
    if (!selectedRaffle) return;
    setBusyAction("sync");
    try {
      const updated = await raffleApi.syncParticipants(selectedRaffle.id);
      setRaffles((curr) =>
        curr.map((r) => (r.id === updated.id ? updated : r)),
      );
      toast.success(
        t("raffle.participants.syncSuccess", {
          count: updated.participants.length,
        }),
      );
    } catch (err: unknown) {
      toast.error(
        getErrorMessage(err) || t("raffle.participants.syncError"),
      );
    } finally {
      setBusyAction(null);
    }
  }

  async function handleAddPrize(event: FormEvent) {
    event.preventDefault();
    if (!selectedRaffle) return;
    setBusyAction("prize");
    try {
      const updated = await raffleApi.addPrize(selectedRaffle.id, newPrize);
      setNewPrize(emptyPrize);
      setRaffles((curr) =>
        curr.map((r) => (r.id === updated.id ? updated : r)),
      );
      toast.success(t("raffle.prizes.success"));
    } catch (err: unknown) {
      toast.error(
        getErrorMessage(err) || t("raffle.prizes.error"),
      );
    } finally {
      setBusyAction(null);
    }
  }

  async function handleDraw() {
    if (!selectedRaffle) return;
    setBusyAction("draw");
    try {
      await raffleApi.draw(selectedRaffle.id);
      await refreshSelectedRaffle(selectedRaffle.id);
      setSimulation(null);
      toast.success(t("raffle.draw.success"));
    } catch (err: unknown) {
      toast.error(
        getErrorMessage(err) || t("raffle.draw.error"),
      );
    } finally {
      setBusyAction(null);
    }
  }

  async function handleSimulate() {
    if (!selectedRaffle) return;
    setBusyAction("simulate");
    try {
      const result = await raffleApi.simulate(selectedRaffle.id);
      setSimulation(result);
      setActiveTab("winners");
      toast.success(t("raffle.simulation.title"));
    } catch (err: unknown) {
      toast.error(
        getErrorMessage(err) || t("raffle.simulation.error"),
      );
    } finally {
      setBusyAction(null);
    }
  }

  async function handleRerun() {
    if (!selectedRaffle) return;
    setBusyAction("rerun");
    try {
      await raffleApi.rerun(selectedRaffle.id, rerunReason);
      setRerunReason("");
      await refreshSelectedRaffle(selectedRaffle.id);
      setSimulation(null);
      toast.success(t("raffle.rerun.success"));
    } catch (err: unknown) {
      toast.error(
        getErrorMessage(err) || t("raffle.rerun.error"),
      );
    } finally {
      setBusyAction(null);
    }
  }

  async function handleSaveRaffleSettings() {
    if (!selectedRaffle) return;
    setBusyAction("save");
    try {
      const updated = await raffleApi.update(selectedRaffle.id, {
        title: selectedRaffle.title,
        description: selectedRaffle.description,
        access_mode: selectedRaffle.access_mode,
        show_participants: selectedRaffle.show_participants,
        status: selectedRaffle.status,
        run_mode: selectedRaffle.run_mode,
        scheduled_run_at: selectedRaffle.scheduled_run_at,
        archive_after_days: selectedRaffle.archive_after_days,
      });
      setRaffles((curr) =>
        curr.map((r) => (r.id === updated.id ? updated : r)),
      );
      setEditMode(false);
      toast.success(t("raffle.edit.saveSuccess"));
    } catch (err: unknown) {
      toast.error(
        getErrorMessage(err) || t("raffle.edit.saveError"),
      );
    } finally {
      setBusyAction(null);
    }
  }

  async function handleShareRaffle() {
    if (!selectedRaffle) return;
    const url = `${window.location.origin}/raffles/${selectedRaffle.public_code}`;
    try {
      await navigator.clipboard.writeText(url);
      toast.success(t("raffle.share.success"));
    } catch {
      toast.error(t("raffle.share.error"));
    }
  }

  async function handleDeleteRaffle() {
    if (!selectedRaffle) return;
    if (
      !(await confirmation.confirm(t("raffle.delete.confirm"), {
        danger: true,
      }))
    )
      return;
    setBusyAction("delete");
    try {
      await raffleApi.softDelete(selectedRaffle.id, "deleted by manager");
      await loadRaffles();
      toast.success(t("raffle.delete.success"));
    } catch (err: unknown) {
      toast.error(
        getErrorMessage(err) || t("raffle.delete.error"),
      );
    } finally {
      setBusyAction(null);
    }
  }

  async function handleManualParticipant() {
    if (!selectedRaffle || !manualCharacter.trim()) return;
    setBusyAction("manual");
    try {
      const updated = await raffleApi.addManualParticipant(
        selectedRaffle.id,
        manualCharacter.trim(),
      );
      setRaffles((curr) =>
        curr.map((r) => (r.id === updated.id ? updated : r)),
      );
      setManualCharacter("");
      toast.success(t("raffle.participants.addSuccess"));
    } catch (err: unknown) {
      toast.error(
        getErrorMessage(err) || t("raffle.participants.addError"),
      );
    } finally {
      setBusyAction(null);
    }
  }

  async function handleWeightChange(participantId: number, value: number) {
    if (!selectedRaffle) return;
    setBusyAction(`weight-${participantId}`);
    try {
      const updated = await raffleApi.updateWeight(
        selectedRaffle.id,
        participantId,
        value,
      );
      setRaffles((curr) =>
        curr.map((r) => (r.id === updated.id ? updated : r)),
      );
    } catch (err: unknown) {
      toast.error(
        getErrorMessage(err) || t("raffle.participants.weightError"),
      );
    } finally {
      setBusyAction(null);
    }
  }

  async function handleRefreshRoster() {
    if (!selectedRaffle) return;
    setBusyAction("roster");
    try {
      await raffleApi.refreshGuildRoster(selectedRaffle.id);
      await loadCandidates(selectedRaffle.id);
      toast.success(t("raffle.participants.rosterRefreshed"));
    } catch (error: unknown) { toast.error(getErrorMessage(error) || t("raffle.participants.rosterError")); }
    finally { setBusyAction(null); }
  }

  async function handleAddCandidates(addAll = false) {
    if (!selectedRaffle) return;
    const count = addAll ? candidates.filter(item => item.selectable || (replaceParticipants && item.already_participating)).length : selectedCandidates.length;
    if (replaceParticipants && !(await confirmation.confirm(t("raffle.participants.replaceConfirm", { current: selectedRaffle.participant_count, next: count }), { danger: true }))) return;
    setBusyAction(addAll ? "add-all" : "add-selected");
    try {
      const result = await raffleApi.addRosterParticipants(selectedRaffle.id, selectedCandidates, replaceParticipants, addAll, activityDays);
      await refreshSelectedRaffle(selectedRaffle.id);
      await loadCandidates(selectedRaffle.id);
      setSelectedCandidates([]);
      toast.success(t("raffle.participants.bulkAdded", { added: result.added + result.restored, removed: result.removed }));
    } catch (error: unknown) { toast.error(getErrorMessage(error) || t("raffle.participants.addError")); }
    finally { setBusyAction(null); }
  }

  async function handleRemoveSelected() {
    if (!selectedRaffle || !selectedParticipants.length) return;
    if (!(await confirmation.confirm(t("raffle.participants.removeSelectedConfirm", { count: selectedParticipants.length }), { danger: true }))) return;
    setBusyAction("remove-selected");
    try {
      await raffleApi.removeParticipants(selectedRaffle.id, selectedParticipants);
      setSelectedParticipants([]);
      await refreshSelectedRaffle(selectedRaffle.id);
      await loadCandidates(selectedRaffle.id);
      toast.success(t("raffle.participants.removeSuccess"));
    } catch (error: unknown) { toast.error(getErrorMessage(error) || t("raffle.participants.removeError")); }
    finally { setBusyAction(null); }
  }

  async function handleParticipationSetting(payload: { unique_account_participation?: boolean; weighting_mode?: "equal" | "weighted" }) {
    if (!selectedRaffle) return;
    setBusyAction("participant-settings");
    try {
      const updated = await raffleApi.updateParticipationSettings(selectedRaffle.id, payload);
      setRaffles(current => current.map(item => item.id === updated.id ? updated : item));
    } catch (error: unknown) { toast.error(getErrorMessage(error) || t("raffle.participants.settingsError")); }
    finally { setBusyAction(null); }
  }

  async function handleRemoveParticipant(participantId: number) {
    if (!selectedRaffle) return;
    if (
      !(await confirmation.confirm(t("raffle.participants.removeConfirm"), {
        danger: true,
      }))
    )
      return;
    setBusyAction(`remove-${participantId}`);
    try {
      const updated = await raffleApi.removeParticipant(
        selectedRaffle.id,
        participantId,
      );
      setRaffles((curr) =>
        curr.map((r) => (r.id === updated.id ? updated : r)),
      );
      toast.success(t("raffle.participants.removeSuccess"));
    } catch (err: unknown) {
      toast.error(
        getErrorMessage(err) || t("raffle.participants.removeError"),
      );
    } finally {
      setBusyAction(null);
    }
  }

  if (!canManage) {
    return (
      <div className="rounded-2xl border border-danger/20 bg-danger/20 p-6 text-danger">
        <div className="mb-3 flex items-center gap-3 text-lg font-semibold">
          <FontAwesomeIcon icon={faTriangleExclamation} className="h-5 w-5" />
          {t("raffle.console.noAccess")}
        </div>
        <p className="text-sm text-danger/80">
          {t("raffle.console.noAccessDesc")}
        </p>
      </div>
    );
  }

  if (!rafflesEnabled) {
    return (
      <div className="rounded-2xl border border-primary/20 bg-primary/20 p-6 text-primary">
        {t("raffle.console.disabled")}
      </div>
    );
  }

  const TABS: { id: Tab; label: string }[] = [
    { id: "overview", label: t("raffle.detail.tabs.overview") },
    { id: "participants", label: t("raffle.detail.tabs.participants") },
    { id: "prizes", label: t("raffle.detail.tabs.prizes") },
    { id: "winners", label: t("raffle.detail.tabs.winners") },
    { id: "admin", label: t("raffle.detail.tabs.admin") },
  ];

  return (
    <div className="workspace-page">
      <WorkspaceContentHeader
        eyebrow={t("raffle.legacyLabel")}
        title={t("raffle.console.title")}
        description={t("raffle.console.subtitle")}
        icon={<FontAwesomeIcon icon={faTrophy} />}
      />

      <div className="grid gap-6 xl:grid-cols-[380px_minmax(0,1fr)]">
        <form
          onSubmit={handleCreateRaffle}
          className="space-y-4 rounded-2xl border border-line bg-surface-base/70 p-5"
        >
          <h2 className="flex items-center gap-2 text-lg font-semibold text-content-primary">
            <FontAwesomeIcon icon={faGift} className="h-4 w-4 text-primary" />
            {t("raffle.create.title")}
          </h2>

          <input
            value={createForm.title}
            onChange={(e) =>
              setCreateForm((c) => ({ ...c, title: e.target.value }))
            }
            placeholder={t("raffle.create.titlePlaceholder")}
            className="w-full rounded-xl border border-line bg-surface-base px-4 py-2.5 text-content-primary outline-none focus:border-primary"
            required
          />

          {manageableGuilds.length > 1 ? <label className="grid gap-1 text-sm"><span>{t("raffle.workspace.fields.guild")}</span><select value={createForm.guild_name} onChange={event => setCreateForm(current => ({ ...current, guild_name: event.target.value }))} required className="min-h-11 rounded-xl border border-line bg-surface-base px-4"><option value="" />{manageableGuilds.map(name => <option key={name}>{name}</option>)}</select></label> : <dl className="rounded-xl border border-line bg-surface-base/60 px-4 py-3"><dt className="text-xs text-content-muted">{t("raffle.workspace.fields.guild")}</dt><dd className="mt-1 font-medium">{createForm.guild_name || "—"}</dd></dl>}

          <div className="grid gap-3 sm:grid-cols-2">
            <dl className="rounded-xl border border-line bg-surface-base/60 px-4 py-3"><dt className="text-xs text-content-muted">{t("raffle.workspace.fields.scope")}</dt><dd className="mt-1 font-medium">{t("raffle.workspace.scopes.guild.title")}</dd></dl>
            <dl className="rounded-xl border border-line bg-surface-base/60 px-4 py-3"><dt className="text-xs text-content-muted">{t("raffle.workspace.fields.purpose")}</dt><dd className="mt-1 font-medium">{t("raffle.operations.real")}</dd></dl>
            <dl className="rounded-xl border border-line bg-surface-base/60 px-4 py-3"><dt className="text-xs text-content-muted">{t("raffle.workspace.fields.server")}</dt><dd className="mt-1 font-medium">{manageableGuildWorlds[createForm.guild_name] || user?.world_name || "—"}</dd></dl>
            <label className="flex items-center gap-3 rounded-xl border border-line bg-surface-base/60 px-4 py-3 text-sm text-content-secondary">
              <input
                type="checkbox"
                checked={createForm.show_participants}
                onChange={(e) =>
                  setCreateForm((c) => ({
                    ...c,
                    show_participants: e.target.checked,
                  }))
                }
                className="accent-primary"
              />
              {t("raffle.create.showParticipantsLabel")}
            </label>
          </div>

          <textarea
            value={createForm.description}
            onChange={(e) =>
              setCreateForm((c) => ({ ...c, description: e.target.value }))
            }
            placeholder={t("raffle.create.descriptionPlaceholder")}
            className="min-h-20 w-full rounded-xl border border-line bg-surface-base px-4 py-2.5 text-content-primary outline-none focus:border-primary"
          />

          <div className="space-y-2">
            {createForm.prizes.map((prize, idx) => (
              <div key={idx} className="grid gap-2 sm:grid-cols-2">
                <input
                  value={prize.name}
                  onChange={(e) =>
                    setCreateForm((c) => ({
                      ...c,
                      prizes: c.prizes.map((p, i) =>
                        i === idx ? { ...p, name: e.target.value } : p,
                      ),
                    }))
                  }
                  placeholder={`${t("raffle.create.prizeName")} ${idx + 1}`}
                  className="rounded-xl border border-line bg-surface-base px-3 py-2 text-content-primary outline-none focus:border-primary"
                />
                <input
                  value={prize.reward}
                  onChange={(e) =>
                    setCreateForm((c) => ({
                      ...c,
                      prizes: c.prizes.map((p, i) =>
                        i === idx ? { ...p, reward: e.target.value } : p,
                      ),
                    }))
                  }
                  placeholder={t("raffle.create.prizeReward")}
                  className="rounded-xl border border-line bg-surface-base px-3 py-2 text-content-primary outline-none focus:border-primary"
                />
              </div>
            ))}
          </div>

          <button
            type="submit"
            disabled={busyAction === "create"}
            className="inline-flex w-full items-center justify-center gap-2 rounded-xl bg-primary px-4 py-2.5 font-semibold text-content-inverse transition hover:bg-primary-hover disabled:opacity-50"
          >
            {busyAction === "create" ? (
              <>
                <FontAwesomeIcon icon={faSpinner} spin className="h-4 w-4" />{" "}
                {t("raffle.create.submitting")}
              </>
            ) : (
              <>
                <FontAwesomeIcon icon={faGift} className="h-4 w-4" />{" "}
                {t("raffle.create.submit")}
              </>
            )}
          </button>
        </form>

        <div className="space-y-5">
          <div className="rounded-2xl border border-line bg-surface-base/70 p-5">
            <div className="mb-3 flex items-center justify-between">
              <h2 className="text-lg font-semibold text-content-primary">
                {t("raffle.list.title")}
              </h2>
              <IconBtn
                onClick={() => void loadRaffles()}
                tooltip={t("raffle.list.refresh")}
                disabled={loading}
              >
                <FontAwesomeIcon icon={faRotate} className="h-4 w-4" />
              </IconBtn>
            </div>

            {loading ? (
              <div className="flex items-center gap-3 text-content-secondary">
                <FontAwesomeIcon icon={faSpinner} spin className="h-4 w-4" />{" "}
                {t("raffle.list.refresh")}...
              </div>
            ) : raffles.length === 0 ? (
              <div className="rounded-xl border border-dashed border-line py-8 text-center text-sm text-content-muted">
                {t("raffle.list.empty")}
              </div>
            ) : (
              <div className="grid gap-3 sm:grid-cols-2">
                {raffles.map((raffle) => (
                  <button
                    key={raffle.id}
                    onClick={() => {
                      setSelectedRaffleId(raffle.id);
                      setActiveTab("overview");
                      setSimulation(null);
                    }}
                    className={`rounded-xl border p-4 text-left transition ${
                      selectedRaffleId === raffle.id
                        ? "border-primary bg-primary/10"
                        : "border-line bg-surface-base/60 hover:border-line"
                    }`}
                  >
                    <div className="mb-1.5 flex items-start justify-between gap-2">
                      <div className="truncate text-base font-semibold text-content-primary">
                        {raffle.title}
                      </div>
                      <StatusBadge status={raffle.status} />
                    </div>
                    <div className="text-xs uppercase tracking-wide text-content-muted">
                      {raffle.guild_name}
                    </div>
                    <div className="mt-2.5 flex flex-wrap gap-3 text-xs text-content-secondary">
                      <span className="flex items-center gap-1">
                        <FontAwesomeIcon icon={faUsers} className="h-3 w-3" />
                        {raffle.participant_count}{" "}
                        {t("raffle.list.participants")}
                      </span>
                      <span className="flex items-center gap-1">
                        <FontAwesomeIcon icon={faGift} className="h-3 w-3" />
                        {raffle.prizes.length} {t("raffle.list.prizes")}
                      </span>
                      <span>
                        {t("raffle.list.run")} {raffle.current_run_number}
                      </span>
                    </div>
                  </button>
                ))}
              </div>
            )}
          </div>

          {selectedRaffle && (
            <div className="rounded-2xl border border-line bg-surface-base/70">
              <div className="flex flex-col gap-3 border-b border-line p-5 sm:flex-row sm:items-start sm:justify-between">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <h2 className="truncate text-xl font-bold text-content-primary">
                      {selectedRaffle.title}
                    </h2>
                    <StatusBadge status={selectedRaffle.status} />
                    <AccessModeBadge accessMode={selectedRaffle.access_mode} />
                  </div>
                  <p className="mt-1 text-sm text-content-secondary">
                    {selectedRaffle.description ||
                      t("raffle.detail.noDescription")}
                  </p>
                  <p className="mt-1 text-xs text-content-muted">
                    {t("raffle.detail.guild")}: {selectedRaffle.guild_name}
                    <>
                      {" "}
                      &middot; {t("raffle.detail.accessMode")}:{" "}
                      {t(`raffle.accessModes.${selectedRaffle.access_mode}`)}
                    </>
                    {selectedRaffle.rerun_count > 0 && (
                      <>
                        {" "}
                        &middot; {t("raffle.detail.reruns")}:{" "}
                        {selectedRaffle.rerun_count}
                      </>
                    )}
                  </p>
                </div>

                <div className="flex flex-wrap items-center gap-1.5">
                  <IconBtn
                    onClick={() => void handleShareRaffle()}
                    tooltip={t("raffle.actions.share")}
                    disabled={busyAction === "share"}
                  >
                    {busyAction === "share" ? (
                      <FontAwesomeIcon
                        icon={faSpinner}
                        spin
                        className="h-4 w-4"
                      />
                    ) : (
                      <FontAwesomeIcon
                        icon={faShareNodes}
                        className="h-4 w-4"
                      />
                    )}
                  </IconBtn>
                  <IconBtn
                    onClick={() => setEditMode((v) => !v)}
                    tooltip={
                      editMode
                        ? t("raffle.actions.closeEdit")
                        : t("raffle.actions.edit")
                    }
                  >
                    {editMode ? (
                      <FontAwesomeIcon icon={faLock} className="h-4 w-4" />
                    ) : (
                      <FontAwesomeIcon icon={faPen} className="h-4 w-4" />
                    )}
                  </IconBtn>
                  <IconBtn
                    onClick={() => void handleSyncParticipants()}
                    tooltip={t("raffle.actions.sync")}
                    disabled={busyAction === "sync"}
                  >
                    {busyAction === "sync" ? (
                      <FontAwesomeIcon
                        icon={faSpinner}
                        spin
                        className="h-4 w-4"
                      />
                    ) : (
                      <FontAwesomeIcon icon={faRotate} className="h-4 w-4" />
                    )}
                  </IconBtn>
                  <IconBtn
                    onClick={() => void handleSimulate()}
                    tooltip={t("raffle.actions.simulate")}
                    disabled={busyAction === "simulate"}
                  >
                    {busyAction === "simulate" ? (
                      <FontAwesomeIcon
                        icon={faSpinner}
                        spin
                        className="h-4 w-4"
                      />
                    ) : (
                      <FontAwesomeIcon icon={faFlask} className="h-4 w-4" />
                    )}
                  </IconBtn>
                  <IconBtn
                    onClick={() => void handleDraw()}
                    tooltip={t("raffle.actions.draw")}
                    disabled={busyAction === "draw"}
                    primary
                  >
                    {busyAction === "draw" ? (
                      <FontAwesomeIcon
                        icon={faSpinner}
                        spin
                        className="h-4 w-4"
                      />
                    ) : (
                      <FontAwesomeIcon icon={faDice} className="h-4 w-4" />
                    )}
                  </IconBtn>
                  <IconBtn
                    onClick={() => void handleDeleteRaffle()}
                    tooltip={t("raffle.actions.delete")}
                    disabled={busyAction === "delete"}
                    danger
                  >
                    {busyAction === "delete" ? (
                      <FontAwesomeIcon
                        icon={faSpinner}
                        spin
                        className="h-4 w-4"
                      />
                    ) : (
                      <FontAwesomeIcon icon={faTrash} className="h-4 w-4" />
                    )}
                  </IconBtn>
                </div>
              </div>

              {editMode && (
                <div className="border-b border-line bg-surface-base/40 p-5">
                  <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                    <div>
                      <label className="mb-1 block text-xs text-content-secondary">
                        {t("raffle.edit.titleLabel")}
                      </label>
                      <input
                        value={selectedRaffle.title}
                        onChange={(e) =>
                          setRaffles((curr) =>
                            curr.map((r) =>
                              r.id === selectedRaffle.id
                                ? { ...r, title: e.target.value }
                                : r,
                            ),
                          )
                        }
                        className="w-full rounded-xl border border-line bg-surface-base px-3 py-2 text-content-primary"
                      />
                    </div>
                    <div>
                      <label className="mb-1 block text-xs text-content-secondary">
                        {t("raffle.edit.accessMode")}
                      </label>
                      <select
                        value={selectedRaffle.access_mode}
                        onChange={(e) =>
                          setRaffles((curr) =>
                            curr.map((r) =>
                              r.id === selectedRaffle.id
                                ? {
                                    ...r,
                                    access_mode: e.target.value as
                                      "guild_only" | "world_only" | "public",
                                  }
                                : r,
                            ),
                          )
                        }
                        className="w-full rounded-xl border border-line bg-surface-base px-3 py-2 text-content-primary"
                      >
                        <option value="guild_only">
                          {t("raffle.accessModes.guild_only")}
                        </option>
                        <option value="world_only">
                          {t("raffle.accessModes.world_only")}
                        </option>
                        <option value="public">
                          {t("raffle.accessModes.public")}
                        </option>
                      </select>
                      <p className="mt-1 text-xs text-content-muted">
                        {selectedRaffle.access_mode === "guild_only" &&
                          t("raffle.edit.accessModeHelpGuild")}
                        {selectedRaffle.access_mode === "world_only" &&
                          t("raffle.edit.accessModeHelpWorld")}
                        {selectedRaffle.access_mode === "public" &&
                          t("raffle.edit.accessModeHelpPublic")}
                      </p>
                    </div>
                    <div>
                      <label className="mb-1 block text-xs text-content-secondary">
                        {t("raffle.edit.statusLabel")}
                      </label>
                      <select
                        value={selectedRaffle.status}
                        onChange={(e) =>
                          setRaffles((curr) =>
                            curr.map((r) =>
                              r.id === selectedRaffle.id
                                ? {
                                    ...r,
                                    status: e.target.value as RaffleStatus,
                                  }
                                : r,
                            ),
                          )
                        }
                        className="w-full rounded-xl border border-line bg-surface-base px-3 py-2 text-content-primary"
                      >
                        <option value="draft">
                          {t("raffle.edit.statusDraft")}
                        </option>
                        <option value="open">
                          {t("raffle.edit.statusOpen")}
                        </option>
                        <option value="closed">
                          {t("raffle.edit.statusClosed")}
                        </option>
                        <option value="completed">
                          {t("raffle.edit.statusCompleted")}
                        </option>
                        <option value="cancelled">
                          {t("raffle.edit.statusCancelled")}
                        </option>
                      </select>
                    </div>
                    <label className="flex items-center gap-2 text-sm text-content-secondary sm:col-span-2 lg:col-span-3">
                      <input
                        type="checkbox"
                        checked={selectedRaffle.show_participants}
                        onChange={(e) =>
                          setRaffles((curr) =>
                            curr.map((r) =>
                              r.id === selectedRaffle.id
                                ? { ...r, show_participants: e.target.checked }
                                : r,
                            ),
                          )
                        }
                        className="accent-primary"
                      />
                      {selectedRaffle.show_participants
                        ? t("raffle.edit.showParticipantsEnabled")
                        : t("raffle.edit.showParticipantsDisabled")}
                    </label>
                  </div>
                  <button
                    onClick={() => void handleSaveRaffleSettings()}
                    disabled={busyAction === "save"}
                    className="mt-3 inline-flex items-center gap-2 rounded-xl bg-primary px-4 py-2 text-sm font-semibold text-content-inverse disabled:opacity-50"
                  >
                    {busyAction === "save" ? (
                      <FontAwesomeIcon
                        icon={faSpinner}
                        spin
                        className="h-4 w-4"
                      />
                    ) : (
                      <FontAwesomeIcon
                        icon={faFloppyDisk}
                        className="h-4 w-4"
                      />
                    )}
                    {busyAction === "save"
                      ? t("raffle.actionLabels.saving")
                      : t("raffle.actions.save")}
                  </button>
                </div>
              )}

              <div className="flex overflow-x-auto border-b border-line">
                {TABS.map((tab) => (
                  <button
                    key={tab.id}
                    onClick={() => setActiveTab(tab.id)}
                    className={`shrink-0 border-b-2 px-4 py-3 text-sm font-medium transition ${
                      activeTab === tab.id
                        ? "border-primary text-primary"
                        : "border-transparent text-content-secondary hover:text-content-primary"
                    }`}
                  >
                    {tab.label}
                    {tab.id === "participants" &&
                      selectedRaffle.participants.length > 0 && (
                        <span className="ml-1.5 rounded-full bg-surface-raised px-1.5 py-0.5 text-xs">
                          {selectedRaffle.participants.length}
                        </span>
                      )}
                    {tab.id === "prizes" &&
                      selectedRaffle.prizes.length > 0 && (
                        <span className="ml-1.5 rounded-full bg-surface-raised px-1.5 py-0.5 text-xs">
                          {selectedRaffle.prizes.length}
                        </span>
                      )}
                  </button>
                ))}
              </div>

              <div className="p-5">
                {activeTab === "overview" && (
                  <div className="grid gap-4 sm:grid-cols-3">
                    <div className="rounded-xl border border-line bg-surface-base/60 p-4 text-center">
                      <div className="text-2xl font-bold text-primary">
                        {selectedRaffle.participant_count}
                      </div>
                      <div className="mt-1 text-xs text-content-secondary">
                        {t("raffle.detail.tabs.participants")}
                      </div>
                    </div>
                    <div className="rounded-xl border border-line bg-surface-base/60 p-4 text-center">
                      <div className="text-2xl font-bold text-primary">
                        {selectedRaffle.prizes.length}
                      </div>
                      <div className="mt-1 text-xs text-content-secondary">
                        {t("raffle.detail.tabs.prizes")}
                      </div>
                    </div>
                    <div className="rounded-xl border border-line bg-surface-base/60 p-4 text-center">
                      <div className="text-2xl font-bold text-primary">
                        {selectedRaffle.current_run_number}
                      </div>
                      <div className="mt-1 text-xs text-content-secondary">
                        {t("raffle.list.run")}
                      </div>
                    </div>
                    {selectedRaffle.prizes.length > 0 && (
                      <div className="sm:col-span-3">
                        <div className="mb-2 text-sm font-medium text-content-secondary">
                          {t("raffle.detail.tabs.prizes")}
                        </div>
                        <div className="flex flex-wrap gap-2">
                          {selectedRaffle.prizes.map((prize) => (
                            <span
                              key={prize.id}
                              className="inline-flex items-center gap-1.5 rounded-full border border-primary/30 bg-primary/10 px-3 py-1 text-sm text-primary"
                            >
                              <FontAwesomeIcon
                                icon={faTrophy}
                                className="h-3 w-3"
                              />
                              <span className="font-medium">{prize.name}</span>
                              <span className="text-primary/70">&middot;</span>
                              <span>{prize.reward}</span>
                            </span>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                )}

                {activeTab === "participants" && (
                  <div className="space-y-4">
                    <div className="grid gap-3 rounded-xl border border-line bg-surface-base/50 p-4 lg:grid-cols-2">
                      <label className="grid gap-1 text-sm">
                        <span>{t("raffle.participants.activityWindow")}</span>
                        <select value={activityDays} onChange={event => setActivityDays(Number(event.target.value) as 7 | 15 | 30)} className="min-h-11 rounded-lg border border-line bg-surface px-3">
                          {([7, 15, 30] as const).map(days => <option key={days} value={days}>{t("raffle.participants.days", { days })}</option>)}
                        </select>
                      </label>
                      <label className="grid gap-1 text-sm">
                        <span>{t("raffle.participants.search")}</span>
                        <input value={candidateSearch} onChange={event => setCandidateSearch(event.target.value)} onKeyDown={event => { if (event.key === "Enter") { event.preventDefault(); void loadCandidates(selectedRaffle.id); } }} className="min-h-11 rounded-lg border border-line bg-surface px-3" placeholder={t("raffle.participants.searchPlaceholder")} />
                      </label>
                      <label className="flex min-h-11 items-center gap-2 text-sm"><input type="checkbox" checked={selectedRaffle.unique_account_participation} disabled={busyAction === "participant-settings"} onChange={event => void handleParticipationSetting({ unique_account_participation: event.target.checked })} />{t("raffle.participants.uniqueKnownAccount")}</label>
                      <label className="grid gap-1 text-sm"><span>{t("raffle.participants.weightingMode")}</span><select value={selectedRaffle.weighting_mode} disabled={busyAction === "participant-settings"} onChange={event => void handleParticipationSetting({ weighting_mode: event.target.value as "equal" | "weighted" })} className="min-h-11 rounded-lg border border-line bg-surface px-3"><option value="equal">{t("raffle.participants.equal")}</option><option value="weighted">{t("raffle.participants.weighted")}</option></select></label>
                      <p className="text-xs text-content-muted lg:col-span-2">{t("raffle.participants.unknownAccountHelp")}</p>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      <button type="button" onClick={() => void handleRefreshRoster()} disabled={busyAction === "roster"} className="app-button-secondary">{t("raffle.participants.refreshRoster")}</button>
                      <button type="button" onClick={() => void loadCandidates(selectedRaffle.id)} className="app-button-secondary">{t("raffle.participants.searchAction")}</button>
                      <label className="flex min-h-11 items-center gap-2 rounded-lg border border-line px-3 text-sm"><input type="checkbox" checked={replaceParticipants} onChange={event => setReplaceParticipants(event.target.checked)} />{t("raffle.participants.replaceExisting")}</label>
                    </div>
                    <div className="max-h-72 space-y-2 overflow-y-auto rounded-xl border border-line p-2">
                      {candidates.length === 0 ? <p className="p-4 text-center text-sm text-content-muted">{t("raffle.participants.noCandidates")}</p> : candidates.map(candidate => <label key={candidate.roster_character_id} className={`flex min-w-0 items-start gap-3 rounded-lg border p-3 ${candidate.selectable ? "border-line" : "border-line bg-disabled text-content-muted"}`}>
                        <input type="checkbox" className="mt-1" disabled={!candidate.selectable} checked={selectedCandidates.includes(candidate.roster_character_id)} onChange={event => setSelectedCandidates(current => event.target.checked ? [...current, candidate.roster_character_id] : current.filter(id => id !== candidate.roster_character_id))} />
                        <span className="min-w-0 flex-1"><strong className="block truncate">{candidate.character_name}</strong><span className="block text-xs text-content-muted">{candidate.rank || t("guild.member")} · {candidate.level ?? "—"} {candidate.vocation || ""} · {formatDate(candidate.last_activity_at, i18n.resolvedLanguage || i18n.language)}</span><span className="mt-1 inline-flex rounded-full border border-line px-2 py-0.5 text-xs">{t(candidate.account_identity_known ? "raffle.participants.registered" : "raffle.participants.unregistered")}</span>{candidate.reason ? <span className="ml-2 text-xs">{t(`raffle.participants.reasons.${candidate.reason}`, candidate.reason)}</span> : null}</span>
                      </label>)}
                    </div>
                    <div className="flex flex-wrap gap-2"><button type="button" disabled={!selectedCandidates.length || busyAction === "add-selected"} onClick={() => void handleAddCandidates(false)} className="app-button-primary">{t("raffle.participants.addSelected", { count: selectedCandidates.length })}</button><button type="button" disabled={!candidates.some(item => item.selectable || (replaceParticipants && item.already_participating)) || busyAction === "add-all"} onClick={() => void handleAddCandidates(true)} className="app-button-secondary">{t("raffle.participants.addAll")}</button></div>
                    {selectedRaffle.purpose === "test" && user?.is_superuser ? <div className="flex gap-2">
                      <input
                        value={manualCharacter}
                        onChange={(e) => setManualCharacter(e.target.value)}
                        placeholder={t(
                          "raffle.participants.characterPlaceholder",
                        )}
                        className="flex-1 rounded-xl border border-line bg-surface-base px-3 py-2 text-content-primary outline-none focus:border-primary"
                        onKeyDown={(e) => {
                          if (e.key === "Enter") {
                            e.preventDefault();
                            void handleManualParticipant();
                          }
                        }}
                      />
                      <IconBtn
                        onClick={() => void handleManualParticipant()}
                        tooltip={t("raffle.actions.addParticipant")}
                        disabled={
                          busyAction === "manual" || !manualCharacter.trim()
                        }
                      >
                        {busyAction === "manual" ? (
                          <FontAwesomeIcon
                            icon={faSpinner}
                            spin
                            className="h-4 w-4"
                          />
                        ) : (
                          <FontAwesomeIcon
                            icon={faUserPlus}
                            className="h-4 w-4"
                          />
                        )}
                      </IconBtn>
                    </div> : null}
                    <div className="flex items-center justify-between gap-3"><h3 className="font-semibold">{t("raffle.participants.current")}</h3><button type="button" disabled={!selectedParticipants.length || busyAction === "remove-selected"} onClick={() => void handleRemoveSelected()} className="app-button-danger">{t("raffle.participants.removeSelected", { count: selectedParticipants.length })}</button></div>
                    <div className="max-h-80 space-y-2 overflow-y-auto pr-1">
                      {selectedRaffle.participants.length === 0 ? (
                        <div className="rounded-xl border border-dashed border-line py-8 text-center text-sm text-content-muted">
                          {t("raffle.participants.empty")}
                        </div>
                      ) : (
                        selectedRaffle.participants.map((participant) => (
                          <div
                            key={participant.id}
                            className="flex min-w-0 items-center gap-3 rounded-xl border border-line bg-surface-base/50 px-3 py-2.5"
                          >
                            <input type="checkbox" checked={selectedParticipants.includes(participant.id)} onChange={event => setSelectedParticipants(current => event.target.checked ? [...current, participant.id] : current.filter(id => id !== participant.id))} aria-label={t("raffle.participants.selectCharacter", { character: participant.character_name })} />
                            <div className="min-w-0">
                              <div className="truncate font-medium text-content-primary">
                                {participant.character_name}
                              </div>
                              <div className="text-xs text-content-muted">
                                {participant.username || t("raffle.participants.unregistered")} &middot;{" "}
                                {participant.guild_rank || t("guild.member")}
                              </div>
                            </div>
                            <div className="ml-3 flex shrink-0 items-center gap-2">
                              <div className="text-right text-xs text-content-secondary">
                                <div
                                  className={
                                    participant.is_eligible
                                      ? "text-success"
                                      : "text-content-muted"
                                  }
                                >
                                  {participant.is_eligible
                                    ? t("raffle.participants.eligible")
                                    : t("raffle.participants.ineligible")}
                                </div>
                                <div>
                                  {t("raffle.participants.weight")}{" "}
                                  {Number.isFinite(Number(participant.weight))
                                    ? Number(participant.weight).toFixed(1)
                                    : "1.0"}
                                </div>
                              </div>
                              {selectedRaffle.weighting_mode === "weighted" ? <input type="number" min="0.0001" max="1000000" step="0.1" defaultValue={participant.weight} onBlur={event => { const value = Number(event.target.value); if (!Number.isFinite(value) || value <= 0 || value > 1000000) { toast.error(t("raffle.participants.invalidWeight")); event.currentTarget.value = String(participant.weight); return; } if (value !== Number(participant.weight)) void handleWeightChange(participant.id, value); }} className="h-9 w-24 rounded-lg border border-line bg-surface px-2 text-sm" aria-label={t("raffle.participants.weightFor", { character: participant.character_name })} /> : <span className="text-xs text-content-muted">{t("raffle.participants.equalProbability")}</span>}
                              <IconBtn
                                onClick={() =>
                                  void handleRemoveParticipant(participant.id)
                                }
                                tooltip={t("raffle.actions.removeParticipant")}
                                disabled={
                                  busyAction === `remove-${participant.id}`
                                }
                                danger
                              >
                                {busyAction === `remove-${participant.id}` ? (
                                  <FontAwesomeIcon
                                    icon={faSpinner}
                                    spin
                                    className="h-3 w-3"
                                  />
                                ) : (
                                  <FontAwesomeIcon
                                    icon={faUserMinus}
                                    className="h-3 w-3"
                                  />
                                )}
                              </IconBtn>
                            </div>
                          </div>
                        ))
                      )}
                    </div>
                  </div>
                )}

                {activeTab === "prizes" && (
                  <div className="space-y-4">
                    <div className="flex flex-wrap gap-2">
                      {selectedRaffle.prizes.length === 0 ? (
                        <div className="w-full rounded-xl border border-dashed border-line py-6 text-center text-sm text-content-muted">
                          {t("raffle.prizes.empty")}
                        </div>
                      ) : (
                        selectedRaffle.prizes.map((prize) => (
                          <div
                            key={prize.id}
                            className="flex items-center gap-2 rounded-xl border border-primary/20 bg-primary/8 px-4 py-2.5"
                          >
                            <FontAwesomeIcon
                              icon={faGift}
                              className="h-4 w-4 text-primary"
                            />
                            <div>
                              <div className="text-sm font-medium text-primary">
                                {prize.name}
                              </div>
                              <div className="text-xs text-primary/70">
                                {prize.reward}
                              </div>
                            </div>
                          </div>
                        ))
                      )}
                    </div>
                    <form onSubmit={handleAddPrize} className="flex gap-2">
                      <input
                        value={newPrize.name}
                        onChange={(e) =>
                          setNewPrize((p) => ({ ...p, name: e.target.value }))
                        }
                        placeholder={t("raffle.prizes.namePlaceholder")}
                        className="flex-1 rounded-xl border border-line bg-surface-base px-3 py-2 text-content-primary outline-none focus:border-primary"
                        required
                      />
                      <input
                        value={newPrize.reward}
                        onChange={(e) =>
                          setNewPrize((p) => ({ ...p, reward: e.target.value }))
                        }
                        placeholder={t("raffle.prizes.rewardPlaceholder")}
                        className="w-24 rounded-xl border border-line bg-surface-base px-3 py-2 text-content-primary outline-none focus:border-primary"
                        required
                      />
                      <IconBtn
                        type="submit"
                        tooltip={t("raffle.actions.addPrize")}
                        disabled={busyAction === "prize"}
                      >
                        {busyAction === "prize" ? (
                          <FontAwesomeIcon
                            icon={faSpinner}
                            spin
                            className="h-4 w-4"
                          />
                        ) : (
                          <FontAwesomeIcon icon={faGift} className="h-4 w-4" />
                        )}
                      </IconBtn>
                    </form>
                  </div>
                )}

                {activeTab === "winners" && (
                  <div className="space-y-5">
                    {simulation && (
                      <div className="rounded-xl border border-info/30 bg-info/20 p-4">
                        <div className="mb-3 flex items-center gap-2 text-sm font-medium text-info">
                          <FontAwesomeIcon icon={faFlask} className="h-4 w-4" />
                          {t("raffle.simulation.title")}
                          <span className="ml-auto rounded-full bg-info/20 px-2 py-0.5 text-xs">
                            {t("raffle.simulation.eligible")}:{" "}
                            {simulation.eligible_count} &middot;{" "}
                            {t("raffle.simulation.ineligible")}:{" "}
                            {simulation.ineligible_count}
                          </span>
                        </div>
                        <div className="mb-3 flex flex-wrap gap-2 text-xs text-info">
                          {simulation.prizes.map((prize) => (
                            <span
                              key={prize.id}
                              className="rounded-full border border-info/20 px-2 py-1"
                            >
                              {prize.name}: {prize.reward}
                            </span>
                          ))}
                        </div>
                        <div className="mb-3 rounded-lg border border-info/20 bg-surface-base/20 p-3 text-xs text-info">
                          <div className="mb-1 font-semibold">
                            {t("raffle.simulation.warnings")}
                          </div>
                          {simulation.warnings.length > 0 ? (
                            simulation.warnings.map((warning) => (
                              <div key={warning}>{warning}</div>
                            ))
                          ) : (
                            <div>{t("raffle.simulation.noWarnings")}</div>
                          )}
                        </div>
                        <div className="space-y-2">
                          {simulation.winners.map((w) => (
                            <div
                              key={w.id}
                              className="flex items-center justify-between rounded-lg border border-info/20 px-3 py-2 text-sm"
                            >
                              <div>
                                <span className="font-medium text-info">
                                  {w.character_name}
                                </span>
                                <span className="ml-1 text-info/60">
                                  &middot; {w.username}
                                </span>
                              </div>
                              <div className="text-right text-info">
                                <div className="font-medium">
                                  {w.prize_name}
                                </div>
                                <div className="text-xs text-info/60">
                                  {w.reward}
                                </div>
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    <div>
                      <div className="mb-3 flex items-center gap-2 text-sm font-medium text-content-primary">
                        <FontAwesomeIcon
                          icon={faTrophy}
                          className="h-4 w-4 text-primary"
                        />
                        {t("raffle.winners.title")}
                      </div>
                      <div className="space-y-2">
                        {selectedRaffle.current_winners.length === 0 ? (
                          <div className="text-sm text-content-muted">
                            {t("raffle.winners.empty")}
                          </div>
                        ) : (
                          selectedRaffle.current_winners.map((winner) => (
                            <div
                              key={winner.id}
                              className="flex items-center justify-between rounded-xl border border-line bg-surface-base/60 px-4 py-3"
                            >
                              <div>
                                <div className="font-medium text-content-primary">
                                  {winner.character_name}
                                </div>
                                <div className="text-xs text-content-muted">
                                  {winner.username}
                                </div>
                              </div>
                              <div className="text-right">
                                <div className="text-sm font-medium text-primary">
                                  {winner.prize_name}
                                </div>
                                <div className="text-xs text-primary/70">
                                  {winner.reward}
                                </div>
                                <div className="text-xs text-content-muted">
                                  {t("raffle.winners.run")} {winner.run_number}
                                </div>
                              </div>
                            </div>
                          ))
                        )}
                      </div>
                    </div>

                    {selectedRaffle.history.length > 0 && (
                      <details>
                        <summary className="cursor-pointer text-sm text-content-secondary hover:text-content-primary">
                          {t("raffle.winners.history")} (
                          {selectedRaffle.history.length})
                        </summary>
                        <div className="mt-3 max-h-60 space-y-2 overflow-y-auto">
                          {selectedRaffle.history.map((winner) => (
                            <div
                              key={winner.id}
                              className="rounded-lg border border-line/60 px-3 py-2 text-sm text-content-secondary"
                            >
                              <span className="font-medium text-content-secondary">
                                {winner.prize_name}
                              </span>
                              {" \u2192 "}
                              {winner.character_name}
                              <span className="ml-2 text-xs">
                                {t("raffle.winners.run")} {winner.run_number}
                                {winner.is_rerun &&
                                  ` \u00b7 ${t("raffle.winners.rerun")}: ${winner.rerun_reason || t("raffle.winners.noReason")}`}
                              </span>
                            </div>
                          ))}
                        </div>
                      </details>
                    )}
                  </div>
                )}

                {activeTab === "admin" && (
                  <div className="space-y-5">
                    <div className="rounded-xl border border-danger/20 bg-danger/10 p-4">
                      <div className="mb-3 flex items-center gap-2 text-sm font-medium text-danger">
                        <FontAwesomeIcon
                          icon={faRotateLeft}
                          className="h-4 w-4"
                        />
                        {t("raffle.rerun.title")}
                      </div>
                      <textarea
                        value={rerunReason}
                        onChange={(e) => setRerunReason(e.target.value)}
                        placeholder={t("raffle.rerun.reasonPlaceholder")}
                        className="min-h-20 w-full rounded-xl border border-line bg-surface-base px-3 py-2 text-content-primary outline-none focus:border-danger"
                      />
                      <button
                        onClick={() => void handleRerun()}
                        disabled={!rerunReason.trim() || busyAction === "rerun"}
                        className="mt-3 inline-flex items-center gap-2 rounded-xl bg-danger px-4 py-2 text-sm font-semibold text-content-on-primary disabled:opacity-50"
                      >
                        {busyAction === "rerun" ? (
                          <FontAwesomeIcon
                            icon={faSpinner}
                            spin
                            className="h-4 w-4"
                          />
                        ) : (
                          <FontAwesomeIcon
                            icon={faRotateLeft}
                            className="h-4 w-4"
                          />
                        )}
                        {busyAction === "rerun"
                          ? t("raffle.actionLabels.rerunning")
                          : t("raffle.actions.rerun")}
                      </button>
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
