#!/usr/bin/env python3
"""
Tech vigilance paper fetcher.
Sources: PubMed, Semantic Scholar, Europe PMC (all free, no mandatory keys).
Reads watchtags.csv → writes papers.json + papers.csv.
"""

import csv
import json
import os
import re
import time
import datetime
import requests
import xml.etree.ElementTree as ET
from pathlib import Path

# ── Config ─────────────────────────────────────────────────────────────────────

REPO_ROOT   = Path(__file__).parent.parent
TAGS_FILE   = REPO_ROOT / "watchtags.csv"
OUTPUT_JSON = REPO_ROOT / "papers.json"
OUTPUT_CSV  = REPO_ROOT / "papers.csv"

DAYS_BACK    = 90
DELAY        = 0.4   # seconds between API calls (polite throttling)
DELAY_S2     = 1.2   # Semantic Scholar is stricter (100 req / 5 min unauth)

NCBI_API_KEY = os.environ.get("NCBI_API_KEY", "")
S2_API_KEY   = os.environ.get("S2_API_KEY", "")

# ── API base URLs ──────────────────────────────────────────────────────────────

PUBMED_SEARCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
PUBMED_FETCH  = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
S2_SEARCH     = "https://api.semanticscholar.org/graph/v1/paper/search"
EPMC_SEARCH   = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"

S2_FIELDS = "title,authors,year,externalIds,abstract,citationCount,publicationDate,venue"

# ── Tag loading ────────────────────────────────────────────────────────────────

def load_tags(path: Path) -> list[dict]:
    tags = []
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row.get("active", "true").strip().lower() == "false":
                continue
            synonyms = [s.strip() for s in row.get("synonyms", "").split(",") if s.strip()]
            must     = [m.strip() for m in row.get("mustInclude", "").split(",") if m.strip()]
            tags.append({
                "tag":         row["tag"].strip(),
                "synonyms":    synonyms,
                "mustInclude": must,
                "domain":      row.get("domain", "General").strip(),
                "folder":      row.get("folder", "General").strip(),
            })
    return tags

# ── PubMed ─────────────────────────────────────────────────────────────────────

def _pubmed_params(extra: dict) -> dict:
    p = {"retmode": "xml", **extra}
    if NCBI_API_KEY:
        p["api_key"] = NCBI_API_KEY
    return p


def pubmed_search(query: str, days: int) -> list[str]:
    date_to   = datetime.date.today()
    date_from = date_to - datetime.timedelta(days=days)
    params = _pubmed_params({
        "db":       "pubmed",
        "term":     query,
        "datetype": "pdat",
        "mindate":  date_from.strftime("%Y/%m/%d"),
        "maxdate":  date_to.strftime("%Y/%m/%d"),
        "retmax":   100,
    })
    try:
        r = requests.get(PUBMED_SEARCH, params=params, timeout=20)
        r.raise_for_status()
        root = ET.fromstring(r.text)
        return [el.text for el in root.findall(".//Id") if el.text]
    except Exception as e:
        print(f"  [PubMed search] '{query}': {e}")
        return []


def pubmed_fetch(pmids: list[str]) -> list[dict]:
    if not pmids:
        return []
    params = _pubmed_params({
        "db":      "pubmed",
        "id":      ",".join(pmids),
        "rettype": "abstract",
    })
    try:
        r = requests.get(PUBMED_FETCH, params=params, timeout=30)
        r.raise_for_status()
        return _parse_pubmed_xml(r.text)
    except Exception as e:
        print(f"  [PubMed fetch] {pmids[:2]}: {e}")
        return []


def _parse_pubmed_xml(xml_text: str) -> list[dict]:
    root = ET.fromstring(xml_text)
    out  = []
    for art in root.findall(".//PubmedArticle"):
        title_el = art.find(".//ArticleTitle")
        title    = "".join(title_el.itertext()).strip() if title_el is not None else ""
        if not title:
            continue

        parts = []
        for ab in art.findall(".//AbstractText"):
            label = ab.get("Label")
            text  = "".join(ab.itertext()).strip()
            parts.append(f"**{label}:** {text}" if label else text)
        abstract = "\n\n".join(parts) if parts else ""

        doi  = ""
        pmid = ""
        for aid in art.findall(".//ArticleId"):
            if aid.get("IdType") == "doi" and not doi:
                doi = (aid.text or "").strip()
            if aid.get("IdType") == "pubmed" and not pmid:
                pmid = (aid.text or "").strip()
        if not pmid:
            el = art.find(".//PMID")
            pmid = el.text.strip() if el is not None else ""

        authors = []
        for a in art.findall(".//Author"):
            last  = a.findtext("LastName", "")
            first = a.findtext("ForeName", "")
            if last:
                authors.append(f"{last} {first}".strip())
        author_str = ", ".join(authors[:3]) + (" et al." if len(authors) > 3 else "")

        journal = art.findtext(".//Journal/Title", "") or art.findtext(".//Journal/ISOAbbreviation", "")

        year = pub_date = ""
        for dp in [".//PubDate", ".//ArticleDate"]:
            d = art.find(dp)
            if d is not None:
                y, m, dy = d.findtext("Year",""), d.findtext("Month",""), d.findtext("Day","")
                if y:
                    year     = y
                    pub_date = "-".join(filter(None, [y, m, dy]))
                    break

        out.append({
            "title": title, "abstract": abstract, "doi": doi, "pmid": pmid,
            "authors": author_str, "journal": journal, "year": year,
            "pub_date": pub_date, "source": "PubMed", "citations": 0,
        })
    return out

# ── Semantic Scholar ───────────────────────────────────────────────────────────

def search_semantic_scholar(query: str, days: int) -> list[dict]:
    year_from = (datetime.date.today() - datetime.timedelta(days=days)).year
    headers   = {"User-Agent": "paper-monitor/2.0 (github.com/JavierAldea78/paper-monitor)"}
    if S2_API_KEY:
        headers["x-api-key"] = S2_API_KEY
    params = {"query": query, "fields": S2_FIELDS, "limit": 50}
    try:
        r = requests.get(S2_SEARCH, params=params, headers=headers, timeout=30)
        if r.status_code == 429:
            print("  [S2] rate limited, waiting 15s…")
            time.sleep(15)
            r = requests.get(S2_SEARCH, params=params, headers=headers, timeout=30)
        r.raise_for_status()
        out = []
        for p in r.json().get("data", []):
            year = p.get("year") or 0
            if year and year < year_from:
                continue
            doi  = (p.get("externalIds") or {}).get("DOI", "") or ""
            pmid = str((p.get("externalIds") or {}).get("PubMed", "") or "")
            araw = p.get("authors") or []
            anames = [a.get("name","") for a in araw[:3]]
            astr   = ", ".join(filter(None, anames)) + (" et al." if len(araw) > 3 else "")
            out.append({
                "title":    (p.get("title") or "").strip(),
                "abstract": p.get("abstract") or "",
                "doi":      doi.strip(),
                "pmid":     pmid,
                "authors":  astr,
                "journal":  p.get("venue") or "",
                "year":     str(year) if year else "",
                "pub_date": p.get("publicationDate") or str(year),
                "source":   "Semantic Scholar",
                "citations": p.get("citationCount") or 0,
            })
        return out
    except Exception as e:
        print(f"  [S2] '{query}': {e}")
        return []

# ── Europe PMC ─────────────────────────────────────────────────────────────────

def search_europe_pmc(query: str, days: int) -> list[dict]:
    date_from = (datetime.date.today() - datetime.timedelta(days=days)).strftime("%Y-%m-%d")
    params = {
        "query":      f"({query}) AND FIRST_PDATE:[{date_from} TO *]",
        "format":     "json",
        "pageSize":   100,
        "resultType": "core",
    }
    try:
        r = requests.get(EPMC_SEARCH, params=params, timeout=30)
        r.raise_for_status()
        out = []
        for p in r.json().get("resultList", {}).get("result", []):
            title = (p.get("title") or "").strip()
            if not title:
                continue
            doi  = p.get("doi") or ""
            pmid = str(p.get("pmid") or "")
            astr = p.get("authorString") or ""
            aparts = [a.strip() for a in astr.split(",") if a.strip()]
            if len(aparts) > 3:
                astr = ", ".join(aparts[:3]) + " et al."
            journal  = p.get("journalTitle") or ""
            year     = str(p.get("pubYear") or "")
            pub_date = p.get("firstPublicationDate") or year
            abstract = p.get("abstractText") or ""
            out.append({
                "title": title, "abstract": abstract, "doi": doi.strip(), "pmid": pmid,
                "authors": astr, "journal": journal, "year": year,
                "pub_date": pub_date, "source": "Europe PMC",
                "citations": p.get("citedByCount") or 0,
            })
        return out
    except Exception as e:
        print(f"  [Europe PMC] '{query}': {e}")
        return []

# ── Deduplication & merging ────────────────────────────────────────────────────

def _norm_doi(doi: str) -> str:
    doi = (doi or "").lower().strip()
    doi = re.sub(r"^https?://(dx\.)?doi\.org/", "", doi)
    return doi


def merge_papers(raw: list[dict]) -> list[dict]:
    """Deduplicate by DOI, then by title. Merge metadata from multiple sources."""
    by_doi: dict[str, dict] = {}
    no_doi: list[dict]      = []

    for p in raw:
        ndoi = _norm_doi(p.get("doi", ""))
        if ndoi:
            if ndoi in by_doi:
                ex = by_doi[ndoi]
                if len(p.get("abstract","")) > len(ex.get("abstract","")):
                    ex["abstract"] = p["abstract"]
                if (p.get("citations") or 0) > (ex.get("citations") or 0):
                    ex["citations"] = p["citations"]
                srcs = set(ex["source"].split(" + ")) | {p["source"]}
                ex["source"] = " + ".join(sorted(srcs))
                for f in ("authors","journal","year","pub_date","pmid"):
                    if not ex.get(f) and p.get(f):
                        ex[f] = p[f]
            else:
                by_doi[ndoi] = {**p, "doi": ndoi}
        else:
            no_doi.append(p)

    seen_titles: set[str] = set()
    for p in no_doi:
        key = re.sub(r'\s+', ' ', (p.get("title","")).lower().strip())[:80]
        if key and key not in seen_titles:
            seen_titles.add(key)
            by_doi[f"__notitle__{key}"] = p

    return list(by_doi.values())


CUTOFF_DATE = datetime.date(2024, 1, 1)

def _paper_date(paper: dict) -> datetime.date | None:
    """Return the best-available publication date, or None if unparseable."""
    for field in ("pub_date", "year"):
        raw = (paper.get(field) or "").strip()
        if not raw:
            continue
        for fmt, length in (("%Y-%m-%d", 10), ("%Y-%m", 7), ("%Y", 4)):
            try:
                return datetime.datetime.strptime(raw[:length], fmt).date()
            except ValueError:
                continue
    return None


def _is_recent_enough(paper: dict) -> bool:
    """Return False if the paper has a known publication date before CUTOFF_DATE."""
    d = _paper_date(paper)
    if d is None:
        return True          # no date info → keep (benefit of the doubt)
    return d >= CUTOFF_DATE


def score_paper(paper: dict, n_tags: int) -> int:
    s = min(n_tags * 10, 40)                           # tag relevance (0-40)
    s += min(int((paper.get("citations") or 0) / 5), 30)  # citations  (0-30)
    try:                                                # recency     (0-20)
        py = int((paper.get("pub_date","") or paper.get("year",""))[:4])
        cy = datetime.date.today().year
        s += 20 if py == cy else (10 if py == cy - 1 else 0)
    except (ValueError, TypeError):
        pass
    if paper.get("abstract"):                          # has abstract (0-10)
        s += 10
    return min(s, 100)

# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    today = datetime.date.today().isoformat()
    print(f"Paper fetcher — {today}  ({DAYS_BACK} days back)")
    print(f"Sources: PubMed  Semantic Scholar  Europe PMC\n")

    tags = load_tags(TAGS_FILE)
    print(f"Loaded {len(tags)} active tag(s)\n")

    all_raw: list[dict]           = []
    tag_index:    dict[str,list]  = {}  # doi/title-key → [matched tags]
    domain_index: dict[str,str]   = {}
    folder_index: dict[str,str]   = {}

    for tag_info in tags:
        tag     = tag_info["tag"]
        domain  = tag_info["domain"]
        folder  = tag_info["folder"]
        queries = [tag] + tag_info["synonyms"]
        print(f"── {tag}  [{domain}]")

        seen_pmids: set[str] = set()
        batch: list[dict]    = []

        for query in queries:
            # PubMed
            pmids = pubmed_search(query, DAYS_BACK)
            time.sleep(DELAY)
            new_pmids = [p for p in pmids if p not in seen_pmids]
            seen_pmids.update(new_pmids)
            if new_pmids:
                papers = pubmed_fetch(new_pmids)
                batch.extend(papers)
                time.sleep(DELAY)

            # Semantic Scholar
            s2 = search_semantic_scholar(query, DAYS_BACK)
            batch.extend(s2)
            time.sleep(DELAY_S2)

            # Europe PMC
            epmc = search_europe_pmc(query, DAYS_BACK)
            batch.extend(epmc)
            time.sleep(DELAY)

        # Apply mustInclude filter (all listed terms must appear in title or abstract)
        must = tag_info["mustInclude"]
        if must:
            filtered = []
            for p in batch:
                haystack = (p.get("title","") + " " + p.get("abstract","")).lower()
                if all(m.lower() in haystack for m in must):
                    filtered.append(p)
            batch = filtered

        # Tag each paper and accumulate
        for p in batch:
            ndoi = _norm_doi(p.get("doi",""))
            key  = ndoi if ndoi else f"__notitle__{p.get('title','')[:80].lower()}"
            if not key:
                continue
            p["domain"] = domain
            p["folder"] = folder
            if key not in tag_index:
                tag_index[key]    = []
                domain_index[key] = domain
                folder_index[key] = folder
            tag_index[key].append(tag)

        all_raw.extend(batch)
        print(f"   raw: {len(batch)}")

    print(f"\nTotal raw: {len(all_raw)}")
    merged = merge_papers(all_raw)
    print(f"After dedup: {len(merged)}")
    merged = [p for p in merged if _is_recent_enough(p)]
    print(f"After 2024-01-01 cutoff: {len(merged)}\n")

    today_iso = datetime.date.today().isoformat()
    for paper in merged:
        ndoi = _norm_doi(paper.get("doi",""))
        key  = ndoi if ndoi else f"__notitle__{paper.get('title','')[:80].lower()}"
        tags_for = sorted(set(tag_index.get(key, [])))
        paper["matched_tags"] = tags_for
        paper["domain"]       = domain_index.get(key, paper.get("domain","General"))
        paper["folder"]       = folder_index.get(key, paper.get("folder","General"))
        paper["score"]        = score_paper(paper, len(tags_for))
        paper["fetch_date"]   = today_iso
        paper["doi_url"]      = f"https://doi.org/{paper['doi']}" if paper.get("doi") else ""
        paper["pubmed_url"]   = (f"https://pubmed.ncbi.nlm.nih.gov/{paper['pmid']}/"
                                  if paper.get("pmid") else "")

    merged.sort(key=lambda p: p.get("score", 0), reverse=True)

    # ── Save JSON ──────────────────────────────────────────────────────────────
    OUTPUT_JSON.write_text(
        json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"papers.json  →  {len(merged)} papers")

    # ── Save CSV ───────────────────────────────────────────────────────────────
    FIELDS = [
        "score","title","authors","journal","year","pub_date",
        "doi","doi_url","pmid","pubmed_url","domain","folder",
        "matched_tags","citations","source","fetch_date","abstract",
    ]
    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, extrasaction="ignore")
        w.writeheader()
        for p in merged:
            row = dict(p)
            row["matched_tags"] = "; ".join(row.get("matched_tags", []))
            w.writerow(row)
    print(f"papers.csv   →  {OUTPUT_CSV.name}")


if __name__ == "__main__":
    main()
