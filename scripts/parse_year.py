#!/usr/bin/env python3
"""Parse a year page (past/YYYYmain.htm) or special page into records (JSON lines)."""
import sys, re, json, html
from html.parser import HTMLParser

DATE_RE = re.compile(r'(\d{1,2})\s*月\s*(\d{1,2})\s*日')
AIRDATE_RE = re.compile(r'(\d{4})\s*[/／年.]\s*(\d{1,2})\s*[/／月.]\s*(\d{1,2})')
HEADER_KEYS = {'artist': 'アーティスト', 'title': '曲名', 'soramimi': '空耳', 'lyric': '原詞', 'rating': '評価', 'airdate': '放送', 'intro': 'イントロ歌詞'}

class P(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tables = []   # stack: each {'rows': [], 'cur_row': None, 'cur_cell': None}
        self.records = []
        self.last_date = None
        self.last_date_src = None
        self.text_buf = []  # outside-cell text for date detection
        self.in_script = False
        self.anchor_names = []
    # --- helpers
    def cur(self):
        return self.tables[-1] if self.tables else None
    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in ('script', 'style'):
            self.in_script = True
        if tag == 'table':
            self.tables.append({'rows': [], 'cur_row': None, 'cur_cell': None, 'header': None, 'date': self.last_date,
                                'border': (a.get('border') or '').strip(), 'nrows': 0})
        elif tag == 'tr' and self.cur():
            t = self.cur(); t['cur_row'] = []
        elif tag in ('td', 'th') and self.cur():
            t = self.cur()
            if t['cur_row'] is None: t['cur_row'] = []
            try: rs = int(a.get('rowspan', 1) or 1)
            except ValueError: rs = 1
            t['cur_cell'] = {'text': [], 'colspan': int(a.get('colspan', 1) or 1), 'rowspan': rs}
        elif tag in ('font', 'span') and re.search(r'008000|green', (a.get('color') or '') + (a.get('style') or ''), re.I):
            t = self.cur()
            if t and t['cur_cell'] is not None: t['cur_cell']['green'] = True
        elif tag == 'br':
            t = self.cur()
            if t and t['cur_cell'] is not None: t['cur_cell']['text'].append('\n')
            else: self.text_buf.append('\n')
        elif tag == 'a' and a.get('name'):
            m = re.fullmatch(r'(\d{1,2})(\d{2})', a['name'].strip())
            if m: self.anchor_names.append((int(m.group(1)), int(m.group(2))))
        elif tag in ('p', 'div', 'h1', 'h2', 'h3', 'h4', 'tr', 'li'):
            self.text_buf.append('\n')
    def handle_endtag(self, tag):
        if tag in ('script', 'style'):
            self.in_script = False
        t = self.cur()
        if tag in ('td', 'th') and t and t['cur_cell'] is not None:
            txt = ''.join(t['cur_cell']['text'])
            t['cur_row'].append({'text': clean(txt), 'colspan': t['cur_cell']['colspan'], 'rowspan': t['cur_cell']['rowspan'], 'green': t['cur_cell'].get('green', False)})
            t['cur_cell'] = None
        elif tag == 'tr' and t and t['cur_row'] is not None:
            self.finish_row(t)
        elif tag == 'table' and t:
            if t['cur_cell'] is not None:
                self.handle_endtag('td')
            if t['cur_row']: self.finish_row(t)
            self.tables.pop()
        elif tag in ('p', 'div', 'h1', 'h2', 'h3', 'h4', 'li'):
            self.text_buf.append('\n')
    def handle_data(self, data):
        if self.in_script: return
        t = self.cur()
        if t and t['cur_cell'] is not None:
            t['cur_cell']['text'].append(data)
        else:
            self.text_buf.append(data)
            self.scan_date()
    def scan_date(self):
        # look at last line fragments for a date
        s = ''.join(self.text_buf[-6:])
        ms = list(DATE_RE.finditer(s))
        if not ms: return
        m = ms[-1]
        self.last_date = (int(m.group(1)), int(m.group(2)))
    def finish_row(self, t):
        row = t['cur_row']; t['cur_row'] = None
        # apply pending rowspans from earlier rows
        pend = t.setdefault('pending', {})
        if pend:
            merged = []; it = iter(row); i = 0
            total = len(row) + len(pend)
            while i < total:
                if i in pend:
                    merged.append({'text': pend[i][1], 'colspan': 1, 'rowspan': 1}); pend[i] = (pend[i][0]-1, pend[i][1])
                    if pend[i][0] <= 0: del pend[i]
                else:
                    try: merged.append(next(it))
                    except StopIteration: break
                i += 1
            row = merged
        for i, c in enumerate(row):
            if c.get('rowspan', 1) > 1:
                pend[i] = (c['rowspan']-1, c['text'])
        texts = [c['text'] for c in row]
        greens = [c.get('green', False) for c in row]
        joined = ' '.join(texts)
        t['nrows'] += 1
        if t['header'] is None:
            if is_header(texts):
                hdr = {}
                for i, c in enumerate(texts):
                    for key, kw in HEADER_KEYS.items():
                        if kw in c and key not in hdr:
                            hdr[key] = i
                            break
                t['header'] = hdr
                t['header_texts'] = texts
                t['ncols'] = len(texts)
                t['date'] = self.last_date
                if 'rating' in hdr: self.last_header = hdr
                return
            # header-less data table: border=1 and first row has 4+ cells
            if len(texts) <= 1 and joined.strip():
                t['section'] = joined.strip(); return
            if t['border'] != '0' and len(texts) >= 4:
                # drop leading empty cells (spacer columns)
                lead = 0
                while lead < len(texts) - 4 and not texts[lead]: lead += 1
                t['skip_lead'] = lead
                texts = texts[lead:]
                hdr = getattr(self, 'last_header', None)
                has_date = any(AIRDATE_RE.search(x) for x in texts[3:])
                if hdr is None or 'artist' not in hdr or max(hdr.values()) + 1 != len(texts) or (has_date and 'airdate' not in hdr):
                    hdr = None
                    if len(texts) == 5 and AIRDATE_RE.search(texts[4]):
                        hdr = {'artist': 1, 'title': 2, 'soramimi': 3, 'airdate': 4}   # guest-pick tables
                    elif len(texts) == 5:
                        hdr = dict(zip(['artist','title','soramimi','lyric','rating'], range(5)))
                    elif len(texts) == 4:
                        if any(AIRDATE_RE.search(x) for x in texts[3:]):
                            hdr = dict(zip(['artist','title','soramimi','airdate'], range(4)))
                        elif re.search(r'[A-Za-z]{3,}', texts[3]) and not re.search(r'手ぬぐい|シャツ|ミミかき|ジャンパー', texts[3]):
                            hdr = dict(zip(['artist','title','soramimi','lyric'], range(4)))
                        else:
                            hdr = dict(zip(['artist','title','soramimi','rating'], range(4)))
                if hdr is None:
                    return
                t['header'] = hdr
                t['ncols'] = len(texts)
                t['date'] = self.last_date
                t['headerless'] = True
            else:
                return
        hdr = t['header']
        if is_header(texts):
            return
        if t.get('skip_lead'):
            texts = texts[t['skip_lead']:]
        if len(texts) != t['ncols'] or all(x == '' for x in texts):
            # section / note rows
            if joined.strip():
                if len(texts) == 1 or sum(1 for x in texts if x) == 1:
                    t['section'] = joined.strip()
                else:
                    self.records.append({'_note': joined.strip(), 'date': t['date']})
            return
        rec = {k: texts[i] for k, i in hdr.items()}
        rec['_texts'] = texts
        rec['green'] = any(greens)
        rec['date'] = t['date']
        rec['section'] = t.get('section')
        rec['header_texts'] = t.get('header_texts')
        rec['kind'] = 'rerun' if 'airdate' in hdr else ('intro' if 'intro' in hdr else 'work')
        if any(('英語' in h or '日本語' in h) for h in (t.get('header_texts') or [])): rec['kind'] = 'other'
        if t.get('headerless'): rec['_headerless'] = True
        self.records.append(rec)

def is_header(texts):
    n = 0
    for c in texts:
        c2 = c.replace(' ', '')
        if len(c2) <= 12 and any(kw in c2 for kw in HEADER_KEYS.values()):
            n += 1
    return n >= 2

def clean(s):
    s = s.replace('\xa0', ' ').replace('　', ' ')
    lines = [re.sub(r'[ \t\r]+', ' ', l).strip() for l in s.split('\n')]
    lines = [l for l in lines if l]
    return '\n'.join(lines)

def parse(path):
    p = P()
    p.feed(open(path, encoding='utf-8').read())
    return p.records

if __name__ == '__main__':
    for path in sys.argv[1:]:
        for r in parse(path):
            r['_src'] = path
            print(json.dumps(r, ensure_ascii=False))
