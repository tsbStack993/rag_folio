export type Subject = {
  id: string
  name: string
  slug: string
  description: string | null
  vectorCollectionName: string
  createdAt: string
}

export type User = {
  id: string
  email: string
  createdAt: string
}

export type ChatSession = {
  id: string
  userId: string
  subjectId: string
  title: string
  createdAt: string
  updatedAt: string
}

export type Source = {
  id?: string
  title: string
  page: number
  score: number
}

export type Message = {
  id: string
  sessionId: string
  sender: 'user' | 'assistant'
  content: string
  sources: Source[]
  ragMetadata: Record<string, unknown>
  createdAt: string
  isStreaming?: boolean
}
