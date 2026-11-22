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
import {
  createDraft,
  getDraftVersion,
  patchDraft,
  type Draft,
  type DraftChanges,
  type DraftLocation,
  type DraftNotice,
} from './drafts';

export const TEXT_DEBOUNCE_MS = 1000;
/** Detect a save made elsewhere within 30 s (SC-004). */
export const VERSION_POLL_MS = 15_000;

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

const SUBSCRIPTION_KEYS = ['area_id', 'tower_id', 'plan_id'] as const;

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
  readonly queue: AutosaveQueue;

  constructor(private readonly initial: Draft | null) {
    this.current = valuesFromDraft(initial);
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

  private onSaved(draft: Draft): void {
    this.listener?.serverDraft(draft);
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
    void this.queue.enqueue({ [field]: this.current[field] });
  }

  /** Text typed: saved ~1 s after the last keystroke. */
  setText(field: TextField, value: string): void {
    this.update({ [field]: value });
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
  saveNow(changes: Partial<FormValues>): void {
    this.update(changes);
    void this.queue.enqueue(changes as DraftChanges);
  }

  /** «تحميل الأحدث». */
  loadLatest(draft: Draft): void {
    for (const timer of this.timers.values()) clearTimeout(timer);
    this.timers.clear();
    this.queue.reset(draft);
    this.listener?.serverDraft(draft);
    this.listener?.notices(draft.notices);
    this.current = valuesFromDraft(draft);
    this.listener?.values(this.current);
  }

  /** «الإبقاء على نسختي»: every local field over the newer server version. */
  keepMine(): void {
    void this.queue.keepMine(
      { ...this.current },
      Math.max(this.queue.currentVersion, this.newerVersion),
    );
  }

  /** An upload on this page moved the version forward. */
  applyServerDraft(draft: Draft): void {
    this.queue.setVersion(draft.version);
    this.listener?.serverDraft(draft);
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
