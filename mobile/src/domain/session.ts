export type SessionName = 'tokyo' | 'london' | 'new_york' | 'utc_rollover';

interface SessionDefinition {
  name: SessionName;
  label: string;
  timeZone: string;
  hour: number;
  minute: number;
}

/** Mirrors the backend SessionScheduler so the app and the scanner agree. */
const SESSIONS: SessionDefinition[] = [
  { name: 'tokyo', label: 'Tokyo open', timeZone: 'Asia/Tokyo', hour: 9, minute: 0 },
  { name: 'london', label: 'London open', timeZone: 'Europe/London', hour: 8, minute: 0 },
  { name: 'new_york', label: 'New York open', timeZone: 'America/New_York', hour: 9, minute: 30 },
  { name: 'utc_rollover', label: 'UTC rollover', timeZone: 'UTC', hour: 0, minute: 0 },
];

/** Standard-time fallbacks, used only if the runtime lacks time zone data. */
const FALLBACK_OFFSETS: Record<string, number> = {
  'Asia/Tokyo': 540,
  'Europe/London': 0,
  'America/New_York': -300,
  UTC: 0,
};

const MINUTE = 60_000;
/** The backend sweeps a session from 15 minutes before to 60 minutes after. */
const WINDOW_BEFORE = 15;
const WINDOW_AFTER = 60;

export type OffsetResolver = (timeZone: string, at: Date) => number;

/** Minutes that `timeZone` is ahead of UTC at `at`, DST included. */
export const zoneOffsetMinutes: OffsetResolver = (timeZone, at) => {
  try {
    const parts = new Intl.DateTimeFormat('en-US', { timeZone, timeZoneName: 'longOffset' }).formatToParts(at);
    const name = parts.find((part) => part.type === 'timeZoneName')?.value ?? '';
    const match = /GMT([+-])(\d{1,2})(?::(\d{2}))?/.exec(name);
    if (!match) return name.includes('GMT') ? 0 : (FALLBACK_OFFSETS[timeZone] ?? 0);
    const sign = match[1] === '-' ? -1 : 1;
    return sign * (Number(match[2]) * 60 + Number(match[3] ?? 0));
  } catch {
    return FALLBACK_OFFSETS[timeZone] ?? 0;
  }
};

function openInstant(definition: SessionDefinition, now: Date, resolve: OffsetResolver, dayOffset: number): Date {
  const offset = resolve(definition.timeZone, now);
  const local = new Date(now.getTime() + offset * MINUTE);
  const localOpen = Date.UTC(
    local.getUTCFullYear(),
    local.getUTCMonth(),
    local.getUTCDate() + dayOffset,
    definition.hour,
    definition.minute,
  );
  const approximate = new Date(localOpen - offset * MINUTE);
  // Re-resolve at the candidate instant so a DST boundary between now and the
  // open shifts the result rather than silently skewing it by an hour.
  const settled = resolve(definition.timeZone, approximate);
  return settled === offset ? approximate : new Date(localOpen - settled * MINUTE);
}

export interface SessionContext {
  name: SessionName;
  label: string;
  /** `active` while the sweep window is open; otherwise the next session. */
  phase: 'active' | 'upcoming';
  at: Date;
  /** Minutes since the open when active, minutes until it when upcoming. */
  minutes: number;
}

/**
 * The session that matters right now.
 *
 * A session schedules analysis. It never implies a trade, and the UI says so —
 * this exists to explain *why* the system is looking, not to create urgency.
 */
export function currentSessionContext(now: Date = new Date(), resolve: OffsetResolver = zoneOffsetMinutes): SessionContext {
  const candidates = SESSIONS.flatMap((definition) =>
    [0, 1].map((dayOffset) => ({ definition, at: openInstant(definition, now, resolve, dayOffset) })),
  );

  const active = candidates
    .filter(({ at }) => {
      const delta = (now.getTime() - at.getTime()) / MINUTE;
      return delta >= -WINDOW_BEFORE && delta <= WINDOW_AFTER;
    })
    .sort((left, right) => left.at.getTime() - right.at.getTime())[0];

  if (active) {
    return {
      name: active.definition.name,
      label: active.definition.label,
      phase: 'active',
      at: active.at,
      minutes: Math.max(0, Math.round((now.getTime() - active.at.getTime()) / MINUTE)),
    };
  }

  const [next] = candidates
    .filter(({ at }) => at.getTime() > now.getTime())
    .sort((left, right) => left.at.getTime() - right.at.getTime());

  return {
    name: next.definition.name,
    label: next.definition.label,
    phase: 'upcoming',
    at: next.at,
    minutes: Math.round((next.at.getTime() - now.getTime()) / MINUTE),
  };
}

/** "in 42m", "in 3h 10m", "24m ago". */
export function describeSession(context: SessionContext): string {
  const { minutes, phase } = context;
  if (phase === 'active') {
    return minutes <= 0 ? 'opening now' : `opened ${formatDuration(minutes)} ago`;
  }
  return `in ${formatDuration(minutes)}`;
}

function formatDuration(minutes: number): string {
  if (minutes < 60) return `${minutes}m`;
  const hours = Math.floor(minutes / 60);
  const rest = minutes % 60;
  return rest === 0 ? `${hours}h` : `${hours}h ${rest}m`;
}
