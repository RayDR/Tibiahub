import { FormEvent, useCallback, useEffect, useState } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  DatabaseZap,
  Search,
  ShieldCheck,
} from "lucide-react";
import { useTranslation } from "react-i18next";

import {
  Badge,
  Dialog,
  EmptyState,
  LoadingState,
} from "../../components/ui";
import { WorkspaceContentHeader } from "../../components/workspace/WorkspacePrimitives";
import { useToast } from "../../context/ToastContext";
import {
  MaintenanceCategory,
  MaintenanceItem,
  maintenanceApi,
} from "../../services/maintenance";

const categories: MaintenanceCategory[] = [
  "guilds",
  "users",
  "characters",
  "raffles",
  "leadership",
  "events",
  "hunts",
  "knowledge",
];

export default function Maintenance() {
  const { t } = useTranslation();
  const toast = useToast();
  const [category, setCategory] = useState<MaintenanceCategory>("guilds");
  const [items, setItems] = useState<MaintenanceItem[]>([]);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [selected, setSelected] = useState<MaintenanceItem | null>(null);
  const load = useCallback(async () => {
    setLoading(true);
    setError(false);
    try {
      setItems(await maintenanceApi.list(category, search));
    } catch {
      setError(true);
    } finally {
      setLoading(false);
    }
  }, [category, search]);
  useEffect(() => {
    const handle = window.setTimeout(() => void load(), 250);
    return () => window.clearTimeout(handle);
  }, [load]);
  return (
    <div className="workspace-page">
      <WorkspaceContentHeader
        eyebrow={t("maintenance.eyebrow")}
        title={t("maintenance.title")}
        description={t("maintenance.subtitle")}
        icon={<DatabaseZap />}
      />
      <section className="rounded-2xl bg-warning-subtle p-4 text-warning">
        <div className="flex items-start gap-3">
          <ShieldCheck className="mt-0.5 size-5 shrink-0" />
          <div>
            <h2 className="font-semibold">{t("maintenance.safety.title")}</h2>
            <p className="mt-1 text-sm">{t("maintenance.safety.help")}</p>
          </div>
        </div>
      </section>
      <div
        className="flex gap-2 overflow-x-auto pb-1"
        aria-label={t("maintenance.categoriesLabel")}
      >
        {categories.map((value) => (
          <button
            type="button"
            key={value}
            onClick={() => setCategory(value)}
            className={`min-h-11 shrink-0 rounded-xl px-4 text-sm font-semibold ${category === value ? "bg-primary text-content-inverse" : "bg-surface-raised text-content-secondary"}`}
          >
            {t(`maintenance.categories.${value}`)}
          </button>
        ))}
      </div>
      <label className="relative block">
        <span className="sr-only">{t("maintenance.search")}</span>
        <Search className="absolute left-3 top-3.5 size-4 text-content-muted" />
        <input
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          placeholder={t("maintenance.search")}
          className="min-h-11 w-full rounded-xl bg-surface-raised pl-10 pr-3 shadow-sm"
        />
      </label>
      {loading ? (
        <LoadingState title={t("maintenance.loading")} />
      ) : error ? (
        <EmptyState
          title={t("maintenance.error")}
          description={t("maintenance.errorHelp")}
          action={
            <button
              className="app-button-secondary"
              onClick={() => void load()}
            >
              {t("common.retry")}
            </button>
          }
        />
      ) : items.length === 0 ? (
        <EmptyState
          title={t("maintenance.empty")}
          description={t("maintenance.emptyHelp")}
        />
      ) : (
        <div className="grid gap-3 lg:grid-cols-2">
          {items.map((item) => (
            <article
              key={`${item.category}:${item.id}`}
              className="rounded-2xl bg-surface-raised p-4 shadow-sm"
            >
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <p className="text-xs uppercase tracking-wide text-content-muted">
                    {t(`maintenance.actions.${item.action}`)}
                  </p>
                  <h2 className="truncate font-semibold">{item.label}</h2>
                </div>
                <Badge tone={item.deletable ? "success" : "warning"}>
                  {item.deletable
                    ? t("maintenance.ready")
                    : t("maintenance.review")}
                </Badge>
              </div>
              {Object.keys(item.counts).length > 0 && (
                <dl className="mt-3 flex flex-wrap gap-2">
                  {Object.entries(item.counts).map(([key, value]) => (
                    <div
                      key={key}
                      className="rounded-lg bg-surface px-2 py-1 text-xs"
                    >
                      <dt className="inline text-content-muted">
                        {t(`maintenance.counts.${key}`, key)}:{" "}
                      </dt>
                      <dd className="inline font-semibold">{value}</dd>
                    </div>
                  ))}
                </dl>
              )}
              {item.blockers.length > 0 && (
                <ul className="mt-3 space-y-1 text-sm text-warning">
                  {item.blockers.map((blocker) => (
                    <li key={blocker} className="flex gap-2">
                      <AlertTriangle className="mt-0.5 size-4 shrink-0" />
                    {t(`maintenance.blockers.${blocker}`)}
                    </li>
                  ))}
                </ul>
              )}
              <button
                type="button"
                disabled={!item.deletable}
                onClick={async () => {
                  const current = await maintenanceApi.preflight(item);
                  setSelected(current);
                }}
                className="app-button-secondary mt-4 w-full disabled:opacity-50"
              >
                <DatabaseZap className="size-4" />
                {t("maintenance.preflight")}
              </button>
            </article>
          ))}
        </div>
      )}
      <Dialog
        open={Boolean(selected)}
        onClose={() => setSelected(null)}
        label={t("maintenance.confirm.title")}
        className="p-5 sm:max-w-lg"
      >
        {selected && (
          <Confirmation
            item={selected}
            onCancel={() => setSelected(null)}
            onDone={() => {
              setSelected(null);
              toast.success(t("maintenance.success"));
              void load();
            }}
          />
        )}
      </Dialog>
    </div>
  );
}

function Confirmation({
  item,
  onCancel,
  onDone,
}: {
  item: MaintenanceItem;
  onCancel: () => void;
  onDone: () => void;
}) {
  const { t } = useTranslation();
  const toast = useToast();
  const [confirmation, setConfirmation] = useState("");
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setBusy(true);
    try {
      await maintenanceApi.execute(item, confirmation, reason);
      onDone();
    } catch {
      toast.error(t("maintenance.executeError"));
      setBusy(false);
    }
  };
  return (
    <form onSubmit={submit} className="space-y-4">
      <div className="flex items-start gap-3 rounded-xl bg-danger-subtle p-4 text-danger">
        <AlertTriangle className="mt-0.5 size-5 shrink-0" />
        <p className="text-sm">
          {t("maintenance.confirm.help", {
            action: t(`maintenance.actions.${item.action}`),
            label: item.label,
          })}
        </p>
      </div>
      <label className="grid gap-1 text-sm">
        <span>
          {t("maintenance.confirm.typeLabel", { label: item.confirmation })}
        </span>
        <input
          value={confirmation}
          onChange={(event) => setConfirmation(event.target.value)}
          required
          autoComplete="off"
          className="min-h-11 rounded-xl bg-surface px-3"
        />
      </label>
      <label className="grid gap-1 text-sm">
        <span>{t("maintenance.confirm.reason")}</span>
        <textarea
          value={reason}
          onChange={(event) => setReason(event.target.value)}
          minLength={5}
          maxLength={1000}
          required
          className="min-h-24 rounded-xl bg-surface p-3"
        />
      </label>
      <div className="flex gap-2">
        <button
          type="button"
          onClick={onCancel}
          className="app-button-secondary flex-1"
        >
          {t("common.cancel")}
        </button>
        <button
          disabled={
            busy ||
            confirmation !== item.confirmation ||
            reason.trim().length < 5
          }
          className="app-button-primary flex-1 bg-danger"
        >
          <CheckCircle2 className="size-4" />
          {t("maintenance.confirm.execute")}
        </button>
      </div>
    </form>
  );
}
