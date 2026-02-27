import { useState } from 'react'

export function ConfigSection({ models, modelKey, setModelKey, chunkSize, setChunkSize, chunkOverlap, setChunkOverlap, llamaParseKey, setLlamaParseKey, llamaParseConfigured, llamaParseLastFour, busy, onModelChange, onChunkUpdate, onLlamaParseKeyUpdate }) {
  const [persistToEnv, setPersistToEnv] = useState(true)

  return (
    <section className="modernAdminCard">
      <div className="cardHeader">
        <div className="cardHeaderIcon">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <circle cx="12" cy="12" r="3"/>
            <path d="M12 1v6m0 6v6"/>
            <path d="M17.657 6.343l-4.243 4.243m0 2.828l4.243 4.243M1 12h6m6 0h6"/>
          </svg>
        </div>
        <div className="cardHeaderTitle">
          <span className="cardKicker">System Configuration</span>
          <h2>Models & Chunking</h2>
        </div>
      </div>
      <div className="cardBody">
        <div className="formGroup">
          <label className="formLabel">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/>
            </svg>
            Embedding Model
          </label>
          <select className="formSelect" value={modelKey} onChange={(e) => setModelKey(e.target.value)}>
            {models.map((m) => (
              <option key={m.key} value={m.key}>🤖 {m.key} — {m.dimensions}d</option>
            ))}
          </select>
          <button className="primaryBtn" disabled={busy === 'config'} onClick={onModelChange} style={{ marginTop: '12px' }}>
            {busy === 'config' ? (
              <><span className="btnSpinner"/>Switching...</>
            ) : (
              <>🔄 Switch Model</>
            )}
          </button>
        </div>

        <div className="configDivider"/>

        <div className="formGroup">
          <label className="formLabel">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M4 4h16v16H4z" />
              <path d="M8 8h8v8H8z" />
            </svg>
            LlamaParse API Key
          </label>
          <div className="statusRow" style={{ marginBottom: 8 }}>
            <span className={`statusPill ${llamaParseConfigured ? 'success' : 'warning'}`}>
              {llamaParseConfigured ? `Configured${llamaParseLastFour ? ` (…${llamaParseLastFour})` : ''}` : 'Not set'}
            </span>
            <small style={{ color: '#6b7280' }}>
              Used for PDF parsing; update when rotating free-tier keys.
            </small>
          </div>
          <input
            className="formInput"
            type="password"
            placeholder="Enter new LlamaParse API key"
            value={llamaParseKey}
            onChange={(e) => setLlamaParseKey(e.target.value)}
            autoComplete="off"
          />
          <label className="checkboxLabel" style={{ marginTop: 8 }}>
            <input
              type="checkbox"
              checked={persistToEnv}
              onChange={(e) => setPersistToEnv(e.target.checked)}
            />
            <span>Persist to .env so restarts keep this key</span>
          </label>
          <button
            className="primaryBtn"
            disabled={busy === 'config'}
            onClick={() => onLlamaParseKeyUpdate(persistToEnv)}
            style={{ marginTop: '12px' }}
          >
            {busy === 'config' ? (
              <><span className="btnSpinner"/>Saving...</>
            ) : (
              <>🔑 Update LlamaParse Key</>
            )}
          </button>
        </div>

        <div className="chunkingGrid">
          <div className="formGroup">
            <label className="formLabel">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <rect x="3" y="3" width="18" height="18" rx="2" ry="2"/>
                <line x1="3" y1="9" x2="21" y2="9"/>
                <line x1="3" y1="15" x2="21" y2="15"/>
              </svg>
              Chunk Size
            </label>
            <input className="formInput" type="number" value={chunkSize} onChange={(e) => setChunkSize(e.target.value)} />
          </div>
          <div className="formGroup">
            <label className="formLabel">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <circle cx="12" cy="12" r="10"/>
                <path d="M8 14s1.5 2 4 2 4-2 4-2"/>
              </svg>
              Chunk Overlap
            </label>
            <input className="formInput" type="number" value={chunkOverlap} onChange={(e) => setChunkOverlap(e.target.value)} />
          </div>
        </div>
        <button className="secondaryBtn" disabled={busy === 'config'} onClick={onChunkUpdate}>
          {busy === 'config' ? (
            <><span className="btnSpinner"/>Updating...</>
          ) : (
            <>📝 Update Chunking</>
          )}
        </button>
      </div>
    </section>
  )
}
