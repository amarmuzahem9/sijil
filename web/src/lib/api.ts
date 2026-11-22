/**
 * API client. The access token lives in memory only (never localStorage — research.md R2);
 * the long-lived refresh token is an httpOnly cookie the browser sends to /api/auth only.
 */
export type Role = 'super_admin' | 'admin' | 'marketer';

export interface User {
  id: number;
  name: string;
  phone: string;
  role: Role;
  permissions: string[];
  must_change_password: boolean;
}

export interface TokenResponse {
  access_token: string;
  token_type: 'bearer';
  expires_in: number;
  user: User;
}

export const NETWORK_ERROR_MESSAGE = 'تعذّر الاتصال، حاول مرة أخرى';
const GENERIC_ERROR_MESSAGE = 'حدث خطأ غير متوقع، حاول مرة أخرى';
const TIMEOUT_MS = 15000;

export class ApiError extends Error {
  readonly code: string;
  readonly status: number;
  readonly extra: Record<string, unknown>;

  constructor(code: string, message: string, status: number, extra: Record<string, unknown> = {}) {
    super(message);
    this.code = code;
    this.status = status;
    this.extra = extra;
  }
}

let accessToken: string | null = null;

/** Notified when the server ends the session (revoked / inactive). Set by AuthProvider. */
type SessionEndedListener = (code: string, message: string) => void;
let onSessionEnded: SessionEndedListener | null = null;

export function setAccessToken(token: string | null): void {
  accessToken = token;
}

export function setSessionEndedListener(listener: SessionEndedListener | null): void {
  onSessionEnded = listener;
}

/** Notified on a `forbidden` 403 so the current user (and permissions) is re-read (002 R2). */
let onForbidden: (() => void) | null = null;

export function setForbiddenListener(listener: (() => void) | null): void {
  onForbidden = listener;
}

async function send(path: string, init: RequestInit, withAuth: boolean): Promise<Response> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), TIMEOUT_MS);
  const headers = new Headers(init.headers);
  if (init.body !== undefined) headers.set('Content-Type', 'application/json');
  if (withAuth && accessToken) headers.set('Authorization', `Bearer ${accessToken}`);
  try {
    return await fetch(path, {
      ...init,
      headers,
      credentials: 'same-origin',
      signal: controller.signal,
    });
  } catch {
    throw new ApiError('network_error', NETWORK_ERROR_MESSAGE, 0);
  } finally {
    clearTimeout(timer);
  }
}

async function toError(res: Response): Promise<ApiError> {
  try {
    const body = await res.json();
    if (body && typeof body.code === 'string' && typeof body.message === 'string') {
      const { code, message, ...extra } = body;
      return new ApiError(code, message, res.status, extra);
    }
  } catch {
    /* not JSON (e.g. proxy error page) */
  }
  return new ApiError(
    res.status >= 500 ? 'server_error' : 'unknown_error',
    res.status === 502 || res.status === 503 ? NETWORK_ERROR_MESSAGE : GENERIC_ERROR_MESSAGE,
    res.status,
  );
}

let refreshInFlight: Promise<TokenResponse> | null = null;

/** Exchange the refresh cookie for a new access token (deduplicated across callers). */
export function refreshSession(): Promise<TokenResponse> {
  refreshInFlight ??= (async () => {
    try {
      const res = await send('/api/auth/refresh', { method: 'POST' }, false);
      if (!res.ok) throw await toError(res);
      const body = (await res.json()) as TokenResponse;
      setAccessToken(body.access_token);
      return body;
    } finally {
      refreshInFlight = null;
    }
  })();
  return refreshInFlight;
}

interface FetchOptions {
  method?: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE';
  body?: unknown;
  auth?: boolean;
  /** Extra request headers (e.g. `X-Client-Id` for drafts, specs/005 research.md R3). */
  headers?: Record<string, string>;
}

export async function apiFetch<T>(path: string, options: FetchOptions = {}): Promise<T> {
  const { method = 'GET', body, auth = true, headers } = options;
  const init: RequestInit = {
    method,
    body: body === undefined ? undefined : JSON.stringify(body),
    headers,
  };

  let res = await send(path, init, auth);
  if (auth && res.status === 401) {
    const err = await toError(res);
    if (err.code !== 'token_expired') {
      notifyEnded(err);
      throw err;
    }
    try {
      await refreshSession();
    } catch (refreshErr) {
      if (refreshErr instanceof ApiError) notifyEnded(refreshErr);
      throw refreshErr;
    }
    res = await send(path, init, auth); // retry once
  }
  if (!res.ok) {
    const err = await toError(res);
    if (auth) {
      notifyEnded(err);
      if (err.code === 'forbidden') onForbidden?.();
    }
    throw err;
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

function notifyEnded(err: ApiError): void {
  if (['session_revoked', 'account_inactive', 'not_authenticated'].includes(err.code)) {
    setAccessToken(null);
    onSessionEnded?.(err.code, err.message);
  }
}
