/**
 * Autosave queue for one draft (specs/005 research.md R3). Pure logic: no React and no timers
 * of its own, so it can be tested with fakes (__tests__/autosaveQueue.test.ts).
 *
 * - Changes are merged into `pending`; one request is in flight at a time, and changes made
 *   during it go into the next PATCH.
 * - The first save creates the draft (PUT with a client UUID). A retried create is followed by
 *   a PATCH of the same changes, because an idempotent PUT on an existing draft changes nothing.
 * - 409 from this same page (`same_client`) → silent rebase on the new version and resend.
 *   409 from another page/device → state `conflict`, paused until the user chooses.
 * - Network / 5xx → `offline` with backoff 2, 4, 8, 16, 30 s; `failed` after 3 attempts.
 * - Session ended → `session_ended`, paused with the pending changes kept; `resume()` sends them.
 *
 * Nothing is persisted: card data never touches device storage (Principle II).
 */
import { ApiError, NETWORK_ERROR_MESSAGE } from './api';
import { conflictInfo, type Draft, type DraftChanges } from './drafts';

export type SaveState =
  'idle' | 'saving' | 'saved' | 'offline' | 'failed' | 'conflict' | 'deleted' | 'session_ended';

export interface QueueDeps {
  newId: () => string;
  create: (id: string, changes: DraftChanges) => Promise<Draft>;
  patch: (id: string, version: number, changes: DraftChanges) => Promise<Draft>;
  /** Run `fn` after `ms`; returns a cancel function. */
  schedule: (fn: () => void, ms: number) => () => void;
  onCreated?: (id: string) => void;
  onSaved?: (draft: Draft) => void;
  onState?: (state: SaveState, error: ApiError | null) => void;
}

export const FAILED_AFTER = 3;
const BACKOFF_MS = [2000, 4000, 8000, 16000, 30000];
const SESSION_ENDED_CODES = new Set(['session_revoked', 'not_authenticated', 'token_expired']);

export function backoffMs(failures: number): number {
  return BACKOFF_MS[Math.min(Math.max(failures, 1), BACKOFF_MS.length) - 1];
}

const isEmpty = (changes: DraftChanges) => Object.keys(changes).length === 0;

export class AutosaveQueue {
  private id: string | null;
  private version: number;
  private pending: DraftChanges = {};
  private inFlight: Promise<void> | null = null;
  private failures = 0;
  private paused = false;
  private createRetried = false;
  private cancelRetry: (() => void) | null = null;
  state: SaveState = 'idle';
  lastError: ApiError | null = null;

  constructor(
    private readonly deps: QueueDeps,
    initial: { id: string | null; version: number } = { id: null, version: 0 },
  ) {
    this.id = initial.id;
    this.version = initial.version;
  }

  get draftId(): string | null {
    return this.id;
  }

  get currentVersion(): number {
    return this.version;
  }

  get hasPending(): boolean {
    return !isEmpty(this.pending) || this.inFlight !== null;
  }

  /** Merge `changes` into the next save and start it unless one is running or paused. */
  enqueue(changes: DraftChanges): Promise<void> {
    this.pending = { ...this.pending, ...changes };
    return this.flush();
  }

  /** A save made elsewhere on this page (an image upload) moved the version forward. */
  setVersion(version: number): void {
    if (version > this.version) this.version = version;
  }

  /** «تحميل الأحدث»: drop local pending changes and continue from the server's draft. */
  reset(draft: Draft): void {
    this.cancelTimer();
    this.pending = {};
    this.version = draft.version;
    this.failures = 0;
    this.paused = false;
    this.setState('saved', null);
  }

  /** «الإبقاء على نسختي»: send every local field on top of the server's current version. */
  keepMine(allFields: DraftChanges, serverVersion: number): Promise<void> {
    this.pending = { ...allFields, ...this.pending };
    this.version = serverVersion;
    this.paused = false;
    return this.flush();
  }

  /** After signing in again, after `online`, or on «إعادة المحاولة». */
  resume(): Promise<void> {
    if (this.state === 'conflict' || this.state === 'deleted') return Promise.resolve();
    this.cancelTimer();
    this.paused = false;
    return this.flush();
  }

  /** Stop saving (conflict / deleted detected by polling). */
  pause(state: 'conflict' | 'deleted'): void {
    this.cancelTimer();
    this.paused = true;
    this.setState(state, null);
  }

  /** Make sure the draft exists on the server (before the first image upload). */
  async ensureCreated(): Promise<string> {
    if (this.inFlight) await this.inFlight;
    if (this.id !== null && this.version > 0) return this.id;
    if (!this.paused) {
      const sending = this.pending;
      this.pending = {};
      this.cancelTimer();
      this.setState('saving', null);
      this.inFlight = this.send(sending).finally(() => {
        this.inFlight = null;
      });
      await this.inFlight;
    }
    if (this.id !== null && this.version > 0) return this.id;
    throw this.lastError ?? new ApiError('network_error', NETWORK_ERROR_MESSAGE, 0);
  }

  flush(): Promise<void> {
    if (this.inFlight) return this.inFlight;
    if (this.paused || isEmpty(this.pending)) return Promise.resolve();
    this.cancelTimer();
    const sending = this.pending;
    this.pending = {};
    this.setState('saving', null);
    this.inFlight = this.send(sending).finally(() => {
      this.inFlight = null;
    });
    return this.inFlight.then(() => {
      if (
        !this.paused &&
        !isEmpty(this.pending) &&
        this.state !== 'offline' &&
        this.state !== 'failed'
      )
        return this.flush();
    });
  }

  private async send(sending: DraftChanges): Promise<void> {
    try {
      let draft: Draft;
      if (this.id === null || this.version === 0) {
        const id = this.id ?? this.deps.newId();
        if (this.id === null) {
          this.id = id;
          this.deps.onCreated?.(id);
        }
        draft = await this.deps.create(id, sending);
        if (this.createRetried) {
          // The first PUT may have created the draft without us seeing the answer.
          this.version = draft.version;
          draft = await this.deps.patch(id, draft.version, sending);
        }
      } else {
        draft = await this.deps.patch(this.id, this.version, sending);
      }
      this.version = draft.version;
      this.failures = 0;
      this.createRetried = false;
      this.deps.onSaved?.(draft);
      this.setState(isEmpty(this.pending) ? 'saved' : 'saving', null);
    } catch (err) {
      this.handleError(err, sending);
    }
  }

  private handleError(err: unknown, sending: DraftChanges): void {
    const requeue = () => {
      this.pending = { ...sending, ...this.pending };
    };
    const conflict = conflictInfo(err);
    if (conflict) {
      requeue();
      this.version = conflict.version;
      if (conflict.same_client) {
        this.setState('saving', null); // rebase silently; flush() continues
        return;
      }
      this.paused = true;
      this.setState('conflict', err as ApiError);
      return;
    }
    const apiErr = err instanceof ApiError ? err : new ApiError('network_error', '', 0);
    if (apiErr.code === 'draft_not_found') {
      this.paused = true;
      this.setState('deleted', apiErr);
      return;
    }
    if (SESSION_ENDED_CODES.has(apiErr.code)) {
      requeue();
      this.paused = true;
      this.setState('session_ended', apiErr);
      return;
    }
    if (apiErr.status === 0 || apiErr.status >= 500) {
      requeue();
      if (this.id !== null && this.version === 0) this.createRetried = true;
      this.failures += 1;
      this.setState(this.failures >= FAILED_AFTER ? 'failed' : 'offline', apiErr);
      this.cancelRetry = this.deps.schedule(() => {
        this.cancelRetry = null;
        void this.flush();
      }, backoffMs(this.failures));
      return;
    }
    // A refused value (e.g. `too_long`): retrying cannot help. The field shows the error and
    // the next edit of that field is sent again.
    this.setState('failed', apiErr);
  }

  private cancelTimer(): void {
    this.cancelRetry?.();
    this.cancelRetry = null;
  }

  private setState(state: SaveState, error: ApiError | null): void {
    this.state = state;
    this.lastError = error;
    this.deps.onState?.(state, error);
  }
}
