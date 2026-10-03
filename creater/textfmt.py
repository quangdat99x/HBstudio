"""Tiny markdown-ish to HTML renderer for analysis blocks (no external dependency).

Handles what the chon-noi-dung skill writes: **bold**, *italic*, `code`, bullet lists, numbered items whose
number must stay visible ("1.", "2." separated by other lines), indented continuation lines ("   → reason"),
headings, --- rules and fenced code.
"""
from __future__ import annotations

import html
import re

_RE_LINK = re.compile(r"\[([^\]]+)\]\((https?://[^)\s]+)\)")
_RE_BOLD = re.compile(r"\*\*(.+?)\*\*")
_RE_ITAL = re.compile(r"(?<![*\w])\*(?![*\s])(.+?)(?<![*\s])\*(?![*\w])")
_RE_CODE = re.compile(r"`([^`]+)`")
_RE_BULLET = re.compile(r"^\s*[-•]\s+(.*)$")
_RE_NUM = re.compile(r"^\s*(\d{1,2})\.\s+(.*)$")


def _inline(s: str) -> str:
    s = html.escape(s, quote=False)
    s = _RE_CODE.sub(r"<code>\1</code>", s)
    s = _RE_LINK.sub(r'<a href="\2" target="_blank" rel="noopener">\1</a>', s)
    s = _RE_BOLD.sub(r"<strong>\1</strong>", s)
    s = _RE_ITAL.sub(r"<em>\1</em>", s)
    return s


def _append_to(out: list[str], idx: int, text: str) -> None:
    head, tail = out[idx].rsplit("</", 1)
    out[idx] = f"{head}<br>{_inline(text)}</{tail}"


_RE_TABLE_SEP = re.compile(r"^\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?$")


def _cells(line: str) -> list[str]:
    s = line.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|"):
        s = s[:-1]
    return [c.strip() for c in s.split("|")]


def _render_table(rows: list[str]) -> str:
    """rows: raw table lines; a separator line right after the first row makes that row the header."""
    header = None
    body = []
    for i, r in enumerate(rows):
        if _RE_TABLE_SEP.match(r.strip()):
            if i == 1 and body:
                header = body.pop(0)
            continue
        body.append(_cells(r))
    html_rows = []
    if header:
        html_rows.append("<thead><tr>" + "".join(f"<th>{_inline(c)}</th>" for c in header) + "</tr></thead>")
    html_rows.append("<tbody>" + "".join("<tr>" + "".join(f"<td>{_inline(c)}</td>" for c in row) + "</tr>"
                                         for row in body) + "</tbody>")
    return '<table class="md-table">' + "".join(html_rows) + "</table>"


def md_to_html(text: str) -> str:
    if not text:
        return ""
    out: list[str] = []
    in_list = in_code = False
    last_item: int | None = None          # index in `out` of the last list/numbered item (for continuation lines)
    table: list[str] = []
    for raw in text.replace("\r\n", "\n").split("\n"):
        line = raw.rstrip()
        stripped = line.strip()
        if not in_code and stripped.startswith("|") and stripped.count("|") >= 2:
            if in_list:
                out.append("</ul>")
                in_list = False
            table.append(stripped)
            last_item = None
            continue
        if table:
            out.append(_render_table(table))
            table = []
        if stripped.startswith("```"):
            if in_code:
                out.append("</pre>")
                in_code = False
            else:
                if in_list:
                    out.append("</ul>")
                    in_list = False
                out.append("<pre>")
                in_code = True
            last_item = None
            continue
        if in_code:
            out.append(html.escape(line))
            continue
        if last_item is not None and stripped and raw[:1] in (" ", "\t") and not _RE_NUM.match(line) \
                and not _RE_BULLET.match(line):
            _append_to(out, last_item, stripped)
            continue
        mb = _RE_BULLET.match(line)
        if mb:
            if not in_list:
                out.append("<ul>")
                in_list = True
            out.append(f"<li>{_inline(mb.group(1))}</li>")
            last_item = len(out) - 1
            continue
        if in_list:
            out.append("</ul>")
            in_list = False
        mn = _RE_NUM.match(line)
        if mn:
            out.append(f'<p class="num-item"><span class="num">{mn.group(1)}.</span> {_inline(mn.group(2))}</p>')
            last_item = len(out) - 1
            continue
        last_item = None
        if not stripped:
            continue
        if re.fullmatch(r"-{3,}|\*{3,}", stripped):
            out.append("<hr>")
            continue
        if stripped.startswith(">"):
            out.append(f"<blockquote>{_inline(stripped.lstrip('>').strip())}</blockquote>")
            continue
        hm = re.match(r"^(#{1,4})\s+(.*)$", stripped)
        if hm:
            lvl = min(4, len(hm.group(1)) + 2)
            out.append(f"<h{lvl}>{_inline(hm.group(2))}</h{lvl}>")
            continue
        out.append(f"<p>{_inline(stripped)}</p>")
    if table:
        out.append(_render_table(table))
    if in_list:
        out.append("</ul>")
    if in_code:
        out.append("</pre>")
    return "\n".join(out)
