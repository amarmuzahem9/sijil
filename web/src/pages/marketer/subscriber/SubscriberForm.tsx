/**
 * «إضافة مشترك جديد» — one page with the sections in the order of docs/system.md §5 (FR-003).
 *
 * `/drafts/new` starts an empty form; the first real change creates the draft and the URL is
 * replaced with `/drafts/{id}` without remounting the form. `/drafts/{id}` loads a saved draft
 * (any device of the same account, FR-016). A missing or foreign draft shows «المسودة غير موجودة».
 */
import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import CircularProgress from '@mui/material/CircularProgress';
import Paper from '@mui/material/Paper';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';
import { useQuery } from '@tanstack/react-query';
import { useEffect, useState } from 'react';
import type { ReactNode } from 'react';
import { Link as RouterLink, useLocation, useNavigate, useParams } from 'react-router-dom';

import { useAuth } from '../../../auth/AuthProvider';
import { ApiError, setSessionEndedInterceptor } from '../../../lib/api';
import { getDraft, type Draft } from '../../../lib/drafts';
import { useDraftAutosave } from '../../../lib/useDraftAutosave';
import { CardDataSection } from './CardDataSection';
import { CardSection } from './CardSection';
import { LocationSection } from './LocationSection';
import { SaveBadge } from './SaveBadge';
import { SECTIONS, SEND_DISABLED_NOTE, type SectionId } from './sections';
import { SignInDialog } from './SignInDialog';

const TITLES = Object.fromEntries(SECTIONS.map((s) => [s.id, s.title])) as Record<
  SectionId,
  string
>;

function FormSection({ id, children }: { id: SectionId; children?: ReactNode }) {
  return (
    <Paper
      component="section"
      variant="outlined"
      id={id}
      aria-labelledby={`${id}-title`}
      sx={{ p: 2 }}
    >
      <Typography id={`${id}-title`} component="h2" variant="h6" sx={{ fontWeight: 700, mb: 1.5 }}>
        {TITLES[id]}
      </Typography>
      {children ?? (
        <Typography variant="body2" color="text.secondary">
          قريباً
        </Typography>
      )}
    </Paper>
  );
}

function DraftEditor({
  initial,
  onCreated,
}: {
  initial: Draft | null;
  onCreated: (id: string) => void;
}) {
  const autosave = useDraftAutosave(initial);
  const { user } = useAuth();
  const navigate = useNavigate();
  const [sessionEnded, setSessionEnded] = useState(false);

  // While the form is open, an ended session asks for sign-in here instead of leaving the page
  // (analysis U2): the values typed so far stay on screen.
  useEffect(() => {
    setSessionEndedInterceptor(() => setSessionEnded(true));
    return () => setSessionEndedInterceptor(null);
  }, []);

  useEffect(() => {
    if (autosave.draftId) onCreated(autosave.draftId);
  }, [autosave.draftId, onCreated]);

  const showSignIn = sessionEnded || autosave.saveState === 'session_ended';

  return (
    <Stack
      spacing={2}
      sx={{ maxWidth: 640 }}
      data-testid="subscriber-form"
      data-draft-id={autosave.draftId ?? ''}
    >
      <Box
        sx={{
          position: 'sticky',
          top: 0,
          zIndex: 2,
          bgcolor: 'background.default',
          py: 1,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: 1,
          flexWrap: 'wrap',
        }}
      >
        <Typography component="h1" variant="h5" sx={{ fontWeight: 700 }}>
          إضافة مشترك جديد
        </Typography>
        <SaveBadge state={autosave.saveState} onRetry={autosave.retry} />
      </Box>

      {autosave.saveState === 'failed' && autosave.lastError?.message && (
        <Alert severity="error">{autosave.lastError.message}</Alert>
      )}

      <FormSection id="section-card">
        <CardSection autosave={autosave} />
      </FormSection>
      <FormSection id="section-card-data">
        <CardDataSection autosave={autosave} />
      </FormSection>
      <FormSection id="section-location">
        <LocationSection autosave={autosave} />
      </FormSection>
      <FormSection id="section-subscription" />
      <FormSection id="section-phone" />

      {/* «النواقص» slot (US5, MissingSummary). */}
      <Box data-testid="missing-summary-slot" />

      <Stack spacing={0.5}>
        <Button variant="contained" size="large" disabled sx={{ py: 1.5 }}>
          إرسال
        </Button>
        <Typography variant="caption" color="text.secondary" align="center">
          {SEND_DISABLED_NOTE}
        </Typography>
      </Stack>

      <SignInDialog
        open={showSignIn}
        expectedUserId={user?.id ?? null}
        onSameUser={() => {
          setSessionEnded(false);
          autosave.resume();
        }}
        onOtherUser={() => navigate('/', { replace: true })}
      />
    </Stack>
  );
}

function NotFound() {
  return (
    <Stack spacing={2} sx={{ maxWidth: 640 }}>
      <Alert severity="warning">المسودة غير موجودة</Alert>
      <Button component={RouterLink} to="/requests?tab=drafts" variant="outlined">
        العودة إلى المسودات
      </Button>
    </Stack>
  );
}

const noop = () => undefined;

export default function SubscriberForm() {
  const { draftId = 'new' } = useParams<{ draftId: string }>();
  const location = useLocation();
  // The id this page created itself: reaching /drafts/{ownId} must not reload or remount.
  const [ownId, setOwnId] = useState<string | null>(null);
  const [newKey, setNewKey] = useState(location.key);

  // A fresh «إضافة مشترك جديد» while a created draft is open starts over.
  if (draftId === 'new' && ownId !== null) {
    setOwnId(null);
    setNewKey(location.key);
  }

  const isNew = draftId === 'new' || draftId === ownId;
  const query = useQuery({
    queryKey: ['draft', draftId],
    queryFn: () => getDraft(draftId),
    enabled: !isNew,
    retry: (count, err) => !(err instanceof ApiError && err.status < 500) && count < 2,
    staleTime: Infinity,
    gcTime: 0,
  });

  if (isNew) return <DraftEditor key={`new-${newKey}`} initial={null} onCreated={setOwnId} />;
  if (query.isPending) return <CircularProgress aria-label="جارٍ التحميل" />;
  if (query.isError) {
    const err = query.error;
    if (err instanceof ApiError && err.status >= 400 && err.status < 500) return <NotFound />;
    return (
      <Alert
        severity="error"
        action={
          <Button color="inherit" size="small" onClick={() => query.refetch()}>
            إعادة المحاولة
          </Button>
        }
      >
        {err.message}
      </Alert>
    );
  }
  return <DraftEditor key={draftId} initial={query.data} onCreated={noop} />;
}
