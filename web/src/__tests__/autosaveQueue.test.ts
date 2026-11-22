import { describe, expect, it, vi } from 'vitest';

import { ApiError } from '../lib/api';
import { AutosaveQueue, backoffMs, FAILED_AFTER, type QueueDeps } from '../lib/autosaveQueue';
import type { Draft, DraftChanges } from '../lib/drafts';

function draft(version: number, extra: Partial<Draft> = {}): Draft {
  return { id: 'd1', version, ...extra } as Draft;
}

function deferred<T>() {
  let resolve!: (v: T) => void;
  let reject!: (e: unknown) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

function setup(initial = { id: 'd1' as string | null, version: 1 }) {
  const timers: { fn: () => void; ms: number }[] = [];
  const states: string[] = [];
  const deps = {
    newId: vi.fn(() => 'new-id'),
    create: vi.fn<QueueDeps['create']>(),
    patch: vi.fn<QueueDeps['patch']>(),
    schedule: vi.fn((fn: () => void, ms: number) => {
      const t = { fn, ms };
      timers.push(t);
      return () => {
        const i = timers.indexOf(t);
        if (i >= 0) timers.splice(i, 1);
      };
    }),
    onCreated: vi.fn(),
    onState: vi.fn((s: string) => void states.push(s)),
  };
  const queue = new AutosaveQueue(deps, initial);
  return { deps, queue, timers, states };
}

const conflict = (version: number, sameClient: boolean) =>
  new ApiError('draft_conflict', 'تغيّرت المسودة من جهاز آخر', 409, {
    version,
    updated_at: '2026-11-22T00:00:00Z',
    same_client: sameClient,
  });
const network = () => new ApiError('network_error', 'تعذّر الاتصال', 0);

describe('AutosaveQueue', () => {
  it('creates the draft on the first change with a client UUID', async () => {
    const { deps, queue } = setup({ id: null, version: 0 });
    deps.create.mockResolvedValue(draft(1));
    await queue.enqueue({ subscriber_name: 'مشترك' });
    expect(deps.onCreated).toHaveBeenCalledWith('new-id');
    expect(deps.create).toHaveBeenCalledWith('new-id', { subscriber_name: 'مشترك' });
    expect(queue.currentVersion).toBe(1);
    expect(queue.state).toBe('saved');
  });

  it('keeps one request in flight and merges changes made meanwhile', async () => {
    const { deps, queue } = setup();
    const first = deferred<Draft>();
    deps.patch.mockReturnValueOnce(first.promise).mockResolvedValueOnce(draft(3));
    const done = queue.enqueue({ address: 'أ' });
    void queue.enqueue({ landmark: 'ب' });
    void queue.enqueue({ address: 'ج' });
    expect(deps.patch).toHaveBeenCalledTimes(1);
    first.resolve(draft(2));
    await done;
    await queue.flush();
    expect(deps.patch).toHaveBeenCalledTimes(2);
    expect(deps.patch).toHaveBeenLastCalledWith('d1', 2, { landmark: 'ب', address: 'ج' });
    expect(queue.currentVersion).toBe(3);
  });

  it('backs off 2, 4, 8 … up to 30 s and reports failed after 3 attempts', async () => {
    expect([1, 2, 3, 4, 5, 6, 9].map(backoffMs)).toEqual([
      2000, 4000, 8000, 16000, 30000, 30000, 30000,
    ]);
    const { deps, queue, timers, states } = setup();
    deps.patch.mockRejectedValue(network());
    await queue.enqueue({ address: 'أ' });
    expect(queue.state).toBe('offline');
    expect(timers.map((t) => t.ms)).toEqual([2000]);
    for (let i = 1; i < FAILED_AFTER; i++) {
      timers.shift()!.fn();
      await queue.flush();
    }
    expect(queue.state).toBe('failed');
    expect(timers.map((t) => t.ms)).toEqual([8000]);
    expect(states).toContain('offline');
    // The value is still queued and is sent once the network is back.
    deps.patch.mockResolvedValue(draft(2));
    await queue.resume();
    expect(deps.patch).toHaveBeenLastCalledWith('d1', 1, { address: 'أ' });
    expect(queue.state).toBe('saved');
    expect(timers).toHaveLength(0);
  });

  it('rebases silently on a 409 from the same page (same_client)', async () => {
    const { deps, queue, states } = setup();
    deps.patch.mockRejectedValueOnce(conflict(2, true)).mockResolvedValueOnce(draft(3));
    await queue.enqueue({ address: 'أ' });
    await queue.flush();
    expect(deps.patch).toHaveBeenNthCalledWith(2, 'd1', 2, { address: 'أ' });
    expect(queue.state).toBe('saved');
    expect(states).not.toContain('conflict');
  });

  it('pauses on a 409 from another page or device and keeps the changes', async () => {
    const { deps, queue } = setup();
    deps.patch.mockRejectedValueOnce(conflict(5, false));
    await queue.enqueue({ address: 'أ' });
    expect(queue.state).toBe('conflict');
    await queue.enqueue({ landmark: 'ب' });
    await queue.resume(); // resume does not override a conflict
    expect(deps.patch).toHaveBeenCalledTimes(1);

    // «الإبقاء على نسختي»: every local field on top of the server's version.
    deps.patch.mockResolvedValueOnce(draft(6));
    const all: DraftChanges = { address: 'أ', landmark: 'ب', subscriber_name: 'مشترك' };
    await queue.keepMine(all, 5);
    expect(deps.patch).toHaveBeenLastCalledWith('d1', 5, all);
    expect(queue.state).toBe('saved');
  });

  it('«تحميل الأحدث» drops local pending changes', async () => {
    const { deps, queue } = setup();
    deps.patch.mockRejectedValueOnce(conflict(5, false));
    await queue.enqueue({ address: 'أ' });
    queue.reset(draft(5));
    expect(queue.hasPending).toBe(false);
    expect(queue.currentVersion).toBe(5);
    expect(queue.state).toBe('saved');
  });

  it('stops with state deleted on 404', async () => {
    const { deps, queue } = setup();
    deps.patch.mockRejectedValueOnce(new ApiError('draft_not_found', 'المسودة غير موجودة', 404));
    await queue.enqueue({ address: 'أ' });
    expect(queue.state).toBe('deleted');
    await queue.enqueue({ address: 'ب' });
    expect(deps.patch).toHaveBeenCalledTimes(1);
  });

  it('pauses on session end and sends the kept changes after resume()', async () => {
    const { deps, queue } = setup();
    deps.patch.mockRejectedValueOnce(new ApiError('session_revoked', 'انتهت الجلسة', 401));
    await queue.enqueue({ address: 'أ' });
    expect(queue.state).toBe('session_ended');
    await queue.enqueue({ landmark: 'ب' });
    expect(deps.patch).toHaveBeenCalledTimes(1);
    deps.patch.mockResolvedValueOnce(draft(2));
    await queue.resume();
    expect(deps.patch).toHaveBeenLastCalledWith('d1', 1, { address: 'أ', landmark: 'ب' });
    expect(queue.state).toBe('saved');
  });

  it('follows a retried create with a PATCH of the same changes', async () => {
    const { deps, queue, timers } = setup({ id: null, version: 0 });
    deps.create.mockRejectedValueOnce(network()).mockResolvedValueOnce(draft(1));
    deps.patch.mockResolvedValueOnce(draft(2));
    await queue.enqueue({ address: 'أ' });
    timers.shift()!.fn();
    await queue.flush();
    expect(deps.create).toHaveBeenCalledTimes(2);
    expect(deps.create).toHaveBeenLastCalledWith('new-id', { address: 'أ' });
    expect(deps.patch).toHaveBeenCalledWith('new-id', 1, { address: 'أ' });
    expect(queue.currentVersion).toBe(2);
  });

  it('applies a newer version from an upload on this page', async () => {
    const { deps, queue } = setup();
    queue.setVersion(4);
    queue.setVersion(2); // never goes back
    deps.patch.mockResolvedValueOnce(draft(5));
    await queue.enqueue({ address: 'أ' });
    expect(deps.patch).toHaveBeenCalledWith('d1', 4, { address: 'أ' });
  });

  it('does not retry a refused value', async () => {
    const { deps, queue, timers } = setup();
    deps.patch.mockRejectedValueOnce(
      new ApiError('too_long', 'النص أطول من المسموح', 422, { field: 'landmark' }),
    );
    await queue.enqueue({ landmark: 'x' });
    expect(queue.state).toBe('failed');
    expect(queue.lastError?.code).toBe('too_long');
    expect(timers).toHaveLength(0);
  });
});

describe('AutosaveQueue.ensureCreated', () => {
  it('creates the draft once, with any pending text', async () => {
    const { deps, queue } = setup({ id: null, version: 0 });
    deps.create.mockResolvedValue(draft(1));
    await expect(queue.ensureCreated()).resolves.toBe('new-id');
    await expect(queue.ensureCreated()).resolves.toBe('new-id');
    expect(deps.create).toHaveBeenCalledTimes(1);
  });

  it('rejects when the create fails, so the upload can show its error', async () => {
    const { deps, queue } = setup({ id: null, version: 0 });
    deps.create.mockRejectedValue(network());
    await expect(queue.ensureCreated()).rejects.toMatchObject({ code: 'network_error' });
  });
});

describe('AutosaveQueue.touch', () => {
  it('sends an empty PATCH so the server refreshes catalog copies', async () => {
    const { deps, queue } = setup();
    deps.patch.mockResolvedValueOnce(draft(2));
    await queue.touch();
    expect(deps.patch).toHaveBeenCalledWith('d1', 1, {});
  });

  it('never creates a draft by itself', async () => {
    const { deps, queue } = setup({ id: null, version: 0 });
    await queue.touch();
    expect(deps.create).not.toHaveBeenCalled();
  });

  it('reports pending keys', async () => {
    const { deps, queue } = setup();
    deps.patch.mockReturnValue(new Promise(() => undefined));
    void queue.enqueue({ address: 'أ' });
    void queue.enqueue({ plan_id: 3 });
    expect(queue.hasPendingKey('plan_id')).toBe(true);
    expect(queue.hasPendingKey('area_id')).toBe(false);
  });
});

describe('AutosaveQueue.pause', () => {
  it('keeps the conflict state when an in-flight save finishes', async () => {
    const { deps, queue } = setup();
    const inFlight = deferred<Draft>();
    deps.patch.mockReturnValueOnce(inFlight.promise);
    const done = queue.enqueue({ address: 'أ' });
    queue.pause('conflict');
    inFlight.resolve(draft(2));
    await done;
    expect(queue.state).toBe('conflict');
    await queue.enqueue({ landmark: 'ب' });
    expect(deps.patch).toHaveBeenCalledTimes(1);
  });
});
