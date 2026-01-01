import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import PageHeader from '@/components/PageHeader';
import { api, UsageResponse, UsageTopUser } from '@/lib/api';
import {
  Area,
  AreaChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';

const RANGE_PRESETS = [
  { key: '24h', label: '24H', minutes: 1440 },
  { key: '7d', label: '7D', minutes: 10080 },
  { key: '30d', label: '30D', minutes: 43200 },
  { key: '90d', label: '90D', minutes: 129600 },
];

const numberFormatter = new Intl.NumberFormat('en-US');
const compactFormatter = new Intl.NumberFormat('en-US', { notation: 'compact' });

export default function DashboardPage() {
  const [usage, setUsage] = useState<UsageResponse | null>(null);
  const [topUsers, setTopUsers] = useState<UsageTopUser[]>([]);
  const [rangePreset, setRangePreset] = useState('7d');
  const [isLoading, setIsLoading] = useState(false);

  const range = useMemo(() => {
    const preset = RANGE_PRESETS.find((item) => item.key === rangePreset);
    if (!preset) return null;
    const end = new Date();
    const start = new Date(end.getTime() - preset.minutes * 60 * 1000);
    return { start, end, label: preset.label };
  }, [rangePreset]);

  const bucketType = useMemo(() => {
    if (!range) return 'hour';
    const hours = (range.end.getTime() - range.start.getTime()) / (60 * 60 * 1000);
    if (hours <= 6) return 'minute';
    if (hours <= 48) return 'hour';
    if (hours <= 24 * 21) return 'day';
    return 'week';
  }, [range]);

  useEffect(() => {
    if (!range) return;
    let active = true;
    setIsLoading(true);

    const params = {
      bucket_type: bucketType,
      start_time: range.start.toISOString(),
      end_time: range.end.toISOString(),
    };

    Promise.all([api.getUsage(params), api.getTopUsers({ ...params, limit: 6 })])
      .then(([usageResponse, topUsersResponse]) => {
        if (!active) return;
        setUsage(usageResponse);
        setTopUsers(topUsersResponse);
      })
      .catch(() => {
        if (!active) return;
        setUsage(null);
        setTopUsers([]);
      })
      .finally(() => {
        if (active) setIsLoading(false);
      });

    return () => {
      active = false;
    };
  }, [bucketType, range]);

  const chartData =
    usage?.buckets.map((bucket) => ({
      time: formatTimestamp(bucket.bucket_start),
      totalTokens: bucket.total_tokens,
      inputTokens: bucket.input_tokens,
      outputTokens: bucket.output_tokens,
      requests: bucket.requests,
    })) || [];

  const cumulativeData = useMemo(() => {
    if (!usage) return [];
    let runningTotal = 0;
    return usage.buckets.map((bucket) => {
      runningTotal += bucket.total_tokens;
      return {
        time: formatTimestamp(bucket.bucket_start),
        cumulativeTokens: runningTotal,
      };
    });
  }, [usage]);

  const totalTokens = usage?.total_tokens ?? 0;
  const tokensPerRequest =
    usage && usage.total_requests > 0 ? usage.total_tokens / usage.total_requests : 0;
  const outputInputRatio =
    usage && usage.total_input_tokens > 0
      ? usage.total_output_tokens / usage.total_input_tokens
      : 0;
  const topUser = topUsers[0];
  const topUserShare =
    usage && totalTokens > 0 && topUser ? topUser.total_tokens / totalTokens : 0;
  const topUserMaxTokens = Math.max(...topUsers.map((user) => user.total_tokens), 1);

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="Overview"
        title="Token Overview"
        subtitle="Monitor token throughput, cumulative burn, and user concentration in one view."
        actions={
          <>
            <div className="inline-flex flex-wrap rounded-full border border-line bg-surface p-1 shadow-soft">
              {RANGE_PRESETS.map((preset) => (
                <button
                  key={preset.key}
                  type="button"
                  onClick={() => setRangePreset(preset.key)}
                  className={[
                    'rounded-full px-4 py-1.5 text-sm font-semibold transition',
                    rangePreset === preset.key
                      ? 'bg-accent text-white shadow-soft'
                      : 'text-muted hover:text-ink hover:bg-surface-2',
                  ].join(' ')}
                >
                  {preset.label}
                </button>
              ))}
            </div>
            <Link
              to="/users"
              className="rounded-full border border-line px-4 py-2 text-sm font-semibold text-ink transition hover:bg-surface-2"
            >
              Users
            </Link>
          </>
        }
      />

      {range && (
        <div className="flex flex-wrap items-center justify-between gap-3 text-xs text-muted">
          <div>
            Range: {range.label} - {formatDate(range.start)} - {formatDate(range.end)}
          </div>
          <div>Bucket: {bucketType}</div>
        </div>
      )}

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        <StatCard label="Total Tokens" value={formatNumber(totalTokens)} />
        <StatCard label="Input Tokens" value={formatNumber(usage?.total_input_tokens ?? 0)} />
        <StatCard label="Output Tokens" value={formatNumber(usage?.total_output_tokens ?? 0)} />
        <StatCard label="Requests" value={formatNumber(usage?.total_requests ?? 0)} />
        <StatCard
          label="Tokens / Request"
          value={formatNumber(Math.round(tokensPerRequest))}
          note={`Output/Input ${outputInputRatio.toFixed(2)}x`}
        />
        <StatCard
          label="Top User Share"
          value={formatPercent(topUserShare)}
          note={topUser ? topUser.name : 'No top user yet'}
        />
      </div>

      {isLoading && (
        <div className="rounded-2xl border border-line bg-surface p-8 text-sm text-muted">
          Loading usage data...
        </div>
      )}

      {!isLoading && !usage && (
        <div className="rounded-2xl border border-line bg-surface p-8 text-sm text-muted">
          No usage data available yet. Metrics will populate as traffic flows through the proxy.
        </div>
      )}

      {!isLoading && usage && (
        <div className="grid gap-6 lg:grid-cols-[minmax(0,2.2fr)_minmax(0,1fr)]">
          <div className="rounded-2xl border border-line bg-surface p-6 shadow-soft">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-lg font-semibold text-ink">Token Throughput</h2>
                <p className="text-xs text-muted">Input vs output tokens by bucket.</p>
              </div>
              <div className="text-xs text-muted">{chartData.length} points</div>
            </div>
            <div className="mt-6 h-72">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={chartData}>
                  <defs>
                    <linearGradient id="inputGradient" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#2563eb" stopOpacity={0.32} />
                      <stop offset="100%" stopColor="#2563eb" stopOpacity={0} />
                    </linearGradient>
                    <linearGradient id="outputGradient" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#0ea5e9" stopOpacity={0.28} />
                      <stop offset="100%" stopColor="#0ea5e9" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(148, 163, 184, 0.4)" />
                  <XAxis dataKey="time" tick={{ fill: '#94a3b8', fontSize: 12 }} />
                  <YAxis tick={{ fill: '#94a3b8', fontSize: 12 }} />
                  <Tooltip contentStyle={{ borderRadius: 12, borderColor: '#e2e8f0' }} />
                  <Area
                    type="monotone"
                    dataKey="inputTokens"
                    stroke="#2563eb"
                    fill="url(#inputGradient)"
                    strokeWidth={2}
                  />
                  <Area
                    type="monotone"
                    dataKey="outputTokens"
                    stroke="#0ea5e9"
                    fill="url(#outputGradient)"
                    strokeWidth={2}
                  />
                  <Line type="monotone" dataKey="requests" stroke="#0f172a" strokeWidth={1.5} />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </div>

          <div className="rounded-2xl border border-line bg-surface p-6 shadow-soft">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-lg font-semibold text-ink">Top Users</h2>
                <p className="text-xs text-muted">Token share by user.</p>
              </div>
            </div>
            <div className="mt-6 space-y-4">
              {topUsers.length === 0 && (
                <div className="rounded-xl border border-line bg-surface-2 px-4 py-3 text-sm text-muted">
                  No usage data in this range.
                </div>
              )}
              {topUsers.map((user) => (
                <Link
                  key={user.user_id}
                  to={`/users/${user.user_id}`}
                  className="block rounded-xl border border-transparent px-2 py-2 transition hover:border-line hover:bg-surface-2"
                >
                  <div className="flex items-center justify-between text-sm font-semibold text-ink">
                    <span>{user.name}</span>
                    <span>{formatCompact(user.total_tokens)}</span>
                  </div>
                  <div className="mt-2 h-2 rounded-full bg-surface-2">
                    <div
                      className="h-2 rounded-full bg-accent"
                      style={{ width: `${(user.total_tokens / topUserMaxTokens) * 100}%` }}
                    />
                  </div>
                  <div className="mt-2 text-xs text-muted">
                    {formatNumber(user.total_requests)} requests
                  </div>
                </Link>
              ))}
            </div>
          </div>
        </div>
      )}

      {!isLoading && usage && (
        <div className="grid gap-6 lg:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
          <div className="rounded-2xl border border-line bg-surface p-6 shadow-soft">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-lg font-semibold text-ink">Cumulative Tokens</h2>
                <p className="text-xs text-muted">Total tokens consumed over the selected range.</p>
              </div>
            </div>
            <div className="mt-6 h-64">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={cumulativeData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(148, 163, 184, 0.4)" />
                  <XAxis dataKey="time" tick={{ fill: '#94a3b8', fontSize: 12 }} />
                  <YAxis tick={{ fill: '#94a3b8', fontSize: 12 }} />
                  <Tooltip contentStyle={{ borderRadius: 12, borderColor: '#e2e8f0' }} />
                  <Line type="monotone" dataKey="cumulativeTokens" stroke="#1d4ed8" strokeWidth={2} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>

          <div className="rounded-2xl border border-line bg-surface p-6 shadow-soft">
            <h2 className="text-lg font-semibold text-ink">Focus</h2>
            <div className="mt-4 space-y-4 text-sm text-muted">
              <div>
                <div className="text-xs uppercase tracking-[0.28em] text-muted">Efficiency</div>
                <div className="mt-2 text-sm text-ink">
                  {formatNumber(Math.round(tokensPerRequest))} tokens/request
                </div>
                <div className="text-xs text-muted">
                  Output/Input ratio {outputInputRatio.toFixed(2)}x
                </div>
              </div>
              <div>
                <div className="text-xs uppercase tracking-[0.28em] text-muted">Concentration</div>
                <div className="mt-2 text-sm text-ink">
                  {formatPercent(topUserShare)} owned by {topUser?.name || 'top user'}
                </div>
                <div className="text-xs text-muted">Track heavy consumers weekly.</div>
              </div>
              <div>
                <div className="text-xs uppercase tracking-[0.28em] text-muted">Throughput</div>
                <div className="mt-2 text-sm text-ink">
                  {formatNumber(usage.total_requests)} requests in range
                </div>
                <div className="text-xs text-muted">Bucket size: {bucketType}</div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function StatCard({ label, value, note }: { label: string; value: string; note?: string }) {
  return (
    <div className="rounded-2xl border border-line bg-surface p-5 shadow-soft">
      <div className="text-xs uppercase tracking-[0.24em] text-muted">{label}</div>
      <div className="mt-3 text-2xl font-semibold text-ink">{value}</div>
      {note && <div className="mt-2 text-xs text-muted">{note}</div>}
    </div>
  );
}

function formatTimestamp(isoString: string) {
  const date = new Date(isoString);
  return date.toLocaleString('en-US', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function formatDate(date: Date) {
  return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}

function formatNumber(value: number) {
  return numberFormatter.format(value);
}

function formatCompact(value: number) {
  return compactFormatter.format(value);
}

function formatPercent(value: number) {
  return `${(value * 100).toFixed(1)}%`;
}
