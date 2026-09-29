import { useLayoutEffect, useRef, useState, type FormEvent, type KeyboardEvent } from 'react'
import {
  ArrowDown,
  ArrowUp,
  Check,
  ChevronDown,
  Copy,
  Cpu,
  FileText,
  Image,
  LoaderCircle,
  MessageSquare,
  Menu,
  Sparkles,
  Square,
  Waves,
  Cloud,
  Code2,
} from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { useWorkspaceStore } from '../../store/useWorkspaceStore'
import type { Message } from '../../types/workspace'
import { ThemeToggle } from '../ThemeToggle'

const suggestionsBySlug: Record<string, string[]> = {
  'embedded-system': [
    'Explain RTOS task scheduling vs interrupts',
    'How does a UART interface work?',
    'When should I use an RTOS?',
  ],
  'cloud-technology': [
    'Explain containers vs virtual machines',
    'How does Kubernetes scale a service?',
    'What is a cloud availability zone?',
  ],
  'digital-image-processing': [
    'How does a Gaussian blur work?',
    'Explain image segmentation techniques',
    'What is the frequency domain?',
  ],
  'digital-signal-processing': [
    'Explain the FFT in simple terms',
    'How do FIR and IIR filters differ?',
    'What is a z-transform used for?',
  ],
  'software-engineering': [
    'Explain the SOLID principles',
    'How do I choose an architecture pattern?',
    'What makes a useful unit test?',
  ],
}

const subjectIconMap: Record<string, typeof Cpu> = {
  'embedded-system': Cpu,
  'cloud-technology': Cloud,
  'digital-image-processing': Image,
  'digital-signal-processing': Waves,
  'software-engineering': Code2,
}

function SourceAccordion({ message }: { message: Message }) {
  const [isOpen, setIsOpen] = useState(false)
  if (!message.sources.length) return null

  return (
    <div className="sources">
      <button className="sources-toggle" onClick={() => setIsOpen((open) => !open)} aria-expanded={isOpen}>
        <span className="sources-toggle-icon"><FileText size={14} /></span>
        <span>Retrieved sources <b>{message.sources.length}</b></span>
        <ChevronDown className={isOpen ? 'chevron-open' : ''} size={15} />
      </button>
      {isOpen && (
        <div className="sources-list">
          {message.sources.map((source) => (
            <div className="source-row" key={`${source.title}-${source.page}`}>
              <div className="source-file-icon"><FileText size={15} /></div>
              <div className="source-info"><strong>{source.title}</strong><span>Page {source.page}</span></div>
              <span className="source-score">{Math.round(source.score * 100)}%</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function ChatMessage({ message }: { message: Message }) {
  const [copied, setCopied] = useState(false)
  const isUser = message.sender === 'user'

  const copyMessage = async () => {
    await navigator.clipboard.writeText(message.content)
    setCopied(true)
    window.setTimeout(() => setCopied(false), 1600)
  }

  return (
    <article className={`message-row ${isUser ? 'message-user' : 'message-assistant'}`}>
      {!isUser && <div className="assistant-avatar"><Sparkles size={15} /></div>}
      <div className="message-content-wrap">
        {!isUser && <div className="message-author">Folio <span>·</span> Assistant</div>}
        <div className={`message-bubble ${isUser ? 'user-bubble' : 'assistant-bubble'}`}>
          {message.content ? (
            <div className="markdown-content">
              <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                components={{
                  a: ({ children, ...props }) => <a {...props} target="_blank" rel="noreferrer">{children}</a>,
                  code: ({ children, className, ...props }) => {
                    const inline = !className
                    return inline
                      ? <code className="inline-code" {...props}>{children}</code>
                      : <code className={className} {...props}>{children}</code>
                  },
                }}
              >
                {message.content}
              </ReactMarkdown>
            </div>
          ) : (
            <div className="typing-indicator" aria-label="Assistant is thinking"><span /><span /><span /></div>
          )}
          {message.isStreaming && message.content.length > 0 && <span className="stream-cursor" />}
        </div>
        {!isUser && message.content && (
          <div className="message-actions">
            <button onClick={copyMessage} aria-label="Copy response" title="Copy response">
              {copied ? <Check size={14} /> : <Copy size={14} />}
            </button>
          </div>
        )}
        {!isUser && <SourceAccordion message={message} />}
      </div>
    </article>
  )
}

export function ChatWindow({ onOpenSidebar }: { onOpenSidebar: () => void }) {
  const activeSubject = useWorkspaceStore((state) => state.activeSubject)
  const activeSessionId = useWorkspaceStore((state) => state.activeSessionId)
  const sessions = useWorkspaceStore((state) => state.sessions)
  const messages = useWorkspaceStore((state) => state.messages)
  const isStreaming = useWorkspaceStore((state) => state.isStreaming)
  const isSending = useWorkspaceStore((state) => state.isSending)
  const isLoading = useWorkspaceStore((state) => state.isLoading)
  const error = useWorkspaceStore((state) => state.error)
  const sendMessage = useWorkspaceStore((state) => state.sendMessage)
  const stopGeneration = useWorkspaceStore((state) => state.stopGeneration)
  const [input, setInput] = useState('')
  const [showScrollButton, setShowScrollButton] = useState(false)
  const scrollContainerRef = useRef<HTMLDivElement>(null)
  const isAtBottomRef = useRef(true)
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const activeSession = sessions.find((session) => session.id === activeSessionId)
  const suggestions = activeSubject ? suggestionsBySlug[activeSubject.slug] : []
  const SubjectIcon = activeSubject ? subjectIconMap[activeSubject.slug] : Cpu

  useLayoutEffect(() => {
    isAtBottomRef.current = true
    const container = scrollContainerRef.current
    if (container) container.scrollTop = container.scrollHeight
  }, [activeSessionId])

  useLayoutEffect(() => {
    const container = scrollContainerRef.current
    if (!container || !isAtBottomRef.current) return
    container.scrollTo({
      top: container.scrollHeight,
      behavior: isStreaming ? 'auto' : 'smooth',
    })
  }, [messages, isStreaming])

  if (!activeSubject) return null

  const submit = async (event?: FormEvent<HTMLFormElement>) => {
    event?.preventDefault()
    if (!input.trim() || isStreaming || isSending || isLoading) return
    if (await sendMessage(input)) {
      setInput('')
      if (textareaRef.current) textareaRef.current.style.height = 'auto'
    }
  }

  const onInputKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      submit()
    }
  }

  const onInputChange = (value: string) => {
    setInput(value)
    const textarea = textareaRef.current
    if (textarea) {
      textarea.style.height = 'auto'
      textarea.style.height = `${Math.min(textarea.scrollHeight, 160)}px`
    }
  }

  const onScroll = () => {
    const container = scrollContainerRef.current
    if (!container) return
    const distanceFromBottom = container.scrollHeight - container.scrollTop - container.clientHeight
    isAtBottomRef.current = distanceFromBottom <= 48
    setShowScrollButton(distanceFromBottom > 240)
  }

  return (
    <section className="chat-panel">
      <header className="chat-header">
        <button
          className="mobile-menu-button icon-button"
          type="button"
          onClick={onOpenSidebar}
          aria-label="Open navigation menu"
        >
          <Menu size={19} />
        </button>
        <div className="chat-header-subject">
          <div className="header-subject-icon"><SubjectIcon size={17} /></div>
          <span>{activeSubject.name}</span>
          <span className="header-divider">/</span>
          <span className="chat-title">{activeSession?.title ?? 'New conversation'}</span>
        </div>
        <div className="chat-header-actions">
          <div className="rag-status"><span>Saved to workspace</span></div>
          <ThemeToggle />
        </div>
      </header>

      <div className="messages-scroll" ref={scrollContainerRef} onScroll={onScroll}>
        {messages.length === 0 ? (
          <div className="chat-welcome">
            <div className="welcome-orbit">
              <div className="welcome-orbit-inner"><SubjectIcon size={29} strokeWidth={1.5} /></div>
              <span className="orbit-dot orbit-dot-one" /><span className="orbit-dot orbit-dot-two" />
            </div>
            <div className="welcome-kicker"><span /> YOUR {activeSubject.name.toUpperCase()} WORKSPACE</div>
            <h1>Let’s make sense<br />of <span>something.</span></h1>
            <p>Start a conversation. Your messages are securely saved to your account.</p>
            <div className="suggestion-area">
              <span className="suggestion-label">A FEW PLACES TO START</span>
              <div className="suggestion-grid">
                {suggestions?.map((suggestion, index) => (
                  <button
                    className="suggestion-card"
                    key={suggestion}
                    onClick={() => {
                      void sendMessage(suggestion)
                    }}
                  >
                    <span>0{index + 1}</span>{suggestion}<ArrowUp size={14} className="suggestion-arrow" />
                  </button>
                ))}
              </div>
            </div>
          </div>
        ) : (
          <div className="message-list">
            {messages.map((message) => <ChatMessage key={message.id} message={message} />)}
          </div>
        )}
      </div>

      {showScrollButton && (
        <button className="scroll-bottom" onClick={() => scrollContainerRef.current?.scrollTo({ top: scrollContainerRef.current.scrollHeight, behavior: 'smooth' })} aria-label="Scroll to latest message">
          <ArrowDown size={17} />
        </button>
      )}

      {error && <p className="api-error chat-api-error" role="alert">{error}</p>}
      <footer className={`composer-area ${messages.length === 0 ? 'composer-welcome' : ''}`}>
        {messages.length > 0 && (
          <div className="composer-suggestions">
            <Sparkles size={13} />
            {suggestions?.slice(0, 2).map((suggestion) => (
              <button key={suggestion} disabled={isStreaming || isSending || isLoading} onClick={() => setInput(suggestion)}>{suggestion}</button>
            ))}
          </div>
        )}
        <form className="composer" onSubmit={submit}>
          <textarea
            ref={textareaRef}
            value={input}
            onChange={(event) => onInputChange(event.target.value)}
            onKeyDown={onInputKeyDown}
            placeholder={`Ask anything about ${activeSubject.name.toLowerCase()}...`}
            rows={1}
            aria-label="Message"
            disabled={isStreaming || isSending || isLoading}
          />
          <div className="composer-bottom">
            <div className="composer-hint"><span className="hint-icon"><MessageSquare size={13} /></span> Messages are saved to your account</div>
            {isStreaming ? (
              <button className="send-button stop-button" type="button" onClick={stopGeneration} aria-label="Stop generating" title="Stop generating"><Square size={13} fill="currentColor" /></button>
            ) : (
              <button className="send-button" type="submit" disabled={!input.trim() || isSending || isLoading} aria-label="Send message">
                {isSending ? <LoaderCircle size={16} className="loading-spinner" /> : <ArrowUp size={17} />}
              </button>
            )}
          </div>
        </form>
        <p className="composer-disclaimer">Assistant responses will be available when the RAG service is connected.</p>
      </footer>
    </section>
  )
}
