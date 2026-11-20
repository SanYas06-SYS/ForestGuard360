const tokenKey = 'vanrakshak:tab-session'
export const getToken = () => sessionStorage.getItem(tokenKey)
export function clearSession() { sessionStorage.removeItem(tokenKey) }

export async function api(path, options = {}) {
  const token = getToken()
  const response = await fetch(path, {
    ...options,
    credentials: 'omit',
    cache: 'no-store',
    headers: { ...(options.body && !(options.body instanceof FormData) ? { 'Content-Type': 'application/json' } : {}), ...(token ? { Authorization: `Bearer ${token}` } : {}), ...options.headers },
  })
  if (response.status === 204) return null
  const result = await response.json().catch(() => ({}))
  if (!response.ok) {
    if (response.status === 401 && token && token === getToken() && !path.startsWith('/api/auth/')) {
      clearSession()
      window.dispatchEvent(new Event('session-expired'))
    }
    throw new Error(result.error || `Request failed (${response.status}).`)
  }
  if (result.token && (path === '/api/auth/login' || path === '/api/auth/register')) sessionStorage.setItem(tokenKey, result.token)
  return result
}
