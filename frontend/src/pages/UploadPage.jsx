import { useState, useRef, useEffect } from 'react'
import { uploadFile, ingestUrl, getDocuments, deleteDocument } from '../api/client'
import { UploadIcon, LinkIcon, TrashIcon, CheckIcon, SpinnerIcon, SourceTypeIcon } from '../components/Icons'

const STATUS_STYLES = {
  ready:      'bg-emerald-500/15 text-emerald-400 border-emerald-500/20',
  processing: 'bg-amber-500/15 text-amber-400 border-amber-500/20',
  pending:    'bg-blue-500/15 text-blue-400 border-blue-500/20',
  failed:     'bg-red-500/15 text-red-400 border-red-500/20',
}

function DocRow({ doc, onDelete }) {
  const [confirming, setConfirming] = useState(false)

  const handleDelete = () => {
    if (!confirming) { setConfirming(true); setTimeout(() => setConfirming(false), 3000); return }
    onDelete(doc.id)
  }

  return (
    <div className="flex items-center gap-3 py-3 px-4 hover:bg-white/[0.02] rounded-lg transition-colors group animate-fade-in">
      <div className="w-8 h-8 rounded-lg bg-dark-elevated border border-dark-border flex items-center justify-center text-gray-400">
        <SourceTypeIcon type={doc.source_type} className="w-4 h-4" />
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-gray-200 truncate">{doc.filename}</p>
        <p className="text-xs text-gray-500">
          {doc.chunk_count} chunks · {new Date(doc.created_at).toLocaleDateString()}
        </p>
        {doc.error_msg && <p className="text-xs text-red-400 truncate">{doc.error_msg}</p>}
      </div>
      <span className={`text-xs px-2.5 py-1 rounded-full font-medium border ${STATUS_STYLES[doc.status] || STATUS_STYLES.pending}`}>
        {doc.status}
      </span>
      <button
        onClick={handleDelete}
        className={`text-sm transition-all duration-200 ${
          confirming
            ? 'text-red-400 hover:text-red-300'
            : 'text-gray-600 hover:text-red-400 opacity-0 group-hover:opacity-100'
        }`}
        title={confirming ? 'Click again to confirm' : 'Delete document'}
      >
        <TrashIcon className="w-4 h-4" />
      </button>
    </div>
  )
}

export default function UploadPage() {
  const [docs, setDocs] = useState([])
  const [loaded, setLoaded] = useState(false)
  const [uploads, setUploads] = useState([])
  const [url, setUrl] = useState('')
  const [urlLoading, setUrlLoading] = useState(false)
  const [dragOver, setDragOver] = useState(false)
  const fileRef = useRef(null)

  const refresh = () =>
    getDocuments().then(r => { setDocs(r.data); setLoaded(true) }).catch(() => setLoaded(true))

  // Fixed: was `useState(() => { refresh() }, [])` — should be useEffect
  useEffect(() => { refresh() }, [])

  const handleFiles = async files => {
    for (const file of Array.from(files)) {
      const id = Date.now() + Math.random()
      setUploads(prev => [...prev, { id, name: file.name, progress: 0, status: 'uploading' }])
      try {
        await uploadFile(file, pct => {
          setUploads(prev => prev.map(u => u.id === id ? { ...u, progress: pct } : u))
        })
        setUploads(prev => prev.map(u => u.id === id ? { ...u, status: 'done', progress: 100 } : u))
        refresh()
        setTimeout(() => setUploads(prev => prev.filter(u => u.id !== id)), 2000)
      } catch (e) {
        const msg = e.response?.data?.detail || 'Upload failed'
        setUploads(prev => prev.map(u => u.id === id ? { ...u, status: 'error', error: msg } : u))
      }
    }
  }

  const handleDrop = e => {
    e.preventDefault()
    setDragOver(false)
    handleFiles(e.dataTransfer.files)
  }

  const handleUrlSubmit = async () => {
    if (!url.trim()) return
    setUrlLoading(true)
    try {
      await ingestUrl(url.trim())
      setUrl('')
      refresh()
    } catch (e) {
      alert(e.response?.data?.detail || 'Failed to ingest URL')
    } finally {
      setUrlLoading(false)
    }
  }

  const handleDelete = async id => {
    await deleteDocument(id)
    refresh()
  }

  return (
    <div className="max-w-2xl mx-auto p-6 space-y-6 animate-fade-in">
      <div>
        <h1 className="text-xl font-semibold text-gray-100">Upload documents</h1>
        <p className="text-sm text-gray-500 mt-1">Add PDFs, notes, web pages, or code files to your knowledge base</p>
      </div>

      {/* Drop zone */}
      <div
        onDrop={handleDrop}
        onDragOver={e => { e.preventDefault(); setDragOver(true) }}
        onDragLeave={() => setDragOver(false)}
        onClick={() => fileRef.current?.click()}
        className={`relative border-2 border-dashed rounded-xl p-10 text-center cursor-pointer transition-all duration-300 ${
          dragOver
            ? 'border-brand-500 bg-brand-500/5 shadow-[0_0_30px_rgba(127,119,221,0.1)]'
            : 'border-dark-border hover:border-brand-500/40 hover:bg-white/[0.01]'
        }`}
      >
        <div className={`w-12 h-12 rounded-xl mx-auto mb-3 flex items-center justify-center transition-transform duration-300 ${
          dragOver ? 'scale-110 bg-brand-500/20' : 'bg-dark-elevated border border-dark-border'
        }`}>
          <UploadIcon className={`w-6 h-6 transition-colors ${dragOver ? 'text-brand-400' : 'text-gray-400'}`} />
        </div>
        <p className="font-medium text-gray-300">Drop files here or click to browse</p>
        <p className="text-xs text-gray-500 mt-1.5">Supports PDF, MD, TXT, PY, JS, TS</p>
        <input
          ref={fileRef}
          type="file"
          multiple
          className="hidden"
          accept=".pdf,.md,.txt,.py,.js,.ts,.jsx,.tsx"
          onChange={e => handleFiles(e.target.files)}
        />
      </div>

      {/* Active uploads */}
      {uploads.length > 0 && (
        <div className="space-y-2">
          {uploads.map(u => (
            <div key={u.id} className="surface-card px-4 py-3 animate-fade-in">
              <div className="flex justify-between items-center mb-2">
                <span className="text-sm text-gray-300 truncate">{u.name}</span>
                <span className={`text-xs font-medium ${
                  u.status === 'error' ? 'text-red-400'
                  : u.status === 'done' ? 'text-emerald-400'
                  : 'text-gray-500'
                }`}>
                  {u.status === 'error' ? u.error : u.status === 'done' ? 'Done!' : `${u.progress}%`}
                </span>
              </div>
              {u.status === 'uploading' && (
                <div className="h-1.5 bg-dark-border rounded-full overflow-hidden">
                  <div
                    className="h-full bg-gradient-to-r from-brand-500 to-brand-400 rounded-full transition-all duration-300"
                    style={{ width: `${u.progress}%` }}
                  />
                </div>
              )}
              {u.status === 'done' && (
                <div className="h-1.5 bg-emerald-500/30 rounded-full overflow-hidden">
                  <div className="h-full bg-emerald-500 rounded-full w-full" />
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* URL ingestion */}
      <div>
        <p className="text-sm font-medium text-gray-300 mb-2 flex items-center gap-2">
          <LinkIcon className="w-4 h-4 text-gray-500" />
          Or add a web URL
        </p>
        <div className="flex gap-2">
          <input
            value={url}
            onChange={e => setUrl(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && handleUrlSubmit()}
            placeholder="https://example.com/article"
            className="input-field flex-1"
          />
          <button
            onClick={handleUrlSubmit}
            disabled={urlLoading || !url.trim()}
            className="btn-primary"
          >
            {urlLoading ? <SpinnerIcon className="w-4 h-4" /> : 'Add'}
          </button>
        </div>
      </div>

      {/* Document list */}
      <div>
        <div className="flex items-center justify-between mb-3">
          <p className="text-sm font-medium text-gray-300">Documents ({docs.length})</p>
          <button onClick={refresh} className="text-xs text-brand-400 hover:text-brand-300 transition-colors">
            Refresh
          </button>
        </div>
        {!loaded ? (
          <div className="surface-card p-8 flex items-center justify-center">
            <SpinnerIcon className="w-5 h-5 text-gray-500" />
          </div>
        ) : docs.length === 0 ? (
          <div className="surface-card p-8 text-center text-sm text-gray-500">
            No documents yet. Upload one above.
          </div>
        ) : (
          <div className="surface-card divide-y divide-dark-border">
            {docs.map(d => <DocRow key={d.id} doc={d} onDelete={handleDelete} />)}
          </div>
        )}
      </div>
    </div>
  )
}
