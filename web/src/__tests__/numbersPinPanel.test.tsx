/**
 * «تثبيت الأرقام» (specs/010 US3: FR-013, FR-014; research R4): each edited number with its reading,
 * MRZ, marketer value and current value; pinning from a source or a typed value; the pin history.
 * Synthetic values only.
 */
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { ApiError } from '../lib/api';
import { formatBaghdad } from '../lib/time';

const pin = vi.fn();
vi.mock('../lib/adminRequests', async (original) => ({
  ...(await original<typeof import('../lib/adminRequests')>()),
  pin: (...args: unknown[]) => pin(...args),
}));

import { NumbersPinPanel } from '../pages/admin/pending/NumbersPinPanel';
import { requestFile } from './fixtures/requestFile';

const onPinned = vi.fn();

beforeEach(() => {
  pin.mockReset();
  onPinned.mockReset();
});
afterEach(cleanup);

/** Both numbers edited; the card did not read the family number. */
function bothEdited() {
  const file = requestFile();
  return requestFile({
    numbers: {
      national_id: {
        reading: '199000000002',
        mrz: '199000000003',
        marketer: '199000000001',
        current: '199000000001',
        edited: true,
        pins: [
          {
            value: '199000000001',
            source: 'marketer',
            by: 'أدمن تجريبي',
            at: '2026-11-23T11:00:00Z',
          },
        ],
      },
      family_number: { ...file.numbers!.family_number, reading: null },
    },
  });
}

function show(file = bothEdited()) {
  render(<NumbersPinPanel file={file} onPinned={onPinned} />);
}

const group = (name: string) => screen.getByRole('group', { name });
const value = (scope: HTMLElement, label: string) =>
  (within(scope).getByLabelText(label) as HTMLInputElement).value;

describe('NumbersPinPanel', () => {
  it('shows every source of each edited number side by side', () => {
    show();
    const nid = group('الرقم الوطني');
    expect(value(nid, 'قراءة البطاقة')).toBe('199000000002');
    expect(value(nid, 'MRZ')).toBe('199000000003');
    expect(value(nid, 'قيمة المسوّق')).toBe('199000000001');
    expect(value(nid, 'القيمة الحالية')).toBe('199000000001');
    // The reading and the MRZ differ from the current value.
    expect(within(nid).getAllByText('تختلف عن القيمة الحالية')).toHaveLength(2);

    const family = group('الرقم العائلي');
    expect(within(family).queryByLabelText('MRZ')).toBeNull();
    expect(value(family, 'قيمة المسوّق')).toBe('1234A5678901234567');
  });

  it('says «لم تقرأه البطاقة» and offers no pin when there is no reading', () => {
    show();
    const family = group('الرقم العائلي');
    expect(value(family, 'قراءة البطاقة')).toBe('—');
    expect(within(family).getByText('لم تقرأه البطاقة')).toBeTruthy();
    const button = within(family).getByRole('button', {
      name: 'تثبيت القيمة: قراءة البطاقة',
    }) as HTMLButtonElement;
    expect(button.disabled).toBe(true);
  });

  it('pins a source without sending its value', async () => {
    const updated = requestFile();
    pin.mockResolvedValue(updated);
    show();

    fireEvent.click(
      within(group('الرقم الوطني')).getByRole('button', { name: 'تثبيت القيمة: MRZ' }),
    );

    await vi.waitFor(() =>
      expect(pin).toHaveBeenCalledWith(11, { field: 'national_id', source: 'mrz' }),
    );
    await vi.waitFor(() => expect(onPinned).toHaveBeenCalledWith(updated));
  });

  it('pins a typed value', async () => {
    pin.mockResolvedValue(requestFile());
    show();
    const family = group('الرقم العائلي');

    const typed = within(family).getByRole('textbox', { name: 'قيمة أخرى' });
    const button = within(family).getByRole('button', {
      name: 'تثبيت القيمة: قيمة أخرى',
    }) as HTMLButtonElement;
    expect(button.disabled).toBe(true);
    fireEvent.change(typed, { target: { value: ' 1234A5678901234599 ' } });
    fireEvent.click(button);

    await vi.waitFor(() =>
      expect(pin).toHaveBeenCalledWith(11, {
        field: 'family_number',
        source: 'typed',
        value: '1234A5678901234599',
      }),
    );
  });

  it('lists the pins with who and when', () => {
    show();
    const history = within(group('الرقم الوطني')).getByRole('list', { name: 'سجل التثبيت' });
    const item = within(history).getByRole('listitem');
    expect(item.textContent).toContain('199000000001');
    expect(item.textContent).toContain('قيمة المسوّق');
    expect(item.textContent).toContain('أدمن تجريبي');
    expect(item.textContent).toContain(formatBaghdad('2026-11-23T11:00:00Z'));
  });

  it('shows the Arabic message of a refused pin', async () => {
    pin.mockRejectedValue(
      new ApiError('invalid_national_id', 'الرقم الوطني يجب أن يكون 12 رقماً', 422),
    );
    show();
    const nid = group('الرقم الوطني');
    fireEvent.change(within(nid).getByRole('textbox', { name: 'قيمة أخرى' }), {
      target: { value: '123' },
    });
    fireEvent.click(within(nid).getByRole('button', { name: 'تثبيت القيمة: قيمة أخرى' }));

    expect(await screen.findByText('الرقم الوطني يجب أن يكون 12 رقماً')).toBeTruthy();
    expect(onPinned).not.toHaveBeenCalled();
  });

  it('shows only the edited numbers, and no buttons on a decided request', () => {
    show(requestFile({ status: 'approved' }));
    expect(screen.queryByRole('group', { name: 'الرقم الوطني' })).toBeNull();
    expect(group('الرقم العائلي')).toBeTruthy();
    expect(screen.queryByRole('button')).toBeNull();
  });
});
