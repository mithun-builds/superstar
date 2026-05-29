"""Re-ingest a plugin's KB into pgvector.

Walks `SUPERSTAR_CONFIG_DIR/<plugin>/kb/*.md` (or `SUPERSTAR_CONFIG_DIR/kb/*.md`
for single-plugin configs), parses YAML frontmatter, embeds the body with
BGE-M3, and upserts a `RuleChunk` row per file.

Idempotent: re-running replaces existing rows for the same
(org, plugin_identifier, rule_id) tuple. Removed rule files are NOT
auto-deleted from the DB — use `--prune` to drop chunks that no longer
have a source file.

    python manage.py kb_ingest --org acme --plugin itaccess.access-request
    python manage.py kb_ingest --org acme --plugin homelane.nonstandard --prune
    python manage.py kb_ingest --org acme --plugin itaccess.access-request --dry-run

The `--bypass-rls` flag uses `set_config('app.org_id', ...)` directly so the
command works whether or not RLS is enforced on the connection role.
"""
from __future__ import annotations

import logging
from decimal import Decimal
from pathlib import Path

import frontmatter
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction

from apps.kb.models import RuleChunk
from apps.tenants.models import Org

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Re-ingest a plugin's KB markdown into pgvector."

    def add_arguments(self, parser) -> None:
        parser.add_argument("--org", required=True, help="Org slug")
        parser.add_argument("--plugin", required=True, help="Plugin identifier, e.g. homelane.nonstandard")
        parser.add_argument(
            "--kb-dir",
            default=None,
            help="Override KB dir. Defaults to SUPERSTAR_CONFIG_DIR/<plugin-folder>/kb/",
        )
        parser.add_argument("--prune", action="store_true", help="Delete chunks whose source file is gone")
        parser.add_argument("--dry-run", action="store_true", help="Parse + embed but don't write to DB")

    def handle(self, *args, **opts) -> None:
        org_slug = opts["org"]
        plugin_id = opts["plugin"]
        dry_run = opts["dry_run"]
        prune = opts["prune"]

        try:
            org = Org.objects.get(slug=org_slug)
        except Org.DoesNotExist as exc:
            raise CommandError(f"No org with slug {org_slug!r}") from exc

        kb_dir = _resolve_kb_dir(opts["kb_dir"], plugin_id)
        if not kb_dir.is_dir():
            raise CommandError(f"KB dir not found: {kb_dir}")

        self.stdout.write(self.style.NOTICE(f"Org={org.slug}  Plugin={plugin_id}  KB={kb_dir}"))

        rule_files = sorted(kb_dir.glob("*.md"))
        if not rule_files:
            raise CommandError(f"No *.md files in {kb_dir}")

        # Bind org_id on the connection so RLS doesn't reject our writes.
        with connection.cursor() as cur:
            cur.execute("SELECT set_config('app.org_id', %s, true)", [str(org.id)])

        # Lazy import — embedding model is heavy.
        from apps.decisioning.embedding import embed_batch

        rules = [_parse_rule(p) for p in rule_files]
        rule_ids = [r["rule_id"] for r in rules]
        bodies = [r["body"] for r in rules]

        self.stdout.write(f"Parsed {len(rules)} rules: {rule_ids}")
        self.stdout.write("Embedding...")
        vectors = embed_batch(bodies)

        if dry_run:
            self.stdout.write(self.style.WARNING("--dry-run: skipping writes."))
            return

        with transaction.atomic():
            written = 0
            pruned = 0
            for r, v in zip(rules, vectors):
                _, created = RuleChunk.objects.update_or_create(
                    org=org,
                    plugin_identifier=plugin_id,
                    rule_id=r["rule_id"],
                    defaults={
                        "source_path": r["source_path"],
                        "title": r["title"],
                        "body": r["body"],
                        "category": r.get("category", ""),
                        "subcategory": r.get("subcategory", ""),
                        "decision_hint": r.get("decision_hint", ""),
                        "price_delta": r.get("price_delta", Decimal(0)),
                        "post_actions": r.get("post_actions", []),
                        "extra": r.get("extra", {}),
                        "embedding": v,
                    },
                )
                written += 1
                self.stdout.write(f"  {'+' if created else '~'} {r['rule_id']}")

            if prune:
                fs_ids = set(rule_ids)
                stale = RuleChunk.objects.filter(
                    org=org, plugin_identifier=plugin_id
                ).exclude(rule_id__in=fs_ids)
                pruned = stale.count()
                if pruned:
                    stale.delete()
                self.stdout.write(self.style.WARNING(f"Pruned {pruned} chunks no longer on disk."))

        # Audit.
        from apps.audit.services import log_event

        log_event(
            event_type="kb.ingested",
            org=org,
            data={
                "plugin": plugin_id,
                "kb_dir": str(kb_dir),
                "written": written,
                "pruned": pruned,
                "rule_ids": rule_ids,
            },
        )

        self.stdout.write(self.style.SUCCESS(f"Wrote {written} chunks."))


def _resolve_kb_dir(override: str | None, plugin_id: str) -> Path:
    if override:
        return Path(override).expanduser().resolve()
    base = Path(settings.SUPERSTAR_CONFIG_DIR)
    # Accept either:
    #   base/kb/...               (single-plugin config, e.g. examples/kb-it-access)
    #   base/<plugin-folder>/kb/  (multi-plugin tenant config — folder name matches plugin_id or its suffix)
    if (base / "kb").is_dir():
        return (base / "kb").resolve()
    # Try plugin_id, then last segment after dot.
    candidates = [base / plugin_id / "kb", base / plugin_id.split(".")[-1] / "kb"]
    # Also try every immediate subdir that has a plugins/*.yaml matching this identifier.
    for sub in base.iterdir():
        if sub.is_dir() and (sub / "kb").is_dir():
            candidates.append(sub / "kb")
    for c in candidates:
        if c.is_dir():
            return c.resolve()
    return (base / "kb").resolve()  # fall through, let caller error


def _parse_rule(path: Path) -> dict:
    post = frontmatter.load(path)
    fm = post.metadata or {}
    rule_id = fm.get("rule_id")
    if not rule_id:
        raise CommandError(f"{path.name} has no rule_id frontmatter")

    title = next(
        (ln.lstrip("# ").strip() for ln in post.content.splitlines() if ln.startswith("#")),
        "",
    )
    return {
        "rule_id": str(rule_id),
        "source_path": str(path),
        "title": title,
        "body": post.content.strip(),
        "category": str(fm.get("category", fm.get("main_category", ""))),
        "subcategory": str(fm.get("subcategory", "")),
        "decision_hint": str(fm.get("decision", "")),
        "price_delta": Decimal(str(fm.get("price_delta", 0)))
        if not isinstance(fm.get("price_delta"), dict)
        else Decimal(0),
        "post_actions": list(fm.get("post_actions", [])),
        "extra": {k: v for k, v in fm.items() if k not in {
            "rule_id", "category", "main_category", "subcategory",
            "decision", "price_delta", "post_actions",
        }},
    }
