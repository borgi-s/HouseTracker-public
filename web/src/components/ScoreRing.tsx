import { score5 } from '@/lib/format'
import { cn } from '@/lib/utils'

const TONE = { a: 'var(--person-a)', b: 'var(--person-b)', both: 'var(--foreground)' } as const

/** An overall (0..1) as a ring filled to its share of 5, the score in the middle. The
 *  middle is see-through (a mask), so the ring sits on any background. */
export function ScoreRing({ name, value, tone, size = 'lg' }: {
  name: string; value: number | null | undefined; tone: keyof typeof TONE; size?: 'lg' | 'sm'
}) {
  const pct = value == null ? 0 : Math.round(value * 100)
  const width = size === 'lg' ? 7 : 4
  const mask = `radial-gradient(farthest-side, transparent calc(100% - ${width}px), #000 calc(100% - ${width}px + 1px))`
  return (
    <div role="img" aria-label={`${name} ${score5(value)}`}
      className={cn('flex items-center', size === 'lg' ? 'flex-col gap-2' : 'gap-2')}>
      <div aria-hidden className={cn('relative grid place-items-center',
        size === 'lg' ? 'size-24 text-[1.75rem] font-semibold' : 'size-10 text-[13px] font-bold')}>
        <span className="absolute inset-0 rounded-full"
          style={{ background: `conic-gradient(${TONE[tone]} ${pct}%, var(--track) 0)`, mask, WebkitMask: mask }} />
        {score5(value)}
      </div>
      <span aria-hidden className={cn('text-sm font-semibold',
        tone === 'a' && 'text-person-a', tone === 'b' && 'text-person-b')}>{name}</span>
    </div>
  )
}
