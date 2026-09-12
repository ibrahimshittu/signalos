import { describe, expect, it } from '@jest/globals';
import { currentSessionContext, describeSession, zoneOffsetMinutes } from './session';

/** Fixed offsets keep the assertions independent of the host's ICU data. */
const offsets: Record<string, number> = {
  'Asia/Tokyo': 540,
  'Europe/London': 60,
  'America/New_York': -240,
  UTC: 0,
};
const resolve = (timeZone: string) => offsets[timeZone] ?? 0;

describe('session context', () => {
  it('reports the London open as active inside the sweep window', () => {
    // 07:20 UTC is 08:20 in London — 20 minutes after the open.
    const context = currentSessionContext(new Date(Date.UTC(2026, 7, 14, 7, 20)), resolve);
    expect(context.name).toBe('london');
    expect(context.phase).toBe('active');
    expect(context.minutes).toBe(20);
    expect(describeSession(context)).toBe('opened 20m ago');
  });

  it('treats the 15 minutes before an open as already active', () => {
    const context = currentSessionContext(new Date(Date.UTC(2026, 7, 14, 6, 50)), resolve);
    expect(context.name).toBe('london');
    expect(context.phase).toBe('active');
  });

  it('falls through to the next open once the window closes', () => {
    // 08:30 UTC is 90 minutes past the London open and before New York.
    const context = currentSessionContext(new Date(Date.UTC(2026, 7, 14, 8, 30)), resolve);
    expect(context.name).toBe('new_york');
    expect(context.phase).toBe('upcoming');
    expect(context.minutes).toBe(300);
    expect(describeSession(context)).toBe('in 5h');
  });

  it('rolls over to tomorrow rather than reporting a past open', () => {
    const context = currentSessionContext(new Date(Date.UTC(2026, 7, 14, 22, 0)), resolve);
    expect(context.phase).toBe('upcoming');
    expect(context.at.getTime()).toBeGreaterThan(Date.UTC(2026, 7, 14, 22, 0));
    expect(context.name).toBe('tokyo');
  });

  it('formats multi-hour waits with hours and minutes', () => {
    const context = currentSessionContext(new Date(Date.UTC(2026, 7, 14, 10, 20)), resolve);
    expect(describeSession(context)).toBe('in 3h 10m');
  });
});

describe('zone offsets', () => {
  it('resolves a real zone offset from the runtime', () => {
    expect(zoneOffsetMinutes('UTC', new Date(Date.UTC(2026, 7, 14)))).toBe(0);
  });

  it('falls back to a standard offset for an unknown zone', () => {
    expect(zoneOffsetMinutes('Not/AZone', new Date(Date.UTC(2026, 7, 14)))).toBe(0);
  });
});
