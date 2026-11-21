/** Display helpers: times are stored/sent in UTC and shown in Baghdad time (Principle X). */
const dateTimeFormat = new Intl.DateTimeFormat('ar-IQ', {
  timeZone: 'Asia/Baghdad',
  dateStyle: 'medium',
  timeStyle: 'short',
});

export function formatBaghdad(isoUtc: string): string {
  return dateTimeFormat.format(new Date(isoUtc));
}
