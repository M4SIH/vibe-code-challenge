import { useEffect, useMemo, useState } from 'react';
import { analyze } from './api';
import { buildAttention, urgentCount } from './attention';
import { faNumber } from './format';
import type { AnalyzeResult } from './types';
import UploadForm from './components/UploadForm';
import SummaryTiles from './components/SummaryTiles';
import CategoryBreakdown from './components/CategoryBreakdown';
import AttentionList from './components/AttentionList';
import MessagesTable from './components/MessagesTable';

/** The countdown refreshes this often (README: at least once a minute). No server or LLM call. */
export const REFRESH_MS = 30_000;

/** Browser time, optionally shifted to replay an old export ("now" = reference + time since upload). */
function useNow(offsetMs: number): number {
  const [now, setNow] = useState(() => Date.now() + offsetMs);
  useEffect(() => {
    const tick = () => setNow(Date.now() + offsetMs);
    tick();
    const id = setInterval(tick, REFRESH_MS);
    document.addEventListener('visibilitychange', tick);
    return () => {
      clearInterval(id);
      document.removeEventListener('visibilitychange', tick);
    };
  }, [offsetMs]);
  return now;
}

export default function App() {
  const [result, setResult] = useState<AnalyzeResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [offsetMs, setOffsetMs] = useState(0);
  const now = useNow(offsetMs);

  async function handleSubmit(file: File, referenceTehran?: string) {
    const offset = referenceTehran ? Date.parse(`${referenceTehran}:00+03:30`) - Date.now() : 0;
    setLoading(true);
    setError(null);
    try {
      const r = await analyze(file, new Date(Date.now() + offset).toISOString());
      setOffsetMs(Number.isFinite(offset) ? offset : 0);
      setResult(r);
    } catch (e) {
      setResult(null);
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }

  const attention = useMemo(() => (result ? buildAttention(result.messages, now) : null), [result, now]);
  const resends = result ? result.messages.filter((m) => m.duplicate_of !== null).length : 0;
  const dq = result?.data_quality;
  const cls = result?.classification;

  return (
    <main className="container">
      <header>
        <h1>داشبورد پشتیبانی بازارچه</h1>
        <p className="muted">خروجی روزانهٔ پیام‌های پشتیبانی را بارگذاری کنید تا ببینید مشتریان با چه مشکلی درگیرند و چه پیام‌هایی فوری است.</p>
      </header>
      <UploadForm onSubmit={handleSubmit} loading={loading} />
      {error && <p className="error" role="alert">{error}</p>}
      {result && attention && (
        <>
          {offsetMs !== 0 && (
            <p className="notice">حالت بازپخش: «اکنون» {new Date(now).toLocaleString('fa-IR', { timeZone: 'Asia/Tehran' })} به وقت تهران است.</p>
          )}
          <SummaryTiles
            total={result.total_unique_messages}
            attention={attention.items.length}
            urgent={urgentCount(attention.items)}
            resends={resends}
          />
          <AttentionList items={attention.items} unknownTime={attention.unknownTime} />
          <CategoryBreakdown counts={result.category_counts} total={result.total_unique_messages} />
          <MessagesTable messages={result.messages} />
          <footer className="muted small">
            {dq && (
              <p>
                کیفیت داده: {faNumber(dq.records_read)} ردیف خوانده شد، {faNumber(dq.rows_kept)} پیام نگه داشته شد،
                {' '}{faNumber(dq.blank_rows_skipped + dq.rows_without_id_skipped)} ردیف خالی/بدون شناسه کنار گذاشته شد
                {dq.unparseable_received_at.length > 0 && `، ${faNumber(dq.unparseable_received_at.length)} زمان دریافتِ ناخوانا`}
                {dq.answered_before_received.length > 0 && `، ${faNumber(dq.answered_before_received.length)} پاسخ با زمانی پیش از دریافت (پاسخ‌داده حساب شد)`}.
              </p>
            )}
            {cls && (
              <p>
                دسته‌بندی: {cls.mode !== 'keywords'
                  ? `هوش مصنوعی برای ${faNumber(cls.llm_labels ?? 0)} پیام، قواعد کلیدواژه‌ای برای ${faNumber(cls.keyword_labels ?? 0)} پیام`
                  : 'فقط قواعد کلیدواژه‌ای (هوش مصنوعی پیکربندی نشده)'}.
              </p>
            )}
          </footer>
        </>
      )}
    </main>
  );
}
