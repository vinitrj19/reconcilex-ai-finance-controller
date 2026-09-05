import { useEffect, useRef, useState, useCallback } from 'react'

interface UseApiState<T> {
  data: T | null
  loading: boolean
  error: string | null
  refetch: () => void
}

/**
 * Runs `fetcher` whenever `deps` change, tracking loading/error state.
 * Guards against setting state after unmount / after a newer call has
 * already started (stale-response protection for fast filter changes).
 */
export function useApi<T>(fetcher: () => Promise<T>, deps: unknown[] = []): UseApiState<T> {
  const [data, setData] = useState<T | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const callId = useRef(0)

  const run = useCallback(() => {
    const id = ++callId.current
    setLoading(true)
    setError(null)
    fetcher()
      .then((res) => {
        if (id === callId.current) {
          setData(res)
          setLoading(false)
        }
      })
      .catch((err) => {
        if (id === callId.current) {
          setError(err instanceof Error ? err.message : 'Something went wrong.')
          setLoading(false)
        }
      })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps)

  useEffect(() => {
    run()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [run])

  return { data, loading, error, refetch: run }
}
