import { useEffect, useMemo, useState } from 'react'
import { useIngestionAdmin } from '../hooks/useIngestionAdmin'
import { AdminLayout, AlertStack } from '../components/admin/AdminLayout'
import { UploadSection } from '../components/admin/UploadSection'
import { DocumentsSection } from '../components/admin/DocumentsSection'
import { CollectionsSection } from '../components/admin/CollectionsSection'
import { IngestedContentSection } from '../components/admin/IngestedContentSection'
import { ConfigSection } from '../components/admin/ConfigSection'
import AdminNav from '../components/admin/AdminNav'
import { AUTO_API_URL } from '../config'

function AdminIngestionPage({ session, onLogout }) {
  const baseUrl = AUTO_API_URL
  const state = useIngestionAdmin(baseUrl, undefined, session?.token || '')
  const [activeSection, setActiveSection] = useState('documents')
  const [collectionScope, setCollectionScope] = useState('all')
  const [collectionActionSource, setCollectionActionSource] = useState('student_server_2024')

  const scopedSourceOptions = useMemo(() => {
    if (collectionScope === 'all') return state.sourceOptions || []
    const key = collectionScope === 'student' ? 'student' : 'faculty'
    return (state.sourceOptions || []).filter((s) => s.key.toLowerCase().includes(key))
  }, [collectionScope, state.sourceOptions])

  const scopedCollections = useMemo(() => {
    if (collectionScope === 'all') return state.collections
    const key = collectionScope === 'student' ? 'student' : 'faculty'
    return state.collections.filter((c) => (c.sourceKey || '').toLowerCase().includes(key))
  }, [collectionScope, state.collections])

  const scopedCollectionNames = useMemo(() => new Set(scopedCollections.map((c) => c.name)), [scopedCollections])

  const scopedDocuments = useMemo(
    () => state.filteredDocs.filter((doc) => scopedCollectionNames.has(doc.collection_name)),
    [state.filteredDocs, scopedCollectionNames],
  )

  useEffect(() => {
    if (state.docFilter && !scopedCollections.find((c) => c.id === state.docFilter)) {
      state.setDocFilter('')
    }
  }, [scopedCollections, state.docFilter, state.setDocFilter])

  useEffect(() => {
    const allowedKeys = new Set((scopedSourceOptions || []).map((s) => s.key))
    if (!allowedKeys.size) return
    if (!allowedKeys.has(collectionActionSource)) {
      setCollectionActionSource((scopedSourceOptions || [])[0]?.key || 'student_server_2024')
    }
  }, [scopedSourceOptions, collectionActionSource])

  const busyLabel = state.busy ? `${state.busy} in progress` : 'Ready'

  const sidebar = (
    <div className="adminSidebarFrame">
      {/* Logo Section */}
      <div className="adminLogoContainer">
        <img src="/kec-logo.jfif" alt="KEC Logo" className="adminLogo" />
      </div>

      {/* User Profile Section */}
      <div className="adminUserProfile">
        <div className="adminUserAvatar">
          {session.email?.charAt(0).toUpperCase() || 'A'}
        </div>
        <div className="adminUserDetails">
          <div className="adminUserEmail">{session.email?.split('@')[0] || 'Admin'}</div>
          <div className="adminUserRole">{session.role || 'Administrator'}</div>
        </div>
      </div>

      {/* Scope Selector */}
      <div className="adminScopeSection">
        <label className="adminSidebarLabel" htmlFor="scope-select">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>
          </svg>
          Collection Scope
        </label>
        <select
          id="scope-select"
          className="adminScopeSelect"
          value={collectionScope}
          onChange={(e) => setCollectionScope(e.target.value)}
        >
          <option value="all">🌐 All Collections</option>
          <option value="student">🎓 Student Resources</option>
          <option value="faculty">👨‍🏫 Faculty Resources</option>
        </select>
      </div>

      {/* Navigation */}
      <AdminNav active={activeSection} onChange={setActiveSection} />

      {/* Footer with Logout */}
      <div className="adminSidebarFooter">
        <div className="adminStatusIndicator">
          <span className="statusDot" />
          <span className="statusLabel">{busyLabel}</span>
        </div>
        <button className="adminLogoutBtn" type="button" onClick={onLogout} title="Logout">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/>
            <polyline points="16 17 21 12 16 7"/>
            <line x1="21" y1="12" x2="9" y2="12"/>
          </svg>
          Logout
        </button>
      </div>
    </div>
  )

  return (
    <AdminLayout session={session} busyLabel={busyLabel} sidebar={sidebar}>
      <AlertStack status={state.status} error={state.error} />

      <main className="adminShell">

        {activeSection === 'documents' && (
          <>
            <UploadSection
              collections={scopedCollections}
              uploadCollection={state.uploadCollection}
              setUploadCollection={state.setUploadCollection}
              files={state.files}
              setFiles={state.setFiles}
              replaceId={state.replaceId}
              setReplaceId={state.setReplaceId}
              replaceFile={state.replaceFile}
              setReplaceFile={state.setReplaceFile}
              deleteId={state.deleteId}
              setDeleteId={state.setDeleteId}
              busy={state.busy}
              onUpload={state.handleUpload}
              onReplace={state.handleReplace}
              onDelete={state.handleDelete}
            />

            <DocumentsSection
              collections={scopedCollections}
              docFilter={state.docFilter}
              setDocFilter={state.setDocFilter}
              filteredDocs={scopedDocuments}
              onRefresh={state.loadDocuments}
            />
          </>
        )}

        {activeSection === 'collections' && (
          <CollectionsSection
            collections={scopedCollections}
            sourceOptions={scopedSourceOptions}
            collectionActionSource={collectionActionSource}
            setCollectionActionSource={setCollectionActionSource}
            busy={state.busy}
            newCollectionName={state.newCollectionName}
            setNewCollectionName={state.setNewCollectionName}
            renameFrom={state.renameFrom}
            setRenameFrom={state.setRenameFrom}
            renameTo={state.renameTo}
            setRenameTo={state.setRenameTo}
            onCreate={state.handleCreateCollection}
            onRename={state.handleRenameCollection}
            onReset={state.handleResetCollection}
            onDelete={state.handleDeleteCollection}
            onRefresh={() => state.loadDocuments(state.docFilter)}
            docFilter={state.docFilter}
          />
        )}

        {activeSection === 'content' && (
          <IngestedContentSection
            collections={scopedCollections}
            docFilter={state.docFilter}
            setDocFilter={state.setDocFilter}
            documents={scopedDocuments}
            onRefresh={state.loadDocuments}
            selectedDocId={state.selectedDocId}
            setSelectedDocId={state.setSelectedDocId}
            docDetail={state.docDetail}
            loadingDocDetail={state.loadingDocDetail}
            onPreview={state.loadDocumentDetail}
          />
        )}

        {activeSection === 'config' && (
          <ConfigSection
            models={state.models}
            modelKey={state.modelKey}
            setModelKey={state.setModelKey}
            chunkSize={state.chunkSize}
            setChunkSize={state.setChunkSize}
            chunkOverlap={state.chunkOverlap}
            setChunkOverlap={state.setChunkOverlap}
            llamaParseKey={state.llamaParseKey}
            setLlamaParseKey={state.setLlamaParseKey}
            llamaParseConfigured={state.llamaParseConfigured}
            llamaParseLastFour={state.llamaParseLastFour}
            busy={state.busy}
            onModelChange={state.handleModelChange}
            onChunkUpdate={state.handleChunkUpdate}
            onLlamaParseKeyUpdate={state.handleLlamaParseKeyUpdate}
          />
        )}
      </main>
    </AdminLayout>
  )
}

export default AdminIngestionPage
