export function IngestedContentSection({
  collections,
  docFilter,
  setDocFilter,
  documents,
  onRefresh,
  selectedDocId,
  setSelectedDocId,
  docDetail,
  loadingDocDetail,
  onPreview,
}) {
  const metadata = docDetail?.metadata || {}
  const sampleChunks = docDetail?.sample_chunks || []

  return (
    <section className="modernAdminCard">
      <div className="cardHeader">
        <div className="cardHeaderIcon">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
            <polyline points="14 2 14 8 20 8"/>
            <line x1="16" y1="13" x2="8" y2="13"/>
            <line x1="16" y1="17" x2="8" y2="17"/>
            <polyline points="10 9 9 9 8 9"/>
          </svg>
        </div>
        <div className="cardHeaderTitle">
          <span className="cardKicker">Content Visibility</span>
          <h2>Ingested Content</h2>
        </div>
        <div className="cardHeaderActions">
          <select
            className="filterSelect"
            value={docFilter}
            onChange={(e) => {
              setDocFilter(e.target.value)
              onRefresh(e.target.value)
            }}
          >
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
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {documents.length === 0 ? (
                <tr>
                  <td colSpan={6} className="emptyState">
                    <div className="emptyIcon">📄</div>
                    <div className="emptyText">No documents found</div>
                    <div className="emptyHint">Upload and ingest documents to see them here</div>
                  </td>
                </tr>
              ) : (
                documents.map((doc) => {
                  const isActive = doc.doc_id === selectedDocId
                  return (
                    <tr key={doc.doc_id} className={isActive ? 'activeRow' : ''}>
                      <td className="docId">{doc.doc_id}</td>
                      <td className="filename">📄 {doc.filename}</td>
                      <td className="collection">📂 {doc.collection_name}</td>
                      <td>
                        <span className={`statusBadge ${doc.status?.toLowerCase()}`}>
                          {doc.status}
                        </span>
                      </td>
                      <td className="number">
                        <span className="docCount">{doc.total_chunks}</span>
                      </td>
                      <td>
                        <button
                          className={`previewBtn ${isActive ? 'active' : ''}`}
                          onClick={() => {
                            setSelectedDocId(doc.doc_id)
                            onPreview(doc.doc_id)
                          }}
                          disabled={loadingDocDetail && isActive}
                        >
                          {loadingDocDetail && isActive ? (
                            <><span className="btnSpinner"/>Loading...</>
                          ) : (
                            <>👁 Preview</>
                          )}
                        </button>
                      </td>
                    </tr>
                  )
                })
              )}
            </tbody>
          </table>
        </div>

        {(docDetail || !selectedDocId) && (
          <div className="previewSection">
            <div className="previewHeader">
              <h3>Document Preview</h3>
              {docDetail && <span className="previewBadge">Active</span>}
            </div>
            {!docDetail && (
              <div className="previewPlaceholder">
                <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                  <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                  <polyline points="14 2 14 8 20 8"/>
                </svg>
                <p>Select a document from the table above to preview its content and chunks</p>
              </div>
            )}
            {docDetail && (
              <>
                <div className="previewMetadata">
                  <div className="metadataGrid">
                    <div className="metadataItem">
                      <span className="metadataLabel">Document ID</span>
                      <span className="metadataValue">{metadata.doc_id}</span>
                    </div>
                    <div className="metadataItem">
                      <span className="metadataLabel">Filename</span>
                      <span className="metadataValue">{metadata.filename}</span>
                    </div>
                    <div className="metadataItem">
                      <span className="metadataLabel">Collection</span>
                      <span className="metadataValue">{metadata.collection_name}</span>
                    </div>
                    <div className="metadataItem">
                      <span className="metadataLabel">Status</span>
                      <span className={`statusBadge ${metadata.status?.toLowerCase()}`}>{metadata.status}</span>
                    </div>
                    <div className="metadataItem">
                      <span className="metadataLabel">Total Chunks</span>
                      <span className="metadataValue">{metadata.total_chunks}</span>
                    </div>
                    <div className="metadataItem">
                      <span className="metadataLabel">Total Pages</span>
                      <span className="metadataValue">{metadata.total_pages}</span>
                    </div>
                    <div className="metadataItem">
                      <span className="metadataLabel">Embedding Model</span>
                      <span className="metadataValue">{metadata.embedding_model}</span>
                    </div>
                    <div className="metadataItem">
                      <span className="metadataLabel">Updated At</span>
                      <span className="metadataValue">{metadata.updated_at}</span>
                    </div>
                  </div>
                </div>
                <div className="chunksSection">
                  <div className="chunksSectionHeader">
                    <h4>Sample Chunks</h4>
                    <span className="chunksCount">{sampleChunks.length} chunk{sampleChunks.length !== 1 ? 's' : ''}</span>
                  </div>
                  {sampleChunks.length === 0 ? (
                    <div className="noChunks">
                      <p>No chunk samples available for this document yet.</p>
                    </div>
                  ) : (
                    <div className="chunksList">
                      {sampleChunks.map((chunk) => (
                        <article key={chunk.id || chunk.chunk_id} className="chunkCard">
                          <header className="chunkHeader">
                            <span className="chunkIndex">Chunk {chunk.chunk_index ?? chunk.id}</span>
                            {chunk.page_label && <span className="chunkPage">Page {chunk.page_label}</span>}
                          </header>
                          <pre className="chunkText">{chunk.document_text || chunk.text}</pre>
                          {(chunk.metadata && Object.keys(chunk.metadata).length > 0) && (
                            <div className="chunkMetadata">
                              {Object.entries(chunk.metadata).map(([key, value]) => (
                                <span key={key} className="chunkMetaTag">{key}: {String(value)}</span>
                              ))}
                            </div>
                          )}
                        </article>
                      ))}
                    </div>
                  )}
                </div>
              </>
            )}
          </div>
        )}
      </div>
    </section>
  )
}
