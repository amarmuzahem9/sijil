/**
 * Google Maps JavaScript API loader (specs/005 research.md R10). No npm package: the official
 * script is injected once with the key from /api/client-config, then the `maps` and `marker`
 * libraries are imported. Anything that goes wrong resolves to `null` (map unavailable), and the
 * form keeps working with «استخدم موقعي الحالي» (FR-009).
 *
 * Only the few API members the map picker uses are typed here.
 */
import type { MapsConfig } from './clientConfig';

export interface LatLngLiteral {
  lat: number;
  lng: number;
}

interface MapsEventListener {
  remove(): void;
}

/** Event shapes vary by API version, so the position is read through `toLatLngLiteral`. */
export interface MapMouseEvent {
  latLng?: unknown;
}

export interface GMap {
  panTo(pos: LatLngLiteral): void;
  setZoom(zoom: number): void;
  addListener(event: 'click', handler: (e: MapMouseEvent | undefined) => void): MapsEventListener;
}

export interface GMarker {
  map: GMap | null;
  position: unknown;
  gmpDraggable: boolean;
  addListener(event: 'dragend', handler: () => void): MapsEventListener;
}

export interface MapsApi {
  Map: new (el: HTMLElement, options: Record<string, unknown>) => GMap;
  AdvancedMarkerElement: new (options: Record<string, unknown>) => GMarker;
  /** Places API (New) for the search bar; null when the library failed to load. */
  places: PlacesLibrary | null;
}

/** The members of the `places` library the search bar uses (Places API New). */
export interface PlacePrediction {
  placeId: string;
  text?: { text: string } | null;
  mainText?: { text: string } | null;
  secondaryText?: { text: string } | null;
  toPlace(): { fetchFields(req: { fields: string[] }): Promise<unknown>; location?: unknown };
}

export interface PlacesLibrary {
  AutocompleteSessionToken: new () => unknown;
  AutocompleteSuggestion: {
    fetchAutocompleteSuggestions(request: Record<string, unknown>): Promise<{
      suggestions: { placePrediction?: PlacePrediction | null }[];
    }>;
  };
}

interface GoogleGlobal {
  maps: { importLibrary(name: string): Promise<Record<string, unknown>> };
}

declare global {
  interface Window {
    google?: GoogleGlobal;
    __sijilMapsReady?: () => void;
  }
}

export const MAPS_TIMEOUT_MS = 10_000;

let loading: Promise<MapsApi | null> | null = null;

function injectScript(config: MapsConfig): Promise<void> {
  return new Promise((resolve, reject) => {
    window.__sijilMapsReady = () => resolve();
    const params = new URLSearchParams({
      key: config.api_key,
      v: 'weekly',
      loading: 'async',
      libraries: 'maps,marker,places',
      language: 'ar',
      region: 'IQ',
      callback: '__sijilMapsReady',
    });
    const script = document.createElement('script');
    script.src = `https://maps.googleapis.com/maps/api/js?${params.toString()}`;
    script.async = true;
    script.onerror = () => reject(new Error('maps script failed'));
    document.head.appendChild(script);
  });
}

async function load(config: MapsConfig): Promise<MapsApi | null> {
  const timeout = new Promise<null>((resolve) => setTimeout(() => resolve(null), MAPS_TIMEOUT_MS));
  const ready = (async () => {
    if (!window.google?.maps) await injectScript(config);
    const google = window.google;
    if (!google?.maps) return null;
    const maps = await google.maps.importLibrary('maps');
    const marker = await google.maps.importLibrary('marker');
    // The map works without search: a failure here only hides the search bar.
    const places = await google.maps.importLibrary('places').catch(() => null);
    return {
      Map: maps.Map as MapsApi['Map'],
      AdvancedMarkerElement: marker.AdvancedMarkerElement as MapsApi['AdvancedMarkerElement'],
      places:
        places?.AutocompleteSuggestion && places.AutocompleteSessionToken
          ? (places as unknown as PlacesLibrary)
          : null,
    };
  })().catch(() => null);
  return Promise.race([ready, timeout]);
}

/** Load the API once per page. Resolves to null when the map is unavailable. */
export function loadGoogleMaps(config: MapsConfig | null): Promise<MapsApi | null> {
  if (!config) return Promise.resolve(null);
  loading ??= load(config).then((api) => {
    if (!api) loading = null; // allow a later retry (e.g. the network came back)
    return api;
  });
  return loading;
}

/**
 * Turn any position the Maps API hands us into a plain `{lat, lng}`, or null when it has no usable
 * coordinates. Google may give a `LatLng` (methods `lat()`/`lng()`), a literal, or a
 * `LatLngAltitude` whose `lat`/`lng` are prototype getters, so a spread (`{...pos}`) would drop
 * them. Each value is read directly and must be a finite number.
 */
export function toLatLngLiteral(value: unknown): LatLngLiteral | null {
  if (value === null || typeof value !== 'object') return null;
  const read = (key: 'lat' | 'lng'): number | null => {
    let v: unknown;
    try {
      const member = (value as Record<string, unknown>)[key];
      v = typeof member === 'function' ? (member as () => unknown).call(value) : member;
    } catch {
      return null;
    }
    return typeof v === 'number' && Number.isFinite(v) ? v : null;
  };
  const lat = read('lat');
  const lng = read('lng');
  if (lat === null || lng === null) return null;
  return { lat, lng };
}

export function readPosition(marker: GMarker): LatLngLiteral | null {
  return toLatLngLiteral(marker.position);
}
