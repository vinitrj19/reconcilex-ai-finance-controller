// Thin fetch wrapper for the real backend. Every function here has an exact
// mock counterpart in mockApi.ts with the same signature and return type,
// so ApiProvider (index.ts) can switch between them without touching any
// component.

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8001/api/v1'

export class ApiError extends Error {
  status: number
  constructor(message: string, status: number) {
    super(message)
    this.status = status
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  })
  if (!res.ok) {
    const body = await res.text().catch(() => '')
    throw new ApiError(body || res.statusText, res.status)
  }
  return res.json() as Promise<T>
}

export const httpClient = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: 'POST', body: body ? JSON.stringify(body) : undefined }),
}
