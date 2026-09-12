-- Football Predictor — local SQLite mirror of schema_supabase.sql
-- Same tables, same keys, same column names. Applied automatically by
-- src/db.py when STORAGE_BACKEND=sqlite. Keep in sync with the Postgres file.

create table if not exists venues (
    venue_id     text primary key,
    sport        text not null,
    name         text,
    city         text,
    state        text,
    latitude     real,
    longitude    real,
    elevation_m  real,
    is_dome      integer default 0,
    capacity     integer,
    timezone     text,
    pulled_at    text not null
);

create table if not exists games (
    game_id          text primary key,
    sport            text not null,
    season           integer not null,
    week             integer,
    season_type      text,
    home_team        text not null,
    away_team        text not null,
    home_conference  text,
    away_conference  text,
    kickoff_time     text,
    venue            text,
    venue_id         text,
    is_neutral_site  integer default 0,
    is_conference    integer default 0,
    home_points      integer,
    away_points      integer,
    completed        integer default 0,
    home_rest_days   real,
    away_rest_days   real,
    pulled_at        text not null
);
create index if not exists games_kickoff_idx on games (sport, kickoff_time);
create index if not exists games_week_idx    on games (sport, season, week);

create table if not exists team_ratings (
    team          text not null,
    sport         text not null,
    season        integer not null,
    week          integer not null,
    conference    text,
    power_rating  real,
    elo           real,
    sp_plus       real,
    sp_plus_off   real,
    sp_plus_def   real,
    fpi           real,
    off_epa       real,
    def_epa       real,
    pulled_at     text not null,
    primary key (team, sport, season, week)
);

create table if not exists injuries (
    player           text not null,
    team             text not null,
    sport            text not null,
    season           integer not null,
    week             integer not null,
    position         text,
    status           text,
    practice_trend   text,
    position_weight  real,
    play_probability real,
    pulled_at        text not null,
    primary key (player, team, sport, season, week)
);

create table if not exists depth_charts (
    team        text not null,
    sport       text not null,
    position    text not null,
    depth_order integer not null,
    player      text,
    pulled_at   text not null,
    primary key (team, sport, position, depth_order)
);

create table if not exists weather (
    game_id      text primary key,
    temp_f       real,
    wind_mph     real,
    precip_pct   real,
    is_dome      integer default 0,
    forecast_for text,
    pulled_at    text not null
);

create table if not exists odds (
    game_id         text not null,
    book            text not null,
    spread          real,
    total           real,
    moneyline_home  integer,
    moneyline_away  integer,
    source          text,
    pulled_at       text not null,
    primary key (game_id, book)
);

create table if not exists predictions (
    game_id             text not null,
    model_version       text not null,
    sport               text,
    model_win_prob_home real,
    model_margin_home   real,
    model_spread        real,
    market_spread       real,
    market_source       text,
    edge                real,
    is_value            integer default 0,
    confidence          text,
    baseline_source     text,
    components          text,
    actual_home_points  integer,
    actual_away_points  integer,
    graded_at           text,
    generated_at        text not null,
    primary key (game_id, model_version)
);
create index if not exists predictions_generated_idx on predictions (generated_at desc);

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
    home_latitude  real,
    home_longitude real,
    home_timezone  text,
    pulled_at      text not null,
    primary key (team, sport)
);
