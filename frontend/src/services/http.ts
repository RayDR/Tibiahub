import { REQUEST_TIMEOUT_MS, ADMIN_ACTION_TIMEOUT_MS } from './api';

type FetchTimeoutMode = 'default' | 'admin';

type FetchJsonOptions = {
  method?: string;
  headers?: HeadersInit;
  body?: BodyInit | null;
  signal?: AbortSignal;
  timeoutMode?: FetchTimeoutMode;
};

function withTimeout(signal: AbortSignal | undefined, timeoutMs: number): AbortSignal {
  const controller = new AbortController();

  if (signal) {
    if (signal.aborted) {
      controller.abort();
    } else {
      signal.addEventListener('abort', () => controller.abort(), { once: true });
    }
  }

  window.setTimeout(() => {
    controller.abort();
  }, timeoutMs);

  return controller.signal;
}

export async function fetchJson<T>(url: string, options: FetchJsonOptions = {}): Promise<T> {
  const timeoutMs = options.timeoutMode === 'admin' ? ADMIN_ACTION_TIMEOUT_MS : REQUEST_TIMEOUT_MS;
  const response = await fetch(url, {
    method: options.method,
    headers: options.headers,
    body: options.body,
    signal: withTimeout(options.signal, timeoutMs),
  });

  if (!response.ok) {
    let detail = `HTTP ${response.status}`;
    try {
      const payload = await response.json();
      detail = payload?.detail || payload?.message || detail;
    } catch {
      // Keep default detail when response body is not JSON.
    }
    throw new Error(detail);
  }

  return response.json() as Promise<T>;
}
