import { jsx as _jsx } from "react/jsx-runtime";
// Derives the current org slug from the URL (`/o/:slug/...`) so every
// downstream component can read it via useOrg() without prop-drilling.
import { createContext, useContext } from "react";
import { useParams } from "react-router-dom";
const OrgContext = createContext({ slug: null });
export function OrgProvider({ children }) {
    const params = useParams();
    const slug = params.orgSlug ?? null;
    return _jsx(OrgContext.Provider, { value: { slug }, children: children });
}
export function useOrg() {
    return useContext(OrgContext).slug;
}
export function useOrgRequired() {
    const slug = useOrg();
    if (!slug) {
        throw new Error("useOrgRequired called outside an org-scoped route");
    }
    return slug;
}
