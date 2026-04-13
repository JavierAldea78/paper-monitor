#!/usr/bin/env python3
"""
PubMed paper monitor for brewing/food science topics.
Searches the last 90 days and saves new papers as markdown notes.
"""

import os
import re
import time
import datetime
import requests
import xml.etree.ElementTree as ET

# ── Configuration ──────────────────────────────────────────────────────────────

BASE_DIR     = "/storage/emulated/0/Bóveda/Papers"
NOVEDADES    = "/storage/emulated/0/Bóveda/Novedades.md"
DAYS_BACK    = 90
DELAY        = 0.4   # seconds between PubMed requests (be polite)

# Topic → subfolder mapping
TOPIC_FOLDER = {
    "non-alcoholic beer":              "NOLO",
    "beer sensory mouthfeel":          "NOLO",
    "BSG valorization":                "BSG",
    "non-conventional yeast brewing":  "Biotech",
    "lactic acid bacteria brewing":    "Biotech",
    "brewing enzymes":                 "Biotech",
    "precision fermentation":          "Biotech",
    "metabolic engineering brewing":   "Biotech",
    "phage brewery":                   "Biotech",
    "antimicrobial peptides brewing":  "Biotech",
    "bioactive peptides brewing":      "Biotech",
    "cell-free brewing":               "Biotech",
    "CoQ10 fermentation":              "Biotech",
    "beer off-flavors":                "Quality",
    "beer haze stability":             "Quality",
    "beer oxidation":                  "Quality",
    "CIP brewery":                     "Process",
    "CO2 recovery brewery":            "Process",
}

TOPICS = {
    "non-alcoholic beer": [
        "non-alcoholic beer", "dealcoholization", "vacuum distillation",
        "reverse osmosis beer", "pervaporation beer",
    ],
    "beer off-flavors": [
        "beer off-flavor", "beer metallic", "beer phenolic",
        "DMS beer", "diacetyl beer",
    ],
    "BSG valorization": [
        "brewers spent grain", "BSG valorization", "arabinoxylan brewery",
        "dietary fiber brewers grain",
    ],
    "beer oxidation": [
        "beer staling", "beer aldehydes", "trans-2-nonenal",
        "beer shelf-life oxidation",
    ],
    "CIP brewery": [
        "CIP brewery", "enzymatic CIP", "ozone brewery cleaning",
        "electrolyzed water brewery",
    ],
    "non-conventional yeast brewing": [
        "Lachancea brewing", "Torulaspora brewing",
        "non-conventional yeast beer", "non-Saccharomyces brewing aroma",
    ],
    "beer haze stability": [
        "beer haze stability", "colloidal stability beer",
        "beer polyphenols haze", "PVPP beer",
    ],
    "CO2 recovery brewery": [
        "brewery CO2 recovery", "fermentation CO2 capture",
        "CO2 reuse brewery",
    ],
    "beer sensory mouthfeel": [
        "beer mouthfeel", "beer foam stability", "beer aroma retention",
        "beer sensory off-flavor",
    ],
}

# ── PubMed helpers ─────────────────────────────────────────────────────────────

BASE_SEARCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
BASE_FETCH  = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"


def pubmed_search(query: str, days: int) -> list[str]:
    """Return a list of PubMed IDs matching query within the last `days` days."""
    date_to   = datetime.date.today()
    date_from = date_to - datetime.timedelta(days=days)
    params = {
        "db":        "pubmed",
        "term":      query,
        "datetype":  "pdat",
        "mindate":   date_from.strftime("%Y/%m/%d"),
        "maxdate":   date_to.strftime("%Y/%m/%d"),
        "retmax":    100,
        "retmode":   "xml",
    }
    resp = requests.get(BASE_SEARCH, params=params, timeout=20)
    resp.raise_for_status()
    root = ET.fromstring(resp.text)
    return [id_el.text for id_el in root.findall(".//Id") if id_el.text]


def pubmed_fetch(pmids: list[str]) -> list[dict]:
    """Fetch article metadata for a list of PubMed IDs."""
    if not pmids:
        return []
    params = {
        "db":      "pubmed",
        "id":      ",".join(pmids),
        "retmode": "xml",
        "rettype": "abstract",
    }
    resp = requests.get(BASE_FETCH, params=params, timeout=30)
    resp.raise_for_status()
    return parse_articles(resp.text)


def parse_articles(xml_text: str) -> list[dict]:
    """Parse PubMed XML into a list of article dicts."""
    root = ET.fromstring(xml_text)
    articles = []
    for article in root.findall(".//PubmedArticle"):
        title_el = article.find(".//ArticleTitle")
        title = "".join(title_el.itertext()).strip() if title_el is not None else ""

        # Abstract – join all AbstractText sections
        abstract_parts = []
        for ab in article.findall(".//AbstractText"):
            label = ab.get("Label")
            text  = "".join(ab.itertext()).strip()
            if label:
                abstract_parts.append(f"**{label}:** {text}")
            elif text:
                abstract_parts.append(text)
        abstract = "\n\n".join(abstract_parts) if abstract_parts else "_No abstract available._"

        # DOI
        doi = ""
        for aid in article.findall(".//ArticleId"):
            if aid.get("IdType") == "doi":
                doi = aid.text.strip() if aid.text else ""
                break

        # PMID
        pmid_el = article.find(".//PMID")
        pmid = pmid_el.text.strip() if pmid_el is not None else ""

        # Publication date
        pub_date = ""
        for date_path in [".//PubDate", ".//ArticleDate"]:
            d = article.find(date_path)
            if d is not None:
                year  = d.findtext("Year", "")
                month = d.findtext("Month", "")
                day   = d.findtext("Day", "")
                pub_date = " ".join(filter(None, [year, month, day]))
                if pub_date:
                    break

        # Authors (first 3 only)
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

        # Year only
        year = ""
        for date_path in [".//PubDate", ".//ArticleDate"]:
            d = article.find(date_path)
            if d is not None:
                year = d.findtext("Year", "")
                if year:
                    break

        if title:
            articles.append({
                "title":    title,
                "abstract": abstract,
                "doi":      doi,
                "pmid":     pmid,
                "pub_date": pub_date,
                "year":     year,
                "authors":  author_str,
                "journal":  journal,
            })
    return articles

# ── File helpers ───────────────────────────────────────────────────────────────

def sanitize_filename(name: str) -> str:
    """Make a string safe for use as a filename."""
    name = re.sub(r'[\\/*?:"<>|]', "", name)
    name = name.replace("\n", " ").strip()
    return name[:180]


def load_existing_dois(base_dir: str) -> set[str]:
    """Scan all markdown files in all subfolders for DOI frontmatter entries."""
    dois = set()
    if not os.path.isdir(base_dir):
        return dois
    # Match both frontmatter `doi: https://doi.org/XXX` and inline links
    fm_pattern  = re.compile(r"^doi:\s*https://doi\.org/(.+)$")
    lnk_pattern = re.compile(r"https://doi\.org/([^\s\)]+)")
    for root_dir, dirs, files in os.walk(base_dir):
        # Skip the base dir itself — only scan subdirectories
        for fname in files:
            if not fname.endswith(".md"):
                continue
            fpath = os.path.join(root_dir, fname)
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    for line in f:
                        m = fm_pattern.match(line.strip())
                        if m:
                            dois.add(m.group(1).strip())
                            break
                        m2 = lnk_pattern.search(line)
                        if m2:
                            dois.add(m2.group(1).strip())
                            break
            except OSError:
                pass
    return dois


def save_paper(article: dict, topic: str, folder: str) -> str:
    """Write a markdown note with YAML frontmatter and return the file path."""
    os.makedirs(folder, exist_ok=True)
    today = datetime.date.today().isoformat()

    doi_value = f"https://doi.org/{article['doi']}" if article["doi"] else ""
    doi_fm    = doi_value or "_not available_"
    doi_link  = (
        f"[{doi_value}]({doi_value})"
        if doi_value
        else "_DOI not available_"
    )
    pmid_line = (
        f"[PubMed {article['pmid']}](https://pubmed.ncbi.nlm.nih.gov/{article['pmid']}/)"
        if article["pmid"]
        else ""
    )

    year    = article.get("year", "")
    authors_fm = article["authors"].replace('"', "'") if article["authors"] else ""
    journal_fm = article["journal"].replace('"', "'") if article["journal"] else ""

    content = f"""---
date_found: {today}
doi: {doi_fm}
topic: {topic}
authors: "{authors_fm}"
journal: "{journal_fm}"
year: {year or '""'}
stars: 0
read: false
new: true
---

# {article['title']}

| Field | Value |
|---|---|
| **Authors** | {article['authors'] or '_unknown_'} |
| **Journal** | {article['journal'] or '_unknown_'} |
| **Published** | {article['pub_date'] or '_unknown_'} |
| **DOI** | {doi_link} |
| **PubMed** | {pmid_line} |
| **Topic tag** | `{topic}` |
| **Search date** | {today} |

## Abstract

{article['abstract']}
"""

    filename = sanitize_filename(article["title"]) + ".md"
    filepath = os.path.join(folder, filename)
    if os.path.exists(filepath):
        filepath = os.path.join(folder, sanitize_filename(article["title"]) + f"_{article['pmid']}.md")

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    return filepath


def write_novedades(saved_papers: list[dict], today: str) -> None:
    """Write/overwrite Novedades.md grouped by folder."""
    # Group by folder name
    by_folder: dict[str, list[dict]] = {}
    for entry in saved_papers:
        by_folder.setdefault(entry["folder"], []).append(entry)

    lines = [f"# Novedades - {today}", ""]

    for folder in sorted(by_folder):
        lines.append(f"## {folder}")
        lines.append("")
        for entry in by_folder[folder]:
            doi_url = f"https://doi.org/{entry['doi']}" if entry["doi"] else ""
            if doi_url:
                lines.append(f"- [{entry['title']}]({doi_url})")
            else:
                lines.append(f"- {entry['title']}")
        lines.append("")

    lines.append("---")
    lines.append(f"Total nuevos: {len(saved_papers)} papers")
    lines.append("")

    os.makedirs(os.path.dirname(NOVEDADES), exist_ok=True)
    with open(NOVEDADES, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    today = datetime.date.today().isoformat()
    print(f"PubMed paper monitor — {today}  (last {DAYS_BACK} days)")
    print(f"Output → {BASE_DIR}\n")

    existing_dois = load_existing_dois(BASE_DIR)
    print(f"Already saved: {len(existing_dois)} paper(s)\n")

    total_found   = 0
    total_saved   = 0
    total_skipped = 0
    all_saved: list[dict] = []   # for Novedades.md

    for topic, queries in TOPICS.items():
        subfolder = TOPIC_FOLDER.get(topic, "Misc")
        folder    = os.path.join(BASE_DIR, subfolder)
        print(f"── Topic: {topic}  [{subfolder}]")

        seen_pmids: set[str] = set()
        all_articles: list[dict] = []

        for query in queries:
            try:
                pmids = pubmed_search(query, DAYS_BACK)
                new_pmids = [p for p in pmids if p not in seen_pmids]
                seen_pmids.update(new_pmids)
                if new_pmids:
                    time.sleep(DELAY)
                    articles = pubmed_fetch(new_pmids)
                    all_articles.extend(articles)
                    time.sleep(DELAY)
            except requests.RequestException as exc:
                print(f"   [ERROR] query '{query}': {exc}")
                continue

        # Deduplicate by DOI / PMID within this topic
        seen_ids: set[str] = set()
        unique_articles = []
        for art in all_articles:
            key = art["doi"] or art["pmid"]
            if key and key not in seen_ids:
                seen_ids.add(key)
                unique_articles.append(art)

        saved   = 0
        skipped = 0
        for art in unique_articles:
            if art["doi"] and art["doi"] in existing_dois:
                skipped += 1
                continue
            try:
                save_paper(art, topic, folder)
                if art["doi"]:
                    existing_dois.add(art["doi"])
                saved += 1
                all_saved.append({
                    "title":  art["title"],
                    "doi":    art["doi"],
                    "folder": subfolder,
                    "topic":  topic,
                })
                print(f"   + {art['title'][:80]}")
            except OSError as exc:
                print(f"   [ERROR] could not save '{art['title'][:60]}': {exc}")

        print(f"   Found {len(unique_articles)}, saved {saved}, skipped {skipped}\n")
        total_found   += len(unique_articles)
        total_saved   += saved
        total_skipped += skipped

    # Write Novedades.md
    write_novedades(all_saved, today)
    print("─" * 60)
    print(f"TOTAL  found: {total_found}  |  saved: {total_saved}  |  skipped: {total_skipped}")
    print(f"Novedades → {NOVEDADES}")


if __name__ == "__main__":
    main()
