"""`gdmd spec` — print docs/spec.md to stdout with frontmatter stripped."""
from __future__ import annotations

import hashlib
import re
from importlib import resources as ir
from pathlib import Path


_FENCE_RE = re.compile(r"^---\s*\n.*?\n---\s*\n", re.DOTALL)


def _read_packaged() -> str | None:
    """Read the spec from packaged data (wheel installs) via importlib.resources.

    Returns None when the package data is unavailable (editable dev install
    without a build step). The dev-tree fallback handles that case.
    """
    try:
        res = ir.files("game_design_md").joinpath("_data/spec.md")
        if res.is_file():
            return res.read_text(encoding="utf-8")
    except (FileNotFoundError, ModuleNotFoundError, OSError):
        pass
    return None


def _read_dev_tree() -> str:
    here = Path(__file__).resolve()
    for candidate in (
        here.parents[2] / "docs" / "spec.md",
        here.parents[3] / "docs" / "spec.md",
    ):
        if candidate.is_file():
            return candidate.read_text(encoding="utf-8")
    raise FileNotFoundError(
        "docs/spec.md not found in package data or near " + str(here.parents[2])
    )


def spec_text() -> str:
    text = _read_packaged() or _read_dev_tree()
    return _FENCE_RE.sub("", text, count=1).lstrip()


# ---- sections and the agent card (WS4, D-024, D-029, spec §9.4) --------------------

_HEADING_RE = re.compile(r"^(#{2,4}) (?:(\d+(?:\.\d+)*)\.?|Appendix ([A-Z])\b)\s*(.*)$")
_FENCE_OPEN_RE = re.compile(r"^ {0,3}(`{3,}|~{3,})")
RFC2119_RE = re.compile(r"\b(?:MUST NOT|MUST|REQUIRED|SHALL NOT|SHALL)\b")
_CODE_SPAN_RE = re.compile(r"`[^`]*`")


def rfc2119_keywords(line: str) -> list[str]:
    """Uppercase RFC-2119 keywords used in `line`. A keyword inside an inline
    code span (`` `MUST` ``) is a mention, not a requirement, and is skipped."""
    return RFC2119_RE.findall(_CODE_SPAN_RE.sub("", line))


class Section:
    """A numbered section (`## 4.`, `### 4.8`, `#### 9.5.5`) or an appendix
    (`## Appendix A`): its id, heading level, title and 1-based line span in
    `spec_text()`. The span runs to the line before the next heading of the
    same or a higher level, so it includes subsections."""

    __slots__ = ("id", "level", "title", "start", "end")

    def __init__(self, id: str, level: int, title: str, start: int, end: int):
        self.id, self.level, self.title, self.start, self.end = id, level, title, start, end


def sections(text: str | None = None) -> list[Section]:
    """Every numbered section and appendix, outside fenced code blocks."""
    lines = (text if text is not None else spec_text()).split("\n")
    heads: list[tuple[int, int, str, str]] = []
    fence: str | None = None
    for i, line in enumerate(lines, 1):
        m = _FENCE_OPEN_RE.match(line)
        if fence is not None:
            if m and m.group(1)[0] == fence[0] and len(m.group(1)) >= len(fence):
                fence = None
            continue
        if m:
            fence = m.group(1)
            continue
        h = _HEADING_RE.match(line)
        if h:
            sid = h.group(2) or h.group(3)
            title = h.group(4).lstrip("—– ").strip()
            heads.append((i, len(h.group(1)), sid, title))
    out = []
    for k, (i, level, sid, title) in enumerate(heads):
        nxt = next((j for j, lv, _, _ in heads[k + 1:] if lv <= level), len(lines) + 1)
        end = nxt - 1
        while end > i and not lines[end - 1].strip():
            end -= 1
        out.append(Section(sid, level, title, i, end))
    return out


def normalize_section_id(arg: str) -> str:
    sid = arg.strip().lstrip("§").strip()
    if sid.lower().startswith("appendix"):
        sid = sid[len("appendix"):].strip()
    return sid.rstrip(".").upper() if sid.isalpha() else sid.rstrip(".")


def section_text(sid: str, text: str | None = None) -> str | None:
    """The verbatim text of one section (with its subsections), or None."""
    text = text if text is not None else spec_text()
    want = normalize_section_id(sid)
    lines = text.split("\n")
    for s in sections(text):
        if s.id == want:
            return "\n".join(lines[s.start - 1:s.end])
    return None


class CardAnchorMissing(ValueError):
    """The spec no longer has a structure the card is generated from."""


def _section_lines(text: str, sid: str) -> list[str]:
    body = section_text(sid, text)
    if body is None:
        raise CardAnchorMissing(f"spec section {sid} not found")
    return body.split("\n")


def _paragraph(lines: list[str], lead: str, *, then_blocks: int = 0, where: str) -> list[str]:
    """The paragraph whose first line starts with `lead`, plus the next
    `then_blocks` paragraphs (a list or a table that belongs to it)."""
    for i, line in enumerate(lines):
        if line.startswith(lead):
            out: list[str] = []
            j, blocks = i, 0
            while j < len(lines):
                if not lines[j].strip():
                    if blocks == then_blocks:
                        break
                    k = j
                    while k < len(lines) and not lines[k].strip():
                        k += 1
                    if k >= len(lines) or lines[k].startswith("#"):
                        break
                    out.extend(lines[j:k])
                    j, blocks = k, blocks + 1
                    continue
                out.append(lines[j])
                j += 1
            return out
    raise CardAnchorMissing(f"§{where}: no paragraph starting {lead!r}")


def _first_block(lines: list[str], kind: str, where: str) -> list[str]:
    """The first table (`|` lines) or fenced code block in `lines`."""
    if kind == "table":
        for i, line in enumerate(lines):
            if line.startswith("|"):
                j = i
                while j < len(lines) and lines[j].startswith("|"):
                    j += 1
                return lines[i:j]
    else:
        for i, line in enumerate(lines):
            if line.startswith("```"):
                j = i + 1
                while j < len(lines) and not lines[j].startswith("```"):
                    j += 1
                return lines[i:j + 1]
    raise CardAnchorMissing(f"§{where}: no {kind}")


def card(text: str | None = None) -> str:
    """The agent card: verbatim excerpts selected by the spec's structure
    (D-024 §1), plus an index of every section with its `--section` pointer.
    Nothing in it is paraphrased; the fixed lines are labels and pointers."""
    text = text if text is not None else spec_text()
    s3 = _section_lines(text, "3")
    s81 = _section_lines(text, "8.1")
    s82 = _section_lines(text, "8.2")
    s99 = _section_lines(text, "9.9")
    ref_intro = next((ln for ln in s3[1:] if ln.strip()), None)
    if ref_intro is None:
        raise CardAnchorMissing("§3: no opening paragraph")
    sha = hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]
    out = [
        "# `game-design.md`: agent card",
        "",
        f"> Generated by `gdmd spec --card` from `docs/spec.md` (sha256 {sha}). "
        "Every block below is a verbatim excerpt of the spec. "
        "The full text of any section: `gdmd spec --section <id>`.",
        "",
        "## Reference syntax (§3)",
        "",
        ref_intro,
        "",
        *_paragraph(s3, "**Namespace ownership.**", then_blocks=1, where="3"),
        "",
        *_paragraph(s3, "**Resolution.**", where="3"),
        "",
        *_paragraph(s3, "**Unresolved references.**", where="3"),
        "",
        *_paragraph(s3, "**Context-local prefixes", then_blocks=1, where="3"),
        "",
        "## Status lifecycle (§8.1)",
        "",
        *_first_block(s81, "table", "8.1"),
        "",
        "## Maintenance ritual (§8.2)",
        "",
        *_paragraph(s82, "4. **The session-end agent ritual.**", where="8.2"),
        "",
        "## Projected views (§9.9)",
        "",
        *_first_block(s99, "code", "9.9"),
        "",
        "## Sections",
        "",
        "`[n MUST]` counts the uppercase RFC-2119 keywords (MUST, MUST NOT, REQUIRED, "
        "SHALL, SHALL NOT) in a section, its subsections included.",
        "",
    ]
    lines = text.split("\n")
    for s in sections(text):
        n = sum(len(rfc2119_keywords(ln)) for ln in lines[s.start - 1:s.end])
        label = f"Appendix {s.id}" if s.id.isalpha() else f"§{s.id}"
        mark = f" [{n} MUST]" if n else ""
        out.append(f"{'  ' * (s.level - 2)}- {label} {s.title}{mark}: "
                   f"`gdmd spec --section {s.id}`")
    return "\n".join(out) + "\n"
