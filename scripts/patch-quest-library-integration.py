#!/usr/bin/env python3
"""Apply the small Cyclopedia integration for the self-contained Quest Library."""
from pathlib import Path

path = Path(__file__).resolve().parents[1] / "frontend/src/pages/CreaturesPage.tsx"
text = path.read_text(encoding="utf-8")

old_landing = """          ) : mode === 'quests' ? (\n            <QuestLibraryShelves\n              linkState={cyclopediaRouteState}\n              onNavigate={persistCyclopediaState}\n            />\n          ) : ("""
if old_landing not in text:
    raise SystemExit("Quest landing branch was not found; refusing to patch.")
text = text.replace(old_landing, """          ) : mode === 'quests' ? null : (""", 1)

anchor = """      </div>\n\n      <div>\n        {!loading &&\n        (mode === 'creatures' || mode === 'bosses') ? ("""
replacement = """      </div>\n\n      {mode === 'quests' ? (\n        <QuestLibraryShelves\n          linkState={cyclopediaRouteState}\n          onNavigate={persistCyclopediaState}\n        />\n      ) : null}\n\n      <div>\n        {!loading &&\n        (mode === 'creatures' || mode === 'bosses') ? ("""
if anchor not in text:
    raise SystemExit("Quest library insertion anchor was not found; refusing to patch.")
text = text.replace(anchor, replacement, 1)

legacy_cards = """            {mode === 'quests' &&\n              quests.map((quest, index) => {"""
if legacy_cards not in text:
    raise SystemExit("Legacy quest card block was not found; refusing to patch.")
text = text.replace(legacy_cards, """            {mode === 'quests' && false &&\n              quests.map((quest, index) => {""", 1)

empty_state = """        {isEmpty && !errorMessage && ("""
if empty_state not in text:
    raise SystemExit("Cyclopedia empty-state guard was not found; refusing to patch.")
text = text.replace(empty_state, """        {isEmpty && mode !== 'quests' && !errorMessage && (""", 1)

path.write_text(text, encoding="utf-8")
print(f"Patched {path}")
