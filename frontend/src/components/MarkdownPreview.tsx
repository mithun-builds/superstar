// Read-only rendered preview of a markdown string. Sanitized via DOMPurify
// because admins write this content themselves but bad copy-paste from a
// styled doc can smuggle in <script> / event handlers — better to scrub.

import DOMPurify from "dompurify";
import { marked } from "marked";
import { useMemo } from "react";

export default function MarkdownPreview({ source }: { source: string }) {
  const html = useMemo(() => {
    // marked.parse may return Promise<string> when async config is on; we
    // configure it sync. Casting via String() guards against future API drift.
    const raw = String(marked.parse(source ?? "", { async: false }));
    return DOMPurify.sanitize(raw);
  }, [source]);

  if (!source?.trim()) {
    return <p className="muted">(empty — type something on the left to preview it)</p>;
  }
  // Disabling react's noDangerouslySetInnerHTML lint for this single use —
  // the sanitizer above is the contract.
  // eslint-disable-next-line react/no-danger
  return <div className="md-preview" dangerouslySetInnerHTML={{ __html: html }} />;
}
