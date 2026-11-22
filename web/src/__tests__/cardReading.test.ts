/**
 * Card reading on the form (specs/006 research R5, R8; tasks T020, T030).
 * Synthetic names and numbers only.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import {
  anyFailed,
  fieldsToMerge,
  MARK_EDITED,
  MARK_FROM_CARD,
  reshootText,
  shouldPoll,
  waitsForOtherSide,
} from '../lib/cardReading';
import { DraftFormController } from '../lib/draftFormController';
import { CARD_FIELDS, type CardReading, type Draft } from '../lib/drafts';
import { fieldMarkText } from '../pages/marketer/subscriber/FieldSourceMark';

function draft(overrides: Partial<Draft> = {}): Draft {
  return {
    id: '00000000-0000-4000-8000-000000000001',
    status: 'draft',
    version: 3,
    created_at: '2026-11-23T10:00:00Z',
    updated_at: '2026-11-23T10:00:00Z',
    first_name: null,
    father_name: null,
    grandfather_name: null,
    great_grandfather_name: null,
    surname: null,
    mother_first_name: null,
    mother_second_name: null,
    mother_third_name: null,
    mother_surname: null,
    full_name: null,
    national_id: null,
    family_number: null,
    location: null,
    address: null,
    landmark: null,
    area_id: null,
    tower_id: null,
    plan_id: null,
    area_name: null,
    tower_code: null,
    plan_name: null,
    trial_price: null,
    second_price: null,
    phone_input: null,
    phone_normalized: null,
    images: { front: null, back: null },
    no_surname: false,
    card_fields: {},
    national_id_check: null,
    card_reading: { front: null, back: null },
    missing: [],
    notices: [],
    ...overrides,
  };
}

const READ: Partial<Draft> = {
  version: 5,
  first_name: 'مشترك',
  father_name: 'تجريبي',
  grandfather_name: 'اختبار',
  surname: 'الوهمي',
  mother_first_name: 'أم',
  mother_second_name: 'تجريبية',
  national_id: '199912345678',
  family_number: '1064L00M1234567890',
  card_fields: {
    first_name: { source: 'card', original: 'مشترك', confidence: 0.97, from: 'front' },
  },
  card_reading: {
    front: { state: 'done', reason: null },
    back: { state: 'done', reason: null },
  },
};

describe('reading status helpers', () => {
  const side = (state: 'pending' | 'running' | 'done' | 'reshoot' | 'failed') => ({
    state,
    reason: null,
  });

  it('polls only while a side waits or runs', () => {
    expect(shouldPoll({ front: side('pending'), back: side('done') })).toBe(true);
    expect(shouldPoll({ front: side('running'), back: null })).toBe(true);
    expect(shouldPoll({ front: side('done'), back: side('reshoot') })).toBe(false);
    expect(shouldPoll(null)).toBe(false);
  });

  it('knows when the reading waits for the other side', () => {
    expect(waitsForOtherSide({ front: side('pending'), back: null })).toBe(true);
    expect(waitsForOtherSide({ front: side('pending'), back: side('pending') })).toBe(false);
    expect(waitsForOtherSide({ front: null, back: null })).toBe(false);
  });

  it('reports a failed side', () => {
    const reading: CardReading = { front: side('done'), back: side('failed') };
    expect(anyFailed(reading)).toBe(true);
    expect(anyFailed({ front: side('done'), back: side('done') })).toBe(false);
  });

  it('names the side in the re-shoot messages', () => {
    expect(reshootText('front', 'no_card')).toBe('لم نتمكن من قراءة وجه البطاقة');
    expect(reshootText('back', 'no_card')).toBe('لم نتمكن من قراءة ظهر البطاقة');
    expect(reshootText('front', 'wrong_side')).toBe('هذه صورة الظهر، ضعها في خانتها');
    expect(reshootText('back', 'multiple')).toBe('يظهر أكثر من مستمسك في الصورة');
    expect(reshootText('front', 'not_unified')).toBe('البطاقة الوطنية الموحدة فقط');
  });

  it('skips fields with a local change', () => {
    expect(fieldsToMerge(CARD_FIELDS, (f) => f === 'surname')).not.toContain('surname');
    expect(fieldsToMerge(CARD_FIELDS, () => false)).toHaveLength(8);
  });
});

describe('field marks', () => {
  const card = {
    source: 'card' as const,
    original: 'اختبار',
    confidence: 0.9,
    from: 'front' as const,
  };

  it('shows «من البطاقة» for an unchanged reading', () => {
    expect(fieldMarkText(card, false)).toBe(MARK_FROM_CARD);
  });

  it('shows «عُدِّل يدوياً» once changed here or on the server', () => {
    expect(fieldMarkText(card, true)).toBe(MARK_EDITED);
    expect(fieldMarkText({ ...card, source: 'edited' }, false)).toBe(MARK_EDITED);
  });

  it('shows nothing for a field that was never read', () => {
    expect(fieldMarkText(undefined, false)).toBeNull();
    expect(
      fieldMarkText({ source: 'edited', original: null, confidence: null, from: null }, false),
    ).toBeNull();
  });
});

describe('merging a finished reading into the form', () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it('fills the card fields and takes the new version', () => {
    const ctl = new DraftFormController(draft());
    ctl.mergeReading(draft(READ));
    expect(ctl.values.first_name).toBe('مشترك');
    expect(ctl.values.national_id).toBe('199912345678');
    expect(ctl.values.family_number).toBe('1064L00M1234567890');
    expect(ctl.queue.currentVersion).toBe(5);
  });

  it('keeps a field typed during the reading', () => {
    const ctl = new DraftFormController(draft());
    ctl.setText('grandfather_name', 'مكتوب'); // debounce still waiting
    ctl.mergeReading(draft(READ));
    expect(ctl.values.grandfather_name).toBe('مكتوب');
    expect(ctl.values.father_name).toBe('تجريبي');
  });

  it('keeps «لا يوجد لقب» chosen here while it is being saved', () => {
    const ctl = new DraftFormController(draft());
    ctl.saveNow({ no_surname: true, surname: '' });
    ctl.mergeReading(draft({ ...READ, no_surname: false }));
    expect(ctl.values.no_surname).toBe(true);
    expect(ctl.values.surname).toBe('');
  });

  it('typing a surname clears «لا يوجد لقب»', () => {
    const ctl = new DraftFormController(draft({ no_surname: true }));
    expect(ctl.values.no_surname).toBe(true);
    ctl.setText('surname', 'الوهمي');
    expect(ctl.values.no_surname).toBe(false);
  });
});
