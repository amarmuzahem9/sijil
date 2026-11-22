import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

const auth = vi.hoisted(() => ({ login: vi.fn() }));
vi.mock('../auth/AuthProvider', () => ({ useAuth: () => ({ login: auth.login }) }));

import { ApiError } from '../lib/api';
import { SESSION_ENDED_TITLE, SignInDialog } from '../pages/marketer/subscriber/SignInDialog';

afterEach(() => {
  cleanup();
  auth.login.mockReset();
});

function renderDialog() {
  const onSameUser = vi.fn();
  const onOtherUser = vi.fn();
  render(
    <SignInDialog open expectedUserId={7} onSameUser={onSameUser} onOtherUser={onOtherUser} />,
  );
  const fill = (phone: string, password: string) => {
    fireEvent.change(screen.getByLabelText('رقم الهاتف'), { target: { value: phone } });
    fireEvent.change(screen.getByLabelText('كلمة السر'), { target: { value: password } });
    fireEvent.click(screen.getByRole('button', { name: 'دخول' }));
  };
  return { onSameUser, onOtherUser, fill };
}

describe('SignInDialog (analysis U2)', () => {
  it('shows the session-ended title over the form', () => {
    renderDialog();
    expect(screen.getByText(SESSION_ENDED_TITLE)).toBeTruthy();
  });

  it('resumes when the same account signs in', async () => {
    auth.login.mockResolvedValue({ id: 7 });
    const { onSameUser, onOtherUser, fill } = renderDialog();
    fill('07710000001', 'Test-Passw0rd');
    await waitFor(() => expect(onSameUser).toHaveBeenCalled());
    expect(onOtherUser).not.toHaveBeenCalled();
    expect(auth.login).toHaveBeenCalledWith('07710000001', 'Test-Passw0rd');
  });

  it('discards the form when another account signs in', async () => {
    auth.login.mockResolvedValue({ id: 8 });
    const { onSameUser, onOtherUser, fill } = renderDialog();
    fill('07710000002', 'Test-Passw0rd');
    await waitFor(() => expect(onOtherUser).toHaveBeenCalled());
    expect(onSameUser).not.toHaveBeenCalled();
  });

  it('shows the server message on a wrong password and stays open', async () => {
    auth.login.mockRejectedValue(
      new ApiError('invalid_credentials', 'رقم الهاتف أو كلمة السر غير صحيحة', 401),
    );
    const { onSameUser, onOtherUser, fill } = renderDialog();
    fill('07710000001', 'wrong');
    expect(await screen.findByText('رقم الهاتف أو كلمة السر غير صحيحة')).toBeTruthy();
    expect(onSameUser).not.toHaveBeenCalled();
    expect(onOtherUser).not.toHaveBeenCalled();
  });

  it('refuses an invalid phone before calling the server', () => {
    const { fill } = renderDialog();
    fill('123', 'x');
    expect(screen.getByText('رقم غير صالح')).toBeTruthy();
    expect(auth.login).not.toHaveBeenCalled();
  });
});
