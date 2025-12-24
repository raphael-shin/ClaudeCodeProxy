'use client';

import { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { api, UsageResponse, UsageTopUser, User } from '@/lib/api';
import {
  AreaChart,
  Area,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';

const RANGE_PRESETS = [
  { key: '1h', label: '1h', minutes: 60 },
  { key: '3h', label: '3h', minutes: 180 },
  { key: '12h', label: '12h', minutes: 720 },
  { key: '1d', label: '1d', minutes: 1440 },
  { key: '3d', label: '3d', minutes: 4320 },
  { key: '1w', label: '1w', minutes: 10080 },
  { key: 'custom', label: 'Custom' },
];

const TIMEZONE_OPTIONS = [
  { value: 'UTC', label: 'UTC timezone', offsetMinutes: 0 },
  { value: 'Asia/Seoul', label: 'Asia/Seoul (GMT+9)', offsetMinutes: 540 },
];

export default function UsagePage() {
  const [usage, setUsage] = useState<UsageResponse | null>(null);
  const [userUsage, setUserUsage] = useState<UsageResponse | null>(null);
  const [topUsers, setTopUsers] = useState<UsageTopUser[]>([]);
  const [users, setUsers] = useState<User[]>([]);
  const [selectedUserId, setSelectedUserId] = useState('');
  const [rangePreset, setRangePreset] = useState('3h');
  const [customRange, setCustomRange] = useState({ start: '', end: '' });
  const [timezone, setTimezone] = useState('Asia/Seoul');

  const timezoneOption = TIMEZONE_OPTIONS.find((option) => option.value === timezone) || TIMEZONE_OPTIONS[1];

  const range = useMemo(() => {
    if (rangePreset !== 'custom') {
      const preset = RANGE_PRESETS.find((item) => item.key === rangePreset);
      if (!preset || !preset.minutes) return null;
      const end = new Date();
      const start = new Date(end.getTime() - preset.minutes * 60 * 1000);
      return { start, end };
    }

    if (!customRange.start || !customRange.end) {
      return null;
    }

    const start = parseDateTimeLocal(customRange.start, timezoneOption.offsetMinutes);
    const end = parseDateTimeLocal(customRange.end, timezoneOption.offsetMinutes);
    if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime())) {
      return null;
    }
    return { start, end };
  }, [customRange.end, customRange.start, rangePreset, timezoneOption.offsetMinutes]);

  const bucketType = useMemo(() => {
    if (!range) return 'hour';
    const hours = (range.end.getTime() - range.start.getTime()) / (60 * 60 * 1000);
    if (hours <= 3) return 'minute';
    if (hours <= 48) return 'hour';
    if (hours <= 24 * 14) return 'day';
    return 'week';
  }, [range]);

  useEffect(() => {
    api.getUsers().then(setUsers).catch(() => {});
  }, []);

  useEffect(() => {
    if (!range) return;

    const params = {
      bucket_type: bucketType,
      start_time: range.start.toISOString(),
      end_time: range.end.toISOString(),
    };

    api.getUsage(params).then(setUsage).catch(() => {});
    api.getTopUsers({ ...params, limit: 8 }).then(setTopUsers).catch(() => {});

    if (selectedUserId) {
      api.getUsage({ ...params, user_id: selectedUserId }).then(setUserUsage).catch(() => {});
    } else {
      setUserUsage(null);
    }
  }, [bucketType, range, selectedUserId]);

  const chartData =
    usage?.buckets.map((b) => ({
      time: formatTimestamp(b.bucket_start, timezone),
      tokens: b.total_tokens,
      requests: b.requests,
      inputTokens: b.input_tokens,
      outputTokens: b.output_tokens,
    })) || [];

  const userChartData =
    userUsage?.buckets.map((b) => ({
      time: formatTimestamp(b.bucket_start, timezone),
      tokens: b.total_tokens,
      requests: b.requests,
    })) || [];

  const topUserMaxTokens = Math.max(...topUsers.map((u) => u.total_tokens), 1);
  const selectedUser = users.find((user) => user.id === selectedUserId);

  return (
    <div className="p-8 max-w-7xl mx-auto space-y-6">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <h1 className="text-2xl font-bold">Usage Dashboard</h1>
          <p className="text-gray-500 text-sm">
            전체 사용량 트렌드와 사용자별 분포를 한 번에 확인하세요.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <div className="inline-flex flex-wrap rounded-full border border-gray-200 bg-white p-1 shadow-sm">
            {RANGE_PRESETS.map((preset) => (
              <button
                key={preset.key}
                type="button"
                onClick={() => setRangePreset(preset.key)}
                className={`px-4 py-1.5 text-sm font-semibold rounded-full transition ${
                  rangePreset === preset.key
                    ? 'bg-blue-600 text-white shadow'
                    : 'text-gray-600 hover:text-gray-900 hover:bg-gray-100'
                }`}
              >
                {preset.label}
              </button>
            ))}
          </div>
          <select
            value={timezone}
            onChange={(e) => setTimezone(e.target.value)}
            className="rounded-full border border-gray-200 bg-white px-4 py-2 text-sm font-semibold text-gray-700 shadow-sm"
          >
            {TIMEZONE_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
          <Link href="/users" className="text-blue-600 text-sm font-semibold">
            ← Back to Users
          </Link>
        </div>
      </div>

      {rangePreset === 'custom' && (
        <div className="flex flex-wrap items-center gap-3 rounded-xl border border-gray-200 bg-white px-4 py-3 shadow-sm">
          <div className="text-sm text-gray-600 font-semibold">Custom Range</div>
          <input
            type="datetime-local"
            value={customRange.start}
            onChange={(e) => setCustomRange((prev) => ({ ...prev, start: e.target.value }))}
            className="rounded-lg border border-gray-200 px-3 py-2 text-sm"
          />
          <span className="text-gray-400 text-sm">to</span>
          <input
            type="datetime-local"
            value={customRange.end}
            onChange={(e) => setCustomRange((prev) => ({ ...prev, end: e.target.value }))}
            className="rounded-lg border border-gray-200 px-3 py-2 text-sm"
          />
          <div className="text-xs text-gray-500">
            표시 시간대: {timezoneOption.label}
          </div>
        </div>
      )}

      {usage && (
        <>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <MetricCard label="Total Tokens" value={usage.total_tokens} />
            <MetricCard label="Total Requests" value={usage.total_requests} />
            <MetricCard label="Input Tokens" value={usage.total_input_tokens} />
            <MetricCard label="Output Tokens" value={usage.total_output_tokens} />
          </div>

          <div className="grid gap-6 lg:grid-cols-3">
            <div className="bg-white p-6 rounded-2xl shadow-sm border border-gray-100 lg:col-span-2">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-lg font-bold">전체 토큰 추세</h2>
                <div className="text-xs text-gray-500 font-semibold">
                  Bucket: {bucketType}
                </div>
              </div>
              <ResponsiveContainer width="100%" height={320}>
                <AreaChart data={chartData}>
                  <defs>
                    <linearGradient id="tokensGradient" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#2563eb" stopOpacity={0.3} />
                      <stop offset="100%" stopColor="#2563eb" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="time" />
                  <YAxis />
                  <Tooltip />
                  <Area type="monotone" dataKey="tokens" stroke="#2563eb" fill="url(#tokensGradient)" />
                  <Line type="monotone" dataKey="requests" stroke="#0f172a" strokeWidth={2} />
                </AreaChart>
              </ResponsiveContainer>
            </div>

            <div className="bg-white p-6 rounded-2xl shadow-sm border border-gray-100">
              <h2 className="text-lg font-bold mb-4">Top Users</h2>
              <div className="space-y-4">
                {topUsers.length === 0 && (
                  <div className="text-sm text-gray-500">No usage data in this range.</div>
                )}
                {topUsers.map((user) => (
                  <button
                    key={user.user_id}
                    onClick={() => setSelectedUserId(user.user_id)}
                    className="w-full text-left"
                    type="button"
                  >
                    <div className="flex items-center justify-between text-sm font-semibold text-gray-700">
                      <span>{user.name}</span>
                      <span>{user.total_tokens.toLocaleString()}</span>
                    </div>
                    <div className="mt-2 h-2 rounded-full bg-gray-100">
                      <div
                        className="h-2 rounded-full bg-blue-500"
                        style={{ width: `${(user.total_tokens / topUserMaxTokens) * 100}%` }}
                      />
                    </div>
                    <div className="mt-1 text-xs text-gray-500">
                      Requests: {user.total_requests.toLocaleString()}
                    </div>
                  </button>
                ))}
              </div>
            </div>
          </div>

          <div className="bg-white p-6 rounded-2xl shadow-sm border border-gray-100 space-y-4">
            <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
              <div>
                <h2 className="text-lg font-bold">User Drilldown</h2>
                <p className="text-sm text-gray-500">
                  선택한 사용자의 상세 사용량과 추세를 확인합니다.
                </p>
              </div>
              <select
                value={selectedUserId}
                onChange={(e) => setSelectedUserId(e.target.value)}
                className="rounded-lg border border-gray-200 px-3 py-2 text-sm font-semibold text-gray-700"
              >
                <option value="">Select user...</option>
                {users.map((user) => (
                  <option key={user.id} value={user.id}>
                    {user.name}
                  </option>
                ))}
              </select>
            </div>

            {!selectedUserId && (
              <div className="text-sm text-gray-500">사용자를 선택하면 세부 차트가 표시됩니다.</div>
            )}

            {selectedUserId && userUsage && (
              <div className="space-y-4">
                <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                  <MetricCard label="User Tokens" value={userUsage.total_tokens} />
                  <MetricCard label="User Requests" value={userUsage.total_requests} />
                  <MetricCard label="Input Tokens" value={userUsage.total_input_tokens} />
                  <MetricCard label="Output Tokens" value={userUsage.total_output_tokens} />
                </div>

                <div className="bg-slate-50 rounded-xl p-4 flex items-center justify-between">
                  <div className="text-sm text-gray-600">
                    Selected User: <span className="font-semibold text-gray-900">{selectedUser?.name}</span>
                  </div>
                  <div className="text-xs text-gray-500">Timezone: {timezoneOption.label}</div>
                </div>

                <ResponsiveContainer width="100%" height={280}>
                  <LineChart data={userChartData}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="time" />
                    <YAxis />
                    <Tooltip />
                    <Line type="monotone" dataKey="tokens" stroke="#16a34a" strokeWidth={2} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}

function MetricCard({ label, value }: { label: string; value: number }) {
  return (
    <div className="bg-white p-4 rounded-xl shadow-sm border border-gray-100">
      <p className="text-gray-500 text-sm font-semibold">{label}</p>
      <p className="text-2xl font-bold text-gray-900">{value.toLocaleString()}</p>
    </div>
  );
}

function formatTimestamp(timestamp: string, timeZone: string) {
  return new Intl.DateTimeFormat('en-US', {
    timeZone,
    month: 'short',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(timestamp));
}

function parseDateTimeLocal(value: string, offsetMinutes: number) {
  const [datePart, timePart] = value.split('T');
  if (!datePart || !timePart) return new Date('');
  const [year, month, day] = datePart.split('-').map(Number);
  const [hour, minute] = timePart.split(':').map(Number);
  const utcMillis = Date.UTC(year, month - 1, day, hour, minute) - offsetMinutes * 60 * 1000;
  return new Date(utcMillis);
}
