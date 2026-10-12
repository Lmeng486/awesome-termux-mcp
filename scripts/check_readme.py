#!/usr/bin/env python3
"""Validate the awesome-termux-mcp README.

Two guarantees, both cheap and offline:

1. The "Directory of Termux/Android MCP Servers" table stays well-formed:
   every data row has exactly 4 columns and its badge is one of the badges
   the README itself defines.
2. Every relative link in the README points at a file that actually exists,
   so `./nano` style links never rot.

Run locally:  python3 scripts/check_readme.py
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
README = os.path.join(ROOT, "README.md")

LINK_RE = re.compile(r"\[[^\]]+\]\(([^)]+)\)")


def norm(s):
    """Strip emoji variation selectors so badge comparison is stable."""
    return s.replace("\ufe0f", "").strip()


ALLOWED_BADGES = {norm(x) for x in ("✅", "⚠️", "🚫", "⚠️→✅*")}


def main():
    with open(README, encoding="utf-8") as f:
        text = f.read()
    errors = []

    # --- 1. Directory table shape -------------------------------------
    head, sep, rest = text.partition("## Directory of Termux/Android MCP Servers")
    if not sep:
        errors.append("missing '## Directory of Termux/Android MCP Servers' section")
        body_rows = []
    else:
        table = rest.split("\n## ", 1)[0]
        rows = [l for l in table.splitlines() if l.strip().startswith("|")]
        body_rows = [l for l in rows if not set(l) <= set("|-: ")]
        body_rows = body_rows[1:] if body_rows else []  # drop header row
        for row in body_rows:
            cells = [c.strip() for c in row.strip().strip("|").split("|")]
            if len(cells) != 4:
                errors.append("row is not 4 columns: " + row[:60])
                continue
            if norm(cells[2]) not in ALLOWED_BADGES:
                errors.append("unexpected badge %r in: %s" % (cells[2], cells[0]))

    # --- 2. Relative links must resolve --------------------------------
    for target in LINK_RE.findall(text):
        if target.startswith(("http://", "https://", "mailto:", "#")):
            continue
        path = target.split("#", 1)[0]
        if not path:
            continue
        if not os.path.exists(os.path.join(ROOT, path)):
            errors.append("broken relative link: " + target)

    if errors:
        print("README check FAILED:")
        for e in errors:
            print("  - " + e)
        return 1
    print("README check OK (%d directory rows)" % len(body_rows))
    return 0


if __name__ == "__main__":
    sys.exit(main())