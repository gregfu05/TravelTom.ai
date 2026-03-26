import { useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useSessionStore } from "../store/session";
import { ChatView } from "../components/ChatView";
import { TopNav } from "../components/TopNav";

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
