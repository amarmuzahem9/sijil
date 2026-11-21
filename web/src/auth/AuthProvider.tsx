import { useQueryClient } from '@tanstack/react-query';
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react';
import type { ReactNode } from 'react';

import {
  ApiError,
  apiFetch,
  refreshSession,
  setAccessToken,
  setForbiddenListener,
  setSessionEndedListener,
} from '../lib/api';
import type { TokenResponse, User } from '../lib/api';

type Status = 'loading' | 'anonymous' | 'authenticated';

interface AuthContextValue {
  status: Status;
  user: User | null;
  /** Arabic message shown on the login screen after the server ended the session. */
  notice: string | null;
  login: (phone: string, password: string) => Promise<User>;
  logout: () => Promise<void>;
  setSession: (tokens: TokenResponse) => void;
  /** Re-read /api/auth/me so permission and name changes show without signing out. */
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const [status, setStatus] = useState<Status>('loading');
  const [user, setUser] = useState<User | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const clear = useCallback(
    (message: string | null = null) => {
      setAccessToken(null);
      queryClient.clear();
      setUser(null);
      setNotice(message);
      setStatus('anonymous');
    },
    [queryClient],
  );

  const setSession = useCallback((tokens: TokenResponse) => {
    setAccessToken(tokens.access_token);
    setUser(tokens.user);
    setNotice(null);
    setStatus('authenticated');
  }, []);

  // Restore the session from the refresh cookie on start (session survives app restarts).
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        await refreshSession();
        const me = await apiFetch<User>('/api/auth/me');
        if (!cancelled) {
          setUser(me);
          setStatus('authenticated');
        }
      } catch (err) {
        if (cancelled) return;
        const inactive = err instanceof ApiError && err.code === 'account_inactive';
        clear(inactive ? err.message : null);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [clear]);

  // The API client reports revoked sessions / deactivated accounts on any request.
  useEffect(() => {
    setSessionEndedListener((code, message) => {
      clear(code === 'account_inactive' ? message : null);
    });
    return () => setSessionEndedListener(null);
  }, [clear]);

  // Re-read the user on window focus and after any `forbidden` response (002 research R2).
  const inFlight = useRef<Promise<void> | null>(null);
  const refreshUser = useCallback(() => {
    if (status !== 'authenticated') return Promise.resolve();
    inFlight.current ??= (async () => {
      try {
        setUser(await apiFetch<User>('/api/auth/me'));
      } catch {
        /* session-ended errors are handled by the listener; network errors keep the old user */
      } finally {
        inFlight.current = null;
      }
    })();
    return inFlight.current;
  }, [status]);

  useEffect(() => {
    const onFocus = () => void refreshUser();
    window.addEventListener('focus', onFocus);
    setForbiddenListener(onFocus);
    return () => {
      window.removeEventListener('focus', onFocus);
      setForbiddenListener(null);
    };
  }, [refreshUser]);

  const login = useCallback(
    async (phone: string, password: string) => {
      const tokens = await apiFetch<TokenResponse>('/api/auth/login', {
        method: 'POST',
        body: { phone, password },
        auth: false,
      });
      setSession(tokens);
      return tokens.user;
    },
    [setSession],
  );

  const logout = useCallback(async () => {
    try {
      // Revokes this device's session on the server and clears the refresh cookie.
      await apiFetch<void>('/api/auth/logout', { method: 'POST', auth: false });
    } catch {
      /* offline: the local state is still cleared; the cookie expires server-side later */
    }
    clear();
  }, [clear]);

  const value = useMemo(
    () => ({ status, user, notice, login, logout, setSession, refreshUser }),
    [status, user, notice, login, logout, setSession, refreshUser],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used inside <AuthProvider>');
  return ctx;
}
