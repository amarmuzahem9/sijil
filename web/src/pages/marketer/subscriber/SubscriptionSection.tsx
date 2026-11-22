/**
 * «الاشتراك» (docs/system.md §5.3, specs/005 US7): area → tower of that area → plan, with both
 * prices. Choices come from /api/catalog (active items only, 004 FR-014). The server copies the
 * names and prices on every save; the client never sends prices (research.md R4).
 */
import Alert from '@mui/material/Alert';
import MenuItem from '@mui/material/MenuItem';
import Skeleton from '@mui/material/Skeleton';
import Stack from '@mui/material/Stack';
import TextField from '@mui/material/TextField';
import Typography from '@mui/material/Typography';
import { useQuery } from '@tanstack/react-query';

import type { DraftNotice } from '../../../lib/drafts';
import { formatMoney } from '../../../lib/money';
import { catalogApi } from '../../../lib/settings';
import type { DraftAutosave } from '../../../lib/useDraftAutosave';

export const CHOICE_UNAVAILABLE = 'لم يعد متاحاً، اختر من جديد';
export const NO_ACTIVE_TOWERS = 'لا توجد أبراج فعّالة';

const FIELD_NAMES: Record<DraftNotice['field'], string> = {
  area_id: 'المنطقة',
  tower_id: 'البرج',
  plan_id: 'الفئة',
};

function noticeText(n: DraftNotice): string {
  if (n.code === 'price_changed' && n.old && n.new) {
    const parts: string[] = [];
    if (n.old.trial_price !== n.new.trial_price)
      parts.push(
        `الشهر التجريبي من ${formatMoney(n.old.trial_price)} إلى ${formatMoney(n.new.trial_price)}`,
      );
    if (n.old.second_price !== n.new.second_price)
      parts.push(
        `الشهر الثاني من ${formatMoney(n.old.second_price)} إلى ${formatMoney(n.new.second_price)}`,
      );
    return `تغيّر السعر: ${parts.join('، ')}`;
  }
  return `${FIELD_NAMES[n.field]}: ${CHOICE_UNAVAILABLE}`;
}

export function SubscriptionSection({
  autosave,
  errors = {},
}: {
  autosave: Pick<DraftAutosave, 'values' | 'saveNow' | 'notices' | 'dismissNotice'>;
  errors?: Partial<Record<'area_id' | 'tower_id' | 'plan_id', string>>;
}) {
  const { values, saveNow, notices, dismissNotice } = autosave;
  const catalog = useQuery({ queryKey: ['catalog'], queryFn: catalogApi.get, staleTime: 60_000 });

  if (catalog.isPending) return <Skeleton height={160} />;
  if (catalog.isError) return <Alert severity="error">{catalog.error.message}</Alert>;

  const { areas, towers, plans } = catalog.data;
  const areaTowers = towers.filter((t) => t.area_id === values.area_id);
  const plan = plans.find((p) => p.id === values.plan_id) ?? null;

  // A saved id that is no longer offered shows as empty until the server clears it.
  const areaValue = areas.some((a) => a.id === values.area_id) ? values.area_id : '';
  const towerValue = areaTowers.some((t) => t.id === values.tower_id) ? values.tower_id : '';
  const planValue = plan ? plan.id : '';

  return (
    <Stack spacing={1.5}>
      {notices.map((n) => (
        <Alert
          key={`${n.field}-${n.code}`}
          severity={n.code === 'price_changed' ? 'info' : 'warning'}
          onClose={() => dismissNotice(n.field)}
          data-testid={`notice-${n.field}-${n.code}`}
        >
          {noticeText(n)}
        </Alert>
      ))}

      <TextField
        select
        id="field-area_id"
        label="المنطقة"
        value={areaValue ?? ''}
        error={Boolean(errors.area_id)}
        helperText={errors.area_id ?? ' '}
        onChange={(e) => {
          const id = Number(e.target.value);
          dismissNotice('area_id');
          dismissNotice('tower_id');
          saveNow({ area_id: id, tower_id: null });
        }}
        slotProps={{ htmlInput: { 'data-testid': 'field-area_id' } }}
      >
        {areas.map((a) => (
          <MenuItem key={a.id} value={a.id}>
            {a.name}
          </MenuItem>
        ))}
      </TextField>

      <TextField
        select
        id="field-tower_id"
        label="البرج"
        value={towerValue ?? ''}
        disabled={values.area_id === null || areaTowers.length === 0}
        error={Boolean(errors.tower_id)}
        helperText={
          values.area_id !== null && areaTowers.length === 0
            ? NO_ACTIVE_TOWERS
            : (errors.tower_id ?? ' ')
        }
        onChange={(e) => {
          dismissNotice('tower_id');
          saveNow({ tower_id: Number(e.target.value) });
        }}
        slotProps={{ htmlInput: { 'data-testid': 'field-tower_id' } }}
      >
        {areaTowers.map((t) => (
          <MenuItem key={t.id} value={t.id}>
            <span dir="ltr">{t.code}</span>&nbsp;· {t.name}
          </MenuItem>
        ))}
      </TextField>

      <TextField
        select
        id="field-plan_id"
        label="الفئة"
        value={planValue}
        error={Boolean(errors.plan_id)}
        helperText={errors.plan_id ?? ' '}
        onChange={(e) => {
          dismissNotice('plan_id');
          saveNow({ plan_id: Number(e.target.value) });
        }}
        slotProps={{ htmlInput: { 'data-testid': 'field-plan_id' } }}
      >
        {plans.map((p) => (
          <MenuItem key={p.id} value={p.id}>
            {p.name}
          </MenuItem>
        ))}
      </TextField>

      {plan && (
        <Typography variant="body1" data-testid="plan-prices">
          الشهر التجريبي: {formatMoney(plan.trial_price)} — الشهر الثاني:{' '}
          {formatMoney(plan.second_price)}
        </Typography>
      )}
    </Stack>
  );
}
