import { mockApi } from './mockApi'
import { realApi } from './realApi'

// The ONLY place that decides mock vs real. Every page/component imports
// `api` from here and never touches mockApi/realApi directly, so flipping
// VITE_USE_MOCK_API never requires touching UI code.
const useMock = import.meta.env.VITE_USE_MOCK_API !== 'false'

export const api = useMock ? mockApi : realApi
export const isMockApi = useMock
export type { ApiError } from './client'
