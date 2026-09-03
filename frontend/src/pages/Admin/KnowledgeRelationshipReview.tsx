import { useCallback, useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import {
  AlertCircle,
  Link2,
  RefreshCw,
  ShieldCheck,
  XCircle,
} from "lucide-react";
import { useToast } from "../../context/ToastContext";
import { useConfirmation } from "../../context/ConfirmationContext";
import {
  knowledgeOperationsApi,
  type KnowledgeRelationshipProvenance,
  type KnowledgeRelationshipReview,
} from "../../services/knowledge";
import { DegradedState, LoadingState, PaginationControls } from "../../components/ui";
import { clampPageSkip } from "../../utils/pagination";

type ReviewState = "resolved" | "unresolved" | "ambiguous";
const PAGE_SIZE = 10;

export default function KnowledgeRelationshipReviewPanel() {
  const { t } = useTranslation();
  const toast = useToast();
  const confirmation = useConfirmation();
  const [state, setState] = useState<ReviewState>("unresolved");
  const [items, setItems] = useState<KnowledgeRelationshipReview[]>([]);
  const [total, setTotal] = useState(0);
  const [skip, setSkip] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const [provenance, setProvenance] =
    useState<KnowledgeRelationshipProvenance | null>(null);
  const requestRef = useRef<AbortController | null>(null);
  const retrySkipRef = useRef(0);

  const load = useCallback(async (nextSkip = 0) => {
    requestRef.current?.abort();
    retrySkipRef.current = nextSkip;
    const controller = new AbortController();
    requestRef.current = controller;
    setLoading(true);
    setError(false);
    try {
      let page = await knowledgeOperationsApi.relationshipReview({ resolution_state: state, skip: nextSkip, limit: PAGE_SIZE }, controller.signal);
      if (page.items.length === 0 && page.total > 0 && nextSkip >= page.total) {
        const previousSkip = clampPageSkip(nextSkip, PAGE_SIZE, page.total);
        page = await knowledgeOperationsApi.relationshipReview({ resolution_state: state, skip: previousSkip, limit: PAGE_SIZE }, controller.signal);
      }
      if (controller.signal.aborted) return;
      setItems(page.items);
      setTotal(page.total);
      setSkip(page.skip);
    } catch (loadError: any) {
      if (loadError?.name !== "CanceledError" && loadError?.code !== "ERR_CANCELED") setError(true);
    } finally {
      if (requestRef.current === controller) {
        requestRef.current = null;
        setLoading(false);
      }
    }
  }, [state]);
  useEffect(() => {
    setItems([]);
    setTotal(0);
    setSkip(0);
    setProvenance(null);
    void load(0);
    return () => requestRef.current?.abort();
  }, [load]);

  const resolve = async (
    item: KnowledgeRelationshipReview,
    targetId: string,
  ) => {
    const value = await confirmation.prompt(
      t("knowledgeGraph.review.confirmResolve", { name: item.unresolved_name }),
      { inputLabel: t("knowledgeGraph.review.reasonPrompt"), minimumLength: 3 },
    );
    if (!value) return;
    setBusy(item.id);
    try {
      await knowledgeOperationsApi.resolveRelationship(
        item.id,
        targetId,
        value,
      );
      toast.success(t("knowledgeGraph.review.resolved"));
      await load(skip);
    } catch {
      toast.error(t("knowledgeGraph.review.actionError"));
    } finally {
      setBusy(null);
    }
  };
  const reject = async (item: KnowledgeRelationshipReview) => {
    const value = await confirmation.prompt(
      t("knowledgeGraph.review.confirmReject", { name: item.unresolved_name }),
      {
        inputLabel: t("knowledgeGraph.review.reasonPrompt"),
        minimumLength: 3,
        danger: true,
      },
    );
    if (!value) return;
    setBusy(item.id);
    try {
      await knowledgeOperationsApi.rejectRelationship(item.id, value);
      toast.success(t("knowledgeGraph.review.rejected"));
      await load(skip);
    } catch {
      toast.error(t("knowledgeGraph.review.actionError"));
    } finally {
      setBusy(null);
    }
  };
  const verify = async (item: KnowledgeRelationshipReview) => {
    const value = await confirmation.prompt(
      t("knowledgeGraph.review.confirmVerify", { name: item.target_name }),
      { inputLabel: t("knowledgeGraph.review.reasonPrompt"), minimumLength: 3 },
    );
    if (!value) return;
    setBusy(item.id);
    try {
      await knowledgeOperationsApi.verifyRelationship(item.id, value);
      toast.success(t("knowledgeGraph.review.verified"));
      await load(skip);
    } catch {
      toast.error(t("knowledgeGraph.review.actionError"));
    } finally {
      setBusy(null);
    }
  };

  return (
    <section className="space-y-3 rounded-xl border border-line bg-surface-base/30 p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h3 className="flex items-center gap-2 font-medium text-content-primary">
            <Link2 className="h-4 w-4" />
            {t("knowledgeGraph.review.title")}
          </h3>
          <p className="text-xs text-content-secondary">
            {t("knowledgeGraph.review.subtitle")}
          </p>
        </div>
        <button
          onClick={() => void load(skip)}
          className="flex min-h-11 items-center gap-2 rounded-lg border border-line px-3 text-sm"
        >
          <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
          {t("knowledgeGraph.review.refresh")}
        </button>
      </div>
      <div className="flex flex-wrap gap-2" role="tablist">
        {(["unresolved", "ambiguous", "resolved"] as const).map((value) => (
          <button
            key={value}
            role="tab"
            aria-selected={state === value}
            onClick={() => setState(value)}
            className={`min-h-11 rounded-lg px-3 text-sm ${state === value ? "bg-primary text-content-on-primary" : "border border-line text-content-secondary"}`}
          >
            {t(`knowledgeGraph.states.${value}`)}
          </button>
        ))}
      </div>
      {loading && items.length === 0 ? (
        <LoadingState title={t("common.loading")} />
      ) : error && items.length === 0 ? (
        <div className="rounded-lg bg-danger/10 p-3 text-sm text-danger">
          <AlertCircle className="mr-2 inline h-4 w-4" />
          {t("knowledgeGraph.review.loadError")}
          <button type="button" className="ml-3 underline" onClick={() => void load(retrySkipRef.current)}>{t("common.retry")}</button>
        </div>
      ) : !loading && items.length === 0 ? (
        <p className="rounded-lg border border-line p-4 text-sm text-content-secondary">
          {t("knowledgeGraph.review.empty")}
        </p>
      ) : (
        <>
        {error ? <DegradedState title={t("knowledgeGraph.review.loadError")} action={<button type="button" className="app-button-secondary app-button-sm" onClick={() => void load(retrySkipRef.current)}>{t("common.retry")}</button>} /> : null}
        <div className="grid gap-3 md:grid-cols-2">
          {items.map((item) => (
            <article
              key={item.id}
              className="rounded-xl border border-line bg-surface-base/60 p-4"
            >
              <div className="flex justify-between gap-2">
                <div>
                  <strong className="text-content-primary">
                    {item.source_name}
                  </strong>
                  <p className="text-xs text-content-secondary">
                    {t(
                      `knowledgeGraph.relationships.${item.relationship_type}`,
                    )}
                  </p>
                </div>
                <span className="text-xs text-primary">
                  {t(`knowledgeGraph.states.${item.resolution_state}`)}
                </span>
              </div>
              <p className="mt-3 text-sm text-content-primary">
                {item.target_name || item.unresolved_name}
              </p>
              <p className="mt-1 text-xs text-content-muted">
                {t("knowledgeGraph.review.source", {
                  provider:
                    item.provider_id || t("knowledgeGraph.review.local"),
                  confidence: item.confidence,
                })}
              </p>
              {item.candidates.length > 0 && (
                <div className="mt-3 space-y-2">
                  <p className="text-xs text-content-secondary">
                    {t("knowledgeGraph.review.candidates")}
                  </p>
                  {item.candidates.map((candidate) => (
                    <button
                      disabled={busy === item.id}
                      key={candidate.id}
                      onClick={() => void resolve(item, candidate.id)}
                      className="flex min-h-11 w-full items-center justify-between rounded-lg border border-success/30 px-3 text-left text-sm text-success"
                    >
                      <span>{candidate.name}</span>
                      <ShieldCheck className="h-4 w-4" />
                    </button>
                  ))}
                </div>
              )}
              <div className="mt-3 flex flex-wrap gap-2">
                <button
                  onClick={() =>
                    void knowledgeOperationsApi
                      .relationshipProvenance(item.id)
                      .then(setProvenance)
                      .catch(() =>
                        toast.error(t("knowledgeGraph.review.provenanceError")),
                      )
                  }
                  className="min-h-11 rounded-lg border border-line px-3 text-xs"
                >
                  {t("knowledgeGraph.review.provenance")}
                </button>
                {item.resolution_state === "resolved" ? (
                  <button
                    disabled={busy === item.id}
                    onClick={() => void verify(item)}
                    className="flex min-h-11 items-center gap-1 rounded-lg border border-success/30 px-3 text-xs text-success"
                  >
                    <ShieldCheck className="h-4 w-4" />
                    {t("knowledgeGraph.review.verify")}
                  </button>
                ) : (
                  <button
                    disabled={busy === item.id}
                    onClick={() => void reject(item)}
                    className="flex min-h-11 items-center gap-1 rounded-lg border border-danger/30 px-3 text-xs text-danger"
                  >
                    <XCircle className="h-4 w-4" />
                    {t("knowledgeGraph.review.reject")}
                  </button>
                )}
              </div>
            </article>
          ))}
        </div>
        <PaginationControls skip={skip} limit={PAGE_SIZE} total={total} loading={loading} onPrevious={() => void load(Math.max(0, skip - PAGE_SIZE))} onNext={() => void load(skip + PAGE_SIZE)} />
        </>
      )}
      {provenance && (
        <div className="rounded-lg border border-line bg-surface-base p-3 text-xs text-content-secondary">
          <div className="flex justify-between">
            <strong>{t("knowledgeGraph.review.provenance")}</strong>
            <button onClick={() => setProvenance(null)}>
              {t("knowledgeGraph.review.close")}
            </button>
          </div>
          <p className="mt-2">
            {t("knowledgeGraph.review.provenanceSummary", {
              provider:
                provenance.provider_id || t("knowledgeGraph.review.local"),
              count: Object.keys(provenance.safe_context).length,
            })}
          </p>
        </div>
      )}
    </section>
  );
}
