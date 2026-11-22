/**
 * Place search bar (docs/system.md §5.2 v1.6): Google Places Autocomplete limited to Iraq, in
 * Arabic. Picking a result moves the pin there and saves it.
 */
import SearchOutlined from '@mui/icons-material/SearchOutlined';
import Autocomplete from '@mui/material/Autocomplete';
import Box from '@mui/material/Box';
import CircularProgress from '@mui/material/CircularProgress';
import InputAdornment from '@mui/material/InputAdornment';
import TextField from '@mui/material/TextField';
import Typography from '@mui/material/Typography';
import { useEffect, useRef, useState } from 'react';

import { COORDINATE_ERRORS, inIraq } from '../../../lib/coordinates';
import type { LatLngLiteral, PlacesLibrary } from '../../../lib/googleMaps';
import {
  PLACES_DEBOUNCE_MS,
  PLACES_MIN_CHARS,
  placeLocation,
  searchPlaces,
  type PlaceSuggestion,
} from '../../../lib/placesSearch';

export const SEARCH_UNAVAILABLE = 'البحث عن الأماكن غير متاح حالياً';
export const PLACE_NO_LOCATION = 'تعذّر تحديد موقع هذا المكان، اختر نتيجة أخرى';

export function PlaceSearch({
  places,
  onPick,
}: {
  places: PlacesLibrary;
  onPick: (pos: LatLngLiteral) => void;
}) {
  const [input, setInput] = useState('');
  const [options, setOptions] = useState<PlaceSuggestion[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const token = useRef<unknown>(null);

  useEffect(() => {
    const query = input.trim();
    if (query.length < PLACES_MIN_CHARS) return;
    let cancelled = false;
    const timer = setTimeout(() => {
      token.current ??= new places.AutocompleteSessionToken();
      setLoading(true);
      searchPlaces(places, query, token.current)
        .then((found) => {
          if (cancelled) return;
          setOptions(found);
          setError(null);
        })
        .catch(() => {
          if (!cancelled) setError(SEARCH_UNAVAILABLE);
        })
        .finally(() => {
          if (!cancelled) setLoading(false);
        });
    }, PLACES_DEBOUNCE_MS);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [input, places]);

  async function pick(s: PlaceSuggestion | null) {
    if (!s) return;
    setError(null);
    try {
      const pos = await placeLocation(s.prediction);
      if (!pos) setError(PLACE_NO_LOCATION);
      else if (!inIraq(pos)) setError(COORDINATE_ERRORS.outside_iraq);
      else onPick(pos);
    } catch {
      setError(SEARCH_UNAVAILABLE);
    } finally {
      token.current = null; // the session ends with the details request
    }
  }

  return (
    <Autocomplete
      options={input.trim().length < PLACES_MIN_CHARS ? [] : options}
      value={null}
      inputValue={input}
      onInputChange={(_, value, reason) => {
        if (reason !== 'reset') setInput(value);
      }}
      onChange={(_, value) => void pick(value)}
      filterOptions={(x) => x}
      getOptionLabel={(o) => o.main}
      isOptionEqualToValue={(a, b) => a.placeId === b.placeId}
      loading={loading}
      noOptionsText={input.trim().length < PLACES_MIN_CHARS ? 'اكتب اسم المكان' : 'لا توجد نتائج'}
      loadingText="جارٍ البحث…"
      clearOnBlur={false}
      blurOnSelect
      renderOption={({ key, ...props }, o) => (
        <Box component="li" key={key} {...props} data-testid="place-option">
          <Box>
            <Typography variant="body2">{o.main}</Typography>
            {o.secondary && (
              <Typography variant="caption" color="text.secondary">
                {o.secondary}
              </Typography>
            )}
          </Box>
        </Box>
      )}
      renderInput={(params) => (
        <TextField
          {...params}
          label="ابحث عن مكان"
          size="small"
          error={Boolean(error)}
          helperText={error ?? 'داخل العراق فقط'}
          slotProps={{
            ...params.slotProps,
            input: {
              ...params.slotProps.input,
              startAdornment: (
                <InputAdornment position="start">
                  <SearchOutlined fontSize="small" />
                </InputAdornment>
              ),
              endAdornment: (
                <>
                  {loading && <CircularProgress size={16} />}
                  {params.slotProps.input.endAdornment}
                </>
              ),
            },
            htmlInput: { ...params.slotProps.htmlInput, 'data-testid': 'place-search' },
          }}
        />
      )}
    />
  );
}
