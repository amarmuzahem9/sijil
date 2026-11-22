import AddOutlined from '@mui/icons-material/AddOutlined';
import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import CircularProgress from '@mui/material/CircularProgress';
import Snackbar from '@mui/material/Snackbar';
import TextField from '@mui/material/TextField';
import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';

import { ConfirmDialog } from '../../../components/ConfirmDialog';
import { FormDialog } from '../../../components/FormDialog';
import { ItemList } from '../../../components/ItemList';
import { MoneyField } from '../../../components/MoneyField';
import { formatMoney, moneyText } from '../../../lib/money';
import { plansApi } from '../../../lib/settings';
import type { Plan } from '../../../lib/settings';
import { useItemActions } from './useItemActions';

const MAX_AMOUNT = 10_000_000;
const AMOUNT_ERROR = 'المبلغ يجب أن يكون عدداً صحيحاً من 0 إلى 10,000,000';

function amountError(value: number | null): string | null {
  return value === null || value > MAX_AMOUNT ? AMOUNT_ERROR : null;
}

function PlanDialog({
  plan,
  onSaved,
  onClose,
}: {
  plan: Plan | null;
  onSaved: () => Promise<void>;
  onClose: () => void;
}) {
  const [name, setName] = useState(plan?.name ?? '');
  const [trialText, setTrialText] = useState(moneyText(plan?.trial_price));
  const [trial, setTrial] = useState<number | null>(plan?.trial_price ?? null);
  const [secondText, setSecondText] = useState(moneyText(plan?.second_price));
  const [second, setSecond] = useState<number | null>(plan?.second_price ?? null);
  const [touched, setTouched] = useState(false);

  const trimmed = name.trim();
  const nameError =
    trimmed.length < 1 || trimmed.length > 100 ? 'الاسم يجب أن يكون بين 1 و100 حرف' : null;

  return (
    <FormDialog
      title={plan ? 'تعديل الفئة' : 'إضافة فئة'}
      onClose={onClose}
      onSubmit={async () => {
        setTouched(true);
        if (nameError || amountError(trial) || amountError(second)) return false;
        const body = { name: trimmed, trial_price: trial!, second_price: second! };
        if (plan) await plansApi.update(plan.id, body);
        else await plansApi.create(body);
        await onSaved();
      }}
    >
      <TextField
        label="اسم الفئة"
        value={name}
        onChange={(e) => setName(e.target.value)}
        error={touched && Boolean(nameError)}
        helperText={touched ? nameError : 'مثال: PLUS'}
        required
        fullWidth
        autoFocus
      />
      <MoneyField
        label="سعر الشهر التجريبي"
        text={trialText}
        onChange={(text, value) => {
          setTrialText(text);
          setTrial(value);
        }}
        error={touched ? amountError(trial) : null}
      />
      <MoneyField
        label="سعر الشهر الثاني"
        text={secondText}
        onChange={(text, value) => {
          setSecondText(text);
          setSecond(value);
        }}
        error={touched ? amountError(second) : null}
      />
    </FormDialog>
  );
}

/** «الفئات» (specs/004 US2). Price changes apply to new requests only (FR-006). */
export default function PlansTab() {
  const plans = useQuery({ queryKey: ['settings', 'plans'], queryFn: plansApi.list });
  const actions = useItemActions(plansApi);
  const [editing, setEditing] = useState<Plan | 'new' | null>(null);
  const [deleting, setDeleting] = useState<Plan | null>(null);

  return (
    <>
      <Box sx={{ display: 'flex', justifyContent: 'flex-end', mb: 2 }}>
        <Button variant="contained" startIcon={<AddOutlined />} onClick={() => setEditing('new')}>
          إضافة فئة
        </Button>
      </Box>
      {plans.isPending && <CircularProgress aria-label="جارٍ التحميل" />}
      {plans.isError && <Alert severity="error">{plans.error.message}</Alert>}
      {plans.isSuccess && (
        <ItemList
          rows={plans.data}
          emptyText="لا توجد فئات بعد"
          columns={[
            { header: 'الفئة', render: (p) => <bdi>{p.name}</bdi> },
            { header: 'الشهر التجريبي', render: (p) => formatMoney(p.trial_price) },
            { header: 'الشهر الثاني', render: (p) => formatMoney(p.second_price) },
          ]}
          actions={(p) => (
            <>
              <Button size="small" onClick={() => setEditing(p)}>
                تعديل
              </Button>
              {p.is_active ? (
                <Button
                  size="small"
                  color="warning"
                  disabled={actions.busy}
                  onClick={() => actions.setActive(p.id, false)}
                >
                  إيقاف
                </Button>
              ) : (
                <Button
                  size="small"
                  color="success"
                  disabled={actions.busy}
                  onClick={() => actions.setActive(p.id, true)}
                >
                  تفعيل
                </Button>
              )}
              {!p.in_use && (
                <Button size="small" color="error" onClick={() => setDeleting(p)}>
                  حذف
                </Button>
              )}
            </>
          )}
        />
      )}
      {editing !== null && (
        <PlanDialog
          plan={editing === 'new' ? null : editing}
          onClose={() => setEditing(null)}
          onSaved={async () => {
            setEditing(null);
            await actions.saved();
          }}
        />
      )}
      <ConfirmDialog
        open={deleting !== null}
        title="حذف الفئة"
        message={`حذف الفئة «${deleting?.name ?? ''}» نهائياً؟ يمكن الحذف فقط لأنها غير مستعملة.`}
        confirmLabel="حذف"
        busy={actions.busy}
        onConfirm={async () => {
          if (deleting && (await actions.remove(deleting.id))) setDeleting(null);
        }}
        onClose={() => setDeleting(null)}
      />
      <Snackbar
        open={actions.notice !== null}
        autoHideDuration={4000}
        onClose={actions.clearNotice}
        message={actions.notice}
      />
    </>
  );
}
