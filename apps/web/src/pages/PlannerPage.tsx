import { Link } from "react-router-dom";

import { ChatView } from "../components/ChatView";
import { TopNav } from "../components/TopNav";

export function PlannerPage() {
  return (
    <main className="home page planner-page">
      <TopNav />

      <section className="planner-hero">
        <div>
          <p className="eyebrow">Trip Planner</p>
          <h1>Chat-first planning starts here.</h1>
          <p className="page-lead">
            Share trip intent and constraints. TravelTom will orchestrate
            deterministic recommendation tooling and return structured options.
          </p>
        </div>
        <Link className="button button-ghost" to="/how-it-works">
          Review How It Works
        </Link>
      </section>

      <ChatView />
    </main>
  );
}
