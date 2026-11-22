/**
 * «بيانات البطاقة» (docs/system.md §5.1 v1.5): the nine name fields of the ministry form, then
 * the national ID and the family number. Typed by hand in this feature (FR-004); card reading
 * comes in 006, and the fourth name is never on the card.
 *
 * Phone layout: first + second and third + fourth side by side, the surname full width, and the
 * mother's names grouped under «اسم الأم».
 */
import Box from '@mui/material/Box';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';
import type { ReactNode } from 'react';

import { NAME_LABELS, OPTIONAL_NAME_FIELDS, type NameField } from '../../../lib/nameFields';
import type { DraftAutosave, TextField } from '../../../lib/useDraftAutosave';
import { DraftTextField } from './DraftTextField';

export const FOURTH_NAME_HINT = 'غير موجود على البطاقة، اسأل المشترك';

type CardField = NameField | 'national_id' | 'family_number';

function Pair({ children }: { children: ReactNode }) {
  return (
    <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr', columnGap: 1 }}>{children}</Box>
  );
}

export function CardDataSection({
  autosave,
  errors = {},
  onCommit,
}: {
  autosave: Pick<DraftAutosave, 'values' | 'setText' | 'commitField'>;
  errors?: Partial<Record<CardField, string>>;
  /** Called on blur instead of `commitField` (the form marks the field as touched). */
  onCommit?: (field: TextField) => void;
}) {
  const { values, setText } = autosave;
  const commitField = onCommit ?? autosave.commitField;

  const name = (field: NameField, helperText?: string) => (
    <DraftTextField
      field={field}
      label={
        OPTIONAL_NAME_FIELDS.includes(field)
          ? `${NAME_LABELS[field]} (اختياري)`
          : `${NAME_LABELS[field]} *`
      }
      value={values[field]}
      onText={setText}
      onCommit={commitField}
      error={errors[field]}
      helperText={helperText}
      autoComplete="off"
    />
  );

  return (
    <Stack spacing={1}>
      <Pair>
        {name('first_name')}
        {name('father_name')}
      </Pair>
      <Pair>
        {name('grandfather_name')}
        {name('great_grandfather_name', FOURTH_NAME_HINT)}
      </Pair>
      {name('surname')}

      <Box
        component="fieldset"
        sx={{ border: 1, borderColor: 'divider', borderRadius: 1, px: 1.5, pt: 0.5, pb: 0, m: 0 }}
      >
        <Typography component="legend" variant="subtitle2" sx={{ px: 0.5, fontWeight: 600 }}>
          اسم الأم
        </Typography>
        <Pair>
          {name('mother_first_name')}
          {name('mother_second_name')}
        </Pair>
        <Pair>
          {name('mother_third_name')}
          {name('mother_surname')}
        </Pair>
      </Box>

      <DraftTextField
        field="national_id"
        label="الرقم الوطني *"
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
        label="الرقم العائلي *"
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
