/**
 * Map positions (staging crash: «Cannot read properties of undefined (reading 'toFixed')»).
 * Google may hand us a LatLng (lat()/lng()), a literal, a LatLngAltitude with getter properties,
 * or nothing. The map picker must accept the first ones and ignore the rest without crashing.
 */
import { cleanup, render, screen } from '@testing-library/react';
import { createMemoryRouter, RouterProvider } from 'react-router-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';

import RouteError, { ROUTE_ERROR_TITLE } from '../components/RouteError';
import { toLatLngLiteral, type MapMouseEvent, type MapsApi } from '../lib/googleMaps';
import { MapPicker } from '../pages/marketer/subscriber/MapPicker';

afterEach(cleanup);

/** Like google.maps.LatLng: coordinates only through methods. */
class FakeLatLng {
  #lat: number;
  #lng: number;
  constructor(lat: number, lng: number) {
    this.#lat = lat;
    this.#lng = lng;
  }
  lat() {
    return this.#lat;
  }
  lng() {
    return this.#lng;
  }
}

/** Like google.maps.LatLngAltitude: prototype getters, so `{...pos}` would lose them. */
class FakeLatLngAltitude {
  #lat: number;
  #lng: number;
  constructor(lat: number, lng: number) {
    this.#lat = lat;
    this.#lng = lng;
  }
  get lat() {
    return this.#lat;
  }
  get lng() {
    return this.#lng;
  }
}

describe('toLatLngLiteral', () => {
  it('reads a LatLng with lat()/lng() methods', () => {
    expect(toLatLngLiteral(new FakeLatLng(33.31, 44.36))).toEqual({ lat: 33.31, lng: 44.36 });
  });

  it('reads a literal and getter properties', () => {
    expect(toLatLngLiteral({ lat: 33.31, lng: 44.36 })).toEqual({ lat: 33.31, lng: 44.36 });
    expect(toLatLngLiteral(new FakeLatLngAltitude(33.31, 44.36))).toEqual({
      lat: 33.31,
      lng: 44.36,
    });
  });

  it('returns null when there are no usable coordinates', () => {
    for (const bad of [
      null,
      undefined,
      {},
      { lat: 33.31 },
      { lat: undefined, lng: undefined },
      { lat: '33.31', lng: '44.36' },
      { lat: Number.NaN, lng: 44.36 },
      { lat: () => undefined, lng: () => undefined },
      42,
    ]) {
      expect(toLatLngLiteral(bad)).toBeNull();
    }
  });
});

/** A fake Maps API that keeps the listeners so the test can fire them. */
function fakeApi() {
  const handlers: {
    click?: (e: MapMouseEvent | undefined) => void;
    dragend?: () => void;
  } = {};
  const marker = { map: null as unknown, position: null as unknown, gmpDraggable: true };
  const api = {
    Map: vi.fn(function () {
      return {
        panTo: vi.fn(),
        setZoom: vi.fn(),
        addListener: (_: string, h: (e: MapMouseEvent | undefined) => void) => {
          handlers.click = h;
          return { remove: vi.fn() };
        },
      };
    }),
    AdvancedMarkerElement: vi.fn(function (opts: Record<string, unknown>) {
      marker.position = opts.position;
      return Object.assign(marker, {
        addEventListener: (event: string, h: () => void) => {
          if (event === 'gmp-dragend') handlers.dragend = h;
        },
        removeEventListener: vi.fn(),
        addListener: () => {
          throw new Error('the marker must use addEventListener with gmp- events');
        },
      });
    }),
  } as unknown as MapsApi;
  return { api, handlers, marker };
}

function renderPicker() {
  const fake = fakeApi();
  const onPin = vi.fn();
  render(
    <MapPicker
      api={fake.api}
      mapId=""
      center={{ lat: 33.3, lng: 44.4 }}
      pin={null}
      onPin={onPin}
    />,
  );
  return { ...fake, onPin };
}

describe('MapPicker events', () => {
  it('click with a LatLng (methods) moves the pin', () => {
    const { handlers, marker, onPin } = renderPicker();
    handlers.click?.({ latLng: new FakeLatLng(33.31, 44.36) });
    expect(onPin).toHaveBeenCalledWith({ lat: 33.31, lng: 44.36 });
    expect(marker.position).toEqual({ lat: 33.31, lng: 44.36 });
  });

  it('click with a LatLngLiteral moves the pin', () => {
    const { handlers, onPin } = renderPicker();
    handlers.click?.({ latLng: { lat: 33.32, lng: 44.37 } });
    expect(onPin).toHaveBeenCalledWith({ lat: 33.32, lng: 44.37 });
  });

  it('click without coordinates is ignored', () => {
    const { handlers, marker, onPin } = renderPicker();
    expect(() => {
      handlers.click?.({ latLng: null });
      handlers.click?.({});
      handlers.click?.(undefined);
    }).not.toThrow();
    expect(onPin).not.toHaveBeenCalled();
    expect(marker.position).toBeNull();
  });

  it('drag reads LatLng, literal and getter positions, and ignores an empty one', () => {
    const { handlers, marker, onPin } = renderPicker();
    marker.position = new FakeLatLng(33.4, 44.5);
    handlers.dragend?.();
    marker.position = { lat: 33.41, lng: 44.51 };
    handlers.dragend?.();
    marker.position = new FakeLatLngAltitude(33.42, 44.52);
    handlers.dragend?.();
    marker.position = null;
    handlers.dragend?.();
    expect(onPin.mock.calls).toEqual([
      [{ lat: 33.4, lng: 44.5 }],
      [{ lat: 33.41, lng: 44.51 }],
      [{ lat: 33.42, lng: 44.52 }],
    ]);
  });
});

describe('RouteError', () => {
  it('shows an Arabic message when a page throws', () => {
    vi.spyOn(console, 'error').mockImplementation(() => {});
    function Broken(): never {
      throw new TypeError("Cannot read properties of undefined (reading 'toFixed')");
    }
    const router = createMemoryRouter(
      [{ errorElement: <RouteError />, children: [{ path: '/', element: <Broken /> }] }],
      { initialEntries: ['/'] },
    );
    render(<RouterProvider router={router} />);
    expect(screen.getByTestId('route-error').textContent).toContain(ROUTE_ERROR_TITLE);
    expect(screen.queryByText(/toFixed/)).toBeNull();
    vi.restoreAllMocks();
  });
});
