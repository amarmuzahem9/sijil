import InputAdornment from '@mui/material/InputAdornment';
import TextField from '@mui/material/TextField';

import { formatNumber, parseMoney } from '../lib/money';

/**
 * Whole-dinar input (specs/004 FR-012): accepts Arabic-Indic digits and separators, shows grouping
 * as you type, and reports the parsed integer (or null when the text is not a whole number).
 */
export function MoneyField({
  label,
  text,
  onChange,
  error,
  unit = 'د.ع',
}: {
  label: string;
  text: string;
  onChange: (text: string, value: number | null) => void;
  error?: string | null;
  unit?: string;
}) {
  return (
    <TextField
      label={label}
      value={text}
      onChange={(e) => {
        const value = parseMoney(e.target.value);
        // Re-group a valid number as it is typed; leave invalid text as is so it can be fixed.
        onChange(value === null ? e.target.value : formatNumber(value), value);
      }}
      error={Boolean(error)}
      helperText={error ?? null}
      required
      fullWidth
      slotProps={{
        htmlInput: { dir: 'ltr', inputMode: 'numeric' },
        input: { endAdornment: <InputAdornment position="end">{unit}</InputAdornment> },
      }}
    />
  );
}
