import { create } from 'zustand'
import { createJSONStorage, persist } from 'zustand/middleware'
import { api, ApiError } from '../lib/api'
import type { ChatSession, Message, Subject, User } from '../types/workspace'

type WorkspaceState = {
  theme: 'dark' | 'light'
  currentUser: User | null
  accessToken: string | null
  subjects: Subject[]
  activeSubject: Subject | null
  activeSessionId: string | null
  sessions: ChatSession[]
  messages: Message[]
  isInitializing: boolean
  isLoading: boolean
  isSending: boolean
  isStreaming: boolean
  error: string | null
  sessionHistory: ChatSession[]
  initialize: () => Promise<void>
  authenticate: (email: string, password: string, registering: boolean) => Promise<void>
  clearError: () => void
  toggleTheme: () => void
  logout: () => void
  selectSubject: (subjectId: string) => Promise<void>
  clearSubject: () => void
  createSession: () => Promise<string | null>
  selectSession: (sessionId: string) => Promise<void>
  sendMessage: (content: string) => Promise<boolean>
  stopGeneration: () => void
}

const errorMessage = (error: unknown) =>
  error instanceof Error ? error.message : 'An unexpected API error occurred'

const sortSessions = (sessions: ChatSession[]) =>
  [...sessions].sort((first, second) => second.updatedAt.localeCompare(first.updatedAt))

export const useWorkspaceStore = create<WorkspaceState>()(
  persist(
    (set, get) => ({
      theme: 'dark',
      currentUser: null,
      accessToken: null,
      subjects: [],
      activeSubject: null,
      activeSessionId: null,
      sessions: [],
      messages: [],
      isInitializing: true,
      isLoading: false,
      isSending: false,
      isStreaming: false,
      error: null,
      sessionHistory: [],
      initialize: async () => {
        set({ isInitializing: true, error: null })
        const token = get().accessToken
        try {
          const loadedSubjects = await api.subjects()
          set({ subjects: loadedSubjects })
          if (!token) {
            set({
              currentUser: null,
              activeSubject: null,
              activeSessionId: null,
              sessions: [],
              messages: [],
              sessionHistory: [],
            })
            return
          }

          try {
            const [currentUser, history] = await Promise.all([
              api.me(token),
              api.chatSessions(token),
            ])
            const activeSubject = loadedSubjects.find(
              (subject) => subject.id === get().activeSubject?.id,
            ) ?? null
            const subjectSessions = activeSubject
              ? sortSessions(history.filter((session) => session.subjectId === activeSubject.id))
              : []
            const activeSessionId = subjectSessions.some(
              (session) => session.id === get().activeSessionId,
            )
              ? get().activeSessionId
              : subjectSessions[0]?.id ?? null
            set({
              currentUser,
              sessionHistory: history,
              activeSubject,
              sessions: subjectSessions,
              activeSessionId,
              messages: [],
            })
            if (activeSessionId) {
              const messages = await api.messages(token, activeSessionId)
              set({ messages })
            }
          } catch (error) {
            if (error instanceof ApiError && error.status === 401) {
              set({
                currentUser: null,
                accessToken: null,
                activeSubject: null,
                activeSessionId: null,
                sessions: [],
                messages: [],
                sessionHistory: [],
              })
            } else {
              throw error
            }
          }
        } catch (error) {
          set({ error: errorMessage(error) })
        } finally {
          set({ isInitializing: false })
        }
      },
      authenticate: async (email, password, registering) => {
        set({ isLoading: true, error: null })
        try {
          const result = registering
            ? await api.register(email, password)
            : await api.login(email, password)
          set({
            currentUser: result.user,
            accessToken: result.accessToken,
            activeSubject: null,
            activeSessionId: null,
            sessions: [],
            messages: [],
            sessionHistory: [],
          })
          const history = await api.chatSessions(result.accessToken)
          set({ sessionHistory: history })
        } catch (error) {
          set({ error: errorMessage(error) })
        } finally {
          set({ isLoading: false })
        }
      },
      clearError: () => set({ error: null }),
      toggleTheme: () =>
        set((state) => ({ theme: state.theme === 'dark' ? 'light' : 'dark' })),
      logout: () =>
        set({
          currentUser: null,
          accessToken: null,
          activeSubject: null,
          activeSessionId: null,
          sessions: [],
          messages: [],
          sessionHistory: [],
          error: null,
        }),
      selectSubject: async (subjectId) => {
        const subject = get().subjects.find((item) => item.id === subjectId)
        const token = get().accessToken
        if (!subject || !token) {
          set({ error: 'The selected subject is unavailable. Refresh and try again.' })
          return
        }
        set({
          activeSubject: subject,
          activeSessionId: null,
          sessions: [],
          messages: [],
          isLoading: true,
          error: null,
        })
        try {
          const sessions = sortSessions(await api.chatSessions(token, subjectId))
          const activeSessionId = sessions[0]?.id ?? null
          set((state) => ({
            sessions,
            sessionHistory: sortSessions([
              ...state.sessionHistory.filter((session) => session.subjectId !== subjectId),
              ...sessions,
            ]),
            activeSessionId,
          }))
          if (activeSessionId) {
            set({ messages: await api.messages(token, activeSessionId) })
          }
        } catch (error) {
          set({ error: errorMessage(error) })
        } finally {
          set({ isLoading: false })
        }
      },
      clearSubject: () =>
        set({
          activeSubject: null,
          activeSessionId: null,
          sessions: [],
          messages: [],
          error: null,
        }),
      createSession: async () => {
        const { accessToken, activeSubject } = get()
        if (!accessToken || !activeSubject || get().isLoading || get().isSending) return null
        set({ isLoading: true, error: null })
        try {
          const session = await api.createChatSession(accessToken, activeSubject.id)
          set((state) => ({
            sessions: [session, ...state.sessions],
            sessionHistory: [session, ...state.sessionHistory],
            activeSessionId: session.id,
            messages: [],
          }))
          return session.id
        } catch (error) {
          set({ error: errorMessage(error) })
          return null
        } finally {
          set({ isLoading: false })
        }
      },
      selectSession: async (sessionId) => {
        const { accessToken, sessions } = get()
        if (!accessToken || !sessions.some((session) => session.id === sessionId)) {
          set({ error: 'That conversation is not available in this workspace.' })
          return
        }
        set({ activeSessionId: sessionId, messages: [], isLoading: true, error: null })
        try {
          set({ messages: await api.messages(accessToken, sessionId) })
        } catch (error) {
          set({ error: errorMessage(error) })
        } finally {
          set({ isLoading: false })
        }
      },
      sendMessage: async (content) => {
        const text = content.trim()
        const { accessToken, activeSubject } = get()
        if (!text || !accessToken || !activeSubject || get().isSending || get().isLoading) return false
        set({ isSending: true, error: null })
        try {
          let sessionId = get().activeSessionId
          if (!sessionId) {
            const session = await api.createChatSession(accessToken, activeSubject.id)
            sessionId = session.id
            set((state) => ({
              sessions: [session, ...state.sessions],
              sessionHistory: [session, ...state.sessionHistory],
              activeSessionId: session.id,
            }))
          }
          const message = await api.createMessage(accessToken, sessionId, text)
          set((state) => {
            const updateSession = (session: ChatSession) =>
              session.id === sessionId
                ? {
                    ...session,
                    title: session.title === 'New Chat' ? text.slice(0, 42) : session.title,
                    updatedAt: message.createdAt,
                  }
                : session
            const sessionHistory = sortSessions(state.sessionHistory.map(updateSession))
            return {
              sessionHistory,
              sessions:
                state.activeSubject?.id === activeSubject.id
                  ? sortSessions(state.sessions.map(updateSession))
                  : state.sessions,
              messages:
                state.activeSessionId === sessionId
                  ? [...state.messages, message]
                  : state.messages,
            }
          })
          return true
        } catch (error) {
          set({ error: errorMessage(error) })
          return false
        } finally {
          set({ isSending: false, isStreaming: false })
        }
      },
      stopGeneration: () => set({ isStreaming: false }),
    }),
    {
      name: 'rag-workspace',
      storage: createJSONStorage(() => localStorage),
      partialize: (state) => ({
        theme: state.theme,
        currentUser: state.currentUser,
        accessToken: state.accessToken,
        activeSubject: state.activeSubject,
        activeSessionId: state.activeSessionId,
      }),
    },
  ),
)
