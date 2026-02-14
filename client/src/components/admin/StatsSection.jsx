export function StatsSection({ health, config, documentsCount }) {
  return (
    <section className="adminCard" style={{ marginBottom: 18 }}>
      <div className="adminCardHead">
        <p className="adminKicker">Overview</p>
        <h2>Health & Stats</h2>
      </div>
      <div className="adminForm" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 14 }}>
        <div className="stat-card-lite">
          <p className="adminLabel">Status</p>
          <div className="stat-value">{health?.status || 'Unknown'}</div>
          <p className="adminHint">Chroma connected: {health?.chroma_connected ? 'Yes' : 'No'}</p>
        </div>
        <div className="stat-card-lite">
          <p className="adminLabel">Collections</p>
          <div className="stat-value">{health?.collections_count ?? '—'}</div>
          <p className="adminHint">Model: {health?.current_embedding_model || 'n/a'}</p>
        </div>
        <div className="stat-card-lite">
          <p className="adminLabel">Default Collection</p>
          <div className="stat-value">{config?.default_collection || '—'}</div>
          <p className="adminHint">Chunk {config?.chunking?.chunk_size} / overlap {config?.chunking?.chunk_overlap}</p>
        </div>
        <div className="stat-card-lite">
          <p className="adminLabel">Uploads</p>
          <div className="stat-value">{documentsCount}</div>
          <p className="adminHint">Showing current list</p>
        </div>
      </div>
    </section>
  )
}
