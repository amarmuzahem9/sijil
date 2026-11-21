import Visibility from '@mui/icons-material/Visibility';
import VisibilityOff from '@mui/icons-material/VisibilityOff';
import IconButton from '@mui/material/IconButton';
import InputAdornment from '@mui/material/InputAdornment';
import TextField from '@mui/material/TextField';
import { useState } from 'react';

/** Temporary-password input with show/hide. The value lives only in the form state. */
export function PasswordField({
  label,
  value,
  onChange,
  error,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  error?: string | null;
}) {
  const [shown, setShown] = useState(false);
  return (
    <TextField
      label={label}
      type={shown ? 'text' : 'password'}
      value={value}
      onChange={(e) => onChange(e.target.value)}
      autoComplete="new-password"
      error={Boolean(error)}
      helperText={error ?? 'ثمانية أحرف على الأقل'}
      fullWidth
      required
      slotProps={{
        htmlInput: { dir: 'ltr' },
        input: {
          endAdornment: (
            <InputAdornment position="end">
              <IconButton
                aria-label={shown ? 'إخفاء كلمة السر' : 'إظهار كلمة السر'}
                onClick={() => setShown((s) => !s)}
                edge="end"
              >
                {shown ? <VisibilityOff /> : <Visibility />}
              </IconButton>
            </InputAdornment>
          ),
        },
      }}
    />
  );
}
