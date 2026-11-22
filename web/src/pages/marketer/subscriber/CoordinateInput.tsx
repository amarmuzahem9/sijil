/**
 * «إدخال إحداثية» (docs/system.md §5.2 v1.6): "lat, lng" or a pasted Google Maps link, checked to be
 * inside Iraq. «انتقال» (or Enter) moves the pin there and saves it.
 */
import Button from '@mui/material/Button';
import Stack from '@mui/material/Stack';
import TextField from '@mui/material/TextField';
import { useState } from 'react';

import { COORDINATE_ERRORS, parseCoordinates } from '../../../lib/coordinates';
import type { LatLngLiteral } from '../../../lib/googleMaps';

export const COORDINATE_HINT = 'مثل 34.70, 43.68 أو رابط من Google Maps';

export function CoordinateInput({ onGo }: { onGo: (pos: LatLngLiteral) => void }) {
  const [text, setText] = useState('');
  const [error, setError] = useState<string | null>(null);

  function go() {
    const result = parseCoordinates(text);
    if (!result.ok) {
      setError(COORDINATE_ERRORS[result.error]);
      return;
    }
    setError(null);
    onGo(result.pos);
  }

  return (
    <Stack direction="row" spacing={1} sx={{ alignItems: 'flex-start' }}>
      <TextField
        label="إدخال إحداثية"
        value={text}
        onChange={(e) => {
          setText(e.target.value);
          if (error) setError(null);
        }}
        onKeyDown={(e) => {
          if (e.key === 'Enter') {
            e.preventDefault();
            go();
          }
        }}
        error={Boolean(error)}
        helperText={error ?? COORDINATE_HINT}
        fullWidth
        size="small"
        autoComplete="off"
        slotProps={{
          htmlInput: { dir: 'ltr', inputMode: 'text', 'data-testid': 'coordinate-input' },
        }}
      />
      <Button
        variant="outlined"
        onClick={go}
        data-testid="coordinate-go"
        sx={{ flexShrink: 0, minHeight: 40 }}
      >
        انتقال
      </Button>
    </Stack>
  );
}
