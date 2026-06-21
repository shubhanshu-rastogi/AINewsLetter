import { FormEvent, useState } from "react";
import { useAuth } from "../auth";
import { ApiError } from "../api";

export default function Login() {
  const { login } = useAuth();
  const [token, setTokenInput] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await login(token.trim());
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Login failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="center-screen">
      <form className="card login-card" onSubmit={onSubmit}>
        <h1 style={{ marginBottom: 4 }}>
          AI<span style={{ color: "var(--accent)" }}>·</span>Newsletter
        </h1>
        <p className="muted" style={{ marginTop: 0 }}>
          Enter the admin token to access the operator console.
        </p>
        {error && <div className="error-banner">{error}</div>}
        <div className="field">
          <label htmlFor="token">Admin token</label>
          <input
            id="token"
            type="password"
            value={token}
            autoFocus
            onChange={(e) => setTokenInput(e.target.value)}
            placeholder="REVIEW_AUTH_TOKEN"
          />
        </div>
        <button className="btn btn-primary" type="submit" disabled={busy} style={{ width: "100%" }}>
          {busy ? <span className="spin" /> : "Sign in"}
        </button>
      </form>
    </div>
  );
}
