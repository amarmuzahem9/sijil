/**
 * The read-only field of the view pages (owner's request, specs/010): the same frame, corners,
 * height and small label as the form's inputs, but read-only; notes go under the box; two
 * columns on a computer and one on a phone.
 */
import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';

import { ReadOnlyField, ReadOnlyFields } from '../components/ReadOnlyField';

afterEach(cleanup);

describe('ReadOnlyField', () => {
  it('shows the value in a read-only box under its label, like the form inputs', () => {
    render(<ReadOnlyField label="الرقم الوطني" value="199000000001" ltr />);
    const box = screen.getByLabelText('الرقم الوطني') as HTMLInputElement | HTMLTextAreaElement;
    expect(box.value).toBe('199000000001');
    expect(box.readOnly).toBe(true);
    expect(box.getAttribute('dir')).toBe('ltr');
    // The same outlined frame as the form's TextField.
    expect(box.closest('.MuiOutlinedInput-root')).not.toBeNull();
    expect(box.closest('.MuiInputBase-readOnly')).not.toBeNull();
  });

  it('puts the note under the box and links it to the field', () => {
    render(<ReadOnlyField label="اسم أب الجد" value="مثال" note="لم تقرأه البطاقة" />);
    const box = screen.getByLabelText('اسم أب الجد');
    const note = screen.getByText('لم تقرأه البطاقة');
    expect(note.classList.contains('MuiFormHelperText-root')).toBe(true);
    expect(box.getAttribute('aria-describedby')).toBe(note.id);
  });

  it('shows a dash for an empty value', () => {
    render(<ReadOnlyField label="لقب الأم" value={null} />);
    expect((screen.getByLabelText('لقب الأم') as HTMLInputElement).value).toBe('—');
  });

  it('cannot be typed into', () => {
    render(<ReadOnlyField label="العنوان" value="حي تجريبي" />);
    const box = screen.getByLabelText('العنوان') as HTMLInputElement;
    expect(box.readOnly).toBe(true);
  });
});

describe('ReadOnlyFields', () => {
  it('lays the fields in a grid of one column on a phone and two on a computer', () => {
    render(
      <ReadOnlyFields>
        <ReadOnlyField label="أ" value="1" />
        <ReadOnlyField label="ب" value="2" />
      </ReadOnlyFields>,
    );
    const grid = screen.getByTestId('readonly-fields');
    expect(grid.dataset.columns).toBe('1 2');
    expect(grid.contains(screen.getByLabelText('أ'))).toBe(true);
  });
});
