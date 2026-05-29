// Renders an HTML form from a plugin's FieldSpec[]. Returns a payload
// dict matching the plugin schema's `name` keys.
//
// Type mapping:
//   string  → <input type="text">
//   int     → <input type="number">
//   bool    → <input type="checkbox">
//   text    → <textarea>
//   enum    → <select> (or radio for ≤4 choices? — keeping simple for now)

import { useState } from "react";
import type { PluginFieldSpec } from "../api/types";

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

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    // Coerce types: int field comes back as a string from <input type="number"> —
    // convert before sending. Empty optional fields are dropped so backend
    // serializer doesn't validate them as required-but-blank.
    const out: Record<string, unknown> = {};
    for (const f of fields) {
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
      {fields.map((f) => (
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
              {f.choices.map((c) => (
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
      ))}
      <button type="submit" className="btn btn-primary" disabled={submitting}>
        {submitting ? "Submitting…" : submitLabel}
      </button>
    </form>
  );
}
