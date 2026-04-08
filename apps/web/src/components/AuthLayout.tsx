import type { PropsWithChildren, ReactNode } from "react";
import { Link } from "react-router-dom";

import { TopNav } from "./TopNav";

interface AuthLayoutProps extends PropsWithChildren {
  eyebrow: string;
  title: string;
  description: string;
  panelTitle: string;
  panelBody: string;
  highlights: readonly string[];
  reassurance: ReactNode;
}

export function AuthLayout({
  eyebrow,
  title,
  description,
  panelTitle,
  panelBody,
  highlights,
  reassurance,
  children,
}: AuthLayoutProps) {
  return (
    <main className="home page auth-shell">
      <TopNav />

      <section className="auth-grid" aria-labelledby="auth-title">
        <div className="auth-copy">
          <Link className="auth-home-link" to="/">
            Back to home
          </Link>
          <p className="eyebrow">{eyebrow}</p>
          <h1 id="auth-title">{title}</h1>
          <p className="auth-description">{description}</p>
          <div className="auth-panel">
            <p className="auth-panel-kicker">{panelTitle}</p>
            <p className="auth-panel-body">{panelBody}</p>
            <ul className="auth-highlights" aria-label="TravelTom planning highlights">
              {highlights.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </div>
        </div>

        <section className="auth-card" aria-label={title}>
          {children}
          <div className="auth-reassurance">{reassurance}</div>
        </section>
      </section>
    </main>
  );
}
