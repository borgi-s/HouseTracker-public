import { QueryClientProvider } from '@tanstack/react-query'
import { useState } from 'react'
import { createBrowserRouter, RouterProvider } from 'react-router'
import { SessionGate } from '@/components/SessionGate'
import { Toaster } from '@/components/ui/sonner'
import { makeQueryClient } from '@/queryClient'
import { Shell } from '@/routes/Shell'

// A data router (not <BrowserRouter>) so a page can block leaving it (useBlocker).
// Shell keeps its own <Routes>; this one route only hosts it.
const router = createBrowserRouter([{ path: '*', element: <SessionGate><Shell /></SessionGate> }])

export default function App() {
  const [client] = useState(makeQueryClient)
  return (
    <QueryClientProvider client={client}>
      <RouterProvider router={router} />
      <Toaster position="top-center" />
    </QueryClientProvider>
  )
}
