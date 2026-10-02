import { useState } from 'react'
import { toast } from 'sonner'
import { api } from '@/api/client'
import { useRefreshHouse } from '@/api/queries'
import type { Status } from '@/api/types'
import { NoteDialog } from '@/components/house/NoteDialog'
import { Button, buttonVariants } from '@/components/ui/button'
import { cn } from '@/lib/utils'

/** Spec §4.4: the three things you do at a viewing, always one thumb away. Sits above
 *  the phone nav bar; hidden on a laptop. */
export function CaptureBar({ houseId, status }: { houseId: string; status: Status }) {
  const refresh = useRefreshHouse()
  const [progress, setProgress] = useState<string | null>(null)

  async function upload(files: File[]) {
    for (const [i, file] of files.entries()) {
      setProgress(`Uploading ${i + 1} of ${files.length}…`)
      try {
        await api.uploadPhoto(houseId, file)
      } catch (e) {
        toast.error(`${file.name}: ${e instanceof Error ? e.message : String(e)}`)   // the rest continue
      }
    }
    setProgress(null)
    await refresh(houseId)
  }

  const big = 'h-12 flex-1 text-[15px]'
  return (
    <>
      {progress && (
        <div role="status" className="fixed inset-x-4 bottom-36 z-20 rounded-2xl bg-card p-3 text-center text-sm font-bold shadow lg:hidden">
          {progress}
        </div>
      )}
      <div className="fixed inset-x-0 bottom-[calc(3.5rem+env(safe-area-inset-bottom))] z-20 flex gap-2 border-t bg-background px-3 py-2.5 lg:hidden">
        <label className={cn(buttonVariants({ variant: 'outline' }), big, 'cursor-pointer')}>
          Add photo
          <input aria-label="Add photos" type="file" accept="image/*" capture="environment" multiple className="sr-only"
            onChange={e => {
              const files = [...(e.target.files ?? [])]      // copy before the reset clears the list
              e.target.value = ''
              if (files.length) void upload(files)
            }} />
        </label>
        <Button className={big} variant={status === 'not_visited' ? 'outline' : 'default'}
          onClick={() => document.getElementById('our-take')?.scrollIntoView?.({ behavior: 'smooth' })}>
          Rate
        </Button>
        <NoteDialog houseId={houseId} trigger={<Button variant="outline" className={big}>Add note</Button>} />
      </div>
    </>
  )
}
