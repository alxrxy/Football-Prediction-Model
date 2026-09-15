-- Football Predictor — local SQLite mirror of db/PASTE_INTO_SUPABASE.sql
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
    snap_share       real,
    source           text,
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

-- Monte Carlo game simulations (src/simulate_nfl.py). Kept apart from
-- predictions so the simpler pipeline output is never touched. Margins are
-- home minus away. td_scorers is lower-confidence than everything else here.
create table if not exists game_simulations (
    game_id               text not null,
    sim_version           text not null,
    sport                 text,
    home_team             text,
    away_team             text,
    n_sims                integer,
    modal_home_points     integer,
    modal_away_points     integer,
    modal_score_prob      real,
    median_home_points    real,
    median_away_points    real,
    mean_home_points      real,
    mean_away_points      real,
    home_win_prob         real,
    tie_prob              real,
    margin_50_low         real,
    margin_50_high        real,
    margin_80_low         real,
    margin_80_high        real,
    total_50_low          real,
    total_50_high         real,
    total_80_low          real,
    total_80_high         real,
    home_td_mode          integer,
    away_td_mode          integer,
    home_fg_mode          integer,
    away_fg_mode          integer,
    home_td_mean          real,
    away_td_mean          real,
    home_fg_mean          real,
    away_fg_mean          real,
    anchor_margin_home    real,
    sim_margin_home       real,
    market_spread         real,
    market_total          real,
    score_confidence      text,
    td_scorer_confidence  text,
    distributions         text,
    td_scorers            text,
    components            text,
    box_score             text,
    generated_at          text not null,
    primary key (game_id, sim_version)
);

-- Live in-game snapshots (src/live_tracker.py), one row per game per poll, so
-- a game's whole trajectory is kept rather than only its latest state.
-- Percentiles place the live total / home margin among the pregame
-- simulations at the same elapsed game time.
create table if not exists live_tracking (
    game_id               text not null,
    polled_at             text not null,
    espn_event_id         text,
    state                 text,
    period                integer,
    display_clock         text,
    elapsed_minutes       real,
    home_team             text,
    away_team             text,
    home_score            integer,
    away_score            integer,
    possession            text,
    down_distance         text,
    is_red_zone           integer default 0,
    espn_home_win_prob    real,
    predicted_margin_home real,
    predicted_winner      text,
    sim_median_home       real,
    sim_median_away       real,
    sim_total_median_now  real,
    total_percentile      real,
    margin_percentile     real,
    projected_total       real,
    flag_level            text,
    flags                 text,
    alerted               integer default 0,
    recent_scoring        text,
    pregame               text,
    primary key (game_id, polled_at)
);

-- Live-resume simulations (src/live_sim.py): the pregame engine and team
-- strengths, restarted from the game state at each poll. Keyed to the
-- live_tracking snapshot it was run from. The pregame_* columns repeat the
-- fixed pre-kickoff numbers so "then vs now" sits in one row.
create table if not exists live_simulations (
    game_id               text not null,
    polled_at             text not null,
    sim_version           text,
    n_sims                integer,
    elapsed_minutes       real,
    home_team             text,
    away_team             text,
    home_score            integer,
    away_score            integer,
    home_win_prob         real,
    away_win_prob         real,
    tie_prob              real,
    modal_home_points     integer,
    modal_away_points     integer,
    modal_score_prob      real,
    median_home_points    real,
    median_away_points    real,
    mean_margin_home      real,
    margin_80_low         real,
    margin_80_high        real,
    total_median          real,
    total_80_low          real,
    total_80_high         real,
    pregame_margin_home   real,
    pregame_win_prob_home real,
    start_state           text,
    scorers               text,
    box_score             text,
    runtime_ms            integer,
    primary key (game_id, polled_at)
);

-- Every pregame odds pull, append-only, with the prices the odds table does
-- not keep (src/ingest_odds.py). The prices make devigging possible, and the
-- history is what CLV is measured against.
create table if not exists odds_snapshots (
    game_id            text not null,
    book               text not null,
    pulled_at          text not null,
    source             text,
    commence_time      text,
    spread             real,
    spread_price_home  integer,
    spread_price_away  integer,
    total              real,
    over_price         integer,
    under_price        integer,
    moneyline_home     integer,
    moneyline_away     integer,
    primary key (game_id, book, pulled_at)
);

-- Closing line value per model lean (src/clv.py). One row per game and model,
-- written at prediction time for every lean, flagged or not; the close_*
-- columns are filled after kickoff. Probabilities are for the lean side
-- covering, vig-free. clv_pp = p_close - p_market, at the line bet.
create table if not exists clv_log (
    game_id           text not null,
    model_version     text not null,
    market            text not null,
    sport             text,
    side              text,
    team              text,
    is_flag           integer default 0,
    kickoff_time      text,
    flagged_at        text,
    line              real,
    price             integer,
    p_model           real,
    p_market          real,
    p_blend           real,
    breakeven         real,
    edge_pp           real,
    edge_points       real,
    weight            real,
    buffer            real,
    devig_method      text,
    market_source     text,
    ref_book          text,
    ref_line          real,
    ref_price_home    integer,
    ref_price_away    integer,
    close_line        real,
    close_price_home  integer,
    close_price_away  integer,
    close_source      text,
    close_at          text,
    p_close           real,
    clv_pp            real,
    clv_basis         text,
    result            text,
    graded_at         text,
    primary key (game_id, model_version, market)
);

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
