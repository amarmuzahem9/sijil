/**
 * A read-only value in the same box as the form's inputs (the outlined TextField: the same frame,
 * corners, height and small label on the frame), for every view page. A note (e.g. «لم تقرأه
 * البطاقة») goes under the box as helper text and is linked to the field for screen readers.
 *
 * `ReadOnlyFields` lays them out: one column on a phone, two on a computer. `wide` spans both.
 */
import Box from '@mui/material/Box';
import TextField from '@mui/material/TextField';
import type { ReactNode } from 'react';

export function ReadOnlyField({
  label,
  value,
  note,
  ltr = false,
  wide = false,
}: {
  label: string;
  value: string | number | null | undefined;
  /** Shown under the box. */
  note?: ReactNode;
  /** Numbers, phones, usernames: left to right. */
  ltr?: boolean;
  /** Take both columns of `ReadOnlyFields`. */
  wide?: boolean;
}) {
  const text = value === null || value === undefined || value === '' ? '—' : String(value);
  return (
    <TextField
      label={label}
      value={text}
      fullWidth
      // Multiline with one row keeps the form's height and wraps a long value instead of
      // cutting it.
      multiline
      minRows={1}
      helperText={note}
      sx={wide ? { gridColumn: '1 / -1' } : undefined}
      slotProps={{
        input: { readOnly: true },
        htmlInput: { dir: ltr ? 'ltr' : undefined },
        formHelperText: { sx: { color: 'warning.main' } },
      }}
    />
  );
}

export function ReadOnlyFields({ children }: { children: ReactNode }) {
  return (
    <Box
      data-testid="readonly-fields"
      data-columns="1 2"
      sx={{
        display: 'grid',
        gridTemplateColumns: { xs: '1fr', md: '1fr 1fr' },
        columnGap: 2,
        rowGap: 2.5,
        alignItems: 'start',
      }}
    >
      {children}
    </Box>
  );
}
