/**
 * Imperative side of the new-subscriber form (specs/005 research.md R3): the current values,
 * the per-field debounce timers, the autosave queue and the version polling. It lives outside
 * React so timers and queue callbacks always see the current values; `useDraftAutosave` mirrors
 * its state into React through the `FormListener`.
 *
 * Values are kept in memory only; nothing is written to device storage (Principle II).
 */
import { ApiError } from './api';
import { AutosaveQueue, type SaveState } from './autosaveQueue';
import { fieldsToMerge, READING_POLL_MS, shouldPoll } from './cardReading';
import {
  CARD_FIELDS,
  createDraft,
  getCardReadingStatus,
  getDraft,
  getDraftVersion,
  patchDraft,
  retryCardReading,
  type CardField,
  type Draft,
  type DraftChanges,
  type DraftLocation,
  type DraftNotice,
} from './drafts';
import { isTooLong, type LimitedField } from './draftValidation';
import { cleanArabicName, cleanPlaceText } from './arabicName';
import { isNameField, NAME_FIELDS, type NameField, type NameValues } from './nameFields';

export const TEXT_DEBOUNCE_MS = 1000;
/** Detect a save made elsewhere within 30 s (SC-004). */
export const VERSION_POLL_MS = 15_000;

export interface FormValues extends NameValues {
  national_id: string;
  family_number: string;
  location: DraftLocation | null;
  address: string;
  landmark: string;
  area_id: number | null;
  tower_id: number | null;
  plan_id: number | null;
  phone_input: string;
  /** «لا يوجد لقب على البطاقة» (specs/006 FR-017). */
  no_surname: boolean;
  /** Back of the card: dates as YYYY-MM-DD ('' when empty) and text. */
  birth_date: string;
  birth_place: string;
  issue_date: string;
  expiry_date: string;
  issuing_authority: string;
}

export type TextField =
  | NameField
  | 'national_id'
  | 'family_number'
  | 'address'
  | 'landmark'
  | 'phone_input'
  | 'birth_place'
  | 'issuing_authority';

const SUBSCRIPTION_KEYS = ['area_id', 'tower_id', 'plan_id'] as const;

const EMPTY_NAMES = Object.fromEntries(NAME_FIELDS.map((f) => [f, ''])) as NameValues;

export const EMPTY_VALUES: FormValues = {
  ...EMPTY_NAMES,
  national_id: '',
  family_number: '',
  location: null,
  address: '',
  landmark: '',
  area_id: null,
  tower_id: null,
  plan_id: null,
  phone_input: '',
  no_surname: false,
  birth_date: '',
  birth_place: '',
  issue_date: '',
  expiry_date: '',
  issuing_authority: '',
};

export function valuesFromDraft(draft: Draft | null): FormValues {
  if (!draft) return EMPTY_VALUES;
  return {
    ...(Object.fromEntries(NAME_FIELDS.map((f) => [f, draft[f] ?? ''])) as NameValues),
    national_id: draft.national_id ?? '',
    family_number: draft.family_number ?? '',
    location: draft.location,
    address: draft.address ?? '',
    landmark: draft.landmark ?? '',
    area_id: draft.area_id,
    tower_id: draft.tower_id,
    plan_id: draft.plan_id,
    phone_input: draft.phone_input ?? '',
    no_surname: draft.no_surname ?? false,
    birth_date: draft.birth_date ?? '',
    birth_place: draft.birth_place ?? '',
    issue_date: draft.issue_date ?? '',
    expiry_date: draft.expiry_date ?? '',
    issuing_authority: draft.issuing_authority ?? '',
  };
}

/** False for a value the server refuses outright: a name with a digit or a non-Arabic letter,
 * or text over its limit. Such a value stays on screen with its error and is not sent. */
export function sendable(field: TextField, value: string): boolean {
  if (isTooLong(field as LimitedField, value)) return false;
  if (field === 'birth_place') return cleanPlaceText(value).ok;
  return !isNameField(field) || cleanArabicName(value).ok;
}

/** The back-of-card dates: '' on screen, null for the server (specs/006, system.md v1.8). */
export const DATE_FIELDS = ['birth_date', 'issue_date', 'expiry_date'] as const;

function toChanges(values: Partial<FormValues>): DraftChanges {
  const changes = { ...values } as Record<string, unknown>;
  for (const field of DATE_FIELDS) if (changes[field] === '') changes[field] = null;
  return changes as DraftChanges;
}

export interface FormListener {
  values: (values: FormValues) => void;
  serverDraft: (draft: Draft) => void;
  state: (state: SaveState, error: ApiError | null) => void;
  notices: (notices: DraftNotice[]) => void;
  created: (id: string) => void;
}

export class DraftFormController {
  private current: FormValues;
  private readonly timers = new Map<TextField, ReturnType<typeof setTimeout>>();
  private listener: FormListener | null = null;
  private newerVersion = 0;
  private touched = false;
  /** The latest draft from the server (card reading state and marks live there). */
  private server: Draft | null;
  readonly queue: AutosaveQueue;

  constructor(private readonly initial: Draft | null) {
    this.current = valuesFromDraft(initial);
    this.server = initial;
    this.queue = new AutosaveQueue(
      {
        newId: () => crypto.randomUUID(),
        create: createDraft,
        patch: patchDraft,
        schedule: (fn, ms) => {
          const t = setTimeout(fn, ms);
          return () => clearTimeout(t);
        },
        onCreated: (id) => this.listener?.created(id),
        onSaved: (draft) => this.onSaved(draft),
        onState: (state, error) => this.listener?.state(state, error),
      },
      { id: initial?.id ?? null, version: initial?.version ?? 0 },
    );
  }

  /** Connect React; returns the cleanup that flushes pending fields on unmount. */
  attach(listener: FormListener): () => void {
    this.listener = listener;
    // Opening a draft whose choice or price changed: one save refreshes the copies (R4).
    if (!this.touched && this.initial?.notices.length) {
      this.touched = true;
      void this.queue.touch();
    }
    const onOnline = () => void this.queue.resume();
    window.addEventListener('online', onOnline);
    return () => {
      window.removeEventListener('online', onOnline);
      for (const [field, timer] of this.timers) {
        clearTimeout(timer);
        if (sendable(field, this.current[field]))
          void this.queue.enqueue({ [field]: this.current[field] });
      }
      this.timers.clear();
      this.listener = null;
    };
  }

  get values(): FormValues {
    return this.current;
  }

  private update(changes: Partial<FormValues>): void {
    this.current = { ...this.current, ...changes };
    this.listener?.values(this.current);
  }

  private setServer(draft: Draft): void {
    this.server = draft;
    this.listener?.serverDraft(draft);
  }

  private onSaved(draft: Draft): void {
    this.setServer(draft);
    if (draft.notices.length) this.listener?.notices(draft.notices);
    // The server may clear an unavailable choice (R4); adopt that unless the user changed the
    // same field meanwhile.
    const fromServer: Partial<FormValues> = {};
    for (const key of SUBSCRIPTION_KEYS) {
      if (!this.queue.hasPendingKey(key) && this.current[key] !== draft[key])
        fromServer[key] = draft[key];
    }
    if (Object.keys(fromServer).length) this.update(fromServer);
  }

  private flushField(field: TextField): void {
    const timer = this.timers.get(field);
    if (timer !== undefined) clearTimeout(timer);
    this.timers.delete(field);
    if (!sendable(field, this.current[field])) return; // the field shows its error
    void this.queue.enqueue({ [field]: this.current[field] });
  }

  /** Text typed: saved ~1 s after the last keystroke. */
  setText(field: TextField, value: string): void {
    // Typing a surname clears «لا يوجد لقب على البطاقة» (the server does the same).
    const extra = field === 'surname' && value.trim() && this.current.no_surname;
    this.update(extra ? { [field]: value, no_surname: false } : { [field]: value });
    const timer = this.timers.get(field);
    if (timer !== undefined) clearTimeout(timer);
    this.timers.set(
      field,
      setTimeout(() => this.flushField(field), TEXT_DEBOUNCE_MS),
    );
  }

  /** Field left (blur): save now if a change is waiting. */
  commitField(field: TextField): void {
    if (this.timers.has(field)) this.flushField(field);
  }

  /** Selects, the pin and buttons: save immediately. */
  saveNow(changes: Partial<FormValues> & { national_id_confirmed?: boolean }): void {
    const { national_id_confirmed, ...values } = changes;
    this.update(values);
    const out = toChanges(values);
    // «اعتماد هذا الرقم» (specs/006 FR-012): sent with the value it confirms.
    if (national_id_confirmed) out.national_id_confirmed = true;
    void this.queue.enqueue(out);
  }

  /** «تحميل الأحدث». */
  loadLatest(draft: Draft): void {
    for (const timer of this.timers.values()) clearTimeout(timer);
    this.timers.clear();
    this.queue.reset(draft);
    this.setServer(draft);
    this.listener?.notices(draft.notices);
    this.current = valuesFromDraft(draft);
    this.listener?.values(this.current);
  }

  /** «الإبقاء على نسختي»: every local field over the newer server version. */
  keepMine(): void {
    const mine = { ...this.current } as Record<string, unknown>;
    for (const field of [
      ...NAME_FIELDS,
      'national_id',
      'family_number',
      'address',
      'landmark',
      'phone_input',
      'birth_place',
      'issuing_authority',
    ] as TextField[]) {
      if (!sendable(field, this.current[field])) delete mine[field];
    }
    void this.queue.keepMine(
      toChanges(mine as Partial<FormValues>) as Record<string, unknown>,
      Math.max(this.queue.currentVersion, this.newerVersion),
    );
  }

  /** An upload on this page moved the version forward. */
  applyServerDraft(draft: Draft): void {
    this.queue.setVersion(draft.version);
    this.setServer(draft);
  }

  /** A field with a change typed or queued on this page: a reading must not replace it. */
  private hasLocalChange(field: CardField | 'no_surname'): boolean {
    return this.queue.hasPendingKey(field) || this.timers.has(field as TextField);
  }

  /**
   * A reading finished (specs/006 research R8): take the card fields and their marks from the
   * server, except fields with a local change still waiting (the typed value wins and is sent
   * by the queue).
   */
  mergeReading(draft: Draft): void {
    if (draft.version > this.queue.currentVersion) this.queue.setVersion(draft.version);
    this.setServer(draft);
    const changes: Partial<FormValues> = {};
    for (const field of fieldsToMerge(CARD_FIELDS, (f) => this.hasLocalChange(f))) {
      const value = draft[field] ?? '';
      if (this.current[field] !== value) changes[field] = value;
    }
    if (!this.hasLocalChange('no_surname') && this.current.no_surname !== draft.no_surname)
      changes.no_surname = draft.no_surname;
    if (Object.keys(changes).length) this.update(changes);
  }

  /** «أعد المحاولة» (US5): re-read the failed sides; the 2-second poll then follows them. */
  async retryReading(draftId: string): Promise<void> {
    const reading = await retryCardReading(draftId);
    if (this.server) this.setServer({ ...this.server, card_reading: reading });
  }

  /**
   * While a card reading waits or runs, poll its status every 2 s (research R5). When it
   * finishes after an upload from this page (`same_client`), fetch the draft and merge it; a
   * reading started elsewhere is left to the version poll and the conflict notice.
   */
  startReadingPoll(draftId: string): () => void {
    let stopped = false;
    let busy = false;
    const check = async () => {
      if (stopped || busy || !shouldPoll(this.server?.card_reading)) return;
      if (['conflict', 'deleted', 'session_ended'].includes(this.queue.state)) return;
      busy = true;
      try {
        const status = await getCardReadingStatus(draftId);
        if (stopped || !this.server) return;
        const reading = { front: status.front, back: status.back };
        if (shouldPoll(reading)) {
          this.setServer({ ...this.server, card_reading: reading });
          return;
        }
        if (status.same_client) this.mergeReading(await getDraft(draftId));
        else this.setServer({ ...this.server, card_reading: reading });
      } catch {
        // Network trouble: try again on the next tick.
      } finally {
        busy = false;
      }
    };
    const timer = setInterval(() => void check(), READING_POLL_MS);
    return () => {
      stopped = true;
      clearInterval(timer);
    };
  }

  /** Poll the version while the page is visible (R3); returns the stop function. */
  startPolling(draftId: string): () => void {
    let stopped = false;
    const check = async () => {
      if (stopped || document.visibilityState !== 'visible') return;
      if (['conflict', 'deleted', 'session_ended'].includes(this.queue.state)) return;
      try {
        const info = await getDraftVersion(draftId);
        if (stopped || info.version <= this.queue.currentVersion) return;
        if (info.same_client) this.queue.setVersion(info.version);
        else {
          this.newerVersion = info.version;
          this.queue.pause('conflict');
        }
      } catch (err) {
        if (!stopped && err instanceof ApiError && err.code === 'draft_not_found')
          this.queue.pause('deleted');
      }
    };
    const timer = setInterval(() => void check(), VERSION_POLL_MS);
    const onVisible = () => void check();
    document.addEventListener('visibilitychange', onVisible);
    window.addEventListener('focus', onVisible);
    return () => {
      stopped = true;
      clearInterval(timer);
      document.removeEventListener('visibilitychange', onVisible);
      window.removeEventListener('focus', onVisible);
    };
  }
}
