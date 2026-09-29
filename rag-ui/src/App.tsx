import { useEffect } from 'react'
import { AuthScreen } from './components/auth/AuthScreen'
import { SubjectHub } from './components/hub/SubjectHub'
import { SubjectWorkspace } from './components/workspace/SubjectWorkspace'
import { useWorkspaceStore } from './store/useWorkspaceStore'
import './App.css'

function App() {
  const currentUser = useWorkspaceStore((state) => state.currentUser)
  const activeSubject = useWorkspaceStore((state) => state.activeSubject)
  const theme = useWorkspaceStore((state) => state.theme)
  const isInitializing = useWorkspaceStore((state) => state.isInitializing)
  const initialize = useWorkspaceStore((state) => state.initialize)

  useEffect(() => {
    document.documentElement.dataset.theme = theme
    document.documentElement.style.colorScheme = theme
  }, [theme])

  useEffect(() => {
    void initialize()
  }, [initialize])

  if (isInitializing) return <main className="auth-screen" aria-busy="true">Connecting to workspace…</main>
  if (!currentUser) return <AuthScreen />
  if (activeSubject) return <SubjectWorkspace />
  return <SubjectHub />
}

export default App
