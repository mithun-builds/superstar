// Admin → Team edit page.
// Two sections: identity (name + description) and members (list + add + remove).
// Slug isn't editable post-create — stages reference it.

import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
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

  if (teamState.loading) return <p>Loading…</p>;
  if (teamState.error) {
    return <p className="error">Couldn't load team: {teamState.error.message}</p>;
  }
  if (!teamState.data) return null;
  const team = teamState.data;

  return (
    <section className="page-admin-edit">
      <header className="page-header">
        <div>
          <h1>{team.name}</h1>
          <p className="muted">
            <code>{team.slug}</code> · {team.member_count} member{team.member_count === 1 ? "" : "s"}
            {" · "}
            <Link to={`/o/${orgSlug}/admin/teams`}>← Back to teams</Link>
          </p>
        </div>
        <DeleteButton
          teamPath={path}
          teamLabel={team.slug}
          orgSlug={orgSlug}
          onDeleted={() => navigate(`/o/${orgSlug}/admin/teams`)}
        />
      </header>

      <IdentitySection team={team} orgSlug={orgSlug} onSaved={() => teamState.reload()} />
      <MembersSection
        team={team}
        orgSlug={orgSlug}
        onChanged={() => teamState.reload()}
      />
    </section>
  );
}

function IdentitySection({
  team,
  orgSlug,
  onSaved,
}: {
  team: AdminTeam;
  orgSlug: string;
  onSaved: () => void;
}) {
  const [name, setName] = useState(team.name);
  const [description, setDescription] = useState(team.description);

  const save = useMutation(async () => {
    await api(`/api/admin/teams/${team.id}/`, {
      method: "PATCH",
      orgSlug,
      body: { name, description },
    });
    onSaved();
  });

  return (
    <section className="card">
      <h3>Identity</h3>
      <p className="muted">
        Slug is fixed after creation — workflow stages reference it. To
        rename a team, delete and recreate (orphans existing stage references).
      </p>
      <div className="form-field">
        <label>Display name</label>
        <input type="text" value={name} onChange={(e) => setName(e.target.value)} />
      </div>
      <div className="form-field">
        <label>Description</label>
        <textarea
          rows={2}
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder="What does this team do? When does it get pulled into approvals?"
        />
      </div>
      <div className="btn-row">
        <button
          type="button"
          className="btn btn-primary"
          disabled={save.loading || (!name.trim() && !description.trim())}
          onClick={() => save.call(undefined)}
        >
          {save.loading ? "Saving…" : "Save"}
        </button>
        {save.error && <span className="error">{save.error.message}</span>}
      </div>
    </section>
  );
}

function MembersSection({
  team,
  orgSlug,
  onChanged,
}: {
  team: AdminTeam;
  orgSlug: string;
  onChanged: () => void;
}) {
  const [addEmail, setAddEmail] = useState("");

  const add = useMutation(async (email: string) => {
    await api(`/api/admin/teams/${team.id}/members/`, {
      method: "POST",
      orgSlug,
      body: { user_email: email.trim() },
    });
    setAddEmail("");
    onChanged();
  });

  const remove = useMutation(async (membership: AdminTeamMembership) => {
    await api(`/api/admin/teams/${team.id}/members/${membership.id}/`, {
      method: "DELETE",
      orgSlug,
    });
    onChanged();
  });

  return (
    <section className="card">
      <h3>Members</h3>
      <p className="muted">
        Users in this team can decide workflow stages whose <code>approvers</code>{" "}
        list includes <code>{team.slug}</code>. Members must already be in this org.
      </p>

      <div className="row-edit row-new">
        <div className="row-inputs">
          <input
            type="email"
            value={addEmail}
            onChange={(e) => setAddEmail(e.target.value)}
            placeholder="user@example.com"
            style={{ flex: 1 }}
          />
          <button
            type="button"
            className="btn btn-primary"
            disabled={!addEmail.trim() || add.loading}
            onClick={() => add.call(addEmail)}
          >
            {add.loading ? "Adding…" : "+ Add member"}
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

      {team.memberships.length === 0 ? (
        <p className="muted">No members yet.</p>
      ) : (
        <table className="ticket-table">
          <thead>
            <tr>
              <th>Email</th>
              <th>Name</th>
              <th>Added</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {team.memberships.map((m) => (
              <tr key={m.id}>
                <td><code>{m.user_email}</code></td>
                <td>{m.user_full_name || <span className="muted">—</span>}</td>
                <td>{new Date(m.created_at).toLocaleDateString()}</td>
                <td>
                  <button
                    type="button"
                    className="btn btn-reject"
                    disabled={remove.loading}
                    onClick={() => {
                      if (window.confirm(`Remove ${m.user_email} from ${team.slug}?`)) {
                        remove.call(m);
                      }
                    }}
                  >
                    Remove
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}

function DeleteButton({
  teamPath,
  teamLabel,
  orgSlug,
  onDeleted,
}: {
  teamPath: string;
  teamLabel: string;
  orgSlug: string;
  onDeleted: () => void;
}) {
  const del = useMutation(async () => {
    await api(teamPath, { method: "DELETE", orgSlug });
    onDeleted();
  });
  return (
    <button
      type="button"
      className="btn btn-reject"
      disabled={del.loading}
      onClick={() => {
        if (
          window.confirm(
            `Delete team ${teamLabel}? Stages that reference its slug will lose this approver group.`,
          )
        ) {
          del.call(undefined);
        }
      }}
    >
      Delete team
    </button>
  );
}
