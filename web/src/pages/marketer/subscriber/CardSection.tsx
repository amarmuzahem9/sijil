/**
 * «البطاقة الوطنية»: front, then back (docs/system.md §5.1; only the unified card is accepted).
 * After both are uploaded the server reads the card (specs/006): this section shows that the
 * reading waits for the other side or is running; each slot shows its own re-shoot message.
 */
import Alert from '@mui/material/Alert';
import LinearProgress from '@mui/material/LinearProgress';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';

import {
  READING_NEEDS_OTHER_SIDE,
  READING_RUNNING,
  shouldPoll,
  waitsForOtherSide,
} from '../../../lib/cardReading';
import type { DraftAutosave } from '../../../lib/useDraftAutosave';
import { ImageSlot } from './ImageSlot';

export function CardSection({
  autosave,
}: {
  autosave: Pick<DraftAutosave, 'serverDraft' | 'ensureCreated' | 'applyServerDraft'>;
}) {
  const images = autosave.serverDraft?.images ?? { front: null, back: null };
  const reading = autosave.serverDraft?.card_reading ?? null;
  return (
    <Stack spacing={2}>
      <Typography variant="body2" color="text.secondary">
        البطاقة الوطنية الموحدة فقط.
      </Typography>
      <ImageSlot
        side="front"
        label="وجه البطاقة"
        image={images.front}
        reading={reading?.front ?? null}
        ensureCreated={autosave.ensureCreated}
        onUploaded={autosave.applyServerDraft}
      />
      <ImageSlot
        side="back"
        label="ظهر البطاقة"
        image={images.back}
        reading={reading?.back ?? null}
        ensureCreated={autosave.ensureCreated}
        onUploaded={autosave.applyServerDraft}
      />
      {waitsForOtherSide(reading) && (
        <Alert severity="info" data-testid="reading-waits">
          {READING_NEEDS_OTHER_SIDE}
        </Alert>
      )}
      {!waitsForOtherSide(reading) && shouldPoll(reading) && (
        <Alert severity="info" icon={false} data-testid="reading-running">
          <Typography variant="body2" sx={{ mb: 0.5 }}>
            {READING_RUNNING}
          </Typography>
          <LinearProgress />
        </Alert>
      )}
    </Stack>
  );
}
