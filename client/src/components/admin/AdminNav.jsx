const NAV_ITEMS = [
  { 
    key: 'documents', 
    label: 'Documents',
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
        <polyline points="14 2 14 8 20 8"/>
      </svg>
    )
  },
  { 
    key: 'collections', 
    label: 'Collections',
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
      </svg>
    )
  },
  { 
    key: 'content', 
    label: 'Ingested Content',
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/>
        <path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"/>
      </svg>
    )
  },
  { 
    key: 'config', 
    label: 'Configuration',
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <circle cx="12" cy="12" r="3"/>
        <path d="M12 1v6m0 6v6m5.196-15.804L13.5 6.892m-3 3-3.696-3.696M1 12h6m6 0h6M3.804 5.196 7.5 8.892m3 3 3.696 3.696M1 12h6m6 0h6"/>
        <path d="M19.07 4.93a10 10 0 0 1 0 14.14m-14.14 0a10 10 0 0 1 0-14.14"/>
      </svg>
    )
  },
]

export default function AdminNav({ active, onChange }) {
  return (
    <nav className="adminNav">
      {NAV_ITEMS.map((item) => {
        const isActive = item.key === active
        return (
          <button
            key={item.key}
            className={`adminNavItem ${isActive ? 'active' : ''}`}
            onClick={() => onChange(item.key)}
            type="button"
          >
            <span className="navIcon">{item.icon}</span>
            <span className="navLabel">{item.label}</span>
            {isActive && <span className="activeIndicator" />}
          </button>
        )
      })}
    </nav>
  )
}
