import {
  createContext,
  ReactNode,
  useCallback,
  useContext,
  useRef,
  useState,
} from "react";
import { AlertTriangle } from "lucide-react";
import { useTranslation } from "react-i18next";

import { Dialog } from "../components/ui";

interface ConfirmationOptions {
  title?: string;
  confirmLabel?: string;
  danger?: boolean;
}

interface PromptOptions extends ConfirmationOptions {
  inputLabel?: string;
  minimumLength?: number;
}

interface ConfirmationApi {
  confirm: (message: string, options?: ConfirmationOptions) => Promise<boolean>;
  prompt: (message: string, options?: PromptOptions) => Promise<string | null>;
}

type DialogRequest = {
  mode: "confirm" | "prompt";
  message: string;
  options: PromptOptions;
};

const ConfirmationContext = createContext<ConfirmationApi | null>(null);

export function ConfirmationProvider({ children }: { children: ReactNode }) {
  const { t } = useTranslation();
  const [request, setRequest] = useState<DialogRequest | null>(null);
  const [value, setValue] = useState("");
  const resolver = useRef<((result: boolean | string | null) => void) | null>(
    null,
  );

  const finish = useCallback((result: boolean | string | null) => {
    resolver.current?.(result);
    resolver.current = null;
    setRequest(null);
    setValue("");
  }, []);
  const confirm = useCallback(
    (message: string, options: ConfirmationOptions = {}) =>
      new Promise<boolean>((resolve) => {
        resolver.current = (result) => resolve(result === true);
        setRequest({ mode: "confirm", message, options });
      }),
    [],
  );
  const prompt = useCallback(
    (message: string, options: PromptOptions = {}) =>
      new Promise<string | null>((resolve) => {
        resolver.current = (result) => resolve(typeof result === "string" ? result : null);
        setValue("");
        setRequest({ mode: "prompt", message, options });
      }),
    [],
  );
  const minimumLength = request?.options.minimumLength ?? 1;

  return (
    <ConfirmationContext.Provider value={{ confirm, prompt }}>
      {children}
      <Dialog
        open={request !== null}
        onClose={() => finish(request?.mode === "confirm" ? false : null)}
        label={request?.options.title || t("confirmation.title")}
        className="p-5 sm:max-w-lg"
      >
        {request && (
          <form
            onSubmit={(event) => {
              event.preventDefault();
              finish(request.mode === "confirm" ? true : value.trim());
            }}
            className="space-y-4"
          >
            <div
              className={`flex items-start gap-3 rounded-xl p-4 ${request.options.danger ? "bg-danger-subtle text-danger" : "bg-primary-subtle text-content-primary"}`}
            >
              <AlertTriangle className="mt-0.5 size-5 shrink-0" />
              <div>
                <h2 className="font-semibold">
                  {request.options.title || t("confirmation.title")}
                </h2>
                <p className="mt-1 text-sm text-content-secondary">
                  {request.message}
                </p>
              </div>
            </div>
            {request.mode === "prompt" && (
              <label className="grid gap-1 text-sm">
                <span>
                  {request.options.inputLabel || t("confirmation.reason")}
                </span>
                <textarea
                  autoFocus
                  value={value}
                  onChange={(event) => setValue(event.target.value)}
                  minLength={minimumLength}
                  maxLength={2000}
                  required
                  className="min-h-24 rounded-xl bg-surface p-3"
                />
              </label>
            )}
            <div className="flex gap-2">
              <button
                type="button"
                onClick={() =>
                  finish(request.mode === "confirm" ? false : null)
                }
                className="app-button-secondary flex-1"
              >
                {t("common.cancel")}
              </button>
              <button
                disabled={
                  request.mode === "prompt" &&
                  value.trim().length < minimumLength
                }
                className={`${request.options.danger ? "app-button-danger" : "app-button-primary"} flex-1`}
              >
                {request.options.confirmLabel || t("common.confirm")}
              </button>
            </div>
          </form>
        )}
      </Dialog>
    </ConfirmationContext.Provider>
  );
}

export function useConfirmation(): ConfirmationApi {
  const value = useContext(ConfirmationContext);
  if (!value)
    throw new Error("useConfirmation must be used inside ConfirmationProvider");
  return value;
}
