#!/usr/bin/env python3
"""
Sync papers.json → Obsidian markdown notes.

Usage:
  python sync_obsidian.py                    # reads local papers.json
  python sync_obsidian.py --pull             # git pull first, then sync
  python sync_obsidian.py --json /path/to/papers.json

Creates one .md file per paper in BASE_DIR/<folder>/
Only adds new papers (deduplicates by DOI, then by title).
"""

import argparse
import datetime
import os
import re
import subprocess
import sys
import json
from pathlib import Path

# ── Config ─────────────────────────────────────────────────────────────────────

BASE_DIR  = Path("/storage/emulated/0/Bóveda/Papers")
REPO_DIR  = Path(__file__).parent
JSON_FILE = REPO_DIR / "papers.json"

# ── Helpers ────────────────────────────────────────────────────────────────────

def sanitize_filename(name: str) -> str:
    name = re.sub(r'[\\/*?:"<>|]', "", name)
    return name.replace("\n", " ").strip()[:180]


def load_existing_dois(base_dir: Path) -> set[str]:
    """Scan all .md files for DOI frontmatter. Returns set of normalized DOIs."""
    dois: set[str] = set()
    fm_pat  = re.compile(r"^doi:\s*(?:https://doi\.org/)?(.+)$")
    lnk_pat = re.compile(r"https://doi\.org/([^\s\)\"']+)")
    if not base_dir.is_dir():
        return dois
    for md in base_dir.rglob("*.md"):
        try:
            with open(md, "r", encoding="utf-8") as f:
                for line in f:
                    m = fm_pat.match(line.strip())
                    if m:
                        dois.add(m.group(1).strip().lower())
                        break
                    m2 = lnk_pat.search(line)
                    if m2:
                        dois.add(m2.group(1).strip().lower())
                        break
        except OSError:
            pass
    return dois


def load_existing_titles(base_dir: Path) -> set[str]:
    """Scan all .md files for H1 titles (for papers without DOI)."""
    titles: set[str] = set()
    if not base_dir.is_dir():
        return titles
    for md in base_dir.rglob("*.md"):
        try:
            with open(md, "r", encoding="utf-8") as f:
                for line in f:
                    if line.startswith("# "):
                        titles.add(line[2:].strip().lower())
                        break
        except OSError:
            pass
    return titles


def make_note(paper: dict, topic: str) -> str:
    today   = datetime.date.today().isoformat()
    doi_val = paper.get("doi", "")
    doi_fm  = f"https://doi.org/{doi_val}" if doi_val else "_not available_"
    doi_lnk = f"[{doi_fm}]({doi_fm})" if doi_val else "_DOI not available_"
    pmid    = paper.get("pmid", "")
    pm_lnk  = (f"[PubMed {pmid}](https://pubmed.ncbi.nlm.nih.gov/{pmid}/)"
               if pmid else "_not available_")
    authors_fm = (paper.get("authors") or "").replace('"', "'")
    journal_fm = (paper.get("journal") or "").replace('"', "'")
    year       = paper.get("year") or '""'
    sources    = (paper.get("source") or "").replace('"', "'")
    tags_raw   = paper.get("matched_tags") or []
    tags_str   = ", ".join(tags_raw) if isinstance(tags_raw, list) else str(tags_raw)

    return f"""---
date_found: {today}
doi: {doi_fm}
topic: {topic}
authors: "{authors_fm}"
journal: "{journal_fm}"
year: {year}
source: "{sources}"
tags: [{tags_str}]
stars: 0
read: false
new: true
---

# {paper['title']}

| Field | Value |
|---|---|
| **Authors** | {paper.get('authors') or '_unknown_'} |
| **Journal** | {paper.get('journal') or '_unknown_'} |
| **Published** | {paper.get('pub_date') or paper.get('year') or '_unknown_'} |
| **DOI** | {doi_lnk} |
| **PubMed** | {pm_lnk} |
| **Score** | {paper.get('score', 0)} |
| **Topic** | `{topic}` |
| **Source** | {sources} |
| **Fetched** | {today} |

## Abstract

{paper.get('abstract') or '_No abstract available._'}
"""

# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Sync papers.json to Obsidian.")
    parser.add_argument("--pull",  action="store_true", help="git pull before syncing")
    parser.add_argument("--json",  type=Path, default=JSON_FILE, help="Path to papers.json")
    parser.add_argument("--dir",   type=Path, default=BASE_DIR,  help="Obsidian papers folder")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be created")
    args = parser.parse_args()

    if args.pull:
        print("Pulling latest papers.json…")
        result = subprocess.run(["git", "pull"], cwd=str(REPO_DIR), capture_output=True, text=True)
        if result.returncode != 0:
            print(f"git pull failed:\n{result.stderr}", file=sys.stderr)
            sys.exit(1)
        print(result.stdout.strip())

    if not args.json.exists():
        sys.exit(f"papers.json not found at {args.json}\n"
                 "Run git pull or specify --json /path/to/papers.json")

    papers: list[dict] = json.loads(args.json.read_text(encoding="utf-8"))
    print(f"\nLoaded {len(papers)} papers from {args.json.name}")

    existing_dois   = load_existing_dois(args.dir)
    existing_titles = load_existing_titles(args.dir)
    print(f"Obsidian has {len(existing_dois)} papers with DOI, checking for new ones…\n")

    added   = 0
    skipped = 0

    for paper in papers:
        title = (paper.get("title") or "").strip()
        if not title:
            continue

        # Dedup by DOI first
        doi = (paper.get("doi") or "").lower().strip()
        if doi and doi in existing_dois:
            skipped += 1
            continue

        # Dedup by title (papers without DOI)
        if not doi and title.lower() in existing_titles:
            skipped += 1
            continue

        topic  = paper.get("domain") or "General"
        folder = args.dir / (paper.get("folder") or topic)

        if args.dry_run:
            print(f"  [DRY] Would add: {title[:80]}")
            added += 1
            continue

        folder.mkdir(parents=True, exist_ok=True)
        filename = sanitize_filename(title) + ".md"
        filepath = folder / filename
        if filepath.exists():
            pmid = paper.get("pmid", "")
            suffix = f"_{pmid}" if pmid else f"_{added}"
            filepath = folder / (sanitize_filename(title) + suffix + ".md")

        try:
            filepath.write_text(make_note(paper, topic), encoding="utf-8")
            if doi:
                existing_dois.add(doi)
            existing_titles.add(title.lower())
            added += 1
            print(f"  + {title[:80]}")
        except OSError as exc:
            print(f"  [ERROR] {title[:60]}: {exc}", file=sys.stderr)

    print(f"\n{'─'*60}")
    print(f"Added: {added}  |  Skipped (already exists): {skipped}")
    if args.dry_run:
        print("[DRY RUN] No files were written.")


if __name__ == "__main__":
    main()
