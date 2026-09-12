"""NFL stadium coordinates — the one-time lookup table the architecture calls
for (no-key-data-sources.md: "needs a stadium lat/long lookup table").

nflverse ships the stadium *name* and a `roof` value per game but no
coordinates, so both the weather pull and the travel-distance feature depend
on this table. Keyed by the stadium string nflverse uses.

`roof_type` records what the building is, independent of any single game's
`roof` value:
    fixed       permanently enclosed
    retractable roof may be open or shut on the day
    outdoor     open air

nflverse's per-game `roof` field is authoritative when present; this column is
the fallback for games where it is still null (common for future fixtures).
International venues are included — the league plays several games a year
abroad and those rows would otherwise have no coordinates at all.
"""

from __future__ import annotations

# stadium -> (latitude, longitude, roof_type)
NFL_VENUES: dict[str, tuple[float, float, str]] = {
    # --- AFC ---
    "Highmark Stadium":                 (42.7738, -78.7870, "outdoor"),      # BUF
    "Hard Rock Stadium":                (25.9580, -80.2389, "outdoor"),      # MIA
    "Gillette Stadium":                 (42.0909, -71.2643, "outdoor"),      # NE
    "MetLife Stadium":                  (40.8128, -74.0742, "outdoor"),      # NYJ / NYG
    "M&T Bank Stadium":                 (39.2780, -76.6227, "outdoor"),      # BAL
    "Paycor Stadium":                   (39.0954, -84.5160, "outdoor"),      # CIN
    "Huntington Bank Field":            (41.5061, -81.6995, "outdoor"),      # CLE
    "Acrisure Stadium":                 (40.4468, -80.0158, "outdoor"),      # PIT
    "NRG Stadium":                      (29.6847, -95.4107, "retractable"),  # HOU
    "Reliant Stadium":                  (29.6847, -95.4107, "retractable"),  # HOU (legacy name)
    "Lucas Oil Stadium":                (39.7601, -86.1639, "retractable"),  # IND
    "EverBank Stadium":                 (30.3239, -81.6373, "outdoor"),      # JAX
    "Nissan Stadium":                   (36.1665, -86.7713, "outdoor"),      # TEN
    "Empower Field at Mile High":       (39.7439, -105.0201, "outdoor"),     # DEN
    "GEHA Field at Arrowhead Stadium":  (39.0489, -94.4839, "outdoor"),      # KC
    "Allegiant Stadium":                (36.0909, -115.1833, "fixed"),       # LV
    "SoFi Stadium":                     (33.9535, -118.3392, "fixed"),       # LAC / LA

    # --- NFC ---
    "AT&T Stadium":                     (32.7473, -97.0945, "retractable"),  # DAL
    "Lincoln Financial Field":          (39.9008, -75.1675, "outdoor"),      # PHI
    "Northwest Stadium":                (38.9076, -76.8645, "outdoor"),      # WAS
    "Soldier Field":                    (41.8623, -87.6167, "outdoor"),      # CHI
    "Ford Field":                       (42.3400, -83.0456, "fixed"),        # DET
    "Lambeau Field":                    (44.5013, -88.0622, "outdoor"),      # GB
    "U.S. Bank Stadium":                (44.9738, -93.2578, "fixed"),        # MIN
    "Mercedes-Benz Stadium":            (33.7554, -84.4008, "retractable"),  # ATL
    "Bank of America Stadium":          (35.2258, -80.8528, "outdoor"),      # CAR
    "Caesars Superdome":                (29.9511, -90.0812, "fixed"),        # NO
    "Raymond James Stadium":            (27.9759, -82.5033, "outdoor"),      # TB
    "State Farm Stadium":               (33.5276, -112.2626, "retractable"), # ARI
    "Levi's Stadium":                   (37.4033, -121.9694, "outdoor"),     # SF
    "Lumen Field":                      (47.5952, -122.3316, "outdoor"),     # SEA

    # --- International / neutral sites ---
    "Wembley Stadium":                  (51.5560, -0.2796, "outdoor"),       # London
    "Tottenham Hotspur Stadium":        (51.6043, -0.0665, "outdoor"),       # London
    "Estadio Banorte":                  (19.3029, -99.1505, "outdoor"),      # Mexico City
    "Allianz Arena":                    (48.2188, 11.6247, "fixed"),         # Munich
    "FC Bayern Munich Stadium":         (48.2188, 11.6247, "fixed"),         # Munich
    "Santiago Bernabeu":                (40.4531, -3.6883, "retractable"),   # Madrid
    "Bernabeu":                         (40.4531, -3.6883, "retractable"),   # Madrid
    "Maracana Stadium":                 (-22.9121, -43.2302, "outdoor"),     # Rio
    "Melbourne Cricket Ground":         (-37.8200, 144.9834, "outdoor"),     # Melbourne
    "Stade de France":                  (48.9245, 2.3601, "outdoor"),        # Paris
    "Croke Park":                       (53.3607, -6.2512, "outdoor"),       # Dublin
}

# nflverse `roof` values that mean "no weather".
INDOOR_ROOFS = {"dome", "closed"}


def lookup(stadium: str | None):
    """Return (lat, lon, roof_type) or None if the stadium is unknown."""
    if not stadium:
        return None
    return NFL_VENUES.get(stadium.strip())


def is_indoor(stadium: str | None, roof: str | None) -> bool:
    """Decide whether a game is played indoors.

    The per-game `roof` value wins when present. When it is null — which is
    normal for fixtures that have not been played — fall back to the building:
    a fixed dome is always indoors, and a retractable roof is assumed shut,
    since applying an outdoor wind penalty to a game that may well be played
    under a closed roof is the worse error.
    """
    if roof and str(roof).strip().lower() in INDOOR_ROOFS:
        return True
    if roof and str(roof).strip().lower() in ("outdoors", "open"):
        return False
    entry = lookup(stadium)
    return entry is not None and entry[2] in ("fixed", "retractable")
