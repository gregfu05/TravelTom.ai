import { useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { TopNav } from "../../components/TopNav/TopNav";
import { ChatView } from "../../features/planner/components/ChatView/ChatView";
import { useSessionStore } from "../../store/session";

export function PlannerPage() {
  const { authToken } = useSessionStore();
  const navigate = useNavigate();

  useEffect(() => {
    if (!authToken) {
      navigate("/login", { replace: true, state: { from: "/planner" } });
    }
  }, [authToken, navigate]);

  return (
    <main className="home page planner-page planner-chat-active">
      <TopNav />
      <ChatView />
    </main>
  );
}
