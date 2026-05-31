// Vitest setup — runs once per worker before any test file.
// Pulls in jest-dom's custom matchers (toBeInTheDocument, toHaveValue, etc.)
// so they're available globally without per-file imports.
import "@testing-library/jest-dom/vitest";
