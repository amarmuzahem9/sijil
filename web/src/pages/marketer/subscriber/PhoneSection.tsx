/**
 * «هاتف المشترك» (docs/system.md §5.4 item 1): the subscriber's own phone, normalized per §8.1.
 * The «تحقّق» button and OTP come with feature 007.
 */
import Stack from '@mui/material/Stack';

import { normalizePhone } from '../../../lib/phone';
import type { DraftAutosave, TextField } from '../../../lib/useDraftAutosave';
import { DraftTextField } from './DraftTextField';

export function PhoneSection({
  autosave,
  onCommit,
  error,
}: {
  autosave: Pick<DraftAutosave, 'values' | 'setText'>;
  onCommit: (field: TextField) => void;
  error?: string | null;
}) {
  const { values, setText } = autosave;
  const normalized = normalizePhone(values.phone_input);
  const hint =
    normalized && normalized !== values.phone_input.trim() ? `سيُحفظ كـ ${normalized}` : ' ';
  return (
    <Stack spacing={1}>
      <DraftTextField
        field="phone_input"
        label="هاتف المشترك"
        value={values.phone_input}
        onText={setText}
        onCommit={onCommit}
        error={error}
        helperText={hint}
        ltr
        inputMode="tel"
        autoComplete="off"
      />
    </Stack>
  );
}
