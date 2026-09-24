import { create } from 'zustand';
import { persist } from 'zustand/middleware';

interface UiState {
  /** The location a Manager is currently viewing the staffing board/roster
   * for — persisted so switching tabs/reloading doesn't lose context. */
  selectedLocationId: string | null;
  setSelectedLocationId: (id: string | null) => void;

  assignDrawerShiftId: string | null;
  openAssignDrawer: (shiftId: string) => void;
  closeAssignDrawer: () => void;

  createShiftOpen: boolean;
  setCreateShiftOpen: (open: boolean) => void;
}

export const useUiStore = create<UiState>()(
  persist(
    (set) => ({
      selectedLocationId: null,
      setSelectedLocationId: (id) => set({ selectedLocationId: id }),

      assignDrawerShiftId: null,
      openAssignDrawer: (shiftId) => set({ assignDrawerShiftId: shiftId }),
      closeAssignDrawer: () => set({ assignDrawerShiftId: null }),

      createShiftOpen: false,
      setCreateShiftOpen: (open) => set({ createShiftOpen: open }),
    }),
    { name: 'crew-ui', partialize: (state) => ({ selectedLocationId: state.selectedLocationId }) },
  ),
);
