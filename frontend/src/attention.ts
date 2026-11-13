import { businessMinutesLeft } from './businessTime';
import type { Message } from './types';

export interface AttentionItem {
  message: Message;
  minutesLeft: number;
}

/** Answered by `nowMs` (any copy in the resend group counts). */
export function isAnswered(m: Message, nowMs: number): boolean {
  if (m.answer_time_unknown) return true;
  return m.group_answered_at !== null && Date.parse(m.group_answered_at) <= nowMs;
}

/**
 * The needs-attention list: every high-severity original (not a resend) that is
 * still unanswered at `nowMs`, most overdue first, then closest to breaching.
 * Messages without a readable received time are returned separately.
 */
export function buildAttention(messages: Message[], nowMs: number): { items: AttentionItem[]; unknownTime: Message[] } {
  const items: AttentionItem[] = [];
  const unknownTime: Message[] = [];
  for (const m of messages) {
    if (m.duplicate_of !== null || m.severity !== 'high' || isAnswered(m, nowMs)) continue;
    const received = m.received_at ? Date.parse(m.received_at) : NaN;
    if (Number.isNaN(received)) {
      unknownTime.push(m);
      continue;
    }
    items.push({ message: m, minutesLeft: businessMinutesLeft(received, nowMs) });
  }
  items.sort((a, b) =>
    a.minutesLeft - b.minutesLeft
    || (a.message.received_at ?? '').localeCompare(b.message.received_at ?? '')
    || a.message.message_id.localeCompare(b.message.message_id));
  return { items, unknownTime };
}

export function urgentCount(items: AttentionItem[]): number {
  return items.filter((i) => i.minutesLeft <= 0).length;
}
