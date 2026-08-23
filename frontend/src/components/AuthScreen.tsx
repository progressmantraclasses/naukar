import React, { useState, useEffect } from "react"
import { useAuthStore } from "../store/authStore"

type Mode = "login" | "register"

export function AuthScreen() {
  const [mode, setMode] = useState<Mode>("login")
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [confirmPassword, setConfirmPassword] = useState("")
  const [localError, setLocalError] = useState("")
  const { login, register, isLoading, error, clearError } = useAuthStore()

  useEffect(() => {
    clearError()
    setLocalError("")
  }, [mode])

  const validate = (): boolean => {
    if (!email.includes("@")) { setLocalError("Enter a valid email address."); return false }
    if (password.length < 8) { setLocalError("Password must be at least 8 characters."); return false }
    if (mode === "register") {
      if (!/[A-Za-z]/.test(password) || !/[0-9]/.test(password)) {
        setLocalError("Password must contain at least one letter and one digit.")
        return false
      }
      if (password !== confirmPassword) { setLocalError("Passwords do not match."); return false }
    }
    return true
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLocalError("")
    clearError()
    if (!validate()) return
    try {
      if (mode === "login") await login(email, password)
      else await register(email, password)
    } catch {}
  }

  const displayError = localError || error

  return (
    <div style={{
      minHeight: "100vh", background: "var(--bg-base, #080810)",
      display: "flex", alignItems: "center", justifyContent: "center",
      fontFamily: "Inter, system-ui, sans-serif",
      padding: "20px",
    }}>
      {/* Background glow */}
      <div style={{
        position: "fixed", inset: 0, pointerEvents: "none", zIndex: 0,
        background: "radial-gradient(ellipse 60% 50% at 50% 0%, rgba(99,102,241,0.12) 0%, transparent 70%)",
      }} />

      <div style={{
        width: "100%", maxWidth: 420, zIndex: 1,
        background: "rgba(16,16,32,0.95)",
        border: "1px solid rgba(99,102,241,0.25)",
        borderRadius: 20,
        boxShadow: "0 24px 80px rgba(0,0,0,0.6), 0 0 0 1px rgba(99,102,241,0.1)",
        overflow: "hidden",
      }}>
        {/* Header */}
        <div style={{
          padding: "32px 32px 24px",
          borderBottom: "1px solid rgba(255,255,255,0.05)",
          textAlign: "center",
        }}>
          <div style={{
            width: 52, height: 52, borderRadius: 14,
            background: "linear-gradient(135deg, #6366f1, #8b5cf6)",
            display: "flex", alignItems: "center", justifyContent: "center",
            fontSize: 24, fontWeight: 900, color: "#fff",
            margin: "0 auto 16px",
            boxShadow: "0 8px 24px rgba(99,102,241,0.4)",
          }}>N</div>
          <div style={{ fontSize: 22, fontWeight: 700, color: "#fff", marginBottom: 6 }}>
            {mode === "login" ? "Welcome back" : "Create account"}
          </div>
          <div style={{ fontSize: 13, color: "#666" }}>
            {mode === "login" ? "Sign in to your AI workforce" : "Start your autonomous AI team"}
          </div>
        </div>

        {/* Tab switcher */}
        <div style={{
          display: "flex", padding: "16px 24px 0",
          gap: 4,
        }}>
          {(["login", "register"] as Mode[]).map(m => (
            <button key={m}
              onClick={() => setMode(m)}
              style={{
                flex: 1, padding: "9px 0",
                borderRadius: 8, border: "none", cursor: "pointer",
                fontSize: 13, fontWeight: 600,
                background: mode === m ? "rgba(99,102,241,0.2)" : "transparent",
                color: mode === m ? "#a5b4fc" : "#555",
                transition: "all 0.2s",
                letterSpacing: "0.01em",
              }}
            >
              {m === "login" ? "Sign In" : "Sign Up"}
            </button>
          ))}
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} style={{ padding: "20px 32px 32px" }}>
          {displayError && (
            <div style={{
              background: "rgba(239,68,68,0.12)", border: "1px solid rgba(239,68,68,0.3)",
              borderRadius: 10, padding: "10px 14px", marginBottom: 16,
              fontSize: 13, color: "#fca5a5", lineHeight: 1.4,
            }}>
              {displayError}
            </div>
          )}

          <div style={{ marginBottom: 16 }}>
            <label style={{ display: "block", fontSize: 12, color: "#888", marginBottom: 6, fontWeight: 500 }}>
              Email Address
            </label>
            <input
              id="auth-email"
              type="email"
              value={email}
              onChange={e => setEmail(e.target.value)}
              placeholder="you@example.com"
              required
              autoFocus
              style={{
                width: "100%", boxSizing: "border-box",
                padding: "11px 14px",
                background: "rgba(255,255,255,0.04)",
                border: "1px solid rgba(255,255,255,0.1)",
                borderRadius: 10, color: "#fff", fontSize: 14,
                outline: "none", transition: "border 0.2s",
              }}
              onFocus={e => (e.target.style.borderColor = "rgba(99,102,241,0.6)")}
              onBlur={e => (e.target.style.borderColor = "rgba(255,255,255,0.1)")}
            />
          </div>

          <div style={{ marginBottom: mode === "register" ? 16 : 24 }}>
            <label style={{ display: "block", fontSize: 12, color: "#888", marginBottom: 6, fontWeight: 500 }}>
              Password
            </label>
            <input
              id="auth-password"
              type="password"
              value={password}
              onChange={e => setPassword(e.target.value)}
              placeholder={mode === "register" ? "Min. 8 characters, with a digit" : "••••••••"}
              required
              style={{
                width: "100%", boxSizing: "border-box",
                padding: "11px 14px",
                background: "rgba(255,255,255,0.04)",
                border: "1px solid rgba(255,255,255,0.1)",
                borderRadius: 10, color: "#fff", fontSize: 14,
                outline: "none", transition: "border 0.2s",
              }}
              onFocus={e => (e.target.style.borderColor = "rgba(99,102,241,0.6)")}
              onBlur={e => (e.target.style.borderColor = "rgba(255,255,255,0.1)")}
            />
          </div>

          {mode === "register" && (
            <div style={{ marginBottom: 24 }}>
              <label style={{ display: "block", fontSize: 12, color: "#888", marginBottom: 6, fontWeight: 500 }}>
                Confirm Password
              </label>
              <input
                id="auth-confirm-password"
                type="password"
                value={confirmPassword}
                onChange={e => setConfirmPassword(e.target.value)}
                placeholder="Repeat password"
                required
                style={{
                  width: "100%", boxSizing: "border-box",
                  padding: "11px 14px",
                  background: "rgba(255,255,255,0.04)",
                  border: "1px solid rgba(255,255,255,0.1)",
                  borderRadius: 10, color: "#fff", fontSize: 14,
                  outline: "none", transition: "border 0.2s",
                }}
                onFocus={e => (e.target.style.borderColor = "rgba(99,102,241,0.6)")}
                onBlur={e => (e.target.style.borderColor = "rgba(255,255,255,0.1)")}
              />
            </div>
          )}

          <button
            id="auth-submit"
            type="submit"
            disabled={isLoading}
            style={{
              width: "100%", padding: "12px 0",
              background: isLoading
                ? "rgba(99,102,241,0.4)"
                : "linear-gradient(135deg, #6366f1, #8b5cf6)",
              border: "none", borderRadius: 10,
              color: "#fff", fontSize: 14, fontWeight: 700,
              cursor: isLoading ? "not-allowed" : "pointer",
              letterSpacing: "0.02em",
              boxShadow: isLoading ? "none" : "0 4px 16px rgba(99,102,241,0.4)",
              transition: "all 0.2s",
            }}
          >
            {isLoading ? "Please wait..." : (mode === "login" ? "Sign In" : "Create Account")}
          </button>

          {mode === "register" && (
            <div style={{ marginTop: 16, fontSize: 11, color: "#555", textAlign: "center", lineHeight: 1.5 }}>
              By signing up, you agree to our terms of service.
              Your data is isolated in your private workspace.
            </div>
          )}
        </form>
      </div>
    </div>
  )
}
