/** A text field wired to the draft autosave: debounced on typing, saved on blur. */
import TextField from '@mui/material/TextField';
import type { HTMLAttributes } from 'react';

import type { TextField as DraftField } from '../../../lib/useDraftAutosave';

export function DraftTextField({
  field,
  label,
  value,
  onText,
  onCommit,
  error,
  helperText,
  ltr = false,
  inputMode,
  multiline = false,
  autoComplete = 'off',
}: {
  field: DraftField;
  label: string;
  value: string;
  onText: (field: DraftField, value: string) => void;
  onCommit: (field: DraftField) => void;
  error?: string | null;
  helperText?: string | null;
  ltr?: boolean;
  inputMode?: HTMLAttributes<HTMLInputElement>['inputMode'];
  multiline?: boolean;
  autoComplete?: string;
}) {
  return (
    <TextField
      id={`field-${field}`}
      name={field}
      label={label}
      value={value}
      onChange={(e) => onText(field, e.target.value)}
      onBlur={() => onCommit(field)}
      error={Boolean(error)}
      helperText={error ?? helperText ?? ' '}
      fullWidth
      multiline={multiline}
      minRows={multiline ? 2 : undefined}
      autoComplete={autoComplete}
      slotProps={{
        htmlInput: {
          dir: ltr ? 'ltr' : undefined,
          inputMode,
          'data-testid': `field-${field}`,
        },
      }}
    />
  );
}
