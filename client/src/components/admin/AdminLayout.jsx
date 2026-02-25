import { useState } from 'react'

export function AdminLayout({ session, busyLabel, sidebar, children }) {
  const [sidebarOpen, setSidebarOpen] = useState(false)

  return (
    <div className="adminPage">
      <div className="adminTopLine" />
      <div className="adminLayoutGrid">
        <div className={`adminLayoutSidebar${sidebarOpen ? ' open' : ''}`}>{sidebar}</div>
        {sidebarOpen && (
          <div className="adminOverlay" onClick={() => setSidebarOpen(false)} />
        )}
        <div className="adminLayoutContent">
          <header className="adminHeader">
            <div className="adminHeaderContent">
              <div className="adminHeaderLeft">
                <button
                  className="adminHamburger"
                  onClick={() => setSidebarOpen(!sidebarOpen)}
                  aria-label="Toggle sidebar"
                  type="button"
                >
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
                    <line x1="3" y1="6" x2="21" y2="6" />
                    <line x1="3" y1="12" x2="21" y2="12" />
                    <line x1="3" y1="18" x2="21" y2="18" />
                  </svg>
                </button>
                <div className="adminHeaderTitle">
                  <span className="adminKicker">KEC Knowledge Base</span>
                  <h1>Admin Ingestion Portal</h1>
                  <p className="adminSubhead">Manage documents, collections, and search configurations for the AI-powered knowledge system.</p>
                </div>
              </div>
              <div className="adminStatusBadge" aria-live="polite">
                <span className="statusDot" />
                <span className="statusText">{busyLabel || 'Ready'}</span>
              </div>
            </div>
          </header>
          <div className="adminMainContent">
            {children}
          </div>
        </div>
      </div>
    </div>
  )
}

export function AlertStack({ status, error }) {
  return (
    <>
      {status ? <div className="adminAlert success" style={{ marginBottom: 12 }}>{status}</div> : null}
      {error ? <div className="adminAlert error" style={{ marginBottom: 12 }}>{error}</div> : null}
    </>
  )
}
