import { useCriteria, usePeople } from '@/api/queries'
import type { HouseDetail } from '@/api/types'
import { NotesPanel } from '@/components/house/NotesPanel'
import { ScoresPanel } from '@/components/house/ScoresPanel'
import { ScoreRing } from '@/components/ScoreRing'
import { apartSentence } from '@/lib/apart'
import { combined } from '@/lib/format'

/** Our overalls as rings, where we differ in one sentence, notes, then every criterion. */
export function WhereWeStand({ detail }: { detail: HouseDetail }) {
  const { pair, me, other } = usePeople()
  const criteria = useCriteria().data ?? []
  const sentence = me && other ? apartSentence(criteria, detail.scores[me.id], detail.scores[other.id]) : null
  return (
    <section id="our-take" aria-labelledby="our-take-title"
      className="grid scroll-mt-24 gap-8 rounded-2xl bg-muted p-5 lg:grid-cols-[22rem_1fr] lg:gap-12 lg:p-9">
      <div className="space-y-5">
        <h2 id="our-take-title" className="text-2xl font-bold tracking-tight lg:text-[1.75rem]">Where we stand</h2>
        <div className="flex justify-around lg:justify-start lg:gap-5">
          {pair.map((p, i) => <ScoreRing key={p.id} name={p.name} value={detail.overall[p.id]} tone={i === 0 ? 'a' : 'b'} />)}
          {pair.length === 2 && <ScoreRing name="Together" value={combined(detail.overall, pair.map(p => p.id))} tone="both" />}
        </div>
        {sentence && <p className="text-[15px] leading-relaxed">{sentence}</p>}
        <NotesPanel detail={detail} />
      </div>
      <ScoresPanel detail={detail} />
    </section>
  )
}
