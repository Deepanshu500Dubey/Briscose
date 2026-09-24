export function StaffingGauge({ accepted, max }: { accepted: number; max: number }) {
  const pct = max > 0 ? Math.min(100, Math.round((accepted / max) * 100)) : 0;
  const color = accepted >= max ? 'bg-status-ok-fg' : accepted > 0 ? 'bg-status-warn-fg' : 'bg-line';

  return (
    <div className="w-32">
      <div className="mb-1 text-xs text-ink-soft">
        {accepted} / {max} staffed
      </div>
      <div className="h-1.5 overflow-hidden rounded-full bg-line">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}
