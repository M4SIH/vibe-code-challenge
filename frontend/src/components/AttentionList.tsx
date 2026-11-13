import type { AttentionItem } from '../attention';
import { describeTimeLeft, faNumber, formatCategory, formatDate } from '../format';
import type { Message } from '../types';
import DraftPanel from './DraftPanel';
import OrderText from './OrderText';

interface Props {
  items: AttentionItem[];
  unknownTime: Message[];
}

/**
 * Every unanswered high-severity original, most overdue first, then closest to
 * breaching the 2-business-hour promise. Minutes are business minutes,
 * recomputed in the browser from the current time (no server or LLM call).
 */
export default function AttentionList({ items, unknownTime }: Props) {
  return (
    <section className="card" aria-labelledby="attention-title">
      <h2 id="attention-title">نیازمند رسیدگی ({faNumber(items.length)})</h2>
      <p className="muted">
        پیام‌های جدی پاسخ‌داده‌نشده (به‌جز پیام‌های تکراری). زمان به ساعت کاری حساب می‌شود:
        شنبه تا چهارشنبه ۹ تا ۱۷ به وقت تهران، بدون تعطیلات رسمی.
      </p>
      {items.length === 0 ? (
        <p className="muted">موردی برای رسیدگی نیست.</p>
      ) : (
        <ol className="attention-list">
          {items.map(({ message: m, minutesLeft }) => (
            <li
              key={m.message_id}
              className={minutesLeft <= 0 ? 'overdue' : minutesLeft <= 30 ? 'soon' : ''}
              data-testid="attention-row"
              data-message-id={m.message_id}
              data-business-minutes-left={minutesLeft}
            >
              <div className="attention-head">
                <span className={`countdown ${minutesLeft <= 0 ? 'overdue' : ''}`}>{describeTimeLeft(minutesLeft)}</span>
                <span className="badge">{formatCategory(m.category)}</span>
                <code dir="ltr">{m.message_id}</code>
                {m.order_ref && <code dir="ltr" className="order-ref">{m.order_ref}</code>}
              </div>
              <div className="attention-subject" dir="auto">{m.subject || '(بدون موضوع)'}</div>
              <div className="attention-body" dir="auto"><OrderText text={m.body} /></div>
              <div className="attention-meta">
                دریافت: {formatDate(m.received_at)} · کانال: {m.channel || '—'} · مشتری: <span dir="ltr">{m.customer_id}</span>
              </div>
              <DraftPanel message={m} />
            </li>
          ))}
        </ol>
      )}
      {unknownTime.length > 0 && (
        <div className="unknown-time">
          <h3>زمان دریافت نامعلوم ({faNumber(unknownTime.length)})</h3>
          <p className="muted">زمان این پیام‌های جدی قابل خواندن نبود؛ مهلت را نمی‌توان حساب کرد، دستی بررسی کنید.</p>
          <ul>
            {unknownTime.map((m) => (
              <li key={m.message_id}><code dir="ltr">{m.message_id}</code> <span dir="auto">{m.subject}</span></li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}
