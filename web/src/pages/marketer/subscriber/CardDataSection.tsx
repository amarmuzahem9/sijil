/** «بيانات البطاقة»: typed by hand in this feature (FR-004); card reading comes in 006. */
import Stack from '@mui/material/Stack';

import type { DraftAutosave, TextField } from '../../../lib/useDraftAutosave';
import { DraftTextField } from './DraftTextField';

export function CardDataSection({
  autosave,
  errors = {},
  onCommit,
}: {
  autosave: Pick<DraftAutosave, 'values' | 'setText' | 'commitField'>;
  errors?: Partial<Record<'subscriber_name' | 'national_id' | 'family_number', string>>;
  /** Called on blur instead of `commitField` (the form marks the field as touched). */
  onCommit?: (field: TextField) => void;
}) {
  const { values, setText } = autosave;
  const commitField = onCommit ?? autosave.commitField;
  return (
    <Stack spacing={1}>
      <DraftTextField
        field="subscriber_name"
        label="الاسم حسب البطاقة"
        value={values.subscriber_name}
        onText={setText}
        onCommit={commitField}
        error={errors.subscriber_name}
      />
      <DraftTextField
        field="national_id"
        label="الرقم الوطني"
        value={values.national_id}
        onText={setText}
        onCommit={commitField}
        error={errors.national_id}
        helperText="12 رقماً"
        ltr
        inputMode="numeric"
      />
      <DraftTextField
        field="family_number"
        label="الرقم العائلي"
        value={values.family_number}
        onText={setText}
        onCommit={commitField}
        error={errors.family_number}
        helperText="كما هو مكتوب على البطاقة"
        ltr
      />
    </Stack>
  );
}
