export function AdminLayout({ session, busyLabel, sidebar, children }) {
  return (
    <div className="adminPage">
      <div className="adminTopLine" />
      <div className="adminLayoutGrid">
        <div className="adminLayoutSidebar">{sidebar}</div>
        <div className="adminLayoutContent">
          <header className="adminHeader">
            <div className="adminHeaderContent">
              <div className="adminHeaderTitle">
                <span className="adminKicker">KEC Knowledge Base</span>
                <h1>Admin Ingestion Portal</h1>
                <p className="adminSubhead">Manage documents, collections, and search configurations for the AI-powered knowledge system.</p>
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
