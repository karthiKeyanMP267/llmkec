import { useState } from 'react'

export default function LoginPage({ onLogin, status, error, loading, clearError }) {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')

  const handleSubmit = async (e) => {
    e.preventDefault()
    await onLogin(email.trim(), password)
  }

  return (
    <div className="loginShell">
      <div className="loginCard">
        <div className="loginHero">
          <div className="loginHeroContent">
            <h1>Welcome to KEC Assistant</h1>
            <p>Transform Yourself</p>
          </div>
        </div>

        <div className="loginPanel">
          <img src="/kec-logo.png" alt="KEC logo" className="loginLogo" />
          <h2 className="loginTitle">Welcome</h2>

          <form className="loginForm" onSubmit={handleSubmit}>
            <div className="loginField">
              <label className="loginLabel">Email</label>
              <input
                className="loginInput"
                value={email}
                onChange={(e) => { setEmail(e.target.value); clearError?.() }}
                type="email"
                required
                placeholder="karthi.23cse@kongu.edu"
                autoComplete="username"
              />
            </div>

            <div className="loginField">
              <label className="loginLabel">Password</label>
              <input
                className="loginInput"
                value={password}
                onChange={(e) => { setPassword(e.target.value); clearError?.() }}
                type="password"
                required
                placeholder="********"
                autoComplete="current-password"
              />
            </div>

            <div className="loginActions">
              <a className="loginLink" href="#">Forgot your password?</a>
            </div>

            <button type="submit" className="loginButton" disabled={loading}>{loading ? 'Signing in...' : 'Login'}</button>

          </form>

          {status ? <div className="loginStatus">{status}</div> : null}
          {error ? <div className="loginError">{error}</div> : null}

          <div className="loginFooter">(c) 2026 Kongu Engineering College</div>
        </div>
      </div>
    </div>
  )
}
