import { create } from 'zustand';

interface Toast {
  id: number;
  title: string;
  tone: 'success' | 'error';
}

interface ToastState {
  toasts: Toast[];
  push: (title: string, tone: Toast['tone']) => void;
  dismiss: (id: number) => void;
}

let nextId = 1;

export const useToastStore = create<ToastState>((set) => ({
  toasts: [],
  push: (title, tone) =>
    set((state) => ({ toasts: [...state.toasts, { id: nextId++, title, tone }] })),
  dismiss: (id) => set((state) => ({ toasts: state.toasts.filter((t) => t.id !== id) })),
}));

export function toastSuccess(title: string) {
  useToastStore.getState().push(title, 'success');
}

export function toastError(title: string) {
  useToastStore.getState().push(title, 'error');
}
