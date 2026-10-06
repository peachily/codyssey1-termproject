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
