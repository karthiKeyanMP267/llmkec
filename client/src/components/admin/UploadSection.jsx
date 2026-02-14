export function UploadSection({
  collections,
  uploadCollection,
  setUploadCollection,
  files,
  setFiles,
  replaceId,
  setReplaceId,
  replaceFile,
  setReplaceFile,
  deleteId,
  setDeleteId,
  busy,
  onUpload,
  onReplace,
  onDelete,
}) {
  return (
    <section className="modernAdminCard">
      <div className="cardHeader">
        <div className="cardHeaderIcon">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
            <polyline points="17 8 12 3 7 8"/>
            <line x1="12" y1="3" x2="12" y2="15"/>
          </svg>
        </div>
        <div className="cardHeaderTitle">
          <span className="cardKicker">Document Management</span>
          <h2>Upload / Replace / Delete</h2>
        </div>
      </div>
      <div className="cardBody">
        <div className="formGroup">
          <label className="formLabel">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
            </svg>
            Target Collection
          </label>
          <select className="formSelect" value={uploadCollection} onChange={(e) => setUploadCollection(e.target.value)}>
            <option value="">📁 Default Collection</option>
            {collections.map((c) => (
              <option key={c.id || c.name} value={c.id || c.name}>
                📂 {c.name}{c.sourceLabel ? ` (${c.sourceLabel})` : ''}
              </option>
            ))}
          </select>
          <p className="formHint">💡 Leave blank to use the API default collection</p>
        </div>

        <div className="formGroup">
          <label className="formLabel">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
              <polyline points="14 2 14 8 20 8"/>
            </svg>
            Upload PDFs (Single or Batch)
          </label>
          <input className="formFileInput" type="file" multiple accept="application/pdf" onChange={(e) => setFiles(Array.from(e.target.files || []))} />
          {files.length > 0 && (
            <div className="fileCount">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <polyline points="20 6 9 17 4 12"/>
              </svg>
              {files.length} file(s) selected
            </div>
          )}
          <button className="primaryBtn" disabled={busy === 'upload' || busy === 'ingest'} onClick={onUpload}>
            {busy === 'upload' ? (
              <><span className="btnSpinner"/>Uploading...</>
            ) : busy === 'ingest' ? (
              <><span className="btnSpinner"/>Ingesting...</>
            ) : (
              <>📤 Upload & Ingest</>
            )}
          </button>
        </div>

        <div className="formGroup">
          <label className="formLabel">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <polyline points="1 4 1 10 7 10"/>
              <path d="M3.51 15a9 9 0 1 0 2.13-9.36L1 10"/>
            </svg>
            Replace Existing Document
          </label>
          <input className="formInput" placeholder="Enter document_id" value={replaceId} onChange={(e) => setReplaceId(e.target.value)} />
          <input className="formFileInput" type="file" accept="application/pdf" onChange={(e) => setReplaceFile(e.target.files?.[0] || null)} />
          <button className="secondaryBtn" disabled={busy === 'replace'} onClick={onReplace}>
            {busy === 'replace' ? (
              <><span className="btnSpinner"/>Replacing...</>
            ) : (
              <>🔄 Replace Document</>
            )}
          </button>
        </div>

        <div className="formGroup">
          <label className="formLabel">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <polyline points="3 6 5 6 21 6"/>
              <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
            </svg>
            Delete Document
          </label>
          <input className="formInput" placeholder="Enter document_id" value={deleteId} onChange={(e) => setDeleteId(e.target.value)} />
          <button className="dangerBtn" disabled={busy === 'delete'} onClick={onDelete}>
            {busy === 'delete' ? (
              <><span className="btnSpinner"/>Deleting...</>
            ) : (
              <>🗑️ Delete Document</>
            )}
          </button>
        </div>
      </div>
    </section>
  )
}
