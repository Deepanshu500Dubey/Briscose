import { useEffect } from 'react';
import { NavLink, Outlet, useLocation } from 'react-router-dom';

import { NotificationsBell } from '@/components/NotificationsBell';
import { useLogout } from '@/features/auth/api';
import { useLocations } from '@/features/locations/api';
import { useAuthStore } from '@/stores/auth';
import { useUiStore } from '@/stores/ui';

const NAV_ITEMS = [
  { to: '/manage/dashboard', label: 'Dashboard', end: false },
  { to: '/manage/staffing', label: 'Staffing Board', end: false },
  { to: '/manage/unfilled', label: 'Unfilled', end: false },
  { to: '/manage/roster', label: 'Roster', end: false },
  { to: '/manage/team-availability', label: 'Team & Availability', end: false },
  { to: '/manage/timesheets', label: 'Team Timesheets', end: false },
];

const ADMIN_NAV_ITEMS = [
  { to: '/manage/admin/locations', label: 'Locations', end: false },
  { to: '/manage/admin/users', label: 'Users', end: false },
];

export function ManagerLayout() {
  const user = useAuthStore((s) => s.user);
  const logout = useLogout();
  const { data: locations } = useLocations();
  const selectedLocationId = useUiStore((s) => s.selectedLocationId);
  const setSelectedLocationId = useUiStore((s) => s.setSelectedLocationId);
  const location = useLocation();
  const isAdminRoute = location.pathname.startsWith('/manage/admin');

  // Default to the first location visible to this manager/admin once
  // locations load, if nothing (or a now-invalid location) is selected.
  useEffect(() => {
    if (!locations || locations.length === 0) return;
    const stillValid = locations.some((l) => l.id === selectedLocationId);
    if (!stillValid) setSelectedLocationId(locations[0].id);
  }, [locations, selectedLocationId, setSelectedLocationId]);

  return (
    <div className="min-h-screen bg-paper">
      <header className="bg-brand-navy-deep px-4 py-3">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-2">
          <div className="flex flex-wrap items-center gap-6">
            <span className="font-display text-lg font-extrabold tracking-wide text-white">
              BRISCOES <span className="text-brand-gold-bright">Crew</span>
            </span>
            <nav className="flex flex-wrap gap-1">
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
              {user?.role === 'admin' && (
                <>
                  <span className="mx-1 self-center text-white/30">|</span>
                  {ADMIN_NAV_ITEMS.map((item) => (
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
                </>
              )}
            </nav>
          </div>
          <div className="flex items-center gap-3">
            {locations && locations.length > 0 && (
              <select
                value={selectedLocationId ?? ''}
                onChange={(e) => setSelectedLocationId(e.target.value)}
                className="rounded-md border border-white/20 bg-brand-navy-deep px-2 py-1.5 text-sm text-white"
              >
                {locations.map((loc) => (
                  <option key={loc.id} value={loc.id} className="text-ink">
                    {loc.name}
                  </option>
                ))}
              </select>
            )}
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
      <main className="mx-auto max-w-6xl px-4 py-8">
        {/* Admin routes (e.g. creating the very first location) must stay
            reachable even with zero locations assigned yet — only the
            location-scoped screens need to block on that. */}
        {locations && locations.length === 0 && !isAdminRoute ? (
          <p className="text-sm text-ink-soft">
            No locations are assigned to your account yet
            {user?.role === 'admin' ? (
              <>
                {' '}
                — <NavLink to="/manage/admin/locations" className="underline">create one</NavLink>{' '}
                and assign yourself, or ask another Admin to.
              </>
            ) : (
              ' — ask an Admin to assign you to a location.'
            )}
          </p>
        ) : (
          <Outlet />
        )}
      </main>
    </div>
  );
}
