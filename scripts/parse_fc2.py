#!/usr/bin/env python3
"""Parse soranari001.web.fc2.com/soramimi_data_classification.html into JSON records."""
import re, json, html, sys, os
ROOT = os.path.join(os.path.dirname(__file__), '..')
SRC = os.path.join(ROOT, 'cache', 'raw', 'fc2', 'soramimi_data_classification.html')   # already UTF-8
COLS = ['no', 'date', 'soramimi', 'rating', 'title', 'artist', 'lang', 'country', 'genre', 'released', 'category', 'poster', 'cast']

def parse():
    s = open(SRC, encoding='utf-8').read()
    body = s[s.find('<tbody'):]
    out = []
    for tr in re.findall(r'<tr[^>]*>(.*?)(?=<tr[^>]*>|</tbody>)', body, re.S):
        cells = re.split(r'<td[^>]*>', tr)[1:]
        cells = [html.unescape(re.sub(r'<[^>]+>', '', c)).strip() for c in cells]
        cells = [re.sub(r'\s*</?t[dr]>\s*', '', c).strip() for c in cells]
        if len(cells) < 6: continue
        rec = dict(zip(COLS, cells))
        m = re.match(r'(\d{4})年(\d{1,2})月(\d{1,2})日', rec['date'])
        rec['date_iso'] = '%04d-%02d-%02d' % tuple(int(x) for x in m.groups()) if m else ''
        out.append(rec)
    return out

if __name__ == '__main__':
    recs = parse()
    json.dump(recs, open(os.path.join(ROOT, 'data', 'fc2_works.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    import collections
    print('records', len(recs))
    print(collections.Counter(r['rating'] for r in recs).most_common(40))
    print('no date', sum(1 for r in recs if not r['date_iso']), [r['date'] for r in recs if not r['date_iso']][:10])
    print(recs[-1])
