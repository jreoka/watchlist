#!/usr/bin/env python3
"""Import a Yamtrack CSV export into this repo's watchlist data files.

Usage:
    python3 scripts/import_yamtrack.py /path/to/yamtrack_export.csv [--shows] [--movies]

Reads the export, drops everything that isn't a show or movie (video games,
etc.), maps Yamtrack statuses onto the repo's statuses, and writes
data/shows.json and data/movies.json. Existing entries are kept and matched
by (title, year) so re-imports don't duplicate — imported rows update them.

Yamtrack's export columns aren't contractual, so this sniffs the header for
likely names instead of hard-coding them.
"""

import argparse
import csv
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SHOWS_JSON = ROOT / "data" / "shows.json"
MOVIES_JSON = ROOT / "data" / "movies.json"

# Yamtrack status -> repo status
STATUS_MAP = {
    "completed": "completed",
    "in progress": "watching",
    "in_progress": "watching",
    "watching": "watching",
    "planning": "plan_to_watch",
    "plan to watch": "plan_to_watch",
    "paused": "on_hold",
    "on hold": "on_hold",
    "dropped": "dropped",
}

# Yamtrack media_type -> repo file (None = skip)
TYPE_MAP = {
    "tv": "shows",
    "season": "shows",
    "anime": "shows",
    "movie": "movies",
}


def norm(s):
    return (s or "").strip().lower()


def pick(row, *names):
    """Return the first non-empty cell among candidate column names."""
    lowered = {norm(k): v for k, v in row.items()}
    for n in names:
        v = lowered.get(n)
        if v not in (None, ""):
            return v.strip()
    return ""


def load(path):
    if path.exists():
        return json.loads(path.read_text())
    return []


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv_path")
    args = ap.parse_args()

    shows = load(SHOWS_JSON)
    movies = load(MOVIES_JSON)
    seen = {(norm(e.get("title")), str(e.get("year") or ""))} for e in shows + movies]

    imported = {"shows": 0, "movies": 0}
    skipped = {}
    updated = 0

    with open(args.csv_path, newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            title = pick(row, "title", "name")
            if not title:
                continue
            media_type = norm(pick(row, "media_type", "media type", "type", "kind"))
            bucket = TYPE_MAP.get(media_type)
            if bucket is None:
                skipped[media_type or "?"] = skipped.get(media_type or "?", 0) + 1
                continue

            status = STATUS_MAP.get(norm(pick(row, "status")), "plan_to_watch")
            score_raw = pick(row, "score", "rating")
            try:
                score = float(score_raw) if score_raw else None
            except ValueError:
                score = None

            year_raw = pick(row, "year", "release_year", "start_year")
            try:
                year = int(float(year_raw)) if year_raw else None
            except ValueError:
                year = None

            entry = {
                "title": title,
                "year": year,
                "tmdb_id": None,
                "status": status,
                "score": score,
                "notes": pick(row, "notes", "comment") or "",
                "date_added": date.today().isoformat(),
                "poster": None,
            }
            if bucket == "shows":
                entry["progress"] = ""

            key = (norm(title), str(year or ""))
            target = shows if bucket == "shows" else movies
            existing = next(
                (e for e in target if (norm(e.get("title")), str(e.get("year") or "")) == key),
                None,
            )
            if existing:
                # Refresh status/score from the export, keep notes/progress.
                existing["status"] = status
                if score is not None:
                    existing["score"] = score
                updated += 1
            else:
                target.append(entry)
                imported[bucket] += 1

    for path, items in ((SHOWS_JSON, shows), (MOVIES_JSON, movies)):
        path.write_text(json.dumps(items, indent=2, ensure_ascii=False) + "\n")

    print(f"imported: {imported['shows']} shows, {imported['movies']} movies")
    print(f"updated existing: {updated}")
    if skipped:
        print("skipped (not shows/movies): " + ", ".join(f"{k} x{v}" for k, v in sorted(skipped.items())))


if __name__ == "__main__":
    sys.exit(main())
