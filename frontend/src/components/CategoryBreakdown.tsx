import { CATEGORIES, type Category } from '../types';
import { faNumber, formatCategory, formatPercent } from '../format';

interface Props {
  counts: Partial<Record<Category, number>>;
  total: number;
}

export default function CategoryBreakdown({ counts, total }: Props) {
  return (
    <section className="card" aria-labelledby="categories-title">
      <h2 id="categories-title">مشتریان با چه مشکلی درگیرند؟</h2>
      <p className="muted">بر اساس پیام‌های یکتا (پیام‌های تکراری یک بار شمرده می‌شوند).</p>
      <ul className="breakdown">
        {CATEGORIES.map((cat) => {
          const n = counts[cat] ?? 0; // a missing category is 0, never NaN
          const width = total > 0 ? (n / total) * 100 : 0;
          return (
            <li key={cat}>
              <span className="cat-name">{formatCategory(cat)}</span>
              <span className="bar"><span className="bar-fill" style={{ width: `${width}%` }} /></span>
              <span className="cat-count">{faNumber(n)}</span>
              <span className="cat-pct">{formatPercent(n, total)}</span>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
