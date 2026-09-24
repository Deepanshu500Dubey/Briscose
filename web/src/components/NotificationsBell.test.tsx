import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import type { ReactNode } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { api } from '@/lib/apiClient';
import type { NotificationResponse } from '@/types/api';

import { NotificationsBell } from './NotificationsBell';

vi.mock('@/lib/apiClient', () => ({
  api: { get: vi.fn(), patch: vi.fn() },
}));

function renderWithClient(children: ReactNode) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(<QueryClientProvider client={queryClient}>{children}</QueryClientProvider>);
}

const notification = (overrides: Partial<NotificationResponse> = {}): NotificationResponse =>
  ({
    id: 'n1',
    type: 'offer',
    is_read: false,
    created_at: '2026-08-27T00:00:00Z',
    ...overrides,
  }) as NotificationResponse;

describe('NotificationsBell', () => {
  beforeEach(() => {
    vi.mocked(api.get).mockReset();
    vi.mocked(api.patch).mockReset();
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it('shows no unread badge and "All caught up" with an empty list', async () => {
    vi.mocked(api.get).mockResolvedValue([]);
    renderWithClient(<NotificationsBell />);

    await userEvent.click(screen.getByRole('button', { name: 'Notifications' }));

    expect(await screen.findByText('All caught up')).toBeInTheDocument();
    expect(screen.queryByText(/^\d+$/)).not.toBeInTheDocument();
  });

  it('shows the unread count badge and only that many items marked unread', async () => {
    vi.mocked(api.get).mockResolvedValue([
      notification({ id: 'n1', is_read: false, type: 'offer' }),
      notification({ id: 'n2', is_read: true, type: 'confirmed' }),
    ]);
    renderWithClient(<NotificationsBell />);

    await waitFor(() => expect(screen.getByText('1')).toBeInTheDocument());
  });

  it('maps known notification types to friendly labels', async () => {
    vi.mocked(api.get).mockResolvedValue([notification({ type: 'shift_unfilled' })]);
    renderWithClient(<NotificationsBell />);

    await userEvent.click(screen.getByRole('button', { name: 'Notifications' }));

    expect(await screen.findByText('Shift unfilled')).toBeInTheDocument();
  });

  it('falls back to the raw type string for an unrecognized notification type', async () => {
    vi.mocked(api.get).mockResolvedValue([notification({ type: 'some_future_type' as never })]);
    renderWithClient(<NotificationsBell />);

    await userEvent.click(screen.getByRole('button', { name: 'Notifications' }));

    expect(await screen.findByText('some_future_type')).toBeInTheDocument();
  });

  it('marks an unread notification read on click, but does not re-fire for an already-read one', async () => {
    vi.mocked(api.get).mockResolvedValue([notification({ id: 'n1', is_read: false })]);
    vi.mocked(api.patch).mockResolvedValue(notification({ id: 'n1', is_read: true }));
    renderWithClient(<NotificationsBell />);

    await userEvent.click(screen.getByRole('button', { name: 'Notifications' }));
    const item = await screen.findByText('New shift offer');
    await userEvent.click(item);

    await waitFor(() => expect(api.patch).toHaveBeenCalledWith('/notifications/n1/read'));
  });
});
