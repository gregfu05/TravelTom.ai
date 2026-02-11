import { Link } from "react-router-dom";

import { TopNav } from "../components/TopNav";
import { planningSteps, systemFlowSteps } from "../content/siteContent";

export function HowItWorksPage() {
  return (
    <main className="home page">
      <TopNav />

      <section className="page-hero">
        <p className="eyebrow">How It Works</p>
        <h1>A practical flow from intent capture to trip-ready shortlist.</h1>
        <p className="page-lead">
          TravelTom combines conversational input with deterministic ranking so
          recommendations remain structured, testable, and easy to act on.
        </p>
      </section>

      <section className="section">
        <div className="section-heading">
          <p className="eyebrow">User Journey</p>
          <h2>Simple steps for planning in one loop</h2>
        </div>
        <div className="flow-grid">
          {planningSteps.map((item) => (
            <article key={item.step} className="flow-card">
              <p className="flow-step">{item.step}</p>
              <h3>{item.title}</h3>
              <p>{item.description}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="section">
        <div className="section-heading">
          <p className="eyebrow">System Flow</p>
          <h2>What happens under the hood</h2>
        </div>
        <div className="system-grid">
          {systemFlowSteps.map((step) => (
            <article key={step.title} className="system-card">
              <h3>{step.title}</h3>
              <p>{step.detail}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="cta-panel">
        <div>
          <p className="eyebrow">Ready</p>
          <h2>Continue into the planner and start your chat</h2>
          <p>
            The next implementation step is the interactive chat UI, followed by
            recommendations and shortlist pages.
          </p>
        </div>
        <Link className="button button-primary" to="/planner">
          Open Planner
        </Link>
      </section>
    </main>
  );
}
