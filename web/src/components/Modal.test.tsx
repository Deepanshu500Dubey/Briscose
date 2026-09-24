import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { Modal } from './Modal';

describe('Modal', () => {
  it('renders nothing when closed', () => {
    render(
      <Modal open={false} onOpenChange={() => {}} title="Assign employees">
        <p>Body</p>
      </Modal>,
    );
    expect(screen.queryByText('Assign employees')).not.toBeInTheDocument();
  });

  it('renders title, optional description, and children when open', () => {
    render(
      <Modal open onOpenChange={() => {}} title="Assign employees" description="Pick who covers this shift">
        <p>Body content</p>
      </Modal>,
    );
    expect(screen.getByRole('dialog', { name: 'Assign employees' })).toBeInTheDocument();
    expect(screen.getByText('Pick who covers this shift')).toBeInTheDocument();
    expect(screen.getByText('Body content')).toBeInTheDocument();
  });

  it('omits the description element when none is given', () => {
    render(
      <Modal open onOpenChange={() => {}} title="Create shift">
        <p>Body</p>
      </Modal>,
    );
    expect(screen.queryByText('Pick who covers this shift')).not.toBeInTheDocument();
  });

  it('calls onOpenChange(false) on Escape', () => {
    const onOpenChange = vi.fn();
    render(
      <Modal open onOpenChange={onOpenChange} title="Create shift">
        <p>Body</p>
      </Modal>,
    );

    fireEvent.keyDown(screen.getByRole('dialog'), { key: 'Escape' });

    expect(onOpenChange).toHaveBeenCalledWith(false);
  });
});
