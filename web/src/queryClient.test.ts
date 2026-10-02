import { toast } from 'sonner'
import { expect, test, vi } from 'vitest'
import { ApiError } from '@/api/client'
import { keys } from '@/api/queries'
import { makeQueryClient } from '@/queryClient'

function failingMutation(error: Error) {
  const qc = makeQueryClient()
  qc.setQueryData(keys.session, { person: { id: 'alex', name: 'Alex' } })
  const m = qc.getMutationCache().build(qc, { mutationFn: () => Promise.reject(error) })
  return { qc, run: () => m.execute(undefined) }
}

test('a 401 from any write signs the person out', async () => {
  const { qc, run } = failingMutation(new ApiError(401, 'no person selected'))
  await expect(run()).rejects.toThrow('no person selected')
  expect(qc.getQueryData(keys.session)).toEqual({ person: null })
})

test('any other failed write toasts its detail', async () => {
  const spy = vi.spyOn(toast, 'error')
  const { qc, run } = failingMutation(new ApiError(502, 'fetch failed: timeout'))
  await expect(run()).rejects.toThrow()
  expect(spy).toHaveBeenCalledWith('fetch failed: timeout')
  expect(qc.getQueryData(keys.session)).toEqual({ person: { id: 'alex', name: 'Alex' } })
})
