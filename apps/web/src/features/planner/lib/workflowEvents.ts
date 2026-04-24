import type { ItemType } from "../../../api/client";

export type PlannerWorkflowEventType =
  | "rec.save"
  | "rec.dismiss"
  | "shortlist.update"
  | "booking.funnel";

export interface PlannerWorkflowEventDetail {
  eventType: PlannerWorkflowEventType;
  sessionId: string;
  itemId?: string;
  itemType?: ItemType;
  step?: "view" | "start" | "confirm";
}

export function trackPlannerWorkflowEvent(detail: PlannerWorkflowEventDetail) {
  window.dispatchEvent(
    new CustomEvent<PlannerWorkflowEventDetail>("traveltom:planner-workflow", {
      detail,
    }),
  );
}
