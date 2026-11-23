/** Sections of the new-subscriber form in the order of docs/system.md §5 (FR-003).
 * The ids double as scroll targets for the «النواقص» links (US5). */
export const SECTIONS = [
  { id: 'section-card', title: 'البطاقة الوطنية' },
  { id: 'section-card-data', title: 'بيانات البطاقة' },
  { id: 'section-location', title: 'موقع البيت' },
  { id: 'section-subscription', title: 'الاشتراك' },
  { id: 'section-phone', title: 'هاتف المشترك' },
] as const;

export type SectionId = (typeof SECTIONS)[number]['id'];
