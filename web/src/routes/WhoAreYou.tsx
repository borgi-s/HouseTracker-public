import { useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '@/api/client'
import { keys, usePersons } from '@/api/queries'
import { AddPersonForm } from '@/components/AddPersonForm'
import { Button } from '@/components/ui/button'
import { PERSON, slotOf } from '@/lib/person'
import { cn } from '@/lib/utils'

/** The name picker (parent spec §10): attribution, not authentication. */
export function WhoAreYou() {
  const qc = useQueryClient()
  const persons = usePersons()
  const pick = useMutation({
    mutationFn: api.pickPerson,
    onSuccess: session => qc.setQueryData(keys.session, session),
  })
  const list = persons.data ?? []
  return (
    <div className="mx-auto flex min-h-dvh max-w-sm flex-col justify-center gap-6 p-6">
      <h1 className="text-center text-2xl font-extrabold">Who are you?</h1>
      <div className="grid gap-3">
        {list.map(p => {
          const slot = slotOf(list, p.id)
          return (
            <Button key={p.id} className={cn('h-16 rounded-2xl text-lg', slot && PERSON[slot].solid)}
              onClick={() => pick.mutate(p.id)}>
              {p.name}
            </Button>
          )
        })}
      </div>
      <AddPersonForm />
    </div>
  )
}
