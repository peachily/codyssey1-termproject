export class ApiError extends Error {
  constructor(status, message) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

async function request(path, { method = 'GET', body, signal } = {}) {
  const response = await fetch(`/api/auth/${path}`, {
    method,
    credentials: 'include',
    signal,
    headers: { Accept: 'application/json', ...(body ? { 'Content-Type': 'application/json' } : {}) },
    ...(body ? { body: JSON.stringify(body) } : {}),
  })
  if (!response.ok) throw new ApiError(response.status, 'Authentication request failed')
  let data
  try {
    data = await response.json()
  } catch {
    throw new ApiError(response.status, 'Invalid authentication response')
  }
  const expectedStatus = path === 'signup' ? 201 : 200
  const valid = path === 'logout'
    ? data?.message === 'logged out'
    : Number.isSafeInteger(data?.id) && data.id > 0 && typeof data?.username === 'string' && data.username.length > 0
  if (response.status !== expectedStatus || !valid) throw new ApiError(response.status, 'Invalid authentication response')
  return path === 'logout' ? data : { id: data.id, username: data.username }
}

export const signup = (credentials, signal) => request('signup', { method: 'POST', body: credentials, signal })
export const login = (credentials, signal) => request('login', { method: 'POST', body: credentials, signal })
export const logout = (signal) => request('logout', { method: 'POST', signal })
export const getMe = (signal) => request('me', { signal })

export async function sendChat(message, signal) {
  const response = await fetch('/api/chat', {
    method: 'POST', credentials: 'include', signal,
    headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
    body: JSON.stringify({ message }),
  })
  if (!response.ok) throw new ApiError(response.status, 'Chat request failed')
  let data
  try { data = await response.json() } catch { throw new ApiError(200, 'Invalid chat response') }
  if (response.status !== 200 || !Number.isSafeInteger(data?.id) || data.id <= 0 ||
      typeof data.question !== 'string' || typeof data.answer !== 'string' || !data.answer.trim() ||
      typeof data.created_at !== 'string' || Number.isNaN(Date.parse(data.created_at))) {
    throw new ApiError(response.status, 'Invalid chat response')
  }
  return data
}

export async function requestPrescription(signal) {
  const response = await fetch('/api/prescription', {
    method: 'POST', credentials: 'include', signal,
    headers: { Accept: 'application/json' },
  })
  if (!response.ok) throw new ApiError(response.status, 'Prescription request failed')
  let data
  try { data = await response.json() } catch { throw new ApiError(response.status, 'Invalid prescription response') }
  const pairs = { ANXIETY: 'BLUE', SADNESS: 'PURPLE', LONELINESS: 'PINK', STRESS: 'GREEN', EXHAUSTION: 'YELLOW' }
  if (response.status !== 200 || !data || typeof data.keyword !== 'string' ||
      typeof data.color !== 'string' || !Object.hasOwn(pairs, data.keyword) ||
      pairs[data.keyword] !== data.color || typeof data.message !== 'string' || !data.message.trim()) {
    throw new ApiError(response.status, 'Invalid prescription response')
  }
  return { keyword: data.keyword, color: data.color, message: data.message }
}
