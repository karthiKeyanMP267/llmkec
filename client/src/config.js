// When running behind a proxy (ngrok, Vite dev server), use relative paths.
// Set VITE_AUTH_URL to a full URL only when the auth server is accessed directly.
export const AUTH_URL = import.meta.env.VITE_AUTH_URL || ''
export const ADMIN_API_URL = import.meta.env.VITE_ADMIN_API_URL || 'http://localhost:9000'
export const AUTO_API_URL = import.meta.env.VITE_AUTO_INGEST_URL || 'http://localhost:9000/ingestion'

// Role-based ingestion targets — each points to a separate sub-app that
// reads from the corresponding ChromaDB store.
export const STUDENT_2022_API_URL = import.meta.env.VITE_STUDENT_2022_API_URL || 'http://localhost:9000/ingestion'
export const STUDENT_2024_API_URL = import.meta.env.VITE_STUDENT_2024_API_URL || 'http://localhost:9000/ingestion/student_2024'
export const FACULTY_API_URL = import.meta.env.VITE_FACULTY_API_URL || 'http://localhost:9000/ingestion/faculty'

// Multi-endpoint map used to fan out collection discovery across student/faculty stores.
export const INGESTION_ENDPOINTS = {
	student_server_2022: { label: 'Student 2022', baseUrl: STUDENT_2022_API_URL },
	student_server_2024: { label: 'Student 2024', baseUrl: STUDENT_2024_API_URL },
	faculty_server: { label: 'Faculty', baseUrl: FACULTY_API_URL },
}
