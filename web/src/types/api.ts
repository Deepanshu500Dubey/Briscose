/** Convenience aliases over the generated OpenAPI schemas — the API's own
 * source of truth (see src/types/openapi.d.ts, generated via
 * `npm run gen:api-types`). Import from here everywhere else in the app
 * instead of reaching into `components["schemas"]` directly. */
import type { components } from './openapi';

export type UserRole = components['schemas']['UserRole'];
export type UserResponse = components['schemas']['UserResponse'];
export type UserCreate = components['schemas']['UserCreate'];
export type TokenResponse = components['schemas']['TokenResponse'];
export type PasswordChangeRequest = components['schemas']['PasswordChangeRequest'];

export type LocationResponse = components['schemas']['LocationResponse'];
export type LocationCreate = components['schemas']['LocationCreate'];

export type AvailabilityResponse = components['schemas']['AvailabilityResponse'];
export type AvailabilityDayInput = components['schemas']['AvailabilityDayInput'];

export type ShiftStatus = components['schemas']['ShiftStatus'];
export type ShiftResponse = components['schemas']['ShiftResponse'];
export type CandidateResponse = components['schemas']['CandidateResponse'];
export type AssignedEmployee = components['schemas']['AssignedEmployee'];

export type AssignmentStatus = components['schemas']['AssignmentStatus'];
export type AssignmentResponse = components['schemas']['AssignmentResponse'];

export type NotificationType = components['schemas']['NotificationType'];
export type NotificationResponse = components['schemas']['NotificationResponse'];

export type TimeEntryFlag = components['schemas']['TimeEntryFlag'];
export type TimeEntryResponse = components['schemas']['TimeEntryResponse'];

/** Not in the generated schema: POST /time-entries/clock-in returns a
 * manually-built JSONResponse (see app/api/time_entries.py) rather than a
 * declared response_model, so this ambiguous-shift-choice shape never made
 * it into the OpenAPI output. Hand-typed here to match the real response
 * exactly — same fields as the backend's ShiftChoiceResponse schema. */
export interface ShiftChoiceResponse {
  id: string;
  date: string;
  start_time: string;
  end_time: string;
  location_id: string;
}

export type ClockInResult = TimeEntryResponse | { choose_shift: ShiftChoiceResponse[] };

export function isChooseShiftResult(
  result: ClockInResult,
): result is { choose_shift: ShiftChoiceResponse[] } {
  return 'choose_shift' in result;
}

export type TimesheetResponse = components['schemas']['TimesheetResponse'];
export type TimesheetDayResponse = components['schemas']['TimesheetDayResponse'];
