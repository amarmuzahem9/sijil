/**
 * Place search for «موقع البيت» (docs/system.md §5.2 v1.6) on Places API (New): suggestions limited
 * to Iraq, in Arabic. One session token covers the typing and the final details request, as Google
 * bills them as one session; a new token starts after each pick.
 */
import {
  toLatLngLiteral,
  type LatLngLiteral,
  type PlacePrediction,
  type PlacesLibrary,
} from './googleMaps';

export const PLACES_MIN_CHARS = 2;
export const PLACES_DEBOUNCE_MS = 300;

export interface PlaceSuggestion {
  placeId: string;
  main: string;
  secondary: string;
  prediction: PlacePrediction;
}

/** The request sent to Google: Iraq only, Arabic results. */
export function suggestionRequest(input: string, sessionToken: unknown): Record<string, unknown> {
  return {
    input,
    sessionToken,
    includedRegionCodes: ['iq'],
    region: 'iq',
    language: 'ar',
  };
}

export async function searchPlaces(
  lib: PlacesLibrary,
  input: string,
  sessionToken: unknown,
): Promise<PlaceSuggestion[]> {
  const { suggestions } = await lib.AutocompleteSuggestion.fetchAutocompleteSuggestions(
    suggestionRequest(input, sessionToken),
  );
  const out: PlaceSuggestion[] = [];
  for (const s of suggestions ?? []) {
    const p = s.placePrediction;
    if (!p) continue;
    out.push({
      placeId: p.placeId,
      main: p.mainText?.text ?? p.text?.text ?? '',
      secondary: p.secondaryText?.text ?? '',
      prediction: p,
    });
  }
  return out;
}

/** The chosen place's coordinates, or null when Google gives none. */
export async function placeLocation(prediction: PlacePrediction): Promise<LatLngLiteral | null> {
  const place = prediction.toPlace();
  await place.fetchFields({ fields: ['location'] });
  return toLatLngLiteral(place.location);
}
