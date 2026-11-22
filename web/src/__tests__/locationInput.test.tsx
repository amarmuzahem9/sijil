/**
 * «موقع البيت» inputs (docs/system.md §5.2 v1.6): typed coordinates and Google Maps links, the Iraq
 * bounding box, and the Places search bar (Iraq only, Arabic). Coordinates are synthetic.
 */
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { COORDINATE_ERRORS, inIraq, parseCoordinates } from '../lib/coordinates';
import type { PlacePrediction, PlacesLibrary } from '../lib/googleMaps';
import { suggestionRequest } from '../lib/placesSearch';
import { CoordinateInput } from '../pages/marketer/subscriber/CoordinateInput';
import { PlaceSearch, SEARCH_UNAVAILABLE } from '../pages/marketer/subscriber/PlaceSearch';

afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

const AR = (s: string) => s.replace(/\d/g, (d) => String.fromCodePoint(0x0660 + Number(d)));

describe('parseCoordinates', () => {
  it.each([
    ['34.70, 43.68', 34.7, 43.68],
    ['34.70,43.68', 34.7, 43.68],
    ['  34.70   43.68 ', 34.7, 43.68],
    ['33.3152, 44.3661', 33.3152, 44.3661],
    ['geo:36.19,44.01', 36.19, 44.01],
    ['https://www.google.com/maps/@34.70,43.68,17z', 34.7, 43.68],
    ['https://maps.google.com/?q=34.70,43.68', 34.7, 43.68],
    ['https://www.google.com/maps/search/?api=1&query=34.70%2C43.68', 34.7, 43.68],
    ['https://www.google.com/maps/search/34.70,+43.68?entry=ttu', 34.7, 43.68],
    // A place link: the place (!3d/!4d) wins over the viewport (@).
    [
      'https://www.google.com/maps/place/X/@33.30,44.30,15z/data=!3m1!4b1!4m6!3m5!8m2!3d33.3152!4d44.3661',
      33.3152,
      44.3661,
    ],
  ])('reads %s', (input, lat, lng) => {
    expect(parseCoordinates(input)).toEqual({ ok: true, pos: { lat, lng } });
  });

  it('reads Arabic-Indic digits, the Arabic decimal mark and comma', () => {
    const text = `${AR('34')}٫${AR('70')}، ${AR('43')}٫${AR('68')}`;
    expect(parseCoordinates(text)).toEqual({ ok: true, pos: { lat: 34.7, lng: 43.68 } });
  });

  it.each([
    ['', 'empty'],
    ['   ', 'empty'],
    ['بغداد', 'format'],
    ['34.70', 'format'],
    ['34.70, 43.68, 12', 'format'],
    ['https://www.google.com/maps', 'format'],
    ['https://maps.app.goo.gl/AbCdEf123', 'short_link'],
    ['43.68, 34.70', 'swapped'],
    ['33.89, 35.50', 'outside_iraq'],
    ['24.71, 46.67', 'outside_iraq'],
    ['95, 44', 'format'],
  ])('refuses %j (%s)', (input, error) => {
    expect(parseCoordinates(input)).toEqual({ ok: false, error });
  });

  it('keeps the Iraq box in step with the server (border cities inside)', () => {
    expect(inIraq({ lat: 37.15, lng: 42.68 })).toBe(true); // Zakho
    expect(inIraq({ lat: 30.51, lng: 47.81 })).toBe(true); // Basra
    expect(inIraq({ lat: 33.0, lng: 41.0 })).toBe(true); // western desert
    expect(inIraq({ lat: 0, lng: 0 })).toBe(false);
  });
});

describe('CoordinateInput', () => {
  function type(text: string) {
    fireEvent.change(screen.getByTestId('coordinate-input'), { target: { value: text } });
  }

  it('«انتقال» sends a valid coordinate', () => {
    const onGo = vi.fn();
    render(<CoordinateInput onGo={onGo} />);
    type('34.70, 43.68');
    fireEvent.click(screen.getByTestId('coordinate-go'));
    expect(onGo).toHaveBeenCalledWith({ lat: 34.7, lng: 43.68 });
  });

  it('Enter works too, and a bad value shows the Arabic message without moving the pin', () => {
    const onGo = vi.fn();
    render(<CoordinateInput onGo={onGo} />);
    type('33.89, 35.50');
    fireEvent.keyDown(screen.getByTestId('coordinate-input'), { key: 'Enter' });
    expect(onGo).not.toHaveBeenCalled();
    expect(screen.getByText(COORDINATE_ERRORS.outside_iraq)).toBeTruthy();

    type('https://www.google.com/maps/@34.70,43.68,17z');
    expect(screen.queryByText(COORDINATE_ERRORS.outside_iraq)).toBeNull();
    fireEvent.keyDown(screen.getByTestId('coordinate-input'), { key: 'Enter' });
    expect(onGo).toHaveBeenCalledWith({ lat: 34.7, lng: 43.68 });
  });
});

/** A fake Places library: one suggestion per query, located where the test says. */
function fakePlaces(location: unknown, opts: { fail?: boolean } = {}) {
  const requests: Record<string, unknown>[] = [];
  const fetchFields = vi.fn(async () => undefined);
  const prediction: PlacePrediction = {
    placeId: 'p1',
    mainText: { text: 'ساحة تجريبية' },
    secondaryText: { text: 'بغداد، العراق' },
    toPlace: () => ({ fetchFields, location }),
  };
  const lib: PlacesLibrary = {
    AutocompleteSessionToken: class {} as unknown as PlacesLibrary['AutocompleteSessionToken'],
    AutocompleteSuggestion: {
      fetchAutocompleteSuggestions: vi.fn(async (req: Record<string, unknown>) => {
        requests.push(req);
        if (opts.fail) throw new Error('REQUEST_DENIED');
        return { suggestions: [{ placePrediction: prediction }, { placePrediction: null }] };
      }),
    },
  };
  return { lib, requests, fetchFields };
}

async function searchFor(text: string) {
  const input = screen.getByTestId('place-search');
  fireEvent.focus(input);
  fireEvent.change(input, { target: { value: text } });
  await act(async () => {
    await vi.advanceTimersByTimeAsync(400);
  });
}

describe('PlaceSearch', () => {
  it('asks Google for Iraq-only Arabic results and moves the pin to the pick', async () => {
    vi.useFakeTimers();
    const { lib, requests, fetchFields } = fakePlaces({ lat: () => 33.3336, lng: () => 44.4342 });
    const onPick = vi.fn();
    render(<PlaceSearch places={lib} onPick={onPick} />);

    await searchFor('ساحة');
    expect(requests).toHaveLength(1);
    expect(requests[0]).toMatchObject({
      input: 'ساحة',
      includedRegionCodes: ['iq'],
      region: 'iq',
      language: 'ar',
    });
    expect(requests[0].sessionToken).toBeTruthy();

    fireEvent.click(screen.getByTestId('place-option'));
    await act(async () => {
      await vi.runAllTimersAsync();
    });
    expect(fetchFields).toHaveBeenCalledWith({ fields: ['location'] });
    expect(onPick).toHaveBeenCalledWith({ lat: 33.3336, lng: 44.4342 });
  });

  it('does not search for one letter', async () => {
    vi.useFakeTimers();
    const { lib, requests } = fakePlaces({ lat: 33.3, lng: 44.4 });
    render(<PlaceSearch places={lib} onPick={vi.fn()} />);
    await searchFor('س');
    expect(requests).toHaveLength(0);
  });

  it('a result outside Iraq or without a location does not move the pin', async () => {
    vi.useFakeTimers();
    for (const location of [{ lat: 33.89, lng: 35.5 }, null]) {
      const { lib } = fakePlaces(location);
      const onPick = vi.fn();
      render(<PlaceSearch places={lib} onPick={onPick} />);
      await searchFor('ساحة');
      fireEvent.click(screen.getByTestId('place-option'));
      await act(async () => {
        await vi.runAllTimersAsync();
      });
      expect(onPick).not.toHaveBeenCalled();
      cleanup();
    }
  });

  it('a Google error (e.g. Places API not enabled) shows an Arabic message', async () => {
    vi.useFakeTimers();
    const { lib } = fakePlaces(null, { fail: true });
    render(<PlaceSearch places={lib} onPick={vi.fn()} />);
    await searchFor('ساحة');
    expect(screen.getByText(SEARCH_UNAVAILABLE)).toBeTruthy();
  });

  it('suggestionRequest carries the session token', () => {
    const token = {};
    expect(suggestionRequest('x', token).sessionToken).toBe(token);
  });
});
