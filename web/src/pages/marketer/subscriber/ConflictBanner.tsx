/**
 * The draft changed elsewhere, or was deleted (specs/005 US3, FR-017, research.md R3).
 * Autosave stays paused until the marketer chooses.
 */
import Alert from '@mui/material/Alert';
import AlertTitle from '@mui/material/AlertTitle';
import Button from '@mui/material/Button';
import Stack from '@mui/material/Stack';
import { useState } from 'react';
import { Link as RouterLink } from 'react-router-dom';

import { ApiError, NETWORK_ERROR_MESSAGE } from '../../../lib/api';
import { getDraft } from '../../../lib/drafts';
import type { DraftAutosave } from '../../../lib/useDraftAutosave';

export const CHANGED_ELSEWHERE = 'تغيّرت المسودة من جهاز آخر';
export const DELETED_ELSEWHERE = 'حُذفت هذه المسودة';

export function ConflictBanner({
  autosave,
}: {
  autosave: Pick<DraftAutosave, 'saveState' | 'draftId' | 'loadLatest' | 'keepMine' | 'pause'>;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (autosave.saveState === 'deleted') {
    return (
      <Alert
        severity="error"
        data-testid="draft-deleted-banner"
        action={
          <Button color="inherit" size="small" component={RouterLink} to="/requests?tab=drafts">
            الطلبات
          </Button>
        }
      >
        {DELETED_ELSEWHERE}
      </Alert>
    );
  }
  if (autosave.saveState !== 'conflict' || !autosave.draftId) return null;

  async function loadLatest() {
    setBusy(true);
    setError(null);
    try {
      autosave.loadLatest(await getDraft(autosave.draftId!));
    } catch (err) {
      if (err instanceof ApiError && err.code === 'draft_not_found') autosave.pause('deleted');
      else setError(err instanceof ApiError ? err.message : NETWORK_ERROR_MESSAGE);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Alert severity="warning" data-testid="conflict-banner">
      <AlertTitle>{CHANGED_ELSEWHERE}</AlertTitle>
      الحفظ التلقائي متوقف. اختر النسخة التي تريد الاحتفاظ بها.
      <Stack direction="row" spacing={1} sx={{ mt: 1.5, flexWrap: 'wrap', rowGap: 1 }}>
        <Button variant="contained" size="small" disabled={busy} onClick={() => void loadLatest()}>
          تحميل الأحدث
        </Button>
        <Button variant="outlined" size="small" disabled={busy} onClick={autosave.keepMine}>
          الإبقاء على نسختي
        </Button>
      </Stack>
      {error && (
        <Alert severity="error" sx={{ mt: 1 }}>
          {error}
        </Alert>
      )}
    </Alert>
  );
}
