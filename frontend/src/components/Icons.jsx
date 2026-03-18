/* Inline SVG icon components — 20×20 default, currentColor fill */

export function ChatIcon({ className = 'w-5 h-5' }) {
  return (
    <svg className={className} viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M3 4.5A1.5 1.5 0 0 1 4.5 3h11A1.5 1.5 0 0 1 17 4.5v8A1.5 1.5 0 0 1 15.5 14H7l-4 3v-3a1.5 1.5 0 0 1 0-1V4.5Z" />
      <path d="M7 8h6M7 11h4" />
    </svg>
  )
}

export function UploadIcon({ className = 'w-5 h-5' }) {
  return (
    <svg className={className} viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M10 13V3m0 0L7 6m3-3 3 3" />
      <path d="M3 13v2a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-2" />
    </svg>
  )
}

export function KnowledgeIcon({ className = 'w-5 h-5' }) {
  return (
    <svg className={className} viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="3" width="14" height="14" rx="2" />
      <path d="M3 8h14M8 8v9" />
    </svg>
  )
}

export function QuizIcon({ className = 'w-5 h-5' }) {
  return (
    <svg className={className} viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M5 3h10a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2Z" />
      <path d="M7 8h6M7 11h4M7 14h2" />
    </svg>
  )
}

export function SendIcon({ className = 'w-5 h-5' }) {
  return (
    <svg className={className} viewBox="0 0 20 20" fill="currentColor">
      <path d="M3.105 2.288a.75.75 0 0 1 .835-.11l13.5 6.75a.75.75 0 0 1 0 1.344l-13.5 6.75a.75.75 0 0 1-1.053-.882L5.03 10.5H9.5a.75.75 0 0 0 0-1.5H5.03L2.887 3.17a.75.75 0 0 1 .218-.882Z" />
    </svg>
  )
}

export function FileIcon({ className = 'w-5 h-5' }) {
  return (
    <svg className={className} viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M5 3h7l4 4v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2Z" />
      <path d="M12 3v4h4" />
    </svg>
  )
}

export function LinkIcon({ className = 'w-5 h-5' }) {
  return (
    <svg className={className} viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M8 12a4 4 0 0 0 5.66 0l2-2a4 4 0 0 0-5.66-5.66l-1 1" />
      <path d="M12 8a4 4 0 0 0-5.66 0l-2 2a4 4 0 0 0 5.66 5.66l1-1" />
    </svg>
  )
}

export function TrashIcon({ className = 'w-5 h-5' }) {
  return (
    <svg className={className} viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M4 5h12M8 5V4a1 1 0 0 1 1-1h2a1 1 0 0 1 1 1v1m2 0v10a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2V5h10Z" />
    </svg>
  )
}

export function ChevronIcon({ className = 'w-5 h-5', direction = 'down' }) {
  const rot = { down: 0, up: 180, left: 90, right: -90 }[direction] || 0
  return (
    <svg className={className} viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ transform: `rotate(${rot}deg)`, transition: 'transform 0.2s' }}>
      <path d="M6 8l4 4 4-4" />
    </svg>
  )
}

export function SearchIcon({ className = 'w-5 h-5' }) {
  return (
    <svg className={className} viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="8.5" cy="8.5" r="5" />
      <path d="M12.5 12.5 17 17" />
    </svg>
  )
}

export function SpinnerIcon({ className = 'w-5 h-5' }) {
  return (
    <svg className={`${className} animate-spin`} viewBox="0 0 20 20" fill="none">
      <circle cx="10" cy="10" r="8" stroke="currentColor" strokeWidth="2" opacity="0.2" />
      <path d="M10 2a8 8 0 0 1 8 8" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
    </svg>
  )
}

export function CheckIcon({ className = 'w-5 h-5' }) {
  return (
    <svg className={className} viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M5 10l3 3 7-7" />
    </svg>
  )
}

export function XIcon({ className = 'w-5 h-5' }) {
  return (
    <svg className={className} viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M5 5l10 10M15 5L5 15" />
    </svg>
  )
}

export function BookIcon({ className = 'w-5 h-5' }) {
  return (
    <svg className={className} viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M3 4a1 1 0 0 1 1-1h4a2 2 0 0 1 2 2v12a1 1 0 0 0-1-1H4a1 1 0 0 1-1-1V4Z" />
      <path d="M17 4a1 1 0 0 0-1-1h-4a2 2 0 0 0-2 2v12a1 1 0 0 1 1-1h4a1 1 0 0 0 1-1V4Z" />
    </svg>
  )
}

export function CodeIcon({ className = 'w-5 h-5' }) {
  return (
    <svg className={className} viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M7 5 3 10l4 5M13 5l4 5-4 5M9 17l2-14" />
    </svg>
  )
}

export function GlobeIcon({ className = 'w-5 h-5' }) {
  return (
    <svg className={className} viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="10" cy="10" r="7" />
      <path d="M3 10h14M10 3c2 2.5 2.5 4.5 2.5 7S12 15 10 17c-2-2-2.5-4.5-2.5-7S8 5 10 3Z" />
    </svg>
  )
}

/* Source type to icon mapping */
const TYPE_ICON_MAP = {
  pdf:  FileIcon,
  md:   FileIcon,
  txt:  FileIcon,
  url:  GlobeIcon,
  code: CodeIcon,
}

export function SourceTypeIcon({ type, className = 'w-4 h-4' }) {
  const Icon = TYPE_ICON_MAP[type] || FileIcon
  return <Icon className={className} />
}
