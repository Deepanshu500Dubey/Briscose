import * as ToastPrimitive from '@radix-ui/react-toast';

import { useToastStore } from '@/stores/toast';

export function Toaster() {
  const toasts = useToastStore((s) => s.toasts);
  const dismiss = useToastStore((s) => s.dismiss);

  return (
    <ToastPrimitive.Provider swipeDirection="right">
      {toasts.map((toast) => (
        <ToastPrimitive.Root
          key={toast.id}
          duration={4000}
          onOpenChange={(open) => !open && dismiss(toast.id)}
          className={`rounded-lg border px-4 py-3 text-sm font-medium shadow-card data-[state=open]:animate-in data-[state=closed]:animate-out ${
            toast.tone === 'success'
              ? 'border-status-ok-line bg-status-ok-bg text-status-ok-fg'
              : 'border-status-bad-line bg-status-bad-bg text-status-bad-fg'
          }`}
        >
          <ToastPrimitive.Title>{toast.title}</ToastPrimitive.Title>
        </ToastPrimitive.Root>
      ))}
      <ToastPrimitive.Viewport className="fixed bottom-4 right-4 z-50 flex w-80 flex-col gap-2" />
    </ToastPrimitive.Provider>
  );
}
