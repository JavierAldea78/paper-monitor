#!/usr/bin/env python3
"""Build _site/: retroactive mustInclude filter + consistent rescore + full corpus."""
import json, csv, os, sys, datetime

if not os.path.exists('papers.json'):
    print('No papers.json found — skipping build')
    sys.exit(0)

d = json.load(open('papers.json'))
TODAY_YEAR = datetime.date.today().year

# ── Load mustInclude requirements from watchtags.csv ──────────────────────────
tag_must: dict[str, list[str]] = {}
if os.path.exists('watchtags.csv'):
    with open('watchtags.csv', newline='', encoding='utf-8') as f:
        for row in csv.DictReader(f):
            if row.get('active', 'true').strip().lower() == 'false':
                continue
            must = [m.strip() for m in row.get('mustInclude', '').split(',') if m.strip()]
            tag_must[row['tag'].strip()] = must
    print(f'Loaded {len(tag_must)} active tags from watchtags.csv')

# ── Retroactively apply mustInclude hard filter to existing corpus ────────────
# Papers from old fetches had mustInclude as a soft bonus; here we enforce it
# so spuriously-assigned tags are removed before scoring.
fixed = 0
for p in d:
    old_tags = p.get('matched_tags') or []
    if not old_tags or not tag_must:
        continue
    text = (p.get('title', '') + ' ' + (p.get('abstract') or '')).lower()
    new_tags = []
    for tag in old_tags:
        must = tag_must.get(tag, [])
        if must and not all(m.lower() in text for m in must):
            continue  # tag was spuriously assigned — strip it
        new_tags.append(tag)
    if len(new_tags) != len(old_tags):
        p['matched_tags'] = new_tags
        p['must_match']   = any(bool(tag_must.get(t)) for t in new_tags)
        fixed += 1
print(f'Retroactive mustInclude fix: {fixed} papers had spurious tags removed')


# ── Rescore ───────────────────────────────────────────────────────────────────
def rescore(paper: dict) -> int:
    n_tags = len(paper.get('matched_tags') or [])
    if n_tags == 0:
        return 0
    s = min(n_tags * 15, 60)
    try:
        py = int((paper.get('pub_date', '') or paper.get('year', ''))[:4])
        s += 25 if py == TODAY_YEAR else (15 if py == TODAY_YEAR - 1 else (5 if py == TODAY_YEAR - 2 else 0))
    except Exception:
        pass
    if paper.get('abstract'):   s += 10
    if paper.get('is_oa'):      s += 5
    if paper.get('must_match'): s += 10
    cit = paper.get('citations') or 0
    if cit >= 51:   s += 20
    elif cit >= 11: s += 10
    elif cit >= 1:  s += 5
    return s


for p in d:
    p['score'] = rescore(p)
    ab = p.get('abstract') or ''
    if len(ab) > 300:
        p['abstract'] = ab[:300].rsplit(' ', 1)[0] + '…'

d.sort(key=lambda p: p.get('score', 0), reverse=True)

# ── Write outputs ─────────────────────────────────────────────────────────────
os.makedirs('_site', exist_ok=True)
json.dump(d, open('_site/papers.json', 'w'), ensure_ascii=False)

dates = sorted(set(p.get('fetch_date', '') for p in d if p.get('fetch_date')), reverse=True)
latest = dates[0] if dates else ''
new_papers = [p for p in d if p.get('fetch_date', '') == latest]
json.dump(new_papers, open('_site/papers_new.json', 'w'), ensure_ascii=False)

fields = ['score', 'raw_score', 'title', 'authors', 'journal', 'year', 'pub_date',
          'doi', 'doi_url', 'pmid', 'pubmed_url', 'domain', 'folder',
          'matched_tags', 'must_match', 'citations', 'is_oa', 'source', 'fetch_date', 'abstract']
with open('_site/papers.csv', 'w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=fields, extrasaction='ignore')
    w.writeheader()
    for p in d:
        row = dict(p)
        row['matched_tags'] = '; '.join(row.get('matched_tags') or [])
        w.writerow(row)

relevant = sum(1 for p in d if p['score'] > 0)
top = d[0] if d else {}
print(f'corpus: {len(d)} | con score>0: {relevant} | esta semana: {len(new_papers)} ({latest})')
print(f'Top paper: score={top.get("score",0)} | {top.get("title","")[:80]}')
print(f'Top tags: {top.get("matched_tags",[])}')
