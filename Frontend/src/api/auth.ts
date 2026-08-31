import { authHeaders, setToken, triggerLogout } from '@/lib/auth'

const API_BASE = 'http://localhost:8000/api'

export interface AuthUser {
  id: string
  email: string
  fullName: string
}

interface AuthResponse {
  access_token: string
  user: { id: string; email: string; full_name: string }
}

function mapUser(u: AuthResponse['user']): AuthUser {
  return { id: u.id, email: u.email, fullName: u.full_name }
}

async function parseAuthError(res: Response): Promise<string> {
  try {
    const data = await res.json()
    return data.detail || 'Something went wrong'
  } catch {
    return 'Something went wrong'
  }
}

export async function register(email: string, password: string, fullName: string): Promise<AuthUser> {
  const res = await fetch(`${API_BASE}/auth/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password, full_name: fullName }),
  })
  if (!res.ok) throw new Error(await parseAuthError(res))
  const data: AuthResponse = await res.json()
  setToken(data.access_token)
  return mapUser(data.user)
}

export async function login(email: string, password: string): Promise<AuthUser> {
  const res = await fetch(`${API_BASE}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  })
  if (!res.ok) throw new Error(await parseAuthError(res))
  const data: AuthResponse = await res.json()
  setToken(data.access_token)
  return mapUser(data.user)
}

/** Validates the stored token and returns the current user, or null if not logged in / expired. */
export async function fetchCurrentUser(): Promise<AuthUser | null> {
  const headers = authHeaders()
  if (!headers.Authorization) return null

  const res = await fetch(`${API_BASE}/auth/me`, { headers })
  if (!res.ok) {
    if (res.status === 401) triggerLogout()
    return null
  }
  const u = await res.json()
  return { id: u.id, email: u.email, fullName: u.full_name }
}

export function logout(): void {
  triggerLogout()
}
