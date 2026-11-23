/**
 * «رقم واتساب الإدارة» in «الإعدادات ← عام» (specs/009 FR-005b, T035): saved on its own, shows the
 * server's error, and empty clears it. The OTP minutes keep their own save.
 */
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { ApiError } from '../lib/api';

const api = vi.hoisted(() => ({ get: vi.fn(), update: vi.fn() }));
vi.mock('../lib/settings', () => ({ generalApi: api }));

import GeneralTab from '../pages/admin/settings/GeneralTab';

function show() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <GeneralTab />
    </QueryClientProvider>,
  );
}

const field = () => screen.findByLabelText('رقم واتساب الإدارة');

beforeEach(() => {
  api.get.mockResolvedValue({ otp_validity_minutes: 60, admin_whatsapp: null });
});
afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe('رقم واتساب الإدارة', () => {
  it('saves only the number', async () => {
    api.update.mockResolvedValue({ otp_validity_minutes: 60, admin_whatsapp: '07701112233' });
    show();
    fireEvent.change(await field(), { target: { value: '+964 770 111 2233' } });
    fireEvent.click(screen.getByRole('button', { name: 'حفظ الرقم' }));
    await waitFor(() =>
      expect(api.update).toHaveBeenCalledWith({ admin_whatsapp: '+964 770 111 2233' }),
    );
    await waitFor(() =>
      expect((screen.getByLabelText('رقم واتساب الإدارة') as HTMLInputElement).value).toBe(
        '07701112233',
      ),
    );
  });

  it('shows the server error', async () => {
    api.update.mockRejectedValue(new ApiError('invalid_phone', 'رقم غير صالح', 422));
    show();
    fireEvent.change(await field(), { target: { value: '0770' } });
    fireEvent.click(screen.getByRole('button', { name: 'حفظ الرقم' }));
    expect(await screen.findByText('رقم غير صالح')).toBeTruthy();
  });

  it('empty clears the number', async () => {
    api.get.mockResolvedValue({ otp_validity_minutes: 60, admin_whatsapp: '07701112233' });
    api.update.mockResolvedValue({ otp_validity_minutes: 60, admin_whatsapp: null });
    show();
    fireEvent.change(await field(), { target: { value: '' } });
    fireEvent.click(screen.getByRole('button', { name: 'حفظ الرقم' }));
    await waitFor(() => expect(api.update).toHaveBeenCalledWith({ admin_whatsapp: null }));
  });

  it('the OTP minutes are saved on their own', async () => {
    api.update.mockResolvedValue({ otp_validity_minutes: 30, admin_whatsapp: null });
    show();
    fireEvent.change(await screen.findByLabelText('مدة صلاحية رمز التحقق'), {
      target: { value: '30' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'حفظ' }));
    await waitFor(() => expect(api.update).toHaveBeenCalledWith({ otp_validity_minutes: 30 }));
  });
});
