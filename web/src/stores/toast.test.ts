import { beforeEach, describe, expect, it } from 'vitest';

import { toastError, toastSuccess, useToastStore } from './toast';

describe('useToastStore', () => {
  beforeEach(() => {
    useToastStore.setState({ toasts: [] });
  });

  it('starts empty', () => {
    expect(useToastStore.getState().toasts).toEqual([]);
  });

  it('push appends a toast with a unique id and the given tone', () => {
    useToastStore.getState().push('Saved', 'success');
    const [toast] = useToastStore.getState().toasts;
    expect(toast.title).toBe('Saved');
    expect(toast.tone).toBe('success');
    expect(toast.id).toEqual(expect.any(Number));
  });

  it('assigns increasing ids across pushes, even across store instances', () => {
    useToastStore.getState().push('First', 'success');
    useToastStore.getState().push('Second', 'error');
    const [first, second] = useToastStore.getState().toasts;
    expect(second.id).toBeGreaterThan(first.id);
  });

  it('dismiss removes only the matching toast', () => {
    useToastStore.getState().push('Keep me', 'success');
    useToastStore.getState().push('Remove me', 'error');
    const [keep, remove] = useToastStore.getState().toasts;

    useToastStore.getState().dismiss(remove.id);

    const remaining = useToastStore.getState().toasts;
    expect(remaining).toHaveLength(1);
    expect(remaining[0].id).toBe(keep.id);
  });

  it('toastSuccess / toastError push onto the shared store with the right tone', () => {
    toastSuccess('It worked');
    toastError('It broke');

    const toasts = useToastStore.getState().toasts;
    expect(toasts).toHaveLength(2);
    expect(toasts[0]).toMatchObject({ title: 'It worked', tone: 'success' });
    expect(toasts[1]).toMatchObject({ title: 'It broke', tone: 'error' });
  });
});
