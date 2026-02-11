import { Link } from "react-router-dom";

import { TopNav } from "../components/TopNav";
import { recommendationPreview } from "../content/siteContent";

export function HomePage() {
  return (
    <main id="top" className="home">
      <TopNav />

      <section className="hero-grid">
        <div className="hero-copy">
          <p className="eyebrow">AI-Powered Travel Concierge</p>
          <h1>Plan an incredible trip with one conversation.</h1>
          <p className="hero-description">
            TravelTom captures your intent, applies deterministic ranking, and
            presents clear recommendations across destinations, hotels, and
            flights.
          </p>
          <div className="hero-actions">
            <Link className="button button-primary" to="/planner">
              Start Planning
            </Link>
            <Link className="button button-ghost" to="/why-traveltom">
              See the Flow
            </Link>
          </div>
          <ul className="hero-trust" aria-label="TravelTom guarantees">
            <li>Deterministic recommendations</li>
            <li>Constraint-aware ranking</li>
            <li>Responsive, mobile-first planning UX</li>
          </ul>
        </div>

        <aside className="hero-panel" aria-label="Travel planner snapshot">
          <div className="hero-panel-header">
            <span className="status-dot" aria-hidden="true" />
            <p>Planning session preview</p>
          </div>

          <p className="chat-bubble chat-bubble-user">
            I want a 7-day Europe trip in June with a 2,500 USD budget.
          </p>
          <p className="chat-bubble chat-bubble-assistant">
            Great. I found high-value options with balanced flight time and
            hotel quality. Here are your top picks:
          </p>

          <div className="preview-grid">
            {recommendationPreview.map((item) => (
              <article
                key={item.title}
                className="preview-card"
                data-type={item.itemType}
              >
                <p className="preview-rank">{item.rank}</p>
                <h3>{item.title}</h3>
                <p>{item.detail}</p>
              </article>
            ))}
          </div>
        </aside>
      </section>

      <section className="section">
        <div className="section-heading">
          <p className="eyebrow">Explore Next</p>
          <h2>Start with the pages that explain the product clearly</h2>
        </div>

        <div className="subtle-grid">
          <article className="feature-card">
            <p className="feature-kicker">Why TravelTom</p>
            <h3>Understand what makes this planner better</h3>
            <p>
              See the design principles behind deterministic travel
              recommendations and clearer trip decisions.
            </p>
            <Link className="button button-ghost inline-action" to="/why-traveltom">
              Read Why TravelTom
            </Link>
          </article>
          <article className="flow-card">
            <p className="flow-step">How It Works</p>
            <h3>Review the trip flow from prompt to shortlist</h3>
            <p>
              Walk through the exact interaction sequence and system behavior
              that powers the TravelTom planning loop.
            </p>
            <Link className="button button-ghost inline-action" to="/how-it-works">
              Read How It Works
            </Link>
          </article>
        </div>
      </section>

      <section className="cta-panel">
        <div>
          <p className="eyebrow">Ready to build your next trip?</p>
          <h2>Homepage complete. Chat planner is the next build target.</h2>
          <p>
            This foundation is ready for the next step: integrating the chat
            view, recommendation panels, and shortlist interactions.
          </p>
        </div>
        <Link className="button button-primary" to="/planner">
          Continue to Planner Build
        </Link>
      </section>
    </main>
  );
}
