/**
 * Customer text with order references highlighted, rendered as plain React
 * text nodes. Never use innerHTML here: message bodies come from anyone on the
 * internet and the exports contain <script> and <img onerror> payloads.
 */
const ORDER_REF = /BZ\s*[-_‐-―]?\s*[0-9۰-۹٠-٩]+/gi;

export default function OrderText({ text }: { text: string }) {
  const parts: (string | JSX.Element)[] = [];
  let last = 0;
  for (const match of text.matchAll(ORDER_REF)) {
    const start = match.index ?? 0;
    if (start > last) parts.push(text.slice(last, start));
    parts.push(<mark key={start} className="order-ref" dir="ltr">{match[0]}</mark>);
    last = start + match[0].length;
  }
  if (last < text.length) parts.push(text.slice(last));
  return <>{parts}</>;
}
