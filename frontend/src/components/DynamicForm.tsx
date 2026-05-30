// Renders an HTML form from a plugin's FieldSpec[]. Returns a payload
// dict matching the plugin schema's `name` keys.
//
// Type mapping:
//   string  → <input type="text">
//   int     → <input type="number">
//   bool    → <input type="checkbox">
//   text    → <textarea>
//   enum    → <select>
//
// Conditional rendering (added in the conditional-fields feature):
//   show_if   — field is hidden when its predicate doesn't match the
//                current values. Hidden values are NOT submitted, so the
//                backend never sees stale state from a since-hidden field.
//   choices_if — for enum fields, the first rule whose conditions match
//                wins; its choices override the static `choices` list.

import { useMemo, useState } from "react";
import type { PluginFieldSpec } from "../api/types";
import { activeChoices, appliesTo } from "../lib/appliesWhen";

interface Props {
  fields: PluginFieldSpec[];
  onSubmit: (payload: Record<string, unknown>) => void | Promise<void>;
  submitLabel?: string;
  submitting?: boolean;
}

export default function DynamicForm({ fields, onSubmit, submitLabel = "Submit", submitting = false }: Props) {
  const [values, setValues] = useState<Record<string, unknown>>(() => {
    const init: Record<string, unknown> = {};
    for (const f of fields) {
      init[f.name] = f.type === "bool" ? false : "";
    }
    return init;
  });

  const set = (name: string, value: unknown) =>
    setValues((prev) => ({ ...prev, [name]: value }));

  // Visibility map — derived from values on every render. Cheap; the
  // alternative (cache + invalidate) is not worth the complexity.
  const visible = useMemo(() => {
    const out: Record<string, boolean> = {};
    for (const f of fields) {
      out[f.name] = !f.show_if || appliesTo(f.show_if, values).applies;
    }
    return out;
  }, [fields, values]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const out: Record<string, unknown> = {};
    for (const f of fields) {
      if (!visible[f.name]) continue; // strip hidden field values
      const v = values[f.name];
      if (v === "" || v === null || v === undefined) {
        if (f.required) out[f.name] = v;  // let backend complain about required-missing
        continue;
      }
      if (f.type === "int") {
        const n = typeof v === "number" ? v : Number(v);
        out[f.name] = Number.isFinite(n) ? n : v;
      } else {
        out[f.name] = v;
      }
    }
    onSubmit(out);
  };

  return (
    <form onSubmit={handleSubmit} className="dyn-form">
      {fields.map((f) => {
        if (!visible[f.name]) return null;
        const enumChoices = f.type === "enum" ? activeChoices(f, values) : [];

        return (
          <div key={f.name} className="form-field">
            <label htmlFor={`f-${f.name}`}>
              {f.label}
              {f.required && <span className="required">*</span>}
            </label>

            {f.type === "enum" ? (
              <select
                id={`f-${f.name}`}
                value={String(values[f.name] ?? "")}
                onChange={(e) => set(f.name, e.target.value)}
                required={f.required}
              >
                <option value="">— select —</option>
                {enumChoices.map((c) => (
                  <option key={c} value={c}>{c}</option>
                ))}
              </select>
            ) : f.type === "text" ? (
              <textarea
                id={`f-${f.name}`}
                value={String(values[f.name] ?? "")}
                onChange={(e) => set(f.name, e.target.value)}
                required={f.required}
                rows={4}
              />
            ) : f.type === "bool" ? (
              <input
                id={`f-${f.name}`}
                type="checkbox"
                checked={Boolean(values[f.name])}
                onChange={(e) => set(f.name, e.target.checked)}
              />
            ) : f.type === "int" ? (
              <input
                id={`f-${f.name}`}
                type="number"
                value={values[f.name] === "" ? "" : String(values[f.name])}
                onChange={(e) => set(f.name, e.target.value)}
                required={f.required}
              />
            ) : (
              <input
                id={`f-${f.name}`}
                type="text"
                value={String(values[f.name] ?? "")}
                onChange={(e) => set(f.name, e.target.value)}
                required={f.required}
              />
            )}

            {f.help_text && <small className="help">{f.help_text}</small>}
          </div>
        );
      })}
      <button type="submit" className="btn btn-primary" disabled={submitting}>
        {submitting ? "Submitting…" : submitLabel}
      </button>
    </form>
  );
}
