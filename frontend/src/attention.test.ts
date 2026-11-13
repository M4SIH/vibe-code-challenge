import { buildAttention, isAnswered, urgentCount } from './attention';
import { MESSAGES, NOW, msg } from './testData';

const now = Date.parse(NOW);

describe('needs-attention list', () => {
  const { items, unknownTime } = buildAttention(MESSAGES, now);
  const ids = items.map((i) => i.message.message_id);

  it('holds unanswered high-severity originals, including ones not overdue yet', () => {
    expect(new Set(ids)).toEqual(new Set(['M_ON_TIME', 'M_OVERDUE_BIG', 'M_OVERDUE_MORE', 'M_ALMOST', 'M_ANSWER_LATER']));
  });
  it('excludes resends, normal severity and answered groups', () => {
    for (const id of ['M_RESEND', 'M_NORMAL', 'M_ANSWERED', 'M_ANSWER_UNREADABLE']) expect(ids).not.toContain(id);
  });
  it('keeps messages without a readable time separately', () => {
    expect(unknownTime.map((m) => m.message_id)).toEqual(['M_NO_TIME']);
  });
  it('sorts most overdue first, then closest to breaching', () => {
    const left = items.map((i) => i.minutesLeft);
    expect(left).toEqual([...left].sort((a, b) => a - b));
    expect(ids[0]).toBe('M_OVERDUE_MORE');
  });
  it('counts business minutes (Thursday does not count)', () => {
    const byId = Object.fromEntries(items.map((i) => [i.message.message_id, i.minutesLeft]));
    expect(byId.M_ON_TIME).toBe(90);
    expect(byId.M_OVERDUE_BIG).toBe(-30);       // received Thursday: clock starts Sat 09:00
    expect(byId.M_OVERDUE_MORE).toBe(-210);     // Wed 14:00-17:00 + Sat 09:00-11:30 = 330 min
    expect(byId.M_ALMOST).toBe(5);
  });
  it('urgent count = rows with 0 or fewer minutes left', () => {
    // M_ANSWER_LATER: received 09:00, its answer comes after "now", so at 11:30 it is overdue too
    const overdue = items.filter((i) => i.minutesLeft <= 0).map((i) => i.message.message_id);
    expect(new Set(overdue)).toEqual(new Set(['M_OVERDUE_MORE', 'M_OVERDUE_BIG', 'M_ANSWER_LATER']));
    expect(urgentCount(items)).toBe(3);
  });
  it('an answer stamped after now does not count yet', () => {
    expect(isAnswered(msg({ message_id: 'x', group_answered_at: '2026-10-24T09:00:00Z' }), now)).toBe(false);
    expect(isAnswered(msg({ message_id: 'x', group_answered_at: '2026-10-24T07:00:00Z' }), now)).toBe(true);
  });
});
