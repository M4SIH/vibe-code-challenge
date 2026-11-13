import type { AnalyzeResult, Message } from './types';

export function msg(over: Partial<Message> & { message_id: string }): Message {
  return {
    category: 'delivery', is_urgent: false, order_ref: null, duplicate_of: null, customer_id: 'C1',
    channel: 'app', received_at: '2026-10-24T05:30:00Z', answered_at: null, subject: 'subject', body: 'body',
    severity: 'high', severity_hint: 'low', answered: false, group_answered_at: null,
    answer_time_unknown: false, sla_deadline: null, business_minutes_left: null, ...over,
  };
}

// Saturday 2026-10-24, Tehran = UTC+03:30. "Now" in the tests: 11:30 Tehran = 08:00Z.
export const NOW = '2026-10-24T08:00:00Z';

export const MESSAGES: Message[] = [
  msg({ message_id: 'M_ON_TIME', received_at: '2026-10-24T07:30:00Z' }),          // 11:00 Tehran -> 90 left
  msg({ message_id: 'M_OVERDUE_BIG', received_at: '2026-10-22T05:30:00Z' }),      // Thursday -> counts from Sat 09:00 -> -30
  msg({ message_id: 'M_OVERDUE_MORE', received_at: '2026-10-21T10:30:00Z' }),     // Wed 14:00 -> 3h Wed + 2.5h Sat
  msg({ message_id: 'M_ALMOST', received_at: '2026-10-24T06:05:00Z' }),           // 09:35 -> 5 left
  msg({ message_id: 'M_RESEND', duplicate_of: 'M_ON_TIME', received_at: '2026-10-24T07:40:00Z' }),
  msg({ message_id: 'M_NORMAL', severity: 'normal' }),
  msg({ message_id: 'M_ANSWERED', group_answered_at: '2026-10-24T07:00:00Z', answered: true }),
  msg({ message_id: 'M_ANSWER_LATER', group_answered_at: '2026-10-24T09:00:00Z' }),  // answered after "now"
  msg({ message_id: 'M_ANSWER_UNREADABLE', answer_time_unknown: true }),
  msg({ message_id: 'M_NO_TIME', received_at: null }),
  msg({ message_id: 'M_XSS', severity: 'normal', body: 'see <img src=x onerror="window.__xss=1"> and <script>window.__xss=2</script> order BZ-۱۲۳۴' }),
];

export const RESULT: AnalyzeResult = {
  total_unique_messages: 10,
  category_counts: { delivery: 10 },  // other categories missing on purpose: no NaN allowed
  urgent_message_ids: [],
  messages: MESSAGES,
};
