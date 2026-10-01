Answer two questions about the Lanternfall design tree at `examples/lanternfall/`, and write your answers to the file `answers/s2_lookup_backward.txt` (relative to the repository root). Don't modify any other file.

Here a *reference* is a `{namespace.id}` token reference written in a YAML value: in a subfile's frontmatter, or in a content entity file under `examples/lanternfall/content/`. References in Markdown prose don't count. A reference to a sub-path (such as `{ns.id.field}`) is a reference to `{ns.id}`. A content entity's id is `{entities.<kind>.<id>}`.

Q1. Which content entities (items, skills, monsters and encounters) reach `{distributions.candlegrit_roll}` by following at most 2 references in a row?

Q2. Which content entities reach `{entities.skills.fen_wail}` by following at most 3 references in a row?

Write the file in this format: each question's header on its own line, then one id per line, and nothing else:

Q1:
{entities.<kind>.<id>}
{entities.<kind>.<id>}
...
Q2:
{entities.<kind>.<id>}
{entities.<kind>.<id>}
...
