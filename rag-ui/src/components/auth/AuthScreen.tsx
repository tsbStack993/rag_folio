import { useState, type FormEvent } from 'react'
import { ArrowRight, BookOpen, Check, Eye, EyeOff, LockKeyhole, Mail } from 'lucide-react'
import { useWorkspaceStore } from '../../store/useWorkspaceStore'

export function AuthScreen() {
  const authenticate = useWorkspaceStore((state) => state.authenticate)
  const isLoading = useWorkspaceStore((state) => state.isLoading)
  const error = useWorkspaceStore((state) => state.error)
  const clearError = useWorkspaceStore((state) => state.clearError)
  const [isRegistering, setIsRegistering] = useState(false)
  const [showPassword, setShowPassword] = useState(false)
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')

  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    void authenticate(email, password, isRegistering)
  }

  return (
    <main className="auth-screen">
      <div className="auth-brand">
        <div className="brand-mark"><BookOpen size={19} strokeWidth={2.1} /></div>
        <span>folio<span className="brand-dot">.</span></span>
      </div>
      <section className="auth-card">
        <div className="auth-eyebrow"><span className="eyebrow-line" /> YOUR KNOWLEDGE, CONNECTED</div>
        <h1>{isRegistering ? 'Create your account' : 'Welcome back'}</h1>
        <p className="auth-intro">
          {isRegistering
            ? 'Start a focused workspace for everything you want to learn.'
            : 'Sign in to continue your learning journey.'}
        </p>

        <form className="auth-form" onSubmit={submit}>
          <label htmlFor="email">Email address</label>
          <div className="field-wrap">
            <Mail size={17} aria-hidden="true" />
            <input
              id="email"
              type="email"
              placeholder="you@example.com"
              autoComplete="email"
              required
              value={email}
              onChange={(event) => setEmail(event.target.value)}
            />
          </div>
          <label htmlFor="password">Password</label>
          <div className="field-wrap">
            <LockKeyhole size={17} aria-hidden="true" />
            <input
              id="password"
              type={showPassword ? 'text' : 'password'}
              placeholder="At least 8 characters"
              autoComplete={isRegistering ? 'new-password' : 'current-password'}
              minLength={8}
              required
              value={password}
              onChange={(event) => setPassword(event.target.value)}
            />
            <button
              className="field-action"
              type="button"
              aria-label={showPassword ? 'Hide password' : 'Show password'}
              onClick={() => setShowPassword((visible) => !visible)}
            >
              {showPassword ? <EyeOff size={17} /> : <Eye size={17} />}
            </button>
          </div>
          {error && <p className="api-error" role="alert">{error}</p>}
          <button className="button button-primary auth-submit" type="submit" disabled={isLoading}>
            {isLoading ? 'Connecting…' : isRegistering ? 'Create account' : 'Sign in'} <ArrowRight size={17} />
          </button>
        </form>

        <div className="auth-switch">
          {isRegistering ? 'Already have an account?' : 'New to folio?'}
          <button type="button" onClick={() => {
            clearError()
            setIsRegistering((registering) => !registering)
          }}>
            {isRegistering ? 'Sign in' : 'Create an account'}
          </button>
        </div>
        <div className="auth-note"><Check size={14} /> Private workspaces. Your knowledge stays yours.</div>
      </section>
      <p className="auth-footer">A quieter place to think, learn, and connect the dots.</p>
    </main>
  )
}
