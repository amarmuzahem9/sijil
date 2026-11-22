/**
 * React side of the draft autosave (specs/005 research.md R3, tasks T021/T040).
 *
 * - Text fields save about 1 s after the last keystroke, and immediately on blur.
 * - Selects, the pin and buttons save immediately (`saveNow`).
 * - The first real change creates the draft and replaces the URL with /drafts/{id}.
 * - The queue itself (merging, one request in flight, backoff, 409 handling) is AutosaveQueue.
 *
 * Values live in React state only; nothing is written to localStorage (Principle II).
 */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';

import { ApiError } from './api';
import { AutosaveQueue, type SaveState } from './autosaveQueue';
import {
  createDraft,
  patchDraft,
  type Draft,
  type DraftChanges,
  type DraftLocation,
} from './drafts';

export const TEXT_DEBOUNCE_MS = 1000;

export interface FormValues {
  subscriber_name: string;
  national_id: string;
  family_number: string;
  location: DraftLocation | null;
  address: string;
  landmark: string;
  area_id: number | null;
  tower_id: number | null;
  plan_id: number | null;
  phone_input: string;
}

export type TextField =
  'subscriber_name' | 'national_id' | 'family_number' | 'address' | 'landmark' | 'phone_input';

export const EMPTY_VALUES: FormValues = {
  subscriber_name: '',
  national_id: '',
  family_number: '',
  location: null,
  address: '',
  landmark: '',
  area_id: null,
  tower_id: null,
  plan_id: null,
  phone_input: '',
};

export function valuesFromDraft(draft: Draft | null): FormValues {
  if (!draft) return EMPTY_VALUES;
  return {
    subscriber_name: draft.subscriber_name ?? '',
    national_id: draft.national_id ?? '',
    family_number: draft.family_number ?? '',
    location: draft.location,
    address: draft.address ?? '',
    landmark: draft.landmark ?? '',
    area_id: draft.area_id,
    tower_id: draft.tower_id,
    plan_id: draft.plan_id,
    phone_input: draft.phone_input ?? '',
  };
}

/** Every field of the local form, for «الإبقاء على نسختي». */
export function allChanges(values: FormValues): DraftChanges {
  return { ...values };
}

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
  saveNow: (changes: Partial<FormValues>) => void;
  retry: () => void;
  /** Called after an image upload on this page: newer version + new server draft. */
  applyServerDraft: (draft: Draft) => void;
  /** «تحميل الأحدث». */
  loadLatest: (draft: Draft) => void;
  /** «الإبقاء على نسختي». */
  keepMine: (serverVersion: number) => void;
  /** Polling found a newer version elsewhere, or the draft was deleted. */
  pause: (state: 'conflict' | 'deleted') => void;
  /** After signing in again. */
  resume: () => void;
  /** Make sure the draft exists (e.g. before the first image upload); resolves to its id. */
  ensureCreated: () => Promise<string>;
  queue: AutosaveQueue;
}

export function useDraftAutosave(initial: Draft | null): DraftAutosave {
  const navigate = useNavigate();
  const [values, setValues] = useState<FormValues>(() => valuesFromDraft(initial));
  const [serverDraft, setServerDraft] = useState<Draft | null>(initial);
  const [saveState, setSaveState] = useState<SaveState>(initial ? 'saved' : 'idle');
  const [lastError, setLastError] = useState<ApiError | null>(null);
  const [draftId, setDraftId] = useState<string | null>(initial?.id ?? null);
  const timers = useRef(new Map<TextField, ReturnType<typeof setTimeout>>());
  // Latest local values for debounced saves; updated wherever `values` changes (never in render).
  const latest = useRef(values);

  const queue = useMemo(
    () =>
      new AutosaveQueue(
        {
          newId: () => crypto.randomUUID(),
          create: createDraft,
          patch: patchDraft,
          schedule: (fn, ms) => {
            const t = setTimeout(fn, ms);
            return () => clearTimeout(t);
          },
          onCreated: (id) => {
            setDraftId(id);
            navigate(`/drafts/${id}`, { replace: true });
          },
          onSaved: (draft) => setServerDraft(draft),
          onState: (state, error) => {
            setSaveState(state);
            setLastError(error);
          },
        },
        { id: initial?.id ?? null, version: initial?.version ?? 0 },
      ),
    // One queue per mounted form; a different draft remounts the form (keyed by id).
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [],
  );

  const flushField = useCallback(
    (field: TextField) => {
      const timer = timers.current.get(field);
      if (timer !== undefined) clearTimeout(timer);
      timers.current.delete(field);
      void queue.enqueue({ [field]: latest.current[field] });
    },
    [queue],
  );

  const setText = useCallback(
    (field: TextField, value: string) => {
      setValues((v) => ({ ...v, [field]: value }));
      latest.current = { ...latest.current, [field]: value };
      const timer = timers.current.get(field);
      if (timer !== undefined) clearTimeout(timer);
      timers.current.set(
        field,
        setTimeout(() => flushField(field), TEXT_DEBOUNCE_MS),
      );
    },
    [flushField],
  );

  const commitField = useCallback(
    (field: TextField) => {
      if (timers.current.has(field)) flushField(field);
    },
    [flushField],
  );

  const saveNow = useCallback(
    (changes: Partial<FormValues>) => {
      setValues((v) => ({ ...v, ...changes }));
      latest.current = { ...latest.current, ...changes };
      void queue.enqueue(changes);
    },
    [queue],
  );

  // Retry as soon as the browser is back online.
  useEffect(() => {
    const onOnline = () => void queue.resume();
    window.addEventListener('online', onOnline);
    return () => window.removeEventListener('online', onOnline);
  }, [queue]);

  // Flush pending debounced fields when the form unmounts (navigation inside the app).
  useEffect(() => {
    const map = timers.current;
    return () => {
      for (const [field, timer] of map) {
        clearTimeout(timer);
        void queue.enqueue({ [field]: latest.current[field] });
      }
      map.clear();
    };
  }, [queue]);

  const ensureCreated = useCallback(() => queue.ensureCreated(), [queue]);

  return {
    draftId,
    values,
    serverDraft,
    saveState,
    lastError,
    setText,
    commitField,
    saveNow,
    retry: () => void queue.resume(),
    applyServerDraft: (draft) => {
      queue.setVersion(draft.version);
      setServerDraft(draft);
    },
    loadLatest: (draft) => {
      for (const timer of timers.current.values()) clearTimeout(timer);
      timers.current.clear();
      queue.reset(draft);
      setServerDraft(draft);
      const fresh = valuesFromDraft(draft);
      latest.current = fresh;
      setValues(fresh);
    },
    keepMine: (serverVersion) => void queue.keepMine(allChanges(latest.current), serverVersion),
    pause: (state) => queue.pause(state),
    resume: () => void queue.resume(),
    ensureCreated,
    queue,
  };
}
