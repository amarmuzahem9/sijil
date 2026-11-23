/**
 * Early warnings from the duplicate check, under their fields (specs/008 US3, US4, US6; FR-008 to
 * FR-010; docs/system.md §6.1).
 *
 * - National ID exists (row 2) and phone used (row 1): the message only. Since 009 the page shows
 *   ReturnNotice («طلب العودة للخدمة») instead; PhoneUsedNotice remains for a used phone that is
 *   not the return target, with «الاتصال بالإدارة».
 * - Family exists (row 3): «إضافة اشتراك ثاني». Once chosen, the request will wait for the admin;
 *   «تراجع» withdraws it. Changing the family number drops the choice on the server.
 *
 * The page gets booleans only, so nothing here can name the other subscriber. Without `checks`
 * (an older server) nothing shows; the server still decides at «إرسال».
 */
import Alert from '@mui/material/Alert';
import Button from '@mui/material/Button';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';
import type { ReactNode } from 'react';

import type { DraftChecks } from '../../../lib/drafts';

export const MATCH_TEXT = {
  nationalId: 'المشترك لديه اشتراك سابق',
  phone: 'المشترك موجود سابقاً، هل يود العودة للخدمة؟',
  family: 'لهذه العائلة اشتراك سابق',
  familyAction: 'إضافة اشتراك ثاني',
  confirmed: 'إضافة اشتراك ثاني: يكمل الطلب بهاتف جديد، ويذهب لموافقة المسؤول',
  withdraw: 'تراجع',
} as const;

type Checks = DraftChecks | undefined;

export function NationalIdExistsNotice({ checks }: { checks: Checks }) {
  if (!checks?.national_id_exists) return null;
  return (
    <Alert severity="error" data-testid="national-id-exists" sx={{ mb: 1 }}>
      {MATCH_TEXT.nationalId}
    </Alert>
  );
}

/** A used phone that is not the return offer's (e.g. phone of A, card of B): the message, and
 * `children` (specs/009: «الاتصال بالإدارة»). */
export function PhoneUsedNotice({ checks, children }: { checks: Checks; children?: ReactNode }) {
  if (!checks?.phone_used) return null;
  return (
    <Alert severity="error" data-testid="phone-used">
      <Stack spacing={1}>
        <span>{MATCH_TEXT.phone}</span>
        {children}
      </Stack>
    </Alert>
  );
}

export function FamilyMatchNotice({
  checks,
  onConfirm,
  onWithdraw,
}: {
  checks: Checks;
  onConfirm: () => void;
  onWithdraw: () => void;
}) {
  if (!checks?.family_exists) return null;
  if (checks.additional_confirmed)
    return (
      <Alert
        severity="info"
        data-testid="family-confirmed"
        sx={{ mb: 1 }}
        action={
          <Button color="inherit" size="small" onClick={onWithdraw}>
            {MATCH_TEXT.withdraw}
          </Button>
        }
      >
        {MATCH_TEXT.confirmed}
      </Alert>
    );
  return (
    <Alert severity="warning" icon={false} data-testid="family-exists" sx={{ mb: 1 }}>
      <Stack spacing={1}>
        <Typography variant="body2" sx={{ fontWeight: 700 }}>
          {MATCH_TEXT.family}
        </Typography>
        <Button
          variant="contained"
          size="small"
          onClick={onConfirm}
          sx={{ alignSelf: 'flex-start' }}
          data-testid="confirm-additional"
        >
          {MATCH_TEXT.familyAction}
        </Button>
      </Stack>
    </Alert>
  );
}
