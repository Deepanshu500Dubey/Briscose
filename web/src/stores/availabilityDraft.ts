import { create } from 'zustand';

export interface AvailabilityDayDraft {
  date: string;
  is_available: boolean;
  start_time: string | null;
  end_time: string | null;
}

interface AvailabilityDraftState {
  days: Record<string, AvailabilityDayDraft>;
  dirtyDates: Set<string>;
  setInitial: (days: AvailabilityDayDraft[]) => void;
  updateDay: (date: string, patch: Partial<Omit<AvailabilityDayDraft, 'date'>>) => void;
  markSaved: () => void;
}

/** Holds in-progress edits to the 14-day availability grid before Save —
 * server state (the persisted rows) lives in TanStack Query, this is purely
 * the unsaved draft (project blueprint, Section 5's stores/ split). */
export const useAvailabilityDraftStore = create<AvailabilityDraftState>((set) => ({
  days: {},
  dirtyDates: new Set(),
  setInitial: (days) =>
    set({
      days: Object.fromEntries(days.map((d) => [d.date, d])),
      dirtyDates: new Set(),
    }),
  updateDay: (date, patch) =>
    set((state) => ({
      days: {
        ...state.days,
        [date]: { ...state.days[date], date, ...patch } as AvailabilityDayDraft,
      },
      dirtyDates: new Set(state.dirtyDates).add(date),
    })),
  markSaved: () => set({ dirtyDates: new Set() }),
}));
