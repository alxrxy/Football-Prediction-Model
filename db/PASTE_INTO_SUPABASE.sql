-- ===========================================================================
-- FOOTBALL PREDICTOR - Supabase setup
--
-- HOW TO USE THIS FILE
--   1. Open your Supabase project at https://supabase.com/dashboard
--   2. Left sidebar -> SQL Editor -> New query
--   3. Select this entire file, copy, paste into the editor
--   4. Click Run (or press Ctrl+Enter)
--   5. The last statement prints a table of what was created - check that all
--      nine tables are listed with the expected column counts.
--
-- Then, back in the project folder:
--   python -m src.sync_to_supabase --check    verify the tables are visible
--   python -m src.sync_to_supabase            push your local data up
--   ...and set STORAGE_BACKEND=supabase in .env
--
-- SAFE TO RE-RUN. Every statement is idempotent: existing tables and columns
-- are left alone, and no data is dropped. Running it twice changes nothing.
-- ===========================================================================


-- ---------------------------------------------------------------------------
-- 1. TABLES
--
-- Raw ingested rows and derived predictions live in separate tables, and every
-- ingested row carries pulled_at, so a bad upstream pull is identifiable and
-- reversible without touching anything derived from it.
-- ---------------------------------------------------------------------------

-- Stadiums. Feeds both the weather lookup and the travel-distance feature.
create table if not exists venues (
    venue_id      text primary key,
    sport         text not null,
    name          text,
    city          text,
    state         text,
    latitude      double precision,
    longitude     double precision,
    elevation_m   double precision,
    is_dome       boolean default false,
    capacity      integer,
    timezone      text,
    pulled_at     timestamptz not null default now()
);

-- Team identity and home coordinates.
-- full_name is what The Odds API and ESPN use ("Kansas City Chiefs"); team is
-- the canonical key, which is a school name for college and an abbreviation
-- ("KC") for the NFL. Matching between feeds needs both.
create table if not exists teams (
    team            text not null,
    sport           text not null,
    full_name       text,
    conference      text,
    classification  text,
    abbreviation    text,
    mascot          text,
    color           text,
    home_venue_id   text,
    home_latitude   double precision,
    home_longitude  double precision,
    home_timezone   text,
    pulled_at       timestamptz not null default now(),
    primary key (team, sport)
);

-- One row per scheduled game, both sports.
create table if not exists games (
    game_id          text primary key,
    sport            text not null,            -- 'ncaaf' | 'nfl'
    season           integer not null,
    week             integer,
    season_type      text,                     -- 'regular' | 'postseason'
    home_team        text not null,
    away_team        text not null,
    home_conference  text,
    away_conference  text,
    kickoff_time     timestamptz,
    venue            text,
    venue_id         text,
    is_neutral_site  boolean default false,
    is_conference    boolean default false,
    home_points      integer,                  -- filled in post-game
    away_points      integer,
    completed        boolean default false,
    home_rest_days   double precision,         -- supplied by nflverse
    away_rest_days   double precision,
    pulled_at        timestamptz not null default now()
);

-- Power ratings by week.
-- power_rating is the sport-neutral modelling input: points above an average
-- team. College fills it from SP+, the NFL from the EPA-derived rating. The
-- model reads only this column, so both sports share one code path.
create table if not exists team_ratings (
    team          text not null,
    sport         text not null,
    season        integer not null,
    week          integer not null,
    conference    text,
    power_rating  double precision,
    elo           double precision,
    sp_plus       double precision,            -- net SP+, already in points
    sp_plus_off   double precision,
    sp_plus_def   double precision,
    fpi           double precision,
    off_epa       double precision,
    def_epa       double precision,
    pulled_at     timestamptz not null default now(),
    primary key (team, sport, season, week)
);

-- Weekly injury reports.
-- snap_share is the load-bearing column: it separates a starter from a third
-- stringer. Without it a backup being ruled out costs a full starter's penalty.
create table if not exists injuries (
    player            text not null,
    team              text not null,
    sport             text not null,
    season            integer not null,
    week              integer not null,
    position          text,
    status            text,                    -- out|doubtful|questionable|probable
    practice_trend    text,                    -- dnp|limited|full
    position_weight   double precision,
    play_probability  double precision,
    snap_share        double precision,
    source            text,                    -- 'nflverse' | 'espn'
    pulled_at         timestamptz not null default now(),
    primary key (player, team, sport, season, week)
);

-- Depth order within a team and position, lowest number = starter.
create table if not exists depth_charts (
    team         text not null,
    sport        text not null,
    position     text not null,
    depth_order  integer not null,
    player       text,
    pulled_at    timestamptz not null default now(),
    primary key (team, sport, position, depth_order)
);

-- Forecast at the kickoff hour. Indoor games short-circuit the adjustment.
create table if not exists weather (
    game_id       text primary key,
    temp_f        double precision,
    wind_mph      double precision,
    precip_pct    double precision,
    is_dome       boolean default false,
    forecast_for  timestamptz,
    pulled_at     timestamptz not null default now()
);

-- Market lines.
-- spread is ALWAYS the home-team line: negative means the home team is
-- favoured. Every source is normalized to this on ingest.
create table if not exists odds (
    game_id         text not null,
    book            text not null,
    spread          double precision,
    total           double precision,
    moneyline_home  integer,
    moneyline_away  integer,
    source          text,
    pulled_at       timestamptz not null default now(),
    primary key (game_id, book)
);

-- One current row per (game, model). Re-running before kickoff overwrites with
-- fresher information; the actual_* columns are filled in after the game so
-- predictions can be scored for calibration.
create table if not exists predictions (
    game_id              text not null,
    model_version        text not null,        -- 'baseline-v1' | 'ml-v1'
    sport                text,
    model_win_prob_home  double precision,
    model_margin_home    double precision,     -- expected home points - away
    model_spread         double precision,     -- home-team line
    market_spread        double precision,
    market_source        text,
    edge                 double precision,     -- + => value on HOME
    is_value             boolean default false,
    confidence           text,
    baseline_source      text,
    components           jsonb,                -- full auditable breakdown
    actual_home_points   integer,
    actual_away_points   integer,
    graded_at            timestamptz,
    generated_at         timestamptz not null default now(),
    primary key (game_id, model_version)
);


-- ---------------------------------------------------------------------------
-- 2. INDEXES
-- ---------------------------------------------------------------------------

create index if not exists games_kickoff_idx
    on games (sport, kickoff_time);
create index if not exists games_week_idx
    on games (sport, season, week);
create index if not exists predictions_generated_idx
    on predictions (generated_at desc);
create index if not exists odds_game_idx
    on odds (game_id);
create index if not exists injuries_team_week_idx
    on injuries (sport, season, week, team);


-- ---------------------------------------------------------------------------
-- 3. ADDITIVE MIGRATIONS
--
-- "create table if not exists" does nothing to a table that already exists, so
-- it will not add a column introduced after the table was first created. Every
-- such column is repeated here, which is what keeps this file safe to re-run
-- against a project set up from an earlier version.
-- ---------------------------------------------------------------------------

alter table teams        add column if not exists full_name text;
alter table team_ratings add column if not exists power_rating double precision;
alter table games        add column if not exists home_rest_days double precision;
alter table games        add column if not exists away_rest_days double precision;
alter table injuries     add column if not exists snap_share double precision;
alter table injuries     add column if not exists source text;


-- ---------------------------------------------------------------------------
-- 4. ROW LEVEL SECURITY  -- please do not skip this section
--
-- Supabase exposes every table in the public schema over its REST API. With
-- RLS switched off, ANY holder of the project's anon key can read and write
-- all of it, and the anon key is designed to be public - it ships in front-end
-- code and is visible to anyone who opens the network tab.
--
-- Enabling RLS without adding any policy denies anon and authenticated users
-- outright. The ingestion pipeline is unaffected: it authenticates with the
-- service_role key, which bypasses RLS by design. The dashboard is unaffected
-- too, because it reads an exported JSON snapshot rather than querying the
-- database.
--
-- Net effect: the pipeline keeps full access, and a leaked anon key gets
-- nothing. If you later add a front end that queries Supabase directly, add a
-- read-only policy for exactly the tables it needs - do not disable RLS.
-- ---------------------------------------------------------------------------

alter table venues       enable row level security;
alter table teams        enable row level security;
alter table games        enable row level security;
alter table team_ratings enable row level security;
alter table injuries     enable row level security;
alter table depth_charts enable row level security;
alter table weather      enable row level security;
alter table odds         enable row level security;
alter table predictions  enable row level security;


-- ---------------------------------------------------------------------------
-- 5. VERIFY
--
-- Expected output: nine rows, with these column counts.
--     depth_charts  6      predictions  17
--     odds          8      games        20
--     weather       7      injuries     13
--     venues       12      teams        13
--     team_ratings 14
-- ---------------------------------------------------------------------------

select
    t.table_name,
    count(c.column_name) as columns,
    bool_or(cls.relrowsecurity) as rls_enabled
from information_schema.tables t
join information_schema.columns c
    on c.table_schema = t.table_schema
   and c.table_name = t.table_name
join pg_class cls
    on cls.relname = t.table_name
join pg_namespace ns
    on ns.oid = cls.relnamespace
   and ns.nspname = t.table_schema
where t.table_schema = 'public'
  and t.table_name in (
      'venues', 'teams', 'games', 'team_ratings', 'injuries',
      'depth_charts', 'weather', 'odds', 'predictions'
  )
group by t.table_name
order by t.table_name;
