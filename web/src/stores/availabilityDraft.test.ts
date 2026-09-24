import { beforeEach, describe, expect, it } from 'vitest';

import { useAvailabilityDraftStore } from './availabilityDraft';

describe('useAvailabilityDraftStore', () => {
  beforeEach(() => {
    useAvailabilityDraftStore.setState({ days: {}, dirtyDates: new Set() });
  });

  it('setInitial indexes days by date and starts clean', () => {
    useAvailabilityDraftStore.getState().setInitial([
      { date: '2026-08-27', is_available: true, start_time: '08:00:00', end_time: '16:00:00' },
      { date: '2026-08-28', is_available: false, start_time: null, end_time: null },
    ]);

    const state = useAvailabilityDraftStore.getState();
    expect(state.days['2026-08-27'].is_available).toBe(true);
    expect(state.days['2026-08-28'].is_available).toBe(false);
    expect(state.dirtyDates.size).toBe(0);
  });

  it('updateDay patches a single day and marks it dirty', () => {
    useAvailabilityDraftStore.getState().setInitial([
      { date: '2026-08-27', is_available: false, start_time: null, end_time: null },
    ]);

    useAvailabilityDraftStore.getState().updateDay('2026-08-27', {
      is_available: true,
      start_time: '09:00:00',
      end_time: '17:00:00',
    });

    const state = useAvailabilityDraftStore.getState();
    expect(state.days['2026-08-27']).toEqual({
      date: '2026-08-27',
      is_available: true,
      start_time: '09:00:00',
      end_time: '17:00:00',
    });
    expect(state.dirtyDates.has('2026-08-27')).toBe(true);
  });

  it('updateDay does not mark unrelated days dirty', () => {
    useAvailabilityDraftStore.getState().setInitial([
      { date: '2026-08-27', is_available: false, start_time: null, end_time: null },
      { date: '2026-08-28', is_available: false, start_time: null, end_time: null },
    ]);

    useAvailabilityDraftStore.getState().updateDay('2026-08-27', { is_available: true });

    const state = useAvailabilityDraftStore.getState();
    expect(state.dirtyDates.has('2026-08-27')).toBe(true);
    expect(state.dirtyDates.has('2026-08-28')).toBe(false);
  });

  it('updateDay accumulates multiple dirty dates', () => {
    useAvailabilityDraftStore.getState().setInitial([
      { date: '2026-08-27', is_available: false, start_time: null, end_time: null },
      { date: '2026-08-28', is_available: false, start_time: null, end_time: null },
    ]);

    useAvailabilityDraftStore.getState().updateDay('2026-08-27', { is_available: true });
    useAvailabilityDraftStore.getState().updateDay('2026-08-28', { is_available: true });

    expect(useAvailabilityDraftStore.getState().dirtyDates.size).toBe(2);
  });

  it('markSaved clears dirtyDates without touching the day data', () => {
    useAvailabilityDraftStore.getState().setInitial([
      { date: '2026-08-27', is_available: false, start_time: null, end_time: null },
    ]);
    useAvailabilityDraftStore.getState().updateDay('2026-08-27', { is_available: true });

    useAvailabilityDraftStore.getState().markSaved();

    const state = useAvailabilityDraftStore.getState();
    expect(state.dirtyDates.size).toBe(0);
    expect(state.days['2026-08-27'].is_available).toBe(true);
  });
});
