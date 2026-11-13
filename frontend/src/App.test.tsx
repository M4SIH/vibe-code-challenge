import indexHtml from '../index.html?raw';
import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import App, { REFRESH_MS } from './App';
import { NOW, RESULT } from './testData';

type Call = { url: string; body?: unknown };

function mockServer(draft: (body: Record<string, string>) => unknown | Promise<unknown>) {
  const calls: Call[] = [];
  vi.stubGlobal('fetch', vi.fn(async (url: string, init?: RequestInit) => {
    if (url.startsWith('/api/analyze')) {
      calls.push({ url });
      return new Response(JSON.stringify(RESULT), { status: 200 });
    }
    const body = JSON.parse(String(init?.body));
    calls.push({ url, body });
    return new Response(JSON.stringify(await draft(body)), { status: 200 });
  }));
  return calls;
}

async function upload() {
  render(<App />);
  const file = new File(['message_id\n'], 'export.csv', { type: 'text/csv' });
  fireEvent.change(screen.getByTestId('upload-input'), { target: { files: [file] } });
  fireEvent.click(screen.getByTestId('analyze-button'));
  await screen.findAllByTestId('attention-row');
}

const row = (id: string) => screen.getAllByTestId('attention-row').find((r) => r.dataset.messageId === id)!;
const minutes = () => screen.getAllByTestId('attention-row').map((r) => Number(r.dataset.businessMinutesLeft));

beforeEach(() => {
  // Freeze the browser clock like the QA smoke tests; keep real setTimeout for waitFor.
  vi.useFakeTimers({ toFake: ['Date', 'setInterval', 'clearInterval'] });
  vi.setSystemTime(new Date(NOW));
});
afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe('page', () => {
  it('is Persian and right-to-left', () => {
    expect(indexHtml).toMatch(/<html lang="fa" dir="rtl">/);
  });
});

describe('dashboard with a frozen clock', () => {
  it('sends the browser time as now and lists rows in order with integer minutes', async () => {
    const calls = mockServer(() => ({}));
    await upload();
    expect(calls[0].url).toBe(`/api/analyze?now=${encodeURIComponent(NOW.replace('Z', '.000Z'))}`);
    const ids = screen.getAllByTestId('attention-row').map((r) => r.dataset.messageId);
    // ties (both -30) go to the one received earlier: it has waited longer
    expect(ids).toEqual(['M_OVERDUE_MORE', 'M_OVERDUE_BIG', 'M_ANSWER_LATER', 'M_ALMOST', 'M_ON_TIME']);
    expect(minutes()).toEqual([-210, -30, -30, 5, 90]);
    for (const r of screen.getAllByTestId('attention-row')) {
      expect(r.dataset.businessMinutesLeft).toMatch(/^-?\d+$/);
    }
  });

  it('urgent count matches the overdue rows in the list', async () => {
    mockServer(() => ({}));
    await upload();
    const overdue = minutes().filter((m) => m <= 0).length;
    expect(screen.getByTestId('urgent-count')).toHaveTextContent(overdue.toLocaleString('fa-IR'));
    expect(overdue).toBe(3);
  });

  it('keeps counting down live without re-uploading or calling the server', async () => {
    const calls = mockServer(() => ({}));
    await upload();
    expect(row('M_ALMOST').dataset.businessMinutesLeft).toBe('5');
    act(() => { vi.advanceTimersByTime(REFRESH_MS * 10); });  // 5 minutes later
    expect(row('M_ALMOST').dataset.businessMinutesLeft).toBe('0');
    expect(screen.getByTestId('urgent-count')).toHaveTextContent('۴');
    expect(calls).toHaveLength(1); // only the upload; no LLM/draft calls to stay live
  });

  it('refreshes at least once a minute', () => {
    expect(REFRESH_MS).toBeLessThanOrEqual(60_000);
  });

  it('renders customer text as text (no XSS) and never shows NaN', async () => {
    mockServer(() => ({}));
    await upload();
    expect(document.querySelector('img')).toBeNull();
    expect(document.querySelector('tbody script')).toBeNull();
    expect(screen.getByText(/onerror/)).toBeInTheDocument();
    expect(document.body.textContent).not.toContain('NaN');
    expect(screen.getAllByText('BZ-۱۲۳۴')[0].tagName).toBe('MARK'); // Persian-digit order ref highlighted
  });
});

describe('draft reply', () => {
  it('is only requested on click, editable, and approve copies the edited text', async () => {
    const calls = mockServer((b) => ({ message_id: b.message_id, draft: 'Thanks, we are checking.',
                                       language: 'en', blocked: false, warnings: [] }));
    const writeText = vi.fn(async () => {});
    Object.assign(navigator, { clipboard: { writeText } });
    await upload();
    expect(calls.filter((c) => c.url === '/api/draft')).toHaveLength(0);

    fireEvent.click(within(row('M_ON_TIME')).getByTestId('draft-button'));
    const text = await within(row('M_ON_TIME')).findByTestId('draft-text');
    expect(text.tagName).toBe('TEXTAREA');
    expect(calls.filter((c) => c.url === '/api/draft')).toHaveLength(1);
    expect(calls[1].body).toMatchObject({ message_id: 'M_ON_TIME', customer_id: 'C1' });

    fireEvent.change(text, { target: { value: 'Edited by Sara.' } });
    fireEvent.click(within(row('M_ON_TIME')).getByTestId('draft-approve'));
    await waitFor(() => expect(writeText).toHaveBeenCalledWith('Edited by Sara.'));
  });

  it('shows a warning instead of a blocked draft', async () => {
    mockServer((b) => ({ message_id: b.message_id, draft: '', language: 'fa', blocked: true,
                         warnings: ['unsafe_draft_blocked', 'mentions_money_or_refund'] }));
    await upload();
    fireEvent.click(within(row('M_ALMOST')).getByTestId('draft-button'));
    const warning = await within(row('M_ALMOST')).findByTestId('draft-warning');
    expect(warning).toHaveTextContent('بازگشت وجه');
    expect(within(row('M_ALMOST')).queryByTestId('draft-text')).toBeNull();
  });

  it('shows a warning when the request fails', async () => {
    mockServer(() => { throw new Error('network down'); });
    await upload();
    fireEvent.click(within(row('M_ALMOST')).getByTestId('draft-button'));
    expect(await within(row('M_ALMOST')).findByTestId('draft-warning')).toHaveTextContent('ارتباط');
  });

  it('when the clipboard is blocked, says so and selects the text for manual copy', async () => {
    mockServer((b) => ({ message_id: b.message_id, draft: 'Thanks, we are checking.', language: 'en',
                         blocked: false, warnings: [] }));
    Object.assign(navigator, { clipboard: { writeText: vi.fn(async () => { throw new Error('NotAllowedError'); }) } });
    document.execCommand = vi.fn(() => false);
    await upload();
    fireEvent.click(within(row('M_ON_TIME')).getByTestId('draft-button'));
    const text = (await within(row('M_ON_TIME')).findByTestId('draft-text')) as HTMLTextAreaElement;
    fireEvent.click(within(row('M_ON_TIME')).getByTestId('draft-approve'));
    expect(await within(row('M_ON_TIME')).findByText(/Ctrl\+C/)).toBeInTheDocument();
    expect(document.activeElement).toBe(text);
    expect(text.selectionEnd - text.selectionStart).toBe(text.value.length);
  });

  it('Persian drafts are right-to-left in the textarea', async () => {
    mockServer((b) => ({ message_id: b.message_id, draft: 'سلام، در حال بررسی هستیم.', language: 'fa',
                         blocked: false, warnings: [] }));
    await upload();
    fireEvent.click(within(row('M_ON_TIME')).getByTestId('draft-button'));
    expect(await within(row('M_ON_TIME')).findByTestId('draft-text')).toHaveAttribute('dir', 'rtl');
  });
});
