// Onboarding journey — a "Get started" checklist that surfaces on the
// dashboard while the org is still being set up.
//
// State is derived from three API calls that the dashboard already needs:
//   1. /api/admin/ticket-types/      → at least one ticket type configured?
//   2. /api/admin/ticket-types/<id>/rules/  → first ticket type has rules?
//   3. /api/tickets/                 → at least one ticket submitted?
//
// The card auto-hides once every step is done so live users aren't nagged.
// To force-show it on a fully-configured org (e.g. for a demo screenshot or
// to remind onboarding-aware tenants what each step does), append
// ?onboarding=1 to the dashboard URL.

import { Link, useSearchParams } from "react-router-dom";
import { useApi } from "../api/hooks";
import type {
  AdminRule,
  AdminTicketType,
  Paginated,
  Ticket,
} from "../api/types";

type Step = {
  done: boolean;
  title: string;
  description: string;
  ctaLabel: string;
  ctaHref: string;
};

export default function GetStarted({ orgSlug }: { orgSlug: string }) {
  const [params] = useSearchParams();
  const forceShow = params.get("onboarding") === "1";

  const types = useApi<Paginated<AdminTicketType> | AdminTicketType[]>(
    "/api/admin/ticket-types/",
    { orgSlug },
  );
  const tix = useApi<Paginated<Ticket>>("/api/tickets/", { orgSlug });

  const typeList = unwrap(types.data);
  const firstTypeId = typeList?.[0]?.id;
  const rules = useApi<Paginated<AdminRule> | AdminRule[]>(
    firstTypeId ? `/api/admin/ticket-types/${firstTypeId}/rules/` : null,
    { orgSlug },
  );
  const rulesList = unwrap(rules.data);

  // While any of the three API calls is still loading, render nothing rather
  // than flashing a half-empty checklist. The dashboard's tickets table will
  // appear below as usual.
  if (types.loading || tix.loading || rules.loading) return null;

  const hasType = !!typeList && typeList.length > 0;
  const hasRule = !!rulesList && rulesList.length > 0;
  const hasTicket = !!tix.data && tix.data.results.length > 0;

  const steps: Step[] = [
    {
      done: hasType,
      title: "Configure a ticket type",
      description:
        "Define the form fields requesters fill in, the approval workflow, and the system prompt Superstar uses for decisioning.",
      ctaLabel: "Open admin",
      ctaHref: `/o/${orgSlug}/admin/ticket-types`,
    },
    {
      done: hasType && hasRule,
      title: "Add KB rules",
      description:
        "The decisioning loop has nothing to retrieve until at least one rule exists. Each rule cites the decision it produces and the conditions that trigger it.",
      ctaLabel: hasType ? "Add a rule" : "Add a ticket type first",
      ctaHref: firstTypeId
        ? `/o/${orgSlug}/admin/ticket-types/${firstTypeId}/rules`
        : `/o/${orgSlug}/admin/ticket-types`,
    },
    {
      done: hasTicket,
      title: "Submit your first ticket",
      description:
        "Run the loop end-to-end. The decision panel will show the cited rule, the confidence, and the reason — all the things the four guards check.",
      ctaLabel: "New ticket",
      ctaHref: `/o/${orgSlug}/new`,
    },
  ];

  const allDone = steps.every((s) => s.done);
  if (allDone && !forceShow) return null;

  const completed = steps.filter((s) => s.done).length;
  const nextStep = steps.find((s) => !s.done) ?? null;

  return (
    <section className="get-started" aria-label="Get started checklist">
      <header className="get-started-head">
        <div>
          <h2>Get started</h2>
          <p className="muted small" style={{ margin: 0 }}>
            {allDone
              ? "All set — your tenant is ready."
              : `${completed} of ${steps.length} steps complete.`}
          </p>
        </div>
        <div className="get-started-progress" aria-hidden="true">
          <div
            className="get-started-progress-fill"
            style={{ width: `${(completed / steps.length) * 100}%` }}
          />
        </div>
      </header>

      <ol className="get-started-steps">
        {steps.map((s, i) => {
          const isNext = !s.done && s === nextStep;
          return (
            <li
              key={i}
              className={`get-started-step ${s.done ? "is-done" : ""} ${isNext ? "is-next" : ""}`}
            >
              <span className="get-started-check" aria-hidden="true">
                {s.done ? "✓" : i + 1}
              </span>
              <div className="get-started-step-body">
                <div className="get-started-step-title">{s.title}</div>
                <p className="get-started-step-desc">{s.description}</p>
              </div>
              {!s.done && (
                <Link
                  to={s.ctaHref}
                  className={isNext ? "btn btn-primary" : "btn"}
                  style={{ alignSelf: "center", whiteSpace: "nowrap" }}
                >
                  {s.ctaLabel}
                </Link>
              )}
            </li>
          );
        })}
      </ol>
    </section>
  );
}

function unwrap<T>(v: Paginated<T> | T[] | null | undefined): T[] | null {
  if (!v) return null;
  if (Array.isArray(v)) return v;
  return v.results;
}
