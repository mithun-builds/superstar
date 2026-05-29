// Approval-chain widget: shows every stage in order, highlights the active
// one, and renders an approve/reject form for the active stage when the user
// is allowed to act (v0: anyone authenticated can decide — role-based gating
// is a Phase 1.5 concern).

import { useState } from "react";
import { api } from "../api/client";
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
              <span className="stage-name">{s.order}. {s.name}</span>
              <span className={`status status-${s.status}`}>{s.status}</span>
            </div>
            {s.note && <p className="stage-note">"{s.note}"</p>}
            {s.decided_at && (
              <p className="stage-meta">
                decided {new Date(s.decided_at).toLocaleString()}
              </p>
            )}
            {s.id === stages.active_stage_id && (
              <StageDecideForm
                ticketId={ticketId}
                stage={s}
                orgSlug={orgSlug}
                onChange={onChange}
              />
            )}
          </li>
        ))}
      </ol>
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
      setError(e instanceof Error ? e.message : String(e));
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
