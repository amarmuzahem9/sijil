/**
 * «التقارير والتصدير» (docs/system.md v1.25 §11; specs/019 contracts/api.md): the requests report
 * with its filters and summaries. A row never carries an identity number, phone, image or money;
 * the server decides who may export identity data (`can_export_identity`).
 */
import { apiFetch } from './api';
import type { DateKind, PeriodKind } from './labels';
import type { RequestStatus } from './requestStatus';

export type ReportStatus = Exclude<RequestStatus, 'draft'>;
export type RequestType = 'new' | 'additional' | 'return';

export interface ReportFilters {
  period: PeriodKind;
  from?: string;
  to?: string;
  date_kind: DateKind;
  area_id?: number;
  tower_id?: number;
  marketer_id?: number;
  plan_id?: number;
  status?: ReportStatus;
  type?: RequestType;
}

export interface ReportRow {
  id: number;
  number: number;
  number_label: string;
  /** Null for a deleted request (§7.4). */
  name: string | null;
  deleted: boolean;
  tower: string;
  plan: string;
  marketer: string;
  status: ReportStatus;
  type: RequestType;
  submitted_at: string;
  linked_at: string | null;
}

export interface ReportSummary {
  by_status: { status: ReportStatus; count: number }[];
  by_tower: { tower_id: number; tower: string; count: number }[];
  by_marketer: { marketer_id: number; marketer: string; count: number }[];
}

export interface ReportResult {
  total: number;
  page: number;
  page_size: number;
  rows: ReportRow[];
  summary: ReportSummary;
  can_export_identity: boolean;
}

export interface ReportOptions {
  areas: { id: number; name: string; active: boolean }[];
  towers: { id: number; code: string; name: string; area_id: number; active: boolean }[];
  plans: { id: number; name: string; active: boolean }[];
  marketers: { id: number; name: string; archived: boolean; active: boolean }[];
}

export const REPORT_PAGE_SIZE = 50;

/** The query string of the filters; empty values are left out. */
export function filterParams(filters: ReportFilters): URLSearchParams {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(filters)) {
    if (value !== undefined && value !== null && value !== '') params.set(key, String(value));
  }
  return params;
}

export const fetchReport = (filters: ReportFilters, page = 1) => {
  const params = filterParams(filters);
  params.set('page', String(page));
  return apiFetch<ReportResult>(`/api/admin/reports/requests?${params.toString()}`);
};

export const fetchOptions = () => apiFetch<ReportOptions>('/api/admin/reports/options');
