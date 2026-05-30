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

// Sync-era shape, kept for back-compat in any code that still uses it.
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

// POST /api/tickets/<id>/decide/ now returns 202 with a Celery task id
// the client polls. This is the dispatch response.
export interface DecideDispatched {
  task_id: string;
  ticket_id: string;
  poll_url: string;
  status: "dispatched";
}

// GET /api/decisions/by-task/<id>/ returns one of two shapes:
//   202 — worker hasn't written the Decision yet
export interface DecisionPending {
  status: "pending";
  task_id: string;
}
//   200 — Decision is in
export interface DecisionRow {
  id: string;
  outcome: Decision | "error";
  cited_rule_ids: string[];
  confidence: number;
  reason_text: string;
  price_delta: string;
  post_actions: string[];
  shadow_mode: boolean;
  task_id: string;
  started_at: string | null;
  created_at: string;
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

// ---------------------------------------------------------------------------
// Admin shapes — for the /api/admin/* endpoints. Editable counterparts of
// the discovery shapes above.
// ---------------------------------------------------------------------------

export interface AdminTicketTypeField {
  id: string;
  order: number;
  name: string;
  field_type: "string" | "int" | "bool" | "text" | "enum";
  label: string;
  required: boolean;
  choices: string[];
  help_text: string;
}

export interface AdminWorkflowStage {
  id: string;
  order: number;
  name: string;
  approvers: string[];
  mode: "any_member" | "unanimous_team" | "majority" | "specific_user";
  sla_hours: number | null;
}

export interface AdminTicketType {
  id: string;
  identifier: string;
  display_name: string;
  description: string;
  sequential: boolean;
  ai_enabled: boolean;
  confidence_threshold: number;
  require_citation: boolean;
  shadow_mode: boolean;
  system_prompt: string;
  notifications: Record<string, unknown>;
  is_active: boolean;
  fields: AdminTicketTypeField[];
  workflow_stages: AdminWorkflowStage[];
  created_at: string;
  updated_at: string;
}

export interface AdminRule {
  id: string;
  rule_id: string;
  title: string;
  body: string;
  category: string;
  subcategory: string;
  decision_hint: "approve" | "reject" | "escalate" | "";
  price_delta: string;
  post_actions: string[];
  applies_when: Record<string, unknown> | null;
  extra: Record<string, unknown>;
  ingested_at: string;
}

// Team + membership (admin side).
export interface AdminTeamMembership {
  id: string;
  user: string;            // user UUID
  user_email: string;
  user_full_name: string;
  created_at: string;
}

export interface AdminTeam {
  id: string;
  slug: string;
  name: string;
  description: string;
  memberships: AdminTeamMembership[];
  member_count: number;
  created_at: string;
  updated_at: string;
}
