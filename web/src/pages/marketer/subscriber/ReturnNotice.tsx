/**
 * «طلب العودة للخدمة» and the numbers-conflict notice (specs/009 US1, US2; FR-003 to FR-007;
 * docs/system.md v1.10 §6.1 rows 1, 2, 2b).
 *
 * - Same person (identity) under the family number, or the phone's owner (phone) under the phone:
 *   the message with «طلب العودة للخدمة». Once chosen, the request goes to the admin; «إلغاء»
 *   withdraws it. Changing the numbers or the phone drops the choice on the server.
 * - A pending request for the same person blocks the return («يوجد طلب سابق بالانتظار…»).
 * - Conflict (national ID only): a notice with no button; sending stays allowed.
 *
 * The page gets booleans and a basis only, so nothing here can name the other subscriber.
 * `children` adds actions next to the offer (the phone basis adds «الاتصال بالإدارة»).
 */
import Alert from '@mui/material/Alert';
import Button from '@mui/material/Button';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';
import type { ReactNode } from 'react';

import type { DraftChecks, ReturnBasis } from '../../../lib/drafts';

export const RETURN_TEXT = {
  identity: 'المشترك لديه اشتراك سابق',
  phone: 'المشترك موجود سابقاً، هل يود العودة للخدمة؟',
  action: 'طلب العودة للخدمة',
  chosen: 'تم اختيار طلب العودة للخدمة: يذهب الطلب لموافقة المسؤول',
  pending: 'يوجد طلب سابق بالانتظار لهذا المشترك',
  withdraw: 'إلغاء',
  conflict: 'الرقم الوطني مسجّل سابقاً ببيانات مختلفة، سيُراجع الطلب من الإدارة',
} as const;

type Checks = DraftChecks | undefined;

export function ReturnNotice({
  basis,
  checks,
  onChoose,
  onWithdraw,
  children,
}: {
  basis: ReturnBasis;
  checks: Checks;
  onChoose: () => void;
  onWithdraw: () => void;
  children?: ReactNode;
}) {
  if (!checks?.return_available || checks.return_basis !== basis) return null;
  const withdraw = (
    <Button color="inherit" size="small" onClick={onWithdraw}>
      {RETURN_TEXT.withdraw}
    </Button>
  );
  if (checks.return_chosen && checks.return_pending)
    return (
      <Alert severity="error" data-testid="return-pending" sx={{ mb: 1 }} action={withdraw}>
        {RETURN_TEXT.pending}
      </Alert>
    );
  if (checks.return_chosen)
    return (
      <Alert severity="info" data-testid="return-chosen" sx={{ mb: 1 }} action={withdraw}>
        {RETURN_TEXT.chosen}
      </Alert>
    );
  return (
    <Alert severity="error" icon={false} data-testid="return-offer" sx={{ mb: 1 }}>
      <Stack spacing={1}>
        <Typography variant="body2" sx={{ fontWeight: 700 }}>
          {RETURN_TEXT[basis]}
        </Typography>
        <Stack direction="row" spacing={1} sx={{ flexWrap: 'wrap', gap: 1 }}>
          <Button variant="contained" size="small" onClick={onChoose} data-testid="choose-return">
            {RETURN_TEXT.action}
          </Button>
          {children}
        </Stack>
      </Stack>
    </Alert>
  );
}

export function IdConflictNotice({ checks }: { checks: Checks }) {
  if (!checks?.id_conflict) return null;
  return (
    <Alert severity="warning" data-testid="id-conflict" sx={{ mb: 1 }}>
      {RETURN_TEXT.conflict}
    </Alert>
  );
}
