/**
 * Business-time arithmetic in the browser (a port of backend/app/sla.py).
 *
 * Support works Saturday–Wednesday, 09:00–17:00 Tehran time, closed on the
 * README's 1405 public holidays. Tehran is a fixed UTC+03:30 (no DST since 2022).
 * Tested on the same cases as the backend: businessTime.cases.json.
 */

const TEHRAN_OFFSET_MS = (3 * 60 + 30) * 60 * 1000;
const DAY_MS = 24 * 60 * 60 * 1000;
const OPEN_MS = 9 * 60 * 60 * 1000;
const CLOSE_MS = 17 * 60 * 60 * 1000;
/** getUTCDay(): Sunday=0 … Saturday=6. Open Sat, Sun, Mon, Tue, Wed. */
const OPEN_WEEKDAYS = new Set([6, 0, 1, 2, 3]);

/** The README holidays (1405/01/01 … 1405/12/29) in Gregorian, Tehran dates. */
export const HOLIDAYS = new Set([
  '2026-03-21', '2026-03-22', '2026-03-23', '2026-03-24', '2026-04-01', '2026-04-02',
  '2026-04-14', '2026-05-28', '2026-06-04', '2026-06-05', '2026-06-26', '2026-06-27',
  '2026-08-06', '2026-08-14', '2026-08-16', '2026-08-23', '2026-09-01', '2026-11-15',
  '2026-12-24', '2027-01-07', '2027-01-25', '2027-02-11', '2027-03-01', '2027-03-11',
  '2027-03-12', '2027-03-20',
]);

export const SLA_MINUTES = 120;

/** Tehran-local "wall clock" as a UTC timestamp (so UTC getters read Tehran time). */
function toLocal(utcMs: number): number {
  return utcMs + TEHRAN_OFFSET_MS;
}

function isBusinessDay(localDayStartMs: number): boolean {
  const d = new Date(localDayStartMs);
  return OPEN_WEEKDAYS.has(d.getUTCDay()) && !HOLIDAYS.has(d.toISOString().slice(0, 10));
}

/** Business seconds in [start, end); 0 when end <= start. Inputs are epoch ms. */
export function businessSecondsBetween(startMs: number, endMs: number): number {
  if (!(endMs > startMs)) return 0;
  const start = toLocal(startMs);
  const end = toLocal(endMs);
  let total = 0;
  for (let day = Math.floor(start / DAY_MS) * DAY_MS; day <= end; day += DAY_MS) {
    if (!isBusinessDay(day)) continue;
    const lo = Math.max(day + OPEN_MS, start);
    const hi = Math.min(day + CLOSE_MS, end);
    if (hi > lo) total += hi - lo;
  }
  return total / 1000;
}

/**
 * Whole business minutes until the 2-hour promise breaks; <= 0 means overdue.
 * Rounded up like the backend, so 0 appears only once the full SLA has elapsed.
 */
export function businessMinutesLeft(receivedMs: number, nowMs: number, slaMinutes = SLA_MINUTES): number {
  const left = slaMinutes * 60 - businessSecondsBetween(receivedMs, nowMs);
  return Math.ceil(left / 60) + 0; // "+ 0" turns -0 into 0
}

/** The instant (epoch ms) at which `minutes` business minutes have elapsed. */
export function addBusinessMinutes(startMs: number, minutes: number): number {
  let remaining = minutes * 60 * 1000;
  const cursor = toLocal(startMs);
  for (let day = Math.floor(cursor / DAY_MS) * DAY_MS, i = 0; i < 3660; day += DAY_MS, i++) {
    if (!isBusinessDay(day)) continue;
    const lo = Math.max(day + OPEN_MS, cursor);
    const close = day + CLOSE_MS;
    if (lo < close) {
      if (remaining <= close - lo) return lo + remaining - TEHRAN_OFFSET_MS;
      remaining -= close - lo;
    }
  }
  throw new Error('deadline is more than ten years away');
}
