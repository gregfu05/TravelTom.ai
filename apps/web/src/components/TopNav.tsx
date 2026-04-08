import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { NavLink, useLocation } from "react-router-dom";
import { useSessionStore } from "../store/session";

import { apiClient } from "../api/client";
import { getApiStatusText } from "../content/siteContent";

function getNavLinkClass({ isActive }: { isActive: boolean }): string {
  return isActive ? "active" : "";
}

export function TopNav() {
  const [isMenuOpen, setIsMenuOpen] = useState(false);
  const location = useLocation();
  const healthQuery = useQuery({
    queryKey: ["health"],
    queryFn: ({ signal }) => apiClient.getHealth(signal),
    staleTime: 60_000,
  });

  const apiStatus = getApiStatusText(healthQuery.isSuccess, healthQuery.isError);
  const { authToken, resetConversation, setAuthToken } = useSessionStore();

  useEffect(() => {
    setIsMenuOpen(false);
  }, [location.pathname]);

  async function handleLogout() {
    if (!authToken) {
      return;
    }

    try {
      await apiClient.logout(authToken);
    } catch {
      // Clear local auth state even if backend logout fails or token already expired.
    } finally {
      resetConversation();
      setAuthToken(null);
    }
  }

  return (
    <header className="home-nav">
      <NavLink className="brand" to="/" aria-label="TravelTom homepage">
        <span className="brand-mark" aria-hidden="true">
          TT
        </span>
        <span className="brand-text">TravelTom.ai</span>
      </NavLink>

      <nav className="home-nav-links" aria-label="Primary">
        <NavLink to="/planner" className={getNavLinkClass}>
          Planner
        </NavLink>
        <NavLink to="/why-traveltom" className={getNavLinkClass}>
          Why TravelTom
        </NavLink>
        <NavLink to="/how-it-works" className={getNavLinkClass}>
          How It Works
        </NavLink>
      </nav>

      <button
        type="button"
        className="button button-sm nav-menu-toggle"
        aria-expanded={isMenuOpen}
        aria-controls="mobile-primary-nav"
        onClick={() => setIsMenuOpen((open) => !open)}
      >
        {isMenuOpen ? "Close" : "Menu"}
      </button>

      <div className="status-and-cta">
        <span className="api-status" data-status={apiStatus}>
          {apiStatus}
        </span>
        {authToken ? (
          <button className="button button-sm" onClick={() => void handleLogout()}>
            Logout
          </button>
        ) : (
          <>
            <NavLink className="button button-sm" to="/login">
              Login
            </NavLink>
            <NavLink className="button button-sm" to="/signup">
              Signup
            </NavLink>
          </>
        )}
      </div>

      <div
        className={`mobile-nav-panel ${isMenuOpen ? "mobile-nav-panel-open" : ""}`}
        id="mobile-primary-nav"
        aria-hidden={!isMenuOpen}
      >
          <nav className="mobile-nav-links" aria-label="Mobile primary">
            <NavLink to="/planner" className={getNavLinkClass}>
              Planner
            </NavLink>
            <NavLink to="/why-traveltom" className={getNavLinkClass}>
              Why TravelTom
            </NavLink>
            <NavLink to="/how-it-works" className={getNavLinkClass}>
              How It Works
            </NavLink>
          </nav>
          <div className="mobile-nav-footer">
            <span className="api-status" data-status={apiStatus}>
              {apiStatus}
            </span>
            {authToken ? (
              <button className="button button-sm" onClick={() => void handleLogout()}>
                Logout
              </button>
            ) : (
              <div className="mobile-nav-actions">
                <NavLink className="button button-sm" to="/login">
                  Login
                </NavLink>
                <NavLink className="button button-sm" to="/signup">
                  Signup
                </NavLink>
              </div>
            )}
          </div>
        </div>
    </header>
  );
}
