import * as DropdownMenu from '@radix-ui/react-dropdown-menu';

import { formatDateTime } from '@/lib/dates';
import { useMarkNotificationRead, useNotifications } from '@/features/notifications/api';

const TYPE_LABEL: Record<string, string> = {
  offer: 'New shift offer',
  reassigned: 'Shift reassigned',
  confirmed: 'Shift confirmed',
  withdrawn: 'Assignment withdrawn',
  shift_unfilled: 'Shift unfilled',
  shift_dropped_below_minimum: 'Shift dropped below minimum staff',
};

export function NotificationsBell() {
  const { data: notifications } = useNotifications();
  const markRead = useMarkNotificationRead();
  const unreadCount = notifications?.filter((n) => !n.is_read).length ?? 0;

  return (
    <DropdownMenu.Root>
      <DropdownMenu.Trigger asChild>
        <button
          className="relative rounded-full p-2 text-white/90 hover:bg-white/10"
          aria-label="Notifications"
        >
          <BellIcon />
          {unreadCount > 0 && (
            <span className="absolute right-1 top-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-brand-gold-bright px-1 text-[10px] font-bold text-ink">
              {unreadCount}
            </span>
          )}
        </button>
      </DropdownMenu.Trigger>
      <DropdownMenu.Portal>
        <DropdownMenu.Content
          align="end"
          sideOffset={8}
          className="z-50 max-h-96 w-80 overflow-y-auto rounded-lg border border-line bg-white p-2 shadow-card"
        >
          {!notifications || notifications.length === 0 ? (
            <p className="p-4 text-center text-sm text-ink-soft">All caught up</p>
          ) : (
            notifications.map((n) => (
              <button
                key={n.id}
                onClick={() => !n.is_read && markRead.mutate(n.id)}
                className={`block w-full rounded-md px-3 py-2 text-left text-sm hover:bg-line-soft ${
                  n.is_read ? 'text-ink-soft' : 'font-semibold text-ink'
                }`}
              >
                <div className="flex items-center gap-2">
                  {!n.is_read && <span className="h-1.5 w-1.5 rounded-full bg-brand-gold-bright" />}
                  {TYPE_LABEL[n.type] ?? n.type}
                </div>
                <div className="text-xs font-normal text-ink-faint">{formatDateTime(n.created_at)}</div>
              </button>
            ))
          )}
        </DropdownMenu.Content>
      </DropdownMenu.Portal>
    </DropdownMenu.Root>
  );
}

function BellIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M18 8a6 6 0 0 0-12 0c0 7-3 9-3 9h18s-3-2-3-9" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M13.73 21a2 2 0 0 1-3.46 0" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}
