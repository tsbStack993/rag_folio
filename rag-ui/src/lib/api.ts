import type { ChatSession, Message, Subject, User } from '../types/workspace'

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000').replace(/\/$/, '')

export class ApiError extends Error {
  readonly status: number

  constructor(message: string, status: number) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

async function request<T>(
  path: string,
  options: RequestInit = {},
  accessToken?: string | null,
): Promise<T> {
  const headers = new Headers(options.headers)
  if (options.body) headers.set('Content-Type', 'application/json')
  if (accessToken) headers.set('Authorization', `Bearer ${accessToken}`)

  let response: Response
  try {
    response = await fetch(`${API_BASE_URL}${path}`, { ...options, headers })
  } catch (error) {
    throw new ApiError(
      error instanceof Error ? `Could not reach the API: ${error.message}` : 'Could not reach the API',
      0,
    )
  }

  if (!response.ok) {
    const body: unknown = await response.json().catch(() => null)
    const detail =
      body && typeof body === 'object' && 'detail' in body && typeof body.detail === 'string'
        ? body.detail
        : `API request failed (${response.status})`
    throw new ApiError(detail, response.status)
  }

  if (response.status === 204) return undefined as T
  return response.json() as Promise<T>
}

export type AuthResponse = {
  accessToken: string
  user: User
}

export const api = {
  subjects: () => request<Subject[]>('/api/v1/subjects'),
  register: (email: string, password: string) =>
    request<AuthResponse>('/api/v1/auth/register', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    }),
  login: (email: string, password: string) =>
    request<AuthResponse>('/api/v1/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    }),
  me: (accessToken: string) => request<User>('/api/v1/auth/me', {}, accessToken),
  chatSessions: (accessToken: string, subjectId?: string) => {
    const query = subjectId ? `?subject_id=${encodeURIComponent(subjectId)}` : ''
    return request<ChatSession[]>(`/api/v1/chat-sessions${query}`, {}, accessToken)
  },
  createChatSession: (accessToken: string, subjectId: string) =>
    request<ChatSession>(
      '/api/v1/chat-sessions',
      { method: 'POST', body: JSON.stringify({ subjectId }) },
      accessToken,
    ),
  messages: (accessToken: string, sessionId: string) =>
    request<Message[]>(`/api/v1/chat-sessions/${encodeURIComponent(sessionId)}/messages`, {}, accessToken),
  createMessage: (accessToken: string, sessionId: string, content: string) =>
    request<Message>(
      `/api/v1/chat-sessions/${encodeURIComponent(sessionId)}/messages`,
      { method: 'POST', body: JSON.stringify({ content }) },
      accessToken,
    ),
}
