#!/usr/bin/env python3
"""Group artist spellings found in works.json -> data/artist_groups.json"""
import json, re, unicodedata, collections, os
ROOT = os.path.join(os.path.dirname(__file__), '..')

def split(a):
    a = re.sub(r'\s+', ' ', a.replace('\n', ' ')).strip()
    m = re.match(r'^(.*?)\s*[\(（]([^()（）]+)[\)）]\s*$', a)
    if m and re.search(r'[A-Za-z]', m.group(2)):
        return m.group(1).strip(), m.group(2).strip()
    return a, ''

def nj(s):
    s = unicodedata.normalize('NFKC', s)
    return re.sub(r'[\s・･、,.．&＆\-ー－「」『』“”"\'’!！?？]', '', s).lower()

def ne(s):
    s = unicodedata.normalize('NFKD', s)
    s = ''.join(c for c in s if not unicodedata.combining(c))
    s = s.lower().replace('&', 'and').replace('+', 'and')
    s = re.sub(r'^the\s+', '', s.strip())
    return re.sub(r'[^a-z0-9]', '', s)

def key_of(a):
    j, e = split(a)
    return ('en:' + ne(e)) if e and ne(e) else ('ja:' + nj(j))

def main():
    works = json.load(open(os.path.join(ROOT, 'data', 'works.json'), encoding='utf-8'))
    fp = os.path.join(ROOT, 'data', 'artist_spelling_fixes.json')
    fixes = {f['from']: f['to'] for f in json.load(open(fp, encoding='utf-8'))} if os.path.exists(fp) else {}
    for w in works: w['artist'] = fixes.get(w['artist'], w['artist'])
    groups = collections.defaultdict(lambda: {'ja': collections.Counter(), 'en': collections.Counter(), 'n': 0})
    for w in works:
        j, e = split(w['artist'])
        g = groups[key_of(w['artist'])]
        g['ja'][j] += 1
        if e: g['en'][e] += 1
        g['n'] += 1
    out = []
    for k, g in sorted(groups.items(), key=lambda kv: -kv[1]['n']):
        out.append({'key': k, 'n': g['n'], 'ja': dict(g['ja'].most_common()), 'en': dict(g['en'].most_common())})
    json.dump(out, open(os.path.join(ROOT, 'data', 'artist_groups.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('groups', len(out), ' with english', sum(1 for o in out if o['key'].startswith('en:')), ' japanese only', sum(1 for o in out if o['key'].startswith('ja:')))
    print('multi-ja groups', sum(1 for o in out if len(o['ja']) > 1))

if __name__ == '__main__':
    main()
