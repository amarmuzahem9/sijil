/**
 * The «حذف مشترك» switch (specs/011 US3: FR-001): shown with the other permissions for an added
 * admin, off unless given, and toggled like the others. The main admin has no switches: it holds
 * every permission on the server (has_any_permission).
 */
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { PermissionSwitches } from '../components/PermissionSwitches';

afterEach(cleanup);

const label = 'حذف مشترك (طلب بالانتظار أو مرفوض)';

describe('PermissionSwitches', () => {
  it('shows «حذف مشترك» last, off by default', () => {
    render(<PermissionSwitches value={['review']} onChange={vi.fn()} />);
    const switches = screen.getAllByRole('switch');
    expect(switches).toHaveLength(7);
    const del = screen.getByRole('switch', { name: label }) as HTMLInputElement;
    expect(switches[6]).toBe(del);
    expect(del.checked).toBe(false);
  });

  it('turns «حذف مشترك» on and off', () => {
    const onChange = vi.fn();
    const { rerender } = render(<PermissionSwitches value={['review']} onChange={onChange} />);
    fireEvent.click(screen.getByRole('switch', { name: label }));
    expect(onChange).toHaveBeenLastCalledWith(['review', 'delete']);

    rerender(<PermissionSwitches value={['review', 'delete']} onChange={onChange} />);
    expect((screen.getByRole('switch', { name: label }) as HTMLInputElement).checked).toBe(true);
    fireEvent.click(screen.getByRole('switch', { name: label }));
    expect(onChange).toHaveBeenLastCalledWith(['review']);
  });
});
