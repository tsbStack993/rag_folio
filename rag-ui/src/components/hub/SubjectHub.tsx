import {
  Activity,
  ArrowRight,
  ArrowUpRight,
  Cloud,
  Code2,
  Cpu,
  Eye,
  LogOut,
  Sparkles,
  type LucideIcon,
} from 'lucide-react'
import { useWorkspaceStore } from '../../store/useWorkspaceStore'
import { ThemeToggle } from '../ThemeToggle'

const subjectIcons: Record<string, LucideIcon> = {
  'embedded-system': Cpu,
  'cloud-technology': Cloud,
  'digital-image-processing': Eye,
  'digital-signal-processing': Activity,
  'software-engineering': Code2,
}

const subjectTones: Record<string, string> = {
  'embedded-system': 'mint',
  'cloud-technology': 'blue',
  'digital-image-processing': 'peach',
  'digital-signal-processing': 'violet',
  'software-engineering': 'lime',
}

export function SubjectHub() {
  const currentUser = useWorkspaceStore((state) => state.currentUser)
  const selectSubject = useWorkspaceStore((state) => state.selectSubject)
  const logout = useWorkspaceStore((state) => state.logout)
  const sessionHistory = useWorkspaceStore((state) => state.sessionHistory)
  const subjects = useWorkspaceStore((state) => state.subjects)
  const error = useWorkspaceStore((state) => state.error)
  const isLoading = useWorkspaceStore((state) => state.isLoading)
  const firstName = currentUser?.email.split('@')[0] ?? 'there'

  return (
    <main className="hub-page">
      <header className="topbar">
        <a className="brand" href="#" aria-label="folio home">
          <span className="brand-mark"><span className="brand-glyph">f</span></span>
          <span>folio<span className="brand-dot">.</span></span>
        </a>
        <div className="topbar-right">
          <ThemeToggle />
          <div className="avatar">{firstName.slice(0, 1).toUpperCase()}</div>
          <span className="account-email">{currentUser?.email}</span>
          <button className="icon-button logout-button" onClick={logout} aria-label="Log out" title="Log out">
            <LogOut size={17} />
          </button>
        </div>
      </header>

      <section className="hub-content">
        <div className="hub-heading">
          <div className="section-kicker"><Sparkles size={14} /> YOUR LEARNING SPACE</div>
          <h1>Select a Knowledge Base<br /><span>Workspace</span></h1>
          <p>Choose a subject and pick up where curiosity takes you.</p>
          <div className="subject-count"><span className="count-dot" /> {subjects.length} curated knowledge bases</div>
        </div>

        {error && <p className="api-error" role="alert">{error}</p>}
        <div className="subject-grid">
          {subjects.map((subject, index) => {
            const Icon = subjectIcons[subject.slug]
            const chats = sessionHistory.filter((session) => session.subjectId === subject.id).length
            return (
              <article className={`subject-card tone-${subjectTones[subject.slug]}`} key={subject.id}>
                <div className="subject-card-top">
                  <div className="subject-icon"><Icon size={21} strokeWidth={1.8} /></div>
                  <span className="subject-index">0{index + 1}</span>
                </div>
                <h2>{subject.name}</h2>
                <p>{subject.description}</p>
                <div className="subject-card-bottom">
                  <span>{chats ? `${chats} ${chats === 1 ? 'conversation' : 'conversations'}` : 'Ready to explore'}</span>
                  <button
                    className="enter-link"
                    disabled={isLoading}
                    onClick={() => selectSubject(subject.id)}
                    aria-label={`Enter ${subject.name} workspace`}
                  >
                    Enter workspace <ArrowRight size={15} />
                  </button>
                </div>
                <ArrowUpRight className="card-watermark" size={88} strokeWidth={0.7} />
              </article>
            )
          })}
        </div>

        <div className="hub-footnote"><span className="footnote-rule" /> Each workspace has its own conversations and sources.</div>
      </section>
      <footer className="hub-footer"><span>folio<span className="brand-dot">.</span></span><span>THINK DEEPER, TOGETHER.</span></footer>
    </main>
  )
}
