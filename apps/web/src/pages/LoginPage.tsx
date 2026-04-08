import { useState } from "react";
import { Link, Navigate, useLocation, useNavigate } from "react-router-dom";

import { apiClient } from "../api/client";
import { getAuthLinkState, getAuthRedirectTarget } from "../auth/authFlow";
import { AuthLayout } from "../components/AuthLayout";
import { authPageContent } from "../content/siteContent";
import { useSessionStore } from "../store/session";

export function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const navigate = useNavigate();
  const location = useLocation();
  const { authToken, resetConversation, setAuthToken } = useSessionStore();
  const redirectTo = getAuthRedirectTarget(location.state);
  const signupLinkState = getAuthLinkState(location.state);

  if (authToken) {
    return <Navigate replace to="/planner" />;
  }

  async function handleLogin(event: React.FormEvent) {
    event.preventDefault();
    setIsLoading(true);
    setError(null);

    try {
      const response = await apiClient.login({ email, password });
      resetConversation();
      setAuthToken(response.accessToken);
      navigate(redirectTo, { replace: true });
    } catch (caughtError) {
      const message =
        caughtError instanceof Error && caughtError.message
          ? caughtError.message
          : "Invalid email or password.";
      setError(message);
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <AuthLayout
      eyebrow={authPageContent.login.eyebrow}
      title={authPageContent.login.title}
      description={authPageContent.login.description}
      panelTitle={authPageContent.login.panelTitle}
      panelBody={authPageContent.login.panelBody}
      highlights={authPageContent.highlights}
      reassurance={
        <p>
          {authPageContent.login.reassurance}{" "}
          <Link className="auth-inline-link" to="/">
            Review the landing page
          </Link>{" "}
          if you want a quick reset before heading into the planner.
        </p>
      }
    >
      <form onSubmit={handleLogin} className="auth-form">
        <div className="auth-form-heading">
          <h2>Sign in</h2>
          <p>
            {redirectTo === "/planner"
              ? "Head straight into the planner after login."
              : "You will be returned to your previous destination after login."}
          </p>
        </div>
        <label className="auth-field">
          <span>Email</span>
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            autoComplete="email"
            className="auth-input"
          />
        </label>
        <label className="auth-field">
          <span>Password</span>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            autoComplete="current-password"
            className="auth-input"
          />
        </label>
        {error ? (
          <p className="auth-feedback auth-feedback-error" role="alert">
            {error}
          </p>
        ) : (
          <p className="auth-feedback">
            Secure local auth is enabled for this TravelTom workspace.
          </p>
        )}
        <button type="submit" disabled={isLoading} className="button button-primary auth-submit">
          {isLoading ? "Signing you in..." : "Enter the planner"}
        </button>
      </form>
      <p className="auth-alternate">
        {authPageContent.login.alternateLabel}{" "}
        <Link className="auth-inline-link" to="/signup" state={signupLinkState}>
          {authPageContent.login.alternateCta}
        </Link>
      </p>
    </AuthLayout>
  );
}
