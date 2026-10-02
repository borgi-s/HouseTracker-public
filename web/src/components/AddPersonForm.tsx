import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { api } from '@/api/client'
import { keys } from '@/api/queries'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'

export function AddPersonForm() {
  const qc = useQueryClient()
  const [name, setName] = useState('')
  const add = useMutation({
    mutationFn: api.addPerson,
    onSuccess: () => {
      setName('')
      return qc.invalidateQueries({ queryKey: keys.persons })
    },
  })
  return (
    <form className="flex gap-2" onSubmit={e => { e.preventDefault(); if (name.trim()) add.mutate(name.trim()) }}>
      <Input aria-label="New person" placeholder="Add a person" value={name} onChange={e => setName(e.target.value)} />
      <Button type="submit" variant="outline" disabled={add.isPending}>Add</Button>
    </form>
  )
}
