import { BrowserRouter } from "react-router-dom";

import { AppRoutes } from "./app/routes";
import { AppShell } from "./components/AppShell/AppShell";

export default function App() {
  return (
    <BrowserRouter>
      <AppShell>
        <AppRoutes />
      </AppShell>
    </BrowserRouter>
  );
}
