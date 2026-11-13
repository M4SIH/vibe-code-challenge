export const CATEGORIES = [
  'delivery',
  'payment',
  'refund',
  'product_quality',
  'account',
  'other',
] as const;

export type Category = (typeof CATEGORIES)[number];

export interface Message {
  message_id: string;
  category: Category;
  is_urgent: boolean;
  order_ref: string | null;
  duplicate_of: string | null;
  customer_id: string;
  channel: string;
  received_at: string | null;
  answered_at: string | null;
  subject: string;
  body: string;
  severity: 'high' | 'normal';
  severity_hint: string | null;
  label_source?: 'llm' | 'keywords';
  answered: boolean;
  group_answered_at: string | null;
  answer_time_unknown: boolean;
  sla_deadline: string | null;
  business_minutes_left: number | null;
}

export interface DataQuality {
  records_read: number;
  rows_kept: number;
  blank_rows_skipped: number;
  rows_without_id_skipped: number;
  unparseable_received_at: string[];
  missing_received_at: string[];
  unparseable_answered_at: string[];
  answered_before_received: string[];
  duplicate_message_ids: string[];
  short_rows: string[];
  rows_with_extra_fields: string[];
}

export interface Classification {
  mode: 'llm' | 'cache+keywords' | 'keywords';
  llm_labels?: number;
  keyword_labels?: number;
  llm_error?: string | null;
}

export interface AnalyzeResult {
  total_unique_messages: number;
  category_counts: Partial<Record<Category, number>>;
  urgent_message_ids: string[];
  messages: Message[];
  data_quality?: DataQuality;
  classification?: Classification;
}

export interface Draft {
  message_id: string;
  draft: string;
  language: 'fa' | 'en';
  blocked: boolean;
  warnings: string[];
}
