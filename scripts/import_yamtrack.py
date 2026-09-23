#!/usr/bin/env python3
"""Import a Yamtrack CSV export into this repo's watchlist data files.

Usage:
    python3 scripts/import_yamtrack.py /path/to/yamtrack_export.csv

Reads the export, drops video games and per-episode tracking rows, maps
Yamtrack statuses onto the repo's statuses, and writes data/shows.json and
data/movies.json. Titles already present are merged (never duplicated):
the first-seen row wins, later rows only fill in a missing score.

Expected Yamtrack columns: media_id, source, media_type, title, image,
season_number, episode_number, score, status, notes, start_date, progress.
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
    "game": None,      # video games live elsewhere
    "episode": None,    # per-episode rows; the show/season row covers it
}


def norm(s):
    return (s or "").strip().lower()


def poster_url(raw):
    raw = (raw or "").strip()
    if not raw:
        return None
    # TMDB w500 posters are heavy for thumbnails; w342 is plenty.
    return raw.replace("/t/p/w500/", "/t/p/w342/")


def progress_text(row):
    sn, en = row.get("season_number", "").strip(), row.get("episode_number", "").strip()
    if sn and en:
        return f"S{sn}E{en}"
    p = (row.get("progress") or "").strip()
    if p.isdigit():
        return f"{p} episodes watched"
    return p


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
    index = {(norm(e.get("title"))): e for e in shows + movies}

    imported = {"shows": 0, "movies": 0}
    merged = 0
    skipped = {}

    with open(args.csv_path, newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            title = (row.get("title") or "").strip()
            if not title:
                continue
            bucket = TYPE_MAP.get(norm(row.get("media_type")))
            if bucket is None:
                mt = norm(row.get("media_type")) or "?"
                skipped[mt] = skipped.get(mt, 0) + 1
                continue

            status = STATUS_MAP.get(norm(row.get("status")), "plan_to_watch")
            try:
                score = float(row["score"]) if (row.get("score") or "").strip() else None
            except ValueError:
                score = None

            start = (row.get("start_date") or "").strip()
            date_added = start[:10] if len(start) >= 10 else date.today().isoformat()
            source = norm(row.get("source"))

            existing = index.get(norm(title))
            if existing:
                # Fill in blanks only; first-seen row wins.
                if existing.get("score") is None and score is not None:
                    existing["score"] = score
                if not existing.get("poster"):
                    existing["poster"] = poster_url(row.get("image"))
                merged += 1
                continue

            entry = {
                "title": title,
                "year": None,
                "tmdb_id": int(row["media_id"]) if source == "tmdb" and (row.get("media_id") or "").strip().isdigit() else None,
                "status": status,
                "score": score,
                "notes": (row.get("notes") or "").strip(),
                "date_added": date_added,
                "poster": poster_url(row.get("image")),
            }
            if bucket == "shows":
                entry["progress"] = progress_text(row)

            (shows if bucket == "shows" else movies).append(entry)
            index[norm(title)] = entry
            imported[bucket] += 1

    for path, items in ((SHOWS_JSON, shows), (MOVIES_JSON, movies)):
        path.write_text(json.dumps(items, indent=2, ensure_ascii=False) + "\n")

    print(f"imported: {imported['shows']} shows, {imported['movies']} movies")
    print(f"merged duplicates: {merged}")
    if skipped:
        print("skipped: " + ", ".join(f"{k} x{v}" for k, v in sorted(skipped.items())))


if __name__ == "__main__":
    sys.exit(main())
