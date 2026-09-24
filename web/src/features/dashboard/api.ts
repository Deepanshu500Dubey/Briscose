import { useQuery } from '@tanstack/react-query';

import { api } from '@/lib/apiClient';

/** Shape of GET /dashboard/today.
 *
 * The endpoint returns plain JSON (no declared response_model), so this is
 * hand-typed to match the backend exactly — same pattern as ShiftChoiceResponse
 * in src/types/api.ts for the clock-in endpoint. */
export interface TodaySummary {
  shifts_today: number;
  open_shifts_today: number;
  pending_offers: number;
  clocked_in_now: number;
  rostered_now: number;
}

export function useTodaySummary() {
  return useQuery({
    queryKey: ['dashboard', 'today'],
    queryFn: () => api.get<TodaySummary>('/dashboard/today'),
    // Refresh every 60 s — this is a live-ops tile, not a historical report.
    refetchInterval: 60_000,
  });
}

// ---------------------------------------------------------------------------
// GET /dashboard/staffing-by-location
// ---------------------------------------------------------------------------

/** One status bucket inside a location row. */
export type ShiftStatusKey =
  | 'open'
  | 'pending_acceptance'
  | 'confirmed'
  | 'unfilled'
  | 'cancelled';

/** Shape of a single element returned by GET /dashboard/staffing-by-location. */
export interface StaffingByLocationRow {
  location_id: string;
  location_name: string;
  by_status: Record<ShiftStatusKey, number>;
  total: number;
}

export function useStaffingByLocation(days = 7) {
  return useQuery({
    queryKey: ['dashboard', 'staffing-by-location', days],
    queryFn: () =>
      api.get<StaffingByLocationRow[]>('/dashboard/staffing-by-location', { days }),
  });
}

// ---------------------------------------------------------------------------
// GET /dashboard/hours-by-employee
// ---------------------------------------------------------------------------

export interface HoursByEmployeeRow {
  employee_id: string;
  email: string;
  week_start: string;
  worked_hours: number;
  rostered_hours: number;
  delta_hours: number;
}

export function useHoursByEmployee(week?: string) {
  return useQuery({
    queryKey: ['dashboard', 'hours-by-employee', week ?? 'current'],
    queryFn: () =>
      api.get<HoursByEmployeeRow[]>('/dashboard/hours-by-employee', { week }),
  });
}

// ---------------------------------------------------------------------------
// GET /dashboard/shifts-by-weekday
// ---------------------------------------------------------------------------

export interface ShiftsByWeekdayRow {
  day_of_week: number; // 1 = Monday … 7 = Sunday
  day_name: string;
  count: number;
}

export function useShiftsByWeekday(days = 30) {
  return useQuery({
    queryKey: ['dashboard', 'shifts-by-weekday', days],
    queryFn: () =>
      api.get<ShiftsByWeekdayRow[]>('/dashboard/shifts-by-weekday', { days }),
  });
}

// ---------------------------------------------------------------------------
// GET /dashboard/offer-outcomes
// ---------------------------------------------------------------------------

export type AssignmentStatusKey = 'offered' | 'accepted' | 'rejected' | 'withdrawn';

export interface OfferOutcomesRow {
  iso_year: number;
  iso_week: number;
  by_status: Record<AssignmentStatusKey, number>;
  auto_reassignments: number;
  total: number;
}

export function useOfferOutcomes(weeks = 8) {
  return useQuery({
    queryKey: ['dashboard', 'offer-outcomes', weeks],
    queryFn: () =>
      api.get<OfferOutcomesRow[]>('/dashboard/offer-outcomes', { weeks }),
  });
}

// ---------------------------------------------------------------------------
// GET /dashboard/overtime
// ---------------------------------------------------------------------------

export interface OvertimeRow {
  employee_id: string;
  email: string;
  week_start: string;
  total_hours: number;
  overtime_threshold: number;
  over_weekly_limit: boolean;
}

export function useOvertime(week?: string) {
  return useQuery({
    queryKey: ['dashboard', 'overtime', week ?? 'current'],
    queryFn: () =>
      api.get<OvertimeRow[]>('/dashboard/overtime', { week }),
  });
}

// ---------------------------------------------------------------------------
// GET /dashboard/fill-rate-trend
// ---------------------------------------------------------------------------

export interface FillRateTrendRow {
  iso_year: number;
  iso_week: number;
  total_shifts: number;
  confirmed_shifts: number;
  fill_rate_pct: number;
}

export function useFillRateTrend(weeks = 8) {
  return useQuery({
    queryKey: ['dashboard', 'fill-rate-trend', weeks],
    queryFn: () =>
      api.get<FillRateTrendRow[]>('/dashboard/fill-rate-trend', { weeks }),
  });
}
