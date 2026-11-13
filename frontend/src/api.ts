import type { AnalyzeResult, Draft } from './types';

/** `now` is the dashboard's current time (ISO-8601 UTC), so the server and the
 *  live countdown agree on what has been answered. */
export async function analyze(file: File, now: string): Promise<AnalyzeResult> {
  const form = new FormData();
  form.append('file', file);
  const res = await fetch(`/api/analyze?now=${encodeURIComponent(now)}`, { method: 'POST', body: form });
  if (!res.ok) {
    let detail = '';
    try {
      detail = (await res.json()).detail ?? '';
    } catch {
      /* not JSON */
    }
    throw new Error(`تحلیل ناموفق بود (${res.status})${detail ? `: ${detail}` : ''}`);
  }
  return res.json();
}

export async function requestDraft(m: {
  message_id: string;
  customer_id: string;
  subject: string;
  body: string;
}): Promise<Draft> {
  const res = await fetch('/api/draft', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(m),
  });
  if (!res.ok) throw new Error(`Draft failed (${res.status})`);
  return res.json();
}
