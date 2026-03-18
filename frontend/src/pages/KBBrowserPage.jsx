import { useState, useEffect } from 'react'
import { getDocuments, getChunks } from '../api/client'
import { SearchIcon, FileIcon, SpinnerIcon, BookIcon } from '../components/Icons'

function highlight(text, query) {
  if (!query || !text) return text
  const reg = new RegExp(`(${query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`, 'gi')
  return text.split(reg).map((part, i) =>
    reg.test(part)
      ? <mark key={i} className="bg-brand-500/25 text-brand-200 rounded px-0.5">{part}</mark>
      : part
  )
}

export default function KBBrowserPage() {
  const [docs, setDocs] = useState([])
  const [selectedId, setSelectedId] = useState(null)
  const [chunks, setChunks] = useState([])
  const [loading, setLoading] = useState(false)
  const [search, setSearch] = useState('')

  useEffect(() => {
    getDocuments().then(r => setDocs(r.data.filter(d => d.status === 'ready'))).catch(() => {})
  }, [])

  useEffect(() => {
    if (!selectedId) return
    setLoading(true)
    getChunks(selectedId, 0, 200).then(r => { setChunks(r.data); setLoading(false) }).catch(() => setLoading(false))
  }, [selectedId])

  const filtered = search
    ? chunks.filter(c => c.text?.toLowerCase().includes(search.toLowerCase()))
    : chunks

  return (
    <div className="flex h-full">
      {/* Sidebar */}
      <aside className="w-56 shrink-0 border-r border-dark-border bg-dark-surface overflow-y-auto">
        <div className="p-3">
          <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-3">Documents</p>
          {docs.length === 0 ? (
            <p className="text-xs text-gray-600 p-2">No documents ready</p>
          ) : (
            <div className="space-y-0.5">
              {docs.map(d => (
                <button
                  key={d.id}
                  onClick={() => { setSelectedId(d.id); setSearch(''); setChunks([]) }}
                  className={`w-full flex items-center gap-2 text-left px-2.5 py-2 rounded-lg text-sm transition-all duration-150 ${
                    selectedId === d.id
                      ? 'bg-brand-500/10 text-brand-400'
                      : 'text-gray-400 hover:bg-white/[0.03] hover:text-gray-300'
                  }`}
                >
                  <FileIcon className="w-3.5 h-3.5 shrink-0" />
                  <span className="truncate">{d.filename}</span>
                  <span className="ml-auto text-xs text-gray-600">{d.chunk_count}</span>
                </button>
              ))}
            </div>
          )}
        </div>
      </aside>

      {/* Main content */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {!selectedId ? (
          <div className="flex-1 flex items-center justify-center text-center p-6 animate-fade-in">
            <div>
              <div className="w-14 h-14 rounded-2xl bg-dark-elevated border border-dark-border flex items-center justify-center mx-auto mb-3">
                <BookIcon className="w-7 h-7 text-gray-500" />
              </div>
              <p className="text-gray-400 font-medium">Select a document</p>
              <p className="text-xs text-gray-600 mt-1">Choose from the sidebar to browse its chunks</p>
            </div>
          </div>
        ) : (
          <>
            {/* Search */}
            <div className="p-3 border-b border-dark-border bg-dark-surface/50">
              <div className="relative">
                <SearchIcon className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500" />
                <input
                  value={search}
                  onChange={e => setSearch(e.target.value)}
                  placeholder="Search chunks…"
                  className="input-field w-full pl-9"
                />
              </div>
              {search && (
                <p className="text-xs text-gray-500 mt-2">{filtered.length} of {chunks.length} chunks match</p>
              )}
            </div>

            {/* Chunks */}
            <div className="flex-1 overflow-y-auto p-4 space-y-3">
              {loading ? (
                <div className="flex items-center justify-center py-12">
                  <SpinnerIcon className="w-6 h-6 text-gray-500" />
                </div>
              ) : filtered.length === 0 ? (
                <p className="text-sm text-gray-500 text-center py-8">No chunks match your search</p>
              ) : (
                filtered.map((c, i) => (
                  <div key={c.id || i} className="surface-card p-4 animate-fade-in hover:border-dark-elevated transition-colors">
                    <div className="flex items-center gap-2 mb-2">
                      <span className="text-xs font-medium text-gray-500">#{i + 1}</span>
                      {c.metadata?.page_num && (
                        <span className="text-xs px-2 py-0.5 rounded-full bg-dark-elevated text-gray-400">
                          p.{c.metadata.page_num}
                        </span>
                      )}
                      {c.token_count && (
                        <span className="text-xs text-gray-600">{c.token_count} tokens</span>
                      )}
                    </div>
                    <p className="text-sm text-gray-300 leading-relaxed whitespace-pre-wrap">
                      {highlight(c.text, search)}
                    </p>
                  </div>
                ))
              )}
            </div>
          </>
        )}
      </div>
    </div>
  )
}
