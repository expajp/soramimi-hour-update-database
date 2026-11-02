#!/usr/bin/env python3
"""Build data/artist_aliases.json: one row per spelling group with its canonical artist_key.
Canonical name = Apple Music (JP) artist name when the group resolved to an Apple artist,
otherwise the most frequent spelling on the source site (flagged unresolved).
Manual fixes go in data/artist_overrides.json: {"key": "en:...", "artist_key": "...", "apple_id": ..., "note": "..."}"""
import json, os, re, sys
sys.path.insert(0, os.path.dirname(__file__))
from artist_groups import ne
ROOT = os.path.join(os.path.dirname(__file__), '..')
COLLAB = re.compile(r'\b(feat\.?|featuring|ft\.?|with|vs\.?|meets|and his|and her|&\s*his|&\s*her|presents)\b|×|[、/]', re.I)

def clean(name):
    """Tidy a site spelling used as artist_key: drop annotations and layout spaces."""
    name = re.sub(r'\s*※.*$', '', name)
    name = re.sub(r'\s*([・＆、＋])\s*', r'\1', name)
    return name.strip(' ,，')

def main():
    groups = json.load(open(os.path.join(ROOT, 'data', 'artist_groups.json'), encoding='utf-8'))
    apple = json.load(open(os.path.join(ROOT, 'data', 'artist_apple.json'), encoding='utf-8')) if os.path.exists(os.path.join(ROOT, 'data', 'artist_apple.json')) else {}
    ov_path = os.path.join(ROOT, 'data', 'artist_overrides.json')
    overrides = {o['key']: o for o in json.load(open(ov_path, encoding='utf-8'))} if os.path.exists(ov_path) else {}
    corrected = json.load(open(os.path.join(ROOT, 'data', 'artist_corrected.json'), encoding='utf-8'))
    out = []
    for g in groups:
        a = corrected.get(g['key']) or apple.get(g['key'], {})
        term = next(iter(g['en'])) if g['key'].startswith('en:') else next(iter(g['ja']))
        row = {'key': g['key'], 'n': g['n'], 'ja': list(g['ja']), 'en': list(g['en']), 'term': term}
        resolved = bool(a.get('apple_name'))
        # a featuring / collaboration credit must not be folded into the lead artist
        if g['key'] not in corrected and resolved and COLLAB.search(term) and not COLLAB.search(a.get('apple_latin', '')):
            resolved = False; row['note'] = 'collab credit kept separate'
        if g['key'] in overrides:
            o = overrides[g['key']]
            row.update({'artist_key': o['artist_key'], 'apple_id': o.get('apple_id', ''), 'source': 'override', 'note': o.get('note', '')})
        elif resolved:
            row.update({'artist_key': a['apple_name'], 'apple_id': a['apple_id'], 'apple_latin': a['apple_latin'], 'source': 'apple', 'how': a.get('how') or 'corrected'})
        else:
            row.update({'artist_key': clean(next(iter(g['ja']), '') or term), 'apple_id': '', 'source': 'site'})
        out.append(row)
    json.dump(out, open(os.path.join(ROOT, 'data', 'artist_aliases.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    keys = {}
    for r in out: keys.setdefault(r['artist_key'], []).append(r['key'])
    print('groups', len(out), 'apple', sum(1 for r in out if r['source'] == 'apple'), 'override', sum(1 for r in out if r['source'] == 'override'), 'site', sum(1 for r in out if r['source'] == 'site'), '-> distinct artist_key', len(keys))
    merged = [(k, v) for k, v in keys.items() if len(v) > 1]
    print('merged groups:', len(merged))
    for k, v in sorted(merged, key=lambda kv: -len(kv[1]))[:30]: print(' ', k, v)

if __name__ == '__main__':
    main()
