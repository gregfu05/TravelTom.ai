import type { Recommendation } from "../../../api/client";
import type {
  BookingStubConfirmation,
  SavedRecommendation,
  SessionItinerary,
} from "../../../store/session";
import { getRecommendationName } from "../lib/plannerChat";

interface PlannerRecommendationsSurfaceProps {
  isDrawerOpen: boolean;
  onCloseDrawer: () => void;
  recommendations: Recommendation[];
  recsJustArrived: boolean;
  savedRecommendations: SavedRecommendation[];
  bookingConfirmation: BookingStubConfirmation | null;
  latestItinerary: SessionItinerary | null;
  onBook: (item: Recommendation) => void;
  onRemoveSavedRecommendation: (itemId: string) => void;
  onSaveRecommendation: (item: Recommendation) => void;
}

function RecommendationCards({
  bookingConfirmation,
  onBook,
  onRemoveSavedRecommendation,
  onSaveRecommendation,
  recommendations,
  savedItemIds,
}: {
  bookingConfirmation: BookingStubConfirmation | null;
  onBook: (item: Recommendation) => void;
  onRemoveSavedRecommendation: (itemId: string) => void;
  onSaveRecommendation: (item: Recommendation) => void;
  recommendations: Recommendation[];
  savedItemIds: Set<string>;
}) {
  return (
    <ol className="recommendation-list">
      {recommendations.map((item) => {
        const isSaved = savedItemIds.has(item.itemId);
        const itemName = getRecommendationName(item);
        const bookingConfirmed = bookingConfirmation?.itemId === item.itemId;

        return (
          <li
            key={`${item.itemId}-${item.rank}`}
            className="recommendation-list-item"
          >
            <article
              className={`recommendation-card ${isSaved ? "recommendation-card-saved" : ""}`}
            >
              <div className="recommendation-card-head">
                <p className="recommendation-rank">#{item.rank}</p>
                <div className="recommendation-card-badges">
                  {isSaved ? <p className="recommendation-saved">Saved</p> : null}
                  <p className="recommendation-type">{item.itemType}</p>
                </div>
              </div>
              <h3>{itemName}</h3>
              <p className="recommendation-subline">
                {item.metadata?.city
                  ? String(item.metadata.city)
                  : "Location unavailable"}
                {item.metadata?.stars
                  ? ` - ${String(item.metadata.stars)} stars`
                  : ""}
              </p>
              {item.explanation ? (
                <p className="recommendation-explanation">{item.explanation}</p>
              ) : null}
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
              <div className="recommendation-card-actions">
                <button
                  className="button button-ghost button-xs"
                  type="button"
                  onClick={() =>
                    isSaved
                      ? onRemoveSavedRecommendation(item.itemId)
                      : onSaveRecommendation(item)
                  }
                  aria-pressed={isSaved}
                >
                  {isSaved ? "Remove" : "Save"}
                </button>
                <button
                  className="button button-ghost button-xs"
                  type="button"
                  onClick={() => onBook(item)}
                >
                  Book stub
                </button>
              </div>
              {bookingConfirmed ? (
                <p className="booking-confirmation" role="status">
                  Booking stub confirmed for {itemName}.
                </p>
              ) : null}
            </article>
          </li>
        );
      })}
    </ol>
  );
}

function renderMetadataValue(value: unknown): string {
  if (value === null || value === undefined || value === "") {
    return "Unavailable";
  }

  if (Array.isArray(value)) {
    return value.map(renderMetadataValue).join(", ");
  }

  if (typeof value === "object") {
    return JSON.stringify(value);
  }

  return String(value);
}

function getComparisonFields(items: SavedRecommendation[]) {
  const fields = new Set<string>();
  items.forEach((item) => {
    Object.keys(item.metadata ?? {})
      .filter((key) => key !== "map_url")
      .slice(0, 8)
      .forEach((key) => fields.add(key));
  });
  return Array.from(fields).slice(0, 8);
}

function PlannerWorkflowPanel({
  bookingConfirmation,
  latestItinerary,
  onBookSavedRecommendation,
  onRemoveSavedRecommendation,
  savedRecommendations,
}: {
  bookingConfirmation: BookingStubConfirmation | null;
  latestItinerary: SessionItinerary | null;
  onBookSavedRecommendation: (item: SavedRecommendation) => void;
  onRemoveSavedRecommendation: (itemId: string) => void;
  savedRecommendations: SavedRecommendation[];
}) {
  const comparisonFields = getComparisonFields(savedRecommendations);
  const itineraryDays = latestItinerary?.days ?? [];

  return (
    <section className="planner-workflow-panel" aria-label="Planner workflow">
      <div className="workflow-section">
        <div className="workflow-section-header">
          <div>
            <p className="eyebrow">Shortlist</p>
            <p>{savedRecommendations.length} saved for this session</p>
          </div>
        </div>
        {savedRecommendations.length === 0 ? (
          <p className="workflow-empty">
            Save a recommendation to compare options and use the booking stub.
          </p>
        ) : (
          <ol className="shortlist-list">
            {savedRecommendations.map((item) => {
              const itemName = getRecommendationName(item);
              return (
                <li key={item.itemId} className="shortlist-item">
                  <div>
                    <p className="shortlist-item-name">{itemName}</p>
                    <p className="recommendation-subline">
                      {item.itemType} #{item.rank}
                    </p>
                  </div>
                  <div className="shortlist-actions">
                    <button
                      className="button button-ghost button-xs"
                      type="button"
                      onClick={() => onBookSavedRecommendation(item)}
                    >
                      Book stub
                    </button>
                    <button
                      className="button button-ghost button-xs"
                      type="button"
                      onClick={() => onRemoveSavedRecommendation(item.itemId)}
                    >
                      Remove
                    </button>
                  </div>
                </li>
              );
            })}
          </ol>
        )}
      </div>

      <div className="workflow-section">
        <p className="eyebrow">Compare</p>
        {savedRecommendations.length < 2 ? (
          <p className="workflow-empty">
            Save at least two recommendations to compare them side by side.
          </p>
        ) : (
          <div className="compare-table-wrap">
            <table className="compare-table">
              <thead>
                <tr>
                  <th scope="col">Item</th>
                  <th scope="col">Type</th>
                  <th scope="col">Rank</th>
                  <th scope="col">Score</th>
                  <th scope="col">Why</th>
                  {comparisonFields.map((field) => (
                    <th scope="col" key={field}>
                      {field.replaceAll("_", " ")}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {savedRecommendations.map((item) => (
                  <tr key={item.itemId}>
                    <th scope="row">{getRecommendationName(item)}</th>
                    <td>{item.itemType}</td>
                    <td>#{item.rank}</td>
                    <td>
                      {typeof item.score === "number"
                        ? item.score.toFixed(2)
                        : "Unavailable"}
                    </td>
                    <td>{item.explanation ?? "Unavailable"}</td>
                    {comparisonFields.map((field) => (
                      <td key={field}>
                        {renderMetadataValue(item.metadata?.[field])}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <div className="workflow-section">
        <p className="eyebrow">Itinerary</p>
        {itineraryDays.length === 0 ? (
          <p className="workflow-empty">
            No itinerary has been assembled for this session yet.
          </p>
        ) : (
          <ol className="itinerary-list">
            {itineraryDays.map((day, index) => (
              <li key={index} className="itinerary-day">
                <span>Day {index + 1}</span>
                <p>{renderMetadataValue(day)}</p>
              </li>
            ))}
          </ol>
        )}
      </div>

      <div className="workflow-section">
        <p className="eyebrow">Booking Stub</p>
        {bookingConfirmation ? (
          <p className="booking-confirmation" role="status">
            Simulated booking confirmed for {bookingConfirmation.itemName}. No
            reservation, payment, or supplier request was created.
          </p>
        ) : (
          <p className="workflow-empty">
            Use a Book stub action to simulate conversion without creating a real
            booking.
          </p>
        )}
      </div>
    </section>
  );
}

export function PlannerRecommendationsToggle({
  isDrawerOpen,
  onOpenDrawer,
  recommendationsCount,
  recsJustArrived,
  workflowCount = recommendationsCount,
}: {
  isDrawerOpen: boolean;
  onOpenDrawer: () => void;
  recommendationsCount: number;
  recsJustArrived: boolean;
  workflowCount?: number;
}) {
  if (workflowCount === 0) {
    return null;
  }

  const label =
    recommendationsCount > 0
      ? `${recommendationsCount} Picks`
      : `${workflowCount} Saved`;

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
      {label}
    </button>
  );
}

export function PlannerRecommendationsSurface({
  bookingConfirmation,
  isDrawerOpen,
  latestItinerary,
  onCloseDrawer,
  onBook,
  onRemoveSavedRecommendation,
  onSaveRecommendation,
  recommendations,
  recsJustArrived,
  savedRecommendations,
}: PlannerRecommendationsSurfaceProps) {
  const savedItemIds = new Set(savedRecommendations.map((item) => item.itemId));
  const hasRecommendations = recommendations.length > 0;

  return (
    <>
      <aside
        className={`recommendations-panel ${recsJustArrived ? "recommendations-panel-arrive" : ""}`}
        aria-live="polite"
      >
        {hasRecommendations ? (
          <>
            <div className="recommendations-panel-header">
              <div>
                <p className="eyebrow">Current Picks</p>
                <p>{recommendations.length} current candidates from this turn</p>
              </div>
            </div>
            <RecommendationCards
              bookingConfirmation={bookingConfirmation}
              onBook={onBook}
              onRemoveSavedRecommendation={onRemoveSavedRecommendation}
              onSaveRecommendation={onSaveRecommendation}
              recommendations={recommendations}
              savedItemIds={savedItemIds}
            />
          </>
        ) : null}
        <PlannerWorkflowPanel
          bookingConfirmation={bookingConfirmation}
          latestItinerary={latestItinerary}
          onBookSavedRecommendation={onBook}
          onRemoveSavedRecommendation={onRemoveSavedRecommendation}
          savedRecommendations={savedRecommendations}
        />
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
        aria-hidden={!isDrawerOpen}
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
        {hasRecommendations ? (
          <RecommendationCards
            bookingConfirmation={bookingConfirmation}
            onBook={onBook}
            onRemoveSavedRecommendation={onRemoveSavedRecommendation}
            onSaveRecommendation={onSaveRecommendation}
            recommendations={recommendations}
            savedItemIds={savedItemIds}
          />
        ) : null}
        <PlannerWorkflowPanel
          bookingConfirmation={bookingConfirmation}
          latestItinerary={latestItinerary}
          onBookSavedRecommendation={onBook}
          onRemoveSavedRecommendation={onRemoveSavedRecommendation}
          savedRecommendations={savedRecommendations}
        />
      </aside>
    </>
  );
}
