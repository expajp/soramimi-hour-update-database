#!/usr/bin/env python3
"""Build the soramimi database (JSON/CSV/SQLite) from cached pages."""
import sys, os, re, json, csv, unicodedata, difflib, sqlite3, collections
sys.path.insert(0, os.path.dirname(__file__))
import parse_year
from artist_groups import key_of

ROOT = os.path.join(os.path.dirname(__file__), '..')
U8 = os.path.join(ROOT, 'cache', 'utf8')
OUT = os.path.join(ROOT, 'data')
os.makedirs(OUT, exist_ok=True)

RANK = ['評価なし', '手ぬぐい', 'ミミかき', 'Tシャツ', 'ジャンパー']
NONE_WORDS = {'', '－', '―', '-', 'なし', '賞品無し', '無し', '評価なし', '評価し忘れ', '？', '?'}

def norm(s):
    s = unicodedata.normalize('NFKC', s or '')
    return re.sub(r'\s+', '', s)

def rating_info(raw):
    """-> (rating, other, prize_counts)"""
    n = norm(raw)
    n_std = n.replace('Ｔ', 'T').replace('ミミカキ', 'ミミかき')
    n_orig = n_std
    counts = collections.Counter()
    n_std = n_std.replace('ジャケット', 'ジャンパー')
    if re.search(r'無し|なし', n_std) and n_std not in NONE_WORDS:
        n_std = ''   # e.g. 「手ぬぐい以下より賞品なし」「Tシャツと手ぬぐい↓無し」: no prize was given   # 2015/10/30: ジャンパー掛けのジャケット（サイトのジャンパー一覧に含まれる）
    for kw, key in (('ジャンパー', 'ジャンパー'), ('Tシャツ', 'Tシャツ'), ('ミミかき', 'ミミかき'), ('手ぬぐい', '手ぬぐい')):
        c = n_std.count(kw)
        if c:
            m = re.search(kw + r'(?:×|x)(\d+)', n_std)
            counts[key] = int(m.group(1)) if m else c
    rating = '評価なし'
    for r in reversed(RANK[1:]):
        if counts.get(r): rating = r; break
    if n_orig in RANK or n_orig in NONE_WORDS:
        other = ''
    else:
        other = re.sub(r'\s*\n\s*', ' ', (raw or '').strip())
    return rating, other, counts

HOGAKU = '「あなたにも音楽を」邦楽回'
SORAYUMI = '空ユミ（ユーミン初登場SP内コーナー）'

def load_specials():
    """Parse special.htm -> list of (name, date, url_basename)."""
    src = open(os.path.join(U8, 'special.htm'), encoding='utf-8').read()
    out = []
    for m in re.finditer(r'<a[^>]*href="[^"]*special/([^"]+)"[^>]*>(.*?)</a>(.*?)(?=<a |$)', src, re.S | re.I):
        fn, inner, tail = m.group(1), m.group(2), m.group(3)
        name = re.sub(r'<[^>]+>', '', inner)
        name = norm(name)
        d = re.search(r'(\d{4})年(\d{1,2})月(\d{1,2})日', tail)
        if d:
            out.append({'file': fn, 'name': name, 'date': '%04d-%02d-%02d' % tuple(int(x) for x in d.groups())})
    # specials not listed in special.htm (linked from past/2021main.htm and the home page)
    out += [
        {'file': '2021spring.htm', 'name': "空耳アワー'21スプリングコレクション", 'date': '2021-03-12'},
        {'file': '2021summer.htm', 'name': "空耳アワー'21サマーコレクション", 'date': '2021-09-10'},
        {'file': '2022spring.htm', 'name': "空耳アワー'22スプリングコレクション", 'date': '2022-03-04'},
        {'file': '2022yuming.htm', 'name': 'タモリ倶楽部SP ユーミン初登場で空耳やっちゃいました', 'date': '2022-10-04'},
        {'file': '2023.htm', 'name': '頑張ったけどスベったらゴメンねALL新作空耳アワー', 'date': '2023-03-24'},
        # corners treated as specials at the user's request (no page of their own)
        {'file': '', 'name': HOGAKU, 'date': '1992-04-03'},
        {'file': '', 'name': SORAYUMI, 'date': '2022-10-04'},
    ]
    return out

def year_totals(src):
    txt = re.sub(r'<[^>]+>', ' ', src)
    txt = re.sub(r'\s+', ' ', txt)
    res = {}
    for kw, key in (('特製手ぬぐい', '手ぬぐい'), ('特製ソラミミかき', 'ミミかき'), ('特製スタッフＴシャツ', 'Tシャツ'), ('特製ｽﾀｯﾌｼﾞｬﾝﾊﾟｰ', 'ジャンパー'), ('特製スタッフジャンパー', 'ジャンパー')):
        m = re.search(re.escape(kw) + r'\s*(\d+)', txt)
        if m: res[key] = int(m.group(1))
    return res

def main():
    works = []
    totals = {}
    # --- year pages
    for y in range(1992, 2022):
        path = os.path.join(U8, 'past', '%dmain.htm' % y)
        src = open(path, encoding='utf-8').read()
        totals[y] = year_totals(src)
        prev_month = None
        for r in parse_year.parse(path):
            if r.get('kind') != 'work': continue
            if not r['date']:
                raise SystemExit('no date %s %s' % (path, r))
            m, d = r['date']
            yy = y
            if y == 2021 and m <= 10 and prev_month is not None and m > prev_month: pass
            w = dict(src='past/%dmain.htm' % y, date='%04d-%02d-%02d' % (yy, m, d), artist=r.get('artist',''), title=r.get('title',''),
                     lyric=r.get('lyric',''), soramimi=r.get('soramimi',''), rating_raw=r.get('rating',''), specials=[], award='')
            if y == 1992 and (r.get('green') or '西郷輝彦' in w['artist']):
                # 「あなたにも音楽を」時代の邦楽作品（空耳を意図した作品ではない）。特番扱いにする
                w['specials'].append(HOGAKU)
                if not rating_info(w['rating_raw'])[2] and norm(w['rating_raw']) not in NONE_WORDS and not w['lyric']:
                    w['lyric'], w['rating_raw'] = w['rating_raw'], ''   # 4-column table: the last column holds the original lyric
            works.append(w)
    # 2021main 2022 section: dates listed under ～2022年～ heading; handle: entries with date before '2021' heading
    # (2021main has only one work table: 2021-06-18)
    # --- specials
    specials = load_specials()
    reruns = []
    RETRO = {'soramimi-return.htm', '21century.htm'}   # best-of shows: every row is a rerun
    def sim(a, b): return difflib.SequenceMatcher(None, norm(a), norm(b)).ratio()
    def best_global(r, before):
        best = None; bs = 0
        for w in works:
            if w['date'] >= before: continue
            s = 0.6 * sim(w['soramimi'], r.get('soramimi','')) + 0.4 * sim(w['artist'], r.get('artist',''))
            if s > bs: bs, best = s, w
        return best, bs
    for sp in sorted(specials, key=lambda s: s['date']):
        if not sp['file']: continue
        path = os.path.join(U8, 'special', sp['file'])
        if not os.path.exists(path): print('missing', path); continue
        for r in parse_year.parse(path):
            if r.get('kind') == 'work' and not (r.get('artist') or '').strip():
                if sp['file'] == '2022yuming.htm':
                    r = dict(r, artist='松任谷由実', sorayumi=True)
                elif sp['file'] == 'award2015-pre.htm':
                    r = dict(r, artist='イディナ・メンゼル\n(Idina Menzel)', title='レット・イット・ゴー\n(Let It Go)')
                elif sp['file'] == 'award2006-pre.htm':
                    r = dict(r, artist='メガデス', kind='rerun', airdate='')
            if r.get('kind') == 'work' and (sp['file'] in RETRO or not norm(r.get('rating',''))):
                # retrospective row, or a row without a prize: a rerun if it matches an earlier work
                b, bs = best_global(r, sp['date'])
                if b and bs >= (0.5 if sp['file'] in RETRO else 0.9):
                    r = dict(r, kind='rerun', airdate=b['date'].replace('-', '/'))
                elif sp['file'] in RETRO:
                    print('retro unmatched', sp['file'], r.get('artist'), r.get('soramimi'), round(bs, 2))
                    r = dict(r, kind='rerun', airdate='')
            if r.get('kind') == 'rerun' and re.search(r'ボツ|未公開', r.get('airdate') or ''):
                r = dict(r, kind='work', rating='ボツネタ')   # unaired work shown for the first time in the special
            if r.get('kind') == 'work':
                works.append(dict(src='special/' + sp['file'], date=sp['date'], artist=r.get('artist',''), title=r.get('title',''),
                                  lyric=r.get('lyric',''), soramimi=r.get('soramimi',''), rating_raw=r.get('rating',''),
                                  specials=[sp['name']] + ([SORAYUMI] if r.get('sorayumi') else []), award='', section=r.get('section')))
            elif r.get('kind') == 'rerun':
                reruns.append(dict(special=sp, r=r))
    works.sort(key=lambda w: w['date'])
    for i, w in enumerate(works, 1): w['id'] = i
    # --- match reruns
    by_date = collections.defaultdict(list)
    for w in works: by_date[w['date']].append(w)
    unmatched = []
    for rr in reruns:
        r = rr['r']; sp = rr['special']
        m = parse_year.AIRDATE_RE.search(r.get('airdate') or '')
        cands = []
        if m:
            key = '%04d-%02d-%02d' % tuple(int(x) for x in m.groups())
            cands = by_date.get(key, [])
        best = None; bs = 0
        for w in cands:
            s = 0.6 * sim(w['soramimi'], r.get('soramimi','')) + 0.4 * sim(w['artist'], r.get('artist',''))
            if s > bs: bs, best = s, w
        thr = 0.45
        if not best or bs < thr:
            best, bs = best_global(r, sp['date']); thr = 0.7
        if best and bs >= thr:
            if sp['name'] not in best['specials']: best['specials'].append(sp['name'])
        else:
            unmatched.append(dict(special=sp['name'], airdate=r.get('airdate'), artist=r.get('artist'), soramimi=r.get('soramimi'), best=(best['soramimi'] if best else None), score=round(bs,2)))
    # --- manual overrides (prizes stated only in the page text)
    ov_path = os.path.join(ROOT, 'data', 'overrides.json')
    if os.path.exists(ov_path):
        for o in json.load(open(ov_path, encoding='utf-8')):
            found = [w for w in works if w['date'] == o['date'] and norm(o['soramimi']) in norm(w['soramimi'])]
            if len(found) != 1: print('override match problem', o, len(found))
            for w in found: w['rating_raw'] = o['rating_raw']
    # --- cross-check with soranari001.web.fc2.com (secondary source)
    fc2_path = os.path.join(ROOT, 'data', 'fc2_works.json')
    fc2_filled = 0
    if os.path.exists(fc2_path):
        fc2 = json.load(open(fc2_path, encoding='utf-8'))
        by_date = collections.defaultdict(list)
        for w in works: by_date[w['date']].append(w)
        taken = set()
        for f in fc2:
            best = None; bs = 0
            for w in by_date.get(f['date_iso'], []):
                if w['id'] in taken: continue
                sc = 0.7 * sim(w['soramimi'], f['soramimi']) + 0.3 * sim(w['artist'].split('\n')[0], f['artist'])
                if sc > bs: bs, best = sc, w
            if best and bs >= 0.4:
                taken.add(best['id'])
                best['fc2_no'] = f['no']; best['rating_fc2'] = f['rating']
                _, other, counts = rating_info(best['rating_raw'])
                blank = not counts and (not norm(best['rating_raw']) or re.search(r'[A-Za-z]{3,}', best['rating_raw']))
                if blank and rating_info(f['rating'])[2]:
                    # the table on the primary site has no prize column (special pages) or shows the lyric (1992 4-column tables)
                    best['rating_raw'] = f['rating']; best['rating_source'] = 'fc2'; fc2_filled += 1
        print('fc2 matched', len(taken), 'of', len(fc2), '; ratings filled from fc2:', fc2_filled)
    for w in works:
        w.setdefault('fc2_no', ''); w.setdefault('rating_fc2', ''); w.setdefault('rating_source', 'site')
    # --- rating
    prize = collections.Counter(); prize_by_year = collections.defaultdict(collections.Counter)
    for w in works:
        w['rating'], w['rating_other'], counts = rating_info(w['rating_raw'])
        w['_prizes'] = dict(counts)
        prize.update(counts); prize_by_year[int(w['date'][:4])].update(counts)
    # --- awards (grand prix) from manual file
    awards_path = os.path.join(ROOT, 'data', 'awards.json')
    if os.path.exists(awards_path):
        for a in json.load(open(awards_path, encoding='utf-8')):
            found = [w for w in works if w['date'] < a['special_date'] and norm(a['soramimi']) in norm(w['soramimi']) and (not a.get('artist') or norm(a['artist']) in norm(w['artist']))]
            if len(found) != 1: print('award match problem', a, len(found))
            for w in found: w['award'] = a['special']
    works.sort(key=lambda w: w['date'])
    # --- artist_key (canonical artist name, see scripts/artist_aliases.py)
    alias_path = os.path.join(ROOT, 'data', 'artist_aliases.json')
    aliases = {a['key']: a for a in json.load(open(alias_path, encoding='utf-8'))} if os.path.exists(alias_path) else {}
    fixes = {f['from']: f['to'] for f in json.load(open(os.path.join(ROOT, 'data', 'artist_spelling_fixes.json'), encoding='utf-8'))}
    for w in works:
        a = aliases.get(key_of(fixes.get(w['artist'], w['artist'])))
        w['artist_key'] = a['artist_key'] if a else re.sub(r'\s+', ' ', w['artist'].replace('\n', ' '))
    # --- output
    with open(os.path.join(OUT, 'works.json'), 'w', encoding='utf-8') as f:
        json.dump([{k: v for k, v in w.items() if not k.startswith('_')} for w in works], f, ensure_ascii=False, indent=1)
    cols = ['id', 'date', 'artist', 'artist_key', 'title', 'lyric', 'soramimi', 'rating', 'rating_other', 'specials', 'award', 'rating_raw', 'rating_source', 'rating_fc2', 'fc2_no', 'src']
    with open(os.path.join(OUT, 'works.csv'), 'w', encoding='utf-8', newline='') as f:
        wr = csv.writer(f); wr.writerow(cols)
        for w in works: wr.writerow([('|'.join(w[c]) if c == 'specials' else w.get(c, '')) for c in cols])
    dbp = os.path.join(OUT, 'soramimi.sqlite')
    if os.path.exists(dbp): os.remove(dbp)
    con = sqlite3.connect(dbp)
    con.executescript('''
    CREATE TABLE works(id INTEGER PRIMARY KEY, date TEXT, artist TEXT, artist_key TEXT, title TEXT, lyric TEXT, soramimi TEXT, rating TEXT, rating_other TEXT, award TEXT, rating_raw TEXT, rating_source TEXT, rating_fc2 TEXT, fc2_no TEXT, src TEXT);
    CREATE TABLE specials(name TEXT PRIMARY KEY, file TEXT, date TEXT);
    CREATE TABLE work_specials(work_id INTEGER, special TEXT);
    CREATE TABLE artists(artist_key TEXT, apple_id TEXT, source TEXT, spelling TEXT, n INTEGER);
    ''')
    con.executemany('INSERT INTO artists VALUES (?,?,?,?,?)', [(a['artist_key'], str(a.get('apple_id') or ''), a['source'], sp, a['n']) for a in aliases.values() for sp in a['ja']])
    con.executemany('INSERT INTO works VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)', [(w['id'], w['date'], w['artist'], w['artist_key'], w['title'], w['lyric'], w['soramimi'], w['rating'], w['rating_other'], w['award'], w['rating_raw'], w['rating_source'], w['rating_fc2'], w['fc2_no'], w['src']) for w in works])
    con.executemany('INSERT INTO specials VALUES (?,?,?)', [(s['name'], s['file'], s['date']) for s in specials])
    con.executemany('INSERT INTO work_specials VALUES (?,?)', [(w['id'], s) for w in works for s in w['specials']])
    con.commit(); con.close()
    json.dump(unmatched, open(os.path.join(OUT, 'unmatched_reruns.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    # --- report
    site = {'手ぬぐい': 2266, 'ミミかき': 452, 'Tシャツ': 660, 'ジャンパー': 59}
    fc2_prize = collections.Counter()
    if os.path.exists(fc2_path):
        for f in fc2: fc2_prize.update(rating_info(f['rating'])[2])
    print('works:', len(works), ' reruns:', len(reruns), ' unmatched:', len(unmatched))
    print('%-8s %6s %6s %6s %6s' % ('prize', 'site', 'fc2', 'ours', 'diff'))
    for k in site: print('%-8s %6d %6d %6d %6d' % (k, site[k], fc2_prize[k], prize[k], prize[k] - site[k]))
    print('--- per year (site / ours)')
    for y in sorted(prize_by_year):
        t = totals.get(y, {})
        print(y, ' '.join('%s:%s/%d' % (k, t.get(k, '?'), prize_by_year[y][k]) for k in site))

if __name__ == '__main__':
    main()
