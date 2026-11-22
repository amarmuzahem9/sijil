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
import { useCallback, useEffect, useMemo, useState } from 'react';
import type { ReactNode } from 'react';
import { Link as RouterLink, useLocation, useNavigate, useParams } from 'react-router-dom';

import { useAuth } from '../../../auth/AuthProvider';
import { ApiError, setSessionEndedInterceptor } from '../../../lib/api';
import {
  CODE_MESSAGES,
  computeMissing,
  isTooLong,
  type LimitedField,
  type MissingField,
} from '../../../lib/draftValidation';
import { getDraft, type Draft } from '../../../lib/drafts';
import { useDraftAutosave, type TextField } from '../../../lib/useDraftAutosave';
import { CardDataSection } from './CardDataSection';
import { CardSection } from './CardSection';
import { ConflictBanner } from './ConflictBanner';
import { LocationSection } from './LocationSection';
import { MissingSummary } from './MissingSummary';
import { PhoneSection } from './PhoneSection';
import { SaveBadge } from './SaveBadge';
import { SECTIONS, type SectionId } from './sections';
import { SignInDialog } from './SignInDialog';
import { SubscriptionSection } from './SubscriptionSection';

const MISSING_KEY: Partial<Record<TextField, MissingField>> = {
  subscriber_name: 'subscriber_name',
  national_id: 'national_id',
  family_number: 'family_number',
  phone_input: 'phone',
};

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
  const autosave = useDraftAutosave(initial, { onCreated });
  const { user } = useAuth();
  const navigate = useNavigate();
  const [sessionEnded, setSessionEnded] = useState(false);

  // While the form is open, an ended session asks for sign-in here instead of leaving the page
  // (analysis U2): the values typed so far stay on screen.
  useEffect(() => {
    setSessionEndedInterceptor(() => setSessionEnded(true));
    return () => setSessionEndedInterceptor(null);
  }, []);

  const showSignIn = sessionEnded || autosave.saveState === 'session_ended';

  // Inline errors appear once a field has been left (US5); the server list is authoritative
  // once everything is saved.
  const [touched, setTouched] = useState<Set<TextField>>(() => new Set());
  const { commitField } = autosave;
  const onCommit = useCallback(
    (field: TextField) => {
      setTouched((t) => (t.has(field) ? t : new Set(t).add(field)));
      commitField(field);
    },
    [commitField],
  );
  const imageSides = useMemo(() => {
    const images = autosave.serverDraft?.images;
    return (['front', 'back'] as const).filter((side) => images?.[side]);
  }, [autosave.serverDraft]);
  const localMissing = useMemo(
    () =>
      computeMissing(
        {
          ...autosave.values,
          location_lat: autosave.values.location?.lat ?? null,
          location_lng: autosave.values.location?.lng ?? null,
        },
        imageSides,
      ),
    [autosave.values, imageSides],
  );
  const missing =
    autosave.saveState === 'saved' && autosave.serverDraft
      ? autosave.serverDraft.missing
      : localMissing;

  const errorFor = (field: TextField): string | null => {
    if (isTooLong(field as LimitedField, autosave.values[field])) return CODE_MESSAGES.too_long;
    if (!touched.has(field)) return null;
    const key = MISSING_KEY[field];
    const item = key && localMissing.find((m) => m.field === key);
    return item ? CODE_MESSAGES[item.code] : null;
  };

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

      <ConflictBanner autosave={autosave} />
      {autosave.saveState === 'failed' && autosave.lastError?.message && (
        <Alert severity="error">{autosave.lastError.message}</Alert>
      )}

      <FormSection id="section-card">
        <CardSection autosave={autosave} />
      </FormSection>
      <FormSection id="section-card-data">
        <CardDataSection
          autosave={autosave}
          onCommit={onCommit}
          errors={{
            subscriber_name: errorFor('subscriber_name') ?? undefined,
            national_id: errorFor('national_id') ?? undefined,
            family_number: errorFor('family_number') ?? undefined,
          }}
        />
      </FormSection>
      <FormSection id="section-location">
        <LocationSection autosave={autosave} />
      </FormSection>
      <FormSection id="section-subscription">
        <SubscriptionSection autosave={autosave} />
      </FormSection>
      <FormSection id="section-phone">
        <PhoneSection autosave={autosave} onCommit={onCommit} error={errorFor('phone_input')} />
      </FormSection>

      <MissingSummary missing={missing} />

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
  // One "new form" session per navigation to /drafts/new. `ownId` is the draft that session
  // created: reaching /drafts/{ownId} must not reload or remount the form (an upload may be
  // running). Only a new navigation to /drafts/new (a new location key) starts over; the
  // in-between render where the id is known but the URL is still /drafts/new must not.
  const [session, setSession] = useState<{ key: string; ownId: string | null }>({
    key: location.key,
    ownId: null,
  });
  if (draftId === 'new' && location.key !== session.key) {
    setSession({ key: location.key, ownId: null });
  }
  const onCreated = useCallback((id: string) => setSession((s) => ({ ...s, ownId: id })), []);

  const isNew = draftId === 'new' || draftId === session.ownId;
  const query = useQuery({
    queryKey: ['draft', draftId],
    queryFn: () => getDraft(draftId),
    enabled: !isNew,
    retry: (count, err) => !(err instanceof ApiError && err.status < 500) && count < 2,
    staleTime: Infinity,
    gcTime: 0,
  });

  if (isNew) return <DraftEditor key={`new-${session.key}`} initial={null} onCreated={onCreated} />;
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
