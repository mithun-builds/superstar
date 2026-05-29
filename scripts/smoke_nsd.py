#!/usr/bin/env python3
"""RAG smoke against the HomeLane NSD.AI rulebook (18 normalized rules).

Reads the KB and prompt from the HL config repo at
`../superstar-config-homelane/nsd-ai/`. Override with KB_DIR / PROMPT_PATH
env vars if your layout differs.

    python scripts/smoke_nsd.py                     # gemma3:4b default
    OLLAMA_MODEL=qwen2.5:7b-instruct-q4_K_M python scripts/smoke_nsd.py

Exits non-zero if any case fails its expected (decision, citation, no-hallucination).
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

REPO_ROOT = Path(__file__).resolve().parent.parent
# Make `superstar` importable without installing the package.
sys.path.insert(0, str(REPO_ROOT))
from superstar.applies_when import applies_to  # noqa: E402
HL_CONFIG = REPO_ROOT.parent / "superstar-config-homelane" / "nsd-ai"

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "gemma3:4b")
EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL", "BAAI/bge-m3")
KB_DIR = Path(os.environ.get("KB_DIR", HL_CONFIG / "kb"))
PROMPT_PATH = Path(os.environ.get("PROMPT_PATH", HL_CONFIG / "prompts" / "decisioning.md"))
TOP_K = int(os.environ.get("TOP_K", "3"))

GREEN, RED, YELLOW, BOLD, DIM, RESET = (
    "\033[32m", "\033[31m", "\033[33m", "\033[1m", "\033[2m", "\033[0m"
)


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
            continue
        title = next(
            (ln.lstrip("# ").strip() for ln in post.content.splitlines() if ln.startswith("#")),
            "",
        )
        rules.append(Rule(
            rule_id=rule_id,
            source_path=md.name,
            decision_hint=fm.get("decision", ""),
            title=title,
            body=post.content.strip(),
            frontmatter=fm,
        ))
    return rules


def embed_rules(model: SentenceTransformer, rules: list[Rule]) -> None:
    vectors = model.encode(
        [f"{r.title}\n\n{r.body}" for r in rules],
        normalize_embeddings=True,
        show_progress_bar=False,
    )
    for r, v in zip(rules, vectors):
        r.embedding = v


def retrieve(model: SentenceTransformer, rules: list[Rule], payload: dict, top_k: int) -> list[Rule]:
    q = ". ".join(f"{k}: {v}" for k, v in payload.items() if v not in (None, ""))
    qv = model.encode(q, normalize_embeddings=True, show_progress_bar=False)
    return sorted(rules, key=lambda r: float(np.dot(qv, r.embedding)), reverse=True)[:top_k]


def call_ollama(system_prompt: str, payload: dict, chunks: list[Rule]) -> tuple[str, float]:
    chunks_block = "\n\n".join(f"[{c.rule_id}] (source={c.source_path})\n{c.body}" for c in chunks)
    user_msg = (
        f"REQUEST PAYLOAD:\n{json.dumps(payload, indent=2)}\n\n"
        f"RETRIEVED RULE CHUNKS:\n{chunks_block}\n\n"
        "Respond with the JSON object only."
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
    return data.get("message", {}).get("content", ""), time.monotonic() - t0


@dataclass
class Case:
    name: str
    payload: dict
    expected_decision: str
    expected_cite_one_of: list[str]
    notes: str = ""


_BASE = {
    "customer_id": "C-1001",
    "designer_email": "dee.designer@homelane.test",
    "room_type": "kitchen",
    "sub_category": "base_unit",
    "module_name": "WB-2S-450",
}

CASES: list[Case] = [
    Case(
        name="Lock on 1-shutter — escalate per NSD-LOCK-001",
        payload={**_BASE, "request_type": "additional_lock", "type_of_shutter": "1-shutter", "shutter_finish": "Laminate"},
        expected_decision="escalate",
        expected_cite_one_of=["NSD-LOCK-001"],
    ),
    Case(
        name="Lock on 2-shutter PU finish — reject per NSD-LOCK-003",
        payload={**_BASE, "request_type": "additional_lock", "type_of_shutter": "2-shutter", "shutter_finish": "PU"},
        expected_decision="reject",
        expected_cite_one_of=["NSD-LOCK-003"],
    ),
    Case(
        name="Lock on 2-shutter Laminate — approve per NSD-LOCK-004",
        payload={**_BASE, "request_type": "additional_lock", "type_of_shutter": "2-shutter", "shutter_finish": "Laminate"},
        expected_decision="approve",
        expected_cite_one_of=["NSD-LOCK-004"],
    ),
    Case(
        name="Air vent on 250x250mm module — reject per NSD-AIRVENT-001",
        payload={**_BASE, "request_type": "air_vent", "type_of_shutter": "2-shutter", "module_width_mm": 250, "module_height_mm": 250, "shutter_finish": "Laminate"},
        expected_decision="reject",
        expected_cite_one_of=["NSD-AIRVENT-001"],
    ),
    Case(
        name="Air vent on 500x600mm 2-shutter Laminate — approve per NSD-AIRVENT-004",
        payload={**_BASE, "request_type": "air_vent", "type_of_shutter": "2-shutter", "module_width_mm": 500, "module_height_mm": 600, "shutter_finish": "Laminate"},
        expected_decision="approve",
        expected_cite_one_of=["NSD-AIRVENT-004"],
    ),
    Case(
        name="Push-to-open on drawer+shutter combo — escalate per NSD-PUSHOPEN-002",
        payload={**_BASE, "request_type": "push_to_open", "type_of_shutter": "drawer_and_shutter_combination"},
        expected_decision="escalate",
        expected_cite_one_of=["NSD-PUSHOPEN-002"],
    ),
    Case(
        name="Prelam 25mm thickness change — reject per NSD-PRELAM-001",
        payload={**_BASE, "request_type": "prelam_thickness_change", "shelf_or_countertop_thickness_mm": 25},
        expected_decision="reject",
        expected_cite_one_of=["NSD-PRELAM-001"],
    ),
]


def verify_citations(cited: list[str], retrieved: list[Rule]) -> list[str]:
    return [c for c in cited if c not in {r.rule_id for r in retrieved}]


def main() -> int:
    print(f"{BOLD}SuperStar RAG smoke — NSD.AI{RESET}")
    print(f"  model     : {OLLAMA_MODEL}")
    print(f"  embedding : {EMBEDDING_MODEL}")
    print(f"  KB dir    : {KB_DIR}")
    print(f"  top_k     : {TOP_K}")
    print()

    if not KB_DIR.is_dir():
        print(f"{RED}KB dir not found: {KB_DIR}{RESET}")
        return 2
    if not PROMPT_PATH.is_file():
        print(f"{RED}Prompt file not found: {PROMPT_PATH}{RESET}")
        return 2

    rules = load_kb(KB_DIR)
    print(f"Loaded {len(rules)} rules.")

    embedder = SentenceTransformer(EMBEDDING_MODEL)
    embed_rules(embedder, rules)

    system_prompt = PROMPT_PATH.read_text()
    print(f"\n{BOLD}Running {len(CASES)} test cases against {OLLAMA_MODEL}{RESET}\n")

    passed = 0
    for i, case in enumerate(CASES, 1):
        print(f"{BOLD}[{i}/{len(CASES)}] {case.name}{RESET}")
        if case.notes:
            print(f"  {DIM}{case.notes}{RESET}")
        chunks = retrieve(embedder, rules, case.payload, TOP_K)
        print(f"  retrieved : {[c.rule_id for c in chunks]}")

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

        decision_color = GREEN if decision == case.expected_decision else RED
        print(f"  decision  : {decision_color}{decision}{RESET}  (expected {case.expected_decision})")
        print(f"  cited     : {cited}")
        print(f"  confidence: {confidence}")
        print(f"  reason    : {reason}")
        print(f"  latency   : {latency:.1f}s")
        if hallucinated:
            print(f"  {RED}HALLUCINATED rule_ids: {hallucinated}{RESET}")

        # Guard: applies_when check. If any cited rule's conditions don't
        # match the payload, force-escalate (mirrors the Django service guard).
        chunks_by_id = {c.rule_id: c for c in chunks}
        applicability_failures: list[str] = []
        for cite_id in cited:
            rule = chunks_by_id.get(cite_id)
            if rule is None:
                continue  # already counted as hallucination
            conditions = rule.frontmatter.get("applies_when")
            ok_apply, reasons_failed = applies_to(conditions, case.payload)
            if not ok_apply:
                applicability_failures.append(f"{cite_id}: {'; '.join(reasons_failed)}")

        effective_decision = decision
        if applicability_failures:
            print(f"  {YELLOW}applies_when failed:{RESET} {applicability_failures}")
            print(f"  {YELLOW}→ verifier forces escalate{RESET}")
            effective_decision = "escalate"

        decision_match = effective_decision == case.expected_decision
        cite_match = (
            any(c in cited for c in case.expected_cite_one_of)
            if case.expected_cite_one_of
            else True
        )
        no_hallucination = not hallucinated
        # When the verifier forces escalation, citation-match doesn't apply —
        # we're correctly bailing, regardless of which rule the model named.
        if applicability_failures and case.expected_decision == "escalate":
            cite_match = True
        ok = decision_match and cite_match and no_hallucination

        verdict = f"{GREEN}PASS{RESET}" if ok else f"{RED}FAIL{RESET}"
        if applicability_failures and ok:
            verdict += f" {DIM}(via verifier){RESET}"
        if not decision_match:
            verdict += f" {DIM}(decision mismatch){RESET}"
        if not cite_match:
            verdict += f" {DIM}(want cite of: {case.expected_cite_one_of}){RESET}"
        if hallucinated:
            verdict += f" {DIM}(hallucinated cite){RESET}"
        print(f"  {verdict}\n")
        if ok:
            passed += 1

    print(f"{BOLD}Summary{RESET}: {passed}/{len(CASES)} passed")
    return 0 if passed == len(CASES) else 1


if __name__ == "__main__":
    sys.exit(main())
