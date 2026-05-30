// Approval-chain widget. Per stage we show:
//   - the stage name + status pill
//   - vote tally for non-any_member modes (X of Y approved, etc.)
//   - the current user's own vote, if any
//   - approve/reject form on the active stage when they haven't voted yet
//
// Backend's authorization gate decides who can actually vote (org owner/
// admin/superuser bypass; otherwise team membership for team-based modes,
// or email match for specific_user). The UI doesn't try to gate up-front
// — it surfaces backend's 403 if the user lacks permission.

import { useState } from "react";
import { ApiError, api } from "../api/client";
import type { ApprovalStage, StageDecisionResult, StagesResponse } from "../api/types";

interface Props {
  ticketId: string;
  orgSlug: string;
  stages: StagesResponse;
  onChange: () => void;
}

export default function StagesPanel({ ticketId, orgSlug, stages, onChange }: Props) {
  return (
    <div className="stages-panel">
      <h3>Approval chain</h3>
      <ol className="stages-list">
        {stages.stages.map((s) => (
          <li
            key={s.id}
            className={`stage stage-${s.status} ${s.id === stages.active_stage_id ? "stage-active" : ""}`}
          >
            <div className="stage-row">
              <span className="stage-name">
                {s.order}. {s.name}
                <ModeBadge mode={s.mode} />
              </span>
              <span className={`status status-${s.status}`}>{s.status}</span>
            </div>

            <VoteSummary stage={s} />

            {s.note && <p className="stage-note">"{s.note}"</p>}
            {s.decided_at && (
              <p className="stage-meta">
                decided {new Date(s.decided_at).toLocaleString()}
              </p>
            )}

            {s.id === stages.active_stage_id && s.vote_tally.my_vote === null && (
              <StageDecideForm
                ticketId={ticketId}
                stage={s}
                orgSlug={orgSlug}
                onChange={onChange}
              />
            )}
            {s.id === stages.active_stage_id && s.vote_tally.my_vote !== null && (
              <p className="stage-meta">
                You voted <strong className={`status status-${s.vote_tally.my_vote}`}>
                  {s.vote_tally.my_vote}
                </strong>. Waiting for others to reach threshold.
              </p>
            )}
          </li>
        ))}
      </ol>
    </div>
  );
}

/** Small label clarifying the mode for stages that aren't "any one approver".
 *  Skipped for any_member since that's the implied default. */
function ModeBadge({ mode }: { mode: ApprovalStage["mode"] }) {
  if (!mode || mode === "any_member") return null;
  const label = {
    unanimous_team: "unanimous",
    majority: "majority",
    specific_user: "named user",
  }[mode] ?? mode;
  return <span className="mode-badge">{label}</span>;
}

/** Vote tally — only meaningful for multi-voter modes. For any_member,
 *  hide the tally entirely (the stage closes on the first vote, so a
 *  tally never grows past 1 anyway). */
function VoteSummary({ stage }: { stage: ApprovalStage }) {
  if (stage.mode === "any_member") return null;

  const { approves, rejects, required, my_vote } = stage.vote_tally;
  // Threshold semantics for the meter:
  //   unanimous_team  → need ALL of `required` to approve
  //   majority        → need >50% of `required`
  //   specific_user   → need that one vote
  let threshold = required;
  if (stage.mode === "majority") threshold = Math.floor(required / 2) + 1;

  const total = required;
  const cleared = stage.mode === "majority" ? approves >= threshold || rejects >= threshold : approves >= threshold;

  return (
    <div className="vote-summary">
      <div className="vote-counts">
        <span className="vote-pill vote-pill-approve">✓ {approves}</span>
        {rejects > 0 && <span className="vote-pill vote-pill-reject">✗ {rejects}</span>}
        <span className="muted">/ {total} {total === 1 ? "voter" : "voters"}</span>
        {stage.mode !== "specific_user" && total > 0 && (
          <span className="muted small">
            (need {threshold} {stage.mode === "majority" ? "for majority" : "to approve"})
          </span>
        )}
        {my_vote !== null && (
          <span className="vote-mine">
            you: <strong className={`status status-${my_vote}`}>{my_vote}</strong>
          </span>
        )}
      </div>
      {total > 0 && stage.status === "pending" && (
        <div className="vote-meter">
          <div
            className="vote-meter-fill"
            style={{ width: `${Math.min(100, (approves / Math.max(1, threshold)) * 100)}%` }}
          />
        </div>
      )}
      {cleared && stage.status === "pending" && (
        <p className="muted small">Threshold reached — stage will close on the next vote-evaluation pass.</p>
      )}
    </div>
  );
}

function StageDecideForm({
  ticketId,
  stage,
  orgSlug,
  onChange,
}: {
  ticketId: string;
  stage: ApprovalStage;
  orgSlug: string;
  onChange: () => void;
}) {
  const [note, setNote] = useState<string>("");
  const [busy, setBusy] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const decide = async (decision: "approved" | "rejected") => {
    setBusy(true);
    setError(null);
    try {
      await api<StageDecisionResult>(
        `/api/tickets/${ticketId}/stages/${stage.id}/decide/`,
        {
          method: "POST",
          orgSlug,
          body: { decision, note: note.trim() },
        },
      );
      setNote("");
      onChange();
    } catch (e) {
      if (e instanceof ApiError) {
        const body = e.body as { detail?: string } | undefined;
        setError(body?.detail ?? `API ${e.status}`);
      } else {
        setError(e instanceof Error ? e.message : String(e));
      }
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="stage-actions">
      <textarea
        placeholder="Optional note for the requester / approver trail"
        value={note}
        onChange={(e) => setNote(e.target.value)}
        rows={2}
      />
      <div className="btn-row">
        <button type="button" className="btn btn-approve" disabled={busy} onClick={() => decide("approved")}>
          Approve
        </button>
        <button type="button" className="btn btn-reject" disabled={busy} onClick={() => decide("rejected")}>
          Reject
        </button>
      </div>
      {error && <p className="error">{error}</p>}
    </div>
  );
}
