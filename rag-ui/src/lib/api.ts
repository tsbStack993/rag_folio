import type { ChatSession, Message, Source, Subject, User } from '../types/workspace'

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000').replace(/\/$/, '')

export class ApiError extends Error {
  readonly status: number

  constructor(message: string, status: number) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

type StreamSources = {
  sources: Source[]
  userMessage: Message
}

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === 'object' && value !== null && !Array.isArray(value)

const isSource = (value: unknown): value is Source =>
  isRecord(value)
  && typeof value.title === 'string'
  && typeof value.page === 'number'
  && typeof value.score === 'number'
  && (value.id === undefined || typeof value.id === 'string')

const isMessage = (value: unknown): value is Message =>
  isRecord(value)
  && typeof value.id === 'string'
  && typeof value.sessionId === 'string'
  && (value.sender === 'user' || value.sender === 'assistant')
  && typeof value.content === 'string'
  && Array.isArray(value.sources)
  && value.sources.every(isSource)
  && isRecord(value.ragMetadata)
  && typeof value.createdAt === 'string'

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
  streamChat: async (
    accessToken: string,
    sessionId: string,
    content: string,
    callbacks: {
      onSources: (payload: StreamSources) => void
      onToken: (token: string) => void
      onComplete: (message: Message) => void
    },
    signal: AbortSignal,
  ) => {
    let response: Response
    try {
      response = await fetch(
        `${API_BASE_URL}/api/v1/chats/${encodeURIComponent(sessionId)}/stream`,
        {
          method: 'POST',
          headers: {
            Authorization: `Bearer ${accessToken}`,
            'Content-Type': 'application/json',
            Accept: 'text/event-stream',
          },
          body: JSON.stringify({ content }),
          signal,
        },
      )
    } catch (error) {
      if (signal.aborted) throw error
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
    if (!response.body) throw new ApiError('The API did not return a streaming response', response.status)

    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    let completed = false

    const processEvent = (event: string) => {
      const data = event
        .split(/\r?\n/)
        .filter((line) => line.startsWith('data:'))
        .map((line) => line.slice(5).trimStart())
        .join('\n')
      if (!data) return
      const payload: unknown = JSON.parse(data)
      if (!isRecord(payload) || typeof payload.type !== 'string') {
        throw new ApiError('The API returned an invalid streaming event', response.status)
      }
      if (payload.type === 'sources') {
        if (
          !Array.isArray(payload.sources)
          || !payload.sources.every(isSource)
          || !isMessage(payload.userMessage)
        ) {
          throw new ApiError('The API returned invalid source citations', response.status)
        }
        callbacks.onSources({
          sources: payload.sources,
          userMessage: payload.userMessage,
        } satisfies StreamSources)
      } else if (payload.type === 'token' && typeof payload.content === 'string') {
        callbacks.onToken(payload.content)
      } else if (payload.type === 'done' && isMessage(payload.assistantMessage)) {
        callbacks.onComplete(payload.assistantMessage)
        completed = true
      } else if (payload.type === 'error' && typeof payload.message === 'string') {
        throw new ApiError(payload.message, response.status)
      }
    }

    try {
      while (true) {
        const { done, value } = await reader.read()
        buffer += decoder.decode(value, { stream: !done })
        const events = buffer.split(/\r?\n\r?\n/)
        buffer = events.pop() ?? ''
        for (const event of events) processEvent(event)
        if (done) {
          if (buffer.trim()) processEvent(buffer)
          break
        }
      }
    } finally {
      reader.releaseLock()
    }
    if (!completed) throw new ApiError('The response stream ended before completion', response.status)
  },
}
