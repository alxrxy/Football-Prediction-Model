"""Feature engineering (architecture §4).

Everything here is derived from the raw tables and never writes back to them.

IMPORTANT — the coefficients below are *priors*, not fitted values. They are
deliberately conservative starting points chosen to be roughly consistent with
published football research, and they exist so Layers 1+2 produce a sane number
before the ML layer (step 7) is trained. Treat every magnitude as provisional
until backtesting replaces it.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

# --- tunable priors --------------------------------------------------------

HOME_FIELD_POINTS = 2.4          # CFB home edge, neutral sites get 0
REST_POINTS_PER_DAY = 0.12       # per day of rest differential
REST_CAP_POINTS = 1.5            # cap so a bye week can't dominate
TRAVEL_POINTS_PER_1000MI = 0.45  # penalty to the travelling side
TRAVEL_CAP_POINTS = 1.0
WIND_THRESHOLD_MPH = 15.0        # below this, wind is ignored entirely
WIND_COMPRESSION_PER_MPH = 0.006 # fraction of margin shaved per mph over
WIND_COMPRESSION_CAP = 0.10

# Teams with no SP+ row are almost always FCS opponents. Rating them at a
# fixed replacement level keeps those games in the slate, clearly flagged,
# rather than silently dropping them.
FCS_PROXY_SP_PLUS = -28.0

# Points-per-Elo conversion. 25 Elo ~ 1 point is the long-standing convention.
ELO_POINTS_DIVISOR = 25.0

# Scoring-margin dispersion, used to turn a predicted margin into a win
# probability. CFB margins are noisier than the NFL's.
MARGIN_SIGMA = {"ncaaf": 16.0, "nfl": 13.0}

# Position weights for the injury layer (§4). Unused until step 6 wires up
# ESPN depth charts — kept here so the weighting lives with the other priors.
POSITION_WEIGHTS = {
    "QB": 1.00,
    "LT": 0.35, "OT": 0.30, "OL": 0.25, "C": 0.25, "G": 0.20,
    "EDGE": 0.32, "DE": 0.30, "DT": 0.22,
    "CB": 0.28, "S": 0.20, "LB": 0.20,
    "WR": 0.22, "RB": 0.18, "TE": 0.15,
    "K": 0.10, "P": 0.05,
}
PLAY_PROBABILITY = {
    "out": 0.0, "doubtful": 0.15, "questionable": 0.55,
    "probable": 0.85, "available": 1.0,
}


def parse_dt(value):
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def haversine_miles(lat1, lon1, lat2, lon2) -> float | None:
    if None in (lat1, lon1, lat2, lon2):
        return None
    radius = 3958.8
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * radius * math.asin(math.sqrt(a))


def normal_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


class FeatureContext:
    """Pre-loaded lookups so building N games' features costs one DB read each."""

    def __init__(self, store, sport: str = "ncaaf"):
        self.sport = sport
        self.games = store.select("games", {"sport": sport})
        self.teams = {t["team"]: t for t in store.select("teams", {"sport": sport})}
        self.venues = {v["venue_id"]: v for v in store.select("venues")}
        self.weather = {w["game_id"]: w for w in store.select("weather")}
        self.injuries = store.select("injuries", {"sport": sport})

        ratings = store.select("team_ratings", {"sport": sport})
        # Keep the most recent week per team.
        self.ratings: dict[str, dict] = {}
        for r in ratings:
            prev = self.ratings.get(r["team"])
            if prev is None or (r.get("week") or 0) >= (prev.get("week") or 0):
                self.ratings[r["team"]] = r

        # game_id -> {book: row}
        self.odds: dict[str, dict[str, dict]] = {}
        for row in store.select("odds"):
            self.odds.setdefault(row["game_id"], {})[row["book"]] = row

        # team -> sorted kickoff times, for rest days
        self.schedule: dict[str, list[datetime]] = {}
        for g in self.games:
            kickoff = parse_dt(g.get("kickoff_time"))
            if kickoff is None:
                continue
            for team in (g["home_team"], g["away_team"]):
                self.schedule.setdefault(team, []).append(kickoff)
        for team in self.schedule:
            self.schedule[team].sort()

    # --- individual features ---------------------------------------------

    def rest_days(self, team: str, kickoff: datetime) -> float | None:
        """Days since this team's previous game. None if no prior game loaded."""
        history = self.schedule.get(team, [])
        previous = [k for k in history if k < kickoff - timedelta(hours=6)]
        if not previous:
            return None
        return (kickoff - previous[-1]).total_seconds() / 86400.0

    def travel_miles(self, team: str, game: dict) -> float | None:
        """Distance from the team's home stadium to the game venue."""
        team_row = self.teams.get(team)
        venue = self.venues.get(str(game.get("venue_id"))) if game.get("venue_id") else None
        if not team_row or not venue:
            return None
        return haversine_miles(
            team_row.get("home_latitude"), team_row.get("home_longitude"),
            venue.get("latitude"), venue.get("longitude"),
        )

    def market(self, game_id: str) -> tuple[float | None, float | None, str | None, int]:
        """Consensus market line for a game.

        Prefers The Odds API consensus (live, multiple US books) and falls back
        to CFBD's consensus, which is free and does not touch the quota.
        Returns (spread, total, source, n_books).
        """
        books = self.odds.get(game_id, {})
        for key, label in (("oddsapi_consensus", "the_odds_api"), ("cfbd_consensus", "cfbd")):
            row = books.get(key)
            if row and row.get("spread") is not None:
                prefix = "oddsapi:" if label == "the_odds_api" else "cfbd:"
                n_books = sum(1 for b in books if b.startswith(prefix))
                return float(row["spread"]), row.get("total"), label, n_books
        return None, None, None, 0

    def baseline_margin(self, home: str, away: str) -> tuple[float | None, str, dict]:
        """Layer 1: expected neutral-field margin from power ratings.

        SP+ is already expressed in points, so the raw difference is the
        prediction. Elo is the fallback, converted at 25 Elo per point.
        """
        h, a = self.ratings.get(home, {}), self.ratings.get(away, {})
        h_sp, a_sp = h.get("sp_plus"), a.get("sp_plus")
        detail = {
            "home_sp_plus": h_sp, "away_sp_plus": a_sp,
            "home_elo": h.get("elo"), "away_elo": a.get("elo"),
        }

        # Fill an unrated (FCS) side with a replacement-level proxy.
        proxied = []
        if h_sp is None and a_sp is not None:
            h_sp, _ = FCS_PROXY_SP_PLUS, proxied.append(home)
        elif a_sp is None and h_sp is not None:
            a_sp, _ = FCS_PROXY_SP_PLUS, proxied.append(away)

        if h_sp is not None and a_sp is not None:
            detail["fcs_proxy_applied_to"] = proxied or None
            source = "sp_plus_fcs_proxy" if proxied else "sp_plus"
            return h_sp - a_sp, source, detail

        h_elo, a_elo = h.get("elo"), a.get("elo")
        if h_elo is not None and a_elo is not None:
            return (h_elo - a_elo) / ELO_POINTS_DIVISOR, "elo", detail

        return None, "none", detail

    def injury_adjustment(self, team: str) -> tuple[float, bool]:
        """Layer 2 injury shift, in points, positive = this team is hurt less.

        Returns (points, has_data). Until step 6 populates the injuries table
        this is a genuine no-op and reports has_data=False, so the report can
        say so rather than implying injuries were considered.
        """
        rows = [i for i in self.injuries if i.get("team") == team]
        if not rows:
            return 0.0, False
        penalty = 0.0
        for row in rows:
            weight = row.get("position_weight")
            if weight is None:
                weight = POSITION_WEIGHTS.get((row.get("position") or "").upper(), 0.15)
            play_prob = row.get("play_probability")
            if play_prob is None:
                play_prob = PLAY_PROBABILITY.get((row.get("status") or "").lower(), 0.5)
            # Missed availability × positional importance, scaled to points.
            penalty += weight * (1.0 - play_prob) * 7.0
        return -penalty, True

    # --- assembly ---------------------------------------------------------

    def build(self, game: dict) -> dict:
        home, away = game["home_team"], game["away_team"]
        kickoff = parse_dt(game.get("kickoff_time"))
        neutral = bool(game.get("is_neutral_site"))

        margin, source, rating_detail = self.baseline_margin(home, away)

        home_rest = self.rest_days(home, kickoff) if kickoff else None
        away_rest = self.rest_days(away, kickoff) if kickoff else None
        rest_adj = 0.0
        if home_rest is not None and away_rest is not None:
            rest_adj = max(
                -REST_CAP_POINTS,
                min(REST_CAP_POINTS, (home_rest - away_rest) * REST_POINTS_PER_DAY),
            )

        # At a neutral site both teams travel; the adjustment is the difference.
        home_travel = self.travel_miles(home, game)
        away_travel = self.travel_miles(away, game)
        travel_adj = 0.0
        if away_travel is not None:
            away_pen = min(TRAVEL_CAP_POINTS, away_travel / 1000.0 * TRAVEL_POINTS_PER_1000MI)
            home_pen = 0.0
            if neutral and home_travel is not None:
                home_pen = min(TRAVEL_CAP_POINTS, home_travel / 1000.0 * TRAVEL_POINTS_PER_1000MI)
            travel_adj = away_pen - home_pen

        hfa = 0.0 if neutral else HOME_FIELD_POINTS

        weather = self.weather.get(game["game_id"]) or {}
        wind = weather.get("wind_mph")
        is_dome = bool(weather.get("is_dome"))
        wind_factor = 1.0
        if not is_dome and wind is not None and wind > WIND_THRESHOLD_MPH:
            wind_factor = 1.0 - min(
                WIND_COMPRESSION_CAP, (wind - WIND_THRESHOLD_MPH) * WIND_COMPRESSION_PER_MPH
            )

        home_inj, home_inj_data = self.injury_adjustment(home)
        away_inj, away_inj_data = self.injury_adjustment(away)
        injury_adj = home_inj - away_inj

        market_spread, market_total, market_source, n_books = self.market(game["game_id"])

        return {
            "game_id": game["game_id"],
            "sport": game.get("sport", self.sport),
            "home_team": home,
            "away_team": away,
            "kickoff_time": game.get("kickoff_time"),
            "is_neutral_site": neutral,
            "baseline_margin": margin,
            "baseline_source": source,
            "rating_detail": rating_detail,
            "hfa": hfa,
            "rest_adj": rest_adj,
            "home_rest_days": home_rest,
            "away_rest_days": away_rest,
            "travel_adj": travel_adj,
            "away_travel_miles": away_travel,
            "injury_adj": injury_adj,
            "injury_data_available": home_inj_data or away_inj_data,
            "wind_mph": wind,
            "temp_f": weather.get("temp_f"),
            "precip_pct": weather.get("precip_pct"),
            "is_dome": is_dome,
            "wind_factor": wind_factor,
            "has_weather": bool(weather),
            "market_spread": market_spread,
            "market_total": market_total,
            "market_source": market_source,
            "market_books": n_books,
        }
