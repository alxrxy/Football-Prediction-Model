"""NFL team names, colours and logos for the dashboard.

    python -m src.export_team_meta

Writes dashboard/src/nflTeams.json from nflverse's team table: full name,
nickname, primary and secondary colours, and ESPN's logo URL, keyed by the
same abbreviations the games table uses (LA for the Rams, WAS for
Washington). Teams rarely change, so the file is committed and only needs
re-running after a rebrand or relocation.
"""

from __future__ import annotations

import json

from . import config

OUT = config.ROOT / "dashboard" / "src" / "nflTeams.json"


def run() -> str:
    import nfl_data_py as nfl

    teams = nfl.import_team_desc()
    out = {
        str(r.team_abbr): {
            "name": r.team_name, "nick": r.team_nick,
            "color": r.team_color, "color2": r.team_color2, "logo": r.team_logo_espn,
        }
        for r in teams.itertuples()
    }
    OUT.write_text(json.dumps(dict(sorted(out.items())), indent=1), encoding="utf-8")
    print(f"[teams] {len(out)} teams -> {OUT}")
    return str(OUT)


if __name__ == "__main__":
    run()
