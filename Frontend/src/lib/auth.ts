const TOKEN_KEY = 'emunim_token'

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY)
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token)
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY)
}

export function authHeaders(): Record<string, string> {
  const token = getToken()
  return token ? { Authorization: `Bearer ${token}` } : {}
}

/** Dispatched whenever a request comes back 401 (expired/invalid session) or the user logs out. */
export const AUTH_LOGOUT_EVENT = 'emunim:logout'

export function triggerLogout(): void {
  clearToken()
  window.dispatchEvent(new Event(AUTH_LOGOUT_EVENT))
}
