import { type ReactElement, useState } from 'react'
import { NoteForm } from '@/components/house/NotesPanel'
import { Dialog, DialogContent, DialogTitle, DialogTrigger } from '@/components/ui/dialog'

/** "Add note" from anywhere on the house page: the phone bar and the laptop summary. */
export function NoteDialog({ houseId, trigger }: { houseId: string; trigger: ReactElement }) {
  const [open, setOpen] = useState(false)
  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>{trigger}</DialogTrigger>
      <DialogContent aria-describedby={undefined}>
        <DialogTitle>Add a note</DialogTitle>
        <NoteForm houseId={houseId} onDone={() => setOpen(false)} />
      </DialogContent>
    </Dialog>
  )
}
