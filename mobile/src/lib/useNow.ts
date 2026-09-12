import { useEffect, useState } from 'react';

/**
 * A clock that ticks slowly.
 *
 * Expiry is stated in minutes, so a 30-second tick keeps it truthful without a
 * per-second countdown — a live countdown would manufacture exactly the urgency
 * this product avoids.
 */
export function useNow(intervalMs = 30_000): Date {
  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    const timer = setInterval(() => setNow(new Date()), intervalMs);
    return () => clearInterval(timer);
  }, [intervalMs]);
  return now;
}
