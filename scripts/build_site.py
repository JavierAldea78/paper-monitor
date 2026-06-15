#!/usr/bin/env python3
"""Build _site/ from papers.json: top-5000 corpus + latest-week split."""
import json, csv, os, sys

if not os.path.exists('papers.json'):
    print('No papers.json found — skipping build')
    sys.exit(0)

d = json.load(open('papers.json'))
d.sort(key=lambda p: p.get('score', 0), reverse=True)

os.makedirs('_site', exist_ok=True)

# Top 5000 by score → corpus view
json.dump(d[:5000], open('_site/papers.json', 'w'), ensure_ascii=False)

# Latest fetch_date → Esta semana
dates = sorted(set(p.get('fetch_date', '') for p in d if p.get('fetch_date')), reverse=True)
latest = dates[0] if dates else ''
new_papers = [p for p in d if p.get('fetch_date', '') == latest]
json.dump(new_papers, open('_site/papers_new.json', 'w'), ensure_ascii=False)

# CSV download (top 5000)
fields = [
    'score', 'raw_score', 'title', 'authors', 'journal', 'year', 'pub_date',
    'doi', 'doi_url', 'pmid', 'pubmed_url', 'domain', 'folder',
    'matched_tags', 'must_match', 'citations', 'is_oa', 'source', 'fetch_date', 'abstract',
]
with open('_site/papers.csv', 'w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=fields, extrasaction='ignore')
    w.writeheader()
    for p in d[:5000]:
        row = dict(p)
        row['matched_tags'] = '; '.join(row.get('matched_tags') or [])
        w.writerow(row)

print(f'corpus: {len(d[:5000])} | esta semana: {len(new_papers)} ({latest}) | total: {len(d)}')
