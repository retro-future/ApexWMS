"""Reading a rendered PDF back, so a print test can assert what is on it.

Asserting that a download starts with ``%PDF`` proves the route is wired
and nothing else. FR-8.2 is a claim about the *page* — the customer's proof
of which handset they bought — so the test has to be able to see the IMEI.

fpdf2 compresses its content streams, so the drawn text is not in the file
as plain bytes; this inflates every stream it can. With the core font the
text lands in the stream as Latin-1. With a Unicode TTF (the deployment
default now, for Cyrillic) fpdf2 subsets the font and writes text as
two-byte glyph ids, plus a ``/ToUnicode`` CMap that maps them back — so
this parses that CMap and decodes the ``Tj``/``TJ`` operators through it.
Deliberately not a full PDF parser.
"""

import contextlib
import re
import zlib

# A 24x12 PNG, for the letterhead logo an upload test has to send.
PNG_BASE64 = (
    "iVBORw0KGgoAAAANSUhEUgAAABgAAAAMCAIAAAD3UuoiAAAAH0lEQVR4nGMUidrCQA3A"
    "RBVTGEYNIgaMBjZhMPjCCAAKLAE6Pmc9OAAAAABJRU5ErkJggg=="
)

_STREAM = re.compile(rb"stream\r?\n(.*?)endstream", re.S)
_ESCAPED = re.compile(r"\\([()\\])")
_BFCHAR = re.compile(r"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>")
_BFRANGE = re.compile(r"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>")
_SHOW = re.compile(r"\(((?:[^()\\]|\\.)*)\)\s*T[jJ]", re.S)
_PDF_ESCAPES = {"n": "\n", "r": "\r", "t": "\t", "b": "\b", "f": "\f"}


def _unescape(s: str) -> bytes:
    out = bytearray()
    i = 0
    while i < len(s):
        ch = s[i]
        if ch != "\\":
            out.append(ord(ch) & 0xFF)
            i += 1
            continue
        nxt = s[i + 1] if i + 1 < len(s) else ""
        if nxt in _PDF_ESCAPES:
            out.append(ord(_PDF_ESCAPES[nxt]))
            i += 2
        elif nxt in "0123456789":
            digits = s[i + 1 : i + 4]
            octal = "".join(d for d in digits if d in "01234567")[:3]
            out.append(int(octal, 8) & 0xFF)
            i += 1 + len(octal)
        else:
            out.append(ord(nxt) & 0xFF)
            i += 2
    return bytes(out)


def _cmap(streams: list[str]) -> dict[int, str] | None:
    table: dict[int, str] = {}
    found = False
    for text in streams:
        for block in re.findall(r"beginbfchar(.*?)endbfchar", text, re.S):
            found = True
            for src, dst in _BFCHAR.findall(block):
                table[int(src, 16)] = chr(int(dst, 16))
        for block in re.findall(r"beginbfrange(.*?)endbfrange", text, re.S):
            found = True
            for lo, hi, start in _BFRANGE.findall(block):
                for i in range(int(lo, 16), int(hi, 16) + 1):
                    table[i] = chr(int(start, 16) + (i - int(lo, 16)))
    return table if found else None


def _decode_with_cmap(streams: list[str], table: dict[int, str]) -> str:
    out: list[str] = []
    for text in streams:
        for shown in _SHOW.findall(text):
            raw = _unescape(shown)
            for i in range(0, len(raw) - 1, 2):
                code = (raw[i] << 8) | raw[i + 1]
                out.append(table.get(code, ""))
    return "".join(out)


def pdf_text(content: bytes) -> str:
    streams: list[str] = []
    for match in _STREAM.finditer(content):
        raw = match.group(1)
        with contextlib.suppress(zlib.error):
            raw = zlib.decompress(raw)
        streams.append(raw.decode("latin-1"))
    table = _cmap(streams)
    if table is not None:
        return _decode_with_cmap(streams, table)
    return _ESCAPED.sub(r"\1", "".join(streams))
