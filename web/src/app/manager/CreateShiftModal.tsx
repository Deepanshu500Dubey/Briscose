import { zodResolver } from '@hookform/resolvers/zod';
import type { ReactNode } from 'react';
import { useForm } from 'react-hook-form';
import { z } from 'zod';

import { Button } from '@/components/Button';
import { Modal } from '@/components/Modal';
import { useCreateShift } from '@/features/shifts/api';
import { toastError, toastSuccess } from '@/stores/toast';

const shiftSchema = z
  .object({
    date: z.string().min(1, 'Required'),
    start_time: z.string().min(1, 'Required'),
    end_time: z.string().min(1, 'Required'),
    min_staff: z.coerce.number().int().min(1),
    max_staff: z.coerce.number().int().min(1),
  })
  .refine((v) => v.start_time < v.end_time, {
    message: 'Start time must be before end time',
    path: ['end_time'],
  })
  .refine((v) => v.min_staff <= v.max_staff, {
    message: 'Minimum staff must be ≤ maximum staff',
    path: ['max_staff'],
  });

type ShiftForm = z.infer<typeof shiftSchema>;

export function CreateShiftModal({
  open,
  onOpenChange,
  locationId,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  locationId: string;
}) {
  const createShift = useCreateShift();
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<ShiftForm>({
    resolver: zodResolver(shiftSchema),
    defaultValues: { min_staff: 3, max_staff: 5 },
  });

  const onSubmit = handleSubmit(async (values) => {
    try {
      await createShift.mutateAsync({
        location_id: locationId,
        date: values.date,
        start_time: `${values.start_time}:00`,
        end_time: `${values.end_time}:00`,
        min_staff: values.min_staff,
        max_staff: values.max_staff,
      });
      toastSuccess('Shift created');
      reset();
      onOpenChange(false);
    } catch (error) {
      toastError(error instanceof Error ? error.message : 'Could not create shift');
    }
  });

  return (
    <Modal open={open} onOpenChange={onOpenChange} title="Create shift">
      <form onSubmit={onSubmit} className="flex flex-col gap-3" noValidate>
        <Field label="Date" error={errors.date?.message}>
          <input type="date" className="input" {...register('date')} />
        </Field>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Start time" error={errors.start_time?.message}>
            <input type="time" className="input" {...register('start_time')} />
          </Field>
          <Field label="End time" error={errors.end_time?.message}>
            <input type="time" className="input" {...register('end_time')} />
          </Field>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Min staff" error={errors.min_staff?.message}>
            <input type="number" min={1} className="input" {...register('min_staff')} />
          </Field>
          <Field label="Max staff" error={errors.max_staff?.message}>
            <input type="number" min={1} className="input" {...register('max_staff')} />
          </Field>
        </div>

        <Button type="submit" disabled={createShift.isPending} className="mt-2">
          {createShift.isPending ? 'Creating…' : 'Create shift'}
        </Button>
      </form>
    </Modal>
  );
}

function Field({
  label,
  error,
  children,
}: {
  label: string;
  error?: string;
  children: ReactNode;
}) {
  return (
    <label className="flex flex-col gap-1 text-sm">
      <span className="font-semibold text-ink-soft">{label}</span>
      {children}
      {error && <span className="text-xs text-status-bad-fg">{error}</span>}
    </label>
  );
}
