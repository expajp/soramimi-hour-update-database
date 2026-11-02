#!/usr/bin/env python3
"""Resolve artist groups to Apple Music (JP) artist names. Resumable; results cached under cache/apple/."""
import json, os, re, sys, time, hashlib, difflib, unicodedata, urllib.request, urllib.parse, html
sys.path.insert(0, os.path.dirname(__file__))
from artist_groups import ne, nj
ROOT = os.path.join(os.path.dirname(__file__), '..')
CACHE = os.path.join(ROOT, 'cache', 'apple')
OUT = os.path.join(ROOT, 'data', 'artist_apple.json')
UA = 'Mozilla/5.0 (soramimi-db-builder; cached, low-rate)'
DELAY = 3.2

def cached(kind, key, fetch):
    p = os.path.join(CACHE, kind, hashlib.md5(key.encode()).hexdigest() + '.json')
    if os.path.exists(p):
        return json.load(open(p, encoding='utf-8'))
    for attempt in range(4):
        try:
            data = fetch()
            break
        except Exception as e:
            print('  retry', kind, key, e, flush=True); time.sleep(10 * (attempt + 1)); data = None
    if data is None: return None
    json.dump(data, open(p, 'w', encoding='utf-8'), ensure_ascii=False)
    time.sleep(DELAY)
    return data

def search(term):
    def f():
        q = urllib.parse.urlencode({'term': term, 'entity': 'musicArtist', 'country': 'jp', 'limit': 8})
        req = urllib.request.Request('https://itunes.apple.com/search?' + q, headers={'User-Agent': UA})
        return json.load(urllib.request.urlopen(req, timeout=30))['results']
    return cached('search', term, f)

def page_name(artist_id):
    def f():
        req = urllib.request.Request('https://music.apple.com/jp/artist/%d' % artist_id, headers={'User-Agent': UA, 'Accept-Language': 'ja-JP'})
        body = urllib.request.urlopen(req, timeout=30).read().decode('utf-8', 'replace')
        m = re.search(r'<title>([^<]*)</title>', body)
        t = html.unescape(m.group(1)) if m else ''
        return {'name': t}
    r = cached('page', str(artist_id), f)
    if not r: return ''
    t = r['name'].replace('\xa0', ' ')
    t = re.sub(r'\s*-\s*Apple Music.*$', '', t).strip().lstrip('\u200e').strip()
    return t

def sim(a, b): return difflib.SequenceMatcher(None, a, b).ratio()

def main():
    groups = json.load(open(os.path.join(ROOT, 'data', 'artist_groups.json'), encoding='utf-8'))
    out = json.load(open(OUT, encoding='utf-8')) if os.path.exists(OUT) else {}
    for i, g in enumerate(groups):
        if g['key'] in out: continue
        is_en = g['key'].startswith('en:')
        term = next(iter(g['en'])) if is_en else next(iter(g['ja']))
        res = search(term) or []
        pick = None; how = ''
        for r in res:
            n = ne(r['artistName'])
            if is_en and n == ne(term): pick, how = r, 'exact'; break
        if not pick and res:
            r = res[0]
            if is_en:
                s = sim(ne(r['artistName']), ne(term))
                if s >= 0.85: pick, how = r, 'fuzzy%.2f' % s
            else:
                pick, how = r, 'ja-candidate'
        rec = {'key': g['key'], 'term': term, 'n': g['n'], 'ja': g['ja'], 'en': g['en']}
        if pick:
            name = page_name(pick['artistId'])
            ok = True
            if not is_en:
                # verify the Japanese page name against our spelling
                ok = sim(nj(name), nj(term)) >= 0.6 or nj(name) == nj(term)
            if ok and name:
                rec.update({'apple_id': pick['artistId'], 'apple_name': name, 'apple_latin': pick['artistName'], 'how': how})
        out[g['key']] = rec
        if i % 20 == 0:
            json.dump(out, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
            print('%d/%d %s -> %s' % (i, len(groups), term, rec.get('apple_name', '(unresolved)')), flush=True)
    json.dump(out, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('done', len(out), 'resolved', sum(1 for r in out.values() if r.get('apple_name')))

if __name__ == '__main__':
    main()
