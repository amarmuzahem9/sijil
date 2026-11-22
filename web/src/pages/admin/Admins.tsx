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
import { ConfirmDialog } from '../../components/ConfirmDialog';
import { ResetPasswordDialog } from '../../components/ResetPasswordDialog';
import { accountsApi } from '../../lib/accounts';
import type { Account } from '../../lib/accounts';
import { ApiError, NETWORK_ERROR_MESSAGE } from '../../lib/api';
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

/** «الأدمنية والصلاحيات»: main admin only (specs/002 US1 + US3). */
export default function Admins() {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const admins = useQuery({ queryKey: QUERY_KEY, queryFn: () => accountsApi.list('admins') });
  const [adding, setAdding] = useState(false);
  const [editing, setEditing] = useState<Account | null>(null);
  const [resetting, setResetting] = useState<Account | null>(null);
  const [stopping, setStopping] = useState<Account | null>(null);
  const [archiving, setArchiving] = useState<Account | null>(null);
  const isMainAdmin = user?.role === 'super_admin';
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);

  const done = async () => {
    setNotice('تم الحفظ');
    await queryClient.invalidateQueries({ queryKey: QUERY_KEY });
  };

  async function create(values: AccountFormValues) {
    await accountsApi.create('admins', values);
    setAdding(false);
    await done();
  }

  async function update(values: AccountFormValues) {
    if (!editing) return;
    await accountsApi.update('admins', editing.id, {
      name: values.name,
      phone: values.phone,
      permissions: values.permissions,
    });
    setEditing(null);
    await done();
  }

  async function reset(temporaryPassword: string) {
    if (!resetting) return;
    await accountsApi.resetPassword('admins', resetting.id, temporaryPassword);
    setResetting(null);
    await done();
  }

  async function archive(account: Account) {
    setBusy(true);
    try {
      await accountsApi.archive(account.id);
      setArchiving(null);
      setNotice('نُقل الحساب إلى الأرشيف');
      await queryClient.invalidateQueries({ queryKey: ['accounts'] });
    } catch (err) {
      setNotice(err instanceof ApiError ? err.message : NETWORK_ERROR_MESSAGE);
    } finally {
      setBusy(false);
    }
  }

  async function setActive(account: Account, active: boolean) {
    setBusy(true);
    try {
      await (active
        ? accountsApi.reactivate('admins', account.id)
        : accountsApi.deactivate('admins', account.id));
      setStopping(null);
      await done();
    } catch (err) {
      setNotice(err instanceof ApiError ? err.message : NETWORK_ERROR_MESSAGE);
    } finally {
      setBusy(false);
    }
  }

  // The main admin row: no actions, no switches (spec FR-002, US3 scenario 5).
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
    actions: (
      <>
        <Button size="small" onClick={() => setEditing(a)}>
          تعديل
        </Button>
        <Button size="small" color="warning" onClick={() => setResetting(a)}>
          تصفير كلمة السر
        </Button>
        {a.is_active ? (
          <Button size="small" color="error" onClick={() => setStopping(a)}>
            إيقاف
          </Button>
        ) : (
          <Button size="small" color="success" disabled={busy} onClick={() => setActive(a, true)}>
            إعادة تفعيل
          </Button>
        )}
        {isMainAdmin && (
          <Button size="small" color="error" onClick={() => setArchiving(a)}>
            حذف
          </Button>
        )}
      </>
    ),
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
      <AccountDialog
        open={editing !== null}
        title="تعديل الأدمن"
        mode="edit"
        withPermissions
        initial={editing ?? undefined}
        onSubmit={update}
        onClose={() => setEditing(null)}
      />
      <ResetPasswordDialog
        open={resetting !== null}
        subject="الأدمن"
        name={resetting?.name ?? ''}
        onSubmit={reset}
        onClose={() => setResetting(null)}
      />
      <ConfirmDialog
        open={stopping !== null}
        title="إيقاف الأدمن"
        message={`إيقاف حساب ${stopping?.name ?? ''}؟ سيُسجَّل خروجه فوراً ولن يستطيع الدخول.`}
        confirmLabel="إيقاف"
        busy={busy}
        onConfirm={() => stopping && setActive(stopping, false)}
        onClose={() => setStopping(null)}
      />
      <ConfirmDialog
        open={archiving !== null}
        title="حذف الأدمن"
        message={`نقل حساب ${archiving?.name ?? ''} إلى الأرشيف؟ سيُسجَّل خروجه فوراً ولن يستطيع الدخول، ويمكن استرجاعه من «أرشيف الحسابات».`}
        confirmLabel="حذف"
        busy={busy}
        onConfirm={() => archiving && archive(archiving)}
        onClose={() => setArchiving(null)}
      />
      <Snackbar
        open={notice !== null}
        autoHideDuration={3000}
        onClose={() => setNotice(null)}
        message={notice}
      />
    </>
  );
}
