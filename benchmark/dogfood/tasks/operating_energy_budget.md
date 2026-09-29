The designers of Ember Ascent (`examples/deckbuilder/`) have decided to raise the per-turn energy budget from 3 to 4.

Update the design tree: change the value where it is defined, and propagate the change to every other token whose value must change as a consequence. Card costs stay capped at 3: don't change the card schema or any card. Follow this repository's workflow for design changes.

Work only inside `examples/deckbuilder/`. When you are done, the tree must lint clean (no errors, no warnings).
