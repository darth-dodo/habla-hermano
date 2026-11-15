"""The CSP has no 'unsafe-inline', so inline on*= handlers are silently blocked.

Use Alpine (@click) or Tailwind hover: classes instead.
"""

import re
from pathlib import Path

SRC = Path(__file__).parents[1] / "src"
INLINE_HANDLER = re.compile(r"""\son[a-z]+\s*=\s*["']""", re.IGNORECASE)


def test_no_inline_event_handlers_in_templates_or_scripts() -> None:
    files = [*SRC.glob("templates/**/*.html"), *SRC.glob("static/js/**/*.js")]
    offenders = [
        f"{path.relative_to(SRC)}:{n}"
        for path in files
        if not path.name.endswith(".min.js")
        for n, line in enumerate(path.read_text().splitlines(), 1)
        if INLINE_HANDLER.search(line)
    ]
    assert files and offenders == []
