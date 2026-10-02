import { money } from '@/lib/format'

/** The asking price, or for a house sold at another price the asking price struck
 *  through with the sold price beside it. Styling (size, weight) comes from the parent. */
export function Price({ price, sold }: { price: number | null; sold: number | null }) {
  if (sold == null || sold === price) return <>{money(price)}</>
  return (
    <span className="inline-flex flex-wrap items-baseline gap-x-2">
      <span aria-hidden className="contents">
        {price != null && <s className="text-[0.7em] font-medium text-muted-foreground">{money(price)}</s>}
        <span>{money(sold)}</span>
      </span>
      <span className="sr-only">Asking price {money(price)}, sold for {money(sold)}</span>
    </span>
  )
}
