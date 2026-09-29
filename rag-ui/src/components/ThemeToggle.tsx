import { Moon, Sun } from 'lucide-react'
import { useWorkspaceStore } from '../store/useWorkspaceStore'

export function ThemeToggle() {
  const theme = useWorkspaceStore((state) => state.theme)
  const toggleTheme = useWorkspaceStore((state) => state.toggleTheme)
  const isLight = theme === 'light'

  return (
    <button
      className="icon-button theme-toggle"
      type="button"
      onClick={toggleTheme}
      aria-label={`Switch to ${isLight ? 'dark' : 'light'} mode`}
      aria-pressed={isLight}
      title={`Switch to ${isLight ? 'dark' : 'light'} mode`}
    >
      {isLight ? <Moon size={17} /> : <Sun size={17} />}
    </button>
  )
}
