import { useState } from "react";
import { Link, Navigate, useLocation, useNavigate } from "react-router-dom";

import { apiClient } from "../api/client";
import { getAuthLinkState, getAuthRedirectTarget } from "../auth/authFlow";
import { AuthLayout } from "../components/AuthLayout";
import { authPageContent } from "../content/siteContent";
import { useSessionStore } from "../store/session";

export function SignupPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const navigate = useNavigate();
  const location = useLocation();
  const { authToken, resetConversation, setAuthToken } = useSessionStore();
  const redirectTo = getAuthRedirectTarget(location.state);
  const loginLinkState = getAuthLinkState(location.state);

  if (authToken) {
    return <Navigate replace to="/planner" />;
  }

  async function handleSignup(event: React.FormEvent) {
    event.preventDefault();
    if (password !== confirmPassword) {
      setError("Passwords do not match.");
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      const response = await apiClient.signup({ email, password });
      resetConversation();
      setAuthToken(response.accessToken);
      navigate(redirectTo, { replace: true });
    } catch (caughtError) {
      const message =
        caughtError instanceof Error && caughtError.message
          ? caughtError.message
          : "Failed to create account. Please try again.";
      setError(message);
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <AuthLayout
      eyebrow={authPageContent.signup.eyebrow}
      title={authPageContent.signup.title}
      description={authPageContent.signup.description}
      panelTitle={authPageContent.signup.panelTitle}
      panelBody={authPageContent.signup.panelBody}
      highlights={authPageContent.highlights}
      reassurance={
        <p>
          {authPageContent.signup.reassurance}{" "}
          <Link className="auth-inline-link" to="/">
            Back to home
          </Link>{" "}
          stays available if you want to revisit the product story first.
        </p>
      }
    >
      <form onSubmit={handleSignup} className="auth-form">
        <div className="auth-form-heading">
          <h2>Create account</h2>
          <p>
            {redirectTo === "/planner"
              ? "Your account opens directly into the planner."
              : "Your account will return you to the route that sent you here."}
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
            autoComplete="new-password"
            className="auth-input"
          />
        </label>
        <label className="auth-field">
          <span>Confirm password</span>
          <input
            type="password"
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
            required
            autoComplete="new-password"
            className="auth-input"
          />
        </label>
        {error ? (
          <p className="auth-feedback auth-feedback-error" role="alert">
            {error}
          </p>
        ) : (
          <p className="auth-feedback">
            Choose a strong password you can reuse for the rest of your TravelTom planning.
          </p>
        )}
        <button type="submit" disabled={isLoading} className="button button-primary auth-submit">
          {isLoading ? "Creating your account..." : "Start planning"}
        </button>
      </form>
      <p className="auth-alternate">
        {authPageContent.signup.alternateLabel}{" "}
        <Link className="auth-inline-link" to="/login" state={loginLinkState}>
          {authPageContent.signup.alternateCta}
        </Link>
      </p>
    </AuthLayout>
  );
}
