import { useEffect, useMemo, useRef, useState } from 'react'
import { AUTO_API_URL, INGESTION_ENDPOINTS } from '../config'
import logger from '../utils/logger'

const collectionId = (sourceKey, name) => (sourceKey ? `${sourceKey}::${name}` : name)
const parseCollectionId = (value) => {
  if (!value || !value.includes('::')) return { sourceKey: null, name: value || '' }
  const [sourceKey, ...rest] = value.split('::')
  return { sourceKey, name: rest.join('::') }
}

export function useIngestionAdmin(defaultBaseUrl = AUTO_API_URL, endpoints = INGESTION_ENDPOINTS, authToken = '') {
  const activePollSeq = useRef(0)
  const [busy, setBusy] = useState('')
  const [status, setStatus] = useState('')
  const [error, setError] = useState('')

  const [health, setHealth] = useState(null)
  const [config, setConfig] = useState(null)
  const [models, setModels] = useState([])

  const [collections, setCollections] = useState([]) // {id, name, sourceKey, sourceLabel, baseUrl, ...}
  const [documents, setDocuments] = useState([])
  const [docFilter, setDocFilter] = useState('') // collection id
  const [selectedDocId, setSelectedDocId] = useState('')
  const [docDetail, setDocDetail] = useState(null)
  const [loadingDocDetail, setLoadingDocDetail] = useState(false)

  const [files, setFiles] = useState([])
  const [uploadCollection, setUploadCollection] = useState('')
  const [replaceFile, setReplaceFile] = useState(null)
  const [replaceId, setReplaceId] = useState('')
  const [deleteId, setDeleteId] = useState('')

  const [newCollectionName, setNewCollectionName] = useState('')
  const [renameFrom, setRenameFrom] = useState('')
  const [renameTo, setRenameTo] = useState('')

  const [chunkSize, setChunkSize] = useState('')
  const [chunkOverlap, setChunkOverlap] = useState('')
  const [modelKey, setModelKey] = useState('')
  const [llamaParseKey, setLlamaParseKey] = useState('')
  const [llamaParseConfigured, setLlamaParseConfigured] = useState(false)
  const [llamaParseLastFour, setLlamaParseLastFour] = useState('')

  const resetStatus = () => {
    setStatus('')
    setError('')
  }

  const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms))

  const resolveEndpoint = (sourceHint) => {
    if (!sourceHint) return Object.values(endpoints || {})[0]
    if (sourceHint.includes && sourceHint.includes('::')) {
      const { sourceKey } = parseCollectionId(sourceHint)
      return endpoints?.[sourceKey] || Object.values(endpoints || {})[0]
    }
    return endpoints?.[sourceHint] || Object.values(endpoints || {})[0]
  }

  const apiFetch = async (path, options = {}, baseUrl = defaultBaseUrl) => {
    const headers = new Headers(options.headers || {})
    if (authToken && !headers.has('Authorization')) {
      headers.set('Authorization', `Bearer ${authToken}`)
    }
    const res = await fetch(`${baseUrl}${path}`, { ...options, headers })
    const isJson = res.headers.get('content-type')?.includes('application/json')
    const data = isJson ? await res.json() : null
    if (!res.ok) {
      const msg = data?.detail || data?.message || 'Request failed'
      logger.error('API request failed (%s): %s', path, msg)
      setError(msg)
      return null
    }
    return data
  }

  const loadHealth = async () => {
    try {
      const data = await apiFetch('/health')
      if (!data) {
        // HTTP error (e.g. 404 when health endpoint not wired) — degrade silently
        setHealth({ status: 'degraded', chroma_connected: false, collections_count: 0, current_embedding_model: 'n/a' })
        setError('') // clear error set by apiFetch — this is expected
        return
      }
      setHealth(data)
    } catch (err) {
      // Network-level failure
      logger.error('Health check network error:', err)
      setHealth(null)
      setError(err.message || 'Health check failed')
    }
  }

  const loadConfig = async () => {
    try {
      const data = await apiFetch('/api/v1/config')
      setConfig(data)
      setChunkSize(String(data?.chunking?.chunk_size || ''))
      setChunkOverlap(String(data?.chunking?.chunk_overlap || ''))
      setModelKey(String(data?.embedding_model?.key || ''))
      setLlamaParseConfigured(Boolean(data?.llama_parse?.configured))
      setLlamaParseLastFour(data?.llama_parse?.last_four || '')
      setLlamaParseKey('')
    } catch (err) {
      setError(err.message)
    }
  }

  const loadModels = async () => {
    try {
      const data = await apiFetch('/api/v1/config/models')
      setModels(data || [])
    } catch (err) {
      setError(err.message)
    }
  }

  const loadCollections = async () => {
    const collected = []
    const entries = Object.entries(endpoints || {})
    for (const [sourceKey, cfg] of entries) {
      try {
        const data = await apiFetch('/api/v1/collections', {}, cfg.baseUrl)
        const cols = (data?.collections || []).map((c) => ({
          ...c,
          id: collectionId(sourceKey, c.name),
          sourceKey,
          sourceLabel: cfg.label,
          baseUrl: cfg.baseUrl,
        }))
        collected.push(...cols)
      } catch (err) {
        // continue; surface only if none succeed
        if (!collected.length) setError(`Collections load failed for ${cfg.label}: ${err.message}`)
      }
    }
    setCollections(collected)
    if (!uploadCollection && collected[0]) setUploadCollection(collected[0].id)
    if (!docFilter && collected[0]) setDocFilter(collected[0].id)
  }

  const loadDocuments = async (collectionIdValue = '') => {
    const target = collectionIdValue || docFilter
    if (!target) {
      setDocuments([])
      return
    }
    const { sourceKey, name } = parseCollectionId(target)
    const cfg = endpoints?.[sourceKey] || Object.values(endpoints || {})[0]
    if (!cfg) {
      setError('No ingestion endpoints configured')
      return
    }
    try {
      const qs = name ? `?collection_name=${encodeURIComponent(name)}` : ''
      const data = await apiFetch(`/api/v1/documents/${qs}`.replace('//', '/'), {}, cfg.baseUrl)
      setDocuments((data?.documents || []).map((d) => ({ ...d, _sourceKey: sourceKey })))
    } catch (err) {
      setError(err.message)
    }
  }

  useEffect(() => {
    setHealth(null)
    setConfig(null)
    setModels([])
    setCollections([])
    setDocuments([])
    setSelectedDocId('')
    setDocDetail(null)
    setLoadingDocDetail(false)
    setError('')
    setStatus('')
    setLlamaParseConfigured(false)
    setLlamaParseLastFour('')
    setLlamaParseKey('')

    if (!authToken) {
      setError('Please login again to continue ingestion management')
      return
    }

    loadHealth()
    loadConfig()
    loadModels()
    loadCollections()
  }, [defaultBaseUrl, endpoints, authToken])

  const loadDocumentDetail = async (docId) => {
    resetStatus()
    if (!docId) {
      setError('Select a document to preview')
      return
    }
    setBusy('preview')
    setLoadingDocDetail(true)
    try {
      const { sourceKey } = parseCollectionId(docFilter || uploadCollection)
      const cfg = endpoints?.[sourceKey] || Object.values(endpoints || {})[0]
      const data = await apiFetch(`/api/v1/documents/${encodeURIComponent(docId)}`, {}, cfg?.baseUrl || defaultBaseUrl)
      setDocDetail(data)
      setSelectedDocId(docId)
    } catch (err) {
      setError(err.message)
      setDocDetail(null)
    } finally {
      setBusy('')
      setLoadingDocDetail(false)
    }
  }

  const handleUpload = async () => {
    resetStatus()
    if (!files.length) {
      setError('Choose at least one PDF')
      return
    }
    setBusy('upload')
    activePollSeq.current += 1
    const pollSeq = activePollSeq.current
    try {
      const form = new FormData()
      const uploadedDocs = []
      const selectedCollectionName = uploadCollection ? parseCollectionId(uploadCollection).name : ''
      const uploadPath = selectedCollectionName
        ? `/api/v1/documents/upload?collection_name=${encodeURIComponent(selectedCollectionName)}`
        : '/api/v1/documents/upload'
      const batchUploadPath = selectedCollectionName
        ? `/api/v1/documents/upload/batch?collection_name=${encodeURIComponent(selectedCollectionName)}`
        : '/api/v1/documents/upload/batch'

      if (files.length === 1) {
        form.append('file', files[0])
        const { sourceKey } = parseCollectionId(uploadCollection)
        const cfg = endpoints?.[sourceKey] || Object.values(endpoints || {})[0]
        const data = await apiFetch(uploadPath, { method: 'POST', body: form }, cfg?.baseUrl || defaultBaseUrl)
        if (data?.doc_id) uploadedDocs.push({ docId: data.doc_id, sourceKey, collectionName: parseCollectionId(uploadCollection).name })
        setStatus(`Upload accepted for ${data?.filename}. Ingestion started...`)
      } else {
        files.forEach((f) => form.append('files', f))
        const { sourceKey } = parseCollectionId(uploadCollection)
        const cfg = endpoints?.[sourceKey] || Object.values(endpoints || {})[0]
        const data = await apiFetch(batchUploadPath, { method: 'POST', body: form }, cfg?.baseUrl || defaultBaseUrl)
        const acceptedDocs = data?.documents || []
        acceptedDocs.forEach((d) => d?.doc_id && uploadedDocs.push({ docId: d.doc_id, sourceKey, collectionName: parseCollectionId(uploadCollection).name }))
        setStatus(`Upload accepted: ${data?.accepted || 0}/${data?.total_files || files.length}. Ingestion started...`)
      }

      setFiles([])
      if (uploadCollection) setDocFilter(uploadCollection)
      await loadDocuments(uploadCollection || docFilter)
      await loadCollections()

      if (uploadedDocs.length) {
        setBusy('ingest')
        const { sourceKey, name } = parseCollectionId(uploadCollection || docFilter)
        const cfg = endpoints?.[sourceKey] || Object.values(endpoints || {})[0]
        const maxAttempts = 90
        for (let attempt = 0; attempt < maxAttempts; attempt += 1) {
          if (activePollSeq.current !== pollSeq) break

          const tracked = []
          for (const item of uploadedDocs) {
            const itemCfg = endpoints?.[item.sourceKey] || cfg
            try {
              const statusData = await apiFetch(`/api/v1/documents/${encodeURIComponent(item.docId)}/status`, {}, itemCfg?.baseUrl || defaultBaseUrl)
              tracked.push({ doc_id: item.docId, status: statusData?.status })
            } catch {
              tracked.push({ doc_id: item.docId, status: 'pending' })
            }
          }

          const completed = tracked.filter((d) => String(d.status).toLowerCase() === 'completed')
          const failed = tracked.filter((d) => String(d.status).toLowerCase() === 'failed')

          if (failed.length) {
            setError(`Ingestion failed for ${failed.length} file(s)`)
            setStatus('')
            await loadDocuments(uploadCollection || docFilter)
            break
          }

          if (tracked.length === uploadedDocs.length && completed.length === uploadedDocs.length) {
            setStatus(`Ingestion completed for ${completed.length} file(s)`)
            await loadDocuments(uploadCollection || docFilter)
            break
          }

          setStatus(`Ingestion in progress... ${completed.length}/${uploadedDocs.length} completed`)
          await loadDocuments(uploadCollection || docFilter)
          await sleep(2000)

          if (attempt === maxAttempts - 1) {
            setStatus('Upload accepted. Ingestion is still running; refresh to check latest status.')
          }
        }
      }
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy('')
    }
  }

  const handleLlamaParseKeyUpdate = async (persistToEnv = true) => {
    resetStatus()
    if (!llamaParseKey.trim()) {
      setError('Enter a LlamaParse API key')
      return
    }
    setBusy('config')
    try {
      const data = await apiFetch('/api/v1/config/llamaparse-key', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ api_key: llamaParseKey.trim(), persist_to_env: persistToEnv }),
      })
      setStatus(data?.message || 'LlamaParse API key updated')
      setLlamaParseConfigured(true)
      setLlamaParseLastFour(data?.last_four || '')
      setLlamaParseKey('')
      await loadConfig()
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy('')
    }
  }

  const handleReplace = async () => {
    resetStatus()
    if (!replaceId.trim() || !replaceFile) {
      setError('Provide document_id and a replacement file')
      return
    }
    setBusy('replace')
    try {
      const form = new FormData()
      form.append('file', replaceFile)
      const selectedCollectionName = uploadCollection ? parseCollectionId(uploadCollection).name : ''
      const { sourceKey } = parseCollectionId(uploadCollection || docFilter)
      const cfg = endpoints?.[sourceKey] || Object.values(endpoints || {})[0]
      const replacePath = selectedCollectionName
        ? `/api/v1/documents/${replaceId.trim()}?collection_name=${encodeURIComponent(selectedCollectionName)}`
        : `/api/v1/documents/${replaceId.trim()}`
      const data = await apiFetch(replacePath, { method: 'PUT', body: form }, cfg?.baseUrl || defaultBaseUrl)
      setStatus(`Replacement queued for ${data?.filename}`)
      await loadDocuments(docFilter)
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy('')
    }
  }

  const handleDelete = async () => {
    resetStatus()
    if (!deleteId.trim()) {
      setError('Provide document_id to delete')
      return
    }
    setBusy('delete')
    try {
      const { sourceKey } = parseCollectionId(docFilter || uploadCollection)
      const cfg = endpoints?.[sourceKey] || Object.values(endpoints || {})[0]
      const data = await apiFetch(`/api/v1/documents/${deleteId.trim()}`, { method: 'DELETE' }, cfg?.baseUrl || defaultBaseUrl)
      setStatus(data?.message || 'Deleted')
      await loadDocuments(docFilter)
      await loadCollections()
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy('')
    }
  }

  const handleCreateCollection = async (sourceHint = '') => {
    resetStatus()
    if (!newCollectionName.trim()) {
      setError('Enter a collection name')
      return
    }
    setBusy('collection')
    try {
      const { sourceKey } = parseCollectionId(uploadCollection || docFilter)
      const cfg = resolveEndpoint(sourceHint || sourceKey)
      await apiFetch('/api/v1/collections/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: newCollectionName.trim() }),
      }, cfg?.baseUrl || defaultBaseUrl)
      setStatus('Collection created')
      setNewCollectionName('')
      await loadCollections()
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy('')
    }
  }

  const handleRenameCollection = async (sourceHint = '') => {
    resetStatus()
    if (!renameFrom.trim() || !renameTo.trim()) {
      setError('Provide current and new collection names')
      return
    }
    setBusy('collection')
    try {
      const { sourceKey, name } = parseCollectionId(renameFrom || docFilter || uploadCollection)
      const cfg = resolveEndpoint(sourceHint || sourceKey)
      await apiFetch(`/api/v1/collections/${encodeURIComponent(name || renameFrom.trim())}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ new_name: renameTo.trim() }),
      }, cfg?.baseUrl || defaultBaseUrl)
      setStatus('Collection renamed')
      setRenameFrom('')
      setRenameTo('')
      await loadCollections()
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy('')
    }
  }

  const handleDeleteCollection = async (idOrName) => {
    resetStatus()
    setBusy('collection')
    try {
      const parsed = parseCollectionId(idOrName)
      const cfg = endpoints?.[parsed.sourceKey] || Object.values(endpoints || {})[0]
      await apiFetch(`/api/v1/collections/${encodeURIComponent(parsed.name || idOrName)}`, { method: 'DELETE' }, cfg?.baseUrl || defaultBaseUrl)
      setStatus(`Deleted collection ${parsed.name || idOrName}`)
      await loadCollections()
      await loadDocuments(docFilter)
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy('')
    }
  }

  const handleResetCollection = async (idOrName) => {
    resetStatus()
    setBusy('collection')
    try {
      const parsed = parseCollectionId(idOrName)
      const cfg = endpoints?.[parsed.sourceKey] || Object.values(endpoints || {})[0]
      await apiFetch(`/api/v1/collections/${encodeURIComponent(parsed.name || idOrName)}/reset`, { method: 'POST' }, cfg?.baseUrl || defaultBaseUrl)
      setStatus(`Reset collection ${parsed.name || idOrName}`)
      await loadCollections()
      await loadDocuments(docFilter)
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy('')
    }
  }

  const handleModelChange = async () => {
    resetStatus()
    if (!modelKey) return
    setBusy('config')
    try {
      await apiFetch('/api/v1/config/embedding-model', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ model_key: modelKey }),
      })
      setStatus(`Switched model to ${modelKey}`)
      await loadConfig()
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy('')
    }
  }

  const handleChunkUpdate = async () => {
    resetStatus()
    setBusy('config')
    try {
      await apiFetch('/api/v1/config/chunking', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          chunk_size: chunkSize ? Number(chunkSize) : undefined,
          chunk_overlap: chunkOverlap ? Number(chunkOverlap) : undefined,
        }),
      })
      setStatus('Chunking parameters updated')
      await loadConfig()
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy('')
    }
  }

  const filteredDocs = useMemo(
    () => (docFilter ? documents.filter((d) => d.collection_name === parseCollectionId(docFilter).name) : documents),
    [documents, docFilter],
  )

  const sourceOptions = useMemo(
    () => Object.entries(endpoints || {}).map(([key, cfg]) => ({ key, label: cfg.label || key })),
    [endpoints],
  )

  return {
    busy,
    status,
    error,
    setError,
    health,
    config,
    models,
    collections,
    documents,
    filteredDocs,
    sourceOptions,
    docFilter,
    setDocFilter,
    parseCollectionId,
    files,
    setFiles,
    uploadCollection,
    setUploadCollection,
    replaceFile,
    setReplaceFile,
    replaceId,
    setReplaceId,
    deleteId,
    setDeleteId,
    newCollectionName,
    setNewCollectionName,
    renameFrom,
    setRenameFrom,
    renameTo,
    setRenameTo,
    selectedDocId,
    setSelectedDocId,
    docDetail,
    loadingDocDetail,
    chunkSize,
    setChunkSize,
    chunkOverlap,
    setChunkOverlap,
    modelKey,
    setModelKey,
    llamaParseKey,
    setLlamaParseKey,
    llamaParseConfigured,
    llamaParseLastFour,
    loadDocuments,
    loadDocumentDetail,
    handleUpload,
    handleReplace,
    handleDelete,
    handleCreateCollection,
    handleRenameCollection,
    handleDeleteCollection,
    handleResetCollection,
    handleModelChange,
    handleChunkUpdate,
    handleLlamaParseKeyUpdate,
  }
}
