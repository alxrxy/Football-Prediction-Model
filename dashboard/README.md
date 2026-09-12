# Dashboard

React + Vite front end for the predictor. Step 8 of the architecture build order.

## Running it

```bash
cd dashboard
npm install
npm run dev          # http://localhost:5173
```

The dev server reads `public/data.json`. Regenerate that after a pipeline run:

```bash
python -m src.export_dashboard
```

## Why a snapshot instead of a live query

The dashboard reads an exported JSON snapshot rather than querying Supabase or
the APIs directly. That keeps credentials out of the front end, makes the build
deployable as plain static files, and means a dashboard left open in a browser
tab can never be the reason The Odds API quota runs out.

## Single-file export

```bash
npm run build
python -m src.export_static_dashboard
```

Inlines the CSS, the JS bundle and the current snapshot into
`data/dashboard_static.html` — one file, no external requests, opens from disk
or any static host. `--fragment` emits body content only, for hosts that supply
their own document shell.

This reuses the compiled React app rather than reimplementing the UI in plain
HTML, so there is no second version to drift out of sync.

## What it shows

- **Slate table** — market line, baseline model line, ML model line, edge, the
  side the model leans to, home win probability, and a confidence tier. Sortable
  by kickoff, edge size or team; proxy-rated games can be hidden.
- **Per-game breakdown** (click any row) — the layer-by-layer path from power
  rating to final number, the injury report with each player's snap share and
  points cost, and every book's price.
- **Backtest panel** — holdout MAE against the closing line, ATS record by edge
  threshold with Bonferroni-corrected p-values, and this slate's spread against
  the market.
- **Injury coverage** — how many teams actually have data, stated plainly
  because it is 32/32 for the NFL and about 1/138 for college.

## A deliberate design decision

The backtest sits beside the picks, not buried behind a tab. A dashboard that
shows edges without the evidence about whether those edges have ever worked is
precisely the thing this project is trying not to build.

For the same reason the two kinds of flag are kept visually and verbally
distinct: the trained model's value gate is reported in the backtest panel and
is currently shut, while games past the baseline's fixed threshold are labelled
`unvalidated` rather than `value`, because that is what they are.

## Theming

Light and dark are both first-class. Tokens are defined on bare `:root`,
redefined under `@media (prefers-color-scheme: dark)` guarded with
`:not([data-theme="light"])`, and again under `:root[data-theme="dark"]` so an
explicit choice wins in either direction.
