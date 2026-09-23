"""Tiny markdown-ish to HTML renderer for analysis blocks (no external dependency)."""
from __future__ import annotations

import html
import re

_RE_BOLD = re.compile(r"\*\*(.+?)\*\*")
_RE_ITAL = re.compile(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)")
_RE_CODE = re.compile(r"`([^`]+)`")


def _inline(s: str) -> str:
    s = html.escape(s, quote=False)
    s = _RE_CODE.sub(r"<code>\1</code>", s)
    s = _RE_BOLD.sub(r"<strong>\1</strong>", s)
    s = _RE_ITAL.sub(r"<em>\1</em>", s)
    return s


def md_to_html(text: str) -> str:
    if not text:
        return ""
    out, in_list, in_code = [], False, False
    for raw in text.splitlines():
        line = raw.rstrip()
        if line.strip().startswith("```"):
            if in_code:
                out.append("</pre>"); in_code = False
            else:
                if in_list:
                    out.append("</ul>"); in_list = False
                out.append("<pre>"); in_code = True
            continue
        if in_code:
            out.append(html.escape(line))
            continue
        m = re.match(r"^\s*(?:[-•]|\d+\.)\s+(.*)$", line)
        if m:
            if not in_list:
                out.append("<ul>"); in_list = True
            out.append(f"<li>{_inline(m.group(1))}</li>")
            continue
        if in_list:
            out.append("</ul>"); in_list = False
        if not line.strip():
            out.append("")
            continue
        if line.strip() == "---":
            out.append("<hr>")
            continue
        hm = re.match(r"^(#{1,4})\s+(.*)$", line)
        if hm:
            lvl = min(4, len(hm.group(1)) + 2)
            out.append(f"<h{lvl}>{_inline(hm.group(2))}</h{lvl}>")
            continue
        out.append(f"<p>{_inline(line)}</p>")
    if in_list:
        out.append("</ul>")
    if in_code:
        out.append("</pre>")
    return "\n".join(out)
