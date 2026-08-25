"""Reading a rendered PDF back, so a print test can assert what is on it.

Asserting that a download starts with ``%PDF`` proves the route is wired
and nothing else. FR-8.2 is a claim about the *page* — the customer's proof
of which handset they bought — so the test has to be able to see the IMEI.

fpdf2 compresses its content streams, so the drawn text is not in the file
as plain bytes; this inflates every stream it can and joins the results.
Enough to search for a number or a name, and deliberately not a PDF parser.
"""

import re
import zlib

# A 24x12 PNG, for the letterhead logo an upload test has to send.
PNG_BASE64 = (
    "iVBORw0KGgoAAAANSUhEUgAAABgAAAAMCAIAAAD3UuoiAAAAH0lEQVR4nGMUidrCQA3A"
    "RBVTGEYNIgaMBjZhMPjCCAAKLAE6Pmc9OAAAAABJRU5ErkJggg=="
)

_STREAM = re.compile(rb"stream\r?\n(.*?)endstream", re.S)
# A PDF string escapes its own delimiters, so "Total (USD)" is written
# "Total \(USD\)". Undone in one pass so a test can assert what it reads.
_ESCAPED = re.compile(r"\\([()\\])")


def pdf_text(content: bytes) -> str:
    parts = []
    for match in _STREAM.finditer(content):
        try:
            parts.append(zlib.decompress(match.group(1)).decode("latin-1"))
        except zlib.error:
            continue
    return _ESCAPED.sub(r"\1", "".join(parts))
