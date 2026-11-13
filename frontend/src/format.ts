import type { Category } from './types';

const CATEGORY_FA: Record<Category, string> = {
  delivery: 'ارسال و تحویل',
  payment: 'پرداخت',
  refund: 'بازگشت وجه',
  product_quality: 'کیفیت کالا',
  account: 'حساب کاربری',
  other: 'سایر',
};

export function formatCategory(cat: string): string {
  return CATEGORY_FA[cat as Category] ?? cat;
}

/** Persian digits for display; attributes for QA stay Latin. */
export function faNumber(n: number): string {
  return n.toLocaleString('fa-IR');
}

export function formatPercent(part: number, total: number): string {
  const pct = total > 0 && Number.isFinite(part) ? (part / total) * 100 : 0;
  return `${pct.toLocaleString('fa-IR', { minimumFractionDigits: 1, maximumFractionDigits: 1 })}٪`;
}

/** "۱ ساعت و ۵ دقیقه" for a number of business minutes (sign ignored). */
export function formatDuration(minutes: number): string {
  const abs = Math.abs(minutes);
  const h = Math.floor(abs / 60);
  const m = abs % 60;
  if (h && m) return `${faNumber(h)} ساعت و ${faNumber(m)} دقیقه`;
  if (h) return `${faNumber(h)} ساعت`;
  return `${faNumber(m)} دقیقه`;
}

/** Text for the countdown column. */
export function describeTimeLeft(minutes: number): string {
  if (minutes > 0) return `${formatDuration(minutes)} تا پایان مهلت`;
  if (minutes === 0) return 'مهلت همین حالا تمام شد';
  return `${formatDuration(minutes)} از مهلت گذشته`;
}

/** Tehran time, Persian calendar, for display. */
export function formatDate(iso: string | null): string {
  if (!iso) return '—';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString('fa-IR', {
    timeZone: 'Asia/Tehran', year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit',
  });
}

export const WARNING_FA: Record<string, string> = {
  llm_unavailable: 'سرویس هوش مصنوعی الان در دسترس نیست؛ لطفاً پاسخ را خودتان بنویسید.',
  unsafe_draft_blocked: 'پیش‌نویسِ امن ساخته نشد، بنابراین نمایش داده نمی‌شود.',
  mentions_money_or_refund: 'به پول، بازگشت وجه یا جبران خسارت اشاره داشت.',
  contains_number: 'عدد یا مبلغ داشت.',
  mentions_date_or_time: 'به تاریخ، زمان یا مدت اشاره داشت.',
  promises_outcome: 'وعده یا تأیید نتیجه داشت.',
  contains_link_or_contact: 'لینک یا اطلاعات تماس داشت.',
  asks_for_sensitive_data: 'اطلاعات حساس (رمز، شماره کارت، کد) خواسته بود.',
  wrong_language: 'به زبان مشتری نبود.',
  empty_draft: 'پیش‌نویس خالی بود.',
  too_long: 'پیش‌نویس بیش از حد طولانی بود.',
  internal_error: 'خطای داخلی هنگام ساخت پیش‌نویس.',
  network_error: 'ارتباط با سرور برقرار نشد.',
};

export function warningText(code: string): string {
  return WARNING_FA[code] ?? code;
}
