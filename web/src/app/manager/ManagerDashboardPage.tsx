import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';

import { Card } from '@/components/Card';
import { ErrorState, Skeleton, StaleDataBanner } from '@/components/States';
import {
  useHoursByEmployee,
  useOfferOutcomes,
  useOvertime,
  useFillRateTrend,
  useShiftsByWeekday,
  useStaffingByLocation,
  useTodaySummary,
} from '@/features/dashboard/api';
import type {
  AssignmentStatusKey,
  ShiftStatusKey,
  TodaySummary,
} from '@/features/dashboard/api';

// ---------------------------------------------------------------------------
// Design tokens — hex values from tailwind.config.ts, used wherever
// Tailwind class names cannot reach (SVG attributes, Recharts props).
// ---------------------------------------------------------------------------

const C = {
  navy:      '#0B3D70',
  gold:      '#DD9200',
  okFg:      '#166B45',
  okBg:      '#E4F6EC',
  warnFg:    '#8A5300',
  warnBg:    '#FDF1DA',
  badFg:     '#9C2A34',
  badBg:     '#FBE9EA',
  infoFg:    '#1D4F8C',
  infoBg:    '#E9F0FB',
  inkSoft:   '#46536B',
  inkFaint:  '#6B7690',
  lineSoft:  '#EAEEF5',
  line:      '#DDE3EE',
  paper:     '#F4F6FA',
  ink:       '#10192B',
  white:     '#FFFFFF',
} as const;

// Tooltip / cartesian shared props — kept as a const so every chart is
// visually identical without repeating the same six lines.
const TOOLTIP_STYLE: React.CSSProperties = {
  borderRadius: '10px',
  border: `1px solid ${C.line}`,
  boxShadow: '0 1px 2px rgba(10,20,40,.04), 0 8px 24px -12px rgba(10,20,40,.12)',
  fontSize: 12,
  fontFamily: 'Public Sans, sans-serif',
  color: C.ink,
};
const TICK_X = { fontSize: 12, fill: C.inkSoft,  fontFamily: 'Public Sans, sans-serif' } as const;
const TICK_Y = { fontSize: 11, fill: C.inkFaint, fontFamily: 'Public Sans, sans-serif' } as const;
const LEGEND_STYLE: React.CSSProperties = {
  fontSize: 12,
  fontFamily: 'Public Sans, sans-serif',
  color: C.inkSoft,
};

// ---------------------------------------------------------------------------
// Shift-status colour + label maps (reused by staffing-by-location chart)
// ---------------------------------------------------------------------------

const SHIFT_STATUS_COLOURS: Record<ShiftStatusKey, string> = {
  confirmed:          C.okFg,
  pending_acceptance: C.infoFg,
  open:               C.warnFg,
  unfilled:           C.badFg,
  cancelled:          C.inkFaint,
};
const SHIFT_STATUS_LABELS: Record<ShiftStatusKey, string> = {
  confirmed:          'Confirmed',
  pending_acceptance: 'Pending acceptance',
  open:               'Open',
  unfilled:           'Unfilled',
  cancelled:          'Cancelled',
};
const SHIFT_STATUS_ORDER: ShiftStatusKey[] = [
  'confirmed', 'pending_acceptance', 'open', 'unfilled', 'cancelled',
];

// ---------------------------------------------------------------------------
// Assignment-status colours (offer-outcomes chart)
// ---------------------------------------------------------------------------

const ASSIGNMENT_COLOURS: Record<AssignmentStatusKey, string> = {
  accepted:  C.okFg,
  offered:   C.infoFg,
  rejected:  C.badFg,
  withdrawn: C.inkFaint,
};
const ASSIGNMENT_LABELS: Record<AssignmentStatusKey, string> = {
  accepted:  'Accepted',
  offered:   'Offered',
  rejected:  'Rejected',
  withdrawn: 'Withdrawn',
};
// Stack order: positive outcomes first
const ASSIGNMENT_ORDER: AssignmentStatusKey[] = [
  'accepted', 'offered', 'rejected', 'withdrawn',
];

// ---------------------------------------------------------------------------
// Shared primitives
// ---------------------------------------------------------------------------

function ChartSkeleton() {
  return <Skeleton className="h-[260px] w-full" />;
}

/** Title + sub-text header used inside every chart Card. */
function ChartHeader({ title, sub }: { title: string; sub: string }) {
  return (
    <div className="mb-4">
      <h2 className="font-display text-lg font-bold">{title}</h2>
      <p className="text-xs text-ink-soft">{sub}</p>
    </div>
  );
}

/** Centred soft message for empty data sets.
 * min-h matches ChartSkeleton so the card doesn't collapse when empty. */
function ChartEmpty({ message }: { message: string }) {
  return (
    <div className="flex min-h-[260px] items-center justify-center">
      <p className="text-sm text-ink-soft">{message}</p>
    </div>
  );
}

// ---------------------------------------------------------------------------
// 1. Staffing by location (grouped bars, one group per location)
// ---------------------------------------------------------------------------

function StaffingByLocationChart() {
  const { data, isLoading, isError, refetch } = useStaffingByLocation(7);

  if (isLoading) return <ChartSkeleton />;
  if (isError && !data)
    return <ErrorState message="Couldn't load staffing breakdown." onRetry={() => refetch()} />;
  if (!data || data.length === 0)
    return <ChartEmpty message="No shifts scheduled in the next 7 days." />;

  const chartData = data.map((row) => ({ name: row.location_name, ...row.by_status }));

  return (
    <>
      {isError && <StaleDataBanner onRetry={() => refetch()} />}
      <ResponsiveContainer width="100%" height={260}>
      <BarChart data={chartData} margin={{ top: 4, right: 8, left: -8, bottom: 0 }}
        barCategoryGap="28%" barGap={2}>
        <CartesianGrid vertical={false} stroke={C.lineSoft} />
        <XAxis dataKey="name" tick={TICK_X} axisLine={false} tickLine={false} />
        <YAxis allowDecimals={false} tick={TICK_Y} axisLine={false} tickLine={false} width={24} />
        <Tooltip cursor={{ fill: C.paper }} contentStyle={TOOLTIP_STYLE} />
        <Legend iconType="square" iconSize={10} wrapperStyle={LEGEND_STYLE}
          formatter={(v: string) => SHIFT_STATUS_LABELS[v as ShiftStatusKey] ?? v} />
        {SHIFT_STATUS_ORDER.map((s) => (
          <Bar key={s} dataKey={s} name={s} fill={SHIFT_STATUS_COLOURS[s]}
            radius={[3, 3, 0, 0]} maxBarSize={32} />
        ))}
      </BarChart>
      </ResponsiveContainer>
    </>
  );
}

// ---------------------------------------------------------------------------
// 2. Hours worked vs rostered by employee (grouped bars)
// ---------------------------------------------------------------------------

function HoursByEmployeeChart() {
  const { data, isLoading, isError, refetch } = useHoursByEmployee();

  if (isLoading) return <ChartSkeleton />;
  if (isError && !data)
    return <ErrorState message="Couldn't load hours breakdown." onRetry={() => refetch()} />;
  if (!data || data.length === 0)
    return <ChartEmpty message="No time entries or accepted shifts this week." />;

  // Use the local part of the email (before @) to keep X-axis labels readable.
  const chartData = data.map((row) => ({
    name: row.email.split('@')[0],
    Worked:   row.worked_hours,
    Rostered: row.rostered_hours,
  }));

  return (
    <>
      {isError && <StaleDataBanner onRetry={() => refetch()} />}
      <ResponsiveContainer width="100%" height={260}>
        <BarChart data={chartData} margin={{ top: 4, right: 8, left: -8, bottom: 0 }}
          barCategoryGap="30%" barGap={3}>
          <CartesianGrid vertical={false} stroke={C.lineSoft} />
          <XAxis dataKey="name" tick={TICK_X} axisLine={false} tickLine={false} />
          <YAxis allowDecimals={false} tick={TICK_Y} axisLine={false} tickLine={false}
            width={28} unit="h" />
          <Tooltip cursor={{ fill: C.paper }} contentStyle={TOOLTIP_STYLE}
            formatter={(v) => [`${Number(v)} h`, '']} />
          <Legend iconType="square" iconSize={10} wrapperStyle={LEGEND_STYLE} />
          <Bar dataKey="Worked"   fill={C.navy}   radius={[3, 3, 0, 0]} maxBarSize={28} />
          <Bar dataKey="Rostered" fill={C.inkFaint} radius={[3, 3, 0, 0]} maxBarSize={28} />
        </BarChart>
      </ResponsiveContainer>
    </>
  );
}

// ---------------------------------------------------------------------------
// 3. Shifts by weekday (single series — past 30 days)
// ---------------------------------------------------------------------------

function ShiftsByWeekdayChart() {
  const { data, isLoading, isError, refetch } = useShiftsByWeekday(30);

  if (isLoading) return <ChartSkeleton />;
  if (isError && !data)
    return <ErrorState message="Couldn't load weekday breakdown." onRetry={() => refetch()} />;
  // Backend always returns all 7 rows even with zero counts, so no empty guard needed.
  if (!data) return <ChartSkeleton />;

  const chartData = data.map((row) => ({
    name:  row.day_name.slice(0, 3), // Mon, Tue …
    count: row.count,
  }));

  return (
    <>
      {isError && <StaleDataBanner onRetry={() => refetch()} />}
      <ResponsiveContainer width="100%" height={260}>
        <BarChart data={chartData} margin={{ top: 4, right: 8, left: -8, bottom: 0 }}
          barCategoryGap="32%">
          <CartesianGrid vertical={false} stroke={C.lineSoft} />
          <XAxis dataKey="name" tick={TICK_X} axisLine={false} tickLine={false} />
          <YAxis allowDecimals={false} tick={TICK_Y} axisLine={false} tickLine={false} width={24} />
          <Tooltip cursor={{ fill: C.paper }} contentStyle={TOOLTIP_STYLE} />
          <Bar dataKey="count" name="Shifts" fill={C.navy} radius={[3, 3, 0, 0]} maxBarSize={40} />
        </BarChart>
      </ResponsiveContainer>
    </>
  );
}

// ---------------------------------------------------------------------------
// 4. Offer outcomes by week (stacked bars — last 8 weeks)
// ---------------------------------------------------------------------------

function OfferOutcomesChart() {
  const { data, isLoading, isError, refetch } = useOfferOutcomes(8);

  if (isLoading) return <ChartSkeleton />;
  if (isError && !data)
    return <ErrorState message="Couldn't load offer outcomes." onRetry={() => refetch()} />;
  if (!data || data.length === 0)
    return <ChartEmpty message="No assignment activity in the last 8 weeks." />;

  const chartData = data.map((row) => ({
    name: `W${row.iso_week}`,
    ...row.by_status,
  }));

  return (
    <>
      {isError && <StaleDataBanner onRetry={() => refetch()} />}
      <ResponsiveContainer width="100%" height={260}>
        <BarChart data={chartData} margin={{ top: 4, right: 8, left: -8, bottom: 0 }}
          barCategoryGap="28%" barSize={24}>
          <CartesianGrid vertical={false} stroke={C.lineSoft} />
          <XAxis dataKey="name" tick={TICK_X} axisLine={false} tickLine={false} />
          <YAxis allowDecimals={false} tick={TICK_Y} axisLine={false} tickLine={false} width={24} />
          <Tooltip cursor={{ fill: C.paper }} contentStyle={TOOLTIP_STYLE} />
          <Legend iconType="square" iconSize={10} wrapperStyle={LEGEND_STYLE}
            formatter={(v: string) => ASSIGNMENT_LABELS[v as AssignmentStatusKey] ?? v} />
          {ASSIGNMENT_ORDER.map((s) => (
            <Bar key={s} dataKey={s} name={s} stackId="a"
              fill={ASSIGNMENT_COLOURS[s]}
              // Only round the top corners of the topmost bar in the stack.
              radius={s === 'withdrawn' ? [3, 3, 0, 0] : [0, 0, 0, 0]}
            />
          ))}
        </BarChart>
      </ResponsiveContainer>
    </>
  );
}

// ---------------------------------------------------------------------------
// 5. Overtime by employee — sorted single series, over-threshold cells red
// ---------------------------------------------------------------------------

function OvertimeChart() {
  const { data, isLoading, isError, refetch } = useOvertime();

  if (isLoading) return <ChartSkeleton />;
  if (isError && !data)
    return <ErrorState message="Couldn't load overtime data." onRetry={() => refetch()} />;
  if (!data || data.length === 0)
    return <ChartEmpty message="No closed time entries this week." />;

  const threshold = data[0]?.overtime_threshold ?? 40;

  // Backend already returns rows sorted desc by total_hours.
  const chartData = data.map((row) => ({
    name:  row.email.split('@')[0],
    hours: row.total_hours,
    over:  row.over_weekly_limit,
  }));

  return (
    <>
      {isError && <StaleDataBanner onRetry={() => refetch()} />}
      <ResponsiveContainer width="100%" height={260}>
        <BarChart data={chartData} margin={{ top: 4, right: 8, left: -8, bottom: 0 }}
          barCategoryGap="32%">
          <CartesianGrid vertical={false} stroke={C.lineSoft} />
          <XAxis dataKey="name" tick={TICK_X} axisLine={false} tickLine={false} />
          <YAxis allowDecimals={false} tick={TICK_Y} axisLine={false} tickLine={false}
            width={28} unit="h" />
          <Tooltip cursor={{ fill: C.paper }} contentStyle={TOOLTIP_STYLE}
            formatter={(v) => [`${Number(v)} h`, 'Worked']} />
          {/* Dashed reference line at the overtime threshold */}
          <ReferenceLine y={threshold} stroke={C.badFg} strokeDasharray="4 3"
            label={{ value: `${threshold} h`, position: 'insideTopRight',
              fontSize: 10, fill: C.badFg, fontFamily: 'Public Sans, sans-serif' }} />
          <Bar dataKey="hours" name="Worked hours" radius={[3, 3, 0, 0]} maxBarSize={36}>
            {chartData.map((entry, i) => (
              <Cell key={i} fill={entry.over ? C.badFg : C.navy} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </>
  );
}

// ---------------------------------------------------------------------------
// 6. Fill-rate trend — % confirmed per ISO week
// ---------------------------------------------------------------------------

function FillRateTrendChart() {
  const { data, isLoading, isError, refetch } = useFillRateTrend(8);

  if (isLoading) return <ChartSkeleton />;
  if (isError && !data)
    return <ErrorState message="Couldn't load fill-rate trend." onRetry={() => refetch()} />;
  if (!data || data.length === 0)
    return <ChartEmpty message="No shift history in the last 8 weeks." />;

  const chartData = data.map((row) => ({
    name: `W${row.iso_week}`,
    pct:  row.fill_rate_pct,
  }));

  return (
    <>
      {isError && <StaleDataBanner onRetry={() => refetch()} />}
      <ResponsiveContainer width="100%" height={260}>
        <BarChart data={chartData} margin={{ top: 4, right: 8, left: -8, bottom: 0 }}
          barCategoryGap="32%" barSize={28}>
          <CartesianGrid vertical={false} stroke={C.lineSoft} />
          <XAxis dataKey="name" tick={TICK_X} axisLine={false} tickLine={false} />
          <YAxis domain={[0, 100]} tick={TICK_Y} axisLine={false} tickLine={false}
            width={32} unit="%" />
          <Tooltip cursor={{ fill: C.paper }} contentStyle={TOOLTIP_STYLE}
            formatter={(v) => [`${Number(v)}%`, 'Fill rate']} />
          {/* Colour each bar by fill-rate band */}
          <Bar dataKey="pct" name="Fill rate" radius={[3, 3, 0, 0]}>
            {chartData.map((entry, i) => (
              <Cell
                key={i}
                fill={
                  entry.pct >= 80 ? C.okFg
                  : entry.pct >= 50 ? C.warnFg
                  : C.badFg
                }
              />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </>
  );
}

// ---------------------------------------------------------------------------
// Stat tile (KPI strip)
// ---------------------------------------------------------------------------

interface StatTileProps {
  label: string;
  value: number;
  valueClassName?: string;
  sub?: string;
}

function StatTile({ label, value, valueClassName = '', sub }: StatTileProps) {
  return (
    <Card className="flex flex-col gap-1 min-w-0">
      <p className="text-xs font-semibold uppercase tracking-wide text-ink-soft">{label}</p>
      <p className={`font-display text-4xl font-extrabold leading-none ${valueClassName}`}>
        {value}
      </p>
      {sub && <p className="text-xs text-ink-faint">{sub}</p>}
    </Card>
  );
}

function SkeletonTile() {
  return (
    <Card className="flex flex-col gap-2 min-w-0">
      <Skeleton className="h-3 w-24" />
      <Skeleton className="h-10 w-14" />
    </Card>
  );
}

// ---------------------------------------------------------------------------
// KPI tile definitions
// ---------------------------------------------------------------------------

interface TileSpec {
  key: keyof TodaySummary;
  label: string;
  sub: string;
  colour: (n: number) => string;
}

const TILES: TileSpec[] = [
  {
    key: 'shifts_today',
    label: 'Shifts today',
    sub: 'All statuses',
    colour: () => 'text-ink',
  },
  {
    key: 'open_shifts_today',
    label: 'Open shifts',
    sub: 'Need staffing',
    colour: (n) => (n > 0 ? 'text-status-warn-fg' : 'text-status-ok-fg'),
  },
  {
    key: 'pending_offers',
    label: 'Pending offers',
    sub: 'Awaiting employee response',
    colour: (n) => (n > 0 ? 'text-status-warn-fg' : 'text-ink'),
  },
  {
    key: 'clocked_in_now',
    label: 'Clocked in now',
    sub: 'Active time entries',
    colour: (n) => (n > 0 ? 'text-status-ok-fg' : 'text-ink'),
  },
  {
    key: 'rostered_now',
    label: 'Rostered now',
    sub: 'Accepted & on shift',
    colour: (n) => (n > 0 ? 'text-brand-navy' : 'text-ink'),
  },
];

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export function ManagerDashboardPage() {
  const { data, isLoading, isError, refetch } = useTodaySummary();

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="font-display text-2xl font-bold">Dashboard</h1>
        <p className="mt-0.5 text-sm text-ink-soft">
          Live snapshot for today across your locations
        </p>
      </div>

      {/* KPI strip */}
      {isError && !data ? (
        <ErrorState message="Couldn't load today's summary." onRetry={() => refetch()} />
      ) : (
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-5">
          {isLoading
            ? Array.from({ length: TILES.length }, (_, i) => <SkeletonTile key={i} />)
            : TILES.map((spec) => (
                <StatTile
                  key={spec.key}
                  label={spec.label}
                  value={data![spec.key]}
                  valueClassName={spec.colour(data![spec.key])}
                  sub={spec.sub}
                />
              ))}
        </div>
      )}

      {/* Chart grid — 2 columns on large screens, 1 on mobile */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">

        <Card>
          <ChartHeader title="Shifts by location" sub="Next 7 days · grouped by status" />
          <StaffingByLocationChart />
        </Card>

        <Card>
          <ChartHeader title="Hours: worked vs rostered" sub="Current week · per employee" />
          <HoursByEmployeeChart />
        </Card>

        <Card>
          <ChartHeader title="Shifts by weekday" sub="Past 30 days · shift volume pattern" />
          <ShiftsByWeekdayChart />
        </Card>

        <Card>
          <ChartHeader title="Offer outcomes" sub="Last 8 weeks · stacked by status" />
          <OfferOutcomesChart />
        </Card>

        <Card>
          <ChartHeader title="Weekly overtime" sub="Current week · hours worked, threshold 40 h" />
          <OvertimeChart />
        </Card>

        <Card>
          <ChartHeader title="Fill-rate trend" sub="Last 8 weeks · % of shifts confirmed" />
          <FillRateTrendChart />
        </Card>

      </div>
    </div>
  );
}
