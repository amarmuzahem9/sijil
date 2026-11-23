/**
 * «تثبيت الأرقام» on the review file (docs/system.md v1.14 §6.4, specs/010 US3: FR-013, FR-014;
 * research R4). For each number the marketer edited: the card reading, the MRZ (national ID only),
 * the marketer's value and the current value side by side, a pin button per source, a typed value,
 * and the history of pins. The server reads every source but `typed` itself, so only the source is
 * sent.
 */
import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Paper from '@mui/material/Paper';
import Stack from '@mui/material/Stack';
import TextField from '@mui/material/TextField';
import Typography from '@mui/material/Typography';
import { useId, useState } from 'react';

import { ReadOnlyField } from '../../../components/ReadOnlyField';
import {
  pin,
  type NumberView,
  type PinBody,
  type PinField,
  type PinSource,
  type RequestFile,
} from '../../../lib/adminRequests';
import { PIN_FIELD_LABELS, PIN_SOURCE_LABELS } from '../../../lib/labels';
import { formatBaghdad } from '../../../lib/time';

const FIELDS: PinField[] = ['national_id', 'family_number'];

function sourcesOf(field: PinField): Exclude<PinSource, 'typed'>[] {
  return field === 'national_id' ? ['reading', 'mrz', 'marketer'] : ['reading', 'marketer'];
}

function SourceRow({
  field,
  source,
  view,
  canPin,
  busy,
  onPin,
}: {
  field: PinField;
  source: Exclude<PinSource, 'typed'>;
  view: NumberView;
  canPin: boolean;
  busy: boolean;
  onPin: (body: PinBody) => void;
}) {
  const value = view[source];
  const label = PIN_SOURCE_LABELS[source];
  let note: string | undefined;
  if (!value) note = source === 'reading' ? 'لم تقرأه البطاقة' : 'لا توجد قيمة';
  else if (value !== view.current) note = 'تختلف عن القيمة الحالية';
  return (
    <Stack spacing={1}>
      <ReadOnlyField label={label} value={value} note={note} ltr />
      {canPin && (
        <div>
          <Button
            size="small"
            variant="outlined"
            aria-label={`تثبيت القيمة: ${label}`}
            disabled={busy || !value || value === view.current}
            onClick={() => onPin({ field, source })}
          >
            تثبيت القيمة
          </Button>
        </div>
      )}
    </Stack>
  );
}

function FieldGroup({
  field,
  view,
  canPin,
  busy,
  onPin,
}: {
  field: PinField;
  view: NumberView;
  canPin: boolean;
  busy: boolean;
  onPin: (body: PinBody) => void;
}) {
  const titleId = useId();
  const historyId = useId();
  const [typed, setTyped] = useState('');
  const typedLabel = PIN_SOURCE_LABELS.typed;
  return (
    <Box role="group" aria-labelledby={titleId}>
      <Typography id={titleId} sx={{ fontWeight: 700, mb: 1.5 }}>
        {PIN_FIELD_LABELS[field]}
      </Typography>
      <Box
        sx={{
          display: 'grid',
          gridTemplateColumns: { xs: '1fr', md: '1fr 1fr' },
          columnGap: 2,
          rowGap: 2.5,
          alignItems: 'start',
        }}
      >
        <ReadOnlyField label="القيمة الحالية" value={view.current} ltr />
        {sourcesOf(field).map((source) => (
          <SourceRow
            key={source}
            field={field}
            source={source}
            view={view}
            canPin={canPin}
            busy={busy}
            onPin={onPin}
          />
        ))}
        {canPin && (
          <Stack spacing={1}>
            <TextField
              label={typedLabel}
              value={typed}
              onChange={(e) => setTyped(e.target.value)}
              fullWidth
              slotProps={{ htmlInput: { dir: 'ltr' } }}
            />
            <div>
              <Button
                size="small"
                variant="outlined"
                aria-label={`تثبيت القيمة: ${typedLabel}`}
                disabled={busy || typed.trim() === ''}
                onClick={() => onPin({ field, source: 'typed', value: typed.trim() })}
              >
                تثبيت القيمة
              </Button>
            </div>
          </Stack>
        )}
      </Box>
      {view.pins.length > 0 && (
        <Box sx={{ mt: 2 }}>
          <Typography id={historyId} variant="body2" sx={{ fontWeight: 700 }}>
            سجل التثبيت
          </Typography>
          <Box component="ul" aria-labelledby={historyId} sx={{ m: 0, pl: 0, pr: 2.5 }}>
            {view.pins.map((p, i) => (
              <Typography key={i} component="li" variant="body2" color="text.secondary">
                <span dir="ltr">{p.value}</span> ({PIN_SOURCE_LABELS[p.source]}) · {p.by} ·{' '}
                {formatBaghdad(p.at)}
              </Typography>
            ))}
          </Box>
        </Box>
      )}
    </Box>
  );
}

export function NumbersPinPanel({
  file,
  onPinned,
}: {
  file: RequestFile;
  onPinned: (file: RequestFile) => void;
}) {
  const titleId = useId();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const canPin = file.status === 'pending_review';
  const numbers = file.numbers; // null on a deleted request (specs/011 R9)
  const fields = numbers ? FIELDS.filter((f) => numbers[f].edited) : [];
  if (fields.length === 0) return null;

  async function send(body: PinBody) {
    setBusy(true);
    setError(null);
    try {
      onPinned(await pin(file.id, body));
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Paper component="section" aria-labelledby={titleId} variant="outlined" sx={{ p: 2 }}>
      <Typography id={titleId} variant="subtitle1" component="h2" sx={{ fontWeight: 700, mb: 2 }}>
        تثبيت الأرقام
      </Typography>
      {error && (
        <Alert severity="warning" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}
      <Stack spacing={3}>
        {fields.map((field) => (
          <FieldGroup
            key={field}
            field={field}
            view={numbers![field]}
            canPin={canPin}
            busy={busy}
            onPin={(body) => void send(body)}
          />
        ))}
      </Stack>
    </Paper>
  );
}
