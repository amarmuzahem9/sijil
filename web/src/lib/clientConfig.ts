/** Runtime browser configuration from the server (specs/005 research.md R10). */
import { useQuery } from '@tanstack/react-query';

import { apiFetch } from './api';

export interface MapsConfig {
  api_key: string;
  map_id: string;
  default_center: { lat: number; lng: number };
}

/** An open-source component whose source the app's users may get (specs/006 FR-022). */
export interface OpenSourceItem {
  name: string;
  licence: string;
  url: string;
}

export interface ClientConfig {
  /** null when no Maps key is configured: the form works without the map. */
  maps: MapsConfig | null;
  open_source?: OpenSourceItem[];
  /** false when no OTPIQ key is configured (specs/007): «خدمة التحقق غير مهيّأة». */
  otp_enabled?: boolean;
}

export const fetchClientConfig = () => apiFetch<ClientConfig>('/api/client-config');

export function useClientConfig() {
  return useQuery({
    queryKey: ['client-config'],
    queryFn: fetchClientConfig,
    staleTime: 60 * 60 * 1000,
  });
}
