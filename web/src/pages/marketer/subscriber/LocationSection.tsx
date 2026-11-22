/**
 * «موقع البيت» (docs/system.md §5.2 v1.6, specs/005 US6): the phone's GPS, a typed coordinate or a
 * pasted Google Maps link, a place search (Places, Iraq only), or a satellite map with a draggable
 * pin; then the address and the nearest landmark. The pin is saved immediately and must be inside
 * Iraq. With no map key or no network, GPS and the coordinate box still work (FR-009).
 */
import MapOutlined from '@mui/icons-material/MapOutlined';
import MyLocationOutlined from '@mui/icons-material/MyLocationOutlined';
import Alert from '@mui/material/Alert';
import Button from '@mui/material/Button';
import CircularProgress from '@mui/material/CircularProgress';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';
import { useEffect, useState } from 'react';

import { useClientConfig } from '../../../lib/clientConfig';
import { COORDINATE_ERRORS, inIraq } from '../../../lib/coordinates';
import type { DraftLocation, LocationSource } from '../../../lib/drafts';
import {
  loadGoogleMaps,
  toLatLngLiteral,
  type LatLngLiteral,
  type MapsApi,
} from '../../../lib/googleMaps';
import type { DraftAutosave } from '../../../lib/useDraftAutosave';
import { CoordinateInput } from './CoordinateInput';
import { DraftTextField } from './DraftTextField';
import { MapPicker } from './MapPicker';
import { PlaceSearch } from './PlaceSearch';

export const MAP_UNAVAILABLE = 'الخريطة غير متوفرة حالياً';
export const GPS_TIMEOUT_MS = 15_000;
export const GPS_OUTSIDE_IRAQ = 'موقعك الحالي خارج العراق. حدّد البيت بالإحداثية أو على الخريطة.';

const GEO_ERRORS: Record<number, string> = {
  1: 'لم يُسمح بالوصول إلى الموقع. فعّل إذن الموقع للمتصفح، أو حدّد البيت على الخريطة.',
  2: 'تعذّر تحديد الموقع الآن. حاول مرة أخرى في مكان مكشوف، أو حدّد البيت على الخريطة.',
  3: 'انتهت مهلة تحديد الموقع. حاول مرة أخرى، أو حدّد البيت على الخريطة.',
};

type MapState = { kind: 'loading' } | { kind: 'ready'; api: MapsApi } | { kind: 'unavailable' };

function useMapsApi(): { state: MapState; mapId: string; center: LatLngLiteral | null } {
  const config = useClientConfig();
  const maps = config.data?.maps ?? null;
  // Result of loading the API for a given key; `api: null` means it failed to load.
  const [loaded, setLoaded] = useState<{ key: string; api: MapsApi | null } | null>(null);

  useEffect(() => {
    if (!maps) return;
    let cancelled = false;
    void loadGoogleMaps(maps).then((api) => {
      if (!cancelled) setLoaded({ key: maps.api_key, api });
    });
    return () => {
      cancelled = true;
    };
  }, [maps]);

  let state: MapState;
  if (config.isPending) state = { kind: 'loading' };
  else if (!maps || config.isError) state = { kind: 'unavailable' };
  else if (!loaded || loaded.key !== maps.api_key) state = { kind: 'loading' };
  else state = loaded.api ? { kind: 'ready', api: loaded.api } : { kind: 'unavailable' };

  return { state, mapId: maps?.map_id ?? '', center: maps?.default_center ?? null };
}

const fmt = (n: number) => (Number.isFinite(n) ? n.toFixed(6) : '—');

export function LocationSection({
  autosave,
}: {
  autosave: Pick<DraftAutosave, 'values' | 'setText' | 'commitField' | 'saveNow'>;
}) {
  const { values, setText, commitField, saveNow } = autosave;
  const { state: mapState, mapId, center: defaultCenter } = useMapsApi();
  const [mapOpen, setMapOpen] = useState(false);
  const [locating, setLocating] = useState(false);
  const [geoError, setGeoError] = useState<string | null>(null);
  const [devicePos, setDevicePos] = useState<LatLngLiteral | null>(null);

  // A location without finite numbers counts as no pin (never render or send it).
  const pin = toLatLngLiteral(values.location);

  // Every source goes through here: finite numbers, inside Iraq (the server checks the same box).
  function setPin(location: DraftLocation): boolean {
    const pos = toLatLngLiteral(location);
    if (!pos) return false;
    if (!inIraq(pos)) {
      setGeoError(location.source === 'gps' ? GPS_OUTSIDE_IRAQ : COORDINATE_ERRORS.outside_iraq);
      return false;
    }
    setGeoError(null);
    saveNow({ location: { ...location, lat: pos.lat, lng: pos.lng } });
    return true;
  }

  /** A typed coordinate or a search result: save it, then show it on the map when there is one. */
  function goTo(pos: LatLngLiteral, source: LocationSource) {
    if (setPin({ ...pos, source, accuracy_m: null }) && mapState.kind === 'ready') setMapOpen(true);
  }

  function useMyLocation() {
    setGeoError(null);
    if (!('geolocation' in navigator)) {
      setGeoError(GEO_ERRORS[2]);
      return;
    }
    setLocating(true);
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setLocating(false);
        const here = { lat: pos.coords.latitude, lng: pos.coords.longitude };
        setDevicePos(here);
        const saved = setPin({
          ...here,
          source: 'gps',
          accuracy_m: Number.isFinite(pos.coords.accuracy) ? Math.round(pos.coords.accuracy) : null,
        });
        if (saved && mapState.kind === 'ready') setMapOpen(true);
      },
      (err) => {
        setLocating(false);
        setGeoError(GEO_ERRORS[err.code] ?? GEO_ERRORS[2]);
      },
      { enableHighAccuracy: true, timeout: GPS_TIMEOUT_MS, maximumAge: 0 },
    );
  }

  const mapCenter = pin ?? devicePos ?? defaultCenter ?? { lat: 33.3152, lng: 44.3661 };

  return (
    <Stack spacing={1.5}>
      <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1}>
        <Button
          variant="outlined"
          startIcon={locating ? <CircularProgress size={18} /> : <MyLocationOutlined />}
          onClick={useMyLocation}
          disabled={locating}
          sx={{ flex: 1 }}
        >
          استخدم موقعي الحالي
        </Button>
        <Button
          variant={mapOpen ? 'contained' : 'outlined'}
          startIcon={<MapOutlined />}
          onClick={() => setMapOpen((open) => !open)}
          disabled={mapState.kind !== 'ready'}
          sx={{ flex: 1 }}
        >
          حدّد البيت على الخريطة
        </Button>
      </Stack>

      <CoordinateInput onGo={(pos) => goTo(pos, 'coords')} />
      {mapState.kind === 'ready' && mapState.api.places && (
        <PlaceSearch places={mapState.api.places} onPick={(pos) => goTo(pos, 'search')} />
      )}

      {mapState.kind === 'unavailable' && (
        <Alert severity="info" data-testid="map-unavailable">
          {MAP_UNAVAILABLE}
        </Alert>
      )}
      {geoError && (
        <Alert severity="warning" data-testid="location-error">
          {geoError}
        </Alert>
      )}

      {mapOpen && mapState.kind === 'ready' && (
        <>
          <Typography variant="caption" color="text.secondary">
            اسحب الدبوس إلى سطح البيت، أو اضغط على المكان في الخريطة.
          </Typography>
          <MapPicker
            api={mapState.api}
            mapId={mapId}
            center={mapCenter}
            pin={pin}
            onPin={(pos) => setPin({ ...pos, source: 'map', accuracy_m: null })}
          />
        </>
      )}

      <Typography
        variant="body2"
        color={pin ? 'success.main' : 'text.secondary'}
        data-testid="location-status"
      >
        {pin ? (
          <>
            تم تحديد موقع البيت{' '}
            <span dir="ltr" data-testid="location-coords">
              {fmt(pin.lat)}, {fmt(pin.lng)}
            </span>
            {values.location?.source === 'gps' && values.location.accuracy_m != null
              ? ` (دقة تقريبية ${values.location.accuracy_m} م)`
              : ''}
          </>
        ) : (
          'لم يُحدَّد موقع البيت بعد'
        )}
      </Typography>

      <DraftTextField
        field="address"
        label="العنوان"
        value={values.address}
        onText={setText}
        onCommit={commitField}
        multiline
      />
      <DraftTextField
        field="landmark"
        label="أقرب نقطة دالّة"
        value={values.landmark}
        onText={setText}
        onCommit={commitField}
      />
    </Stack>
  );
}
