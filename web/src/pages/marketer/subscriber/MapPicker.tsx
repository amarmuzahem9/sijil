/** Satellite map with a draggable pin (specs/005 US6, research.md R10). Tapping moves the pin. */
import Box from '@mui/material/Box';
import { useEffect, useRef } from 'react';

import {
  readPosition,
  toLatLngLiteral,
  type GMap,
  type GMarker,
  type LatLngLiteral,
  type MapsApi,
} from '../../../lib/googleMaps';

export function MapPicker({
  api,
  mapId,
  center,
  pin,
  onPin,
}: {
  api: MapsApi;
  mapId: string;
  center: LatLngLiteral;
  pin: LatLngLiteral | null;
  onPin: (pos: LatLngLiteral) => void;
}) {
  const el = useRef<HTMLDivElement>(null);
  const map = useRef<GMap | null>(null);
  const marker = useRef<GMarker | null>(null);
  const onPinRef = useRef(onPin);
  useEffect(() => {
    onPinRef.current = onPin;
  }, [onPin]);

  // Create the map once.
  useEffect(() => {
    if (!el.current || map.current) return;
    const m = new api.Map(el.current, {
      center: pin ?? center,
      zoom: pin ? 19 : 17,
      mapTypeId: 'satellite',
      mapId: mapId || undefined,
      gestureHandling: 'greedy',
      streetViewControl: false,
      fullscreenControl: false,
      mapTypeControl: false,
      clickableIcons: false,
    });
    const mk = new api.AdvancedMarkerElement({
      map: m,
      position: pin ?? null,
      gmpDraggable: true,
      title: 'البيت',
    });
    const drag = mk.addListener('dragend', () => {
      const pos = readPosition(mk);
      if (pos) onPinRef.current(pos);
    });
    const click = m.addListener('click', (e) => {
      // LatLng, literal, or nothing at all (e.g. a tap on a control): ignore what has no numbers.
      const pos = toLatLngLiteral(e?.latLng);
      if (!pos) return;
      mk.position = pos;
      onPinRef.current(pos);
    });
    map.current = m;
    marker.current = mk;
    return () => {
      drag.remove();
      click.remove();
      mk.map = null;
      map.current = null;
      marker.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [api, mapId]);

  // Follow pin changes from outside (GPS button, another device's version).
  useEffect(() => {
    if (!marker.current || !map.current || !pin) return;
    const current = readPosition(marker.current);
    if (current && current.lat === pin.lat && current.lng === pin.lng) return;
    marker.current.position = pin;
    map.current.panTo(pin);
  }, [pin]);

  return (
    <Box
      ref={el}
      data-testid="map-picker"
      sx={{ width: '100%', height: { xs: 320, sm: 380 }, borderRadius: 1, overflow: 'hidden' }}
    />
  );
}
