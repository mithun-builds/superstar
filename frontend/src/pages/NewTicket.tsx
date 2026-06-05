// Create-a-ticket flow:
//   1. Fetch /api/tickets/plugins/ — list of supported ticket types
//   2. User picks a plugin from the list (skip step if only one)
//   3. Render DynamicForm from the picked plugin's fields
//   4. POST /api/tickets/ + navigate to detail page
//
// Layout follows the minimal pattern used elsewhere:
//   - One H1, page intent in plain language
//   - Plugin picker only when there's more than one ticket type
//   - Title field is OPTIONAL (defaults to "<display name> request") so
//     it's parked behind a "Set custom title" disclosure — most users
//     accept the default
//   - The AI policy line is a single inline note below the ticket-type
//     name, not a full paragraph
//   - DynamicForm renders the fields; its own submit button sends.

import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import { useApi, useMutation } from "../api/hooks";
import type { PluginSummary, Ticket } from "../api/types";
import DynamicForm from "../components/DynamicForm";
import { useOrgRequired } from "../contexts/OrgContext";

export default function NewTicket() {
  const orgSlug = useOrgRequired();
  const navigate = useNavigate();
  const { data: plugins, loading, error } = useApi<PluginSummary[]>(
    "/api/tickets/plugins/",
    { orgSlug },
  );

  const [pickedId, setPickedId] = useState<string | null>(null);
  const [title, setTitle] = useState<string>("");
  const [editTitle, setEditTitle] = useState<boolean>(false);

  // Auto-pick when there's exactly one plugin.
  const picked = useMemo(() => {
    if (!plugins) return null;
    const id = pickedId ?? (plugins.length === 1 ? plugins[0].identifier : null);
    return plugins.find((p) => p.identifier === id) ?? null;
  }, [plugins, pickedId]);

  const submit = useMutation(
    async ({ payload }: { payload: Record<string, unknown> }) => {
      if (!picked) throw new Error("Pick a ticket type first.");
      const finalTitle = title.trim() || `${picked.display_name} request`;
      const t = await api<Ticket>("/api/tickets/", {
        method: "POST",
        orgSlug,
        body: {
          ticket_type: picked.identifier,
          title: finalTitle,
          payload,
        },
      });
      navigate(`/o/${orgSlug}/tickets/${t.id}`);
      return t;
    },
  );

  if (loading) return <p className="muted">Loading…</p>;
  if (error) return <p className="error">Couldn't fetch ticket types: {error.message}</p>;
  if (!plugins || plugins.length === 0) {
    return (
      <>
        <h1 className="display-heading">New ticket</h1>
        <p className="muted">
          No ticket types are configured yet. Ask an org admin to add one in{" "}
          Admin → Ticket types.
        </p>
      </>
    );
  }

  return (
    <>
      <header className="page-header">
        <h1 className="display-heading">New ticket</h1>
      </header>

      {plugins.length > 1 && (
        <div className="form-field" style={{ marginBottom: "var(--space-8)" }}>
          <label htmlFor="picker">Ticket type</label>
          <select
            id="picker"
            value={pickedId ?? ""}
            onChange={(e) => setPickedId(e.target.value || null)}
          >
            <option value="">Select…</option>
            {plugins.map((p) => (
              <option key={p.identifier} value={p.identifier}>
                {p.display_name}
              </option>
            ))}
          </select>
        </div>
      )}

      {picked && (
        <section className="section" style={{ marginTop: 0 }}>
          <div className="section-head">
            <h3>{picked.display_name}</h3>
            {picked.ai_enabled && (
              <span className="status status-decided" title="Decisioning runs on submit.">
                {picked.shadow_mode ? "AI shadow" : "AI on"}
              </span>
            )}
          </div>

          {/* Title — hidden by default. Surfaced on demand for the few users
              who want to override "<plugin> request". */}
          {!editTitle && (
            <button
              type="button"
              className="disclosure"
              onClick={() => setEditTitle(true)}
              style={{ marginBottom: "var(--space-4)" }}
            >
              ▸ Set a custom title{" "}
              <span className="muted small">
                (defaults to "{picked.display_name} request")
              </span>
            </button>
          )}
          {editTitle && (
            <div className="form-field" style={{ marginBottom: "var(--space-4)" }}>
              <label htmlFor="title">
                Title<span className="optional-mark"> (optional)</span>
              </label>
              <input
                id="title"
                type="text"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder={`${picked.display_name} request`}
                autoFocus
              />
            </div>
          )}

          <DynamicForm
            fields={picked.fields}
            onSubmit={async (payload) => {
              // Drop the return so the type matches DynamicForm's void contract.
              // Errors are surfaced via submit.error below.
              await submit.call({ payload }).catch(() => undefined);
            }}
            submitting={submit.loading}
            submitLabel="Submit ticket"
          />

          {submit.error && (
            <pre className="error-block" style={{ marginTop: "var(--space-4)" }}>
              {submit.error instanceof Error ? submit.error.message : String(submit.error)}
              {"body" in (submit.error as object) &&
                "\n" + JSON.stringify((submit.error as { body: unknown }).body, null, 2)}
            </pre>
          )}
        </section>
      )}
    </>
  );
}
