export function SearchSection({
  collections,
  searchQuery,
  setSearchQuery,
  searchCollection,
  setSearchCollection,
  searchN,
  setSearchN,
  searchResults,
  busy,
  onSearch,
}) {
  return (
    <section className="modernAdminCard">
      <div className="cardHeader">
        <div className="cardHeaderIcon">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <circle cx="11" cy="11" r="8"/>
            <path d="m21 21-4.35-4.35"/>
          </svg>
        </div>
        <div className="cardHeaderTitle">
          <span className="cardKicker">Intelligent Search</span>
          <h2>Semantic Search</h2>
        </div>
      </div>
      <div className="cardBody">
        <div className="searchFormGrid">
          <div className="formGroup">
            <label className="formLabel">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M11 4a7 7 0 0 1 0 14 7 7 0 0 1 0-14z"/>
                <path d="M21 21l-4.35-4.35"/>
              </svg>
              Search Query
            </label>
            <input className="formInput" placeholder="Enter your search query" value={searchQuery} onChange={(e) => setSearchQuery(e.target.value)} />
          </div>
          <div className="formGroup">
            <label className="formLabel">Results Limit</label>
            <input className="formInput" type="number" min="1" max="100" value={searchN} onChange={(e) => setSearchN(e.target.value)} />
          </div>
        </div>
        <div className="formGroup">
          <label className="formLabel">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
            </svg>
            Target Collection (Optional)
          </label>
          <select className="formSelect" value={searchCollection} onChange={(e) => setSearchCollection(e.target.value)}>
            <option value="">🌐 All Collections</option>
            {collections.map((c) => (
              <option key={c.id || c.name} value={c.id || c.name}>📁 {c.name}{c.sourceLabel ? ` (${c.sourceLabel})` : ''}</option>
            ))}
          </select>
        </div>
        <button className="primaryBtn" disabled={busy === 'search'} onClick={onSearch}>
          {busy === 'search' ? (
            <><span className="btnSpinner"/>Searching...</>
          ) : (
            <>🔍 Search Now</>
          )}
        </button>

        {searchResults.length > 0 && (
          <div className="searchResultsSection">
            <div className="resultsSectionHeader">
              <h3>Search Results</h3>
              <span className="resultsCount">{searchResults.length} result{searchResults.length !== 1 ? 's' : ''}</span>
            </div>
            <div className="searchResults">
              {searchResults.map((r, index) => (
                <div key={r.chunk_id} className="searchResultCard">
                  <div className="resultHeader">
                    <span className="resultNumber">#{index + 1}</span>
                    <span className="chunkId">Chunk {r.chunk_id}</span>
                    {r.distance !== null && r.distance !== undefined && (
                      <span className="resultScore">Score: {r.distance.toFixed(4)}</span>
                    )}
                  </div>
                  <p className="resultText">{r.document_text}</p>
                  <div className="resultMeta">
                    {Object.entries(r.metadata || {}).map(([k, v]) => (
                      <span key={k} className="metaTag">{k}: {String(v)}</span>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </section>
  )
}
