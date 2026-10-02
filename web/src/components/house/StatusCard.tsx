import { useMutation } from '@tanstack/react-query'
import { ArrowUpRight } from 'lucide-react'
import { api } from '@/api/client'
import { useRefreshHouse } from '@/api/queries'
import { type HouseDetail, type Status, STATUSES, STATUS_LABELS } from '@/api/types'
import { Button, buttonVariants } from '@/components/ui/button'
import { statusCard } from '@/lib/status'
import { selectClass } from '@/lib/ui'
import { cn } from '@/lib/utils'

/** Where the house is in our process, with the likely next steps one tap away. The
 *  <select> reaches any status. While a change saves, the card already shows it. */
export function StatusCard({ detail }: { detail: HouseDetail }) {
  const h = detail.house
  const refresh = useRefreshHouse()
  const set = useMutation({
    mutationFn: (s: Status) => api.setStatus(h.id, s),
    onSettled: () => refresh(h.id),
  })
  const shown = set.isPending ? set.variables : h.status
  const card = statusCard(shown, detail.status_history)
  return (
    <section aria-labelledby="status-title"
      className="flex flex-col gap-4 bg-sand px-5 py-5 lg:flex-row lg:items-center lg:justify-between lg:px-7">
      <div className="space-y-0.5">
        <p id="status-title" className="text-lg font-bold">{card.title}</p>
        <p className="text-[15px]">{card.text}</p>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        {card.actions.map((a, i) => (
          <Button key={a.label} variant={i === 0 ? 'default' : 'outline'} disabled={set.isPending}
            className={cn('h-11 px-5', i > 0 && 'border-foreground bg-transparent')}
            onClick={() => set.mutate(a.to)}>
            {a.label}
          </Button>
        ))}
        {shown === 'not_visited' && h.listing_url && (
          <a href={h.listing_url} target="_blank" rel="noreferrer"
            className={cn(buttonVariants({ variant: 'outline' }), 'h-11 border-foreground bg-transparent px-5')}>
            Open the listing<ArrowUpRight aria-hidden />
          </a>
        )}
        <select aria-label="Status" className={cn(selectClass, 'bg-background/60')} value={shown}
          onChange={e => set.mutate(e.target.value as Status)}>
          {STATUSES.map(s => <option key={s} value={s}>{STATUS_LABELS[s]}</option>)}
        </select>
      </div>
    </section>
  )
}
