// TypeScript shapes mirroring Django serializers.
// Hand-maintained for now — no codegen until the API stabilizes.

export type Decision = "approve" | "reject" | "escalate";
export type TicketStatus =
  | "open"
  | "escalated"
  | "decided"
  | "approved"
  | "rejected"
  | "closed";

export interface OrgMembership {
  id: string;
  org_slug: string;
  org_name: string;
  role: "owner" | "admin" | "approver" | "requester";
  created_at: string;
}

export interface Me {
  id: string;
  email: string;
  full_name: string;
  is_staff: boolean;
  is_superuser: boolean;
  memberships: OrgMembership[];
}

export interface PluginFieldSpec {
  name: string;
  type: "string" | "int" | "bool" | "text" | "enum";
  label: string;
  required: boolean;
  choices: string[];
  help_text: string;
}

export interface PluginSummary {
  identifier: string;
  display_name: string;
  fields: PluginFieldSpec[];
  ai_enabled: boolean;
  shadow_mode: boolean;
}

export interface Ticket {
  id: string;
  ticket_type: string;
  title: string;
  payload: Record<string, unknown>;
  status: TicketStatus;
  decision_summary: string;
  created_at: string;
  updated_at: string;
  closed_at: string | null;
}

export interface ApprovalStage {
  id: string;
  order: number;
  name: string;
  mode: string;
  status: "pending" | "approved" | "rejected" | "skipped";
  decided_by: string | null;
  decided_at: string | null;
  note: string;
}

export interface StagesResponse {
  active_stage_id: string | null;
  stages: ApprovalStage[];
}

export interface DecideResult {
  decision_id: string;
  outcome: Decision | "error";
  cited_rule_ids: string[];
  confidence: number;
  reason_text: string;
  price_delta: string;
  post_actions: string[];
  shadow_mode: boolean;
}

export interface StageDecisionResult {
  stage: ApprovalStage;
  ticket_status: TicketStatus;
  next_stage: ApprovalStage | null;
}

export interface Paginated<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}
