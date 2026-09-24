import { NavLink, Outlet } from 'react-router-dom';

import { NotificationsBell } from '@/components/NotificationsBell';
import { useLogout } from '@/features/auth/api';
import { useAuthStore } from '@/stores/auth';

const NAV_ITEMS = [
  { to: '/app', label: 'Dashboard', end: true },
  { to: '/app/shifts', label: 'My Shifts', end: false },
  { to: '/app/availability', label: 'Availability', end: false },
  { to: '/app/timesheet', label: 'Timesheet', end: false },
  { to: '/app/profile', label: 'Profile', end: false },
];

export function EmployeeLayout() {
  const user = useAuthStore((s) => s.user);
  const logout = useLogout();

  return (
    <div className="min-h-screen bg-paper">
      <header className="bg-brand-navy-deep px-4 py-3">
        <div className="mx-auto flex max-w-5xl items-center justify-between">
          <div className="flex items-center gap-8">
            <span className="font-display text-lg font-extrabold tracking-wide text-white">
              BRISCOES <span className="text-brand-gold-bright">Crew</span>
            </span>
            <nav className="flex gap-1">
              {NAV_ITEMS.map((item) => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  end={item.end}
                  className={({ isActive }) =>
                    `rounded-md px-3 py-1.5 text-sm font-semibold transition ${
                      isActive ? 'bg-white/15 text-white' : 'text-white/70 hover:text-white'
                    }`
                  }
                >
                  {item.label}
                </NavLink>
              ))}
            </nav>
          </div>
          <div className="flex items-center gap-3">
            <NotificationsBell />
            <span className="text-sm text-white/80">{user?.email}</span>
            <button
              onClick={() => logout.mutate()}
              className="rounded-md px-3 py-1.5 text-sm font-semibold text-white/80 hover:bg-white/10"
            >
              Log out
            </button>
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-5xl px-4 py-8">
        <Outlet />
      </main>
    </div>
  );
}
