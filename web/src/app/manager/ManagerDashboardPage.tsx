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
import { Link } from 'react-router-dom';

import {
  useAttention,
  useHoursByEmployee,
  useOfferOutcomes,
  useFillRateTrend,
  useStaffingByLocation,
  useTodaySummary,
} from '@/features/dashboard/api';
import { useLocations } from '@/features/locations/api';
import type {
  AttentionItem,
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

const OVERTIME_THRESHOLD = 40;

function HoursByEmployeeChart() {
  const { data, isLoading, isError, refetch } = useHoursByEmployee();

  if (isLoading) return <ChartSkeleton />;
  if (isError && !data)
    return <ErrorState message="Couldn't load hours breakdown." onRetry={() => refetch()} />;
  if (!data || data.length === 0)
    return <ChartEmpty message="No time entries or accepted shifts this week." />;

  // Use the local part of the email (before @) to keep X-axis labels readable.
  const chartData = data.map((row) => ({
    name:     row.email.split('@')[0],
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
          {/* Dashed overtime threshold — matches the removed OvertimeChart */}
          <ReferenceLine y={OVERTIME_THRESHOLD} stroke={C.badFg} strokeDasharray="4 3"
            label={{ value: `${OVERTIME_THRESHOLD} h`, position: 'insideTopRight',
              fontSize: 10, fill: C.badFg, fontFamily: 'Public Sans, sans-serif' }} />
          <Bar dataKey="Worked" radius={[3, 3, 0, 0]} maxBarSize={28}>
            {chartData.map((entry, i) => (
              <Cell key={i} fill={entry.Worked > OVERTIME_THRESHOLD ? C.badFg : C.navy} />
            ))}
          </Bar>
          <Bar dataKey="Rostered" fill={C.inkFaint} radius={[3, 3, 0, 0]} maxBarSize={28} />
        </BarChart>
      </ResponsiveContainer>
    </>
  );
}

// ---------------------------------------------------------------------------
// 3. Offer outcomes by week (stacked bars — last 8 weeks)
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
// 5. Fill-rate trend — % confirmed per ISO week
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

// "3 / 4" tile — clocked in vs rostered, warning when under-staffed.
function OnShiftTile({ clockedIn, rostered }: { clockedIn: number; rostered: number }) {
  const valueClass =
    clockedIn < rostered ? 'text-status-warn-fg' : 'text-status-ok-fg';
  return (
    <Card className="flex flex-col gap-1 min-w-0">
      <p className="text-xs font-semibold uppercase tracking-wide text-ink-soft">On shift</p>
      <p className={`font-display text-4xl font-extrabold leading-none ${valueClass}`}>
        {clockedIn}{' '}
        <span className="text-2xl font-bold text-ink-faint">/</span>{' '}
        {rostered}
      </p>
      <p className="text-xs text-ink-faint">Clocked in / rostered</p>
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

// shifts_today removed; clocked_in_now + rostered_now merged into OnShiftTile.
const TILES: TileSpec[] = [
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
];

// ---------------------------------------------------------------------------
// Needs-attention card
// ---------------------------------------------------------------------------

const ATTENTION_META: Record<
  AttentionItem['type'],
  { linkTo: string; linkLabel: string; dot: string }
> = {
  open_or_understaffed:    { linkTo: '/manage/staffing',   linkLabel: 'View board',     dot: C.badFg  },
  offer_pending_long:      { linkTo: '/manage/staffing',   linkLabel: 'View board',     dot: C.warnFg },
  rostered_not_clocked_in: { linkTo: '/manage/timesheets', linkLabel: 'View timesheets', dot: C.warnFg },
};

function AttentionCard() {
  const { data, isLoading, isError, refetch } = useAttention();

  if (isLoading) {
    return (
      <Card>
        <div className="mb-3 flex items-center justify-between">
          <Skeleton className="h-4 w-36" />
          <Skeleton className="h-3 w-20" />
        </div>
        {[0, 1, 2].map((i) => (
          <div key={i} className="flex items-center gap-3 py-2.5 border-b border-line-soft last:border-none">
            <Skeleton className="h-2 w-2 shrink-0 rounded-full" />
            <Skeleton className="h-3 flex-1" />
            <Skeleton className="h-3 w-16" />
          </div>
        ))}
      </Card>
    );
  }

  if (isError && !data) {
    return (
      <Card>
        <ErrorState message="Couldn't load attention items." onRetry={() => refetch()} />
      </Card>
    );
  }

  return (
    <Card>
      <div className="mb-3 flex items-center justify-between">
        <h2 className="font-display text-lg font-bold">Needs attention</h2>
        {data && data.length > 0 && (
          <span className="rounded-full border border-status-bad-line bg-status-bad-bg px-2.5 py-0.5 font-display text-xs font-semibold uppercase tracking-wide text-status-bad-fg">
            {data.length} item{data.length !== 1 ? 's' : ''}
          </span>
        )}
      </div>

      {!data || data.length === 0 ? (
        /* All-clear state */
        <div className="flex items-center gap-2.5 rounded-lg bg-status-ok-bg px-4 py-3">
          <span
            className="h-2 w-2 shrink-0 rounded-full"
            style={{ background: C.okFg }}
          />
          <p className="text-sm font-semibold text-status-ok-fg">All clear — nothing needs attention right now</p>
        </div>
      ) : (
        <ul className="divide-y divide-line-soft">
          {data.map((item, i) => {
            const { linkTo, linkLabel, dot } = ATTENTION_META[item.type];
            return (
              <li key={i} className="flex items-center gap-3 py-2.5">
                {/* Status dot */}
                <span
                  className="h-2 w-2 shrink-0 rounded-full"
                  style={{ background: dot }}
                />
                {/* Label */}
                <p className="flex-1 text-sm text-ink">{item.label}</p>
                {/* Link */}
                <Link
                  to={linkTo}
                  className="shrink-0 text-xs font-semibold text-brand-navy underline-offset-2 hover:underline"
                >
                  {linkLabel}
                </Link>
              </li>
            );
          })}
        </ul>
      )}
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export function ManagerDashboardPage() {
  const { data, isLoading, isError, refetch } = useTodaySummary();
  const { data: locations } = useLocations();
  const multiLocation = (locations?.length ?? 0) > 1;

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="font-display text-2xl font-bold">Dashboard</h1>
        <p className="mt-0.5 text-sm text-ink-soft">
          Live snapshot for today across your locations
        </p>
      </div>

      <AttentionCard />

      {/* KPI strip */}
      {isError && !data ? (
        <ErrorState message="Couldn't load today's summary." onRetry={() => refetch()} />
      ) : (
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-3">
          {isLoading ? (
            Array.from({ length: 3 }, (_, i) => <SkeletonTile key={i} />)
          ) : (
            <>
              {TILES.map((spec) => (
                <StatTile
                  key={spec.key}
                  label={spec.label}
                  value={data![spec.key]}
                  valueClassName={spec.colour(data![spec.key])}
                  sub={spec.sub}
                />
              ))}
              <OnShiftTile
                clockedIn={data!.clocked_in_now}
                rostered={data!.rostered_now}
              />
            </>
          )}
        </div>
      )}

      {/* Chart grid — 2 columns on large screens, 1 on mobile */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">

        {multiLocation && (
          <Card>
            <ChartHeader title="Shifts by location" sub="Next 7 days · grouped by status" />
            <StaffingByLocationChart />
          </Card>
        )}

        <Card className={multiLocation ? '' : 'lg:col-span-2'}>
          <ChartHeader title="Hours: worked vs rostered" sub="Current week · per employee" />
          <HoursByEmployeeChart />
        </Card>

        <Card className="lg:col-span-2">
          <ChartHeader title="Offer outcomes" sub="Last 8 weeks · stacked by status" />
          <OfferOutcomesChart />
        </Card>

        <Card>
          <ChartHeader title="Fill-rate trend" sub="Last 8 weeks · % of shifts confirmed" />
          <FillRateTrendChart />
        </Card>

      </div>
    </div>
  );
}
