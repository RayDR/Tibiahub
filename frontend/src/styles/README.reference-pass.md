# Cyclopedia Creature reference pass

This pass treats the approved Cyclopedia > Creatures mockup as the strict visual reference while preserving authoritative TibiaHub data.

- Theme and density remain independent of the new `compact | wide` content-width preference.
- Public navigation presentation is persisted through `system_settings` and controlled from Admin Settings.
- Domain/navigation imagery uses TibiaHub SVGs; generic controls may continue using Lucide.
- Specific entity media always wins. SVG artwork is fallback-only.
- Creature cards are enriched in batches; the selected Creature alone loads the complete preview read model.
- The side preview exposes only persisted/derived database facts. It does not invent recommended levels, vocations, locations, loot or hunting advice.
