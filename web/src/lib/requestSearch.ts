/**
 * The search box in «الطلبات» (specs/012 research R8). The server decides whether the text is a
 * request number, a phone or part of a name; the page only skips texts under 2 characters.
 */
export const SEARCH_MIN_LENGTH = 2;

export function isSearchable(text: string): boolean {
  return text.trim().length >= SEARCH_MIN_LENGTH;
}
