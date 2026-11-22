/**
 * «تأكد من الرقم الوطني» (specs/006 US4, FR-012, research R7).
 *
 * Shown under the national ID when the back's machine-readable zone is verified by all its check
 * digits and its national ID differs from the current value (typed or read). The marketer looks
 * at the card and adopts one of the two numbers; the choice is saved with the draft. Editing the
 * number again drops the confirmation (the server does the same).
 */
import Alert from '@mui/material/Alert';
import Button from '@mui/material/Button';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';

import {
  NATIONAL_ID_ADOPT,
  NATIONAL_ID_CHECK,
  NATIONAL_ID_CURRENT,
  NATIONAL_ID_MRZ,
} from '../../../lib/cardReading';
import type { NationalIdCheck as Check } from '../../../lib/drafts';
import { normalizeNationalId } from '../../../lib/nationalId';

/** True while the current value differs from the verified MRZ and is not confirmed. */
export function needsNationalIdCheck(
  check: Check | null | undefined,
  current: string,
  savedValue: string | null | undefined,
): boolean {
  if (!check?.mrz) return false;
  const value = normalizeNationalId(current);
  if (!value || value === check.mrz) return false;
  return !(check.confirmed && savedValue === current);
}

export function NationalIdCheck({
  check,
  current,
  savedValue,
  onAdopt,
}: {
  check: Check | null | undefined;
  current: string;
  savedValue: string | null | undefined;
  onAdopt: (value: string, confirm: boolean) => void;
}) {
  if (!check || !needsNationalIdCheck(check, current, savedValue)) return null;
  const row = (label: string, value: string, confirm: boolean, testId: string) => (
    <Stack
      direction="row"
      spacing={1}
      sx={{ alignItems: 'center', justifyContent: 'space-between' }}
    >
      <Typography variant="body2">
        {label}:{' '}
        <Typography component="span" dir="ltr" sx={{ fontFamily: 'monospace', fontWeight: 600 }}>
          {value}
        </Typography>
      </Typography>
      <Button
        size="small"
        variant="outlined"
        onClick={() => onAdopt(value, confirm)}
        data-testid={testId}
      >
        {NATIONAL_ID_ADOPT}
      </Button>
    </Stack>
  );
  return (
    <Alert severity="warning" icon={false} data-testid="national-id-check" sx={{ mb: 1 }}>
      <Typography variant="body2" sx={{ fontWeight: 700, mb: 1 }}>
        {NATIONAL_ID_CHECK}
      </Typography>
      <Stack spacing={1}>
        {row(
          NATIONAL_ID_CURRENT,
          normalizeNationalId(current) ?? current,
          true,
          'adopt-current-national-id',
        )}
        {row(NATIONAL_ID_MRZ, check.mrz, false, 'adopt-mrz-national-id')}
      </Stack>
    </Alert>
  );
}
