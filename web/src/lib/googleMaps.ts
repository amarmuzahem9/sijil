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

interface MapMouseEvent {
  latLng: { lat(): number; lng(): number } | null;
}

export interface GMap {
  panTo(pos: LatLngLiteral): void;
  setZoom(zoom: number): void;
  addListener(event: 'click', handler: (e: MapMouseEvent) => void): MapsEventListener;
}

export interface GMarker {
  map: GMap | null;
  position: LatLngLiteral | { lat(): number; lng(): number } | null;
  gmpDraggable: boolean;
  addListener(event: 'dragend', handler: () => void): MapsEventListener;
}

export interface MapsApi {
  Map: new (el: HTMLElement, options: Record<string, unknown>) => GMap;
  AdvancedMarkerElement: new (options: Record<string, unknown>) => GMarker;
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
      libraries: 'maps,marker',
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
    return {
      Map: maps.Map as MapsApi['Map'],
      AdvancedMarkerElement: marker.AdvancedMarkerElement as MapsApi['AdvancedMarkerElement'],
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

export function readPosition(marker: GMarker): LatLngLiteral | null {
  const pos = marker.position;
  if (!pos) return null;
  return typeof pos.lat === 'function'
    ? { lat: (pos as { lat(): number }).lat(), lng: (pos as { lng(): number }).lng() }
    : (pos as LatLngLiteral);
}
