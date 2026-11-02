#!/usr/bin/env python3
"""Match our works against the fc2 list and report differences."""
import sys, os, json, re, unicodedata, difflib, collections
sys.path.insert(0, os.path.dirname(__file__))
from build import rating_info, norm
ROOT = os.path.join(os.path.dirname(__file__), '..')
ours = json.load(open(os.path.join(ROOT, 'data', 'works.json'), encoding='utf-8'))
fc2 = json.load(open(os.path.join(ROOT, 'data', 'fc2_works.json'), encoding='utf-8'))

def sim(a, b): return difflib.SequenceMatcher(None, norm(a), norm(b)).ratio()
by_date = collections.defaultdict(list)
for w in ours: by_date[w['date']].append(w)
matched = {}; fc2_unmatched = []
for f in fc2:
    best = None; bs = 0
    for w in by_date.get(f['date_iso'], []):
        if w['id'] in matched: continue
        s = 0.7 * sim(w['soramimi'], f['soramimi']) + 0.3 * sim(w['artist'].split('\n')[0], f['artist'])
        if s > bs: bs, best = s, w
    if best and bs >= 0.4:
        matched[best['id']] = (f, bs)
    else:
        fc2_unmatched.append(f)
ours_unmatched = [w for w in ours if w['id'] not in matched]

fc2_prize = collections.Counter(); 
for f in fc2: fc2_prize.update(rating_info(f['rating'])[2])
our_prize = collections.Counter()
for w in ours: our_prize.update(rating_info(w['rating_raw'])[2])
print('fc2 records', len(fc2), ' ours', len(ours), ' matched', len(matched))
print('%-8s %6s %6s %6s' % ('prize', 'site', 'fc2', 'ours'))
site = {'手ぬぐい': 2266, 'ミミかき': 452, 'Tシャツ': 660, 'ジャンパー': 59}
for k in site: print('%-8s %6d %6d %6d' % (k, site[k], fc2_prize[k], our_prize[k]))

print('\n=== fc2 rows not matched to ours (%d)' % len(fc2_unmatched))
for f in fc2_unmatched: print(' ', f['no'], f['date_iso'], f['artist'][:14], '|', f['soramimi'][:30], '|', f['rating'])
print('\n=== our rows not matched to fc2 (%d)' % len(ours_unmatched))
for w in ours_unmatched: print(' ', w['date'], w['artist'][:14].replace('\n','/'), '|', w['soramimi'][:30].replace('\n','/'), '|', w['rating_raw'][:14].replace('\n','/'), '|', w['src'][5:])
print('\n=== rating differences (prize counts differ)')
diffs = []
for wid, (f, bs) in matched.items():
    w = next(x for x in ours if x['id'] == wid)
    a = rating_info(w['rating_raw'])[2]; b = rating_info(f['rating'])[2]
    if a != b: diffs.append((w, f, bs))
print(len(diffs))
for w, f, bs in diffs: print(' ', w['date'], w['artist'][:12].replace('\n','/'), '|', w['soramimi'][:24].replace('\n','/'), '| ours:', w['rating_raw'][:16].replace('\n','/'), '| fc2:', f['rating'][:24], '| %.2f' % bs, w['src'][5:])
json.dump({'fc2_unmatched': fc2_unmatched, 'ours_unmatched': [w['id'] for w in ours_unmatched]}, open(os.path.join(ROOT, 'data', 'fc2_compare.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
