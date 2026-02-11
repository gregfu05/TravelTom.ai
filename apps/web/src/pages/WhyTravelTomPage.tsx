import { Link } from "react-router-dom";

import { TopNav } from "../components/TopNav";
import { featurePillars, whyTrustSignals } from "../content/siteContent";

export function WhyTravelTomPage() {
  return (
    <main className="home page">
      <TopNav />

      <section className="page-hero">
        <p className="eyebrow">Why TravelTom</p>
        <h1>Built to make travel choices clearer, faster, and more confident.</h1>
        <p className="page-lead">
          TravelTom is designed for users who want helpful AI guidance without
          opaque recommendations. The system is structured to stay explainable
          from the first prompt to the shortlist.
        </p>
      </section>

      <section className="section">
        <div className="section-heading">
          <p className="eyebrow">Core Value</p>
          <h2>Every recommendation has a reason behind it</h2>
        </div>
        <div className="feature-grid">
          {featurePillars.map((feature) => (
            <article key={feature.title} className="feature-card">
              <p className="feature-kicker">{feature.kicker}</p>
              <h3>{feature.title}</h3>
              <p>{feature.description}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="section">
        <div className="section-heading">
          <p className="eyebrow">Trust Signals</p>
          <h2>Product decisions that reduce guesswork</h2>
        </div>
        <div className="trust-grid">
          {whyTrustSignals.map((signal) => (
            <article key={signal.title} className="trust-card">
              <h3>{signal.title}</h3>
              <p>{signal.detail}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="cta-panel">
        <div>
          <p className="eyebrow">Continue</p>
          <h2>Move into the planner and start chatting with TravelTom</h2>
          <p>
            If you want more architecture detail first, open the process page.
            Otherwise, jump straight into the planner route.
          </p>
        </div>
        <div className="cta-button-group">
          <Link className="button button-primary" to="/planner">
            Open Planner
          </Link>
          <Link className="button button-ghost" to="/how-it-works">
            View How It Works
          </Link>
        </div>
      </section>
    </main>
  );
}
