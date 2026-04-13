#!/usr/bin/env python3
"""
Enrich existing paper notes that are missing authors, journal, or year
frontmatter fields. Looks up each paper by DOI via PubMed API.
"""

import os
import re
import time
import requests
import xml.etree.ElementTree as ET

BASE_DIR = "/storage/emulated/0/Bóveda/Papers"
DELAY    = 0.4   # seconds between PubMed requests

BASE_SEARCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
BASE_FETCH  = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"

# Fields we want present; if any are missing we'll enrich the file
REQUIRED_FIELDS = {"authors", "journal", "year"}

# ── Frontmatter parsing ────────────────────────────────────────────────────────

def read_frontmatter(text: str) -> tuple[dict, str, str]:
    """
    Split file text into (frontmatter_dict, raw_fm_block, body).
    raw_fm_block is the text between the --- delimiters (without the delimiters).
    Returns ({}, "", text) if no frontmatter found.
    """
    if not text.startswith("---"):
        return {}, "", text
    end = text.find("\n---", 3)
    if end == -1:
        return {}, "", text
    raw_fm = text[3:end].lstrip("\n")
    body   = text[end + 4:]   # skip closing ---\n
    fm: dict = {}
    for line in raw_fm.splitlines():
        if ":" in line:
            key, _, val = line.partition(":")
            fm[key.strip()] = val.strip().strip('"').strip("'")
    return fm, raw_fm, body


def build_frontmatter(fm: dict) -> str:
    """Serialize frontmatter dict back to YAML lines (values quoted if needed)."""
    lines = []
    for key, val in fm.items():
        # Re-quote string fields that may contain commas or special chars
        if key in ("authors", "journal", "topic", "doi") and val not in ("", '""'):
            val_clean = str(val).replace('"', "'")
            lines.append(f'{key}: "{val_clean}"')
        else:
            lines.append(f"{key}: {val}")
    return "\n".join(lines)


def rewrite_frontmatter(text: str, fm: dict, raw_fm: str) -> str:
    """Replace the frontmatter block in text with updated fm dict."""
    new_fm_block = build_frontmatter(fm)
    # Reconstruct: opening --- + new block + closing ---
    body_start = text.find("\n---", 3) + 4   # skip \n---
    body = text[body_start:]
    return f"---\n{new_fm_block}\n---{body}"

# ── PubMed lookup by DOI ───────────────────────────────────────────────────────

def pubmed_search_doi(doi: str) -> str | None:
    """Return a PMID for the given DOI, or None if not found."""
    params = {
        "db":      "pubmed",
        "term":    f"{doi}[doi]",
        "retmax":  1,
        "retmode": "xml",
    }
    try:
        resp = requests.get(BASE_SEARCH, params=params, timeout=20)
        resp.raise_for_status()
        root = ET.fromstring(resp.text)
        ids  = [el.text for el in root.findall(".//Id") if el.text]
        return ids[0] if ids else None
    except (requests.RequestException, ET.ParseError):
        return None


def pubmed_fetch_metadata(pmid: str) -> dict | None:
    """Fetch authors (first 3), journal, and year for a PMID."""
    params = {
        "db":      "pubmed",
        "id":      pmid,
        "retmode": "xml",
        "rettype": "abstract",
    }
    try:
        resp = requests.get(BASE_FETCH, params=params, timeout=30)
        resp.raise_for_status()
        root    = ET.fromstring(resp.text)
        article = root.find(".//PubmedArticle")
        if article is None:
            return None

        # Authors (first 3)
        authors = []
        for author in article.findall(".//Author"):
            last  = author.findtext("LastName", "")
            first = author.findtext("ForeName", "")
            if last:
                authors.append(f"{last} {first}".strip())
        author_str = ", ".join(authors[:3])
        if len(authors) > 3:
            author_str += " et al."

        # Journal
        journal = article.findtext(".//Journal/Title", "") or \
                  article.findtext(".//Journal/ISOAbbreviation", "")

        # Year
        year = ""
        for date_path in [".//PubDate", ".//ArticleDate"]:
            d = article.find(date_path)
            if d is not None:
                year = d.findtext("Year", "")
                if year:
                    break

        return {"authors": author_str, "journal": journal, "year": year}
    except (requests.RequestException, ET.ParseError):
        return None

# ── File walker ────────────────────────────────────────────────────────────────

def collect_files(base_dir: str) -> list[str]:
    """Return sorted list of all .md file paths under base_dir."""
    paths = []
    for root_dir, _, files in os.walk(base_dir):
        for fname in sorted(files):
            if fname.endswith(".md"):
                paths.append(os.path.join(root_dir, fname))
    return sorted(paths)


def needs_enrichment(fm: dict) -> bool:
    """True if any required field is missing or empty."""
    for field in REQUIRED_FIELDS:
        val = fm.get(field, "")
        if not val or val in ('""', "''", ""):
            return True
    return False

# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    files = collect_files(BASE_DIR)
    total = len(files)
    print(f"Scanning {total} files in {BASE_DIR}...\n")

    to_enrich = []
    for fpath in files:
        try:
            text = open(fpath, encoding="utf-8").read()
        except OSError:
            continue
        fm, raw_fm, _ = read_frontmatter(text)
        if fm and needs_enrichment(fm):
            to_enrich.append(fpath)

    print(f"Need enrichment: {len(to_enrich)} / {total} files\n")

    updated   = 0
    skipped   = 0
    no_doi    = 0
    not_found = 0

    for idx, fpath in enumerate(to_enrich, 1):
        fname = os.path.basename(fpath)
        try:
            text = open(fpath, encoding="utf-8").read()
        except OSError:
            print(f"  [ERROR] cannot read {fname}")
            skipped += 1
            continue

        fm, raw_fm, body = read_frontmatter(text)

        # Extract DOI from frontmatter
        doi_raw = fm.get("doi", "")
        doi_match = re.search(r"doi\.org/(.+)", doi_raw)
        if not doi_match:
            print(f"  [SKIP] {idx}/{len(to_enrich)}: no DOI — {fname[:70]}")
            no_doi += 1
            continue
        doi = doi_match.group(1).strip()

        # Search PubMed for the DOI
        time.sleep(DELAY)
        pmid = pubmed_search_doi(doi)
        if not pmid:
            print(f"  [NOT FOUND] {idx}/{len(to_enrich)}: {doi} — {fname[:60]}")
            not_found += 1
            continue

        # Fetch metadata
        time.sleep(DELAY)
        meta = pubmed_fetch_metadata(pmid)
        if not meta:
            print(f"  [FETCH ERR] {idx}/{len(to_enrich)}: PMID {pmid} — {fname[:60]}")
            not_found += 1
            continue

        # Patch only missing/empty fields; never overwrite existing values
        changed = False
        for field in REQUIRED_FIELDS:
            current = fm.get(field, "")
            if (not current or current in ('""', "''")) and meta.get(field):
                fm[field] = meta[field]
                changed = True

        # Add stars and read if absent
        if "stars" not in fm:
            fm["stars"] = "0"
            changed = True
        if "read" not in fm:
            fm["read"] = "false"
            changed = True

        if not changed:
            skipped += 1
            continue

        # Rewrite file
        new_text = rewrite_frontmatter(text, fm, raw_fm)
        try:
            with open(fpath, "w", encoding="utf-8") as f:
                f.write(new_text)
            updated += 1
            print(f"  Updated {updated}/{len(to_enrich)}: {fname[:70]}")
        except OSError as exc:
            print(f"  [ERROR] writing {fname}: {exc}")
            skipped += 1

    print(f"\n{'─'*60}")
    print(f"Updated: {updated}  |  No DOI: {no_doi}  |  Not on PubMed: {not_found}  |  Skipped: {skipped}")


if __name__ == "__main__":
    main()
