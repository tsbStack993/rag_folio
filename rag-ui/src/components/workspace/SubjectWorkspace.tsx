import { useEffect, useRef, useState } from 'react'
import {
  ArrowLeft,
  ArrowUpRight,
  BookOpen,
  Clock3,
  LogOut,
  MessageSquareText,
  Plus,
  Search,
  Sparkles,
} from 'lucide-react'
import { useWorkspaceStore } from '../../store/useWorkspaceStore'
import { ChatWindow } from '../chat/ChatWindow'

export function SubjectWorkspace() {
  const currentUser = useWorkspaceStore((state) => state.currentUser)
  const activeSubject = useWorkspaceStore((state) => state.activeSubject)
  const sessions = useWorkspaceStore((state) => state.sessions)
  const activeSessionId = useWorkspaceStore((state) => state.activeSessionId)
  const clearSubject = useWorkspaceStore((state) => state.clearSubject)
  const createSession = useWorkspaceStore((state) => state.createSession)
  const selectSession = useWorkspaceStore((state) => state.selectSession)
  const logout = useWorkspaceStore((state) => state.logout)
  const subjects = useWorkspaceStore((state) => state.subjects)
  const isLoading = useWorkspaceStore((state) => state.isLoading)
  const [isMobileSidebarOpen, setMobileSidebarOpen] = useState(false)
  const endOfListRef = useRef<HTMLDivElement>(null)
  const activeIcon = subjects.find((subject) => subject.id === activeSubject?.id)?.slug

  useEffect(() => {
    endOfListRef.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
  }, [sessions.length])

  useEffect(() => {
    if (!isMobileSidebarOpen) return
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setMobileSidebarOpen(false)
    }
    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    window.addEventListener('keydown', closeOnEscape)
    return () => {
      document.body.style.overflow = previousOverflow
      window.removeEventListener('keydown', closeOnEscape)
    }
  }, [isMobileSidebarOpen])

  if (!activeSubject) return null

  const initial = currentUser?.email.slice(0, 1).toUpperCase() ?? 'U'
  const createNewSession = () => {
    createSession()
    setMobileSidebarOpen(false)
  }
  const switchSession = (sessionId: string) => {
    selectSession(sessionId)
    setMobileSidebarOpen(false)
  }
  const switchSubject = () => {
    clearSubject()
    setMobileSidebarOpen(false)
  }
  const signOut = () => {
    logout()
    setMobileSidebarOpen(false)
  }

  return (
    <main className="workspace-shell">
      {isMobileSidebarOpen && (
        <button
          className="sidebar-overlay"
          type="button"
          onClick={() => setMobileSidebarOpen(false)}
          aria-label="Close navigation menu"
        />
      )}
      <aside className={`sidebar ${isMobileSidebarOpen ? 'sidebar-open' : ''}`} aria-label="Workspace navigation">
        <div className="sidebar-brand">
          <a className="brand" href="#" aria-label="folio home">
            <span className="brand-mark"><span className="brand-glyph">f</span></span>
            <span>folio<span className="brand-dot">.</span></span>
          </a>
          <button className="sidebar-search icon-button" aria-label="Search conversations" title="Search conversations">
            <Search size={17} />
          </button>
        </div>

        <div className="sidebar-workspace">
          <div className={`mini-subject-icon tone-${activeIcon ?? 'mint'}`}><BookOpen size={16} /></div>
          <div className="sidebar-workspace-copy">
            <span>WORKSPACE</span>
            <strong>{activeSubject.name}</strong>
          </div>
          <button className="switch-subject" onClick={switchSubject} title="Switch subject" aria-label="Switch subject">
            <ArrowLeft size={16} />
          </button>
        </div>

        <button className="button button-new-chat" onClick={createNewSession} disabled={isLoading}>
          <Plus size={17} /> New Chat <span>⌘ K</span>
        </button>

        <div className="history-label"><span>YOUR CONVERSATIONS</span><span>{sessions.length}</span></div>
        <div className="session-list">
          {sessions.length === 0 ? (
            <div className="history-empty"><Clock3 size={17} /><span>Your chats will appear here.</span></div>
          ) : (
            sessions.map((session) => (
              <button
                className={`session-item ${session.id === activeSessionId ? 'active' : ''}`}
                key={session.id}
                onClick={() => switchSession(session.id)}
                disabled={isLoading}
                title={session.title}
              >
                <MessageSquareText size={16} />
                <span>{session.title}</span>
                {session.id === activeSessionId && <span className="session-active-dot" />}
              </button>
            ))
          )}
          <div ref={endOfListRef} />
        </div>

        <div className="sidebar-bottom">
          <div className="sidebar-plan">
            <div className="plan-icon"><Sparkles size={15} /></div>
            <div><strong>Your study space</strong><span>Private and focused</span></div>
            <ArrowUpRight size={15} />
          </div>
          <div className="sidebar-user">
            <div className="avatar">{initial}</div>
            <div className="sidebar-user-copy"><strong>{currentUser?.email.split('@')[0]}</strong><span>{currentUser?.email}</span></div>
            <button className="icon-button" onClick={signOut} aria-label="Log out" title="Log out"><LogOut size={16} /></button>
          </div>
        </div>
      </aside>
      <ChatWindow onOpenSidebar={() => setMobileSidebarOpen(true)} />
    </main>
  )
}
