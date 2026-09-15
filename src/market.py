"""Market probabilities: devigging, blending with the model, and the edge test.

Stage 1 of nfl-modeling-research.md. Three rules replace "flag when the model's
number is 2+ points from the market's":

1. Compare against the market's VIG-FREE probability. Taking the margin off
   proportionally ("equal margin") is the crude method: books load more of
   their margin onto longshots, so it overstates the longshot's chance. Shin,
   odds-ratio and logarithmic devigging all correct for that; Shin is the
   default. On a -110/-110 spread every method gives 50/50; they differ once
   the two prices differ (-105/-115, and every moneyline).
2. BLEND, don't compare. The NFL closing line is the sharpest public estimate
   there is, so it is the prior. The model's probability is combined with it
   in log-odds space with a small weight on the model. The weight should only
   rise once the model's picks show positive closing line value (src/clv.py).
3. Flag only when the blended probability beats the price actually on offer,
   vig included, by a calibration-error buffer.

Probabilities here are for the home side covering unless a name says
otherwise. Spreads are home-team lines (negative = home favoured).
"""

from __future__ import annotations

import math
from functools import lru_cache
from statistics import NormalDist, median

from . import config
from .features import MARGIN_SIGMA, normal_cdf

ASSUMED_PRICE = -110          # a line stored without its price
SHARP_BOOK = "pinnacle"       # used on its own when present (ODDS_BOOKMAKERS)
DEVIG_METHODS = ("shin", "odds_ratio", "log", "multiplicative")


# --- prices -----------------------------------------------------------------

def implied(price: float) -> float:
    """Raw implied probability of an American price, vig included."""
    price = float(price)
    return 100.0 / (price + 100.0) if price > 0 else -price / (-price + 100.0)


def to_american(prob: float) -> int:
    prob = min(max(prob, 1e-6), 1 - 1e-6)
    return round(-100 * prob / (1 - prob)) if prob >= 0.5 else round(100 * (1 - prob) / prob)


def _bisect(f, lo: float, hi: float, iters: int = 200) -> float:
    """Root of f on [lo, hi], where f(lo) > 0 > f(hi)."""
    for _ in range(iters):
        mid = (lo + hi) / 2
        if f(mid) > 0:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def devig(prices: list[float], method: str | None = None) -> list[float]:
    """Vig-free probabilities for one market's outcomes (two for a spread)."""
    method = method or config.DEVIG_METHOD
    q = [implied(p) for p in prices]
    total = sum(q)
    if total <= 1.0 or method == "multiplicative":
        return [x / total for x in q]
    if method == "odds_ratio":
        # Fair odds = raw odds / c for one constant c (Cheung, 2015).
        c = _bisect(lambda c: sum(x / (x + c * (1 - x)) for x in q) - 1, 1.0, 100.0)
        return [x / (x + c * (1 - x)) for x in q]
    if method == "log":
        # Logarithmic / power method: p = q^k.
        k = _bisect(lambda k: sum(x ** k for x in q) - 1, 1.0, 50.0)
        return [x ** k for x in q]
    if method == "shin":
        # Shin (1993): z is the share of money from insiders the book prices
        # against; p_i = (sqrt(z^2 + 4(1-z) q_i^2 / S) - z) / (2(1-z)).
        def probs(z):
            return [(math.sqrt(z * z + 4 * (1 - z) * x * x / total) - z) / (2 * (1 - z)) for x in q]
        z = _bisect(lambda z: sum(probs(z)) - 1, 0.0, 0.5)
        return probs(z)
    raise ValueError(f"unknown devig method {method!r}; use one of {DEVIG_METHODS}")


# --- blending ---------------------------------------------------------------

def logit(p: float) -> float:
    p = min(max(p, 1e-9), 1 - 1e-9)
    return math.log(p / (1 - p))


def expit(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


def blend(p_model: float, p_market: float, weight: float) -> float:
    """Model and market combined in log-odds space; weight is the model's share."""
    return expit(weight * logit(p_model) + (1 - weight) * logit(p_market))


# --- moving a probability between lines ------------------------------------

class MarginTable:
    """How final margins actually fall near a given spread.

    Needed to compare a probability quoted at one line with another line (a
    book at -2.5 against the consensus -2, or the bet's line against the
    close). A half point is not a fixed amount of probability in football: it
    is worth far more across 3 or 7, where games land, than across 5, and a
    normal curve cannot see that. The table is the historical margins of games
    with a similar closing spread, from the training sets, blended lightly
    with a normal curve so no margin has zero probability.
    """

    WINDOW = {"nfl": 1.0, "ncaaf": 1.5}
    MIN_GAMES = 250
    SMOOTH = 0.1

    def __init__(self, sport: str, spreads: list[float] | None = None,
                 margins: list[int] | None = None, smooth: float | None = None):
        self.sport = sport
        self.sigma = MARGIN_SIGMA.get(sport, 14.0)
        self.smooth = self.SMOOTH if smooth is None else smooth
        if spreads is None:
            spreads, margins = self._load(sport)
        self.data = sorted(zip(spreads or [], margins or []))
        self._cache: dict[float, dict[int, float]] = {}

    @staticmethod
    def _load(sport: str) -> tuple[list[float], list[int]]:
        path = config.DATA_DIR / f"training_{sport}.csv"
        if not path.exists():
            return [], []
        import csv

        spreads, margins = [], []
        with open(path, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                try:
                    spreads.append(float(row["market_spread"]))
                    margins.append(int(round(float(row["target_margin"]))))
                except (TypeError, ValueError, KeyError):
                    continue
        return spreads, margins

    def pmf(self, near: float) -> dict[int, float]:
        near = round(near * 2) / 2
        if near in self._cache:
            return self._cache[near]
        window = self.WINDOW.get(self.sport, 1.5)
        chosen: list[int] = []
        while self.data and len(chosen) < self.MIN_GAMES and window <= 30:
            chosen = [m for s, m in self.data if abs(s - near) <= window]
            window *= 1.5
        empirical: dict[int, float] = {}
        for m in chosen:
            empirical[m] = empirical.get(m, 0.0) + 1.0 / len(chosen)
        smooth = self.smooth if chosen else 1.0
        centre, out = -near, {}
        for m in range(int(centre - 6 * self.sigma) - 1, int(centre + 6 * self.sigma) + 2):
            normal = normal_cdf((m + 0.5 - centre) / self.sigma) - normal_cdf((m - 0.5 - centre) / self.sigma)
            out[m] = (1 - smooth) * empirical.get(m, 0.0) + smooth * normal
        for m, p in empirical.items():
            out.setdefault(m, (1 - smooth) * p)
        self._cache[near] = out
        return out

    def cover(self, line: float, near: float | None = None) -> float:
        """P(home covers `line`), pushes excluded, for games priced near `near`."""
        pmf = self.pmf(line if near is None else near)
        win = sum(p for m, p in pmf.items() if m + line > 0)
        push = sum(p for m, p in pmf.items() if m + line == 0)
        return win / (1 - push) if push < 1 else 0.5

    def move(self, p: float, from_line: float, to_line: float, near: float | None = None) -> float:
        """A home-cover probability quoted at from_line, restated at to_line."""
        if from_line == to_line:
            return p
        near = to_line if near is None else near
        return expit(logit(p) + logit(self.cover(to_line, near)) - logit(self.cover(from_line, near)))


@lru_cache(maxsize=4)
def margin_table(sport: str) -> MarginTable:
    return MarginTable(sport)


# --- the market's fair probability ------------------------------------------

def _priced(books: list[dict]) -> list[dict]:
    return [b for b in books if b.get("spread") is not None
            and b.get("spread_price_home") is not None and b.get("spread_price_away") is not None]


def market_cover_prob(line: float, books: list[dict], sport: str,
                      method: str | None = None) -> tuple[float, dict]:
    """The market's vig-free P(home covers `line`).

    Each book is devigged at its own line and restated at `line`; the sharp
    book is used alone when present, otherwise the median across books. With
    no prices stored at all, the line is taken at -110 both ways, which is
    50/50 at the market's own line by construction.
    """
    table = margin_table(sport)
    probs = []
    for b in _priced(books):
        p = devig([b["spread_price_home"], b["spread_price_away"]], method)[0]
        probs.append((str(b.get("book", "")), table.move(p, float(b["spread"]), line)))
    sharp = [p for book, p in probs if book.endswith(SHARP_BOOK)]
    if sharp:
        return sharp[0], {"source": SHARP_BOOK, "books": len(probs)}
    if probs:
        return median(p for _, p in probs), {"source": "books", "books": len(probs)}
    return 0.5, {"source": "assumed_-110", "books": 0}


def side_price(line: float, books: list[dict], side: str) -> float:
    """The going price for one side at exactly `line` (median across books)."""
    key = "spread_price_home" if side == "home" else "spread_price_away"
    prices = [b[key] for b in _priced(books) if float(b["spread"]) == line]
    return median(prices) if prices else ASSUMED_PRICE


def market_win_prob(books: list[dict], method: str | None = None) -> float | None:
    """The market's vig-free home win probability from moneylines."""
    probs = [devig([b["moneyline_home"], b["moneyline_away"]], method)[0]
             for b in books if b.get("moneyline_home") and b.get("moneyline_away")]
    return median(probs) if probs else None


# --- the edge test ----------------------------------------------------------

def spread_edge(margin: float, sigma: float, line: float, books: list[dict], sport: str,
                weight: float | None = None, buffer: float | None = None,
                method: str | None = None) -> dict:
    """Blend the model's cover probability with the market's and test the lean.

    The lean is the side the blend moves toward. It is flagged only when the
    blended probability of that side covering exceeds the break-even of the
    price on offer (52.4% at -110) by `buffer`.
    """
    weight = config.MODEL_MARKET_WEIGHT if weight is None else weight
    buffer = config.EDGE_BUFFER if buffer is None else buffer
    method = method or config.DEVIG_METHOD

    p_model = normal_cdf((margin + line) / sigma)
    p_market, info = market_cover_prob(line, books, sport, method)
    p_blend = blend(p_model, p_market, weight)
    side = "home" if p_blend > p_market else ("away" if p_blend < p_market else None)

    out = {
        "line": line, "sigma": round(sigma, 2), "weight": weight, "buffer": buffer,
        "devig": method, "market_source": info["source"], "priced_books": info["books"],
        "p_model_home": round(p_model, 4), "p_market_home": round(p_market, 4),
        "p_blend_home": round(p_blend, 4), "side": side, "flag": False,
    }
    if side is None:
        return out
    own = (lambda p: p) if side == "home" else (lambda p: 1 - p)
    price = side_price(line, books, side)
    breakeven = implied(price)
    out.update({
        "price": price,
        "breakeven": round(breakeven, 4),
        "p_side_market": round(own(p_market), 4),
        "p_side_blend": round(own(p_blend), 4),
        "edge_vs_market": round(own(p_blend) - own(p_market), 4),
        "edge_pp": round(own(p_blend) - breakeven, 4),
        "flag": own(p_blend) - breakeven >= buffer,
    })
    return out


def points_to_flag(sigma: float, weight: float | None = None, buffer: float | None = None,
                   price: float = ASSUMED_PRICE) -> float:
    """How many points the model must disagree with a 50/50 line to be flagged."""
    weight = config.MODEL_MARKET_WEIGHT if weight is None else weight
    buffer = config.EDGE_BUFFER if buffer is None else buffer
    if weight <= 0:
        return math.inf
    target = implied(price) + buffer
    if target >= 1:
        return math.inf
    p_model = expit(logit(target) / weight)
    return NormalDist().inv_cdf(min(p_model, 1 - 1e-12)) * sigma
