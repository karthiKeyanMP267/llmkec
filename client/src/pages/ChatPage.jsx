import App from '../App'

export default function ChatPage({ session, onLogout }) {
  return (
    <div style={{ height: '100vh', overflow: 'hidden' }}>
      <App 
        session={session}
        onLogout={onLogout}
        storagePrefix={`kec-${(session.email || 'anon').replace(/[^a-z0-9]+/gi, '-').toLowerCase()}`} 
      />
    </div>
  )
}
