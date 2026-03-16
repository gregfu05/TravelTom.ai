import { useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";

import { apiClient } from "../api/client";
import { useSessionStore } from "../store/session";
import "../styles/auth.css";

export function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const navigate = useNavigate();
  const location = useLocation();
  const { setAuthToken } = useSessionStore();

  async function handleLogin(event: React.FormEvent) {
    event.preventDefault();
    setIsLoading(true);
    setError(null);

    try {
      const response = await apiClient.login({ email, password });
      setAuthToken(response.accessToken);
      const redirectTo =
        typeof location.state?.from === "string" ? location.state.from : "/planner";
      navigate(redirectTo, { replace: true });
    } catch {
      setError("Invalid email or password.");
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <div className="auth-page">
      <h1>Login</h1>
      <form onSubmit={handleLogin} className="login-form">
        <label>
          Email
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            className="input-field"
          />
        </label>
        <label>
          Password
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            className="input-field"
          />
        </label>
        {error && <p className="error-message">{error}</p>}
        <button type="submit" disabled={isLoading} className="submit-button">
          {isLoading ? "Logging in..." : "Login"}
        </button>
      </form>
      <p className="signup-link">
        Don&apos;t have an account? <Link to="/signup">Sign up</Link>
      </p>
    </div>
  );
}
