import { faNumber } from '../format';

interface Props {
  total: number;
  attention: number;
  urgent: number;
  resends: number;
}

export default function SummaryTiles({ total, attention, urgent, resends }: Props) {
  return (
    <section className="tiles">
      <div className="card tile urgent" data-testid="urgent-count">
        <div className="tile-label">فوری (از مهلت ۲ ساعت کاری گذشته)</div>
        <div className="tile-value">{faNumber(urgent)}</div>
      </div>
      <div className="card tile">
        <div className="tile-label">نیازمند رسیدگی</div>
        <div className="tile-value">{faNumber(attention)}</div>
      </div>
      <div className="card tile">
        <div className="tile-label">پیام یکتا</div>
        <div className="tile-value" data-testid="total">{faNumber(total)}</div>
      </div>
      <div className="card tile">
        <div className="tile-label">پیام تکراری (یک بار شمرده شد)</div>
        <div className="tile-value">{faNumber(resends)}</div>
      </div>
    </section>
  );
}
