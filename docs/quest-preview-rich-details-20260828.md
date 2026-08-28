# Quest preview, rich references, and completion progress

This change keeps Quest browsing compact while making the Quest detail flow more useful without fabricating local knowledge.

## Interaction changes

- The Quest card surface opens the preview; `Open Quest` remains the explicit bypass action.
- Preview metrics no longer expose a Locations count.
- Optional provider-backed duration appears as a chip before the location chip.
- Missions are exposed as a compact index that deep-links to exact mission anchors.
- Requirements and rewards use local exact item/Quest references with compact item media when cached.
- Full Quest detail keeps a mobile sticky Quest title while the reader scrolls through requirements and missions.
- Shared Design System button classes remain authoritative inside the codex treatment.

## Reference safety

Item and prerequisite Quest links use only exact local matches:

1. an already-resolved canonical relationship, or
2. a single exact normalized-name match from the local PostgreSQL-backed catalog.

Ambiguous or missing records remain unlinked. Public GETs do not call external providers.

## Completion progress

Anonymous users can mark a Quest complete for the current browser session.

Authenticated users with verified characters can persist completion per character. The API verifies that the selected character belongs to the authenticated user and currently has `ownership_status = 'verified'` before reading or changing completion state.

The new `quest_completions` table is introduced by Alembic revision `quest_completion_20260828`, directly after `hunt_zone_registry_20260815`.

## Validation

Run before merge:

```bash
cd /forge/tibiahub

/forge/.venv/bin/python -m pytest \
  backend/tests/test_quest_progress.py \
  backend/tests/test_alembic_single_head.py

npm --prefix frontend run build
npm --prefix frontend run check:layouts
npm --prefix frontend run check:i18n
node frontend/scripts/check-quest-library.mjs
node frontend/scripts/check-quest-product-polish.mjs

git diff --check origin/develop...HEAD
```
