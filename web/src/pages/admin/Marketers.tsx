import PersonAddAlt1Outlined from '@mui/icons-material/PersonAddAlt1Outlined';
import SearchOutlined from '@mui/icons-material/SearchOutlined';
import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import CircularProgress from '@mui/material/CircularProgress';
import InputAdornment from '@mui/material/InputAdornment';
import Snackbar from '@mui/material/Snackbar';
import TextField from '@mui/material/TextField';
import ToggleButton from '@mui/material/ToggleButton';
import ToggleButtonGroup from '@mui/material/ToggleButtonGroup';
import Typography from '@mui/material/Typography';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useMemo, useState } from 'react';

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
import { normalizePhone } from '../../lib/phone';

const QUERY_KEY = ['accounts', 'marketers'] as const;
type StateFilter = 'all' | 'active' | 'inactive';

/** «المسوّقون» — `marketers` permission or main admin (specs/002 US2). */
export default function Marketers() {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const marketers = useQuery({ queryKey: QUERY_KEY, queryFn: () => accountsApi.list('marketers') });
  const [search, setSearch] = useState('');
  const [state, setState] = useState<StateFilter>('all');
  const [adding, setAdding] = useState(false);
  const [editing, setEditing] = useState<Account | null>(null);
  const [resetting, setResetting] = useState<Account | null>(null);
  const [stopping, setStopping] = useState<Account | null>(null);
  const [archiving, setArchiving] = useState<Account | null>(null);
  const isMainAdmin = user?.role === 'super_admin';
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);

  const refresh = () => queryClient.invalidateQueries({ queryKey: QUERY_KEY });
  const done = async () => {
    setNotice('تم الحفظ');
    await refresh();
  };
  const fail = (err: unknown) =>
    setNotice(err instanceof ApiError ? err.message : NETWORK_ERROR_MESSAGE);

  async function create(values: AccountFormValues) {
    await accountsApi.create('marketers', {
      name: values.name,
      phone: values.phone,
      temporary_password: values.temporary_password,
    });
    setAdding(false);
    await done();
  }

  async function update(values: AccountFormValues) {
    if (!editing) return;
    await accountsApi.update('marketers', editing.id, { name: values.name, phone: values.phone });
    setEditing(null);
    await done();
  }

  async function reset(temporaryPassword: string) {
    if (!resetting) return;
    await accountsApi.resetPassword('marketers', resetting.id, temporaryPassword);
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
        ? accountsApi.reactivate('marketers', account.id)
        : accountsApi.deactivate('marketers', account.id));
      setStopping(null);
      await done();
    } catch (err) {
      fail(err);
    } finally {
      setBusy(false);
    }
  }

  const visible = useMemo(() => {
    const q = search.trim();
    const qPhone = normalizePhone(q) ?? q.replace(/\D/g, '');
    return (marketers.data ?? []).filter((m) => {
      if (state === 'active' && !m.is_active) return false;
      if (state === 'inactive' && m.is_active) return false;
      if (!q) return true;
      return m.name.includes(q) || (qPhone.length > 0 && m.phone.includes(qPhone));
    });
  }, [marketers.data, search, state]);

  const rows: AccountRow[] = visible.map((m) => ({
    id: m.id,
    name: m.name,
    phone: m.phone,
    isActive: m.is_active,
    actions: (
      <>
        <Button size="small" onClick={() => setEditing(m)}>
          تعديل
        </Button>
        <Button size="small" color="warning" onClick={() => setResetting(m)}>
          تصفير كلمة السر
        </Button>
        {m.is_active ? (
          <Button size="small" color="error" onClick={() => setStopping(m)}>
            إيقاف
          </Button>
        ) : (
          <Button size="small" color="success" disabled={busy} onClick={() => setActive(m, true)}>
            إعادة تفعيل
          </Button>
        )}
        {isMainAdmin && (
          <Button size="small" color="error" onClick={() => setArchiving(m)}>
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
          المسوّقون
        </Typography>
        <Button
          variant="contained"
          startIcon={<PersonAddAlt1Outlined />}
          onClick={() => setAdding(true)}
        >
          إضافة مسوّق
        </Button>
      </Box>

      <Box sx={{ display: 'flex', gap: 1.5, mb: 2, flexWrap: 'wrap' }}>
        <TextField
          size="small"
          placeholder="بحث بالاسم أو الهاتف"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          sx={{ flexGrow: 1, minWidth: 200 }}
          slotProps={{
            input: {
              startAdornment: (
                <InputAdornment position="start">
                  <SearchOutlined />
                </InputAdornment>
              ),
            },
          }}
        />
        <ToggleButtonGroup
          size="small"
          exclusive
          value={state}
          onChange={(_, v: StateFilter | null) => v && setState(v)}
          aria-label="الحالة"
        >
          <ToggleButton value="all">الكل</ToggleButton>
          <ToggleButton value="active">فعّال</ToggleButton>
          <ToggleButton value="inactive">موقوف</ToggleButton>
        </ToggleButtonGroup>
      </Box>

      {marketers.isPending && <CircularProgress aria-label="جارٍ التحميل" />}
      {marketers.isError && <Alert severity="error">{marketers.error.message}</Alert>}
      {marketers.isSuccess && <AccountList rows={rows} emptyText="لا يوجد مسوّقون" />}

      <AccountDialog
        open={adding}
        title="إضافة مسوّق"
        mode="create"
        withPermissions={false}
        onSubmit={create}
        onClose={() => setAdding(false)}
      />
      <AccountDialog
        open={editing !== null}
        title="تعديل المسوّق"
        mode="edit"
        withPermissions={false}
        initial={editing ?? undefined}
        onSubmit={update}
        onClose={() => setEditing(null)}
      />
      <ResetPasswordDialog
        open={resetting !== null}
        subject="المسوّق"
        name={resetting?.name ?? ''}
        onSubmit={reset}
        onClose={() => setResetting(null)}
      />
      <ConfirmDialog
        open={stopping !== null}
        title="إيقاف المسوّق"
        message={`إيقاف حساب ${stopping?.name ?? ''}؟ سيُسجَّل خروجه فوراً ولن يستطيع الدخول.`}
        confirmLabel="إيقاف"
        busy={busy}
        onConfirm={() => stopping && setActive(stopping, false)}
        onClose={() => setStopping(null)}
      />
      <ConfirmDialog
        open={archiving !== null}
        title="حذف المسوّق"
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
