"""Live in-game tracking for NFL games.

    python -m src.live_tracker                  poll every ~2.5 min until the day's games end
    python -m src.live_tracker --once           one polling cycle, then exit
    python -m src.live_tracker --interval 120   seconds between polls
    python -m src.live_tracker --no-notify      console + log only, no desktop toasts

A layer of its own. It reads the pregame prediction and simulation, never
changes either, and writes only `live_tracking` (plus data/live.json for the
live page and data/live/alerts.log).

Each cycle makes one scoreboard call, which says which games are in progress,
and one summary call per in-progress game for its scoring plays. Games that
have not kicked off are never polled: when nothing is live the tracker sleeps
until the next kickoff, and exits once nothing is scheduled within
IDLE_EXIT_HOURS. A game that finishes gets one closing snapshot from the
scoreboard already fetched, and is then left alone.

ESPN's site API is unofficial and is being hit far more often here than
anywhere else in the project. Every call goes through safe_get_json, and every
parse is guarded per game, so a failed request, a malformed payload or one odd
game costs that piece of that cycle and nothing more.

What "diverging" means
----------------------
The pregame simulation records the score every five minutes of game clock in
each of its 10,000 games, so for any moment there is a distribution of where
the total and the margin would typically be. A live game is placed in the
distribution for its own elapsed time:

  pace      points scored so far, as a percentile of simulated totals by now
  margin    the home margin so far, likewise
  underdog  the pregame underdog leads by more than UNDERDOG_LEAD points

Beyond the 5th/95th percentile is notable, beyond the 1st/99th extreme.
Percentiles are mid-ranked: 0-0 after five minutes is the single most common
state, and it sits mid-distribution rather than at the bottom of it.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import shutil
import subprocess
import sys
import time
import traceback
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone

import numpy as np

from . import config, db
from .features import FeatureContext, parse_dt
from .http import safe_get_json

POLL_SECONDS = 150
POLL_JITTER = 15
IDLE_EXIT_HOURS = 12
MAX_IDLE_SLEEP = 1800         # re-check the scoreboard at least this often while waiting
ESPN_TIMEOUT = 15
ESPN_RETRIES = 2
FAILED_CYCLES_WARNING = 3
STARTUP_RETRY_SECONDS = (0, 10, 30, 60)   # waits before each attempt at the startup read

MIN_ELAPSED_MINUTES = 5.0     # no pace/margin flags before this much game clock
UNDERDOG_LEAD = 7             # flag when the pregame underdog leads by MORE than this
UNDERDOG_EXTREME_LEAD = 14
LATE_MINUTES = 45.0           # from the 4th quarter an underdog lead is extreme
PICKEM_MARGIN = 0.5           # a game predicted this close has no underdog
NOTABLE, EXTREME = 0.05, 0.01
RECENT_SCORING = 3
MAX_ALERTS_EXPORTED = 50

ESPN_ALIASES = {"WSH": "WAS", "LAR": "LA"}   # ESPN code -> nflverse code
BROWSER_UA = {"User-Agent": "Mozilla/5.0"}    # see ingest_injuries.BROWSER_UA

LIVE_DIR = config.DATA_DIR / "live"
ALERT_LOG = LIVE_DIR / "alerts.log"          # human-readable
ALERT_JSONL = LIVE_DIR / "alerts.jsonl"      # the same alerts, reloaded by a restarted tracker
LIVE_JSON = config.DATA_DIR / "live.json"
PUBLIC_LIVE_JSON = config.ROOT / "dashboard" / "public" / "live.json"

LEVEL_RANK = {None: 0, "notable": 1, "extreme": 2}


# --- ESPN ------------------------------------------------------------------

def _espn(path: str, params: dict | None = None):
    """One ESPN call. Returns None on any failure; never raises."""
    return safe_get_json(
        f"{config.ESPN_NFL}/{path}", params=params, headers=BROWSER_UA,
        transport="urllib", timeout=ESPN_TIMEOUT, retries=ESPN_RETRIES,
    )


# --- core-API fallback -----------------------------------------------------
# site.api.espn.com is the only host this tracker reads, and on 2026-09-20 it
# began answering every request with an Akamai 403 ("Access Denied") while
# sports.core.api.espn.com - the host ingest_inactives already uses - kept
# serving. The two carry the same game state in different shapes, so rather
# than fail the whole cycle the tracker rebuilds a scoreboard-shaped payload
# from the core API and hands it to the unchanged parse_scoreboard.
#
# It costs about four calls a game against the site API's one, so it is a
# fallback and not the default: it runs only when the scoreboard call fails,
# and the tracker returns to the single call the moment that host recovers.
CORE_NFL = "https://sports.core.api.espn.com/v2/sports/football/leagues/nfl"
_TEAM_ABBR: dict[str, str] = {}   # team id -> abbreviation; teams do not change


def _core(url: str, params: dict | None = None):
    return safe_get_json(url, params=params, headers=BROWSER_UA, transport="urllib",
                         timeout=ESPN_TIMEOUT, retries=ESPN_RETRIES)


def _ref_id(ref: str | None) -> str:
    """The trailing id of a core-API $ref, without fetching it."""
    path = str(ref or "").split("?")[0].rstrip("/")
    return path.rsplit("/", 1)[-1] if path else ""


def _core_team(team_ref: str | None) -> str:
    """Abbreviation for a team $ref, fetched once and remembered."""
    tid = _ref_id(team_ref)
    if not tid:
        return ""
    if tid not in _TEAM_ABBR:
        data = _core(f"{CORE_NFL}/teams/{tid}") or {}
        _TEAM_ABBR[tid] = str(data.get("abbreviation") or "")
    return _TEAM_ABBR[tid]


def core_scoreboard(day: date | None = None) -> dict | None:
    """A scoreboard-shaped payload built from the core API, or None.

    Only the fields parse_event reads are filled. `situation` is deliberately
    left out: the core API carries down/distance and possession on a separate
    drives feed, and an absent situation already means "no live spot known" to
    every consumer, whereas a half-built one would be read as fact.
    """
    day = day or _now().date()
    index = _core(f"{CORE_NFL}/events", params={"dates": day.strftime("%Y%m%d"), "limit": 100})
    if not isinstance(index, dict):
        return None
    events = []
    for item in index.get("items") or []:
        event = _core(_ref_id_url(item.get("$ref")))
        if not isinstance(event, dict):
            continue
        comp = (event.get("competitions") or [{}])[0]
        eid = str(event.get("id") or "")
        status = _core(f"{CORE_NFL}/events/{eid}/competitions/{eid}/status") or {}
        stype = status.get("type") or {}
        state = str(stype.get("state") or "")
        competitors = []
        for c in comp.get("competitors") or []:
            # A game yet to start has no score document; 0 is right for it.
            score = 0
            if state != "pre":
                doc = _core(str((c.get("score") or {}).get("$ref") or "")) or {}
                score = doc.get("value") or 0
            competitors.append({
                "homeAway": c.get("homeAway"),
                "team": {"id": _ref_id((c.get("team") or {}).get("$ref")),
                         "abbreviation": _core_team((c.get("team") or {}).get("$ref"))},
                "score": score,
            })
        events.append({
            "id": eid,
            "date": event.get("date"),
            "competitions": [{
                "status": {"type": {"state": state,
                                    "name": str(stype.get("name") or ""),
                                    "shortDetail": str(stype.get("shortDetail")
                                                       or stype.get("detail") or "")},
                           "period": status.get("period"),
                           "clock": status.get("clock"),
                           "displayClock": status.get("displayClock")},
                "competitors": competitors,
            }],
        })
    if not events:
        return None
    season = (index.get("season") or {}) if isinstance(index.get("season"), dict) else {}
    return {"season": season, "events": events}


def _ref_id_url(ref: str | None) -> str:
    """A core-API $ref, forced to https (the feed hands back http)."""
    return str(ref or "").replace("http://", "https://", 1)


def _abbr(code) -> str:
    code = str(code or "").upper()
    return ESPN_ALIASES.get(code, code)


def _int(value) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


@dataclass
class LiveState:
    espn_id: str
    state: str                    # pre | in | post
    status: str                   # STATUS_IN_PROGRESS, STATUS_HALFTIME, ...
    period: int
    clock_seconds: float
    display_clock: str
    detail: str
    start: datetime | None
    home: str
    away: str
    home_score: int
    away_score: int
    possession: str | None = None
    down_distance: str | None = None
    red_zone: bool = False
    espn_home_wp: float | None = None
    postseason: bool = False
    home_id: str = ""
    away_id: str = ""
    situation: dict = field(default_factory=dict)   # possession side, down, togo, yardline_100


def yardline_100(possession_text, offense_code, defense_code, yard_line, side: int) -> int | None:
    """The offence's distance to score, from the scoreboard's situation.

    possessionText names the half of the field the ball is in ("LAC 12" is
    the Chargers' 12), which is unambiguous once matched to the offence's or
    the defence's own ESPN code. When it matches neither (ESPN's play text
    sometimes uses other codes, e.g. ARZ for ARI), fall back to yardLine,
    which counts from the HOME side's goal line: the Chargers (home) at their
    own 12 read 12, the Raiders (home) at the Dolphins' 12 read 88, and
    Washington (away) at its own 47 reads 53.
    """
    parts = str(possession_text or "").strip().upper().split()
    if len(parts) == 1 and parts[0] == "50":
        return 50
    if len(parts) == 2 and parts[1].isdigit():
        n = int(parts[1])
        if parts[0] == str(offense_code).upper() and 0 < n < 100:
            return 100 - n
        if parts[0] == str(defense_code).upper() and 0 < n < 100:
            return n
    n = _int(yard_line)
    if not 0 < n < 100:
        return None
    return 100 - n if side == 0 else n


def parse_event(event: dict, postseason: bool = False) -> LiveState:
    """One scoreboard event. Raises KeyError/IndexError if it is malformed."""
    comp = event["competitions"][0]
    status = comp["status"]
    sides = {c["homeAway"]: c for c in comp["competitors"]}
    home, away = sides["home"], sides["away"]
    team_by_id = {str(c["team"]["id"]): _abbr(c["team"]["abbreviation"]) for c in comp["competitors"]}
    situation = comp.get("situation") or {}
    prob = ((situation.get("lastPlay") or {}).get("probability") or {}).get("homeWinPercentage")
    possession = situation.get("possession")
    side_by_id = {str(home["team"]["id"]): 0, str(away["team"]["id"]): 1}
    down = _int(situation.get("down"))
    spot = {}
    if possession and str(possession) in side_by_id and down in (1, 2, 3, 4):
        side = side_by_id[str(possession)]
        offense, defense = (home, away) if side == 0 else (away, home)
        spot = {"possession": side, "down": down,
                "togo": _int(situation.get("distance")) or 10,
                "yardline_100": yardline_100(situation.get("possessionText"),
                                             offense["team"]["abbreviation"], defense["team"]["abbreviation"],
                                             situation.get("yardLine"), side)}
    return LiveState(
        espn_id=str(event["id"]),
        state=str(status["type"]["state"]),
        status=str(status["type"].get("name") or ""),
        period=_int(status.get("period")),
        clock_seconds=float(status.get("clock") or 0.0),
        display_clock=str(status.get("displayClock") or ""),
        detail=str(status["type"].get("shortDetail") or status["type"].get("detail") or ""),
        start=parse_dt(event.get("date")),
        home=_abbr(home["team"]["abbreviation"]),
        away=_abbr(away["team"]["abbreviation"]),
        home_score=_int(home.get("score")),
        away_score=_int(away.get("score")),
        possession=team_by_id.get(str(possession)) if possession else None,
        down_distance=situation.get("downDistanceText"),
        red_zone=bool(situation.get("isRedZone")),
        espn_home_wp=float(prob) if prob is not None else None,
        postseason=postseason,
        home_id=str(home["team"]["id"]),
        away_id=str(away["team"]["id"]),
        situation=spot,
    )


def parse_scoreboard(payload) -> tuple[list[LiveState], int]:
    """Every parseable event, and how many were skipped as malformed."""
    if not isinstance(payload, dict):
        return [], 0
    postseason = (payload.get("season") or {}).get("type") == 3
    states, skipped = [], 0
    for event in payload.get("events") or []:
        try:
            states.append(parse_event(event, postseason))
        except (KeyError, IndexError, TypeError, ValueError):
            skipped += 1
    return states, skipped


def recent_scoring(summary) -> list[dict] | None:
    """The latest scoring plays, newest first. None if the summary is unusable."""
    if not isinstance(summary, dict):
        return None
    out = []
    for p in (summary.get("scoringPlays") or [])[-RECENT_SCORING:][::-1]:
        out.append({
            "period": (p.get("period") or {}).get("number"),
            "clock": (p.get("clock") or {}).get("displayValue"),
            "team": _abbr((p.get("team") or {}).get("abbreviation")),
            "type": (p.get("type") or {}).get("text"),
            "text": p.get("text"),
            "home_score": p.get("homeScore"),
            "away_score": p.get("awayScore"),
        })
    return out


def scoring_path(summary, postseason: bool = False) -> list[dict] | None:
    """Every scoring play as (elapsed minute, score after it), oldest first.

    The live page draws the actual score from this: exact to the play rather
    than joined-up 2.5-minute snapshots, and complete from kickoff even when
    the tracker was started mid-game.
    """
    if not isinstance(summary, dict):
        return None
    out = []
    for p in summary.get("scoringPlays") or []:
        try:
            clock = float((p.get("clock") or {}).get("value"))
        except (TypeError, ValueError):
            continue
        period = _int((p.get("period") or {}).get("number"))
        out.append({"t": elapsed_minutes(period, clock, postseason=postseason),
                    "home": _int(p.get("homeScore")), "away": _int(p.get("awayScore"))})
    return out


def elapsed_minutes(period: int, clock_seconds: float, status: str = "",
                    postseason: bool = False) -> float:
    """Game-clock minutes played. Regular-season overtime is 10 minutes."""
    if period <= 0:
        return 0.0
    if status == "STATUS_HALFTIME":
        return 30.0
    if period <= 4:
        minutes = (period - 1) * 15 + (15 - clock_seconds / 60)
    else:
        ot = 15 if postseason else 10
        minutes = 60 + (period - 5) * ot + (ot - clock_seconds / 60)
    return round(min(max(minutes, 0.0), 120.0), 2)


# --- the simulated distribution at a point in the game ---------------------

def _cdf_at(pace: dict, key: str, t: float) -> np.ndarray:
    """CDF at elapsed minute t, linear between checkpoints. Past 60 minutes
    (overtime) the end-of-regulation distribution is used."""
    minutes = np.asarray(pace["minutes"], dtype=float)
    cdfs = np.asarray(pace[f"{key}_cdf"], dtype=float)
    t = float(np.clip(t, minutes[0], minutes[-1]))
    i = int(np.clip(np.searchsorted(minutes, t, side="right") - 1, 0, len(minutes) - 2))
    w = (t - minutes[i]) / (minutes[i + 1] - minutes[i])
    return (1 - w) * cdfs[i] + w * cdfs[i + 1]


def percentile(pace: dict, key: str, t: float, value: float) -> float:
    """Mid-rank percentile of `value` among simulated games at minute t:
    P(sim < value) + P(sim == value) / 2."""
    cdf = _cdf_at(pace, key, t)
    k = int(round(value)) - int(pace[f"{key}_min"])
    if k < 0:
        return 0.0
    if k >= len(cdf):
        return 1.0
    below = cdf[k - 1] if k > 0 else 0.0
    return float((below + cdf[k]) / 2)


def quantile(pace: dict, key: str, t: float, p: float) -> int:
    cdf = _cdf_at(pace, key, t)
    return int(np.searchsorted(cdf, p - 1e-9)) + int(pace[f"{key}_min"])


def bands(pace: dict) -> dict:
    """Per-checkpoint 5/25/50/75/95 bands for the live page's charts."""
    out = {"minutes": pace["minutes"]}
    for key in ("total", "margin"):
        out[key] = {
            f"p{int(p * 100):02d}": [quantile(pace, key, m, p) for m in pace["minutes"]]
            for p in (0.05, 0.25, 0.5, 0.75, 0.95)
        }
    return out


# --- pregame reference -----------------------------------------------------

@dataclass
class Pregame:
    game_id: str
    home: str
    away: str
    kickoff: datetime | None
    margin_home: float | None = None
    win_prob_home: float | None = None
    model: str | None = None
    generated_at: str | None = None
    market_spread: float | None = None
    market_total: float | None = None
    sim: dict | None = None
    sim_source: str | None = None
    notes: list[str] = field(default_factory=list)

    @property
    def favorite(self) -> str | None:
        if self.margin_home is None or abs(self.margin_home) < PICKEM_MARGIN:
            return None
        return self.home if self.margin_home > 0 else self.away

    @property
    def underdog(self) -> str | None:
        fav = self.favorite
        return None if fav is None else (self.away if fav == self.home else self.home)

    def summary(self) -> dict:
        sim = self.sim or {}
        return {
            "model": self.model,
            "generated_at": self.generated_at,
            "margin_home": self.margin_home,
            "win_prob_home": self.win_prob_home,
            "favorite": self.favorite,
            "market_spread": self.market_spread,
            "market_total": self.market_total,
            "sim_source": self.sim_source,
            "sim_median_home": sim.get("median_home"),
            "sim_median_away": sim.get("median_away"),
            "sim_modal": sim.get("modal"),
            "sim_total_p50": sim.get("total_p50"),
            "notes": self.notes,
        }


def _json(value):
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return None
    return value


def _offense(row: dict) -> dict | None:
    """The pregame simulation's team strengths (anchored EPA targets and
    run/pass tendencies), which the live-resume simulation reuses unchanged."""
    comp = _json(row.get("components")) or {}
    home, away = comp.get("home_offense") or {}, comp.get("away_offense") or {}
    if home.get("target_epa") is None or away.get("target_epa") is None:
        return None
    return {
        "home": {"target_epa": home["target_epa"], "pass_rate_oe": home.get("pass_rate_oe") or 0.0},
        "away": {"target_epa": away["target_epa"], "pass_rate_oe": away.get("pass_rate_oe") or 0.0},
        "wind_mph": comp.get("wind_mph") or 0.0,
    }


def _sim_view(row: dict, dist: dict) -> dict:
    return {
        "median_home": row.get("median_home_points"),
        "median_away": row.get("median_away_points"),
        "modal": [row.get("modal_home_points"), row.get("modal_away_points")],
        "total_p50": (dist.get("total") or {}).get("p50"),
        "pace": dist.get("pace"),
        "offense": _offense(row),
    }


# --- flags -----------------------------------------------------------------

def _tail(p: float) -> str | None:
    if p <= EXTREME or p >= 1 - EXTREME:
        return "extreme"
    if p <= NOTABLE or p >= 1 - NOTABLE:
        return "notable"
    return None


def evaluate(s: LiveState, pg: Pregame) -> dict:
    """Place the live game against its pregame expectations."""
    t = elapsed_minutes(s.period, s.clock_seconds, s.status, s.postseason)
    margin = s.home_score - s.away_score
    total = s.home_score + s.away_score
    out = {"elapsed": t, "flags": [], "total_percentile": None, "margin_percentile": None,
           "sim_total_median_now": None, "projected_total": None}

    fav, dog = pg.favorite, pg.underdog
    if dog and t > 0:
        dog_lead = margin if dog == pg.home else -margin
        if dog_lead > UNDERDOG_LEAD:
            level = "extreme" if dog_lead >= UNDERDOG_EXTREME_LEAD or t >= LATE_MINUTES else "notable"
            out["flags"].append({
                "code": "underdog_leading", "level": level,
                "message": f"{dog} leads by {dog_lead}; pregame had {fav} by {abs(pg.margin_home):.1f}",
            })

    pace = (pg.sim or {}).get("pace")
    if pace:
        tp = percentile(pace, "total", t, total)
        mp = percentile(pace, "margin", t, margin)
        now_median = quantile(pace, "total", t, 0.5)
        final_median = quantile(pace, "total", 60, 0.5)
        out.update(total_percentile=round(tp, 4), margin_percentile=round(mp, 4),
                   sim_total_median_now=now_median,
                   projected_total=round(total + max(final_median - now_median, 0), 1))
        if t >= MIN_ELAPSED_MINUTES:
            level = _tail(tp)
            if level:
                high = tp > 0.5
                share = (1 - tp) if high else tp
                out["flags"].append({
                    "code": "pace_high" if high else "pace_low", "level": level,
                    "message": (f"scoring pace {'high' if high else 'low'}: {total} pts after {t:.0f} min "
                                f"(simulations typically {now_median} by now, only {share:.1%} "
                                f"{'higher' if high else 'lower'}); on track for ~{out['projected_total']:.0f} "
                                f"vs pregame median {final_median}"
                                + (f", market {pg.market_total}" if pg.market_total else "")),
                })
            level = _tail(mp)
            if level:
                home_way = mp > 0.5
                share = (1 - mp) if home_way else mp
                lead = (f"{pg.home} +{margin}" if margin > 0 else
                        f"{pg.away} +{-margin}" if margin < 0 else "tied")
                expect = (f"pregame {fav} by {abs(pg.margin_home):.1f}" if fav else "pregame pick'em")
                out["flags"].append({
                    "code": "margin_home" if home_way else "margin_away", "level": level,
                    "message": (f"margin off-script: {lead} after {t:.0f} min; only {share:.1%} of "
                                f"simulations were this far {pg.home if home_way else pg.away}'s way "
                                f"by now ({expect})"),
                })
    return out


def new_alerts(seen: dict[str, str], flags: list[dict]) -> list[dict]:
    """Flags worth announcing: first appearance, or escalation from notable
    to extreme. A flag hovering around its threshold must not re-announce
    every time it dips back over, so a code stays announced for the game."""
    fresh = []
    for f in flags:
        if LEVEL_RANK[f["level"]] > LEVEL_RANK[seen.get(f["code"])]:
            fresh.append(f)
            seen[f["code"]] = f["level"]
    return fresh


# --- alert outputs ---------------------------------------------------------

TOAST_APP_ID = r"{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\WindowsPowerShell\v1.0\powershell.exe"


def toast(title: str, body: str) -> None:
    """Best-effort Windows desktop notification. Fire and forget: a toast
    that fails to show must never hold up or break the polling loop."""
    if os.name != "nt":
        return
    esc = lambda s: s.replace("'", "''")  # noqa: E731
    script = (
        "[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, "
        "ContentType = WindowsRuntime] > $null;"
        "$t = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent("
        "[Windows.UI.Notifications.ToastTemplateType]::ToastText02);"
        "$x = $t.GetElementsByTagName('text');"
        f"$x.Item(0).AppendChild($t.CreateTextNode('{esc(title)}')) > $null;"
        f"$x.Item(1).AppendChild($t.CreateTextNode('{esc(body)}')) > $null;"
        "[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("
        f"'{TOAST_APP_ID}').Show([Windows.UI.Notifications.ToastNotification]::new($t))"
    )
    try:
        subprocess.Popen(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except Exception:  # noqa: BLE001
        pass


# --- the tracker -----------------------------------------------------------

def _now() -> datetime:
    return datetime.now(timezone.utc)


class Tracker:
    def __init__(self, notify: bool = True, live_sims: int | None = None):
        self.store = db.get_store()
        self.fallback: db.Store | None = None
        self.ctx = self._load_context()
        self.index: dict[tuple[str, str], list[dict]] = {}
        for g in self.ctx.games:
            self.index.setdefault((g["home_team"], g["away_team"]), []).append(g)
        self.notify = notify
        self.sim_inputs = None
        self.live = None                     # LiveSimulator, built on first use
        self.live_sims = live_sims
        self.live_history: dict[str, list[dict]] = {}
        self.local_tables: set[str] = set()  # tables written to the local mirror this session
        self.cycle_seconds = 0.0
        self.finals_this_cycle = 0
        self.pregame: dict[str, Pregame] = {}
        self.seen_flags: dict[str, dict[str, str]] = {}
        self.history: dict[str, list[dict]] = {}
        self.latest: dict[str, dict] = {}
        self.bands: dict[str, dict] = {}
        LIVE_DIR.mkdir(parents=True, exist_ok=True)
        self.alerts: list[dict] = self._recent_alerts()
        self.live_seen: set[str] = set()
        self.finalized: set[str] = set()
        self.last_states: list[LiveState] = []
        self.failures = 0
        self.used_fallback = False

    def _load_context(self) -> FeatureContext:
        """Games, ratings and odds, read once at startup.

        Startup is the one read the polling loop can't absorb, so a transient
        database error (Supabase has returned 504s here) is retried with
        backoff. If the database stays down, the local SQLite mirror is used
        instead: its pregame data may be older, but a tracker running on
        slightly stale pregame numbers beats no tracker at all mid-game.
        """
        last: Exception | None = None
        for wait in STARTUP_RETRY_SECONDS:
            if wait:
                print(f"  [live] retrying startup read in {wait}s")
                time.sleep(wait)
            try:
                return FeatureContext(self.store, "nfl")
            except Exception as exc:  # noqa: BLE001
                last = exc
                print(f"  [warn] could not read pregame data from {self.store.backend}: "
                      f"{type(exc).__name__}: {str(exc)[:160]}")
        if self.store.backend == "sqlite":
            raise last
        print(f"\n  [warn] {self.store.backend} still unreachable. Reading pregame data from the local")
        print("         SQLite mirror for this session; it may be older than the hosted copy.\n")
        self.store = db.SqliteStore()
        return FeatureContext(self.store, "nfl")

    @staticmethod
    def _recent_alerts() -> list[dict]:
        """Alerts from earlier runs today, so a restarted tracker's page still
        shows what already fired (flags are not re-announced, see _load_history)."""
        cutoff = _now() - timedelta(hours=IDLE_EXIT_HOURS)
        out = []
        try:
            lines = ALERT_JSONL.read_text(encoding="utf-8").splitlines()
        except OSError:
            return out
        for line in lines:
            try:
                alert = json.loads(line)
            except json.JSONDecodeError:
                continue
            at = parse_dt(alert.get("at"))
            if at and at > cutoff:
                out.append(alert)
        return out

    # --- matching and pregame -------------------------------------------

    def match(self, s: LiveState) -> dict | None:
        candidates = self.index.get((s.home, s.away), [])
        if s.start is None:
            return candidates[0] if len(candidates) == 1 else None
        best, gap = None, None
        for g in candidates:
            k = parse_dt(g.get("kickoff_time"))
            if k is None:
                continue
            d = abs((k - s.start).total_seconds())
            if gap is None or d < gap:
                best, gap = g, d
        return best if gap is not None and gap <= 36 * 3600 else None

    def load_pregame(self, game: dict) -> Pregame:
        gid = game["game_id"]
        if gid in self.pregame:
            return self.pregame[gid]
        pg = Pregame(gid, game["home_team"], game["away_team"], parse_dt(game.get("kickoff_time")))
        try:
            rows = {r["model_version"]: r for r in self.store.select("predictions", {"game_id": gid})}
            pred = rows.get(config.MODEL_VERSION)
            if pred:
                pg.margin_home = pred.get("model_margin_home")
                pg.win_prob_home = pred.get("model_win_prob_home")
                pg.model = pred.get("model_version")
                pg.generated_at = pred.get("generated_at")
                pg.market_spread = pred.get("market_spread")
                made = parse_dt(pg.generated_at)
                if made and pg.kickoff and made > pg.kickoff:
                    pg.notes.append("prediction was regenerated after kickoff")
            else:
                pg.notes.append(f"no stored {config.MODEL_VERSION} prediction")
        except Exception as exc:  # noqa: BLE001
            pg.notes.append(f"predictions unavailable ({type(exc).__name__})")
        _spread, pg.market_total, _src, _n = self.ctx.market(gid)
        if pg.market_spread is None:
            pg.market_spread = _spread
        pg.sim, pg.sim_source = self._simulation(game, pg)
        if pg.sim is None:
            pg.notes.append("no simulation: pace and margin flags are off for this game")
        self.pregame[gid] = pg
        if pg.sim and pg.sim.get("pace"):
            self.bands[gid] = bands(pg.sim["pace"])
        self._load_history(gid)
        return pg

    def _simulation(self, game: dict, pg: Pregame):
        gid = game["game_id"]
        # Hosted store first, then the local mirror, where simulate_nfl writes
        # while the hosted table is missing.
        rows = self._select_any("game_simulations", {"game_id": gid})
        for row in sorted(rows, key=lambda r: str(r.get("generated_at")), reverse=True):
            dist = _json(row.get("distributions")) or {}
            if dist.get("pace"):
                return _sim_view(row, dist), f"stored {row.get('sim_version')} ({row.get('generated_at')})"

        # No stored simulation with a pace record: build one now. It is pinned
        # to the stored pregame prediction, so the centre is still pregame.
        try:
            from .simulate_nfl import load_inputs, simulate_one

            if self.sim_inputs is None:
                print("  [live] no stored simulation; loading the simulator (once per session)")
                self.sim_inputs = load_inputs(int(game["season"]))
            label = f"{pg.model} @ {pg.generated_at}" if pg.model else None
            row = simulate_one(game, self.ctx, self.sim_inputs, anchor=pg.margin_home, anchor_label=label)
            if row:
                return _sim_view(row, row["distributions"]), "computed at first poll, anchored to the stored pregame prediction"
        except Exception as exc:  # noqa: BLE001
            print(f"  [warn] simulation for {gid} failed: {type(exc).__name__}: {exc}")
        return None, None

    def _load_history(self, gid: str) -> None:
        """Earlier snapshots of this game, so a restarted tracker keeps the
        trajectory and does not re-announce flags it already raised."""
        rows = self._select_any("live_tracking", {"game_id": gid})
        rows.sort(key=lambda r: str(r["polled_at"]))
        self.history[gid] = [
            {"t": r.get("elapsed_minutes"), "home": r.get("home_score"), "away": r.get("away_score"),
             "at": r.get("polled_at")}
            for r in rows if r.get("elapsed_minutes") is not None
        ]
        if rows:
            seen = self.seen_flags.setdefault(gid, {})
            for f in _json(rows[-1].get("flags")) or []:
                new_alerts(seen, [f])

        espn = {str(r["polled_at"]): r.get("espn_home_win_prob") for r in rows}
        from .live_sim import LIVE_SIM_VERSION

        sims = sorted((r for r in self._select_any("live_simulations", {"game_id": gid})
                       if r.get("sim_version") == LIVE_SIM_VERSION),   # earlier versions are superseded
                      key=lambda r: str(r["polled_at"]))
        self.live_history[gid] = [
            {"t": r.get("elapsed_minutes"), "at": r.get("polled_at"), "wp_home": r.get("home_win_prob"),
             "espn_wp": espn.get(str(r["polled_at"])), "margin_proj": r.get("mean_margin_home"),
             "margin_lo": r.get("margin_80_low"), "margin_hi": r.get("margin_80_high"),
             "total_median": r.get("total_median")}
            for r in sims if r.get("elapsed_minutes") is not None
        ]

    def _select_any(self, table: str, where: dict) -> list[dict]:
        """Rows from the hosted store, else from the local mirror, where a
        session whose hosted table was missing will have written them."""
        try:
            rows = self.store.select(table, where)
            if rows or self.store.backend == "sqlite":
                return rows
        except Exception:  # noqa: BLE001 - table not created yet
            if self.store.backend == "sqlite":
                return []
        try:
            if self.fallback is None:
                self.fallback = db.SqliteStore()
            return self.fallback.select(table, where)
        except Exception:  # noqa: BLE001
            return []

    # --- one cycle ------------------------------------------------------

    def cycle(self) -> None:
        payload = _espn("scoreboard")
        states, skipped = parse_scoreboard(payload)
        if payload is None or (not states and skipped):
            # site.api is down or blocking; rebuild the same shape from the
            # core API rather than lose the cycle entirely.
            payload = core_scoreboard()
            states, skipped = parse_scoreboard(payload)
            if states:
                if not self.used_fallback:
                    print(f"[{_now():%H:%M:%S}Z] site.api unavailable; "
                          f"falling back to the core API ({len(states)} game(s))")
                self.used_fallback = True
        elif self.used_fallback:
            print(f"[{_now():%H:%M:%S}Z] site.api is answering again; leaving the core-API fallback")
            self.used_fallback = False
        if payload is None or (not states and skipped):
            self.failures += 1
            print(f"[{_now():%H:%M:%S}Z] scoreboard unavailable (failure {self.failures}); "
                  "skipping this cycle")
            if self.failures == FAILED_CYCLES_WARNING:
                self._announce(None, f"ESPN unreachable for {self.failures} polls in a row; still retrying",
                               level="notable", toast_title="Live tracker: ESPN unreachable")
            return
        self.failures = 0
        self.last_states = states
        if skipped:
            print(f"  [warn] {skipped} scoreboard event(s) malformed, skipped")

        rows, live_rows = [], []
        started = time.perf_counter()
        self.finals_this_cycle = 0
        for s in states:
            try:
                row, live_row = self._process(s)
                if row:
                    rows.append(row)
                if live_row:
                    live_rows.append(live_row)
            except Exception as exc:  # noqa: BLE001 - one odd game must not stop the rest
                print(f"  [warn] {s.away} @ {s.home}: {type(exc).__name__}: {exc}")
                traceback.print_exc(limit=2)
        self.cycle_seconds = time.perf_counter() - started

        self._write("live_tracking", rows)
        self._write("live_simulations", live_rows)
        self._export()
        if self.finals_this_cycle:
            # A game just ended: refresh the dashboard's game view so its
            # actual result sits beside the projections without a manual export.
            try:
                from .export_sims import run as export_sims

                export_sims(quiet=True)
            except Exception as exc:  # noqa: BLE001
                print(f"  [warn] could not refresh sims.json: {type(exc).__name__}: {exc}")
        self._status_line(states)

    def _process(self, s: LiveState) -> tuple[dict | None, dict | None]:
        """(live_tracking row, live_simulations row) for one game."""
        if s.state == "pre":
            return None, None
        game = self.match(s)
        if game is None:
            if s.state == "in":
                print(f"  [warn] ESPN game {s.away} @ {s.home} ({s.espn_id}) matches no game in the games table")
            return None, None
        gid = game["game_id"]
        if s.state == "post" and (gid not in self.live_seen or gid in self.finalized):
            return None, None    # finished before this session, or already closed out

        pg = self.load_pregame(game)
        scoring = path = summary = None
        if s.state == "in":
            self.live_seen.add(gid)
            summary = _espn("summary", {"event": s.espn_id})
            scoring = recent_scoring(summary)
            path = scoring_path(summary, s.postseason)
        previous = self.latest.get(gid) or {}
        if scoring is None:      # summary failed, or the game is over: keep what we had
            scoring = previous.get("recent_scoring") or []
        if path is None:
            path = previous.get("score_path") or []

        ev = evaluate(s, pg)
        polled_at = db.utcnow()
        live_row = live_view = None
        if s.state == "in":
            live_row, live_view = self._live_simulation(s, game, pg, summary, ev, polled_at)
        fresh = []
        if s.state == "in":
            fresh = new_alerts(self.seen_flags.setdefault(gid, {}), ev["flags"])
            for f in fresh:
                self._announce(s, f["message"], f["level"])
        else:
            self.finalized.add(gid)
            self.finals_this_cycle += 1
            self._final_line(s, pg)

        level = max((f["level"] for f in ev["flags"]), key=LEVEL_RANK.get, default=None)
        self.history.setdefault(gid, []).append(
            {"t": ev["elapsed"], "home": s.home_score, "away": s.away_score, "at": polled_at})
        self.latest[gid] = {
            "game_id": gid, "espn_id": s.espn_id, "home": s.home, "away": s.away,
            "kickoff": game.get("kickoff_time"), "state": s.state, "detail": s.detail,
            "period": s.period, "display_clock": s.display_clock, "elapsed": ev["elapsed"],
            "home_score": s.home_score, "away_score": s.away_score, "possession": s.possession,
            "down_distance": s.down_distance, "red_zone": s.red_zone, "espn_home_wp": s.espn_home_wp,
            "flags": ev["flags"], "flag_level": level,
            "total_percentile": ev["total_percentile"], "margin_percentile": ev["margin_percentile"],
            "sim_total_median_now": ev["sim_total_median_now"], "projected_total": ev["projected_total"],
            "recent_scoring": scoring, "score_path": path, "pregame": pg.summary(),
            "trajectory": self.history[gid], "bands": self.bands.get(gid),
            "live_sim": live_view, "live_history": self.live_history.get(gid, []),
            "polled_at": polled_at,
        }
        row = {
            "game_id": gid, "polled_at": polled_at, "espn_event_id": s.espn_id, "state": s.state,
            "period": s.period, "display_clock": s.display_clock, "elapsed_minutes": ev["elapsed"],
            "home_team": s.home, "away_team": s.away,
            "home_score": s.home_score, "away_score": s.away_score,
            "possession": s.possession, "down_distance": s.down_distance, "is_red_zone": s.red_zone,
            "espn_home_win_prob": s.espn_home_wp,
            "predicted_margin_home": pg.margin_home, "predicted_winner": pg.favorite,
            "sim_median_home": (pg.sim or {}).get("median_home"),
            "sim_median_away": (pg.sim or {}).get("median_away"),
            "sim_total_median_now": ev["sim_total_median_now"],
            "total_percentile": ev["total_percentile"], "margin_percentile": ev["margin_percentile"],
            "projected_total": ev["projected_total"],
            "flag_level": level, "flags": ev["flags"], "alerted": bool(fresh),
            "recent_scoring": scoring,
            "pregame": {k: v for k, v in pg.summary().items() if v not in (None, [])},
        }
        return row, live_row

    def _live_simulation(self, s: LiveState, game: dict, pg: Pregame, summary, ev: dict,
                         polled_at: str) -> tuple[dict | None, dict | None]:
        """Re-simulate the rest of this game from where it stands now.

        The same engine and the same (pregame, anchored) team strengths as the
        pregame simulation; only the starting state is live. A failure costs
        this game's live projection for this poll and nothing else.
        """
        offense = (pg.sim or {}).get("offense")
        if offense is None:
            return None, None
        elapsed = ev["elapsed"] * 60
        if s.period <= 4 and elapsed >= 3600 and s.home_score != s.away_score:
            return None, None            # regulation is over and someone won
        gid = game["game_id"]
        try:
            from .live_sim import LIVE_SIM_VERSION, LiveSimulator, describe, live_start

            if self.live is None:
                if self.sim_inputs is None:
                    from .simulate_nfl import load_inputs

                    print("  [live] loading the simulator for live projections (once per session)")
                    self.sim_inputs = load_inputs(int(game["season"]))
                self.live = LiveSimulator(self.sim_inputs.tables, self.sim_inputs.roles,
                                          self.ctx.injuries, n=self.live_sims,
                                          scramble_rates=self.sim_inputs.scramble_rates,
                                          scramble_league=self.sim_inputs.scramble_league)
            side_by_id = {s.home_id: 0, s.away_id: 1}
            halftime = s.status == "STATUS_HALFTIME" or (s.period == 2 and s.clock_seconds <= 0)
            start, source = live_start(elapsed, halftime, s.home_score, s.away_score,
                                       s.situation, summary, side_by_id)
            fields, extra = self.live.run(game_id=gid, home=s.home, away=s.away, offense=offense,
                                          start=start, summary=summary, side_by_id=side_by_id)
        except Exception as exc:  # noqa: BLE001
            print(f"  [warn] live simulation for {gid} failed: {type(exc).__name__}: {exc}")
            traceback.print_exc(limit=2)
            return None, None

        start_state = {"description": describe(start, s.home, s.away), "source": source,
                       **{k: v for k, v in vars(start).items() if v is not None}}
        row = {
            "game_id": gid, "polled_at": polled_at, "sim_version": LIVE_SIM_VERSION,
            "elapsed_minutes": ev["elapsed"], "home_team": s.home, "away_team": s.away,
            "home_score": s.home_score, "away_score": s.away_score, **fields,
            "pregame_margin_home": pg.margin_home, "pregame_win_prob_home": pg.win_prob_home,
            "start_state": start_state,
        }
        self.live_history.setdefault(gid, []).append({
            "t": ev["elapsed"], "at": polled_at, "wp_home": fields["home_win_prob"],
            "espn_wp": s.espn_home_wp, "margin_proj": fields["mean_margin_home"],
            "margin_lo": fields["margin_80_low"], "margin_hi": fields["margin_80_high"],
            "total_median": fields["total_median"],
        })
        regulation = 70 if s.period >= 5 else 60
        view = {**row, **extra, "minutes_left": round(max(regulation - ev["elapsed"], 0.0), 1)}
        return row, view

    # --- outputs --------------------------------------------------------

    def _announce(self, s: LiveState | None, message: str, level: str, toast_title: str | None = None):
        stamp = _now()
        game = f"{s.away} {s.away_score}-{s.home_score} {s.home} ({s.detail})" if s else "tracker"
        line = f"[{stamp:%Y-%m-%d %H:%M:%S}Z] {level.upper():8} {game}: {message}"
        bar = "!" * 78 if level == "extreme" else "*" * 78
        print(f"\n{bar}\n{line}\n{bar}")
        entry = {"at": stamp.isoformat(), "level": level, "game": game, "message": message,
                 "game_id": getattr(s, "espn_id", None)}
        self.alerts.append(entry)
        try:
            with open(ALERT_LOG, "a", encoding="utf-8") as fh:
                fh.write(line + "\n")
            with open(ALERT_JSONL, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(entry) + "\n")
        except OSError as exc:
            print(f"  [warn] could not append to the alert log: {exc}")
        if self.notify:
            toast(toast_title or f"{'EXTREME' if level == 'extreme' else 'Watch'}: {game}", message)

    def _final_line(self, s: LiveState, pg: Pregame) -> None:
        sim = pg.sim or {}
        expect = (f"pregame {pg.favorite} by {abs(pg.margin_home):.1f}" if pg.favorite
                  else "pregame pick'em")
        if sim.get("median_home") is not None:
            expect += f", simulated median {pg.away} {sim['median_away']:.0f}-{sim['median_home']:.0f} {pg.home}"
        print(f"  FINAL  {s.away} {s.away_score}-{s.home_score} {s.home}   ({expect})")

    def _write(self, table: str, rows: list[dict]) -> None:
        """Write to the configured store; a table it lacks goes to the local
        SQLite mirror for the rest of the session instead of being lost."""
        if not rows:
            return
        if table not in self.local_tables:
            try:
                self.store.upsert(table, rows)
                return
            except Exception as exc:  # noqa: BLE001
                if self.store.backend == "sqlite":
                    print(f"  [warn] {table} write failed ({type(exc).__name__}); this cycle is in live.json only")
                    return
                print(f"\n  [warn] cannot write {table} to {self.store.backend} ({type(exc).__name__}).")
                print("         It goes to the local SQLite mirror for the rest of this session.")
                print("         Paste db/PASTE_INTO_SUPABASE.sql into the Supabase SQL Editor to create it.\n")
                self.local_tables.add(table)
        try:
            if self.fallback is None:
                self.fallback = db.SqliteStore()
            self.fallback.upsert(table, rows)
        except Exception as exc:  # noqa: BLE001
            print(f"  [warn] local {table} write failed too ({exc}); this cycle is in live.json only")

    def storage_label(self) -> str:
        if self.local_tables:
            return (f"{self.store.backend}, with {', '.join(sorted(self.local_tables))} in local sqlite "
                    "(table missing upstream)")
        return self.store.backend

    def _export(self) -> None:
        now = _now()
        upcoming = [
            {"home": s.home, "away": s.away, "kickoff": s.start.isoformat() if s.start else None,
             "detail": s.detail}
            for s in self.last_states
            if s.state == "pre" and s.start and s.start - now <= timedelta(hours=IDLE_EXIT_HOURS)
        ]
        payload = {
            "generated_at": now.isoformat(),
            "poll_seconds": POLL_SECONDS,
            "storage": self.storage_label(),
            "thresholds": {"notable": NOTABLE, "extreme": EXTREME, "underdog_lead": UNDERDOG_LEAD,
                           "min_elapsed_minutes": MIN_ELAPSED_MINUTES},
            "games": sorted(self.latest.values(),
                            key=lambda g: (g["state"] != "in", -LEVEL_RANK[g["flag_level"]], g["kickoff"] or "")),
            "upcoming": sorted(upcoming, key=lambda u: u["kickoff"] or ""),
            "alerts": self.alerts[-MAX_ALERTS_EXPORTED:][::-1],
        }
        try:
            LIVE_JSON.write_text(json.dumps(payload, default=str), encoding="utf-8")
            if PUBLIC_LIVE_JSON.parent.exists():
                shutil.copy(LIVE_JSON, PUBLIC_LIVE_JSON)
        except OSError as exc:
            print(f"  [warn] could not write {LIVE_JSON}: {exc}")

    def _status_line(self, states: list[LiveState]) -> None:
        live = [g for g in self.latest.values() if g["state"] == "in"]
        parts = []
        for g in sorted(live, key=lambda g: g["kickoff"] or ""):
            tp, mp = g["total_percentile"], g["margin_percentile"]
            pct = (f" pace p{tp * 100:.0f} margin p{mp * 100:.0f}" if tp is not None else "")
            mark = {"extreme": " !!", "notable": " !"}.get(g["flag_level"], "")
            ls = g.get("live_sim")
            now = f" | now {g['home']} {ls['home_win_prob']:.0%}" if ls else ""
            parts.append(f"{g['away']} {g['away_score']}-{g['home_score']} {g['home']} {g['detail']}{pct}{now}{mark}")
        took = f" ({self.cycle_seconds:.1f}s)" if live else ""
        print(f"[{_now():%H:%M:%S}Z] {len(live)} live{took}" + ("  |  " + "  |  ".join(parts) if parts else ""))

    def next_sleep(self, interval: float) -> float | None:
        """Seconds to the next poll, or None when there is nothing left to do."""
        if self.failures or any(s.state == "in" for s in self.last_states):
            return interval + random.uniform(-POLL_JITTER, POLL_JITTER)
        now = _now()
        kickoffs = [s.start for s in self.last_states if s.state == "pre" and s.start
                    and s.start - now <= timedelta(hours=IDLE_EXIT_HOURS)]
        if not kickoffs:
            return None
        wait = (min(kickoffs) - now).total_seconds()
        return max(interval, min(wait, MAX_IDLE_SLEEP))

    def close(self) -> None:
        for store in (self.store, self.fallback):
            try:
                if store is not None:
                    store.close()
            except Exception:  # noqa: BLE001
                pass


def run(interval: float = POLL_SECONDS, once: bool = False, notify: bool = True,
        live_sims: int | None = None) -> None:
    # Line-buffered, so alerts reach a redirected log (or a scheduler's
    # capture) as they happen rather than when a block buffer fills.
    try:
        sys.stdout.reconfigure(line_buffering=True)
    except (AttributeError, ValueError):
        pass
    tracker = Tracker(notify=notify, live_sims=live_sims)
    print(f"[live] tracking NFL games | poll every ~{interval:.0f}s | storage {tracker.store.backend}"
          f" | alerts -> console, {ALERT_LOG}{', desktop' if notify else ''} | page: dashboard /live.html")
    try:
        while True:
            try:
                tracker.cycle()
            except Exception as exc:  # noqa: BLE001 - the loop itself must survive anything
                tracker.failures += 1
                print(f"  [warn] cycle failed: {type(exc).__name__}: {exc}")
                traceback.print_exc(limit=3)
            if once:
                break
            wait = tracker.next_sleep(interval)
            if wait is None:
                print(f"[live] nothing in progress and no kickoff within {IDLE_EXIT_HOURS}h; done")
                break
            if not any(s.state == "in" for s in tracker.last_states) and not tracker.failures:
                resume = _now() + timedelta(seconds=wait)
                print(f"[live] no game in progress; next check {resume:%H:%M}Z")
            time.sleep(wait)
    except KeyboardInterrupt:
        print("\n[live] stopped")
    finally:
        tracker.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Live NFL in-game tracking.")
    parser.add_argument("--interval", type=float, default=POLL_SECONDS, help="seconds between polls")
    parser.add_argument("--once", action="store_true", help="one cycle, then exit")
    parser.add_argument("--no-notify", action="store_true", help="no desktop notifications")
    parser.add_argument("--live-sims", type=int, help="live-resume simulations per game per poll (default 10,000)")
    args = parser.parse_args()
    run(args.interval, args.once, notify=not args.no_notify, live_sims=args.live_sims)
