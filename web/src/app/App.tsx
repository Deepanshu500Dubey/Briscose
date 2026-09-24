import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';

import { Toaster } from '@/components/Toaster';

import { AdminLocationsPage } from './admin/AdminLocationsPage';
import { AdminUsersPage } from './admin/AdminUsersPage';
import { LoginPage } from './auth/LoginPage';
import { AvailabilityPage } from './employee/AvailabilityPage';
import { DashboardPage } from './employee/DashboardPage';
import { EmployeeLayout } from './employee/EmployeeLayout';
import { MyShiftsPage } from './employee/MyShiftsPage';
import { ProfilePage } from './employee/ProfilePage';
import { TimesheetPage } from './employee/TimesheetPage';
import { ManagerDashboardPage } from './manager/ManagerDashboardPage';
import { ManagerLayout } from './manager/ManagerLayout';
import { RosterPage } from './manager/RosterPage';
import { StaffingBoardPage } from './manager/StaffingBoardPage';
import { TeamAvailabilityPage } from './manager/TeamAvailabilityPage';
import { TeamTimesheetsPage } from './manager/TeamTimesheetsPage';
import { UnfilledShiftsPage } from './manager/UnfilledShiftsPage';
import { RequireAuth } from './RequireAuth';
import { RoleGate, RoleRedirect } from './RoleGate';

export function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />

        <Route path="/" element={<RequireAuth><RoleRedirect /></RequireAuth>} />

        <Route
          path="/app"
          element={
            <RequireAuth>
              <RoleGate allow={['employee']}>
                <EmployeeLayout />
              </RoleGate>
            </RequireAuth>
          }
        >
          <Route index element={<DashboardPage />} />
          <Route path="shifts" element={<MyShiftsPage />} />
          <Route path="availability" element={<AvailabilityPage />} />
          <Route path="timesheet" element={<TimesheetPage />} />
          <Route path="profile" element={<ProfilePage />} />
        </Route>

        <Route
          path="/manage"
          element={
            <RequireAuth>
              <RoleGate allow={['manager', 'admin']}>
                <ManagerLayout />
              </RoleGate>
            </RequireAuth>
          }
        >
          <Route index element={<Navigate to="dashboard" replace />} />
          <Route path="dashboard" element={<ManagerDashboardPage />} />
          <Route path="staffing" element={<StaffingBoardPage />} />
          <Route path="unfilled" element={<UnfilledShiftsPage />} />
          <Route path="roster" element={<RosterPage />} />
          <Route path="team-availability" element={<TeamAvailabilityPage />} />
          <Route path="timesheets" element={<TeamTimesheetsPage />} />
          <Route
            path="admin/locations"
            element={
              <RoleGate allow={['admin']}>
                <AdminLocationsPage />
              </RoleGate>
            }
          />
          <Route
            path="admin/users"
            element={
              <RoleGate allow={['admin']}>
                <AdminUsersPage />
              </RoleGate>
            }
          />
        </Route>

        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
      <Toaster />
    </BrowserRouter>
  );
}
