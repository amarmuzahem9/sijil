/**
 * «الاتصال بالإدارة» (specs/009 US2; FR-005a, FR-005b; research R8): a real link to the
 * administration's WhatsApp with a ready text naming only the marketer. No subscriber data, not
 * even the phone that was typed. Disabled while the number is not set in the settings.
 */
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { adminWhatsAppLink, CONTACT_ADMIN_TEXT, contactAdminMessage } from '../lib/contactAdmin';
import { ContactAdminButton } from '../pages/marketer/subscriber/ContactAdminButton';

afterEach(cleanup);

describe('adminWhatsAppLink', () => {
  it('uses the 964 form and carries only the marketer name', () => {
    const link = adminWhatsAppLink('07701112233', 'علي');
    const url = new URL(link);
    expect(`${url.origin}${url.pathname}`).toBe('https://wa.me/9647701112233');
    const text = url.searchParams.get('text') ?? '';
    expect(text).toBe(contactAdminMessage('علي'));
    expect(text).toContain('علي');
    expect(text).not.toMatch(/07\d{9}|9647\d{9}/);
  });
});

describe('ContactAdminButton', () => {
  it('is a link opening a new tab and reports the click', () => {
    const onOpen = vi.fn();
    render(<ContactAdminButton number="07701112233" marketerName="علي" onOpen={onOpen} />);
    const link = screen.getByRole('link', { name: CONTACT_ADMIN_TEXT.action });
    expect(link.getAttribute('target')).toBe('_blank');
    expect(link.getAttribute('rel')).toContain('noopener');
    expect(link.getAttribute('href')).toBe(adminWhatsAppLink('07701112233', 'علي'));
    fireEvent.click(link);
    expect(onOpen).toHaveBeenCalledOnce();
  });

  it('never puts the subscriber phone in the link', () => {
    render(<ContactAdminButton number="07701112233" marketerName="علي" onOpen={vi.fn()} />);
    const href = screen.getByRole('link').getAttribute('href') ?? '';
    expect(decodeURIComponent(href)).not.toContain('07801234567');
  });

  it('is disabled with a message when the number is not set', () => {
    render(<ContactAdminButton number={null} marketerName="علي" onOpen={vi.fn()} />);
    expect(screen.queryByRole('link')).toBeNull();
    const button = screen.getByRole('button', { name: CONTACT_ADMIN_TEXT.action });
    expect((button as HTMLButtonElement).disabled).toBe(true);
    expect(screen.getByText('رقم الإدارة غير مضبوط في الإعدادات')).toBeTruthy();
  });
});
