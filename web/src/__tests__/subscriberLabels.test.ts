/**
 * Labels of «المشتركون» (docs/system.md v1.24 §10 item 4; specs/018 T007): sources, link reasons
 * and request history lines, in Arabic.
 */
import { describe, expect, it } from 'vitest';

import { HISTORY_KIND_LABELS, LINK_REASON_LABELS, SUBSCRIBER_SOURCE_LABELS } from '../lib/labels';

describe('subscriber labels (specs/018)', () => {
  it('names the three sources', () => {
    expect(SUBSCRIBER_SOURCE_LABELS).toEqual({
      sijil: 'طلب سِجلّ',
      legacy: 'مشترك قديم',
      sas: 'مشترك SAS',
    });
  });

  it('names the link reasons', () => {
    expect(LINK_REASON_LABELS).toEqual({
      same_person: 'نفس الشخص',
      same_phone: 'نفس الهاتف',
      same_family: 'نفس العائلة',
    });
  });

  it('names the history lines', () => {
    expect(HISTORY_KIND_LABELS).toEqual({
      submitted: 'أُرسل',
      approved: 'قُبل',
      rejected: 'رُفض',
      pinned: 'تثبيت رقم',
      linked: 'تم الربط',
      unlinked: 'تراجع عن الربط',
      deleted: 'حُذف',
    });
  });
});
