/**
 * One place for every HTTP call of the client.
 *
 * `VITE_API_URL` is the address of the Flask API (http://localhost:8000 by default); the
 * token is attached here and nowhere else, so a page cannot forget the Authorization
 * header.  Non-2xx answers are turned into `ApiError`, which keeps the status code for
 * the pages (401 means "log in again", 404 means "not found", 400 carries the message).
 */
export const API_URL = (import.meta.env.VITE_API_URL ?? 'http://localhost:8000').replace(/\/$/, '');
export const DEFAULT_TIMEOUT_MS = 15_000;

export class ApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

interface RequestOptions {
  method?: 'GET' | 'POST' | 'PUT' | 'DELETE';
  body?: unknown;
  token?: string | null;
  signal?: AbortSignal;
  timeoutMs?: number;
}

function errorMessage(payload: unknown, status: number): string {
  if (
    typeof payload === 'object' &&
    payload !== null &&
    'error' in payload &&
    typeof (payload as { error: unknown }).error === 'string'
  ) {
    return (payload as { error: string }).error;
  }
  return `Request failed with status ${status}`;
}

/** Perform one JSON request and return its parsed body. */
export async function apiRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const headers: Record<string, string> = { Accept: 'application/json' };
  if (options.body !== undefined) {
    headers['Content-Type'] = 'application/json';
  }
  if (options.token) {
    headers.Authorization = `Bearer ${options.token}`;
  }

  const controller = new AbortController();
  const timeout = window.setTimeout(
    () => controller.abort(),
    options.timeoutMs ?? DEFAULT_TIMEOUT_MS,
  );
  const abortFromCaller = () => controller.abort();
  if (options.signal) {
    if (options.signal.aborted) {
      controller.abort();
    } else {
      options.signal.addEventListener('abort', abortFromCaller, { once: true });
    }
  }

  let response: Response;
  let text: string;
  try {
    response = await fetch(`${API_URL}${path}`, {
      method: options.method ?? 'GET',
      headers,
      body: options.body === undefined ? undefined : JSON.stringify(options.body),
      signal: controller.signal,
    });
    // Reading the body is part of the request: a server that sends headers and then
    // stalls must not keep the page waiting forever.
    text = await response.text();
  } catch (cause) {
    if (controller.signal.aborted && !options.signal?.aborted) {
      throw new ApiError(408, 'Request timed out');
    }
    throw cause;
  } finally {
    window.clearTimeout(timeout);
    options.signal?.removeEventListener('abort', abortFromCaller);
  }

  let payload: unknown = null;
  if (text) {
    try {
      payload = JSON.parse(text) as unknown;
    } catch {
      payload = text;
    }
  }

  if (!response.ok) {
    throw new ApiError(response.status, errorMessage(payload, response.status));
  }
  return payload as T;
}
