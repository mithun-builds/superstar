// Derives the current org slug from the URL (`/o/:slug/...`) so every
// downstream component can read it via useOrg() without prop-drilling.

import { createContext, useContext, type ReactNode } from "react";
import { useParams } from "react-router-dom";

interface OrgContextValue {
  slug: string | null;
}

const OrgContext = createContext<OrgContextValue>({ slug: null });

export function OrgProvider({ children }: { children: ReactNode }) {
  const params = useParams();
  const slug = params.orgSlug ?? null;
  return <OrgContext.Provider value={{ slug }}>{children}</OrgContext.Provider>;
}

export function useOrg(): string | null {
  return useContext(OrgContext).slug;
}

export function useOrgRequired(): string {
  const slug = useOrg();
  if (!slug) {
    throw new Error("useOrgRequired called outside an org-scoped route");
  }
  return slug;
}
