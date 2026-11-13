import { useRef, useState } from 'react';
import { requestDraft } from '../api';
import { warningText } from '../format';
import type { Message } from '../types';

type State =
  | { status: 'idle' }
  | { status: 'loading' }
  | { status: 'ready'; text: string; language: 'fa' | 'en'; approved: boolean }
  | { status: 'blocked'; warnings: string[] };

async function copyText(text: string): Promise<boolean> {
  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(text);
      return true;
    }
  } catch {
    /* fall through to the legacy path */
  }
  const area = document.createElement('textarea');
  area.value = text;
  document.body.appendChild(area);
  area.select();
  const ok = document.execCommand?.('copy') ?? false;
  area.remove();
  return ok;
}

/** "Draft reply" for one attention row. Drafts are requested only on click. */
export default function DraftPanel({ message }: { message: Message }) {
  const [state, setState] = useState<State>({ status: 'idle' });
  const [copyFailed, setCopyFailed] = useState(false);
  const textRef = useRef<HTMLTextAreaElement>(null);

  async function draft() {
    setState({ status: 'loading' });
    setCopyFailed(false);
    try {
      const d = await requestDraft({
        message_id: message.message_id,
        customer_id: message.customer_id,
        subject: message.subject,
        body: message.body,
      });
      if (d.blocked || !d.draft) {
        setState({ status: 'blocked', warnings: d.warnings.length ? d.warnings : ['unsafe_draft_blocked'] });
      } else {
        setState({ status: 'ready', text: d.draft, language: d.language, approved: false });
      }
    } catch {
      setState({ status: 'blocked', warnings: ['network_error'] });
    }
  }

  async function approve() {
    if (state.status !== 'ready' || !state.text.trim()) return;
    const ok = await copyText(state.text);
    setCopyFailed(!ok);
    setState({ ...state, approved: ok });
    if (!ok) {
      // Clipboard blocked (permissions, embedded browser): select the text so Ctrl+C is one step.
      textRef.current?.focus();
      textRef.current?.select();
    }
  }

  return (
    <div className="draft">
      <button type="button" data-testid="draft-button" onClick={draft} disabled={state.status === 'loading'}>
        {state.status === 'loading' ? 'در حال نوشتن پیش‌نویس…' : state.status === 'idle' ? 'پیش‌نویس پاسخ' : 'پیش‌نویس دوباره'}
      </button>

      {state.status === 'blocked' && (
        <div className="draft-warning" role="alert" data-testid="draft-warning">
          <strong>پیش‌نویس قابل نمایش نیست.</strong>
          <ul>
            {state.warnings.map((w) => <li key={w}>{warningText(w)}</li>)}
          </ul>
          <span>پاسخ را خودتان بنویسید؛ هیچ پیامی بدون تأیید شما ارسال نمی‌شود.</span>
        </div>
      )}

      {state.status === 'ready' && (
        <div className="draft-editor">
          <label className="muted" htmlFor={`draft-${message.message_id}`}>
            پیش‌نویس هوش مصنوعی — پیش از تأیید بازبینی و ویرایش کنید. وعدهٔ مالی یا زمانی فقط با شما.
          </label>
          <textarea
            id={`draft-${message.message_id}`}
            ref={textRef}
            data-testid="draft-text"
            dir={state.language === 'fa' ? 'rtl' : 'ltr'}
            lang={state.language}
            rows={5}
            value={state.text}
            onChange={(e) => setState({ ...state, text: e.target.value, approved: false })}
          />
          <div className="draft-actions">
            <button type="button" data-testid="draft-approve" onClick={approve} disabled={!state.text.trim()}>
              تأیید و کپی متن
            </button>
            {state.approved && <span className="ok" role="status">کپی شد ✓ (ارسال خودکار انجام نمی‌شود)</span>}
            {copyFailed && <span className="error" role="alert">کپی خودکار ممکن نشد؛ متن انتخاب شد، با Ctrl+C کپی کنید.</span>}
          </div>
        </div>
      )}
    </div>
  );
}
