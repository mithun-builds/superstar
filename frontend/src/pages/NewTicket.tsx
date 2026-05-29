// Create-a-ticket flow:
//   1. Fetch /api/tickets/plugins/ — list of supported ticket types
//   2. User picks a plugin from the list (skip step if only one)
//   3. Render DynamicForm from the picked plugin's fields
//   4. POST /api/tickets/ + navigate to detail page

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

  if (loading) return <p>Loading ticket types…</p>;
  if (error) return <p className="error">Couldn't fetch ticket types: {error.message}</p>;
  if (!plugins || plugins.length === 0) {
    return (
      <p>
        No ticket types are configured. Add a plugin YAML under{" "}
        <code>SUPERSTAR_CONFIG_DIR/plugins/</code> and restart the server.
      </p>
    );
  }

  return (
    <section className="page-new-ticket">
      <h1>New ticket</h1>

      {plugins.length > 1 && (
        <div className="form-field">
          <label htmlFor="picker">Ticket type</label>
          <select
            id="picker"
            value={pickedId ?? ""}
            onChange={(e) => setPickedId(e.target.value || null)}
          >
            <option value="">— pick one —</option>
            {plugins.map((p) => (
              <option key={p.identifier} value={p.identifier}>
                {p.display_name} ({p.identifier})
              </option>
            ))}
          </select>
        </div>
      )}

      {picked && (
        <>
          <div className="form-field">
            <label htmlFor="title">Title</label>
            <input
              id="title"
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder={`${picked.display_name} request`}
            />
            <small className="help">Optional — defaults to "{picked.display_name} request".</small>
          </div>

          <hr />
          <h2>{picked.display_name}</h2>
          {picked.ai_enabled && (
            <p className="muted">
              This ticket type runs AI decisioning
              {picked.shadow_mode ? " (shadow mode — decisions logged, not applied)" : ""}.
            </p>
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
            <pre className="error-block">
              {submit.error instanceof Error ? submit.error.message : String(submit.error)}
              {"body" in (submit.error as object) &&
                "\n" + JSON.stringify((submit.error as { body: unknown }).body, null, 2)}
            </pre>
          )}
        </>
      )}
    </section>
  );
}
