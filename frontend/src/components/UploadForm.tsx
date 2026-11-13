import { useState, type FormEvent } from 'react';

interface Props {
  /** referenceTehran: optional "YYYY-MM-DDTHH:mm" in Tehran time, for replaying an old export. */
  onSubmit: (file: File, referenceTehran?: string) => void;
  loading: boolean;
}

export default function UploadForm({ onSubmit, loading }: Props) {
  const [file, setFile] = useState<File | null>(null);
  const [reference, setReference] = useState('');

  function submit(e: FormEvent) {
    e.preventDefault();
    if (file) onSubmit(file, reference || undefined);
  }

  return (
    <form className="card upload" onSubmit={submit}>
      <label>
        فایل خروجی پشتیبانی (CSV)
        <input data-testid="upload-input" type="file" accept=".csv,text/csv"
               onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
      </label>
      <details className="reference">
        <summary>بازپخش یک خروجی قدیمی (اختیاری)</summary>
        <label>
          «اکنون» را این زمان در نظر بگیر (به وقت تهران)؛ شمارش معکوس از همین زمان زنده ادامه می‌یابد
          <input type="datetime-local" dir="ltr" value={reference} onChange={(e) => setReference(e.target.value)} />
        </label>
      </details>
      <button type="submit" data-testid="analyze-button" disabled={!file || loading}>
        {loading ? 'در حال تحلیل… (ممکن است تا یک دقیقه طول بکشد)' : 'تحلیل'}
      </button>
    </form>
  );
}
