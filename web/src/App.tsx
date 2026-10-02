import { QueryClientProvider } from '@tanstack/react-query'
import { useState } from 'react'
import { BrowserRouter } from 'react-router'
import { SessionGate } from '@/components/SessionGate'
import { Toaster } from '@/components/ui/sonner'
import { makeQueryClient } from '@/queryClient'
import { Shell } from '@/routes/Shell'

export default function App() {
  const [client] = useState(makeQueryClient)
  return (
    <QueryClientProvider client={client}>
      <BrowserRouter>
        <SessionGate><Shell /></SessionGate>
      </BrowserRouter>
      <Toaster position="top-center" />
    </QueryClientProvider>
  )
}
