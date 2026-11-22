import Alert from '@mui/material/Alert';
import Button from '@mui/material/Button';
import CircularProgress from '@mui/material/CircularProgress';
import Snackbar from '@mui/material/Snackbar';
import Typography from '@mui/material/Typography';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';

import { ROLE_LABELS } from '../../auth/roles';
import { AccountList } from '../../components/AccountList';
import type { AccountRow } from '../../components/AccountList';
import { accountsApi } from '../../lib/accounts';
import type { ArchivedAccount } from '../../lib/accounts';
import { ApiError, NETWORK_ERROR_MESSAGE } from '../../lib/api';
import { formatBaghdad } from '../../lib/time';

const QUERY_KEY = ['accounts', 'archive'] as const;

function ArchiveInfo({ account }: { account: ArchivedAccount }) {
  return (
    <Typography variant="body2" color="text.secondary" component="div">
      {ROLE_LABELS[account.role]} · أُرشف {formatBaghdad(account.archived_at)}
      {account.archived_by ? ` · بواسطة ${account.archived_by.name}` : ''}
    </Typography>
  );
}

/** «أرشيف الحسابات»: main admin only (docs/system.md §3.6, specs/003). */
export default function Archive() {
  const queryClient = useQueryClient();
  const archived = useQuery({ queryKey: QUERY_KEY, queryFn: accountsApi.listArchived });
  const [busyId, setBusyId] = useState<number | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  async function restore(account: ArchivedAccount) {
    setBusyId(account.id);
    try {
      await accountsApi.restore(account.id);
      setNotice('تم الاسترجاع، الحساب موقوف حتى تفعّله');
      await queryClient.invalidateQueries({ queryKey: ['accounts'] });
    } catch (err) {
      setNotice(err instanceof ApiError ? err.message : NETWORK_ERROR_MESSAGE);
    } finally {
      setBusyId(null);
    }
  }

  const rows: AccountRow[] = (archived.data ?? []).map((a) => ({
    id: a.id,
    name: a.name,
    phone: a.phone,
    isActive: null,
    extra: <ArchiveInfo account={a} />,
    actions: (
      <Button size="small" disabled={busyId === a.id} onClick={() => restore(a)}>
        استرجاع
      </Button>
    ),
  }));

  return (
    <>
      <Typography component="h1" variant="h5" sx={{ fontWeight: 700, mb: 2 }}>
        أرشيف الحسابات
      </Typography>
      {archived.isPending && <CircularProgress aria-label="جارٍ التحميل" />}
      {archived.isError && <Alert severity="error">{archived.error.message}</Alert>}
      {archived.isSuccess && (
        <AccountList rows={rows} extraHeader="الأرشفة" emptyText="لا توجد حسابات مؤرشفة" />
      )}
      <Snackbar
        open={notice !== null}
        autoHideDuration={4000}
        onClose={() => setNotice(null)}
        message={notice}
      />
    </>
  );
}
