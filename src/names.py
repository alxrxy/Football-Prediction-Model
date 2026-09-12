"""Team-name matching across feeds.

Every external source names teams differently: CFBD uses school names
("App State"), nflverse uses abbreviations ("KC"), and The Odds API and ESPN
both spell out the full name with a mascot ("Appalachian State Mountaineers").
Matching lives here so the odds and injury ingesters score names identically.
"""

from __future__ import annotations

import re
import unicodedata
from difflib import SequenceMatcher

# Odds API names carry mascots ("Oklahoma State Cowboys"); CFBD does not.
_NOISE = re.compile(r"[^a-z0-9 ]+")
_APOSTROPHE = re.compile(r"[‘’'`´]")
MATCH_THRESHOLD = 0.72

# Confirmed divergences between Odds API and CFBD naming, normalized form.
# Keyed by the Odds API side, valued by the CFBD side.
_ALIASES = {
    "appalachian state": "app state",
    "umass": "massachusetts",
    "fiu": "florida international",
    "southern mississippi": "southern miss",
    "louisiana lafayette": "louisiana",
    "louisiana ragin cajuns": "louisiana",
    "louisiana monroe": "ul monroe",
    "miami fl": "miami",
    "miami florida": "miami",
    "miami oh": "miami oh",
    "miami ohio": "miami oh",
    "connecticut": "uconn",
    "middle tennessee state": "middle tennessee",
    "sam houston state": "sam houston",
    "texas san antonio": "utsa",
    "texas el paso": "utep",
    "nevada las vegas": "unlv",
}


def norm(name: str) -> str:
    """Casefold, strip diacritics and apostrophes, drop filler words.

    Apostrophes are deleted rather than replaced with a space so CFBD's
    "Hawai'i" collapses to "hawaii" and matches the Odds API spelling.
    """
    name = unicodedata.normalize("NFKD", name or "")
    name = "".join(c for c in name if not unicodedata.combining(c))
    name = _APOSTROPHE.sub("", name.lower())
    name = _NOISE.sub(" ", name)
    name = re.sub(r"\b(university|univ|of|the)\b", " ", name)
    return re.sub(r"\s+", " ", name).strip()


def similarity(odds_name: str, cfbd_name: str) -> float:
    """Score an Odds API name against a CFBD name.

    The CFBD side is expanded into every Odds-API spelling that aliases to it,
    then each variant is tested as a prefix of the Odds name (which carries a
    mascot the CFBD name lacks).
    """
    a, b = norm(odds_name), norm(cfbd_name)
    if not a or not b:
        return 0.0

    variants = {b} | {k for k, v in _ALIASES.items() if v == b}
    best = 0.0
    for variant in variants:
        if a == variant:
            return 1.0
        if a.startswith(variant + " "):
            # Score by how much of the Odds name the CFBD name accounts for.
            # A bare "Texas" covers little of "Texas Tech Red Raiders" and must
            # not outscore the real "Texas Tech" — coverage separates them
            # where a flat prefix bonus does not.
            best = max(best, 0.80 + 0.20 * (len(variant) / len(a)))
        else:
            best = max(best, SequenceMatcher(None, a, variant).ratio())
    return best
