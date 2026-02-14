export function CollectionsSection({
  collections,
  sourceOptions,
  collectionActionSource,
  setCollectionActionSource,
  busy,
  newCollectionName,
  setNewCollectionName,
  renameFrom,
  setRenameFrom,
  renameTo,
  setRenameTo,
  onCreate,
  onRename,
  onReset,
  onDelete,
  onRefresh,
  docFilter,
}) {
  return (
    <section className="modernAdminCard">
      <div className="cardHeader">
        <div className="cardHeaderIcon">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
          </svg>
        </div>
        <div className="cardHeaderTitle">
          <span className="cardKicker">Storage Management</span>
          <h2>Collections</h2>
        </div>
      </div>
      <div className="cardBody">
        <div className="collectionsGrid">
          {/* Create Collection */}
          <div className="collectionActionCard">
            <div className="actionCardHeader">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <line x1="12" y1="5" x2="12" y2="19"/>
                <line x1="5" y1="12" x2="19" y2="12"/>
              </svg>
              <h3>Create Collection</h3>
            </div>
            <div className="actionCardBody">
              <div className="formGroup">
                <label className="formLabel">
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <circle cx="12" cy="12" r="10"/>
                    <line x1="12" y1="8" x2="12" y2="16"/>
                    <line x1="8" y1="12" x2="16" y2="12"/>
                  </svg>
                  Source Server
                </label>
                <select 
                  className="formSelect" 
                  value={collectionActionSource} 
                  onChange={(e) => setCollectionActionSource(e.target.value)}
                >
                  {(sourceOptions || []).map((s) => (
                    <option key={s.key} value={s.key}>{s.label}</option>
                  ))}
                </select>
              </div>
              <div className="formGroup">
                <label className="formLabel">
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
                  </svg>
                  Collection Name
                </label>
                <input 
                  className="formInput" 
                  placeholder="Enter collection name" 
                  value={newCollectionName} 
                  onChange={(e) => setNewCollectionName(e.target.value)} 
                />
              </div>
              <button 
                className="primaryBtn" 
                disabled={busy === 'collection'} 
                onClick={() => onCreate(collectionActionSource)}
              >
                {busy === 'collection' ? (
                  <><span className="btnSpinner"/>Creating...</>
                ) : (
                  <>➕ Create Collection</>
                )}
              </button>
            </div>
          </div>

          {/* Rename Collection */}
          <div className="collectionActionCard">
            <div className="actionCardHeader">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
                <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
              </svg>
              <h3>Rename Collection</h3>
            </div>
            <div className="actionCardBody">
              <div className="formGroup">
                <label className="formLabel">
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <circle cx="12" cy="12" r="10"/>
                    <line x1="12" y1="8" x2="12" y2="16"/>
                    <line x1="8" y1="12" x2="16" y2="12"/>
                  </svg>
                  Source Server
                </label>
                <select 
                  className="formSelect" 
                  value={collectionActionSource} 
                  onChange={(e) => setCollectionActionSource(e.target.value)}
                >
                  {(sourceOptions || []).map((s) => (
                    <option key={s.key} value={s.key}>{s.label}</option>
                  ))}
                </select>
              </div>
              <div className="formGroup">
                <label className="formLabel">Current Name</label>
                <input 
                  className="formInput" 
                  placeholder="Enter current collection name" 
                  value={renameFrom} 
                  onChange={(e) => setRenameFrom(e.target.value)} 
                />
              </div>
              <div className="formGroup">
                <label className="formLabel">New Name</label>
                <input 
                  className="formInput" 
                  placeholder="Enter new collection name" 
                  value={renameTo} 
                  onChange={(e) => setRenameTo(e.target.value)} 
                />
              </div>
              <button 
                className="secondaryBtn" 
                disabled={busy === 'collection'} 
                onClick={() => onRename(collectionActionSource)}
              >
                {busy === 'collection' ? (
                  <><span className="btnSpinner"/>Renaming...</>
                ) : (
                  <>✏️ Rename Collection</>
                )}
              </button>
            </div>
          </div>
        </div>

        {/* Collections Table */}
        <div className="collectionsTableSection">
          <div className="tableSectionHeader">
            <h3>Existing Collections</h3>
            <span className="collectionCount">{collections.length} collection{collections.length !== 1 ? 's' : ''}</span>
          </div>
          <div className="tableContainer">
            <table className="modernTable">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Documents</th>
                  <th>Metadata</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {collections.length === 0 ? (
                  <tr>
                    <td colSpan={4} className="emptyState">
                      <div className="emptyIcon">📂</div>
                      <div className="emptyText">No collections found</div>
                      <div className="emptyHint">Create a new collection to get started</div>
                    </td>
                  </tr>
                ) : (
                  collections.map((c) => (
                    <tr key={c.id || `${c.sourceKey || 'default'}::${c.name}`}>
                      <td className="collectionName">
                        📁 {c.name}
                        {c.sourceLabel && <span className="sourceLabel">{c.sourceLabel}</span>}
                      </td>
                      <td className="number">
                        <span className="docCount">{c.document_count}</span>
                      </td>
                      <td className="metadata">
                        {c.metadata ? (
                          <code className="metadataCode">{JSON.stringify(c.metadata)}</code>
                        ) : (
                          <span className="noMetadata">—</span>
                        )}
                      </td>
                      <td>
                        <div className="actionButtons">
                          <button 
                            className="actionBtn resetBtn" 
                            onClick={() => onReset(c.id || c.name)}
                            title="Reset collection"
                          >
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                              <polyline points="1 4 1 10 7 10"/>
                              <polyline points="23 20 23 14 17 14"/>
                              <path d="M20.49 9A9 9 0 0 0 5.64 5.64L1 10m22 4l-4.64 4.36A9 9 0 0 1 3.51 15"/>
                            </svg>
                            Reset
                          </button>
                          <button 
                            className="actionBtn deleteBtn" 
                            onClick={() => onDelete(c.id || c.name)}
                            title="Delete collection"
                          >
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                              <polyline points="3 6 5 6 21 6"/>
                              <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
                            </svg>
                            Delete
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </section>
  )
}
