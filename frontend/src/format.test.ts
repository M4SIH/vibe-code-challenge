import { describeTimeLeft, formatCategory, formatDuration, formatPercent, warningText } from './format';

describe('format helpers', () => {
  it('formats percentages without NaN', () => {
    expect(formatPercent(1, 4)).toBe('۲۵٫۰٪');
    expect(formatPercent(0, 0)).toBe('۰٫۰٪');
    expect(formatPercent(Number.NaN, 10)).toBe('۰٫۰٪');
  });
  it('uses Persian category labels', () => {
    expect(formatCategory('product_quality')).toBe('کیفیت کالا');
    expect(formatCategory('unknown')).toBe('unknown');
  });
  it('describes business time left and overdue', () => {
    expect(formatDuration(80)).toBe('۱ ساعت و ۲۰ دقیقه');
    expect(describeTimeLeft(45)).toBe('۴۵ دقیقه تا پایان مهلت');
    expect(describeTimeLeft(0)).toBe('مهلت همین حالا تمام شد');
    expect(describeTimeLeft(-120)).toBe('۲ ساعت از مهلت گذشته');
  });
  it('translates draft warning codes for Sara', () => {
    expect(warningText('mentions_money_or_refund')).toContain('بازگشت وجه');
    expect(warningText('something_new')).toBe('something_new');
  });
});
