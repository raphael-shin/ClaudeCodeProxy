export type UsagePeriod = 'day' | 'week' | 'month';
export type BucketType = 'minute' | 'hour' | 'day' | 'week' | 'month';

export const KST_TIME_ZONE = 'Asia/Seoul';

const KST_OFFSET_MS = 9 * 60 * 60 * 1000;
const DAY_MS = 24 * 60 * 60 * 1000;

export interface ResolvedRange {
  startTime: Date;
  endTime: Date;
  rangeDays: number;
  startDate: string;
  endDate: string;
}

export function resolvePeriodRange(period: UsagePeriod, now: Date = new Date()): ResolvedRange {
  const { year, month, day, dayOfWeek } = getKstParts(now);
  let startTime: Date;

  if (period === 'day') {
    startTime = kstDateFromParts(year, month, day);
  } else if (period === 'week') {
    startTime = kstDateFromParts(year, month, day - dayOfWeek);
  } else {
    startTime = kstDateFromParts(year, month, 1);
  }

  const rangeDays = Math.max(
    1,
    Math.ceil((now.getTime() - startTime.getTime()) / DAY_MS)
  );

  return {
    startTime,
    endTime: now,
    rangeDays,
    startDate: toKstDateString(startTime),
    endDate: toKstDateString(now),
  };
}

export function resolveCustomRange(
  startDate: string,
  endDate: string
): ResolvedRange | null {
  const startParts = parseDateString(startDate);
  const endParts = parseDateString(endDate);
  if (!startParts || !endParts) return null;

  const startDayMs = Date.UTC(startParts.year, startParts.month - 1, startParts.day);
  const endDayMs = Date.UTC(endParts.year, endParts.month - 1, endParts.day);
  if (endDayMs < startDayMs) return null;

  const rangeDays = Math.max(1, Math.floor((endDayMs - startDayMs) / DAY_MS) + 1);

  return {
    startTime: kstDateFromParts(startParts.year, startParts.month, startParts.day),
    endTime: kstDateFromParts(endParts.year, endParts.month, endParts.day + 1),
    rangeDays,
    startDate,
    endDate,
  };
}

export function selectBucketType(rangeDays: number): BucketType {
  if (rangeDays <= 2) return 'hour';
  if (rangeDays <= 45) return 'day';
  return 'week';
}

export function toKstDateString(date: Date): string {
  const kst = new Date(date.getTime() + KST_OFFSET_MS);
  const year = kst.getUTCFullYear();
  const month = String(kst.getUTCMonth() + 1).padStart(2, '0');
  const day = String(kst.getUTCDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

export function formatKstDate(date: Date): string {
  return date.toLocaleDateString('en-US', {
    timeZone: KST_TIME_ZONE,
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  });
}

export function formatKstDateTime(date: Date): string {
  return date.toLocaleString('en-US', {
    timeZone: KST_TIME_ZONE,
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function kstDateFromParts(year: number, month: number, day: number): Date {
  return new Date(Date.UTC(year, month - 1, day) - KST_OFFSET_MS);
}

function getKstParts(date: Date) {
  const kst = new Date(date.getTime() + KST_OFFSET_MS);
  return {
    year: kst.getUTCFullYear(),
    month: kst.getUTCMonth() + 1,
    day: kst.getUTCDate(),
    dayOfWeek: kst.getUTCDay(),
  };
}

function parseDateString(value: string) {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
  if (!match) return null;
  const year = Number(match[1]);
  const month = Number(match[2]);
  const day = Number(match[3]);
  if (!year || !month || !day) return null;
  return { year, month, day };
}
