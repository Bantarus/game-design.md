The designers of Ember Ascent (`examples/deckbuilder/`) have decided to raise the per-turn energy budget from 3 to 4. It stays a fixed budget: every turn starts with exactly 4 energy, and it remains a hard target, not a band.

Update the design tree: change the value where it is defined, and propagate the change to every other token that restates the budget. Change nothing that doesn't restate it: other balance targets, card costs (still capped at 3), the card schema and the cards all stay as they are. Follow this repository's workflow for design changes.

Work only inside `examples/deckbuilder/`. When you are done, the tree must lint clean (no errors, no warnings).
