# Watchlist

Cross's personal show & movie tracker — a simpler replacement for Yamtrack
(shows and movies only, no games). Hitori keeps it up to date: just say what
you finished, started, or want to watch next.

## Browse it

Open `index.html` (or the GitHub Pages site) — filter by status, search, sort
by title / score / recently added.

## URL routing

Tabs and filters are real paths, so views are linkable: `/watching`,
`/completed`, `/plan-to-watch`, `/movies`, `/movies/completed`, … — the app
reads `location.pathname` on load and `pushState`s on every tab/filter
change (back/forward buttons work).

GitHub Pages serves `404.html` for unknown paths, so `404.html` is kept as
a copy of `index.html` — **after editing `index.html`, run
`cp index.html 404.html`** before committing. Data fetches use root-absolute
paths (`/data/…`) so they resolve from any route.

## Data

- `data/shows.json` — every show, one object per title
- `data/movies.json` — every movie, one object per title

Entry shape:

```json
{
  "title": "Severance",
  "year": 2022,
  "tmdb_id": null,
  "status": "watching",
  "score": 9,
  "notes": "That finale…",
  "progress": "S2E3",
  "date_added": "2026-09-22",
  "poster": "https://image.tmdb.org/t/p/w342/…"
}
```

Statuses: `watching` · `completed` · `plan_to_watch` · `on_hold` · `dropped`.
Score is 0–10, or `null` when unrated. `progress` is shows-only and freeform
(`S2E3`, `Season 1`, …).

## Importing from Yamtrack

```bash
python3 scripts/import_yamtrack.py /path/to/yamtrack_export.csv
```

Drops anything that isn't a show or movie (games etc.), maps Yamtrack
statuses onto the ones above, and merges without duplicating titles already
present. Check the script's `TYPE_MAP`/`STATUS_MAP` if Yamtrack's export
format ever changes.

## Ideas for later

- Poster art via TMDB (needs a free TMDB API key to enrich `poster` paths)
- Per-season episode checklists
