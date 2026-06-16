#!/usr/bin/env python3
"""Build _site/ from papers.json: full corpus with consistent rescore + esta-semana split."""
import json, csv, os, sys, datetime

if not os.path.exists('papers.json'):
    print('No papers.json found — skipping build')
    sys.exit(0)

d = json.load(open('papers.json'))
TODAY_YEAR = datetime.date.today().year


def rescore(paper: dict) -> int:
    """Consistent scoring: papers with 0 matched tags score 0."""
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
print(f'corpus: {len(d)} | con tags (score>0): {relevant} | esta semana: {len(new_papers)} ({latest})')
