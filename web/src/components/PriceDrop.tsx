import { money } from '@/lib/format'
import { dropPct } from '@/lib/price'
import { cn } from '@/lib/utils'

/** The green "↓5%" bubble, shown while the price is below the original asking price. */
export function PriceDrop({ original, price, className }: {
  original: number | null; price: number | null; className?: string
}) {
  const pct = dropPct(original, price)
  if (pct == null) return null
  return (
    <span className={cn('inline-flex shrink-0 items-center rounded-full bg-drop px-2 py-0.5 text-xs font-bold leading-tight text-drop-foreground', className)}>
      <span aria-hidden>↓{pct}%</span>
      <span className="sr-only">Price reduced {pct}% from {money(original)}</span>
    </span>
  )
}
