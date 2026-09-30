Answer a question about the Lanternfall design tree at `examples/lanternfall/`, and write your answer to the file `answers/s2_impact_tokens.txt` (relative to the repository root). Don't modify any other file.

Here a *reference* is a `{namespace.id}` token reference written in a YAML value: in a subfile's frontmatter, or in a content entity file under `examples/lanternfall/content/`. References in Markdown prose don't count. A reference to a sub-path (such as `{ns.id.field}`) is a reference to `{ns.id}`. A content entity's id is `{entities.<kind>.<id>}`.

Q1. The value of `{distributions.barrowchill_roll}` is about to change. List every token and content entity whose value references `{distributions.barrowchill_roll}`, directly or transitively (through the values of other tokens and content entities). Don't list `{distributions.barrowchill_roll}` itself. Use top-level token ids (for example `{verbs.<id>}`, not `{verbs.<id>.effects}`).

Write the file in this format: each question's header on its own line, then one id per line, and nothing else:

Q1:
{ns.id}
{ns.id}
...
