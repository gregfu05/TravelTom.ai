import { useQuery } from "@tanstack/react-query";
import { NavLink } from "react-router-dom";

import { apiClient } from "../api/client";
import { getApiStatusText } from "../content/siteContent";

function getNavLinkClass({ isActive }: { isActive: boolean }): string {
  return isActive ? "active" : "";
}

export function TopNav() {
  const healthQuery = useQuery({
    queryKey: ["health"],
    queryFn: ({ signal }) => apiClient.getHealth(signal),
    staleTime: 60_000,
  });

  const apiStatus = getApiStatusText(healthQuery.isSuccess, healthQuery.isError);

  return (
    <header className="home-nav">
      <NavLink className="brand" to="/" aria-label="TravelTom homepage">
        <span className="brand-mark" aria-hidden="true">
          TT
        </span>
        <span className="brand-text">TravelTom.ai</span>
      </NavLink>

      <nav className="home-nav-links" aria-label="Primary">
        <NavLink to="/why-traveltom" className={getNavLinkClass}>
          Why TravelTom
        </NavLink>
        <NavLink to="/how-it-works" className={getNavLinkClass}>
          How It Works
        </NavLink>
      </nav>

      <div className="status-and-cta">
        <span className="api-status" data-status={apiStatus}>
          {apiStatus}
        </span>
        <NavLink className="button button-sm" to="/planner">
          Open Planner
        </NavLink>
      </div>
    </header>
  );
}
