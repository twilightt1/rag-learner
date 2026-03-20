import { useState, useRef, useEffect } from 'react'
import { useChat } from '../hooks/useChat'
import { getDocuments } from '../api/client'
import { SendIcon, BookIcon, ChevronIcon, SearchIcon } from '../components/Icons'
import { MarkdownRenderer } from '../components/MarkdownRenderer'

function SourceCard({ chunk }) {
  const [open, setOpen] = useState(false)
  const meta = chunk.metadata || {}
  const label = meta.section || (meta.page_num ? `p.${meta.page_num}` : 'chunk')
  const score = Math.round((chunk.rerank_score ?? chunk.score ?? 0) * 100)

  return (
    <div className="surface-card overflow-hidden text-sm animate-fade-in">
      <button
        onClick={() => setOpen(o => !o)}
        className="w-full flex items-center justify-between px-3 py-2 hover:bg-white/[0.03] text-left transition-colors"
      >
        <span className="font-medium text-gray-300 truncate">{label}</span>
        <div className="flex items-center gap-2 shrink-0 ml-2">
          {/* Score bar */}
          <div className="w-16 h-1.5 rounded-full bg-dark-border overflow-hidden">
            <div
              className="h-full rounded-full bg-gradient-to-r from-brand-500 to-brand-400 transition-all"
              style={{ width: `${score}%` }}
            />
          </div>
          <span className="text-xs text-brand-400 tabular-nums w-8 text-right">{score}%</span>
          <ChevronIcon className="w-3.5 h-3.5 text-gray-500" direction={open ? 'up' : 'down'} />
        </div>
      </button>
      {open && (
        <div className="px-3 py-2 text-gray-400 max-h-48 overflow-y-auto text-xs leading-relaxed border-t border-dark-border animate-fade-in">
          <MarkdownRenderer content={chunk.text} />
        </div>
      )}
    </div>
  )
}

function TypingDots() {
  return (
    <span className="inline-flex gap-1 items-center ml-1 align-text-bottom">
      {[0, 1, 2].map(i => (
        <span
          key={i}
          className="w-1.5 h-1.5 rounded-full bg-brand-400"
          style={{
            animation: 'bounce-dot 1.4s infinite ease-in-out both',
            animationDelay: `${i * 0.16}s`,
          }}
        />
      ))}
    </span>
  )
}

function Message({ msg, sources }) {
  const isUser = msg.role === 'user'
  return (
    <div className={`flex gap-3 animate-fade-in ${isUser ? 'justify-end' : 'justify-start'}`}>
      {!isUser && (
        <div className="w-7 h-7 rounded-full bg-gradient-to-br from-brand-500 to-brand-700 flex items-center justify-center text-white text-xs font-bold shrink-0 mt-1 shadow-md shadow-brand-500/20">
          A
        </div>
      )}
      <div className={`max-w-[75%] ${isUser ? 'order-first' : ''}`}>
        <div className={`rounded-2xl px-4 py-3 text-sm leading-relaxed ${
          isUser
            ? 'bg-gradient-to-br from-brand-500 to-brand-700 text-white rounded-br-sm shadow-lg shadow-brand-500/15'
            : msg.error
              ? 'bg-red-500/10 text-red-300 border border-red-500/30 rounded-bl-sm'
              : 'surface-card text-gray-200 rounded-bl-sm'
        }`}>
          {isUser ? (
            <span className='whitespace-pre-wrap'>{msg.content}</span>
          ) : (
            <MarkdownRenderer content={msg.content} />
          )}
          {msg.streaming && <TypingDots />}
        </div>
        {!isUser && !msg.streaming && sources?.length > 0 && (
          <div className="mt-2 space-y-1">
            {sources.map((s, i) => <SourceCard key={i} chunk={s} />)}
          </div>
        )}
      </div>
      {isUser && (
        <div className="w-7 h-7 rounded-full bg-dark-elevated flex items-center justify-center text-gray-400 text-xs font-bold shrink-0 mt-1 border border-dark-border">
          U
        </div>
      )}
    </div>
  )
}

export default function ChatPage() {
  const [input, setInput] = useState('')
  const [docs, setDocs] = useState([])
  const [filterDocIds, setFilterDocIds] = useState([])
  const bottomRef = useRef(null)

  const { messages, sources, streaming, send } = useChat(null, filterDocIds)

  useEffect(() => {
    getDocuments().then(r => setDocs(r.data.filter(d => d.status === 'ready'))).catch(() => {})
  }, [])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const handleSend = () => {
    const q = input.trim()
    if (!q || streaming) return
    setInput('')
    send(q)
  }

  const toggleDoc = id => setFilterDocIds(prev =>
    prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id]
  )

  return (
    <div className="flex h-full">
      {/* Sidebar — doc filter */}
      {docs.length > 0 && (
        <aside className="w-56 shrink-0 border-r border-dark-border p-3 overflow-y-auto bg-dark-surface">
          <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-3">Filter by doc</p>
          <div className="space-y-1">
            {docs.map(d => (
              <label key={d.id} className="flex items-center gap-2 text-xs text-gray-400 cursor-pointer hover:bg-white/[0.03] rounded-lg px-2 py-1.5 transition-colors">
                <input
                  type="checkbox"
                  checked={filterDocIds.includes(d.id)}
                  onChange={() => toggleDoc(d.id)}
                  className="accent-brand-500 rounded"
                />
                <span className="truncate">{d.filename}</span>
              </label>
            ))}
          </div>
          {filterDocIds.length > 0 && (
            <button onClick={() => setFilterDocIds([])} className="mt-3 text-xs text-brand-400 hover:text-brand-300 transition-colors">
              Clear filter
            </button>
          )}
        </aside>
      )}

      {/* Main chat */}
      <div className="flex flex-col flex-1 min-w-0">
        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {messages.length === 0 && (
            <div className="h-full flex items-center justify-center text-center">
              <div className="animate-fade-in">
                <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-brand-500/20 to-brand-700/20 flex items-center justify-center mx-auto mb-4 border border-brand-500/20">
                  <BookIcon className="w-8 h-8 text-brand-400" />
                </div>
                <p className="font-semibold text-gray-300 text-lg">Ask anything about your documents</p>
                <p className="text-sm mt-1.5 text-gray-500">Upload study materials first, then chat with them here</p>
              </div>
            </div>
          )}
          {messages.map((msg, i) => (
            <Message
              key={msg.id || i}
              msg={msg}
              sources={!msg.streaming && msg.role === 'assistant' ? sources : []}
            />
          ))}
          <div ref={bottomRef} />
        </div>

        <div className="border-t border-dark-border p-4 bg-dark-surface/50">
          <div className="flex gap-2.5">
            <input
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && !e.shiftKey && handleSend()}
              placeholder="Ask a question about your notes…"
              className="input-field flex-1"
            />
            <button
              onClick={handleSend}
              disabled={streaming || !input.trim()}
              className="btn-primary !px-4"
            >
              <SendIcon className="w-4 h-4" />
              <span>{streaming ? '…' : 'Send'}</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
