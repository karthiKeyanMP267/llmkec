const copyDocId = async (docId) => {
  try {
    await navigator.clipboard.writeText(docId)
  } catch (err) {
    console.error('Clipboard copy failed', err)
  }
}

export function DocumentsSection({ collections, docFilter, setDocFilter, filteredDocs, onRefresh }) {
  return (
    <section className="modernAdminCard">
      <div className="cardHeader">
        <div className="cardHeaderIcon">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/>
            <path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"/>
          </svg>
        </div>
        <div className="cardHeaderTitle">
          <span className="cardKicker">Document Inventory</span>
          <h2>All Documents</h2>
        </div>
        <div className="cardHeaderActions">
          <select className="filterSelect" value={docFilter} onChange={(e) => { setDocFilter(e.target.value); onRefresh(e.target.value) }}>
            <option value="">🌐 All Collections</option>
            {collections.map((c) => (
              <option key={c.id || c.name} value={c.id || c.name}>
                📂 {c.name}{c.sourceLabel ? ` (${c.sourceLabel})` : ''}
              </option>
            ))}
          </select>
          <button className="refreshBtn" onClick={() => onRefresh(docFilter)} title="Refresh">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <polyline points="1 4 1 10 7 10"/>
              <polyline points="23 20 23 14 17 14"/>
              <path d="M20.49 9A9 9 0 0 0 5.64 5.64L1 10m22 4l-4.64 4.36A9 9 0 0 1 3.51 15"/>
            </svg>
            Refresh
          </button>
        </div>
      </div>
      <div className="cardBody">
        <div className="tableContainer">
          <table className="modernTable">
            <thead>
              <tr>
                <th>Document ID</th>
                <th>Filename</th>
                <th>Collection</th>
                <th>Status</th>
                <th>Chunks</th>
                <th>Pages</th>
                <th>Model</th>
                <th>Created At</th>
              </tr>
            </thead>
            <tbody>
              {filteredDocs.length === 0 ? (
                <tr>
                  <td colSpan={8} className="emptyState">
                    <div className="emptyIcon">📄</div>
                    <div className="emptyText">No documents found</div>
                    <div className="emptyHint">Upload PDFs to get started</div>
                  </td>
                </tr>
              ) : (
                filteredDocs.map((doc) => (
                  <tr key={doc.doc_id}>
                    <td className="docId">
                      <span className="docIdCell">
                        <span>{doc.doc_id}</span>
                        <button
                          type="button"
                          className="copyBtn"
                          title="Copy document ID"
                          onClick={() => copyDocId(doc.doc_id)}
                        >
                          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                            <rect x="9" y="9" width="13" height="13" rx="2" ry="2" />
                            <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
                          </svg>
                        </button>
                      </span>
                    </td>
                    <td className="filename">📄 {doc.filename}</td>
                    <td className="collection">📂 {doc.collection_name}</td>
                    <td>
                      <span className={`statusBadge ${doc.status?.toLowerCase()}`}>
                        {doc.status}
                      </span>
                    </td>
                    <td className="number">{doc.total_chunks}</td>
                    <td className="number">{doc.total_pages}</td>
                    <td className="model">{doc.embedding_model}</td>
                    <td className="timestamp">{new Date(doc.created_at).toLocaleString()}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </section>
  )
}
