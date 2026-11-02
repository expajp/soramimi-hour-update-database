#!/usr/bin/env python3
"""Generate docs/data.json, the compact data file loaded by the static site."""
import json, os, re, sqlite3

ROOT = os.path.join(os.path.dirname(__file__), '..')
RATINGS = ['評価なし', '手ぬぐい', 'ミミかき', 'Tシャツ', 'ジャンパー']

def main():
    works = json.load(open(os.path.join(ROOT, 'data', 'works.json'), encoding='utf-8'))
    aliases = json.load(open(os.path.join(ROOT, 'data', 'artist_aliases.json'), encoding='utf-8'))
    con = sqlite3.connect(os.path.join(ROOT, 'data', 'soramimi.sqlite'))
    dates = dict(con.execute('SELECT name, date FROM specials'))
    used = {s for w in works for s in w['specials']}
    specials = sorted(used, key=lambda s: (dates.get(s) or '9999', s))
    index = {s: i for i, s in enumerate(specials)}

    spellings = {}
    for a in aliases:
        spellings.setdefault(a['artist_key'], set()).update(a['ja'] + a['en'])
    spellings.pop('', None)

    rows = []
    for w in works:
        rows.append([
            w['id'], w['date'], re.sub(r'\s+', ' ', w['artist']).strip(), w['artist_key'],
            w['title'].strip(), w['lyric'].strip(), w['soramimi'].strip(),
            RATINGS.index(w['rating']), w['rating_other'],
            [index[s] for s in w['specials']], w['award'],
        ])
    data = {
        'ratings': RATINGS,
        'specials': [{'name': s, 'date': dates.get(s) or ''} for s in specials],
        'spellings': {k: sorted(v) for k, v in spellings.items()},
        'works': rows,
    }
    with open(os.path.join(ROOT, 'docs', 'data.json'), 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, separators=(',', ':'))
    print('works', len(rows), 'specials', len(specials), 'artists', len(spellings))

if __name__ == '__main__':
    main()
