#!/usr/bin/env python3
"""Update the watchlist data files and commit.

This is the tool Hitori (the agent) uses when Cross says things like
"watched S2E3 of Severance", "finished Frieren", "dropped Jujutsu Kaisen",
"I want to watch Dandadan", or gives a 1-10 score.

Usage
-----

  ./scripts/update.py --status "Re:Zero kara Hajimeru Isekai Seikatsu 4th Season" \
      --watching-eps 19
  ./scripts/update.py --status "Sousou no Frieren: Ougonkyou-hen" --set completed --score 10
  ./scripts/update.py --status "Shikanoko Nokonoko Koshitantan" --set watching --started
  ./scripts/update.py --status "Clarkson's Farm" --set dropped
  ./scripts/update.py --title "Dandadan" --set plan_to_watch --type show --new
  ./scripts/update.py --status "Severance" --score 9 --notes "That finale…"

Flags
-----
  --status TITLE     update the entry with this exact title
  --title TITLE      same, alias (used for new entries together with --new)
  --type show|movie  which data file the title lives in (default: show)
  --set STATUS       watching | completed | plan_to_watch | on_hold | dropped
  --progress STR     set the freeform progress string verbatim (shows only)
  --watching-eps N   shorthand: progress = "N episodes watched" (implies watching)
  --season N         shorthand: progress = "Season N"
  --episode N        shorthand: progress = "SN E", implies --season or existing season
  --score N          set score 0-10 (or "none" to clear)
  --notes STR        set notes
  --started          when adding a new entry, set status=watching
  --new              create the entry if it does not exist (needs --title)
  --year N / --tmdb-id N / --poster URL   metadata for --new
  --date-added YYYY-MM-DD                 date_added for --new (default: today)
  --no-commit        edit the files but do not commit/push
  --message MSG      override the commit message
  -n / --dry-run     print the diff and exit without writing

Nothing is written until the diff has been printed, and the title match is
exact (case-insensitive, whitespace-tolerant) so a typo fails loudly instead
of silently creating a duplicate entry.
"""

import argparse
import difflib
import json
import os
import re
import subprocess
import sys
from datetime import date

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATUSES = ["watching", "completed", "plan_to_watch", "on_hold", "dropped"]
MEDIA = {"show": "data/shows.json", "movie": "data/movies.json"}


def load(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as fh:
        return json.load(fh)


def dump(rel, data):
    path = os.path.join(ROOT, rel)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)
        fh.write("\n")


def norm(s):
    return re.sub(r"\s+", " ", (s or "").strip().lower())


def find(entries, title):
    """Match a title. Exact (case/whitespace-insensitive) first, then substring,
    then fuzzy — and it fails loudly rather than guessing when ambiguous, so a
    vague "frieren" can never silently edit the wrong row."""
    want = norm(title)
    exact = [i for i, e in enumerate(entries) if norm(e["title"]) == want]
    if len(exact) == 1:
        return exact[0]
    if len(exact) > 1:
        die(f"'{title}' matches {len(exact)} entries:\n  " +
            "\n  ".join(entries[i]["title"] for i in exact))

    # substring: title contains the query, or the query is a prefix of the title
    subs = [i for i, e in enumerate(entries) if want and want in norm(e["title"])]
    if len(subs) == 1:
        note(entries[subs[0]]["title"], title)
        return subs[0]
    if len(subs) > 1:
        die(f"'{title}' could mean any of:\n  " +
            "\n  ".join(entries[i]["title"] for i in subs))

    close = difflib.get_close_matches(
        want, [norm(e["title"]) for e in entries], n=6, cutoff=0.7
    )
    hits = [i for i, e in enumerate(entries) if norm(e["title"]) in close]
    if len(hits) == 1:
        note(entries[hits[0]]["title"], title)
        return hits[0]
    if len(hits) > 1:
        die(f"'{title}' is ambiguous:\n  " + "\n  ".join(entries[i]["title"] for i in hits))
    return -1


def note(matched, asked):
    print(f"note: read '{asked}' as '{matched}'", file=sys.stderr)


def die(msg):
    print(f"error: {msg}", file=sys.stderr)
    sys.exit(1)


def score(v):
    if v is None or v == "none":
        return None
    f = float(v)
    if not 0 <= f <= 10:
        sys.exit("error: score must be between 0 and 10")
    return f


def main():
    ap = argparse.ArgumentParser(add_help=False)
    ap.add_argument("--status")
    ap.add_argument("--title")
    ap.add_argument("--type", default="show", choices=list(MEDIA))
    ap.add_argument("--set", dest="set_status", choices=STATUSES)
    ap.add_argument("--progress")
    ap.add_argument("--watching-eps", type=int)
    ap.add_argument("--season", type=int)
    ap.add_argument("--episode", type=int)
    ap.add_argument("--score")
    ap.add_argument("--notes")
    ap.add_argument("--started", action="store_true")
    ap.add_argument("--new", action="store_true")
    ap.add_argument("--year", type=int)
    ap.add_argument("--tmdb-id", type=int)
    ap.add_argument("--poster")
    ap.add_argument("--date-added")
    ap.add_argument("--no-commit", action="store_true")
    ap.add_argument("--message")
    ap.add_argument("-n", "--dry-run", action="store_true")
    ap.add_argument("-h", "--help", action="store_true")
    args = ap.parse_args()

    if args.help or not any([args.status, args.title]):
        print(__doc__)
        return 0 if args.help else 1
    if args.score is not None:
        score(args.score)  # validate before touching anything

    title = args.status or args.title
    rel = MEDIA[args.type]
    entries = load(rel)
    before = json.dumps(entries, indent=2, ensure_ascii=False)

    idx = find(entries, title)
    created = False
    if idx < 0:
        if not args.new:
            sys.exit(
                f"error: no {args.type} titled '{title}' in {rel}. "
                f"Re-run with --new (plus --year/--poster if you have them) to add it."
            )
        entry = {
            "title": title,
            "year": args.year,
            "tmdb_id": args.tmdb_id,
            "status": "watching" if args.started else "plan_to_watch",
            "score": None,
            "notes": args.notes or "",
            "date_added": args.date_added or date.today().isoformat(),
            "poster": args.poster or "",
        }
        if args.type == "show":
            entry["progress"] = "0 episodes watched"
        entries.append(entry)
        idx = len(entries) - 1
        created = True
    else:
        entry = entries[idx]
        if args.new:
            sys.exit(f"error: '{entry['title']}' already exists — no need for --new")

    if args.set_status:
        entry["status"] = args.set_status
    if args.type == "show":
        if args.watching_eps is not None:
            entry["progress"] = f"{args.watching_eps} episodes watched"
        elif args.season is not None and args.episode is None:
            entry["progress"] = f"Season {args.season}"
        elif args.episode is not None:
            season = args.season
            if season is None:
                m = re.match(r"[Ss](\d+)", entry.get("progress") or "")
                season = int(m.group(1)) if m else 1
            entry["progress"] = f"S{season}E{args.episode}"
        elif args.progress is not None:
            entry["progress"] = args.progress
        if args.watching_eps is not None or args.episode is not None:
            if not args.set_status:
                entry["status"] = "watching"
    if args.score is not None:
        entry["score"] = score(args.score)
    if args.notes is not None:
        entry["notes"] = args.notes

    after = json.dumps(entries, indent=2, ensure_ascii=False)
    if before == after:
        print("no changes")
        return 0

    diff = list(
        difflib.unified_diff(
            before.splitlines(), after.splitlines(),
            fromfile=rel, tofile=rel, lineterm="", n=1,
        )
    )
    print("\n".join(diff[2:]))

    if args.dry_run:
        return 0
    dump(rel, entries)

    verb = "Added" if created else entry["title"]
    msg = args.message or f"{verb} -> " + describe(entry, created)
    git(["add", rel])
    check_404_sync()
    if args.no_commit:
        git(["diff", "--cached", "--stat"])
        return 0
    git(["commit", "-m", msg])
    subprocess.run(["git", "push", "origin", "main"], cwd=ROOT, check=True)
    print(f"\npushed: {msg}")
    return 0


def check_404_sync():
    """README rule: 404.html must be a byte-for-byte copy of index.html, because
    GitHub Pages serves it for the app's real URL routes (/watching, …).
    Data-only updates shouldn't touch it, but if they ever drift, resync silently
    here rather than letting the routes break on the live site."""
    import filecmp
    a, b = os.path.join(ROOT, "index.html"), os.path.join(ROOT, "404.html")
    if os.path.exists(a) and os.path.exists(b) and not filecmp.cmp(a, b, shallow=False):
        import shutil
        shutil.copyfile(a, b)
        git(["add", "404.html"])
        print("note: resynced 404.html from index.html")


def describe(entry, created):
    bits = []
    if created:
        bits.append(entry["status"])
    else:
        bits.append(entry["status"])
        if entry.get("progress"):
            bits.append(entry["progress"])
    if entry.get("score") is not None:
        bits.append(f"score {entry['score']}")
    return ", ".join(bits)


def git(cmd):
    subprocess.run(["git"] + cmd, cwd=ROOT, check=True)


if __name__ == "__main__":
    sys.exit(main())
