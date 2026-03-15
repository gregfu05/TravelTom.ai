import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { apiClient } from "../api/client";
import "../styles/auth.css";

export function SignupPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const navigate = useNavigate();

  async function handleSignup(event: React.FormEvent) {
    event.preventDefault();
    if (password !== confirmPassword) {
      setError("Passwords do not match.");
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      await apiClient.signup({ email, password });
      navigate("/login");
    } catch (err) {
      setError("Failed to create account. Please try again.");
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <div className="auth-page">
      <h1>Signup</h1>
      <form onSubmit={handleSignup} className="signup-form">
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
        <label>
          Confirm Password
          <input
            type="password"
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
            required
            className="input-field"
          />
        </label>
        {error && <p className="error-message">{error}</p>}
        <button type="submit" disabled={isLoading} className="submit-button">
          {isLoading ? "Signing up..." : "Signup"}
        </button>
      </form>
      <p className="login-link">
        Already have an account? <a href="/login">Login</a>
      </p>
    </div>
  );
}
