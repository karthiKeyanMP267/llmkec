import './App.css'
import 'katex/dist/katex.min.css'
import { useEffect, useRef, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import remarkMath from 'remark-math'
import rehypeRaw from 'rehype-raw'
import rehypeKatex from 'rehype-katex'

function extractBoldNumberedItems(text) {
  const pattern = /(\*\*\d+(?:\.\d+)*\*\*)/g
  const parts = String(text || '').split(pattern).map((p) => p.trim()).filter(Boolean)
  const items = []

  for (let i = 0; i < parts.length; i++) {
    const part = parts[i]
    if (pattern.test(part)) {
      const label = part.replace(/\*\*/g, '')
      const body = parts[i + 1] && !pattern.test(parts[i + 1]) ? parts[i + 1] : ''
      items.push({ label, body })
      if (body) i += 1
    }
  }

  return items.length > 1 ? items : null
}

function extractBoldHeadingRows(text) {
  const lines = String(text || '')
    .split(/\r?\n/)
    .map((l) => l.trim())
    .filter(Boolean)

  const rows = []
  for (const line of lines) {
    const match = line.match(/^\*\*([^*]+)\*\*\s*[:\-]\s*(.+)$/i)
    if (match) {
      rows.push({ heading: match[1].trim(), detail: match[2].trim() })
    }
  }

  return rows.length ? rows : null
}

function extractJsonPayload(text) {
  const raw = String(text || '').trim()
  if (!raw) return null

  const tryParse = (candidate) => {
    if (!candidate) return null
    try {
      return JSON.parse(candidate)
    } catch {
      return null
    }
  }

  const fenced = raw.match(/```json\s*([\s\S]*?)\s*```/i) || raw.match(/```\s*([\s\S]*?)\s*```/i)
  if (fenced && fenced[1]) {
    const parsed = tryParse(fenced[1])
    if (parsed) return parsed
  }

  // Only auto-parse when the entire message is JSON-like, to avoid grabbing free-form text.
  if ((raw.startsWith('{') && raw.endsWith('}')) || (raw.startsWith('[') && raw.endsWith(']'))) {
    const parsed = tryParse(raw)
    if (parsed && typeof parsed === 'object') return parsed
  }

  return null
}

function renderStructuredPayload(payload) {
  if (!payload || typeof payload !== 'object') return null

  if (Array.isArray(payload)) {
    if (payload.length && payload.every((row) => row && typeof row === 'object')) {
      const headers = Object.keys(payload[0] || {})
      if (!headers.length) return null
      return (
        <table className="formattedTable">
          <thead>
            <tr>
              {headers.map((h) => (
                <th key={h}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {payload.map((row, idx) => (
              <tr key={idx}>
                {headers.map((h) => (
                  <td key={h}>{String(row?.[h] ?? '')}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      )
    }
  }

  if (payload.table && typeof payload.table === 'object') {
    const headers = Array.isArray(payload.table.headers) ? payload.table.headers : []
    const rows = Array.isArray(payload.table.rows) ? payload.table.rows : []
    if (headers.length && rows.length) {
      return (
        <table className="formattedTable">
          <thead>
            <tr>
              {headers.map((h, idx) => (
                <th key={idx}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, idx) => (
              <tr key={idx}>
                {headers.map((_, hIdx) => (
                  <td key={hIdx}>{String(row?.[hIdx] ?? '')}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      )
    }
  }

  if (Array.isArray(payload.rules)) {
    const rows = payload.rules.filter((r) => r && typeof r === 'object')
    if (rows.length) {
      // Gather all keys from all rows to adapt dynamically to the payload shape.
      const allKeys = Array.from(new Set(rows.flatMap((row) => Object.keys(row || {}))))
      const normalizeKey = (key) => String(key || '').trim()
      const prettyLabel = (key) =>
        normalizeKey(key)
          .replace(/[_-]+/g, ' ')
          .replace(/\s+/g, ' ')
          .replace(/(^\w|\s\w)/g, (m) => m.toUpperCase())

      const headers = allKeys.map(normalizeKey).filter(Boolean)

      return (
        <table className="formattedTable">
          <thead>
            <tr>
              {headers.map((h) => (
                <th key={h}>{prettyLabel(h)}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, idx) => (
              <tr key={idx}>
                {headers.map((h) => (
                  <td key={h}>{String(row?.[h] ?? '')}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      )
    }
  }

  return null
}

function renderMarkdown(text) {
  // Enable GitHub-flavored markdown + LaTeX math (inline $...$ and block $$...$$)
  return (
    <ReactMarkdown remarkPlugins={[remarkGfm, remarkMath]} rehypePlugins={[rehypeRaw, rehypeKatex]}>
      {String(text || '')}
    </ReactMarkdown>
  )
}

function extractLineItems(text) {
  const lines = String(text || '').split(/\r?\n/).map((l) => l.trim()).filter(Boolean)
  if (!lines.length) return null

  const numbered = lines.every((l) => /^\d+\.\s+/.test(l))
  if (numbered) {
    return { type: 'ol', items: lines.map((l) => l.replace(/^\d+\.\s+/, '')) }
  }

  const bulleted = lines.every((l) => /^[-*•]\s+/.test(l))
  if (bulleted) {
    return { type: 'ul', items: lines.map((l) => l.replace(/^[-*•]\s+/, '')) }
  }

  return null
}

function renderMessageText(role, text) {
  if (role !== 'assistant') return text

  // If the response contains an HTML table, render it directly via markdown
  if (/<table[\s\S]*?>/i.test(String(text || ''))) {
    return renderMarkdown(text)
  }

  // Check for JSON payload with structured data
  const payload = extractJsonPayload(text)
  if (payload) {
    const table = renderStructuredPayload(payload)
    if (table) {
      const display = payload.display_text || payload.displayText || payload.message || ''
      return (
        <div className="structuredBlock">
          {display ? <div className="structuredIntro">{renderMarkdown(display)}</div> : null}
          {table}
        </div>
      )
    }
  }

  const boldItems = extractBoldNumberedItems(text)
  if (boldItems) {
    return (
      <ul className="formattedList">
        {boldItems.map((item, idx) => (
          <li key={idx}>
            <strong>{item.label}</strong>{item.body ? ` ${item.body}` : ''}
          </li>
        ))}
      </ul>
    )
  }

  const lineItems = extractLineItems(text)
  if (lineItems) {
    const ListTag = lineItems.type === 'ol' ? 'ol' : 'ul'
    return (
      <ListTag className="formattedList">
        {lineItems.items.map((item, idx) => (
          <li key={idx}>{item}</li>
        ))}
      </ListTag>
    )
  }

  return renderMarkdown(text)
}

function useAutoScroll(dep) {
  const ref = useRef(null)
  useEffect(() => {
    const el = ref.current
    if (!el) return
    el.scrollTop = el.scrollHeight
  }, [dep])
  return ref
}

function readNdjsonLines(reader) {
  const decoder = new TextDecoder()
  let buffer = ''

  return {
    async *[Symbol.asyncIterator]() {
      while (true) {
        const { value, done } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        while (true) {
          const idx = buffer.indexOf('\n')
          if (idx === -1) break
          const line = buffer.slice(0, idx).trim()
          buffer = buffer.slice(idx + 1)
          if (!line) continue
          try {
            yield JSON.parse(line)
          } catch {
            // ignore bad line
          }
        }
      }

      const tail = buffer.trim()
      if (tail) {
        try {
          yield JSON.parse(tail)
        } catch {
          // ignore
        }
      }
    },
  }
}

function parseKeyValueLines(text) {
  const out = {}
  const lines = String(text || '')
    .split(/\r?\n/)
    .map((l) => l.trim())
    .filter(Boolean)
  for (const line of lines) {
    const eq = line.indexOf('=')
    if (eq === -1) continue
    const k = line.slice(0, eq).trim()
    const v = line.slice(eq + 1).trim()
    if (!k) continue
    out[k] = v
  }
  return out
}

function App({ storagePrefix = 'kec', session = null, onLogout = null }) {
  const [conversations, setConversations] = useState(() => {
    try {
      const saved = localStorage.getItem(`${storagePrefix}-conversations`)
      return saved ? JSON.parse(saved) : []
    } catch {
      return []
    }
  })
  const [currentConvId, setCurrentConvId] = useState(null)
  const [threadId, setThreadId] = useState(null)
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [abortController, setAbortController] = useState(null)

  const scrollRef = useAutoScroll(messages.length + (loading ? 1 : 0))

  // Persist conversations to localStorage
  useEffect(() => {
    try {
      localStorage.setItem(`${storagePrefix}-conversations`, JSON.stringify(conversations))
    } catch (e) {
      console.error('Failed to save conversations:', e)
    }
  }, [conversations, storagePrefix])

  // Save current conversation messages
  useEffect(() => {
    if (!currentConvId || messages.length === 0) return
    try {
      localStorage.setItem(`${storagePrefix}-messages-${currentConvId}`, JSON.stringify({ messages, threadId }))
    } catch (e) {
      console.error('Failed to save messages:', e)
    }
  }, [currentConvId, messages, threadId, storagePrefix])

  function stopGeneration() {
    if (abortController) {
      abortController.abort()
      setAbortController(null)
      setLoading(false)
    }
  }

  async function send() {
    const text = input.trim()
    if (!text || loading) return
    setError('')
    setInput('')

    const optimisticUser = { role: 'user', text }
    const assistantIdx = messages.length + 1
    const newMessages = [...messages, optimisticUser, { role: 'assistant', text: '', tools: [] }]
    setMessages(newMessages)
    setLoading(true)

    if (!currentConvId && messages.length === 0) {
      const convId = Date.now().toString()
      const title = text.slice(0, 40) + (text.length > 40 ? '...' : '')
      setCurrentConvId(convId)
      setConversations((prev) => [{ id: convId, title, timestamp: new Date() }, ...prev])
    }

    const controller = new AbortController()
    setAbortController(controller)

    try {
      const body = { threadId, message: text, mode: 'ask' }
      body.agent = 'general'

      const res = await fetch('/api/chat/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
        signal: controller.signal,
      })

      if (!res.ok || !res.body) {
        const t = await res.text().catch(() => '')
        throw new Error(t || `HTTP ${res.status}`)
      }

      const reader = res.body.getReader()
      for await (const evt of readNdjsonLines(reader)) {
        if (evt?.type === 'meta' && evt.threadId) {
          if (!threadId) setThreadId(evt.threadId)
        }
        if (evt?.type === 'delta' && typeof evt.text === 'string') {
          setMessages((m) => {
            const next = [...m]
            if (!next[assistantIdx]) return next
            next[assistantIdx] = { ...next[assistantIdx], text: (next[assistantIdx].text || '') + evt.text }
            return next
          })
        }
        if (evt?.type === 'tool' && evt.tool) {
          setMessages((m) => {
            const next = [...m]
            const cur = next[assistantIdx]
            if (!cur) return next
            const tools = Array.isArray(cur.tools) ? [...cur.tools] : []
            const idx = tools.findIndex((t) => t.callId && t.callId === evt.callId)
            const payload = {
              callId: evt.callId,
              tool: evt.tool,
              status: evt.status || 'unknown',
              title: evt.title || '',
            }
            if (idx >= 0) {
              tools[idx] = { ...tools[idx], ...payload }
            } else {
              tools.push(payload)
            }
            next[assistantIdx] = { ...cur, tools }
            return next
          })
        }
        if (evt?.type === 'assistant_error' && evt.error) {
          const msg =
            evt.error?.data?.message ||
            evt.error?.message ||
            (typeof evt.error === 'string' ? evt.error : null) ||
            'Provider/agent error'
          setError(msg)
        }
        if (evt?.type === 'error') {
          throw new Error(evt.error || 'Chat failed')
        }
        if (evt?.type === 'done') {
          break
        }
      }

      setMessages((m) => {
        const next = [...m]
        const cur = next[assistantIdx]
        if (cur && !String(cur.text || '').trim()) {
          next[assistantIdx] = { ...cur, text: '(no text response)' }
        }
        return next
      })
    } catch (e) {
      if (e.name === 'AbortError') {
        setMessages((m) => {
          const next = [...m]
          if (next[assistantIdx]) next[assistantIdx] = { ...next[assistantIdx], text: (next[assistantIdx].text || '') + '\n\n_Generation stopped._' }
          return next
        })
      } else {
        setError(String(e?.message || e))
        setMessages((m) => {
          const next = [...m]
          if (next[assistantIdx]) next[assistantIdx] = { ...next[assistantIdx], text: 'Sorry — something went wrong.' }
          return next
        })
      }
    } finally {
      setLoading(false)
      setAbortController(null)
    }
  }

  function newChat() {
    setCurrentConvId(null)
    setThreadId(null)
    setMessages([])
    setError('')
  }

  function loadConversation(convId) {
    setCurrentConvId(convId)
    setError('')
    try {
      const saved = localStorage.getItem(`${storagePrefix}-messages-${convId}`)
      if (saved) {
        const data = JSON.parse(saved)
        setMessages(data.messages || [])
        setThreadId(data.threadId || null)
      } else {
        setMessages([])
        setThreadId(null)
      }
    } catch (e) {
      console.error('Failed to load conversation:', e)
      setMessages([])
      setThreadId(null)
    }
  }

  function deleteConversation(convId, e) {
    e.stopPropagation()
    setConversations((prev) => prev.filter((c) => c.id !== convId))
    try {
      localStorage.removeItem(`${storagePrefix}-messages-${convId}`)
    } catch (e) {
      console.error('Failed to delete conversation messages:', e)
    }
    if (currentConvId === convId) {
      newChat()
    }
  }

  return (
    <div className="app">
      <div className="topLine"></div>
      <div className="appContent">
        <aside className="sidebar">
          <div className="logoContainer">
            <img src="/kec-logo.png" alt="KEC - Kongu Engineering College" className="logo" />
          </div>
        <div className="sidebarHeader">
          <button className="btn newChatBtn" onClick={newChat} disabled={loading}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M12 5v14M5 12h14" />
            </svg>
            New chat
          </button>
        </div>

        <div className="chatHistory">
          {conversations.length === 0 ? (
            <div className="emptyHistory">No conversations yet</div>
          ) : (
            conversations.map((conv) => (
              <div
                key={conv.id}
                className={`historyItem ${currentConvId === conv.id ? 'active' : ''}`}
                onClick={() => loadConversation(conv.id)}
              >
                <div className="historyTitle">{conv.title}</div>
                <button className="deleteBtn" onClick={(e) => deleteConversation(conv.id, e)}>
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M18 6L6 18M6 6l12 12" />
                  </svg>
                </button>
              </div>
            ))
          )}
        </div>

        <div className="sidebarFooter">
          {session && (
            <div className="userProfile">
              <div className="userAvatar">
                {session.email?.charAt(0).toUpperCase() || 'U'}
              </div>
              <div className="userInfo">
                <div className="userName">{session.email?.split('@')[0] || 'User'}</div>
                <div className="userRole">{session.role || 'Go'}</div>
              </div>
              {onLogout && (
                <button className="logoutBtn" onClick={onLogout} title="Logout">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4M16 17l5-5-5-5M21 12H9"/>
                  </svg>
                </button>
              )}
            </div>
          )}
          {error ? <div className="error">{error}</div> : null}
        </div>
      </aside>

      <main className="main">
        <section className="chat">
          <div className="messages" ref={scrollRef}>
            {messages.length === 0 ? (
              <div className="empty">
                <div className="emptyTitle">How can I help you today?</div>
                <form className="composerCentered" onSubmit={(e) => { e.preventDefault(); send(); }}>
                  <textarea
                    className="composerInput"
                    rows={1}
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    placeholder="Ask here"
                    disabled={loading}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' && !e.shiftKey) {
                        e.preventDefault()
                        send()
                      }
                    }}
                  />
                  <button type="submit" className="composerBtn sendBtn" disabled={!input.trim()} title="Send message">
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z"/>
                    </svg>
                  </button>
                </form>
              </div>
            ) : null}

            {messages.map((m, idx) => (
              <div key={idx} className={`msg ${m.role === 'user' ? 'user' : 'assistant'}`}>
                <div className="avatar">
                  {m.role === 'user' ? (
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <circle cx="12" cy="8" r="4"/>
                      <path d="M20 21a8 8 0 1 0-16 0"/>
                    </svg>
                  ) : (
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
                      <path d="M5 13.18v4L12 21l7-3.82v-4L12 17l-7-3.82zM12 3L1 9l11 6 9-4.91V17h2V9L12 3z"/>
                    </svg>
                  )}
                </div>
                <div className="bubble">
                  {m.role === 'assistant' && !m.text && loading && idx === messages.length - 1 ? (
                    <div className="thinkingBlock">
                      <div className="thinkingHeader">
                        <span className="thinkingSpinner"></span>
                        Thinking
                      </div>
                      <div className="thinkingContent">
                        {Array.isArray(m.tools) && m.tools.length > 0 ? (
                          m.tools.map((t, tIdx) => (
                            <div key={`${t.callId || tIdx}`} className="thinkingItem">
                              <span className="thinkingBullet">●</span>
                              <span className="thinkingText">{t.title || t.tool || 'Processing...'}</span>
                            </div>
                          ))
                        ) : (
                          <div className="thinkingItem">
                            <span className="thinkingBullet">●</span>
                            <span className="thinkingText">Processing your request...</span>
                          </div>
                        )}
                      </div>
                    </div>
                  ) : null}
                  {m.text ? <div className="text">{renderMessageText(m.role, m.text)}</div> : null}
                </div>
              </div>
            ))}
          </div>

          {messages.length > 0 && (
            <div className="composerWrapper">
              <form className="composer" onSubmit={(e) => { e.preventDefault(); send(); }}>
                <textarea
                  className="composerInput"
                  rows={1}
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  placeholder="Ask here"
                  disabled={loading}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && !e.shiftKey) {
                      e.preventDefault()
                      send()
                    }
                  }}
                />
                {loading ? (
                  <button type="button" className="composerBtn stopBtn" onClick={stopGeneration} title="Stop generating">
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor">
                      <rect x="6" y="6" width="12" height="12" rx="2" />
                    </svg>
                  </button>
                ) : (
                  <button type="submit" className="composerBtn sendBtn" disabled={!input.trim()} title="Send message">
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z"/>
                    </svg>
                  </button>
                )}
              </form>
            </div>
          )}
        </section>
      </main>
      </div>
    </div>
  )
}

export default App
