import type { Recommendation } from "../../../api/client";
import { getRecommendationName } from "../lib/plannerChat";

interface PlannerRecommendationsSurfaceProps {
  isDrawerOpen: boolean;
  onCloseDrawer: () => void;
  recommendations: Recommendation[];
  recsJustArrived: boolean;
}

function RecommendationCards({
  recommendations,
}: {
  recommendations: Recommendation[];
}) {
  return (
    <ol className="recommendation-list">
      {recommendations.map((item) => (
        <li
          key={`${item.itemId}-${item.rank}`}
          className="recommendation-list-item"
        >
          <article className="recommendation-card">
            <div className="recommendation-card-head">
              <p className="recommendation-rank">#{item.rank}</p>
              <div className="recommendation-card-badges">
                <p className="recommendation-type">{item.itemType}</p>
                <p className="recommendation-score">
                  Score {item.score.toFixed(2)}
                </p>
              </div>
            </div>
            <h3>{getRecommendationName(item)}</h3>
            <p className="recommendation-subline">
              {item.metadata?.city
                ? String(item.metadata.city)
                : "Location unavailable"}
              {item.metadata?.stars ? ` - ${String(item.metadata.stars)} stars` : ""}
            </p>
            {typeof item.metadata?.map_url === "string" ? (
              <a
                className="recommendation-map-link"
                href={item.metadata.map_url}
                target="_blank"
                rel="noopener noreferrer"
              >
                View on map
              </a>
            ) : null}
            <details className="recommendation-details">
              <summary>Why this pick</summary>
              <p>{item.explanation}</p>
            </details>
          </article>
        </li>
      ))}
    </ol>
  );
}

export function PlannerRecommendationsToggle({
  isDrawerOpen,
  onOpenDrawer,
  recommendationsCount,
  recsJustArrived,
}: {
  isDrawerOpen: boolean;
  onOpenDrawer: () => void;
  recommendationsCount: number;
  recsJustArrived: boolean;
}) {
  if (recommendationsCount === 0) {
    return null;
  }

  return (
    <button
      className={`picks-glow-pill picks-glow-pill-mobile ${recsJustArrived ? "picks-glow-pill-pulse" : ""}`}
      onClick={onOpenDrawer}
      type="button"
      aria-expanded={isDrawerOpen}
      aria-controls="recommendations-drawer"
    >
      <span className="picks-glow-pill-sparkle" aria-hidden="true">
        *
      </span>
      {recommendationsCount} Picks
    </button>
  );
}

export function PlannerRecommendationsSurface({
  isDrawerOpen,
  onCloseDrawer,
  recommendations,
  recsJustArrived,
}: PlannerRecommendationsSurfaceProps) {
  if (recommendations.length === 0) {
    return null;
  }

  return (
    <>
      <aside
        className={`recommendations-panel ${recsJustArrived ? "recommendations-panel-arrive" : ""}`}
        aria-live="polite"
      >
        <div className="recommendations-panel-header">
          <div>
            <p className="eyebrow">Current Picks</p>
            <p>{recommendations.length} current candidates from this turn</p>
          </div>
        </div>
        <RecommendationCards recommendations={recommendations} />
      </aside>

      {isDrawerOpen ? (
        <div
          className="drawer-overlay"
          onClick={onCloseDrawer}
          aria-hidden="true"
        />
      ) : null}

      <aside
        id="recommendations-drawer"
        className={`drawer ${isDrawerOpen ? "drawer-open" : ""}`}
        role="dialog"
        aria-modal="true"
        aria-label="Recommendations"
        aria-live="polite"
      >
        <div className="drawer-header">
          <div>
            <p className="eyebrow">Recommendations</p>
            <p className="drawer-subtitle">
              {recommendations.length} current candidates from this turn
            </p>
          </div>
          <button
            className="button button-ghost button-xs"
            onClick={onCloseDrawer}
            type="button"
          >
            Close
          </button>
        </div>
        <RecommendationCards recommendations={recommendations} />
      </aside>
    </>
  );
}
