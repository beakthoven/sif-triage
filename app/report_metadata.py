"""Conservative metadata extraction from free-text safety reports."""

from __future__ import annotations

import re


_LOCATION_LABEL = re.compile(
    r"^\s*(?:site|location|field|installation|plant)\s*[:\-–—]\s*"
    r"([^.\n]{2,80})",
    re.IGNORECASE,
)
_LOCATION_CUE = re.compile(
    r"\b(?:site|area|field|plant|station|terminal|yard|rig|well|"
    r"ggs|gcs|ctf|eps|workshop|warehouse|stores|facility|installation|platform)\b",
    re.IGNORECASE,
)
_PREPOSITIONAL_LOCATION = re.compile(
    r"\b(?:at|near|inside|within)\s+(?:the\s+)?([^,.;\n]{2,60})",
    re.IGNORECASE,
)


def extract_site(text: str) -> str | None:
    """Return an explicit leading location, otherwise leave the site unknown.

    Reports often start with a compact header such as ``Duliajan Pipe Yard.``
    or ``Location: Moran Production Area``. Restricting extraction to that
    leading header avoids turning an arbitrary incident sentence into a site.
    """
    labelled = _LOCATION_LABEL.match(text)
    if labelled:
        return labelled.group(1).strip(" \t:;,–—-") or None

    for match in _PREPOSITIONAL_LOCATION.finditer(text):
        candidate = match.group(1).strip(" \t:;,–—-")
        if _LOCATION_CUE.search(candidate):
            return candidate

    first_clause = re.split(r"[.\n]", text, maxsplit=1)[0].strip()
    if 2 <= len(first_clause) <= 80 and _LOCATION_CUE.search(first_clause):
        return first_clause.strip(" \t:;,–—-") or None
    return None
