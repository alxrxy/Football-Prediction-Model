-- Football Predictor — Supabase (Postgres) schema
-- Paste this whole file into the Supabase SQL Editor and hit Run.
-- Safe to re-run: everything is IF NOT EXISTS.
--
-- Design note (architecture §2): raw pulls and derived features stay separate.
-- Every ingested table carries pulled_at so a bad upstream pull is identifiable
-- and reversible without touching derived rows.

-- ---------------------------------------------------------------------------
-- venues: stadium lookup. Feeds both weather and travel-distance features.
-- ---------------------------------------------------------------------------
create table if not exists venues (
    venue_id     text primary key,
    sport        text not null,
    name         text,
    city         text,
    state        text,
    latitude     double precision,
    longitude    double precision,
    elevation_m  double precision,
    is_dome      boolean default false,
    capacity     integer,
    timezone     text,
    pulled_at    timestamptz not null default now()
);

-- ---------------------------------------------------------------------------
-- games: one row per scheduled game, both sports.
-- ---------------------------------------------------------------------------
create table if not exists games (
    game_id          text primary key,
    sport            text not null,           -- 'ncaaf' | 'nfl'
    season           integer not null,
    week             integer,
    season_type      text,                    -- 'regular' | 'postseason'
    home_team        text not null,
    away_team        text not null,
    home_conference  text,
    away_conference  text,
    kickoff_time     timestamptz,
    venue            text,
    venue_id         text,
    is_neutral_site  boolean default false,
    is_conference    boolean default false,
    home_points      integer,                 -- filled in post-game for scoring
    away_points      integer,
    completed        boolean default false,
    home_rest_days   double precision,        -- supplied by nflverse for NFL
    away_rest_days   double precision,
    pulled_at        timestamptz not null default now()
);
create index if not exists games_kickoff_idx on games (sport, kickoff_time);
create index if not exists games_week_idx    on games (sport, season, week);

-- ---------------------------------------------------------------------------
-- team_ratings: power ratings by week. NCAAF from CFBD SP+/Elo,
-- NFL from computed EPA-based Elo (step 5).
-- ---------------------------------------------------------------------------
create table if not exists team_ratings (
    team          text not null,
    sport         text not null,
    season        integer not null,
    week          integer not null,
    conference    text,
    -- power_rating is the sport-neutral baseline: a team's strength expressed
    -- in points above average. NCAAF fills it from SP+, NFL from the
    -- EPA-derived rating. The modeling layer reads this, not the raw columns.
    power_rating  double precision,
    elo           double precision,
    sp_plus       double precision,           -- net SP+, already in points
    sp_plus_off   double precision,
    sp_plus_def   double precision,
    fpi           double precision,
    off_epa       double precision,
    def_epa       double precision,
    pulled_at     timestamptz not null default now(),
    primary key (team, sport, season, week)
);

-- ---------------------------------------------------------------------------
-- injuries: weekly report. practice_trend drives play probability (§4).
-- Populated in step 6 (ESPN / nflverse).
-- ---------------------------------------------------------------------------
create table if not exists injuries (
    player          text not null,
    team            text not null,
    sport           text not null,
    season          integer not null,
    week            integer not null,
    position        text,
    status          text,                     -- out|doubtful|questionable|probable
    practice_trend  text,                     -- dnp|limited|full|dnp->limited etc
    position_weight double precision,
    play_probability double precision,
    pulled_at       timestamptz not null default now(),
    primary key (player, team, sport, season, week)
);

-- ---------------------------------------------------------------------------
-- depth_charts: used to discount toward replacement level rather than
-- applying a flat injury penalty (§4).
-- ---------------------------------------------------------------------------
create table if not exists depth_charts (
    team        text not null,
    sport       text not null,
    position    text not null,
    depth_order integer not null,
    player      text,
    pulled_at   timestamptz not null default now(),
    primary key (team, sport, position, depth_order)
);

-- ---------------------------------------------------------------------------
-- weather: forecast at kickoff hour. Dome games short-circuit the adjustment.
-- ---------------------------------------------------------------------------
create table if not exists weather (
    game_id      text primary key,
    temp_f       double precision,
    wind_mph     double precision,
    precip_pct   double precision,
    is_dome      boolean default false,
    forecast_for timestamptz,
    pulled_at    timestamptz not null default now()
);

-- ---------------------------------------------------------------------------
-- odds: market lines. book='cfbd_consensus' rows come from CFBD (free,
-- no quota); named books come from The Odds API (~500 req/month, shared).
-- ---------------------------------------------------------------------------
create table if not exists odds (
    game_id         text not null,
    book            text not null,
    spread          double precision,         -- home-team line; negative = home favored
    total           double precision,
    moneyline_home  integer,
    moneyline_away  integer,
    source          text,
    pulled_at       timestamptz not null default now(),
    primary key (game_id, book)
);

-- ---------------------------------------------------------------------------
-- predictions: one current row per (game, model_version). Re-running before
-- kickoff overwrites with fresher info; actual_* columns are filled after
-- the game for calibration scoring (§8).
-- ---------------------------------------------------------------------------
create table if not exists predictions (
    game_id             text not null,
    model_version       text not null,
    sport               text,
    model_win_prob_home double precision,
    model_margin_home   double precision,     -- expected home points - away points
    model_spread        double precision,     -- home-team line, market convention
    market_spread       double precision,
    market_source       text,
    edge                double precision,     -- + => value on HOME, - => value on AWAY
    is_value            boolean default false,
    confidence          text,
    baseline_source     text,                 -- 'sp_plus' | 'elo' | ...
    components          jsonb,                -- full adjustment breakdown, auditable
    actual_home_points  integer,
    actual_away_points  integer,
    graded_at           timestamptz,
    generated_at        timestamptz not null default now(),
    primary key (game_id, model_version)
);
create index if not exists predictions_generated_idx on predictions (generated_at desc);

-- ---------------------------------------------------------------------------
-- teams: home venue + identity. Home coordinates drive the travel-distance
-- feature; conference/classification are used for filtering.
-- ---------------------------------------------------------------------------
create table if not exists teams (
    team           text not null,
    sport          text not null,
    full_name      text,
    conference     text,
    classification text,
    abbreviation   text,
    mascot         text,
    color          text,
    home_venue_id  text,
    home_latitude  double precision,
    home_longitude double precision,
    home_timezone  text,
    pulled_at      timestamptz not null default now(),
    primary key (team, sport)
);

-- ---------------------------------------------------------------------------
-- Additive migrations. `create table if not exists` above will not add a
-- column to a table that already exists, so every column introduced after the
-- first run is repeated here. Re-running this whole file is always safe.
-- ---------------------------------------------------------------------------
alter table team_ratings add column if not exists power_rating double precision;
alter table games       add column if not exists home_rest_days double precision;
alter table games       add column if not exists away_rest_days double precision;
alter table teams       add column if not exists full_name text;
