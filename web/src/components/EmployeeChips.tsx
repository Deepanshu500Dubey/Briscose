import type { AssignedEmployee } from '@/types/api';

export function EmployeeChips({ employees }: { employees: AssignedEmployee[] }) {
  if (employees.length === 0) {
    return <span className="text-xs text-ink-faint">—</span>;
  }
  return (
    <div className="flex flex-wrap gap-1">
      {employees.map((employee) => (
        <span
          key={employee.id}
          className="rounded-full border border-line bg-line-soft px-2 py-0.5 text-xs font-medium text-ink-soft"
        >
          {employee.email}
        </span>
      ))}
    </div>
  );
}
