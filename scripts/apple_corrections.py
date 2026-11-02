#!/usr/bin/env python3
"""Re-resolve groups whose site spelling is misspelled, abbreviated or annotated.
Reads data/artist_corrections.json ({"key", "term"}) and writes data/artist_corrected.json."""
import json, os, sys
sys.path.insert(0, os.path.dirname(__file__))
from artist_groups import ne
from apple_lookup import search, page_name, sim, ROOT

def main():
    items = json.load(open(os.path.join(ROOT, 'data', 'artist_corrections.json'), encoding='utf-8'))
    groups = {g['key'] for g in json.load(open(os.path.join(ROOT, 'data', 'artist_groups.json'), encoding='utf-8'))}
    out = {}
    for it in items:
        if it['key'] not in groups:
            print('UNKNOWN GROUP', it['key']); continue
        res = search(it['term']) or []
        pick = next((r for r in res if ne(r['artistName']) == ne(it['term'])), None)
        if not pick and res and sim(ne(res[0]['artistName']), ne(it['term'])) >= 0.85: pick = res[0]
        if not pick:
            print('MISS', it['key'], it['term'], [r['artistName'] for r in res[:4]], flush=True); continue
        name = page_name(pick['artistId'])
        out[it['key']] = {'apple_id': pick['artistId'], 'apple_name': name, 'apple_latin': pick['artistName'], 'term': it['term']}
        print('OK', it['key'], '->', pick['artistName'], '/', name, flush=True)
    json.dump(out, open(os.path.join(ROOT, 'data', 'artist_corrected.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

if __name__ == '__main__':
    main()
