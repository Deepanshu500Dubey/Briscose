import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { EmptyState, ErrorState, SkeletonRows, StaleDataBanner } from './States';

describe('EmptyState', () => {
  it('renders the title without an action button when none is given', () => {
    render(<EmptyState title="No shifts yet" />);
    expect(screen.getByText('No shifts yet')).toBeInTheDocument();
    expect(screen.queryByRole('button')).not.toBeInTheDocument();
  });

  it('renders and wires up the optional action', () => {
    const onClick = vi.fn();
    render(<EmptyState title="No locations" action={{ label: 'Add location', onClick }} />);

    fireEvent.click(screen.getByRole('button', { name: 'Add location' }));
    expect(onClick).toHaveBeenCalledOnce();
  });
});

describe('ErrorState', () => {
  it('renders the message without a retry button when onRetry is omitted', () => {
    render(<ErrorState message="Something went wrong" />);
    expect(screen.getByText('Something went wrong')).toBeInTheDocument();
    expect(screen.queryByRole('button')).not.toBeInTheDocument();
  });

  it('wires up onRetry to the "Try again" button', () => {
    const onRetry = vi.fn();
    render(<ErrorState message="Failed to load" onRetry={onRetry} />);

    fireEvent.click(screen.getByRole('button', { name: 'Try again' }));
    expect(onRetry).toHaveBeenCalledOnce();
  });
});

describe('StaleDataBanner', () => {
  it('wires up onRetry to the "Retry" button', () => {
    const onRetry = vi.fn();
    render(<StaleDataBanner onRetry={onRetry} />);

    fireEvent.click(screen.getByRole('button', { name: 'Retry' }));
    expect(onRetry).toHaveBeenCalledOnce();
  });
});

describe('SkeletonRows', () => {
  it('renders the requested number of placeholder rows', () => {
    const { container } = render(<SkeletonRows count={5} />);
    expect(container.querySelectorAll('.animate-pulse')).toHaveLength(5);
  });

  it('defaults to 3 rows', () => {
    const { container } = render(<SkeletonRows />);
    expect(container.querySelectorAll('.animate-pulse')).toHaveLength(3);
  });
});
