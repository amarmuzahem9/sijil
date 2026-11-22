import { useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';

import { ApiError, NETWORK_ERROR_MESSAGE } from '../../../lib/api';

interface StateApi {
  deactivate: (id: number) => Promise<unknown>;
  reactivate: (id: number) => Promise<unknown>;
  remove: (id: number) => Promise<unknown>;
}

/**
 * Shared deactivate / reactivate / delete handling for the settings tabs. After any change every
 * settings list is refreshed (an area's tower count and «in use» depend on the towers).
 */
export function useItemActions(api: StateApi) {
  const queryClient = useQueryClient();
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);

  const refresh = () => queryClient.invalidateQueries({ queryKey: ['settings'] });

  async function run(action: () => Promise<unknown>, done: string): Promise<boolean> {
    setBusy(true);
    try {
      await action();
      setNotice(done);
      await refresh();
      return true;
    } catch (err) {
      setNotice(err instanceof ApiError ? err.message : NETWORK_ERROR_MESSAGE);
      return false;
    } finally {
      setBusy(false);
    }
  }

  return {
    busy,
    notice,
    clearNotice: () => setNotice(null),
    saved: async () => {
      setNotice('تم الحفظ');
      await refresh();
    },
    setActive: (id: number, active: boolean) =>
      run(() => (active ? api.reactivate(id) : api.deactivate(id)), 'تم الحفظ'),
    remove: (id: number) => run(() => api.remove(id), 'تم الحذف'),
  };
}
