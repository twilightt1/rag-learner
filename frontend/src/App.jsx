import { useState } from 'react'
import ChatPage from './pages/ChatPage'
import UploadPage from './pages/UploadPage'
import KBBrowserPage from './pages/KBBrowserPage'
import QuizPage from './pages/QuizPage'
import { ChatIcon, UploadIcon, KnowledgeIcon, QuizIcon, BookIcon } from './components/Icons'

const TABS = [
  { id: 'chat',   label: 'Chat',      Icon: ChatIcon },
  { id: 'upload', label: 'Upload',    Icon: UploadIcon },
  { id: 'kb',     label: 'Knowledge', Icon: KnowledgeIcon },
  { id: 'quiz',   label: 'Quiz',      Icon: QuizIcon },
]

export default function App() {
  const [tab, setTab] = useState('chat')

  return (
    <div className="h-screen flex flex-col bg-dark-base font-sans">
      {/* Header */}
      <header className="h-14 glass flex items-center px-5 gap-5 shrink-0 z-10 border-b border-dark-border">
        <div className="flex items-center gap-2.5">
          <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-brand-500 to-brand-700 flex items-center justify-center">
            <BookIcon className="w-4 h-4 text-white" />
          </div>
          <span className="font-semibold text-sm tracking-tight text-white">RAG Learner</span>
        </div>
        <nav className="flex gap-1 ml-2">
          {TABS.map(t => (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              className={`relative flex items-center gap-1.5 px-3.5 py-2 rounded-lg text-sm font-medium transition-all duration-200 ${
                tab === t.id
                  ? 'text-brand-400 bg-brand-500/10'
                  : 'text-gray-500 hover:text-gray-300 hover:bg-white/[0.04]'
              }`}
            >
              <t.Icon className="w-4 h-4" />
              {t.label}
              {tab === t.id && (
                <span className="absolute bottom-0 left-3 right-3 h-[2px] bg-brand-500 rounded-full" />
              )}
            </button>
          ))}
        </nav>
      </header>

      {/* Page */}
      <main className="flex-1 overflow-hidden">
        {tab === 'chat'   && <ChatPage />}
        {tab === 'upload' && <div className="h-full overflow-y-auto"><UploadPage /></div>}
        {tab === 'kb'     && <KBBrowserPage />}
        {tab === 'quiz'   && <div className="h-full overflow-y-auto"><QuizPage /></div>}
      </main>
    </div>
  )
}
