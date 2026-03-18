import { useRef, useState, useCallback, useEffect } from 'react'

const WS_URL = `ws://${window.location.host}/api/chat/ws`
const MAX_RETRIES = 5
const BASE_DELAY = 1000

export function useChat(sessionId = null, filterDocIds = []) {
  const [messages, setMessages] = useState([])
  const [sources, setSources] = useState([])
  const [streaming, setStreaming] = useState(false)
  const [isConnected, setIsConnected] = useState(false)
  const wsRef = useRef(null)
  const retryRef = useRef(0)
  const filterRef = useRef(filterDocIds)

  // Keep ref in sync for stable callbacks
  useEffect(() => { filterRef.current = filterDocIds }, [filterDocIds])

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN || wsRef.current?.readyState === WebSocket.CONNECTING) return

    const ws = new WebSocket(WS_URL)

    ws.onopen = () => {
      setIsConnected(true)
      retryRef.current = 0
    }

    ws.onmessage = ev => {
      const msg = JSON.parse(ev.data)

      if (msg.type === 'token') {
        setMessages(prev => {
          const last = prev[prev.length - 1]
          if (last?.role === 'assistant' && last.streaming) {
            return [...prev.slice(0, -1), { ...last, content: last.content + msg.token }]
          }
          return [...prev, { role: 'assistant', content: msg.token, streaming: true }]
        })
      } else if (msg.type === 'sources') {
        setSources(msg.chunks || [])
      } else if (msg.type === 'done') {
        setMessages(prev =>
          prev.map((m, i) => i === prev.length - 1 && m.streaming ? { ...m, streaming: false } : m)
        )
        setStreaming(false)
      } else if (msg.type === 'error') {
        setMessages(prev => [...prev, { role: 'assistant', content: msg.detail || 'Server error', error: true }])
        setStreaming(false)
      }
    }

    ws.onclose = ev => {
      setIsConnected(false)
      wsRef.current = null

      // Only reconnect on abnormal close (not the user navigating away)
      if (!ev.wasClean && retryRef.current < MAX_RETRIES) {
        const delay = BASE_DELAY * Math.pow(2, retryRef.current)
        retryRef.current++
        setTimeout(connect, delay)
      }
    }

    ws.onerror = () => {} // onclose fires after onerror

    wsRef.current = ws
  }, [])

  useEffect(() => {
    connect()
    return () => { wsRef.current?.close() }
  }, [connect])

  const send = useCallback(question => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
      // Try to reconnect first
      connect()
      setTimeout(() => send(question), 500)
      return
    }

    setMessages(prev => [...prev, { role: 'user', content: question }])
    setSources([])
    setStreaming(true)

    const payload = { question }
    if (sessionId) payload.session_id = sessionId
    if (filterRef.current.length) payload.doc_ids = filterRef.current

    wsRef.current.send(JSON.stringify(payload))
  }, [connect, sessionId])

  return { messages, sources, streaming, isConnected, send }
}
