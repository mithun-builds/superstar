// Admin → Team edit page.
//
// Mirrors the TicketTypeEdit layout:
//   - Inline-editable name as H1, slug shown as immutable mono identifier
//   - Description hidden behind a "Show advanced settings" disclosure
//   - Members rendered as a one-line list with a quiet inline "+ Add member"
//   - Delete team button lives at the top-right as btn-danger

import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api } from "../../api/client";
import { useApi, useMutation } from "../../api/hooks";
import type { AdminTeam, AdminTeamMembership } from "../../api/types";
import { useOrgRequired } from "../../contexts/OrgContext";

export default function TeamEdit() {
  const orgSlug = useOrgRequired();
  const navigate = useNavigate();
  const { teamId } = useParams<{ teamId: string }>();
  const path = `/api/admin/teams/${teamId}/`;
  const teamState = useApi<AdminTeam>(path, { orgSlug });

  if (teamState.loading) return <p className="muted">Loading…</p>;
  if (teamState.error) {
    return <p className="error">Couldn't load team: {teamState.error.message}</p>;
  }
  if (!teamState.data) return null;
  const team = teamState.data;

  return (
    <>
      <IdentityHeader
        team={team}
        orgSlug={orgSlug}
        onSaved={() => teamState.reload()}
        onDeleted={() => navigate(`/o/${orgSlug}/admin/teams`)}
      />

      <section className="section">
        <div className="section-head">
          <h3>Members</h3>
        </div>
        <MembersList
          team={team}
          orgSlug={orgSlug}
          onChanged={() => teamState.reload()}
        />
      </section>
    </>
  );
}

// ---------------------------------------------------------------------------
// Identity — inline-editable name + slug + "Show advanced" disclosure
// ---------------------------------------------------------------------------
function IdentityHeader({
  team, orgSlug, onSaved, onDeleted,
}: {
  team: AdminTeam;
  orgSlug: string;
  onSaved: () => void;
  onDeleted: () => void;
}) {
  const [name, setName] = useState(team.name);
  const [description, setDescription] = useState(team.description);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const dirty = name !== team.name || description !== team.description;

  const save = useMutation(async () => {
    await api(`/api/admin/teams/${team.id}/`, {
      method: "PATCH",
      orgSlug,
      body: { name, description },
    });
    onSaved();
  });

  const del = useMutation(async () => {
    await api(`/api/admin/teams/${team.id}/`, { method: "DELETE", orgSlug });
    onDeleted();
  });

  return (
    <header className="page-header">
      <div style={{ display: "grid", gap: "var(--space-2)", flex: 1, minWidth: 0 }}>
        <input
          type="text"
          value={name}
          onChange={(e) => setName(e.target.value)}
          style={{
            fontSize: "30px",
            fontWeight: 500,
            padding: "2px 4px",
            margin: "-2px -4px",
            border: "1px solid transparent",
            borderRadius: "var(--radius-md)",
            letterSpacing: "-0.015em",
            background: "transparent",
            lineHeight: 1.2,
          }}
        />
        <div className="ticket-meta">
          <code>{team.slug}</code>
          <span className="sep-dot">·</span>
          <span>{team.member_count} member{team.member_count === 1 ? "" : "s"}</span>
        </div>

        <button
          type="button"
          className="disclosure"
          onClick={() => setShowAdvanced((v) => !v)}
          style={{ marginTop: "var(--space-2)" }}
        >
          {showAdvanced ? "▾" : "▸"} {showAdvanced ? "Hide" : "Show"} advanced settings
        </button>
        {showAdvanced && (
          <div className="disclosure-panel">
            <div className="form-field">
              <label>Description</label>
              <textarea
                rows={2}
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="What does this team do? When does it get pulled into approvals?"
              />
            </div>
            <p className="muted small" style={{ margin: 0 }}>
              Slug is fixed after creation — workflow stages reference it. To
              rename, delete and recreate (this orphans existing stage references).
            </p>
          </div>
        )}
      </div>

      <div style={{ display: "flex", gap: "var(--space-2)", alignItems: "flex-start" }}>
        <button
          type="button"
          className="btn-danger"
          disabled={del.loading}
          onClick={() => {
            if (window.confirm(
              `Delete team ${team.slug}? Stages that reference its slug will lose this approver group.`,
            )) {
              del.call(undefined);
            }
          }}
        >
          Delete
        </button>
        {dirty && (
          <button
            type="button"
            className="btn btn-primary"
            disabled={save.loading}
            onClick={() => save.call(undefined)}
          >
            {save.loading ? "Saving…" : "Save"}
          </button>
        )}
      </div>
    </header>
  );
}

// ---------------------------------------------------------------------------
// Members — one-line rows + inline add
// ---------------------------------------------------------------------------
function MembersList({
  team, orgSlug, onChanged,
}: {
  team: AdminTeam;
  orgSlug: string;
  onChanged: () => void;
}) {
  const [adding, setAdding] = useState(false);

  const remove = useMutation(async (membership: AdminTeamMembership) => {
    await api(`/api/admin/teams/${team.id}/members/${membership.id}/`, {
      method: "DELETE",
      orgSlug,
    });
    onChanged();
  });

  return (
    <div className="list">
      {team.memberships.length === 0 && !adding && (
        <p className="muted">No members yet.</p>
      )}

      {team.memberships.map((m) => (
        <div key={m.id} className="list-row">
          <span className="list-row-summary">
            <span className="mono">{m.user_email}</span>
            {m.user_full_name && (
              <>
                <span className="sep-dot">·</span>
                <span>{m.user_full_name}</span>
              </>
            )}
            <span className="sep-dot">·</span>
            <span className="list-row-meta">
              added {new Date(m.created_at).toLocaleDateString()}
            </span>
          </span>
          <button
            type="button"
            className="btn-danger"
            disabled={remove.loading}
            onClick={() => {
              if (window.confirm(`Remove ${m.user_email} from ${team.slug}?`)) {
                remove.call(m);
              }
            }}
          >
            Remove
          </button>
        </div>
      ))}

      {adding ? (
        <AddMemberRow
          team={team}
          orgSlug={orgSlug}
          onClose={() => setAdding(false)}
          onAdded={() => { onChanged(); setAdding(false); }}
        />
      ) : (
        <button type="button" className="list-add" onClick={() => setAdding(true)}>
          + Add member
        </button>
      )}
    </div>
  );
}

function AddMemberRow({
  team, orgSlug, onClose, onAdded,
}: {
  team: AdminTeam;
  orgSlug: string;
  onClose: () => void;
  onAdded: () => void;
}) {
  const [email, setEmail] = useState("");

  const add = useMutation(async () => {
    await api(`/api/admin/teams/${team.id}/members/`, {
      method: "POST",
      orgSlug,
      body: { user_email: email.trim() },
    });
    onAdded();
  });

  return (
    <div className="list-row-expanded">
      <div className="form-field">
        <label>Email of user to add</label>
        <input
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="user@example.com"
          autoFocus
        />
        <small className="help">
          The user must already be a member of this org.
        </small>
      </div>

      <div className="row-actions">
        <button type="button" className="btn-quiet" onClick={onClose}>Cancel</button>
        <button
          type="button"
          className="btn btn-primary"
          disabled={!email.trim() || add.loading}
          onClick={() => add.call(undefined)}
        >
          {add.loading ? "Adding…" : "Add member"}
        </button>
      </div>
      {add.error && (
        <p className="error">
          {add.error.message}
          {"body" in (add.error as object) &&
            ": " + JSON.stringify((add.error as { body: unknown }).body)}
        </p>
      )}
    </div>
  );
}
