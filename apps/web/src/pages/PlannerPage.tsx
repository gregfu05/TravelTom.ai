import { ChatView } from "../components/ChatView";
import { TopNav } from "../components/TopNav";

export function PlannerPage() {
  return (
    <main className="planner-fullpage">
      <TopNav />
      <ChatView />
    </main>
  );
}
