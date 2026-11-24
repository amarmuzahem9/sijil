/**
 * «فتح طلب برقمه» (specs/011 US6: FR-022, research R8): the box opens the file of any request by
 * its number, shows «لا يوجد طلب بهذا الرقم» for an unknown one, and stays disabled while the text
 * is not a request number. Synthetic values only.
 */
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { createMemoryRouter, RouterProvider } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { ApiError } from '../lib/api';

const findByNumber = vi.fn();
vi.mock('../lib/adminRequests', async (original) => ({
  ...(await original<typeof import('../lib/adminRequests')>()),
  findByNumber: (...args: unknown[]) => findByNumber(...args),
}));

import { OpenByNumber } from '../pages/admin/pending/OpenByNumber';

beforeEach(() => {
  findByNumber.mockReset();
});
afterEach(cleanup);

function show() {
  const router = createMemoryRouter(
    [
      { path: '/admin/pending', element: <OpenByNumber /> },
      { path: '/admin/pending/:requestId', element: <div>ملف الطلب</div> },
    ],
    { initialEntries: ['/admin/pending'] },
  );
  render(<RouterProvider router={router} />);
  return router;
}

const box = () => screen.getByRole('textbox', { name: 'فتح طلب برقمه' }) as HTMLInputElement;
const open = () => screen.getByRole('button', { name: 'فتح' }) as HTMLButtonElement;

describe('OpenByNumber', () => {
  it('stays disabled until the text is a request number', () => {
    show();
    expect(open().disabled).toBe(true);
    fireEvent.change(box(), { target: { value: 'T3C-' } });
    expect(open().disabled).toBe(true);
    fireEvent.change(box(), { target: { value: '١٠٠٥' } });
    expect(open().disabled).toBe(false);
  });

  it('opens the file of the request found', async () => {
    findByNumber.mockResolvedValue({ id: 42 });
    const router = show();
    fireEvent.change(box(), { target: { value: 'T3C-1005' } });
    fireEvent.click(open());
    await waitFor(() => expect(router.state.location.pathname).toBe('/admin/pending/42'));
    expect(findByNumber).toHaveBeenCalledWith('T3C-1005');
  });

  it('opens on Enter too', async () => {
    findByNumber.mockResolvedValue({ id: 43 });
    const router = show();
    fireEvent.change(box(), { target: { value: '1006' } });
    fireEvent.submit(box().closest('form')!);
    await waitFor(() => expect(router.state.location.pathname).toBe('/admin/pending/43'));
  });

  it('shows «لا يوجد طلب بهذا الرقم» for an unknown number', async () => {
    findByNumber.mockImplementation(async () => {
      throw new ApiError('request_not_found', 'لا يوجد طلب بهذا الرقم', 404);
    });
    const router = show();
    fireEvent.change(box(), { target: { value: '999999' } });
    fireEvent.click(open());
    expect(await screen.findByText('لا يوجد طلب بهذا الرقم')).toBeTruthy();
    expect(router.state.location.pathname).toBe('/admin/pending');
  });
});
