import { useMemo, useState } from 'react';
import { faNumber, formatCategory, formatDate } from '../format';
import { CATEGORIES, type Message } from '../types';
import OrderText from './OrderText';

const MAX_ROWS = 200;

export default function MessagesTable({ messages }: { messages: Message[] }) {
  const [category, setCategory] = useState<string>('');
  const [query, setQuery] = useState('');

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return messages.filter((m) =>
      (!category || m.category === category)
      && (!q || `${m.message_id} ${m.order_ref ?? ''} ${m.subject} ${m.body}`.toLowerCase().includes(q)));
  }, [messages, category, query]);
  const rows = filtered.slice(0, MAX_ROWS);

  return (
    <section className="card" aria-labelledby="messages-title">
      <h2 id="messages-title">همهٔ پیام‌ها</h2>
      <div className="filters">
        <label>
          دسته
          <select value={category} onChange={(e) => setCategory(e.target.value)}>
            <option value="">همه</option>
            {CATEGORIES.map((c) => <option key={c} value={c}>{formatCategory(c)}</option>)}
          </select>
        </label>
        <label>
          جستجو
          <input type="search" value={query} onChange={(e) => setQuery(e.target.value)} placeholder="شناسه، سفارش یا متن" />
        </label>
      </div>
      {filtered.length > MAX_ROWS && (
        <p className="muted">نمایش {faNumber(MAX_ROWS)} پیام از {faNumber(filtered.length)}.</p>
      )}
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>شناسه</th><th>دسته</th><th>جدی</th><th>فوری</th><th>سفارش</th>
              <th>کانال</th><th>دریافت</th><th>موضوع</th><th>متن</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((m) => (
              <tr key={m.message_id} className={m.duplicate_of ? 'resend' : undefined}>
                <td dir="ltr">
                  {m.message_id}
                  {m.duplicate_of && <div className="muted small">تکرارِ <span dir="ltr">{m.duplicate_of}</span></div>}
                </td>
                <td>{formatCategory(m.category)}</td>
                <td>{m.severity === 'high' ? 'بله' : ''}</td>
                <td>{m.is_urgent ? 'بله' : ''}</td>
                <td dir="ltr">{m.order_ref ?? '—'}</td>
                <td dir="ltr">{m.channel || '—'}</td>
                <td>{formatDate(m.received_at)}</td>
                <td dir="auto">{m.subject}</td>
                <td dir="auto" className="body-cell"><OrderText text={m.body} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
