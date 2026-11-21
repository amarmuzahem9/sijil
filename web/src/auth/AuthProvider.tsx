import { useQueryClient } from '@tanstack/react-query';
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import type { ReactNode } from 'react';

import {
  ApiError,
  apiFetch,
  refreshSession,
  setAccessToken,
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
      // Server-side session revocation endpoint arrives with US3; failures are ignored here.
      await apiFetch<void>('/api/auth/logout', { method: 'POST', auth: false });
    } catch {
      /* ignore */
    }
    clear();
  }, [clear]);

  const value = useMemo(
    () => ({ status, user, notice, login, logout, setSession }),
    [status, user, notice, login, logout, setSession],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used inside <AuthProvider>');
  return ctx;
}
