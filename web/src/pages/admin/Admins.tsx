import PersonAddAlt1Outlined from '@mui/icons-material/PersonAddAlt1Outlined';
import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Chip from '@mui/material/Chip';
import CircularProgress from '@mui/material/CircularProgress';
import Snackbar from '@mui/material/Snackbar';
import Typography from '@mui/material/Typography';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';

import { useAuth } from '../../auth/AuthProvider';
import { AccountDialog } from '../../components/AccountDialog';
import type { AccountFormValues } from '../../components/AccountDialog';
import { AccountList } from '../../components/AccountList';
import type { AccountRow } from '../../components/AccountList';
import { accountsApi } from '../../lib/accounts';
import type { Account } from '../../lib/accounts';
import { PERMISSION_LABELS } from '../../lib/labels';

const QUERY_KEY = ['accounts', 'admins'] as const;

function PermissionChips({ account }: { account: Account }) {
  if (account.permissions.length === 0) {
    return (
      <Typography variant="body2" color="text.secondary">
        بلا صلاحيات
      </Typography>
    );
  }
  return (
    <Box sx={{ display: 'flex', gap: 0.5, flexWrap: 'wrap' }}>
      {account.permissions.map((p) => (
        <Chip key={p} size="small" label={PERMISSION_LABELS[p]} />
      ))}
    </Box>
  );
}

/** «الأدمنية والصلاحيات» — main admin only (specs/002 US1; editing arrives with US3). */
export default function Admins() {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const [adding, setAdding] = useState(false);
  const [saved, setSaved] = useState(false);
  const admins = useQuery({ queryKey: QUERY_KEY, queryFn: () => accountsApi.list('admins') });

  async function create(values: AccountFormValues) {
    await accountsApi.create('admins', values);
    setAdding(false);
    setSaved(true);
    await queryClient.invalidateQueries({ queryKey: QUERY_KEY });
  }

  const mainRow: AccountRow[] = user
    ? [
        {
          id: user.id,
          name: user.name,
          phone: user.phone,
          isActive: null,
          extra: <Chip size="small" color="primary" label="أدمن رئيسي · كل الصلاحيات" />,
        },
      ]
    : [];
  const rows: AccountRow[] = (admins.data ?? []).map((a) => ({
    id: a.id,
    name: a.name,
    phone: a.phone,
    isActive: a.is_active,
    extra: <PermissionChips account={a} />,
  }));

  return (
    <>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 2, flexWrap: 'wrap' }}>
        <Typography component="h1" variant="h5" sx={{ fontWeight: 700, flexGrow: 1 }}>
          الأدمنية والصلاحيات
        </Typography>
        <Button
          variant="contained"
          startIcon={<PersonAddAlt1Outlined />}
          onClick={() => setAdding(true)}
        >
          إضافة أدمن
        </Button>
      </Box>

      {admins.isPending && <CircularProgress aria-label="جارٍ التحميل" />}
      {admins.isError && <Alert severity="error">{admins.error.message}</Alert>}
      {admins.isSuccess && (
        <AccountList
          rows={[...mainRow, ...rows]}
          extraHeader="الصلاحيات"
          emptyText="لا يوجد أدمنية"
        />
      )}

      <AccountDialog
        open={adding}
        title="إضافة أدمن"
        mode="create"
        withPermissions
        onSubmit={create}
        onClose={() => setAdding(false)}
      />
      <Snackbar
        open={saved}
        autoHideDuration={3000}
        onClose={() => setSaved(false)}
        message="تم الحفظ"
      />
    </>
  );
}
