import { ChatView } from "../components/ChatView";
import { TopNav } from "../components/TopNav";

export function PlannerPage() {
  return (
    <main className="home page planner-page planner-chat-active">
      <TopNav />
      <ChatView />
    </main>
  );
}
