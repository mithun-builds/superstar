#!/usr/bin/env python3
"""Standalone end-to-end smoke for Superstar's decisioning loop.

No Django, no Postgres, no plugins — just the four moving parts:

    KB markdown  ──►  BGE-M3 embed  ──►  cosine retrieval  ──►  Ollama (JSON)  ──►  citation verifier

Run after `pip install -r scripts/requirements-smoke.txt` and an Ollama daemon
with the configured model pulled. Exits non-zero if any test case fails its
expected outcome — so this script is also a candidate CI smoke later.

    python scripts/smoke_decisioning.py                          # gemma3:4b default
    OLLAMA_MODEL=qwen2.5:7b-instruct-q4_K_M python scripts/smoke_decisioning.py

Override knobs (env vars):
    OLLAMA_URL       — default http://localhost:11434
    OLLAMA_MODEL     — default gemma3:4b
    EMBEDDING_MODEL  — default BAAI/bge-m3
    KB_DIR           — default examples/kb-it-access/kb (relative to repo root)
    PROMPT_PATH      — default examples/kb-it-access/prompts/decisioning.md
    TOP_K            — default 3
"""
from __future__ import annotations

import json
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import frontmatter
import httpx
import numpy as np
from sentence_transformers import SentenceTransformer

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parent.parent

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "gemma3:4b")
EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL", "BAAI/bge-m3")
KB_DIR = REPO_ROOT / os.environ.get("KB_DIR", "examples/kb-it-access/kb")
PROMPT_PATH = REPO_ROOT / os.environ.get(
    "PROMPT_PATH", "examples/kb-it-access/prompts/decisioning.md"
)
TOP_K = int(os.environ.get("TOP_K", "2"))

# ANSI for legibility
GREEN, RED, YELLOW, BOLD, DIM, RESET = (
    "\033[32m", "\033[31m", "\033[33m", "\033[1m", "\033[2m", "\033[0m"
)


# ---------------------------------------------------------------------------
# KB loading + embedding
# ---------------------------------------------------------------------------
@dataclass
class Rule:
    rule_id: str
    source_path: str
    decision_hint: str
    title: str
    body: str
    frontmatter: dict
    embedding: np.ndarray | None = None


def load_kb(kb_dir: Path) -> list[Rule]:
    rules: list[Rule] = []
    for md in sorted(kb_dir.glob("*.md")):
        post = frontmatter.load(md)
        fm = post.metadata
        rule_id = fm.get("rule_id")
        if not rule_id:
            print(f"{YELLOW}WARN{RESET} {md.name} has no rule_id — skipped")
            continue
        # Use the first non-empty heading line as the title.
        title = next((ln.lstrip("# ").strip() for ln in post.content.splitlines() if ln.startswith("#")), "")
        rules.append(
            Rule(
                rule_id=rule_id,
                source_path=str(md.relative_to(REPO_ROOT)),
                decision_hint=fm.get("decision", ""),
                title=title,
                body=post.content.strip(),
                frontmatter=fm,
            )
        )
    return rules


def embed_rules(model: SentenceTransformer, rules: list[Rule]) -> None:
    texts = [f"{r.title}\n\n{r.body}" for r in rules]
    vectors = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
    for r, v in zip(rules, vectors):
        r.embedding = v


# ---------------------------------------------------------------------------
# Retrieval
# ---------------------------------------------------------------------------
def payload_to_query(payload: dict) -> str:
    return ". ".join(f"{k}: {v}" for k, v in payload.items() if v not in (None, ""))


def retrieve(model: SentenceTransformer, rules: list[Rule], payload: dict, top_k: int) -> list[Rule]:
    query = payload_to_query(payload)
    qv = model.encode(query, normalize_embeddings=True, show_progress_bar=False)
    scored = sorted(rules, key=lambda r: float(np.dot(qv, r.embedding)), reverse=True)
    return scored[:top_k]


# ---------------------------------------------------------------------------
# LLM call (Ollama)
# ---------------------------------------------------------------------------
def call_ollama(system_prompt: str, payload: dict, chunks: list[Rule]) -> tuple[str, float]:
    chunks_block = "\n\n".join(
        f"[{c.rule_id}] (source={c.source_path})\n{c.body}"
        for c in chunks
    )
    user_msg = (
        "REQUEST PAYLOAD:\n"
        f"{json.dumps(payload, indent=2)}\n\n"
        "RETRIEVED RULE CHUNKS:\n"
        f"{chunks_block}\n\n"
        "Respond with a single JSON object matching the schema in the system prompt."
    )
    body = {
        "model": OLLAMA_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_msg},
        ],
        "format": "json",
        "stream": False,
        "options": {"temperature": 0.0},
    }
    t0 = time.monotonic()
    with httpx.Client(timeout=180) as c:
        resp = c.post(f"{OLLAMA_URL}/api/chat", json=body)
        resp.raise_for_status()
        data = resp.json()
    latency = time.monotonic() - t0
    raw = data.get("message", {}).get("content", "")
    return raw, latency


# ---------------------------------------------------------------------------
# Citation verifier (the third guard from services.py)
# ---------------------------------------------------------------------------
def verify_citations(cited_ids: list[str], retrieved: list[Rule]) -> list[str]:
    """Return the list of cited IDs that DON'T appear in retrieved chunks."""
    retrieved_ids = {r.rule_id for r in retrieved}
    return [cid for cid in cited_ids if cid not in retrieved_ids]


# ---------------------------------------------------------------------------
# Test cases — each defines expected behavior
# ---------------------------------------------------------------------------
@dataclass
class TestCase:
    name: str
    payload: dict
    expected_decision: str  # "approve" | "reject" | "escalate"
    expected_cite_one_of: list[str]  # decision passes if it cites any of these
    notes: str = ""


CASES: list[TestCase] = [
    TestCase(
        name="VPN for engineer",
        payload={
            "requester_role": "engineer",
            "access_type": "vpn",
            "justification": "Need VPN to access dev environments from home.",
            "duration_days": 180,
        },
        expected_decision="approve",
        expected_cite_one_of=["ITA-VPN-001"],
    ),
    TestCase(
        name="Production DB read",
        payload={
            "requester_role": "engineer",
            "access_type": "prod_db_read",
            "justification": "Debug a customer-reported issue in production.",
            "duration_days": 7,
        },
        expected_decision="escalate",
        expected_cite_one_of=["ITA-PROD-001"],
    ),
    TestCase(
        name="Local admin for engineer, 60 days",
        payload={
            "requester_role": "engineer",
            "access_type": "local_admin",
            "justification": "Need to install custom debuggers for kernel work.",
            "duration_days": 60,
        },
        expected_decision="approve",
        expected_cite_one_of=["ITA-ADMIN-001"],
    ),
    TestCase(
        name="Local admin for finance (no matching rule)",
        payload={
            "requester_role": "finance",
            "access_type": "local_admin",
            "justification": "Spreadsheet plugin needs install permissions.",
            "duration_days": 30,
        },
        expected_decision="escalate",
        expected_cite_one_of=[],  # may cite ITA-ADMIN-001 escalation path or nothing
        notes="Tests whether model escalates when no clear approve-rule covers the requester role.",
    ),
]


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------
def main() -> int:
    print(f"{BOLD}Superstar decisioning smoke{RESET}")
    print(f"  model          : {OLLAMA_MODEL}")
    print(f"  embedding model: {EMBEDDING_MODEL}")
    print(f"  KB dir         : {KB_DIR.relative_to(REPO_ROOT)}")
    print(f"  top_k          : {TOP_K}")
    print()

    if not KB_DIR.is_dir():
        print(f"{RED}KB dir not found: {KB_DIR}{RESET}")
        return 2
    if not PROMPT_PATH.is_file():
        print(f"{RED}Prompt file not found: {PROMPT_PATH}{RESET}")
        return 2

    # Load KB
    print(f"{DIM}Loading KB...{RESET}")
    rules = load_kb(KB_DIR)
    print(f"  Loaded {len(rules)} rules: {[r.rule_id for r in rules]}")

    # Embed
    print(f"{DIM}Loading embedding model {EMBEDDING_MODEL} (first run downloads ~2GB)...{RESET}")
    embedder = SentenceTransformer(EMBEDDING_MODEL)
    print(f"{DIM}Embedding rules...{RESET}")
    embed_rules(embedder, rules)

    # Load prompt
    system_prompt = PROMPT_PATH.read_text()

    # Run cases
    print(f"\n{BOLD}Running {len(CASES)} test cases against {OLLAMA_MODEL}{RESET}\n")
    passed = 0
    for i, case in enumerate(CASES, 1):
        print(f"{BOLD}[{i}/{len(CASES)}] {case.name}{RESET}")
        if case.notes:
            print(f"  {DIM}{case.notes}{RESET}")
        chunks = retrieve(embedder, rules, case.payload, TOP_K)
        print(f"  retrieved: {[c.rule_id for c in chunks]}")

        try:
            raw, latency = call_ollama(system_prompt, case.payload, chunks)
        except httpx.HTTPError as exc:
            print(f"  {RED}Ollama call failed: {exc}{RESET}")
            continue

        try:
            obj = json.loads(raw)
        except json.JSONDecodeError:
            print(f"  {RED}Non-JSON output:{RESET} {raw[:200]}")
            continue

        decision = obj.get("decision")
        cited = obj.get("cited_rule_ids", []) or []
        confidence = obj.get("confidence", 0.0)
        reason = obj.get("reason_text", "")

        hallucinated = verify_citations(cited, chunks)

        # Render result
        decision_color = GREEN if decision == case.expected_decision else RED
        print(f"  decision  : {decision_color}{decision}{RESET}  (expected {case.expected_decision})")
        print(f"  cited     : {cited}")
        print(f"  confidence: {confidence}")
        print(f"  reason    : {reason}")
        print(f"  latency   : {latency:.1f}s")

        if hallucinated:
            print(f"  {RED}HALLUCINATED rule_ids: {hallucinated}{RESET}")

        # Pass/fail
        decision_match = decision == case.expected_decision
        if case.expected_cite_one_of:
            cite_match = any(c in cited for c in case.expected_cite_one_of)
        else:
            cite_match = True  # case explicitly doesn't require a specific citation
        no_hallucination = not hallucinated

        ok = decision_match and cite_match and no_hallucination
        verdict = f"{GREEN}PASS{RESET}" if ok else f"{RED}FAIL{RESET}"
        if not decision_match:
            verdict += f" {DIM}(decision mismatch){RESET}"
        if not cite_match:
            verdict += f" {DIM}(expected cite of: {case.expected_cite_one_of}){RESET}"
        if hallucinated:
            verdict += f" {DIM}(hallucinated cite){RESET}"
        print(f"  {verdict}\n")
        if ok:
            passed += 1

    # Summary
    print(f"{BOLD}Summary{RESET}: {passed}/{len(CASES)} passed")
    return 0 if passed == len(CASES) else 1


if __name__ == "__main__":
    sys.exit(main())
