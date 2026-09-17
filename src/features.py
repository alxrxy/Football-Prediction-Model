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

from . import db

# --- tunable priors --------------------------------------------------------

HOME_FIELD_POINTS = {            # neutral sites get 0
    "ncaaf": 2.4,                # college crowds/travel make this larger
    "nfl": 1.9,                  # modern NFL home edge has compressed
}
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

# Position weights for the injury layer (§4), relative to a starting QB at 1.0.
POSITION_WEIGHTS = {
    "QB": 1.00,
    # Offensive line. Left tackle carries the most, interior the least.
    "LT": 0.35, "T": 0.30, "OT": 0.30, "OL": 0.25, "C": 0.25, "G": 0.20, "OG": 0.20,
    # Pass rush and interior defensive line.
    "EDGE": 0.32, "DE": 0.30, "OLB": 0.28, "DT": 0.22, "NT": 0.18, "DL": 0.25,
    # Secondary and linebackers.
    "CB": 0.28, "DB": 0.24, "S": 0.20, "FS": 0.20, "SS": 0.20,
    "LB": 0.20, "ILB": 0.18, "MLB": 0.20,
    # Skill positions.
    "WR": 0.22, "RB": 0.18, "TE": 0.15, "FB": 0.08,
    # Specialists.
    "K": 0.10, "P": 0.05, "LS": 0.03,
}
DEFAULT_POSITION_WEIGHT = 0.15

# Points a team loses when a full-time starting QB is completely unavailable.
# Everything else scales off this via POSITION_WEIGHTS.
INJURY_POINTS_SCALE = {"ncaaf": 7.0, "nfl": 6.0}

# No single team's injury adjustment may exceed this. A long injury report of
# marginal players should not accumulate into a fictitious blowout.
INJURY_MAX_POINTS = 8.0

# Used only when a player appears in no snap-count table at all - typically a
# rookie or practice-squad call-up. Deliberately low: an unknown player is far
# more likely to be a reserve than a starter, and over-crediting one is the
# expensive mistake here.
DEFAULT_SNAP_SHARE = 0.35

# How many players at a position can realistically be on the field. Only the
# top few by snap share are charged: if the starting QB is out, the backup
# plays, and charging for the backup's own knock as well would double-count a
# seat that only one player can occupy.
STARTER_SLOTS = {
    "QB": 1, "RB": 1, "FB": 1, "TE": 1, "WR": 3, "K": 1, "P": 1, "LS": 1,
    "LT": 1, "T": 2, "OT": 2, "C": 1, "G": 2, "OG": 2, "OL": 5,
    "DE": 2, "EDGE": 2, "DT": 2, "NT": 1, "DL": 4,
    "LB": 3, "ILB": 2, "MLB": 1, "OLB": 2,
    "CB": 3, "S": 2, "FS": 1, "SS": 1, "DB": 4,
}
DEFAULT_STARTER_SLOTS = 3

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


def score_injuries(rows: list[dict], sport: str) -> tuple[float, list[dict]]:
    """Cost of one team's injury report, in points. Negative = weakened.

    Deliberately a free function rather than a method: the ML training set
    scores historical reports with this exact code. If training scored injuries
    even slightly differently from the live pipeline, the model would be fed a
    feature at prediction time that it never actually learned.

    Each player contributes:

        position weight  x  snap share  x  (1 - play probability)  x  scale
    """
    scale = INJURY_POINTS_SCALE.get(sport, 6.5)

    # Keep only the players who could actually be on the field at each
    # position, highest snap share first. Without this a team listing three
    # hurt quarterbacks would be charged three times for one job.
    by_position: dict[str, list[dict]] = {}
    for row in rows:
        by_position.setdefault((row.get("position") or "").upper(), []).append(row)
    eligible = []
    for position, group in by_position.items():
        group.sort(key=lambda r: -(r.get("snap_share") or DEFAULT_SNAP_SHARE))
        eligible.extend(group[: STARTER_SLOTS.get(position, DEFAULT_STARTER_SLOTS)])

    penalty = 0.0
    breakdown = []
    for row in eligible:
        weight = row.get("position_weight")
        if weight is None:
            weight = POSITION_WEIGHTS.get(
                (row.get("position") or "").upper(), DEFAULT_POSITION_WEIGHT
            )
        play_prob = row.get("play_probability")
        if play_prob is None:
            play_prob = PLAY_PROBABILITY.get((row.get("status") or "").lower(), 0.5)
        snap_share = row.get("snap_share")
        if snap_share is None:
            snap_share = DEFAULT_SNAP_SHARE

        cost = weight * snap_share * (1.0 - play_prob) * scale
        if cost < 0.05:
            continue  # immaterial; keeps the breakdown readable
        penalty += cost
        breakdown.append(
            {
                "player": row.get("player"),
                "position": row.get("position"),
                "status": row.get("status"),
                "practice": row.get("practice_trend"),
                "snap_share": round(float(snap_share), 3),
                "play_prob": round(float(play_prob), 2),
                "points": round(cost, 2),
            }
        )

    penalty = min(penalty, INJURY_MAX_POINTS)
    breakdown.sort(key=lambda b: -b["points"])
    return -penalty, breakdown


def qb_availability_loss(rows: list[dict]) -> float:
    """How much of a starting quarterback a team is missing, from 0 to 1.

    Split out as its own feature because a QB injury is categorically unlike
    any other: it is not four cornerbacks' worth of damage, it is a different
    kind of event, and a tree model can use the isolated signal far better than
    it can recover it from an aggregate points total.
    """
    qbs = [r for r in rows if (r.get("position") or "").upper() == "QB"]
    if not qbs:
        return 0.0
    qbs.sort(key=lambda r: -(r.get("snap_share") or DEFAULT_SNAP_SHARE))
    starter = qbs[0]
    play_prob = starter.get("play_probability")
    if play_prob is None:
        play_prob = PLAY_PROBABILITY.get((starter.get("status") or "").lower(), 0.5)
    share = starter.get("snap_share")
    if share is None:
        share = DEFAULT_SNAP_SHARE
    return float(share) * (1.0 - float(play_prob))


# Sources whose report arrives team by team through the week (P19).
PER_TEAM_SOURCES = {"nflverse"}


def latest_injury_report(rows: list[dict]) -> list[dict]:
    """Only the rows from each source's most recent pull.

    Injury rows are upserted and never deleted, so a player who drops off the
    report — cleared, or upgraded to a full practice with no game status, which
    the NFL ingester skips — keeps his older, worse row, and so does every
    earlier week's report. Reading every row keeps charging all of them. Each
    ingest run stamps its rows with a single pulled_at, so the latest pull per
    source is exactly the current report. Per source rather than overall, so a
    run in which one feed failed falls back to that feed's previous report
    instead of silently dropping it.

    nflverse is the exception (P19). Its weekly report fills in team by team --
    Thursday's teams file first -- so a pull can hold only a few teams, and
    taking it whole would retire the reports every other team already filed
    that week. For nflverse the report is its latest week only, and within
    that week each team's latest pull. A team with nothing filed for that week
    has no nflverse rows; last week's statuses are not carried forward. The
    one case this cannot see: a team whose whole report clears mid-week writes
    no rows at all, so its earlier same-week rows stay in force.
    """
    latest: dict = {}
    week: dict = {}
    for row in rows:
        pulled = parse_dt(row.get("pulled_at"))
        source = row.get("source")
        if not pulled:
            continue
        if source in PER_TEAM_SOURCES:
            wk = (row.get("season"), row.get("week"))
            if source not in week or wk > week[source]:
                week[source] = wk
        elif source not in latest or pulled > latest[source]:
            latest[source] = pulled

    for row in rows:
        pulled = parse_dt(row.get("pulled_at"))
        source = row.get("source")
        if pulled and source in PER_TEAM_SOURCES \
                and (row.get("season"), row.get("week")) == week[source]:
            key = (source, row.get("team"))
            if key not in latest or pulled > latest[key]:
                latest[key] = pulled

    def current(r) -> bool:
        source = r.get("source")
        if source in PER_TEAM_SOURCES:
            if (r.get("season"), r.get("week")) != week.get(source):
                return False
            source = (source, r.get("team"))
        return parse_dt(r.get("pulled_at")) == latest.get(source)

    return [r for r in rows if current(r)]


class FeatureContext:
    """Pre-loaded lookups so building N games' features costs one DB read each."""

    def __init__(self, store, sport: str = "ncaaf"):
        self.store = store
        self.sport = sport
        self.prices: dict[str, list[dict]] = {}
        self.games = store.select("games", {"sport": sport})
        self.teams = {t["team"]: t for t in store.select("teams", {"sport": sport})}
        self.venues = {v["venue_id"]: v for v in store.select("venues")}
        self.weather = {w["game_id"]: w for w in store.select("weather")}
        self.injuries = latest_injury_report(store.select("injuries", {"sport": sport}))

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

        Preference order is liveness: The Odds API consensus (current, several
        US books), then CFBD's consensus (free, no quota), then the nflverse
        line, which is a stored closing/opening number rather than a live one.
        Returns (spread, total, source, n_books).
        """
        books = self.odds.get(game_id, {})
        sources = (
            ("oddsapi_consensus", "the_odds_api", "oddsapi:"),
            ("cfbd_consensus", "cfbd", "cfbd:"),
            ("nflverse_close", "nflverse", None),
        )
        for key, label, prefix in sources:
            row = books.get(key)
            if row and row.get("spread") is not None:
                n_books = sum(1 for b in books if b.startswith(prefix)) if prefix else 1
                return float(row["spread"]), row.get("total"), label, n_books
        return None, None, None, 0

    def load_prices(self, game_ids) -> None:
        """Each book's latest pregame line and prices for these games.

        The odds table keeps each book's line but not its price, and
        devigging needs the price (src/market.py), so this reads
        odds_snapshots. A snapshot taken at or after kickoff is an in-play
        price and is ignored. Games with no snapshot get no prices, which the
        edge test treats as -110 both ways.
        """
        ids = sorted(set(game_ids))
        kickoff = {g["game_id"]: parse_dt(g.get("kickoff_time")) for g in self.games}
        rows: list[dict] = []
        for i in range(0, len(ids), 100):
            rows += db.select_merged(self.store, "odds_snapshots", {"game_id": ids[i:i + 100]})
        latest: dict[tuple[str, str], dict] = {}
        for r in rows:
            pulled, k = parse_dt(r.get("pulled_at")), kickoff.get(r["game_id"])
            if pulled is None or (k is not None and pulled >= k):
                continue
            key = (r["game_id"], r["book"])
            if key not in latest or pulled > parse_dt(latest[key]["pulled_at"]):
                latest[key] = r
        for (gid, _book), r in latest.items():
            self.prices.setdefault(gid, []).append(r)

    def ml_books(self, game_id: str) -> list[dict]:
        """Per-book moneylines from the odds table, for the market's win probability."""
        return [r for book, r in self.odds.get(game_id, {}).items() if book.startswith("oddsapi:")]

    def baseline_margin(self, home: str, away: str) -> tuple[float | None, str, dict]:
        """Layer 1: expected neutral-field margin from power ratings.

        `power_rating` is the sport-neutral input — points above average,
        filled from SP+ for NCAAF and from the EPA-derived rating for the NFL.
        Its difference is the prediction directly. Elo is the fallback,
        converted at 25 Elo per point.
        """
        h, a = self.ratings.get(home, {}), self.ratings.get(away, {})
        h_pr, a_pr = h.get("power_rating"), a.get("power_rating")
        detail = {
            "home_power_rating": h_pr, "away_power_rating": a_pr,
            "home_sp_plus": h.get("sp_plus"), "away_sp_plus": a.get("sp_plus"),
            "home_elo": h.get("elo"), "away_elo": a.get("elo"),
        }

        # Fill an unrated side with a replacement-level proxy. This only ever
        # applies to college, where FBS teams routinely play unrated FCS
        # opponents; every NFL team is rated, so an NFL gap is a real fault
        # and must not be papered over with a fabricated rating.
        proxied: list[str] = []
        if self.sport == "ncaaf":
            if h_pr is None and a_pr is not None:
                h_pr = FCS_PROXY_SP_PLUS
                proxied.append(home)
            elif a_pr is None and h_pr is not None:
                a_pr = FCS_PROXY_SP_PLUS
                proxied.append(away)

        if h_pr is not None and a_pr is not None:
            detail["fcs_proxy_applied_to"] = proxied or None
            source = "sp_plus_fcs_proxy" if proxied else "power_rating"
            return h_pr - a_pr, source, detail

        h_elo, a_elo = h.get("elo"), a.get("elo")
        if h_elo is not None and a_elo is not None:
            return (h_elo - a_elo) / ELO_POINTS_DIVISOR, "elo", detail

        return None, "none", detail

    def injury_adjustment(self, team: str) -> tuple[float, bool, list[dict]]:
        """Layer 2 injury shift, in points. Negative = this team is weakened.

        Each player contributes:

            position weight  x  snap share  x  (1 - play probability)  x  scale

        The snap-share term is what makes this safe. An injury report lists
        third-stringers next to starters, and without it a backup QB being out
        would cost a team a full starting-QB penalty. Weighting by the share of
        snaps a player actually takes means a deep reserve contributes ~nothing
        while a genuine starter carries full weight.

        Returns (points, has_data, breakdown). has_data is False when the team
        has no rows at all, which the report surfaces rather than silently
        treating an unreported team as fully healthy.
        """
        rows = [i for i in self.injuries if i.get("team") == team]
        if not rows:
            return 0.0, False, []
        points, breakdown = score_injuries(rows, self.sport)
        return points, True, breakdown

    # --- assembly ---------------------------------------------------------

    def build(self, game: dict) -> dict:
        home, away = game["home_team"], game["away_team"]
        kickoff = parse_dt(game.get("kickoff_time"))
        neutral = bool(game.get("is_neutral_site"))

        margin, source, rating_detail = self.baseline_margin(home, away)

        # nflverse supplies rest days directly; for CFB they are derived from
        # the loaded schedule, which needs the previous week ingested.
        home_rest = game.get("home_rest_days")
        away_rest = game.get("away_rest_days")
        if home_rest is None and kickoff:
            home_rest = self.rest_days(home, kickoff)
        if away_rest is None and kickoff:
            away_rest = self.rest_days(away, kickoff)
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

        sport = game.get("sport", self.sport)
        hfa = 0.0 if neutral else HOME_FIELD_POINTS.get(sport, 2.4)

        weather = self.weather.get(game["game_id"]) or {}
        wind = weather.get("wind_mph")
        is_dome = bool(weather.get("is_dome"))
        wind_factor = 1.0
        if not is_dome and wind is not None and wind > WIND_THRESHOLD_MPH:
            wind_factor = 1.0 - min(
                WIND_COMPRESSION_CAP, (wind - WIND_THRESHOLD_MPH) * WIND_COMPRESSION_PER_MPH
            )

        home_inj, home_inj_data, home_inj_detail = self.injury_adjustment(home)
        away_inj, away_inj_data, away_inj_detail = self.injury_adjustment(away)
        injury_adj = home_inj - away_inj

        market_spread, market_total, market_source, n_books = self.market(game["game_id"])

        return {
            "game_id": game["game_id"],
            "sport": sport,
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
            "home_injury_points": round(home_inj, 2),
            "away_injury_points": round(away_inj, 2),
            "home_injury_detail": home_inj_detail,
            "away_injury_detail": away_inj_detail,
            "injury_coverage": ("both" if home_inj_data and away_inj_data
                                else "home" if home_inj_data
                                else "away" if away_inj_data else "none"),
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
            "market_prices": self.prices.get(game["game_id"], []),
            "market_ml_books": self.ml_books(game["game_id"]),
        }
