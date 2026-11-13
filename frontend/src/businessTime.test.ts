import cases from './businessTime.cases.json';
import { HOLIDAYS, addBusinessMinutes, businessMinutesLeft, businessSecondsBetween } from './businessTime';

const ms = (iso: string) => Date.parse(iso);

describe('business time matches the backend (shared cases)', () => {
  it('uses the same holiday list', () => {
    expect([...HOLIDAYS].sort()).toEqual(cases.holidays);
  });

  it.each(cases.between)('seconds between $start and $end', ({ start, end, seconds }) => {
    expect(businessSecondsBetween(ms(start), ms(end))).toBe(seconds);
  });

  it.each(cases.minutes_left)('minutes left for $received at $now', ({ received, now, left }) => {
    expect(businessMinutesLeft(ms(received), ms(now))).toBe(left);
  });

  it.each(cases.deadline)('deadline from $start', ({ start, deadline }) => {
    expect(addBusinessMinutes(ms(start), 120)).toBe(ms(deadline));
  });
});

describe('README rules, spelled out', () => {
  // Saturday 2026-10-24 09:00 Tehran = 05:30Z
  const received = ms('2026-10-24T05:30:00Z');
  it('exactly two business hours is overdue (0 left)', () => {
    expect(businessMinutesLeft(received, ms('2026-10-24T07:30:00Z'))).toBe(0);
  });
  it('one minute before is not', () => {
    expect(businessMinutesLeft(received, ms('2026-10-24T07:29:00Z'))).toBe(1);
  });
  it('Thursday and Friday do not count', () => {
    // Wednesday 16:30 Tehran -> Friday noon: only 30 business minutes
    expect(businessMinutesLeft(ms('2026-10-21T13:00:00Z'), ms('2026-10-23T08:30:00Z'))).toBe(90);
  });
  it('the 1405/06/01 holiday does not count', () => {
    // Saturday 16:00 Tehran -> Monday 10:30 Tehran (Sunday 2026-08-23 is a holiday): 150 min elapsed
    expect(businessMinutesLeft(ms('2026-08-22T12:30:00Z'), ms('2026-08-24T07:00:00Z'))).toBe(-30);
  });
});
