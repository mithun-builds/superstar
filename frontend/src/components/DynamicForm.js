import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
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
export default function DynamicForm({ fields, onSubmit, submitLabel = "Submit", submitting = false }) {
    const [values, setValues] = useState(() => {
        const init = {};
        for (const f of fields) {
            init[f.name] = f.type === "bool" ? false : "";
        }
        return init;
    });
    const set = (name, value) => setValues((prev) => ({ ...prev, [name]: value }));
    const handleSubmit = (e) => {
        e.preventDefault();
        // Coerce types: int field comes back as a string from <input type="number"> —
        // convert before sending. Empty optional fields are dropped so backend
        // serializer doesn't validate them as required-but-blank.
        const out = {};
        for (const f of fields) {
            const v = values[f.name];
            if (v === "" || v === null || v === undefined) {
                if (f.required)
                    out[f.name] = v; // let backend complain about required-missing
                continue;
            }
            if (f.type === "int") {
                const n = typeof v === "number" ? v : Number(v);
                out[f.name] = Number.isFinite(n) ? n : v;
            }
            else {
                out[f.name] = v;
            }
        }
        onSubmit(out);
    };
    return (_jsxs("form", { onSubmit: handleSubmit, className: "dyn-form", children: [fields.map((f) => (_jsxs("div", { className: "form-field", children: [_jsxs("label", { htmlFor: `f-${f.name}`, children: [f.label, f.required && _jsx("span", { className: "required", children: "*" })] }), f.type === "enum" ? (_jsxs("select", { id: `f-${f.name}`, value: String(values[f.name] ?? ""), onChange: (e) => set(f.name, e.target.value), required: f.required, children: [_jsx("option", { value: "", children: "\u2014 select \u2014" }), f.choices.map((c) => (_jsx("option", { value: c, children: c }, c)))] })) : f.type === "text" ? (_jsx("textarea", { id: `f-${f.name}`, value: String(values[f.name] ?? ""), onChange: (e) => set(f.name, e.target.value), required: f.required, rows: 4 })) : f.type === "bool" ? (_jsx("input", { id: `f-${f.name}`, type: "checkbox", checked: Boolean(values[f.name]), onChange: (e) => set(f.name, e.target.checked) })) : f.type === "int" ? (_jsx("input", { id: `f-${f.name}`, type: "number", value: values[f.name] === "" ? "" : String(values[f.name]), onChange: (e) => set(f.name, e.target.value), required: f.required })) : (_jsx("input", { id: `f-${f.name}`, type: "text", value: String(values[f.name] ?? ""), onChange: (e) => set(f.name, e.target.value), required: f.required })), f.help_text && _jsx("small", { className: "help", children: f.help_text })] }, f.name))), _jsx("button", { type: "submit", className: "btn btn-primary", disabled: submitting, children: submitting ? "Submitting…" : submitLabel })] }));
}
