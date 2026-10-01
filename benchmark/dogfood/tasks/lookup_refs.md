Answer two questions about the Ember Ascent design tree at `examples/deckbuilder/`, and write your answers to the file `answers/lookup.txt` (relative to the repository root). Don't modify any other file.

Q1. Which tokens reference `{resources.energy}`? Count a token if the reference appears anywhere inside its value, including sub-paths such as `{resources.energy.max}` and references embedded inside longer strings. Consider every token defined in the tree's YAML frontmatter and content files; references in Markdown prose don't count. Answer with top-level token ids (for example `{verbs.play_card}`, not `{verbs.play_card.cost}`), and don't list `{resources.energy}` itself.

Q2. Start from `{loops.combat_turn}`. Follow its `sequence` to the verbs it names, then follow each of those verbs' `effects` to the rules they resolve. Which rules do you reach?

Write exactly two lines, in this format:

Q1: {ns.id}, {ns.id}, ...
Q2: {ns.id}, {ns.id}, ...

List each answer's ids sorted alphabetically, separated by a comma and a space.
