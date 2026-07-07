---
name: config-storage-format
description: Config is stored as Markdown, not SQLite — chosen for diff-ability and zero migrations. Reversed an earlier lean toward SQLite.
metadata:
  type: decision
---

# Config storage: Markdown, not SQLite

## compiled_truth

Application config is stored as Markdown files in the repo. This keeps config
diff-able in a PR, human-readable, and free of a migration story — the format
can evolve without a schema step. The parser reads the files at boot; there is
no database dependency for config.

Trade-off accepted: no transactional writes and no query layer over config. This
is fine because config is small, edited by humans, and read-mostly.

## timeline

- 2026-01-12 · hypothesis · leaned toward SQLite for config — atomic writes and a
  query API sounded convenient
- 2026-01-19 · reversal · dropped SQLite: config is small and read-mostly, so the
  migration burden and opaque binary diffs cost more than the query layer is
  worth · source: design discussion
- 2026-01-19 · decision · store config as Markdown, parsed at boot

**Why:** the earlier SQLite lean optimized for a query/write pattern config never
actually has; diff-ability in review and zero migrations matter more here.
**How to apply:** if someone proposes a database for config again, this is the
prior call and the trade-offs weighed — reopen the timeline, do not silently
re-decide.
