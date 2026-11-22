/**
 * React side of the draft autosave (specs/005 research.md R3, tasks T021/T040).
 *
 * - Text fields save about 1 s after the last keystroke, and immediately on blur.
 * - Selects, the pin and buttons save immediately (`saveNow`).
 * - The first real change creates the draft and replaces the URL with /drafts/{id}.
 * - While the form is open the version is polled; a save made elsewhere pauses autosave.
 *
 * The imperative parts (values, timers, queue, polling) live in DraftFormController; this hook
 * mirrors them into React state. Nothing is written to localStorage (Principle II).
 */
import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';

import type { ApiError } from './api';
import type { AutosaveQueue, SaveState } from './autosaveQueue';
import {
  DraftFormController,
  valuesFromDraft,
  type FormValues,
  type TextField,
} from './draftFormController';
import type { Draft, DraftNotice } from './drafts';

export {
  EMPTY_VALUES,
  TEXT_DEBOUNCE_MS,
  VERSION_POLL_MS,
  valuesFromDraft,
  type FormValues,
  type TextField,
} from './draftFormController';

export interface DraftAutosave {
  draftId: string | null;
  values: FormValues;
  serverDraft: Draft | null;
  saveState: SaveState;
  lastError: ApiError | null;
  /** Update a text field; saved after the debounce or on `commitField`. */
  setText: (field: TextField, value: string) => void;
  /** Save a debounced text field now (blur). */
  commitField: (field: TextField) => void;
  /** Update and save immediately (selects, the pin, buttons). */
  saveNow: (changes: Partial<FormValues> & { national_id_confirmed?: boolean }) => void;
  retry: () => void;
  /** Called after an image upload on this page: newer version + new server draft. */
  applyServerDraft: (draft: Draft) => void;
  /** «تحميل الأحدث». */
  loadLatest: (draft: Draft) => void;
  /** «الإبقاء على نسختي»: send every local field over the newer server version. */
  keepMine: () => void;
  /** Polling found a newer version elsewhere, or the draft was deleted. */
  pause: (state: 'conflict' | 'deleted') => void;
  /** After signing in again. */
  resume: () => void;
  /** Make sure the draft exists (e.g. before the first image upload); resolves to its id. */
  ensureCreated: () => Promise<string>;
  /** Catalog notices (choice unavailable / price changed) since the draft was opened. */
  notices: DraftNotice[];
  dismissNotice: (field: DraftNotice['field']) => void;
  /** «أعد المحاولة» after a failed card reading (specs/006 US5). */
  retryReading: () => Promise<void>;
  queue: AutosaveQueue;
}

export function useDraftAutosave(
  initial: Draft | null,
  options: { onCreated?: (id: string) => void } = {},
): DraftAutosave {
  const navigate = useNavigate();
  const { onCreated } = options;
  // One controller per mounted form; a different draft remounts the form (keyed by id).
  const [ctl] = useState(() => new DraftFormController(initial));
  const [values, setValues] = useState<FormValues>(() => valuesFromDraft(initial));
  const [serverDraft, setServerDraft] = useState<Draft | null>(initial);
  const [saveState, setSaveState] = useState<SaveState>(initial ? 'saved' : 'idle');
  const [lastError, setLastError] = useState<ApiError | null>(null);
  const [notices, setNotices] = useState<DraftNotice[]>(initial?.notices ?? []);
  const [draftId, setDraftId] = useState<string | null>(initial?.id ?? null);

  useEffect(
    () =>
      ctl.attach({
        values: setValues,
        serverDraft: setServerDraft,
        state: (state, error) => {
          setSaveState(state);
          setLastError(error);
        },
        notices: setNotices,
        created: (id) => {
          setDraftId(id);
          // Tell the page first, so reaching /drafts/{id} keeps this form mounted (an upload
          // may be running).
          onCreated?.(id);
          navigate(`/drafts/${id}`, { replace: true });
        },
      }),
    [ctl, navigate, onCreated],
  );

  useEffect(() => (draftId ? ctl.startPolling(draftId) : undefined), [ctl, draftId]);
  useEffect(() => (draftId ? ctl.startReadingPoll(draftId) : undefined), [ctl, draftId]);

  return {
    draftId,
    values,
    serverDraft,
    saveState,
    lastError,
    setText: (field, value) => ctl.setText(field, value),
    commitField: (field) => ctl.commitField(field),
    saveNow: (changes) => ctl.saveNow(changes),
    retry: () => void ctl.queue.resume(),
    applyServerDraft: (draft) => ctl.applyServerDraft(draft),
    loadLatest: (draft) => ctl.loadLatest(draft),
    keepMine: () => ctl.keepMine(),
    pause: (state) => ctl.queue.pause(state),
    resume: () => void ctl.queue.resume(),
    ensureCreated: () => ctl.queue.ensureCreated(),
    notices,
    dismissNotice: (field) => setNotices((list) => list.filter((n) => n.field !== field)),
    retryReading: () => (draftId ? ctl.retryReading(draftId) : Promise.resolve()),
    queue: ctl.queue,
  };
}
